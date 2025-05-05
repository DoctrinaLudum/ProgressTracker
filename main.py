# main.py (Revisado e Polido)
import os
import logging
from datetime import datetime, timedelta
import requests
from flask import Flask, render_template, request, jsonify
import config # Importa config inteiro
import database_utils # Funções de DB (Firestore)
import analysis # Funções de análise e cálculo

# Configuração do Logging
# (Use INFO para produção, DEBUG para mais detalhes durante desenvolvimento)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Inicialização do App Flask
app = Flask(__name__)

# Verificação Inicial do Banco de Dados
if not database_utils.db:
    log.critical("ERRO CRÍTICO: Cliente Firestore não inicializado ao iniciar o app.")
    # Considerar talvez impedir o app de iniciar ou mostrar um erro mais explícito
    # dependendo da criticidade do DB para a funcionalidade principal.

# --- Constantes ---
API_BASE_URL = "https://api.sunflower-land.com/community/farms/"

# --- Funções Auxiliares ---
def get_farm_data_full(farm_id):
    """Busca os dados completos da API do Sunflower Land para um farm_id."""
    if not farm_id or not farm_id.isdigit():
        log.warning(f"Tentativa com Farm ID inválido: {farm_id}")
        return None, "Farm ID inválido. Por favor, insira apenas números."

    api_url = f"{API_BASE_URL}{farm_id}"
    log.info(f"Buscando dados da API para Farm ID {farm_id}: {api_url}")
    response = None
    try:
        response = requests.get(api_url, timeout=15) # Timeout de 15 segundos
        response.raise_for_status() # Levanta erro para status 4xx ou 5xx

        # Tenta decodificar JSON apenas se o status for OK (redundante com raise_for_status, mas seguro)
        try:
            data = response.json()
            if 'farm' in data:
                log.info(f"Dados obtidos com sucesso para Farm ID: {farm_id}")
                return data, None # Retorna dados e None para erro
            else:
                log.warning(f"Resposta da API OK (status {response.status_code}) mas sem chave 'farm' para Farm ID: {farm_id}. Resposta: {response.text[:200]}...")
                return None, "A resposta da API foi recebida, mas parece incompleta (sem dados da fazenda)."
        except requests.exceptions.JSONDecodeError:
            log.exception(f"Erro ao decodificar JSON (Status {response.status_code}) para Farm ID: {farm_id}. Resposta: {response.text[:200]}...")
            return None, "A API retornou uma resposta que não é um JSON válido."

    except requests.exceptions.Timeout:
        log.error(f"Erro de Timeout ao conectar com a API para Farm ID: {farm_id}")
        return None, "A API demorou muito para responder (Timeout)."
    except requests.exceptions.HTTPError as http_err:
         status_code = http_err.response.status_code if http_err.response is not None else None
         if status_code == 404:
             log.warning(f"Erro ao buscar dados: Farm ID {farm_id} não encontrado (404).")
             return None, f"Fazenda com ID {farm_id} não encontrada. Verifique o número."
         else:
             # Tenta obter mais detalhes do erro se possível
             error_detail = str(http_err)
             try:
                 if http_err.response is not None and http_err.response.content:
                     error_detail = http_err.response.json().get('message', error_detail)
             except (requests.exceptions.JSONDecodeError, AttributeError):
                 pass # Ignora se não conseguir ler detalhes do corpo
             log.error(f"Erro HTTP inesperado (Status {status_code or 'N/A'}) ao buscar dados para Farm ID {farm_id}: {error_detail}")
             return None, f"Erro ao buscar dados da API (Código: {status_code or 'N/A'}). Tente novamente mais tarde."
    except requests.exceptions.RequestException as e:
        log.exception(f"Erro de conexão genérico com a API para Farm ID {farm_id}: {e}")
        return None, f"Erro de conexão ao tentar acessar a API do Sunflower Land: {e}"
    except Exception as e_geral:
        log.exception(f"Erro inesperado na função get_farm_data_full para Farm {farm_id}: {e_geral}")
        return None, "Ocorreu um erro inesperado no processamento dos dados da fazenda."

    # Fallback genérico (pouco provável de chegar aqui)
    status_code_fallback = response.status_code if response is not None else 'N/A'
    log.error(f"Erro desconhecido (Status {status_code_fallback}) ao buscar dados para Farm ID {farm_id}.")
    return None, f"Ocorreu um erro desconhecido (Código: {status_code_fallback}) ao buscar os dados."

