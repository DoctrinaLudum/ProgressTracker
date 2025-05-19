# database_utils.py (Refatorado para Snapshot por Fazenda/Dia com Mapa de NPCs)
import json
import logging
import os
import time
from datetime import datetime, timedelta  # timedelta pode ser útil

import requests
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import firestore
# Import específico para timestamp do servidor
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import FieldFilter
from google.oauth2 import service_account

import config  # Importa suas configurações (BASE_DELIVERY_REWARDS)

# --- Configuração ---
log = logging.getLogger(__name__)

db = None
try:
    # 1. Tenta inicializar o Firestore usando as credenciais padrão do Google Cloud (para o Google Cloud)
    try:
        log.info("Tentando inicializar Firestore com as credenciais padrão do Google Cloud...")
        db = firestore.Client()
        log.info(f"Cliente Firestore inicializado com sucesso usando as credenciais padrão. Projeto: {db.project if db else 'Não determinado'}")
    except DefaultCredentialsError:
        log.info("Credenciais padrão do Google Cloud não encontradas. Tentando carregar o arquivo de credenciais local...")
        # 2. Se as credenciais padrão não forem encontradas, tenta carregar o arquivo localmente
        base_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(base_dir, 'sfl-tracker-app-84739e970dda.json')

        if os.path.exists(credentials_path):
            log.info(f"Arquivo de credenciais encontrado em: {credentials_path}. Tentando inicializar Firestore...")
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            db = firestore.Client(credentials=credentials)
            log.info(f"Cliente Firestore inicializado com sucesso usando o arquivo: {credentials_path}")
        else:
            log.error("Arquivo de credenciais local não encontrado.")
            db = None # Garante que db seja None se a inicialização falhar
except Exception as e:
    log.exception(f"Falha CRÍTICA ao inicializar cliente Firestore: {e}")
    db = None # Garante que db é None se a inicialização falhar

# --- Nomes das Coleções ---
SNAPSHOTS_COLLECTION = "daily_snapshots_v2" 
NPC_STATE_COLLECTION = "delivery_npc_state_v2"
BOUNTIES_COLLECTION = "bounties"

# ---> get_sfl_world_prices <---
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
        price_data = full_response_data.get('data', {})
        price_data_dict = price_data.get('p2p')

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
            log.error("Estrutura inesperada API preços (sem data ou data.p2p).")
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
# ---> FIM get_sfl_world_prices <---

# --- Funções de Estado de NPC (sem alteração significativa) ---

# ---> get_npc_state (MODIFICADA para Mapa) <---
def get_npc_state(farm_id, npc_name):
    """
    Busca o último estado registrado para um NPC específico DENTRO do documento da fazenda.
    """
    if not db: 
        log.error("DB não inicializado - get_npc_state (mapa) falhou.")
        return None
    try:
        farm_id_int = int(farm_id)
        # Documento é identificado apenas pelo farm_id
        farm_doc_ref = db.collection(NPC_STATE_COLLECTION).document(str(farm_id_int))
        
        farm_doc_snapshot = farm_doc_ref.get()
        
        if farm_doc_snapshot.exists: 
            farm_data = farm_doc_snapshot.to_dict()
            if farm_data: # Garante que to_dict() não é None
                npc_states_map = farm_data.get('npc_states', {})
                npc_specific_state = npc_states_map.get(npc_name) # Pega o estado do NPC do mapa
                
                if npc_specific_state:
                    # log.debug(f"Estado encontrado para NPC '{npc_name}' na Farm {farm_id_int}: {npc_specific_state}")
                    return npc_specific_state
                else:
                    log.debug(f"Nenhum estado anterior encontrado para NPC '{npc_name}' no mapa da Farm {farm_id_int}.")
                    return None # NPC não tem estado salvo no mapa
            else:
                log.warning(f"Documento da Farm {farm_id_int} para estado existe, mas to_dict() é None.")
                return None
        else: 
            log.debug(f"Nenhum documento de estado encontrado para Farm {farm_id_int}.")
            return None # Documento da fazenda não existe
    except ValueError:
        log.error(f"Farm ID inválido '{farm_id}' ao buscar estado de NPC (mapa).")
        return None
    except Exception as e: 
        log.exception(f"Erro ao buscar estado para NPC {npc_name} na Farm {farm_id} (mapa): {e}")
        return None
