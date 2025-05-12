# main.py (Revisado e Polido)
import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import config # Importa config inteiro
import database_utils # Funções de DB (Firestore)
import analysis # Funções de análise e cálculo
import json
from bumpkin_utils import load_item_ids, gerar_url_imagem_bumpkin
from sunflower_api import get_farm_data_full
import route_helpers

# Configuração do Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# Inicialização do App Flask
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_item_ids(BASE_DIR)

# Verificação Inicial do Banco de Dados
if not database_utils.db:
    log.critical("ERRO CRÍTICO: Cliente Firestore não inicializado ao iniciar o app.")

# --- Rota Flask Principal (GET/POST) ---
@app.route('/', methods=['GET', 'POST'])
def index():
     # --- Inicialização das variáveis de contexto ---
    # Variáveis que podem ser preenchidas por GET ou antes do processamento do POST
    error_message = None
    farm_id_submitted = None
    analise_tokens_deliveries = None 
    seasonal_token_name = getattr(config, 'SEASONAL_TOKEN_NAME', 'Ticket Sazonal')
    app_version = getattr(config, 'APP_VERSION', 'N/A')
    itens_loja_completo = getattr(config, 'SEASONAL_SHOP_ITEMS', {})
    itens_loja_tickets = {nome: dados for nome, dados in itens_loja_completo.items() if dados.get('currency') == 'ticket'}
    taxa_media_diaria_placeholder = 10.0 # Usado no GET e como fallback
    current_year = datetime.now().year
    
    # Variáveis que serão preenchidas pelo processamento do POST
    farm_data_display = None
    npc_completion_rates = {}
    live_completions = 0
    live_tokens = 0
    live_cost_sfl = 0.0
    total_delivery_bonus = 0
    active_bonus_details = {}
    bounties_data = {} # Inicializa bounties_data aqui para GET e POST
    bumpkin_image_url = None

    # --- Processamento do POST (Busca de Fazenda) ---
    if request.method == 'POST':
        farm_id_submitted = request.form.get('farm_id')
        log.info(f"Recebido POST para buscar Farm ID: {farm_id_submitted or 'Nenhum ID fornecido'}")

        if not farm_id_submitted:
            error_message = "Por favor, insira um Farm ID."
        else:
            if not database_utils.db:
                error_message = "Erro interno: A conexão com o banco de dados não está disponível. Tente novamente mais tarde."
                return render_template('index.html', error_message=error_message, farm_id_submitted=farm_id_submitted,
                                        token_name=seasonal_token_name, shop_items_all=itens_loja_completo,
                                        avg_daily_rate=taxa_media_diaria_placeholder, current_year=current_year,
                                        app_version=app_version, config=config, 
                                        # Passando os valores inicializados/padrão
                                        farm_data=farm_data_display, npc_rates=npc_completion_rates, analise_tokens=analise_tokens_deliveries,
                                        live_completions=live_completions, live_tokens=live_tokens, live_cost_sfl=live_cost_sfl,
                                        delivery_bonus=total_delivery_bonus, active_bonus_details=active_bonus_details,
                                        bounties_data=bounties_data, bumpkin_image_url=bumpkin_image_url,
                                        shop_items_ticket=itens_loja_tickets)

            api_response_data, error_message_api = get_farm_data_full(farm_id_submitted) 
            error_message = error_message_api # Erro da API tem prioridade

            if api_response_data and 'farm' in api_response_data:
                # <<< CHAMADA PARA A NOVA FUNÇÃO DE PROCESSAMENTO >>>
                # Note que passamos 'config', 'analysis', 'database_utils', 'gerar_url_imagem_bumpkin' e 'log'
                # que estão disponíveis no escopo da função index() devido às importações globais do módulo.
                processed_farm_info = route_helpers.process_farm_data_on_submit(
                    farm_id_submitted, 
                    api_response_data,
                    config, # Passa o módulo config importado
                    analysis, # Passa o módulo analysis importado
                    database_utils, # Passa o módulo database_utils importado
                    gerar_url_imagem_bumpkin, # Passa a função importada especificamente
                    log # Passa a instância de logger
                )

                # Desempacota os resultados da função de processamento
                farm_data_display = processed_farm_info["farm_data_display"]
                npc_completion_rates = processed_farm_info["npc_completion_rates"]
                live_completions = processed_farm_info["live_completions"]
                live_tokens = processed_farm_info["live_tokens"]
                live_cost_sfl = processed_farm_info["live_cost_sfl"]
                total_delivery_bonus = processed_farm_info["total_delivery_bonus"]
                active_bonus_details = processed_farm_info["active_bonus_details"]
                bounties_data = processed_farm_info["bounties_data"] 
                bumpkin_image_url = processed_farm_info["bumpkin_image_url"]

                # Adiciona a mensagem de erro do processamento, se houver e não houver erro de API
                if processed_farm_info["processing_error_message"] and not error_message:
                    error_message = processed_farm_info["processing_error_message"]
                # <<< FIM DA CHAMADA E PROCESSAMENTO DO RETORNO >>>

                # <<< CHAMADA PARA A NOVA FUNÇÃO DE ANÁLISE HISTÓRICA >>>
                if farm_data_display: # A análise histórica só faz sentido se o processamento básico foi OK
                    analise_tokens_deliveries = route_helpers.get_historical_analysis_results(
                        farm_id_submitted,
                        total_delivery_bonus, # Passa o bônus calculado anteriormente
                        database_utils,
                        analysis,
                        log,
                        datetime # Passa a classe/módulo datetime
                    )
                else: 
                    log.warning(f"Processamento básico de dados da fazenda falhou para Farm ID {farm_id_submitted}. Análise histórica pulada.")
                    # analise_tokens_deliveries permanece None ou com o valor de erro do processamento anterior
            
            elif not error_message: 
                 error_message = f"Não foi possível obter dados detalhados para o Farm ID {farm_id_submitted}. Verifique o ID ou tente novamente."
    # --- Fim metodo POST

    # Garante que analise_tokens existe para evitar erros no template
    if 'analise_tokens_deliveries' not in locals():
         analise_tokens_deliveries = None # Define como None se não foi processado

     # Garante que bounties_data existe mesmo para GET
    if not isinstance(bounties_data, dict): # Segurança extra
        bounties_data = {}

    # ---> Define a taxa média diária efetiva para exibição e uso ---
    effective_avg_daily_rate = taxa_media_diaria_placeholder # Default numérico
    avg_daily_rate_status = 'placeholder' # Default textual para o status da taxa

    if analise_tokens_deliveries and isinstance(analise_tokens_deliveries, dict):
        status_analise_hist = analise_tokens_deliveries.get('status')
        taxa_real_calculada = analise_tokens_deliveries.get('taxa_media_diaria_real')

        if status_analise_hist == 'ok' and \
           isinstance(taxa_real_calculada, (float, int)) and taxa_real_calculada > 0:
            effective_avg_daily_rate = taxa_real_calculada
            avg_daily_rate_status = 'real' # A taxa é baseada em dados reais
            log.info(f"Usando taxa média diária REAL calculada: {effective_avg_daily_rate:.2f}")
        elif status_analise_hist == 'sem_historico':
            avg_daily_rate_status = 'sem_historico' # Não há dados para calcular
            log.info("Sem histórico para calcular taxa média diária real. Status: sem_historico.")
            # effective_avg_daily_rate já é o placeholder numérico
        elif status_analise_hist == 'dados_insuficientes':
            avg_daily_rate_status = 'dados_insuficientes' # Dados insuficientes
            log.info("Dados insuficientes para calcular taxa média diária real de forma confiável. Status: dados_insuficientes.")
            # effective_avg_daily_rate já é o placeholder numérico
        else: # Inclui outros status de erro da análise ou taxa não positiva
            avg_daily_rate_status = 'erro_calculo_taxa' # Um status genérico para quando a taxa não pôde ser usada
            log.warning(f"Não foi possível usar taxa média diária real (status análise: {status_analise_hist}, taxa calc: {taxa_real_calculada}). Usando placeholder.")
            # effective_avg_daily_rate já é o placeholder numérico
    else:
        # Este caso ocorre se analise_tokens_deliveries não for um dict (ex: None em requisição GET)
        # ou se farm_data não foi obtido (então analise_tokens_deliveries não foi nem tentado)
        if farm_id_submitted and not farm_data_display and not error_message: # Se um ID foi submetido mas não houve dados/erro fatal
            avg_daily_rate_status = 'aguardando_dados' # Ou um status que indique que a busca falhou
        else: # Para requisições GET ou erros antes da análise
             avg_daily_rate_status = 'nao_calculado_ainda' # Ou simplesmente mantém 'placeholder'
        log.info(f"Análise de tokens não disponível ou farm não buscado. Status da taxa: {avg_daily_rate_status}.")
        # effective_avg_daily_rate já é o placeholder

    log.info(f"Renderizando template index.html (Farm ID: {farm_id_submitted}) com effective_avg_daily_rate: {effective_avg_daily_rate}, status: {avg_daily_rate_status}")
    # ---> FIM Define a taxa média diária efetiva para exibição e uso ---

    log.info(f"Renderizando template index.html (Farm ID: {farm_id_submitted})")

    # <<< ADICIONE ESTAS LINHAS DE DEBUG >>>
    print("-" * 30)
    print(f"DEBUG main.py -> farm_data type: {type(farm_data_display)}")
    print(f"DEBUG main.py -> error_message: {error_message}")
    print(f"DEBUG main.py -> npc_rates: {npc_completion_rates}")
    print(f"DEBUG main.py -> analise_tokens: {analise_tokens_deliveries}")
    print(f"DEBUG main.py -> effective_avg_daily_rate: {effective_avg_daily_rate}")
    print(f"DEBUG main.py -> avg_daily_rate_status: {avg_daily_rate_status}") # << NOVO DEBUG PRINT
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
                           bounties_data=bounties_data,
                           # Dados Gerais e de Configuração
                           token_name=seasonal_token_name,
                           config=config, # Passa config para acesso a constantes no template
                           shop_items_all=itens_loja_completo,
                           shop_items_ticket=itens_loja_tickets, # Apenas itens de ticket (se necessário)
                           avg_daily_rate=effective_avg_daily_rate, # Placeholder inicial
                           avg_daily_rate_status=avg_daily_rate_status,
                           current_year=current_year,
                           app_version=app_version,
                           bumpkin_image_url=bumpkin_image_url,
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
    historical_rate_from_js = data.get('historical_rate') #Pega a taxa histórica
    marked_item_names = data.get('marked_items', []) # Pega a lista, default: lista vazia []

    log.info(f"Calculando projeção AJAX - Item: {item_name}, Taxa Simulada (do input): {simulated_rate_str}, Taxa Histórica (do JS): {historical_rate_from_js}, Marcados: {marked_item_names}")

    if not item_name:
        log.warning("Requisição AJAX sem 'item_name'.")
        return jsonify({"success": False, "error": "Nome do item não fornecido"}), 400

    # Carrega itens da loja do config
    itens_loja_completo = getattr(config, 'SEASONAL_SHOP_ITEMS', {})
    if not itens_loja_completo:
         log.error("Configuração SEASONAL_SHOP_ITEMS não encontrada ou vazia em config.py")
         return jsonify({"success": False, "error": "Configuração interna da loja não encontrada"}), 500

    # <<< ATUALIZA A CHAMADA PARA determine_active_daily_rate >>>
    # Passa a taxa simulada, a taxa histórica recebida do JS, o logger e o placeholder global.
    rate_to_use, is_simulation = route_helpers.determine_active_daily_rate(
        simulated_rate_str,         # Taxa do campo de simulação (pode ser None)
        historical_rate_from_js,    # Taxa do data-attribute (pode ser None)
        log,
        default_placeholder_rate=10.0 # Placeholder global se nenhuma das outras for válida/fornecida
    )
    # <<< FIM DA ATUALIZAÇÃO DA CHAMADA >>>

    # <<< CHAMADA PARA A NOVA FUNÇÃO DE CÁLCULO DE DIAS RESTANTES >>>
    season_end_date_config_str = getattr(config, 'SEASON_END_DATE', None)
    # A classe 'datetime' já está importada no escopo global do main.py
    remaining_days = route_helpers.calculate_remaining_season_days(season_end_date_config_str, datetime, log)
    # A variável 'datetime' aqui se refere à classe datetime importada de from datetime import datetime

    # --- Calcula Custo, Itens de Desbloqueio e Dias Projetados ---
    try:
        # <<< CHAMADA PARA A NOVA FUNÇÃO DE CÁLCULO DETALHADO >>>
        projection_details = route_helpers.get_projection_calculation_details(
            item_name,
            itens_loja_completo,
            marked_item_names,
            rate_to_use,
            analysis, # Passa o módulo analysis
            log
        )

        # Desempacota os resultados
        custo_total_calculado = projection_details["custo_total_calculado"]
        custo_item_base = projection_details["custo_item_base"]
        custo_desbloqueio_calculado = projection_details["custo_desbloqueio_calculado"]
        unlock_items_detalhados = projection_details["unlock_items_detalhados"]
        unlock_items_list = projection_details["unlock_items_list"]
        dias_projetados = projection_details["dias_projetados"]
        
        log.info(f"Resultados Cálculo AJAX para '{item_name}': Custo={custo_total_calculado}, Dias={dias_projetados} (Taxa Usada={rate_to_use})")

        return jsonify({
            "success": True, # Sucesso na execução da rota, mesmo que o item não possa ser adquirido
            "item_name": item_name,
            "calculated_cost": custo_total_calculado if custo_total_calculado != float('inf') else None,
            "projected_days": dias_projetados if dias_projetados != float('inf') else None,
            "avg_daily_rate_used": rate_to_use, # Esta é a taxa efetivamente usada no cálculo
            "is_simulation": is_simulation, # Usa o 'simulated_rate' original para esta flag
            "token_name": getattr(config, 'SEASONAL_TOKEN_NAME', 'Ticket'),
            "unlock_path_items": unlock_items_list,
            "base_item_cost": custo_item_base,
            "calculated_unlock_cost": custo_desbloqueio_calculado if custo_desbloqueio_calculado != float('inf') else None,
            "unlock_path_items_details": unlock_items_detalhados, 
            "remaining_season_days": remaining_days
        })

    except Exception as e: # Erro mais genérico na orquestração da calculate_projection
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