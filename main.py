# main.py
import logging
import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import analysis
import config
import database_utils
import route_helpers
import season_calendar_simulator
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
log.info("Gerando calendário potencial da temporada...")
try:
    GLOBAL_POTENTIAL_CALENDAR_DATA = season_calendar_simulator.generate_max_potential_season_calendar() #
    GLOBAL_SIM_BUFF_PRIORITY_LIST = season_calendar_simulator.SIM_BUFF_ITEM_PURCHASE_PRIORITY
    log.info("Calendário potencial e dados globais inicializados.")
except Exception as e_global:
    log.exception(f"Erro ao inicializar dados globais (calendário): {e_global}")
    GLOBAL_POTENTIAL_CALENDAR_DATA = []
    GLOBAL_SIM_BUFF_PRIORITY_LIST = []


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
        "potential_calendar": GLOBAL_POTENTIAL_CALENDAR_DATA,
        "sim_buff_item_purchase_priority": GLOBAL_SIM_BUFF_PRIORITY_LIST
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

    # --- Preparar shop_items_for_calendar_purchase ---
    # Esta lista conterá itens da loja que custam o token sazonal,
    # para serem usados na funcionalidade de compra manual do calendário.
    shop_items_for_calendar_purchase = []
    if GLOBAL_SHOP_ITEMS and config.SEASONAL_TOKEN_NAME:
        for item_name, item_data in GLOBAL_SHOP_ITEMS.items():
            # Considerar apenas itens que custam o token sazonal
            if item_data.get("currency") == config.SEASONAL_TOKEN_NAME:
                buff_id = None
                # Tentar encontrar o buff_id correspondente se o item for um buff
                if hasattr(config, 'SEASONAL_DELIVERY_BUFFS') and isinstance(config.SEASONAL_DELIVERY_BUFFS, dict):
                    for buff_key, buff_info in config.SEASONAL_DELIVERY_BUFFS.items():
                        if isinstance(buff_info, dict) and buff_info.get("shop_item_name") == item_name:
                            buff_id = buff_key
                            break
                shop_items_for_calendar_purchase.append({
                    "name": item_name,
                    "cost": item_data.get("cost"),
                    "currency": item_data.get("currency"), # Deve ser config.SEASONAL_TOKEN_NAME
                    "buff_id": buff_id
                })
    context["shop_items_for_calendar_purchase"] = shop_items_for_calendar_purchase

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

    return render_template('index.html', **context)

# --- Rota AJAX para Calcular Projeção Sazonal ---
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

# --- Rota AJAX para Simular Calendário Customizado ---
@app.route('/simulate_custom_calendar', methods=['POST'])
def simulate_custom_calendar_route():
    # ... (código existente, sem alterações) ...
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Requisição inválida."}), 400
        user_selected_buffs = data.get('selected_buffs', [])
        log.info(f"Recebida requisição para /simulate_custom_calendar com buffs: {user_selected_buffs}")
        custom_calendar_data = season_calendar_simulator.generate_custom_season_calendar(
            user_selected_buff_names=user_selected_buffs
        )
        if custom_calendar_data is not None:
            return jsonify({
                "success": True,
                "potential_calendar": custom_calendar_data,
                "sim_buff_item_purchase_priority": GLOBAL_SIM_BUFF_PRIORITY_LIST,
                "config": {
                    "SEASONAL_TOKEN_NAME": GLOBAL_SEASONAL_TOKEN_NAME,
                    "SEASONAL_DELIVERY_BUFFS": getattr(config, 'SEASONAL_DELIVERY_BUFFS', {}),
                    "DATE_ACTIVITIES_START_YIELDING_TOKENS": getattr(config, 'DATE_ACTIVITIES_START_YIELDING_TOKENS', None),
                    "DOUBLE_DELIVERY_DATE": getattr(config, 'DOUBLE_DELIVERY_DATE', None),
                    "DOUBLE_DELIVERY_INTERVAL_DAYS": getattr(config, 'DOUBLE_DELIVERY_INTERVAL_DAYS', None),
                    "SIM_IDEAL_PLAYER_HAS_VIP": getattr(config, 'SIM_IDEAL_PLAYER_HAS_VIP', True),
                    "SIM_IDEAL_PLAYER_ACHIEVES_MEGA_BOUNTY_BONUS": getattr(config, 'SIM_IDEAL_PLAYER_ACHIEVES_MEGA_BOUNTY_BONUS', True)
                }
            })
        else:
            log.error("Falha ao gerar calendário customizado a partir da rota (retorno None).")
            return jsonify({"success": False, "error": "Falha ao gerar calendário customizado no servidor."}), 500
    except Exception as e:
        log.exception("Erro na rota /simulate_custom_calendar:")
        return jsonify({"success": False, "error": f"Erro interno do servidor: {str(e)}"}), 500

# --- Bloco de Execução Principal ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Iniciando servidor de desenvolvimento Flask na porta {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)