# ---> FIM get_npc_state <---



# ---> update_npc_state (MODIFICADA para Mapa) <---
def update_npc_state(farm_id, npc_name, delivery_count, skipped_count, completed_at):
    """
    Cria ou atualiza o estado de um NPC específico DENTRO do documento da fazenda.
    """
    if not db: 
        log.error("DB não inicializado - update_npc_state (mapa) falhou.")
        return False
    try:
        farm_id_int = int(farm_id)
        # Documento agora é identificado apenas pelo farm_id
        farm_doc_ref = db.collection(NPC_STATE_COLLECTION).document(str(farm_id_int))
        
        # Prepara os dados apenas para o NPC específico
        # Usaremos notação de ponto para atualizar o campo dentro do mapa 'npc_states'
        npc_state_field_path = f"npc_states.{npc_name}" # Ex: npc_states.bert

        npc_specific_data = {
            'last_delivery_count': delivery_count if delivery_count is not None else 0,
            'last_skipped_count': skipped_count if skipped_count is not None else 0,
            'last_completed_at': str(completed_at) if completed_at is not None else None,
            'state_updated_at': SERVER_TIMESTAMP # Timestamp da atualização deste NPC
        }

        # Dados a serem atualizados/mesclados no documento da fazenda
        update_data = {
            npc_state_field_path: npc_specific_data,
            'farm_id': farm_id_int, # Garante que farm_id exista no documento
            'last_global_update': SERVER_TIMESTAMP # Timestamp da última modificação no documento
        }
        
        # Usamos set com merge=True para criar o doc se não existir ou atualizar os campos
        # A notação de ponto garante que apenas o subcampo do NPC seja atualizado no mapa
        farm_doc_ref.set(update_data, merge=True) 
        
        log.debug(f"Estado para NPC '{npc_name}' atualizado no documento da Farm {farm_id_int}.")
        return True
    except ValueError:
        log.error(f"Farm ID inválido '{farm_id}' ao atualizar estado de NPC (mapa).")
        return False
    except Exception as e: 
        log.exception(f"Erro ao salvar/atualizar estado para NPC {npc_name} na Farm {farm_id} (mapa): {e}")
        return False
# ---> FIM update_npc_state <---


# --- Funções de Snapshot (Refatoradas para Mapa por Fazenda/Dia) ---

# ---> check_snapshot_exists (MODIFICADA) <---
def check_snapshot_exists(farm_id, target_date_str):
    """Verifica se um snapshot (documento da fazenda) já existe para um farm/data."""
    if not db: 
        log.error("DB não inicializado - check_snapshot falhou.")
        return False 
    try:
        farm_id_int = int(farm_id)
        # O ID do documento agora é apenas farm_data
        doc_id = f"{farm_id_int}_{target_date_str}"
        doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(doc_id)
        log.debug(f"Verificando existência do snapshot: {doc_id}")
        exists = doc_ref.get().exists 
        log.debug(f"Snapshot {doc_id} existe? {exists}")
        return exists
    except ValueError:
         log.error(f"Argumento inválido ao verificar snapshot: farm='{farm_id}', date='{target_date_str}'.")
         return False
    except Exception as e: 
        log.exception(f"Erro verificar snapshot {farm_id}_{target_date_str}: {e}")
        return False 
# ---> FIM check_snapshot_exists <---

