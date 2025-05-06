# database_utils.py (Versão Firestore Completa)
import os
import logging
import time
import requests
import config # Importa suas configurações (BASE_DELIVERY_REWARDS)
from datetime import datetime # Import necessário
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# --- Configuração ---
log = logging.getLogger(__name__)

# --- Inicialização do Cliente Firestore ---
try:
    # Tenta inicializar. Requer credenciais via GOOGLE_APPLICATION_CREDENTIALS
    db = firestore.Client()
    log.info(f"Cliente Firestore inicializado para projeto: {db.project}")
except Exception as e:
    log.exception("Falha CRÍTICA ao inicializar cliente Firestore! Verifique as credenciais.")
    db = None # Marca como não inicializado

# --- Nomes das Coleções ---
SNAPSHOTS_COLLECTION = "daily_snapshots_v2"
NPC_STATE_COLLECTION = "delivery_npc_state_v2"

# --- Função de Preços ---
price_cache = {
    "data": None, "last_fetch_time": 0, "cache_duration_seconds": 3600 # 1 hora
}
def get_sfl_world_prices():
    """Busca os preços atuais dos itens da API sfl.world (dados p2p). Cache de 1 hora."""
    current_time = time.time()
    cache_expired = (current_time - price_cache["last_fetch_time"]) > price_cache["cache_duration_seconds"]

    if price_cache["data"] is not None and not cache_expired:
        log.info("Retornando preços da API sfl.world do cache.")
        return price_cache["data"]

    log.info("Buscando preços atualizados da API sfl.world...")
    api_url = "https://sfl.world/api/v1/prices"
    prices_float = {}
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        full_response_data = response.json()
        price_data_dict = full_response_data.get('data', {}).get('p2p') # Acessa o dict correto

        if isinstance(price_data_dict, dict):
            for item, price in price_data_dict.items():
                try: prices_float[item] = float(price)
                except (ValueError, TypeError):
                    log.warning(f"Não converteu preço para '{item}'. Valor: {price}. Usando 0.0.")
                    prices_float[item] = 0.0

            price_cache["data"] = prices_float
            price_cache["last_fetch_time"] = current_time
            log.info(f"Preços sfl.world obtidos/cacheados: {len(prices_float)} itens.")
            return prices_float
        else:
            log.error("Estrutura inesperada API preços (sem data.p2p).")
            return price_cache["data"] if price_cache["data"] else None

    except requests.exceptions.Timeout:
        log.error("Erro ao buscar preços sfl.world: Timeout.")
        return price_cache["data"] if price_cache["data"] else None
    except requests.exceptions.RequestException as e:
        log.error(f"Erro de conexão ao buscar preços sfl.world: {e}")
        return price_cache["data"] if price_cache["data"] else None
    except Exception as e:
        log.exception("Erro inesperado ao buscar/processar preços sfl.world.")
        return None

# --- Funções de Interação com Firestore ---

