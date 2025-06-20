# main.py
import logging
import os
from datetime import datetime
import json
from flask import Flask, jsonify, render_template, request

import analysis
import config
import database_utils
import route_helpers
from bumpkin_utils import gerar_url_imagem_bumpkin, load_item_ids
from sunflower_api import get_farm_data_full

# --- Configuração do Logging ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(module)s.%(funcName)s:%(lineno)d - %(message)s')
log = logging.getLogger(__name__)

# --- Inicialização do App Flask ---
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_item_ids(BASE_DIR) #

# --- Inicialização de Dados Globais ---
log.info("Inicializando dados globais...")
GLOBAL_SEASONAL_TOKEN_NAME = getattr(config, 'SEASONAL_TOKEN_NAME', 'Ticket Sazonal')
GLOBAL_APP_VERSION = getattr(config, 'APP_VERSION', 'N/A')
GLOBAL_SHOP_ITEMS = getattr(config, 'SEASONAL_SHOP_ITEMS', {})
GLOBAL_SHOP_ITEMS_TICKETS = {
    nome: dados for nome, dados in GLOBAL_SHOP_ITEMS.items() if dados.get('currency') == 'ticket'
}
TAXA_MEDIA_DIARIA_PLACEHOLDER = 10.0
log.info("Dados globais inicializados.")



# --- Rota de Health Check ---
@app.route('/healthz')
def healthz():
    return "OK", 200

# --- Verificação Inicial do Banco de Dados ---
if not database_utils.db: #
    log.critical("ERRO CRÍTICO: Cliente Firestore não inicializado.")