# ---> create_snapshot_if_needed (VERSÃO FINAL LIMPA) <---
def create_snapshot_if_needed(farm_id, all_general_npc_data, active_delivery_orders):
    """
    Verifica/cria UM snapshot diário POR FAZENDA contendo um mapa de NPCs relevantes,
    com dados otimizados (contadores e custo SFL da entrega ativa).
    'all_general_npc_data' refere-se à seção 'npcs' da API.
    'active_delivery_orders' refere-se à lista 'delivery.orders' da API.
    """
    if not db: 
        log.error("DB não inicializado - create_snapshot falhou.")
        return
    if not all_general_npc_data or not isinstance(all_general_npc_data, dict): 
        log.warning("Dados gerais de NPC (all_general_npc_data) ausentes ou inválidos para create_snapshot.")
        return
    # active_delivery_orders pode ser uma lista vazia, o que é válido.

    try: 
        farm_id_int = int(farm_id)
    except (ValueError, TypeError): 
        log.error(f"Farm ID inválido '{farm_id}' em create_snapshot.")
        return

    today_date_str = datetime.now().strftime('%Y-%m-%d')
    
    if check_snapshot_exists(farm_id_int, today_date_str):
        return 

    log.info(f"Criando snapshot único para Farm {farm_id_int} no dia {today_date_str}...")
    snapshot_doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(f"{farm_id_int}_{today_date_str}")
    snapshot_data_to_save = {
        'farm_id': farm_id_int, 'date': today_date_str, 
        'created_at': SERVER_TIMESTAMP, 'npcs': {} 
    }
    prices = get_sfl_world_prices() or {} 
    if not prices: log.warning("Não foi possível obter a lista de PREÇOS para o cálculo de custo do snapshot.")
    
    npcs_to_process_config = config.BASE_DELIVERY_REWARDS.keys() 
    npcs_added_count = 0 

    if not npcs_to_process_config:
        log.warning("Nenhum NPC relevante definido em config.BASE_DELIVERY_REWARDS.")
    else:
        for npc_id_from_config in npcs_to_process_config:
            # Pega os dados GERAIS do NPC (para deliveryCount, skipCount)
            general_npc_data = all_general_npc_data.get(npc_id_from_config)
            
            if general_npc_data and isinstance(general_npc_data, dict):
                delivery_count = general_npc_data.get('deliveryCount')
                skipped_count = general_npc_data.get('skippedCount', 0) 
                if skipped_count is None: skipped_count = 0
                
                if delivery_count is None: 
                    log.warning(f"Contador 'deliveryCount' ausente para NPC '{npc_id_from_config}'. Não incluído.")
                    continue 

                estimated_daily_cost = 0.0
                
                # Procura a ORDEM DE ENTREGA ATIVA para este NPC
                active_order_for_npc = None
                if isinstance(active_delivery_orders, list):
                    for order in active_delivery_orders:
                        if isinstance(order, dict) and order.get('from') == npc_id_from_config:
                            active_order_for_npc = order
                            break # Encontrou a ordem ativa para este NPC
                
                if active_order_for_npc:
                    reward_info = active_order_for_npc.get('reward') 
                    # Se reward_info for None ou dict vazio, é recompensa em token
                    if reward_info is None or (isinstance(reward_info, dict) and not reward_info): 
                        log.debug(f"NPC {npc_id_from_config}: Recompensa da ordem ativa (None ou Vazia), calculando custo SFL...")
                        # 'delivery_info' para itens agora é o próprio 'active_order_for_npc'
                        # pois 'items' está diretamente sob ele
                        delivery_items_info = active_order_for_npc # O objeto da ordem contém 'items'
                        
                        if prices and isinstance(delivery_items_info, dict) and delivery_items_info:
                            items_dict = delivery_items_info.get('items')
                            if isinstance(items_dict, dict) and items_dict:
                                current_cost_sum = 0.0
                                try:
                                    for item, amount in items_dict.items():
                                        item_amount = amount or 0
                                        item_price = prices.get(item) 
                                        if item_price is None:
                                            log.warning(f"Preço NÃO encontrado para item: '{item}' (NPC: {npc_id_from_config}). Usando preço 0.")
                                            item_price = 0.0
                                        else:
                                            try: item_price = float(item_price) 
                                            except (ValueError, TypeError):
                                                log.warning(f"Valor de preço inválido ('{item_price}') para item '{item}' (NPC: {npc_id_from_config}). Usando preço 0.")
                                                item_price = 0.0
                                        current_cost_sum += item_amount * item_price
                                    estimated_daily_cost = round(current_cost_sum, 4)
                                    log.info(f"CUSTO CALCULADO para NPC {npc_id_from_config}: {estimated_daily_cost:.4f} SFL")
                                except Exception as e_cost: 
                                    log.exception(f"Erro crítico calculando custo SFL para snapshot NPC {npc_id_from_config}: {e_cost}")
                            else:
                                log.debug(f"NPC {npc_id_from_config}: Dicionário 'items' da entrega ativa inválido ou vazio. Custo SFL será 0.")
                        else:
                            log.debug(f"NPC {npc_id_from_config}: Dicionário 'prices' ou dados da entrega ativa ('items') inválido/vazio. Custo SFL será 0.")
                    # else: A recompensa da ordem ativa não é None nem vazia (ex: SFL direto, não calcula custo de itens)
                else:
                    log.debug(f"NPC {npc_id_from_config}: Nenhuma ordem de entrega ativa encontrada para cálculo de custo.")

                snapshot_data_to_save['npcs'][npc_id_from_config] = {
                    'deliveryCount': delivery_count,
                    'skipCount': skipped_count,
                    'estimated_daily_cost_sfl': estimated_daily_cost 
                }
                npcs_added_count += 1
            else: 
                log.warning(f"Dados GERAIS da API não encontrados ou inválidos para NPC '{npc_id_from_config}'.")

    try:
        snapshot_doc_ref.set(snapshot_data_to_save)
        if npcs_added_count > 0:
            log.info(f"Snapshot único criado com sucesso para Farm {farm_id_int} dia {today_date_str} com {npcs_added_count} NPCs.")
        else:
             log.info(f"Snapshot único criado para Farm {farm_id_int} dia {today_date_str} (sem dados de NPC para salvar).")
    except Exception as e:
        log.exception(f"Erro ao salvar snapshot único para Farm {farm_id_int} dia {today_date_str}: {e}")