def add_snapshot(farm_id, npc_id, snapshot_date, delivery_count, skip_count, estimated_daily_cost):
    """Adiciona um documento de snapshot à coleção Firestore."""
    if not db: log.error("DB não init - add_snapshot"); return False
    try:
        farm_id_int = int(farm_id) # Garante int
        doc_id = f"{farm_id_int}_{npc_id}_{snapshot_date}" # Usa farm_id_int
        doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(doc_id)
        snapshot_data = {
            'farm_id': farm_id_int, 'npc_id': npc_id, 'snapshot_date': snapshot_date,
            'deliveryCount': delivery_count, 'skipCount': skip_count,
            'estimated_daily_cost_sfl': estimated_daily_cost,
            'timestamp': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(snapshot_data) # Cria ou sobrescreve
        log.info(f"Snapshot salvo: {doc_id} (D:{delivery_count}, S:{skip_count}, C:~{estimated_daily_cost:.2f})")
        return True
    except Exception: log.exception(f"Erro ao salvar snapshot {farm_id}_{npc_id}_{snapshot_date}"); return False

def get_snapshot_from_db(farm_id, npc_id, target_date_str):
    """Busca um snapshot específico no Firestore pelo ID composto."""
    if not db: log.error("DB não init - get_snapshot"); return None
    try:
        farm_id_int = int(farm_id)
        doc_id = f"{farm_id_int}_{npc_id}_{target_date_str}"
        doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        if snapshot.exists: return snapshot.to_dict()
        else: log.warning(f"Snapshot NÃO encontrado: {doc_id}"); return None
    except Exception: log.exception(f"Erro ao buscar snapshot {farm_id}_{npc_id}_{target_date_str}"); return None

def get_npc_state(farm_id, npc_name):
    """Busca o último estado registrado para um NPC de uma fazenda."""
    if not db: log.error("DB não init - get_npc_state"); return None
    try:
        farm_id_int = int(farm_id)
        doc_id = f"{farm_id_int}_{npc_name}"
        doc_ref = db.collection(NPC_STATE_COLLECTION).document(doc_id)
        state = doc_ref.get()
        if state.exists: return state.to_dict()
        else: return None
    except Exception: log.exception(f"Erro ao buscar estado {farm_id}_{npc_name}"); return None

def update_npc_state(farm_id, npc_name, delivery_count, skipped_count, completed_at):
    """Cria ou atualiza o estado de um NPC para uma fazenda no Firestore."""
    if not db: log.error("DB não init - update_npc_state"); return False
    try:
        farm_id_int = int(farm_id)
        doc_id = f"{farm_id_int}_{npc_name}"
        doc_ref = db.collection(NPC_STATE_COLLECTION).document(doc_id)
        state_data = {
            'farm_id': farm_id_int, 'npc_name': npc_name,
            'last_delivery_count': delivery_count or 0,
            'last_skipped_count': skipped_count or 0,
            'last_completed_at': str(completed_at) if completed_at else None,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        doc_ref.set(state_data, merge=True) # merge=True atualiza ou cria
        log.debug(f"Estado salvo/atualizado: {doc_id}")
        return True
    except Exception: log.exception(f"Erro ao salvar/atualizar estado {farm_id}_{npc_name}"); return False

def get_daily_costs_for_npc(farm_id, npc_id, start_date_str, end_date_str):
    """Busca lista de custos diários para um NPC/Farm/Período."""
    if not db: log.error("DB não init - get_daily_costs"); return []
    costs = []
    try:
        farm_id_int = int(farm_id)
        snapshots_ref = db.collection(SNAPSHOTS_COLLECTION)
        query = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                             .where(filter=FieldFilter("npc_id", "==", npc_id)) \
                             .where(filter=FieldFilter("snapshot_date", ">=", start_date_str)) \
                             .where(filter=FieldFilter("snapshot_date", "<=", end_date_str))
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict()
            cost = data.get('estimated_daily_cost_sfl')
            if cost is not None:
                try: costs.append(float(cost))
                except (ValueError, TypeError): log.warning(f"Custo inválido no snapshot {doc.id}: {cost}")
        log.debug(f"Custos diários para {farm_id}/{npc_id} ({start_date_str} a {end_date_str}): {len(costs)} regs.")
    except Exception: log.exception(f"Erro buscar custos diários {farm_id}/{npc_id}"); return []
    return costs

# --- FUNÇÃO PARA BUSCAR PRIMEIRA E ÚLTIMA DATA (ADICIONADA) ---
def get_first_and_last_snapshot_date(farm_id):
    """Encontra a data do primeiro e do último snapshot registrado para um farm_id."""
    if not db: log.error("DB não init - get_first_last_date"); return None, None
    try:
        farm_id_int = int(farm_id)
        snapshots_ref = db.collection(SNAPSHOTS_COLLECTION)
        first_date_str = None
        last_date_str = None

        # Query para a primeira data
        query_first = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                                   .order_by("snapshot_date", direction=firestore.Query.ASCENDING) \
                                   .limit(1)
        first_docs = list(query_first.stream())
        if first_docs: first_date_str = first_docs[0].to_dict().get("snapshot_date")

        # Query para a última data (apenas se a primeira foi encontrada)
        if first_date_str:
            query_last = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                                      .order_by("snapshot_date", direction=firestore.Query.DESCENDING) \
                                      .limit(1)
            last_docs = list(query_last.stream())
            if last_docs: last_date_str = last_docs[0].to_dict().get("snapshot_date")

        log.info(f"Datas para Farm {farm_id_int}: Primeira='{first_date_str}', Última='{last_date_str}'")
        return first_date_str, last_date_str
    except ValueError: log.error(f"Farm ID inválido '{farm_id}' ao buscar datas."); return None, None
    except Exception: log.exception(f"Erro buscar primeira/última data snapshot para Farm {farm_id}"); return None, None

# --- FUNÇÕES PARA "COLETA NA VISITA" ---
def check_snapshot_exists(farm_id, npc_id, target_date_str):
    """Verifica se um snapshot já existe para um farm/npc/data."""
    if not db: log.error("DB não init - check_snapshot"); return False
    try:
        doc_id = f"{int(farm_id)}_{npc_id}_{target_date_str}"
        doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(doc_id)
        return doc_ref.get(field_paths=['farm_id']).exists
    except Exception: log.exception(f"Erro verificar snapshot {farm_id}_{npc_id}_{target_date_str}"); return False

def create_snapshot_if_needed(farm_id, all_live_npc_data):
    """Verifica/cria snapshot de HOJE para NPCs relevantes usando dados ao vivo."""
    if not db: log.error("DB não init - create_snapshot"); return
    if not all_live_npc_data: log.warning("Sem dados NPC para create_snapshot"); return

    try: farm_id_int = int(farm_id)
    except (ValueError, TypeError): log.error(f"Farm ID inválido '{farm_id}' em create_snapshot"); return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    log.info(f"Verificando/Criando snapshots para Farm {farm_id_int} data {today_date_str}...")
    prices = get_sfl_world_prices() or {} # Busca preços (ou usa vazio)
    npcs_to_process_config = config.BASE_DELIVERY_REWARDS
    snapshots_created_count = 0

    for npc_id in npcs_to_process_config.keys():
        if check_snapshot_exists(farm_id_int, npc_id, today_date_str):
            log.debug(f"Snapshot {farm_id_int}_{npc_id}_{today_date_str} já existe.")
            continue

        log.info(f"Criando snapshot para {farm_id_int}_{npc_id}_{today_date_str}...")
        npc_api_data = all_live_npc_data.get(npc_id)
        estimated_daily_cost = 0.0

        if npc_api_data and isinstance(npc_api_data, dict):
            delivery_count = npc_api_data.get('deliveryCount')
            skipped_count = npc_api_data.get('skippedCount')
            # Validação mínima
            if delivery_count is None or skipped_count is None:
                log.warning(f"Contagem ausente para {npc_id}. Snapshot não salvo.")
                continue

            delivery_info = npc_api_data.get('delivery')
            reward_info = npc_api_data.get('reward')

            # Calcula custo se for token (reward vazio)
            if isinstance(reward_info, dict) and not reward_info:
                # --- CORREÇÃO EXPLÍCITA PARA PYLANCE (Linhas 174 e 182) ---

                # 1. Garante que 'prices' é um dicionário válido antes de prosseguir
                if isinstance(prices, dict) and prices:

                    # 2. Garante que 'delivery_info' é um dicionário válido antes de prosseguir
                    if isinstance(delivery_info, dict) and delivery_info:

                        # 3. Tenta pegar 'items' de forma segura de 'delivery_info'
                        items_dict = delivery_info.get('items')

                        # 4. Verifica se 'items' foi encontrado, é um dicionário e não está vazio
                        if isinstance(items_dict, dict) and items_dict:
                            items_needed = items_dict # Agora é seguro usar
                            try:
                                # 5. Calcula o custo (agora é seguro usar prices.get)
                                cost = sum((amount or 0) * prices.get(item, 0.0) for item, amount in items_needed.items())
                                estimated_daily_cost = round(cost, 4)
                                log.debug(f"Custo diário {npc_id}: {estimated_daily_cost:.4f} SFL")
                            except Exception as e: # Use 'e' na mensagem de log
                                log.exception(f"Erro calc custo {npc_id}: {e}")
                        # else: # Se items_dict não for válido ou estiver vazio, não faz nada (custo continua 0.0)
                    # else: # Se delivery_info não for válido, não faz nada
                # else: # Se prices não for válido, não faz nada
               # --- CORREÇÃO PARA PYLANCE ---
                # 1. Verifica se 'prices' e 'delivery_info' existem (não são None/False)
                if prices and delivery_info:
                    # 2. Tenta pegar 'items' de forma segura
                    items_dict = delivery_info.get('items')
                    # 3. Verifica se 'items' foi encontrado E é um dicionário E não está vazio
                    if isinstance(items_dict, dict) and items_dict:
                        items_needed = items_dict # Agora seguro usar items_dict
                        try:
                            cost = sum((amount or 0) * prices.get(item, 0.0) for item, amount in items_needed.items())
                            estimated_daily_cost = round(cost, 4)
                            log.debug(f"Custo diário {npc_id}: {estimated_daily_cost:.4f} SFL")
                        except Exception:
                            log.exception(f"Erro calc custo {npc_id}")
                # --- FIM DA CORREÇÃO ---

            # Salva
            if add_snapshot(farm_id_int, npc_id, today_date_str, delivery_count, skipped_count, estimated_daily_cost):
                 snapshots_created_count += 1
            else: log.error(f"Falha salvar snapshot {farm_id_int}_{npc_id}_{today_date_str}")
        else: log.warning(f"Dados não encontrados para {npc_id} (Farm {farm_id_int}).")

    log.info(f"Snapshot check/create concluído Farm {farm_id_int}. {snapshots_created_count} novos criados.")

    # Busca todas as bounties da coleção

def get_all_bounties():
    """Busca todas as bounties da coleção 'bounties' no Firestore."""
    if not db:
        log.error("Firestore não inicializado. Impossível buscar bounties.")
        return [] # Retorna lista vazia se o DB não estiver disponível

    try:
        # Substitua 'bounties' pelo nome exato da sua coleção no Firestore se for diferente
        bounties_ref = db.collection('bounties')
        docs = bounties_ref.stream() # Obtém um iterador de documentos

        bounties = []
        for doc in docs:
            b_data = doc.to_dict()
            if not b_data:
                log.warning(f"Documento de bounty {doc.id} sem dados.")
                continue

            b_data['id'] = doc.id # Adiciona o ID do documento aos dados

            # --- PARSING CORRETO DA RECOMPENSA (ESTRUTURA "items") ---
            b_data['reward_amount'] = None
            b_data['reward_currency'] = None # Mantemos este nome, pois o template espera ele

            if 'items' in b_data and isinstance(b_data['items'], dict) and b_data['items']:
                # Assume que há apenas um item de recompensa no dicionário 'items'
                try:
                    # Pega o primeiro (e único) nome de item (ex: "Geniseed")
                    currency_name = next(iter(b_data['items']))
                    # Pega a quantidade associada a esse nome
                    amount_value = b_data['items'][currency_name]

                    # Valida e atribui os valores
                    if isinstance(amount_value, (int, float)) and amount_value >= 0:
                        b_data['reward_amount'] = amount_value
                        b_data['reward_currency'] = currency_name # Guarda o nome da moeda/item
                    else:
                        log.warning(f"Valor de recompensa inválido para {currency_name} na bounty {doc.id}: {amount_value}")

                except StopIteration:
                    log.warning(f"Dicionário 'items' vazio para bounty {doc.id}.")
                except Exception as e:
                    log.error(f"Erro ao processar 'items' para bounty {doc.id}: {e}")
            # Se não houver 'items' ou for inválido, os valores permanecem None

            # --- FIM DO PARSING CORRETO ---

            # Garante que o campo 'name' existe para filtragem posterior
            if 'name' not in b_data:
                log.warning(f"Bounty {doc.id} não possui campo 'name'. Pulando.")
                continue # Pula esta bounty se não tiver nome

            bounties.append(b_data)

        log.info(f"Buscadas {len(bounties)} bounties do Firestore.")
        return bounties

    except Exception as e:
        # Usar log.exception para incluir traceback no log
        log.exception(f"Erro ao buscar bounties do Firestore: {e}")
        return [] # Retorna lista vazia em caso de erro