# --- Rota Flask Principal (GET/POST) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    context = {
        "error_message": None,
        "farm_id_submitted": None,
        "analise_tokens_deliveries": None,
        "analise_tokens_chores": None,
        "current_year": datetime.now().year,
        "farm_data_display": None, # Será preenchido por processed_farm_info
        "npc_rates": {},           # Alterado de npc_completion_rates
        "live_completions": 0,
        "live_tokens": 0,
        "live_cost_sfl": 0.0,
        "total_delivery_bonus": 0,
        "active_bonus_details": {},
        "bounties_data": {},
        "chores_data": [], # Renomeado de chores_data_for_template para consistência com processed_farm_info
        "bumpkin_image_url": None,
        "token_name": GLOBAL_SEASONAL_TOKEN_NAME,
        "config": config,
        "shop_items_all": GLOBAL_SHOP_ITEMS,
        "shop_items_ticket": GLOBAL_SHOP_ITEMS_TICKETS,
        "avg_daily_rate": TAXA_MEDIA_DIARIA_PLACEHOLDER,
        "avg_daily_rate_status": 'placeholder',
        "app_version": GLOBAL_APP_VERSION,
        "seasonal_shop_items_json": json.dumps(GLOBAL_SHOP_ITEMS)
    }

    if request.method == 'POST':
        context["farm_id_submitted"] = request.form.get('farm_id')
        log.info(f"POST para Farm ID: {context['farm_id_submitted'] or 'Nenhum'}")

        if not context["farm_id_submitted"]:
            context["error_message"] = "Por favor, insira um Farm ID."
        elif not database_utils.db: #
            context["error_message"] = "Erro interno: A conexão com o banco de dados não está disponível."
        else:
            api_response_data, error_message_api = get_farm_data_full(context["farm_id_submitted"]) #

            if error_message_api:
                context["error_message"] = error_message_api
            elif not api_response_data or 'farm' not in api_response_data:
                context["error_message"] = f"Não foram encontrados dados válidos da API para o Farm ID {context['farm_id_submitted']}."
                log.warning(f"Resposta inválida da API para Farm ID {context['farm_id_submitted']}: {api_response_data}")
            else:
                processed_farm_info = route_helpers.process_farm_data_on_submit( #
                    context["farm_id_submitted"], api_response_data, config,
                    analysis, database_utils, gerar_url_imagem_bumpkin, log #
                )
                # Atualiza o contexto com os dados retornados,
                # incluindo "farm_data_display", "chores_data", "bounties_data", etc.
                context.update(processed_farm_info)

                if processed_farm_info.get("processing_error_message") and not context["error_message"]:
                    context["error_message"] = processed_farm_info["processing_error_message"]

                # Só prossegue com análises se o processamento principal (farm_data_display) foi bem-sucedido
                if context.get("farm_data_display"):
                    context["analise_tokens_deliveries"] = route_helpers.get_historical_analysis_results( #
                        context["farm_id_submitted"], context["total_delivery_bonus"],
                        database_utils, analysis, log, datetime
                    )
                    active_player_bonus_names = list(context.get("active_bonus_details", {}).keys())
                    context["analise_tokens_chores"] = route_helpers.get_chores_historical_analysis_results( #
                        context["farm_id_submitted"], active_player_bonus_names,
                        database_utils, analysis, config, log, datetime
                    )
                else:
                    log.warning(f"farm_data_display não populado para Farm ID {context['farm_id_submitted']}. Análises históricas puladas.")
                    if not context["error_message"]:
                         context["error_message"] = f"Falha ao processar dados para Farm ID {context['farm_id_submitted']}."
    
    # --- Determinação da Taxa Média Diária Efetiva ---
    if not context.get("error_message") and isinstance(context.get("analise_tokens_deliveries"), dict):
        analise_deliveries = context["analise_tokens_deliveries"]
        status_analise_hist = analise_deliveries.get('status')
        taxa_real_calculada = analise_deliveries.get('taxa_media_diaria_real')

        if status_analise_hist == 'ok' and isinstance(taxa_real_calculada, (float, int)) and taxa_real_calculada > 0:
            context["avg_daily_rate"] = taxa_real_calculada
            context["avg_daily_rate_status"] = 'real'
        elif status_analise_hist == 'sem_historico':
            context["avg_daily_rate_status"] = 'sem_historico'
        elif status_analise_hist == 'dados_insuficientes':
            context["avg_daily_rate_status"] = 'dados_insuficientes'
        else:
            context["avg_daily_rate_status"] = 'erro_calculo_taxa'
            log.warning(f"Não foi possível usar taxa média diária real (status deliveries: {status_analise_hist}, taxa: {taxa_real_calculada}). Usando placeholder.")
    elif context.get("farm_id_submitted") and not context.get("farm_data_display") and not context.get("error_message"):
        context["avg_daily_rate_status"] = 'aguardando_dados'
    elif not context.get("farm_id_submitted"):
        context["avg_daily_rate_status"] = 'nao_calculado_ainda'

    # --- Logs Resumidos ---
    log.info(f"Renderizando para Farm ID: {context.get('farm_id_submitted', 'Nenhum')}. Taxa: {context.get('avg_daily_rate', TAXA_MEDIA_DIARIA_PLACEHOLDER):.1f} ({context.get('avg_daily_rate_status', 'N/A')})")
    
    # Usa context.get("chores_data", []) para o log, pois é a chave atualizada por context.update()
    chores_para_display_count = len(context.get("chores_data", []))
    log.info(f"Chores para display (cards): {chores_para_display_count} itens.")

    analise_chores_obj = context.get("analise_tokens_chores")
    analise_chores_status = analise_chores_obj.get('status', 'N/A') if isinstance(analise_chores_obj, dict) else 'Nenhuma análise'
    log.info(f"Análise Hist. Chores (status): {analise_chores_status}")
    if isinstance(analise_chores_obj, dict) and analise_chores_status == 'ok':
        log.info(f"  -> Chores Hist.: {analise_chores_obj.get('total_conclusoes',0)} conclusões, {analise_chores_obj.get('total_tokens_estimados',0)} tokens est.")
    elif isinstance(analise_chores_obj, dict) and analise_chores_status != 'ok' and analise_chores_obj.get('mensagem_erro'):
        log.warning(f"  -> Chores Hist. (erro/aviso): {analise_chores_obj.get('mensagem_erro')}")

    context["seasonal_shop_items_for_js"] = GLOBAL_SHOP_ITEMS # Passa o objeto Python
    context["calendar_bonus_priority_for_js"] = getattr(config, 'CALENDAR_BONUS_ITEM_PURCHASE_PRIORITY', []) # Passa a lista Python
    context["seasonal_delivery_buffs_for_js"] = getattr(config, 'SEASONAL_DELIVERY_BUFFS', {}) # Passa o dict Python

    return render_template('index.html', **context)