# ---> FIM create_snapshot_if_needed <---


# ---> get_snapshot_from_db (MODIFICADA) <---
def get_snapshot_from_db(farm_id, npc_id, target_date_str):
    """
    Busca os dados de um NPC específico de dentro do snapshot diário da fazenda (estrutura de mapa).
    Retorna o dicionário de dados do NPC ou None se não encontrado.
    """
    if not db: 
        log.error("DB não inicializado - get_snapshot (mapa) falhou.")
        return None
    try:
        farm_id_int = int(farm_id)
        doc_id = f"{farm_id_int}_{target_date_str}"
        doc_ref = db.collection(SNAPSHOTS_COLLECTION).document(doc_id)
        
        snapshot = doc_ref.get()
        if snapshot.exists: 
            farm_day_data = snapshot.to_dict()
            # Adiciona verificação se farm_day_data não é None
            if farm_day_data:
                npcs_map = farm_day_data.get('npcs', {}) 
                npc_data = npcs_map.get(npc_id) 
                if npc_data:
                    return npc_data 
                else:
                    log.warning(f"NPC '{npc_id}' não encontrado no mapa 'npcs' do snapshot {doc_id}.")
                    return None
            else:
                log.warning(f"Snapshot {doc_id} existe mas .to_dict() retornou None.")
                return None
        else: 
            log.warning(f"Snapshot NÃO encontrado para o dia/fazenda: {doc_id}")
            return None
    except ValueError:
         log.error(f"Farm ID ou data inválida ao buscar snapshot (mapa): farm='{farm_id}', date='{target_date_str}'.")
         return None
    except Exception as e: 
        log.exception(f"Erro ao buscar snapshot (mapa) {farm_id}_{target_date_str} para NPC {npc_id}: {e}")
        return None