# --- Rota Flask Principal (GET/POST) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # --- Inicialização das variáveis de contexto ---
    farm_data_display = None
    error_message = None
    farm_id_submitted = None
    npc_completion_rates = {}
    live_completions = 0
    live_tokens = 0
    live_cost_sfl = 0.0
    analise_tokens_deliveries = None # Para resultados da análise histórica
    total_delivery_bonus = 0
    active_bonus_details = {}
    # Lê do config ou usa um default
    seasonal_token_name = getattr(config, 'SEASONAL_TOKEN_NAME', 'Ticket Sazonal')
    app_version = getattr(config, 'APP_VERSION', 'N/A')
    # Carrega itens da loja do config
    itens_loja_completo = getattr(config, 'SEASONAL_SHOP_ITEMS', {})
    itens_loja_tickets = {nome: dados for nome, dados in itens_loja_completo.items() if dados.get('currency') == 'ticket'}
    # Taxa placeholder usada apenas para exibição inicial se necessário
    taxa_media_diaria_placeholder = 10.0
    current_year = datetime.now().year

    # --- Processamento do POST (Busca de Fazenda) ---
    if request.method == 'POST':
        farm_id_submitted = request.form.get('farm_id')
        log.info(f"Recebido POST para buscar Farm ID: {farm_id_submitted or 'Nenhum ID fornecido'}")

        if not farm_id_submitted:
            error_message = "Por favor, insira um Farm ID."
        else:
            # Verifica disponibilidade do DB ANTES de chamar a API
            if not database_utils.db:
                 error_message = "Erro interno: A conexão com o banco de dados não está disponível. Tente novamente mais tarde."
                 # Retorna imediatamente se DB falhar, pois funcionalidades dependem dele
                 # (Passa as variáveis já inicializadas para evitar erros no template)
                 return render_template('index.html', error_message=error_message, farm_id_submitted=farm_id_submitted,
                                        token_name=seasonal_token_name, shop_items_all=itens_loja_completo,
                                        avg_daily_rate=taxa_media_diaria_placeholder, current_year=current_year,
                                        app_version=app_version, config=config) # Passa config para acesso no template

            # 1. Busca dados da API
            api_response_data, error_message_api = get_farm_data_full(farm_id_submitted)
            error_message = error_message_api # Erro da API tem prioridade

            # 2. Processa dados se a busca na API foi bem-sucedida
            if api_response_data and 'farm' in api_response_data:
                farm_data_display = api_response_data['farm']
                npc_data_completo = farm_data_display.get('npcs', {})

                # 3. Calcula Bônus de Entrega
                try:
                    bonus_info = analysis.calculate_delivery_bonus(farm_data_display, config.SEASONAL_DELIVERY_BUFFS)
                    total_delivery_bonus = bonus_info.get('total_bonus', 0)
                    active_bonus_details = bonus_info.get('details', {})
                    log.info(f"Bônus de entrega calculado para Farm {farm_id_submitted}: +{total_delivery_bonus}")
                except Exception as e_bonus:
                    log.exception(f"Erro ao calcular bônus para Farm {farm_id_submitted}: {e_bonus}")
                    # Pode adicionar uma mensagem de erro parcial se desejar

                # 4. Processamento de NPCs, Snapshots, Histórico e Estado Atual
                if npc_data_completo:
                    npcs_processed_for_state = []
                    state_update_failed = False
                    # Busca preços uma vez para usar no cálculo de custo live
                    prices_now = database_utils.get_sfl_world_prices() or {}

                    # Loop pelos NPCs definidos no config que dão recompensa base
                    for npc_name in config.BASE_DELIVERY_REWARDS:
                        npc_info = npc_data_completo.get(npc_name)
                        if not isinstance(npc_info, dict):
                            log.warning(f"Dados do NPC '{npc_name}' não encontrados ou em formato inválido para Farm {farm_id_submitted}.")
                            continue # Pula para o próximo NPC

                        # Calcula taxa de conclusão
                        current_delivery_count = npc_info.get('deliveryCount')
                        current_skipped_count = npc_info.get('skippedCount', 0) # Assume 0 se não existir
                        if current_delivery_count is not None:
                            total = current_delivery_count + current_skipped_count
                            npc_completion_rates[npc_name] = round((current_delivery_count / total) * 100, 1) if total > 0 else 0.0
                        else:
                            npc_completion_rates[npc_name] = 'N/A' # Indica que não foi possível calcular

                        # Compara com estado anterior e calcula "live" updates
                        if current_delivery_count is not None:
                            try:
                                previous_state_data = database_utils.get_npc_state(farm_id_submitted, npc_name)
                                if previous_state_data:
                                    previous_count = previous_state_data.get('last_delivery_count', 0)
                                    # Calcula apenas se o contador atual for maior que o anterior
                                    if current_delivery_count > previous_count:
                                        completions_now = current_delivery_count - previous_count
                                        live_completions += completions_now
                                        # Calcula tokens live (base + bônus total)
                                        base_token = config.BASE_DELIVERY_REWARDS.get(npc_name, 0)
                                        live_tokens += completions_now * (base_token + total_delivery_bonus) # Usa bônus total aqui
                                        # Calcula custo live (aproximado, baseado nos itens da entrega ATIVA se for recompensa token)
                                        # NOTA: Este custo é apenas da entrega ATIVA, não das N que podem ter ocorrido. É uma estimativa grosseira.
                                        reward_info = npc_info.get('reward', {})
                                        if isinstance(reward_info, dict) and not reward_info: # Se reward é vazio, deu token
                                             delivery_info = npc_info.get('delivery')
                                             cost_current_delivery = 0.0
                                             if prices_now and delivery_info and isinstance(delivery_info.get('items'), dict):
                                                 items_needed = delivery_info.get('items')
                                                 if items_needed:
                                                     try:
                                                         cost = sum((amount or 0) * prices_now.get(item, 0.0) for item, amount in items_needed.items())
                                                         cost_current_delivery = cost
                                                     except Exception as e_cost:
                                                          log.exception(f"Erro ao calcular custo da entrega ativa de {npc_name} para Farm {farm_id_submitted}: {e_cost}")
                                             live_cost_sfl += cost_current_delivery # Acumula custo da entrega ativa (não multiplica por completions_now)

                                # Atualiza o estado do NPC no DB
                                update_success = database_utils.update_npc_state(
                                    farm_id_submitted, npc_name,
                                    current_delivery_count, current_skipped_count,
                                    npc_info.get('deliveryCompletedAt') # Passa data/hora da última conclusão
                                )
                                if update_success:
                                    npcs_processed_for_state.append(npc_name)
                                else:
                                    state_update_failed = True
                                    log.error(f"Falha ao salvar estado para {farm_id_submitted}/{npc_name}")
                            except Exception as e_state:
                                log.exception(f"Erro ao processar estado/live update para {farm_id_submitted}/{npc_name}: {e_state}")
                                state_update_failed = True # Marca falha se qualquer erro ocorrer

                    if state_update_failed and not error_message:
                        error_message = "Atenção: Ocorreu um erro parcial ao salvar o estado atual de progresso das entregas."
                    elif npcs_processed_for_state:
                        log.info(f"Estado atualizado com sucesso para NPCs: {', '.join(npcs_processed_for_state)}")

                    # Cria snapshot diário se necessário
                    try:
                        database_utils.create_snapshot_if_needed(farm_id_submitted, npc_data_completo)
                    except Exception as e_snap:
                        log.exception(f"Erro ao tentar criar snapshot para Farm {farm_id_submitted}: {e_snap}")
                        # Pode adicionar erro parcial aqui também

                    # Realiza a análise histórica
                    try:
                        farm_id_int_lookup = int(farm_id_submitted) # Garante int para busca no DB
                        primeira_data, ultima_data = database_utils.get_first_and_last_snapshot_date(farm_id_int_lookup)
                        if primeira_data and ultima_data:
                            log.info(f"Iniciando análise histórica para Farm {farm_id_submitted} ({primeira_data} a {ultima_data}) com Bônus +{total_delivery_bonus}")
                            # Chama análise passando ID original (string), datas e bônus
                            analise_tokens_deliveries = analysis.calcular_estimativa_token_deliveries(
                                farm_id_submitted, primeira_data, ultima_data, primeira_data, total_delivery_bonus
                            )
                            # Formata período para exibição
                            if analise_tokens_deliveries and 'erro' not in analise_tokens_deliveries:
                                try:
                                    dt_inicio = datetime.strptime(primeira_data, '%Y-%m-%d')
                                    dt_fim = datetime.strptime(ultima_data, '%Y-%m-%d')
                                    periodo_formatado = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
                                    analise_tokens_deliveries['periodo_analisado'] = periodo_formatado
                                except ValueError:
                                    analise_tokens_deliveries['periodo_analisado'] = f"{primeira_data} a {ultima_data}"
                        else:
                            log.warning(f"Nenhum snapshot encontrado para análise histórica do Farm {farm_id_submitted}.")
                            analise_tokens_deliveries = {'status': 'sem_historico', 'mensagem': "Nenhum histórico de entregas encontrado para análise."}
                    except ValueError:
                         log.error(f"Farm ID '{farm_id_submitted}' inválido para consulta histórica.")
                         analise_tokens_deliveries = {"erro": "Farm ID inválido para consulta de histórico."}
                    except Exception as e_analise:
                        log.exception(f"Erro durante busca/análise de snapshots para Farm {farm_id_submitted}: {e_analise}")
                        analise_tokens_deliveries = {"erro": "Falha ao calcular o histórico de entregas."}
                else:
                    log.warning(f"Chave 'npcs' vazia ou ausente na resposta da API para Farm {farm_id_submitted}. Análise de NPCs e histórico pulada.")
            # Fim do if api_response_data
            elif not error_message: # Se não houve erro na API mas não veio 'farm'
                 error_message = f"Não foi possível obter dados detalhados para o Farm ID {farm_id_submitted}. Verifique o ID ou tente novamente."
    # Fim do if request.method == 'POST'

    # Garante que analise_tokens existe para evitar erros no template
    if 'analise_tokens_deliveries' not in locals():
         analise_tokens_deliveries = None # Define como None se não foi processado

    log.info(f"Renderizando template index.html (Farm ID: {farm_id_submitted})")

    # <<< ADICIONE ESTAS LINHAS DE DEBUG >>>
    print("-" * 30)
    print(f"DEBUG main.py -> farm_data type: {type(farm_data_display)}")
    print(f"DEBUG main.py -> error_message: {error_message}")
    print(f"DEBUG main.py -> npc_rates: {npc_completion_rates}")
    print(f"DEBUG main.py -> analise_tokens: {analise_tokens_deliveries}")
    print("-" * 30)
    # --- FIM DEBUG ---

    # --- Renderiza o Template ---
    return render_template('index.html',
                           # Dados da Fazenda e Erros
                           farm_data=farm_data_display,
                           error_message=error_message,
                           farm_id_submitted=farm_id_submitted,
                           # Dados Processados
                           npc_rates=npc_completion_rates,
                           analise_tokens=analise_tokens_deliveries, # Histórico
                           live_completions=live_completions,
                           live_tokens=live_tokens,
                           live_cost_sfl=round(live_cost_sfl, 4),
                           delivery_bonus=total_delivery_bonus,
                           active_bonus_details=active_bonus_details,
                           # Dados Gerais e de Configuração
                           token_name=seasonal_token_name,
                           config=config, # Passa config para acesso a constantes no template
                           shop_items_all=itens_loja_completo,
                           shop_items_ticket=itens_loja_tickets, # Apenas itens de ticket (se necessário)
                           avg_daily_rate=taxa_media_diaria_placeholder, # Placeholder inicial
                           current_year=current_year,
                           app_version=app_version
                           )