# ---> Rota AJAX para Calcular Projeção Sazonal ---
@app.route('/calculate_projection', methods=['POST'])
def calculate_projection():
    # ... (código existente, sem alterações) ...
    log.debug("Requisição AJAX recebida em /calculate_projection")
    data = request.get_json()
    if not data:
        log.warning("Recebida requisição AJAX sem dados JSON.")
        return jsonify({"success": False, "error": "Nenhum dado recebido"}), 400
    item_name = data.get('item_name')
    simulated_rate_str = data.get('simulated_rate')
    historical_rate_from_js = data.get('historical_rate')
    marked_item_names = data.get('marked_items', [])
    log.info(f"Calculando projeção AJAX - Item: {item_name}, Taxa Simulada: {simulated_rate_str}, Taxa Histórica: {historical_rate_from_js}, Marcados: {marked_item_names}")
    if not item_name:
        log.warning("Requisição AJAX sem 'item_name'.")
        return jsonify({"success": False, "error": "Nome do item não fornecido"}), 400
    if not GLOBAL_SHOP_ITEMS:
         log.error("Configuração SEASONAL_SHOP_ITEMS não encontrada ou vazia em config.py")
         return jsonify({"success": False, "error": "Configuração interna da loja não encontrada."}), 500
    rate_to_use, is_simulation = route_helpers.determine_active_daily_rate(
        simulated_rate_str,
        historical_rate_from_js,
        log,
        default_placeholder_rate=TAXA_MEDIA_DIARIA_PLACEHOLDER
    )
    season_end_date_config_str = getattr(config, 'SEASON_END_DATE', None)
    remaining_days = route_helpers.calculate_remaining_season_days(season_end_date_config_str, datetime, log)
    try:
        projection_details = route_helpers.get_projection_calculation_details(
            item_name,
            GLOBAL_SHOP_ITEMS,
            marked_item_names,
            rate_to_use,
            analysis,
            log
        )
        log.info(f"Resultados Cálculo AJAX para '{item_name}': Custo={projection_details['custo_total_calculado']}, Dias={projection_details['dias_projetados']} (Taxa Usada={rate_to_use})")

        calculated_cost_for_frontend = projection_details.get("custo_total_calculado_tickets")
        base_item_cost_for_frontend = projection_details.get("custo_item_base_ticket")
        calculated_unlock_cost_for_frontend = projection_details.get("custo_desbloqueio_tickets")

        return jsonify({
            "success": True,
            "item_name": item_name,
            "calculated_cost": projection_details["custo_total_calculado"] if projection_details["custo_total_calculado"] != float('inf') else None,
            "projected_days": projection_details["dias_projetados"] if projection_details["dias_projetados"] != float('inf') else None,
            "avg_daily_rate_used": rate_to_use,
            "is_simulation": is_simulation,
            "token_name": GLOBAL_SEASONAL_TOKEN_NAME,
            "unlock_path_items": projection_details["unlock_items_list"],
            "base_item_cost": projection_details["custo_item_base"],
            "calculated_unlock_cost": projection_details["custo_desbloqueio_calculado"] if projection_details["custo_desbloqueio_calculado"] != float('inf') else None,
            "unlock_path_items_details": projection_details["unlock_items_detalhados"],
            "remaining_season_days": remaining_days
        })
    except Exception as e:
        log.exception(f"Erro inesperado durante cálculo da projeção AJAX para {item_name}: {e}")
        return jsonify({"success": False, "error": "Erro interno ao calcular a projeção."}), 500