# ---> FIM get_snapshot_from_db <---

# ---> get_daily_costs_for_npc (MODIFICADA) <---
def get_daily_costs_for_npc(farm_id, npc_id, start_date_str, end_date_str):
    """
    Busca lista de custos diários para um NPC específico, lendo do mapa
    nos snapshots diários da fazenda no período.
    """
    if not db: 
        log.error("DB não inicializado - get_daily_costs (mapa) falhou.")
        return []
    costs = []
    try:
        farm_id_int = int(farm_id)
        snapshots_ref = db.collection(SNAPSHOTS_COLLECTION)
        
        query = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                             .where(filter=FieldFilter("date", ">=", start_date_str)) \
                             .where(filter=FieldFilter("date", "<=", end_date_str)) \
                             .order_by("date")
                             
        docs = query.stream()
        processed_dates = set() 
        for doc in docs:
            doc_data = doc.to_dict()
            doc_date = doc_data.get('date') if doc_data else None
            
            if not doc_date or doc_date in processed_dates:
                continue
            processed_dates.add(doc_date)

            if doc_data: # Garante que doc_data não é None
                npcs_map = doc_data.get('npcs', {})
                npc_data = npcs_map.get(npc_id)
                
                if npc_data:
                    cost = npc_data.get('estimated_daily_cost_sfl') 
                    if cost is not None:
                        try: 
                            costs.append(float(cost))
                        except (ValueError, TypeError): 
                            log.warning(f"Custo inválido no snapshot {doc.id} para NPC {npc_id}: {cost}")
                 
        log.debug(f"Custos diários (mapa) para {farm_id}/{npc_id} ({start_date_str} a {end_date_str}): {len(costs)} registros encontrados.")
    except ValueError:
        log.error(f"Argumento inválido ao buscar custos diários (mapa): farm='{farm_id}', npc='{npc_id}', start='{start_date_str}', end='{end_date_str}'.")
        return []
    except Exception as e: 
        log.exception(f"Erro buscar custos diários (mapa) {farm_id}/{npc_id}: {e}")
        return []
    return costs
# ---> FIM get_daily_costs_for_npc <---

# ---> get_first_and_last_snapshot_date <---
def get_first_and_last_snapshot_date(farm_id):
    """Encontra a data do primeiro e do último snapshot registrado para um farm_id."""
    if not db: 
        log.error("DB não inicializado - get_first_last_date falhou.")
        return None, None
    try:
        farm_id_int = int(farm_id)
        snapshots_ref = db.collection(SNAPSHOTS_COLLECTION)
        first_date_str = None
        last_date_str = None
        
        date_field_to_order = "date" 

        query_first = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                                   .order_by(date_field_to_order, direction=firestore.Query.ASCENDING) \
                                   .limit(1)
        first_docs = list(query_first.stream()) 
        if first_docs and first_docs[0].exists: # Verifica se o documento existe
             doc_data = first_docs[0].to_dict()
             if doc_data: # Verifica se to_dict() não é None
                 first_date_str = doc_data.get(date_field_to_order)

        if first_date_str:
            query_last = snapshots_ref.where(filter=FieldFilter("farm_id", "==", farm_id_int)) \
                                      .order_by(date_field_to_order, direction=firestore.Query.DESCENDING) \
                                      .limit(1)
            last_docs = list(query_last.stream())
            if last_docs and last_docs[0].exists: # Verifica se o documento existe
                doc_data = last_docs[0].to_dict()
                if doc_data: # Verifica se to_dict() não é None
                    last_date_str = doc_data.get(date_field_to_order)

        log.info(f"Datas de snapshot (mapa) para Farm {farm_id_int}: Primeira='{first_date_str}', Última='{last_date_str}'")
        return first_date_str, last_date_str
        
    except ValueError: 
        log.error(f"Farm ID inválido '{farm_id}' ao buscar datas.")
        return None, None
    except Exception as e: 
        log.exception(f"Erro buscar primeira/última data snapshot para Farm {farm_id}: {e}")
        return None, None