# --- Rota AJAX para Calcular Projeção Sazonal ---
@app.route('/calculate_projection', methods=['POST'])
def calculate_projection():
    log.debug("Requisição AJAX recebida em /calculate_projection")
    data = request.get_json()
    if not data:
        log.warning("Recebida requisição AJAX sem dados JSON.")
        return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400

    item_name = data.get('item_name')
    simulated_rate_str = data.get('simulated_rate') # Pode ser None
    marked_item_names = data.get('marked_items', []) # Pega a lista, default: lista vazia []
    log.info(f"Calculando projeção AJAX - Item: {item_name}, Taxa Simulada: {simulated_rate_str}")

    if not item_name:
        log.warning("Requisição AJAX sem 'item_name'.")
        return jsonify({"success": False, "error": "Nome do item não fornecido"}), 400

    # Carrega itens da loja do config
    itens_loja_completo = getattr(config, 'SEASONAL_SHOP_ITEMS', {})
    if not itens_loja_completo:
         log.error("Configuração SEASONAL_SHOP_ITEMS não encontrada ou vazia em config.py")
         return jsonify({"success": False, "error": "Configuração interna da loja não encontrada"}), 500

    # --- Determina a taxa de ganho diário a ser usada ---
    rate_to_use = None
    simulated_rate = None
    if simulated_rate_str: # Se foi enviada uma taxa para simulação
        try:
            simulated_rate = float(simulated_rate_str)
            if simulated_rate > 0: # Usa apenas se for válida e positiva
                rate_to_use = simulated_rate
                log.debug(f"Usando taxa SIMULADA fornecida: {rate_to_use}")
            else:
                log.warning(f"Taxa simulada inválida (não positiva): {simulated_rate_str}. Usando placeholder.")
                simulated_rate = None # Anula para is_simulation ser False
        except (ValueError, TypeError):
            log.warning(f"Taxa simulada inválida (não numérica): {simulated_rate_str}. Usando placeholder.")
            simulated_rate = None # Garante que is_simulation será False
    
    if rate_to_use is None: # Se não usou a simulada (não enviada ou inválida)
        # TODO: Implementar busca da taxa histórica real do usuário aqui
        # Substituir este placeholder pela taxa calculada do histórico (se disponível)
        taxa_media_diaria_placeholder = 10.0
        rate_to_use = taxa_media_diaria_placeholder
        log.debug(f"Usando taxa PLACEHOLDER: {rate_to_use}")
    # --- Fim determinação taxa ---

    # --- Calcula dias restantes da temporada ---
    remaining_days = None
    try:
        # Assume SEASON_END_DATE está em config.py no formato 'YYYY-MM-DD'
        end_date_str = getattr(config, 'SEASON_END_DATE', None)
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            today = datetime.now().date()
            if end_date >= today:
                remaining_days = (end_date - today).days
            else:
                remaining_days = 0 # Temporada na teoria já acabou
            log.debug(f"Data final config: '{end_date_str}', Hoje: {today}, Dias restantes: {remaining_days}")
        else:
            log.warning("SEASON_END_DATE não definida em config.py. Não é possível calcular dias restantes.")
    except Exception as e_date:
        log.error(f"Erro ao calcular dias restantes da temporada (SEASON_END_DATE='{config.SEASON_END_DATE}'): {e_date}")
        remaining_days = None # Enviar None para o JS tratar
    # --- FIM Calculo dias restantes ---

    # --- Calcula Custo, Itens de Desbloqueio e Dias Projetados ---
    try:
        # 1. Calcula custo total E obtém a lista de itens de desbloqueio
        custo_info = analysis.calcular_custo_total_item(item_name, itens_loja_completo, marked_item_names)
        custo_total_calculado = custo_info['total_cost']
        custo_item_base = custo_info['item_cost'] # Pode ser None se item não for de ticket
        custo_desbloqueio_calculado = custo_info['unlock_cost']
        unlock_items_detalhados = custo_info['unlock_items_details'] # Lista de dicts
        # Pega também a lista simples de nomes para o highlight atual no JS (pode ser otimizado depois)
        unlock_items_list = [item['name'] for item in unlock_items_detalhados] 

        # 2. Calcula dias projetados (se custo for válido)
        if custo_total_calculado != float('inf'):
            dias_projetados = analysis.projetar_dias_para_item(custo_total_calculado, rate_to_use)
        else:
            dias_projetados = float('inf') # Custo infinito -> Dias infinitos

        log.info(f"Resultados Cálculo AJAX: Custo={custo_total_calculado}, Dias={dias_projetados}, ItensDesbloq={unlock_items_list} (Taxa Usada={rate_to_use})")

        # 3. Monta e retorna a resposta JSON
        return jsonify({
            "success": True,
            "item_name": item_name,
            # Mantém calculated_cost como o custo TOTAL para compatibilidade e exibição principal
            "calculated_cost": custo_total_calculado if custo_total_calculado != float('inf') else None,
            "projected_days": dias_projetados if dias_projetados != float('inf') else None,
            "avg_daily_rate_used": rate_to_use,
            "is_simulation": bool(simulated_rate),
            "token_name": getattr(config, 'SEASONAL_TOKEN_NAME', 'Ticket'),
            # Dados para destaque visual (lista de nomes)
            "unlock_path_items": unlock_items_list,
            # Novos dados para a seção "Detalhes do Cálculo"
            "base_item_cost": custo_item_base,
            "calculated_unlock_cost": custo_desbloqueio_calculado if custo_desbloqueio_calculado != float('inf') else None,
            "unlock_path_items_details": unlock_items_detalhados, # Lista de dicts com detalhes
            # Dados para aviso de tempo
            "remaining_season_days": remaining_days
        })

    except Exception as e:
        log.exception(f"Erro inesperado durante cálculo da projeção AJAX para {item_name}: {e}")
        return jsonify({"success": False, "error": "Erro interno ao calcular a projeção."}), 500
# --- FIM ROTA AJAX ---


# --- Bloco de Execução Principal (para desenvolvimento) ---
if __name__ == '__main__':
    # Usa variável de ambiente para porta, ou default (ex: 8080 para Cloud Run, 5000 local)
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor de desenvolvimento Flask na porta {port}...")
    # host='0.0.0.0' permite acesso externo na rede local/container
    # debug=True é útil para desenvolvimento, mas DESATIVE em produção
    app.run(host='0.0.0.0', port=port, debug=True)