# ---> ROTA AJAX PARA OBTER DADOS DO CALENDÁRIO SAZONAL FIXO ---
@app.route('/get_seasonal_calendar', methods=['POST'])
def get_seasonal_calendar():
    log.info("Requisição POST recebida em /get_seasonal_calendar")

    try:
        data = request.get_json()
        if not data:
            log.warning("Nenhum dado JSON recebido na requisição POST para /get_seasonal_calendar.")
            return jsonify({"success": False, "error": "Dados da requisição ausentes."}), 400

        vip_ativo_para_simulacao = data.get('vip', False) # Pega 'vip' do JSON, default para False
        # Lista de compras simuladas pelo usuário.
        # Formato esperado: [{"name": "NomeItem", "data_compra": "YYYY-MM-DD", "custo_real_gasto": N, "buff_source_key": "ChaveBuff"}, ...]
        compras_simuladas_pelo_usuario = data.get('compras_simuladas', []) 

        log.debug(f"Parâmetros recebidos - VIP: {vip_ativo_para_simulacao}, Compras: {compras_simuladas_pelo_usuario}")

        dados_do_calendario = analysis.gerar_dados_calendario_sazonal( #
            vip_ativo_param=vip_ativo_para_simulacao,
            compras_simuladas_usuario=compras_simuladas_pelo_usuario # Passa a lista de compras
        )
        log.debug(f"Dados do calendário gerados por analysis.py (primeiro item, se houver): {dados_do_calendario[0] if dados_do_calendario else 'Vazio'}")

        
        if not dados_do_calendario:
            log.error("gerar_dados_calendario_sazonal retornou None ou lista vazia.")
            return jsonify({"success": False, "error": "Falha ao gerar dados do calendário (vazio)."}), 500
        
        if isinstance(dados_do_calendario, list) and len(dados_do_calendario) > 0 and "erro" in dados_do_calendario[0]:
             log.error(f"Erro retornado por gerar_dados_calendario_sazonal: {dados_do_calendario[0]['erro']}")
             return jsonify({"success": False, "error": dados_do_calendario[0]["erro"]}), 500

        season_start_date_config = getattr(config, 'SEASON_START_DATE', 'N/A') #
        season_end_date_config = getattr(config, 'SEASON_END_DATE', 'N/A') #
        
        log.info("FIM: Retornando JSON com sucesso para /get_seasonal_calendar") # Log de Fim da Rota (Sucesso)
        return jsonify({
            "success": True,
            "calendar_data": dados_do_calendario,
            "token_name": GLOBAL_SEASONAL_TOKEN_NAME, #
            "season_start": season_start_date_config,
            "season_end": season_end_date_config,
            "vip_simulated": vip_ativo_para_simulacao
        })
    except Exception as e:
        log.exception(f"ERRO INESPERADO na rota /get_seasonal_calendar: {e}")
        return jsonify({"success": False, "error": "Erro interno ao gerar dados do calendário."}), 500
# --->FIM ROTA AJAX PARA OBTER DADOS DO CALENDÁRIO SAZONAL FIXO ---