# ---> FIM get_first_and_last_snapshot_date <---


# ---> get_all_bounties <---
# (Sem alterações necessárias aqui para a mudança de snapshot)
def get_all_bounties():
    """Busca todas as bounties da coleção 'bounties' no Firestore."""
    # (Código como na sua versão anterior)
    if not db:
        log.error("Firestore não inicializado. Impossível buscar bounties.")
        return [] 
    # ... (resto do código da função como estava) ...
    try:
        bounties_ref = db.collection(BOUNTIES_COLLECTION)
        docs = bounties_ref.stream() 
        bounties = []
        for doc in docs:
            b_data = doc.to_dict()
            if not b_data:
                log.warning(f"Documento de bounty {doc.id} sem dados.")
                continue
            b_data['id'] = doc.id 
            b_data['reward_amount'] = None
            b_data['reward_currency'] = None
            if 'items' in b_data and isinstance(b_data['items'], dict) and b_data['items']:
                try:
                    currency_name = next(iter(b_data['items']))
                    amount_value = b_data['items'][currency_name]
                    if isinstance(amount_value, (int, float)) and amount_value >= 0:
                        b_data['reward_amount'] = amount_value
                        b_data['reward_currency'] = currency_name
                    else: log.warning(f"Valor recompensa inválido {currency_name} na bounty {doc.id}: {amount_value}")
                except StopIteration: log.warning(f"Dict 'items' vazio bounty {doc.id}.")
                except Exception as e: log.error(f"Erro processar 'items' bounty {doc.id}: {e}")
            if 'name' not in b_data:
                log.warning(f"Bounty {doc.id} sem campo 'name'. Pulando.")
                continue 
            bounties.append(b_data)
        log.info(f"Buscadas {len(bounties)} bounties do Firestore.")
        return bounties
    except Exception as e:
        log.exception(f"Erro ao buscar bounties do Firestore: {e}")
        return []
# ---> FIM get_all_bounties <---

# ---> get_active_bounties <---
# (Sem alterações necessárias aqui para a mudança de snapshot)
def get_active_bounties(farm_id: str):
    """Busca apenas bounties marcadas como ativas no Firestore."""
    # (Código como na sua versão anterior)
    if not db:
        log.error("Firestore não inicializado. Impossível buscar bounties ativas.")
        return []
    # ... (resto do código da função como estava) ...
    try:
        bounties_ref = db.collection(BOUNTIES_COLLECTION)
        query = bounties_ref.where(filter=FieldFilter("active", "==", True))
        docs = query.stream()
        active_bounties = []
        for doc in docs:
            b_data = doc.to_dict()
            if not b_data: continue
            b_data['id'] = doc.id
            b_data['reward_amount'] = None
            b_data['reward_currency'] = None
            if 'items' in b_data and isinstance(b_data['items'], dict) and b_data['items']:
                try:
                    currency_name = next(iter(b_data['items']))
                    amount_value = b_data['items'][currency_name]
                    if isinstance(amount_value, (int, float)) and amount_value >= 0:
                        b_data['reward_amount'] = amount_value
                        b_data['reward_currency'] = currency_name
                    else: log.warning(f"Valor recompensa inválido {currency_name} na bounty ativa {doc.id}: {amount_value}")
                except StopIteration: log.warning(f"Dict 'items' vazio bounty ativa {doc.id}.")
                except Exception as e: log.error(f"Erro processar 'items' bounty ativa {doc.id}: {e}")
            if 'name' not in b_data:
                 log.warning(f"Bounty ativa {doc.id} sem campo 'name'. Pulando.")
                 continue
            active_bounties.append(b_data)
        log.info(f"Buscadas {len(active_bounties)} bounties ATIVAS do Firestore.")
        return active_bounties
    except Exception as e:
        log.exception(f"Erro ao buscar bounties ATIVAS do Firestore: {e}")
        return []
# ---> FIM get_active_bounties <---