# ---> ROTA CALCULO DE COMPRA CALENDARIO SAZONAL
@app.route('/calculate_purchase_details_for_calendar', methods=['POST'])
def calculate_purchase_details_for_calendar():
    log.info("Requisição POST recebida em /calculate_purchase_details_for_calendar")
    data = request.get_json()
    log.debug(f"Dados brutos recebidos na requisição: {data}")

    item_name_to_evaluate = data.get('item_name') 
    # Usar as chaves que o JavaScript está enviando (conforme o log)
    full_simulated_purchases_list = data.get('simulated_purchases_up_to_date', []) 
    target_date_for_evaluation_str = data.get('target_date_for_unlock_check')    

    if not item_name_to_evaluate:
        log.error("Erro 400: Nome do item não fornecido na chave 'item_name'.")
        return jsonify({"success": False, "error": "Nome do item não fornecido."}), 400
    
    if not target_date_for_evaluation_str:
        log.error("Erro 400: Data alvo não fornecida na chave 'target_date_for_unlock_check'.")
        return jsonify({"success": False, "error": "Data alvo para verificação de desbloqueio não fornecida."}), 400

    item_shop_data_config = GLOBAL_SHOP_ITEMS.get(item_name_to_evaluate)
    if not item_shop_data_config:
        log.error(f"Erro 404: Item '{item_name_to_evaluate}' não encontrado na loja.")
        return jsonify({"success": False, "error": f"Item '{item_name_to_evaluate}' não encontrado na loja."}), 404

    # Restante da função permanece o mesmo...
    # ... (lógica de filtragem, chamada a analysis.calcular_custo_total_item, etc.)
    purchased_names_before_target_date = set()
    if full_simulated_purchases_list: 
        try:
            target_date_obj = datetime.strptime(target_date_for_evaluation_str, '%Y-%m-%d').date()
            for compra in full_simulated_purchases_list:
                compra_date_str = compra.get("data_compra")
                compra_name = compra.get("name")
                if compra_date_str and compra_name: 
                    compra_date_obj = datetime.strptime(compra_date_str, '%Y-%m-%d').date()
                    if compra_date_obj < target_date_obj: 
                        if compra_name != item_name_to_evaluate:
                           purchased_names_before_target_date.add(compra_name)
        except (ValueError, TypeError) as e:
            log.error(f"Erro ao processar datas para desbloqueio para '{item_name_to_evaluate}' na data '{target_date_for_evaluation_str}': {e}")
            return jsonify({"success": False, "error": "Formato de data inválido nas compras simuladas ou data alvo."}), 400
            
    cost_analysis_results = analysis.calcular_custo_total_item(
        item_name_to_evaluate,
        GLOBAL_SHOP_ITEMS,
        list(purchased_names_before_target_date) 
    )
    
    is_tier_unlockable_from_analysis = cost_analysis_results.get('is_tier_unlockable')
    custo_item_original_from_analysis = cost_analysis_results.get('item_cost_original')
    moeda_item_original_from_analysis = cost_analysis_results.get('item_currency_original')
    tier_do_item_alvo_from_config = item_shop_data_config.get('tier')
    
    custo_desbloqueio_tier_em_tickets_from_analysis = cost_analysis_results.get('unlock_cost_tickets')
    itens_ticket_para_desbloqueio_tier_from_analysis = cost_analysis_results.get('unlock_items_details', [])
    total_tickets_a_debitar_from_analysis = cost_analysis_results.get('total_cost_tickets') 

    purchase_possible_on_target_date = False 
    if item_shop_data_config.get('tier', 1) == 1: 
        purchase_possible_on_target_date = True
    elif is_tier_unlockable_from_analysis and custo_desbloqueio_tier_em_tickets_from_analysis == 0:
        purchase_possible_on_target_date = True
    elif is_tier_unlockable_from_analysis and custo_desbloqueio_tier_em_tickets_from_analysis > 0:
        purchase_possible_on_target_date = True
    else: 
        purchase_possible_on_target_date = False
        log.warning(f"Aquisição de '{item_name_to_evaluate}' (Tier {tier_do_item_alvo_from_config}) marcada como impossível: Tier não desbloqueado/desbloqueável na data {target_date_for_evaluation_str} com base nas compras estritamente anteriores.")

    cost_for_dialog = None
    if not purchase_possible_on_target_date:
        cost_for_dialog = custo_item_original_from_analysis 
    elif moeda_item_original_from_analysis == 'ticket':
        cost_for_dialog = total_tickets_a_debitar_from_analysis
    else:
        cost_for_dialog = custo_item_original_from_analysis

    json_cost_for_dialog = None if cost_for_dialog == float('inf') else cost_for_dialog
    json_total_tickets_to_debit = None if total_tickets_a_debitar_from_analysis == float('inf') else total_tickets_a_debitar_from_analysis
    json_custo_desbloqueio_tier = None if custo_desbloqueio_tier_em_tickets_from_analysis == float('inf') else custo_desbloqueio_tier_em_tickets_from_analysis
    
    if not purchase_possible_on_target_date:
        json_cost_for_dialog = None

    # ... (logs de debug) ...
    log.debug(f"Detalhes API para '{item_name_to_evaluate}' (Moeda: {moeda_item_original_from_analysis}, Tier: {tier_do_item_alvo_from_config}):")
    log.debug(f"  Tier Desbloqueável na data '{target_date_for_evaluation_str}': {purchase_possible_on_target_date}")
    log.debug(f"  Custo Original do Item: {custo_item_original_from_analysis} {moeda_item_original_from_analysis}")
    log.debug(f"  Custo Desbloqueio Tier (Tickets): {json_custo_desbloqueio_tier}")
    log.debug(f"  Total Tickets a Debitar (se compra confirmada e possível): {json_total_tickets_to_debit}")
    log.debug(f"  Custo para Diálogo (chave 'total_cost' no JSON): {json_cost_for_dialog}")


    return jsonify({
        "success": True,
        "item_name": item_name_to_evaluate,
        "total_cost": json_cost_for_dialog, 
        "currency": moeda_item_original_from_analysis,
        "tier": tier_do_item_alvo_from_config,
        "unlock_cost_tickets": json_custo_desbloqueio_tier,
        "unlock_items_details": itens_ticket_para_desbloqueio_tier_from_analysis, 
        "total_tickets_to_debit": json_total_tickets_to_debit, 
        "is_tier_unlockable": purchase_possible_on_target_date, 
        "token_name": GLOBAL_SEASONAL_TOKEN_NAME
    })
# ---> FIM ROTA CALCULO DE COMPRA CALENDARIO SAZONAL

# --- Bloco de Execução Principal ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor de desenvolvimento Flask na porta {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)