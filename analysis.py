# analysis.py (Versão Final com Cálculo de Bônus DETALHADO Separado)
import database_utils # Funções Firestore
import config # Importa o config inteiro
from datetime import datetime, timedelta
import math
import logging
import statistics
import time # Importa time para checar VIP

log = logging.getLogger(__name__)

# --- FUNÇÃO PARA CALCULAR BÔNUS (Retorna Detalhes) ---
def calculate_delivery_bonus(farm_data, config_buffs):
    """
    Calcula o bônus total E detalha quais buffs estão ativos.
    Verifica VIP, itens equipados (Bumpkin + FarmHands) e colecionáveis (home + farm).

    Args:
        farm_data (dict): O dicionário de dados da fazenda vindo da API (nível 'farm').
        config_buffs (dict): O dicionário SEASONAL_DELIVERY_BUFFS do config.py.

    Returns:
        dict: {'total_bonus': int, 'details': dict}
              Onde 'details' tem chaves como 'vip', 'NomeDoItemConfig', etc.,
              com valor True se o buff específico estiver ativo.
    """
    if not farm_data:
        return {'total_bonus': 0, 'details': {}} # Retorna estrutura vazia

    total_bonus = 0
    active_buff_details = {} # <<< Dicionário para detalhes
    current_time_ms = int(time.time() * 1000)

    # Dados relevantes do JSON
    vip_data = farm_data.get("vip", {})
    equipped_bumpkin = farm_data.get("bumpkin", {}).get("equipped", {})
    equipped_farmhands = farm_data.get("farmHands", {}).get("bumpkins", {})
    collectibles_home = farm_data.get("home", {}).get("collectibles", {})
    collectibles_farm = farm_data.get("collectibles", {})

    # Buffs configurados
    wearable_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "equipped"}
    collectible_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "collectible"}

    log.debug(f"Iniciando cálculo detalhado de bônus...")

    # 1. Check VIP
    if "vip" in config_buffs and config_buffs["vip"]["type"] == "vip":
        if vip_data.get("expiresAt", 0) > current_time_ms:
            bonus_value = config_buffs["vip"]["bonus"]
            total_bonus += bonus_value
            active_buff_details["vip"] = True # <<< Adiciona detalhe 'vip'
            log.debug(f"  - Buff VIP Ativo (+{bonus_value})")

    # 2. Check Equipped Wearables (Main Bumpkin + FarmHands)
    all_equipped_items_names = set()
    if isinstance(equipped_bumpkin, dict): all_equipped_items_names.update(equipped_bumpkin.values())
    if isinstance(equipped_farmhands, dict):
        for hand_id, hand_data in equipped_farmhands.items():
            hand_equipped = hand_data.get("equipped", {})
            if isinstance(hand_equipped, dict): all_equipped_items_names.update(hand_equipped.values())

    log.debug(f"  - Itens equipados (total): {all_equipped_items_names}")
    for buff_key, buff_info in wearable_buff_configs.items():
         if buff_key.startswith("PLACEHOLDER_"): continue # Pula placeholders
         if buff_key in all_equipped_items_names:
             if buff_key not in active_buff_details: # Evita contar duas vezes
                 bonus_value = buff_info.get("bonus", 0)
                 total_bonus += bonus_value
                 active_buff_details[buff_key] = True # <<< Adiciona detalhe do item
                 log.debug(f"  - Buff Equipado '{buff_key}' Ativo (+{bonus_value})")

    # 3. Check Collectibles (Home + Farm level)
    all_placed_collectibles_names = set()
    if isinstance(collectibles_home, dict): all_placed_collectibles_names.update(collectibles_home.keys())
    if isinstance(collectibles_farm, dict): all_placed_collectibles_names.update(collectibles_farm.keys())

    log.debug(f"  - Colecionáveis colocados: {all_placed_collectibles_names}")
    for buff_key, buff_info in collectible_buff_configs.items():
        if buff_key.startswith("PLACEHOLDER_"): continue
        if buff_key in all_placed_collectibles_names:
            if buff_key not in active_buff_details:
                bonus_value = buff_info.get("bonus", 0)
                total_bonus += bonus_value
                active_buff_details[buff_key] = True # <<< Adiciona detalhe do item
                log.debug(f"  - Buff Colecionável '{buff_key}' Ativo (+{bonus_value})")

    log.info(f"Bônus total: +{total_bonus}. Detalhes Ativos: {list(active_buff_details.keys())}")
    # <<< RETORNA O DICIONÁRIO COMPLETO >>>
    return {'total_bonus': total_bonus, 'details': active_buff_details}


# --- Função Auxiliar Interna _get_period_change_v4 (Mantida EXATAMENTE como você enviou) ---
def _get_period_change_v4(farm_id, npc_id, data_inicio_str, data_fim_str, primeira_data_farm_str):
    # ... (código completo da função _get_period_change_v4 aqui, sem alterações)...
    """ Retorna dict: {'deliveries_change': X, 'skips_change': Y, 'used_zero_base_fallback': bool} ou {'erro': 'mensagem'}. """
    try:
        farm_id_int = int(farm_id); data_final_periodo = data_fim_str
        data_anterior_inicio = (datetime.strptime(data_inicio_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        snapshot_final_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_final_periodo)
        if snapshot_final_data is None:
            snapshot_ontem = database_utils.get_snapshot_from_db(farm_id_int, npc_id, (datetime.strptime(data_fim_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d'))
            if snapshot_ontem: log.warning(f"Snapshot final ({data_final_periodo}) não encontrado. Usando dia anterior."); snapshot_final_data = snapshot_ontem
            else: erro_msg = f"Snapshot final ({data_final_periodo}) não encontrado."; log.error(f"{erro_msg} para {farm_id_int}/{npc_id}."); return {'erro': erro_msg, 'used_zero_base_fallback': False}
        count_fim = snapshot_final_data.get('deliveryCount', 0); skips_fim = snapshot_final_data.get('skipCount', 0)
        count_base = 0; skips_base = 0; used_zero_base_fallback = False
        snapshot_anterior_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_anterior_inicio)
        if snapshot_anterior_data is not None:
            count_base = snapshot_anterior_data.get('deliveryCount', 0); skips_base = snapshot_anterior_data.get('skipCount', 0)
            log.debug(f"Snapshot base ({data_anterior_inicio}) encontrado: {count_base}")
        else:
            if data_inicio_str == primeira_data_farm_str:
                log.info(f"Dia anterior {data_anterior_inicio} não encontrado, {data_inicio_str} é o primeiro dia.")
                snapshot_inicio_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_inicio_str)
                if snapshot_inicio_data: count_base = snapshot_inicio_data.get('deliveryCount', 0); skips_base = snapshot_inicio_data.get('skipCount', 0); log.info(f"Usando base do 1º dia ({data_inicio_str}): {count_base}")
                else: log.warning(f"Snapshots anterior ({data_anterior_inicio}) e 1º dia ({data_inicio_str}) não encontrados. Usando base 0."); count_base = 0; skips_base = 0; used_zero_base_fallback = True
            else: erro_msg = f"Snapshot base ({data_anterior_inicio}) não encontrado."; log.warning(f"{erro_msg} para {farm_id_int}/{npc_id}."); return {'erro': erro_msg, 'used_zero_base_fallback': False}
        deliveries_change = max(0, count_fim - count_base); skips_change = max(0, skips_fim - skips_base)
        log.debug(f"Calculo V4 {farm_id_int}/{npc_id}: Fim({data_fim_str})={count_fim} / Base={count_base} -> Change={deliveries_change}")
        return {'deliveries_change': deliveries_change, 'skips_change': skips_change, 'used_zero_base_fallback': used_zero_base_fallback}
    except Exception as e: log.exception(f"Erro mudança V4 {farm_id}/{npc_id}:"); return {'erro': f'Erro cálculo mudança V4 {npc_id}', 'used_zero_base_fallback': False} # Use farm_id_int here


# --- FUNÇÃO PRINCIPAL DE ANÁLISE (Mantida como na sua versão, recebendo só o total_bonus) ---
def calcular_estimativa_token_deliveries(farm_id, data_inicio_str, data_fim_str, primeira_data_farm_str, total_bonus_per_delivery):
    # ... (Código EXATAMENTE como na sua versão anterior, que já incluía a lógica de zerar totais) ...
    # ... NENHUMA MUDANÇA NECESSÁRIA AQUI ...
    """Calcula estimativas de conclusões, tokens (BASE + BÔNUS) e custo SFL..."""
    if not database_utils.db: return {'erro': 'Cliente DB não inicializado', 'dados_completos': False}
    try: farm_id_int = int(farm_id) # Define farm_id_int aqui
    except (ValueError, TypeError): return {'erro': 'Farm ID inválido', 'dados_completos': False}
    npcs_e_tokens_base = config.BASE_DELIVERY_REWARDS
    if not npcs_e_tokens_base: return {'total_conclusoes': 0, 'total_tokens_estimados': 0, 'total_custo_estimado_sfl': 0.0, 'detalhes_por_npc': {}, 'dados_completos': True}
    total_conclusoes_geral = 0; total_tokens_estimados_geral = 0; total_custo_estimado_geral_sfl = 0.0
    detalhes = {}; dados_completos_geral = True
    log.info(f"Calculando análise para Farm ID {farm_id} ({data_inicio_str} a {data_fim_str}), 1º dia: {primeira_data_farm_str}, Bônus/Entrega: +{total_bonus_per_delivery}")
    try: start_date = datetime.strptime(data_inicio_str, '%Y-%m-%d'); end_date = datetime.strptime(data_fim_str, '%Y-%m-%d'); num_days_in_period = (end_date - start_date).days + 1;
    except ValueError: return {'erro': 'Datas inválidas', 'dados_completos': False}
    for npc_id, base_token_reward in npcs_e_tokens_base.items():
        resultado_mudanca = _get_period_change_v4(farm_id_int, npc_id, data_inicio_str, data_fim_str, primeira_data_farm_str)
        detalhes_npc = {'status': 'ok', 'conclusoes': 0, 'tokens_estimados': 0, 'custo_total_estimado_sfl': 0.0, 'base_por_entrega': base_token_reward, 'custo_medio_diario': 0.0, 'custo_status': 'sem_dados', 'is_accumulated': False }
        if resultado_mudanca and 'erro' not in resultado_mudanca:
            conclusoes_npc_periodo = resultado_mudanca.get('deliveries_change', 0); is_accumulated_flag = resultado_mudanca.get('used_zero_base_fallback', False); detalhes_npc['is_accumulated'] = is_accumulated_flag
            if is_accumulated_flag: detalhes_npc['conclusoes'] = 0; detalhes_npc['tokens_estimados'] = 0; log.info(f"  -> {farm_id_int}/{npc_id}: 0 C (Mudança real não calculável - Base 0 usada)")
            elif conclusoes_npc_periodo >= 0:
                detalhes_npc['conclusoes'] = conclusoes_npc_periodo
                if conclusoes_npc_periodo > 0: effective_reward_per_delivery = base_token_reward + total_bonus_per_delivery; tokens_estimados_npc = conclusoes_npc_periodo * effective_reward_per_delivery; detalhes_npc['tokens_estimados'] = tokens_estimados_npc; total_tokens_estimados_geral += tokens_estimados_npc
                else: detalhes_npc['tokens_estimados'] = 0
                total_conclusoes_geral += conclusoes_npc_periodo
                daily_costs_list = database_utils.get_daily_costs_for_npc(farm_id_int, npc_id, data_inicio_str, data_fim_str); custo_total_npc_periodo = sum(daily_costs_list); detalhes_npc['custo_total_estimado_sfl'] = round(custo_total_npc_periodo, 4); total_custo_estimado_geral_sfl += custo_total_npc_periodo
                if daily_costs_list:
                    try: detalhes_npc['custo_medio_diario'] = round(statistics.mean(daily_costs_list), 4)
                    except: pass
                    if len(daily_costs_list) < num_days_in_period: detalhes_npc['custo_status'] = 'parcial'
                    else: detalhes_npc['custo_status'] = 'completo'
                else:
                     if conclusoes_npc_periodo == 0 and not is_accumulated_flag: detalhes_npc['custo_status'] = 'nao_aplicavel'
                     elif is_accumulated_flag: detalhes_npc['custo_status'] = 'nao_aplicavel'
                     else: detalhes_npc['custo_status'] = 'sem_registros'
                log.info(f"  -> {farm_id_int}/{npc_id}: {conclusoes_npc_periodo} C (M V4; Base0: {detalhes_npc['is_accumulated']}) -> ~{detalhes_npc['tokens_estimados']} {config.SEASONAL_TOKEN_NAME} (B {base_token_reward}+Bôn {total_bonus_per_delivery}) -> ~{custo_total_npc_periodo:.2f} SFL")
        else:
            erro_msg = resultado_mudanca.get('erro', "Erro") if resultado_mudanca else "Erro interno"; log.warning(f"Erro cálculo mudança V4 {npc_id}: {erro_msg}");
            if "não encontrado" in erro_msg: detalhes_npc['status'] = 'dados_insuficientes'
            else: detalhes_npc['status'] = 'erro_calculo'; detalhes_npc['mensagem_erro'] = erro_msg
            detalhes_npc['is_accumulated'] = False; dados_completos_geral = False; detalhes_npc['custo_status'] = 'erro_calculo_base'
        detalhes[npc_id] = detalhes_npc
    # Use farm_id (string) here as farm_id_int might not be defined if the try block failed early (though unlikely with current returns)
    log.info(f"Análise V4 concluída Farm {farm_id}. Conc (Mudança Real):{total_conclusoes_geral}, TokEst:{total_tokens_estimados_geral}, SFLEst:{total_custo_estimado_geral_sfl:.2f}, Completos:{dados_completos_geral}")
    return { 'total_conclusoes': total_conclusoes_geral, 'total_tokens_estimados': total_tokens_estimados_geral, 'total_custo_estimado_sfl': round(total_custo_estimado_geral_sfl, 4), 'detalhes_por_npc': detalhes, 'dados_completos': dados_completos_geral }


# --- LÓGICA PARA PROJEÇÕES SAZONAIS (MODIFICADA) ---

# Custo Minimo (MODIFICADO para retornar itens)
def calcular_custo_minimo_desbloqueio(tier_alvo, itens_loja):
    """
    Calcula o custo mínimo em TICKETS para desbloquear um tier E retorna os itens usados.

    Args:
        tier_alvo (int): O tier que se deseja alcançar (ex: 2, 3, 4).
        itens_loja (dict): O dicionário SEASONAL_SHOP_ITEMS do config.py.

    Returns:
        dict: {'cost': int | float('inf'), 'unlock_items': list[str]}
              Retorna custo e lista de nomes dos itens usados para desbloqueio.
              Retorna custo infinito e lista vazia se impossível.
    """
    if not isinstance(itens_loja, dict) or not itens_loja:
        log.error("calcular_custo_minimo_desbloqueio: Dicionário de itens da loja inválido ou vazio.")
        return {'cost': float('inf'), 'unlock_items': []} # Retorna dict

    if not isinstance(tier_alvo, int) or tier_alvo <= 1:
        return {'cost': 0, 'unlock_items': []} # Sem custo/itens para tier 1

    total_unlock_cost = 0
    unlock_items_list = [] # Lista para guardar os nomes dos itens usados
    log.debug(f"Calculando custo de desbloqueio para alcançar Tier {tier_alvo}")

    for tier_a_comprar in range(1, tier_alvo):
        log.debug(f"  Analisando Tier {tier_a_comprar} para desbloquear Tier {tier_a_comprar + 1}...")

        # 1. Filtra itens do tier atual que custam tickets, guardando (custo, nome)
        itens_do_tier_ticket_with_names = []
        for nome, dados in itens_loja.items():
            if (dados.get('tier') == tier_a_comprar and
                dados.get('currency') == 'ticket' and
                isinstance(dados.get('cost'), (int, float)) and
                dados['cost'] > 0):
                    itens_do_tier_ticket_with_names.append((dados['cost'], nome)) # Guarda (custo, nome)

        log.debug(f"    Itens de Ticket (custo, nome) encontrados no Tier {tier_a_comprar}: {itens_do_tier_ticket_with_names}")

        # 2. Verifica se há itens suficientes
        if len(itens_do_tier_ticket_with_names) < 4:
            log.warning(f"Impossível desbloquear Tier {tier_a_comprar + 1}! Menos de 4 itens de ticket encontrados no Tier {tier_a_comprar}.")
            return {'cost': float('inf'), 'unlock_items': []} # Retorna dict

        # 3. Ordena por custo (primeiro elemento da tupla) e pega os 4 mais baratos
        itens_do_tier_ticket_with_names.sort(key=lambda item: item[0])
        cheapest_four = itens_do_tier_ticket_with_names[:4]

        # 4. Calcula custo do tier e adiciona nomes à lista
        custo_tier_atual = sum(item[0] for item in cheapest_four) # Soma os custos (item[0])
        nomes_tier_atual = [item[1] for item in cheapest_four] # Pega os nomes (item[1])

        log.debug(f"    Custo mínimo para comprar 4 itens do Tier {tier_a_comprar}: {custo_tier_atual} (Itens: {nomes_tier_atual})")
        total_unlock_cost += custo_tier_atual
        unlock_items_list.extend(nomes_tier_atual) # Adiciona os nomes à lista geral

    log.info(f"Custo total mínimo de desbloqueio para Tier {tier_alvo}: {total_unlock_cost}. Itens usados: {unlock_items_list}")
    # Retorna o dicionário com custo e a lista de nomes
    return {'cost': int(round(total_unlock_cost)), 'unlock_items': unlock_items_list}


# Custo Total (MODIFICADO para processar retorno de custo_minimo)
def calcular_custo_total_item(nome_item_alvo, itens_loja):
    """
    Calcula o custo total em TICKETS para adquirir um item específico,
    incluindo o custo mínimo para desbloquear o tier necessário. Retorna também
    a lista de itens usados no desbloqueio.

    Args:
        nome_item_alvo (str): O nome exato do item desejado.
        itens_loja (dict): O dicionário SEASONAL_SHOP_ITEMS.

    Returns:
        dict: {'cost': int | float('inf'), 'unlock_items': list[str]}
              Retorna custo total e lista de nomes dos itens de desbloqueio.
    """
    if not isinstance(itens_loja, dict) or not itens_loja:
        log.error("calcular_custo_total_item: Dicionário de itens da loja inválido ou vazio.")
        return {'cost': float('inf'), 'unlock_items': []}

    item_data = itens_loja.get(nome_item_alvo)
    if not item_data:
        log.error(f"calcular_custo_total_item: Item '{nome_item_alvo}' não encontrado.")
        return {'cost': float('inf'), 'unlock_items': []}

    item_cost = item_data.get('cost')
    item_currency = item_data.get('currency')
    item_tier = item_data.get('tier')

    # Validações (como antes, mas retornando dict em caso de erro)
    if item_currency != 'ticket':
        log.warning(f"calcular_custo_total_item: Item '{nome_item_alvo}' não custa tickets.")
        return {'cost': float('inf'), 'unlock_items': []}
    if not isinstance(item_cost, (int, float)) or item_cost <= 0:
        log.error(f"calcular_custo_total_item: Custo inválido para '{nome_item_alvo}'.")
        return {'cost': float('inf'), 'unlock_items': []}
    if not isinstance(item_tier, int) or item_tier < 1:
        log.error(f"calcular_custo_total_item: Tier inválido para '{nome_item_alvo}'.")
        return {'cost': float('inf'), 'unlock_items': []}

    log.debug(f"Calculando custo total para '{nome_item_alvo}' (Tier {item_tier}, Custo {item_cost} tickets)")

    # Calcula o custo de desbloqueio E pega a lista de itens
    unlock_info = calcular_custo_minimo_desbloqueio(item_tier, itens_loja)
    custo_desbloqueio = unlock_info['cost']
    unlock_items_list = unlock_info['unlock_items'] # Pega a lista retornada

    log.debug(f"  Custo mínimo de desbloqueio para Tier {item_tier}: {custo_desbloqueio}. Itens: {unlock_items_list}")

    if custo_desbloqueio == float('inf'):
        log.warning(f"Não é possível calcular custo total para '{nome_item_alvo}', tier não desbloqueável.")
        return {'cost': float('inf'), 'unlock_items': []} # Retorna lista vazia

    custo_total = custo_desbloqueio + item_cost

    log.info(f"Custo total estimado para '{nome_item_alvo}': {custo_total}. Itens desbloqueio: {unlock_items_list}")
    # Retorna o dicionário com custo total e a lista de itens de desbloqueio
    return {'cost': int(round(custo_total)), 'unlock_items': unlock_items_list}


# Projeção Dias (MODIFICADO para aceitar custo pré-calculado)
def projetar_dias_para_item(custo_total, taxa_media_diaria):
    """
    Estima quantos dias são necessários para obter um item,
    com base no seu custo total em tickets JÁ CALCULADO
    e na taxa média diária de ganho de tickets.

    Args:
        custo_total (int | float): O custo total JÁ CALCULADO do item (incluindo desbloqueio).
        taxa_media_diaria (float): A taxa média estimada de tickets ganhos por dia.

    Returns:
        int | float('inf'): O número estimado de dias necessários (arredondado para cima).
               Retorna float('inf') se a taxa for inválida ou o custo for infinito.
    """
    # 1. Valida a taxa média diária
    if not isinstance(taxa_media_diaria, (int, float)) or taxa_media_diaria <= 0:
        log.warning(f"projetar_dias_para_item: Taxa média diária inválida ou zero ({taxa_media_diaria}).")
        return float('inf')

    # 2. Verifica se o custo é válido (já foi calculado antes)
    if not isinstance(custo_total, (int, float)) or custo_total == float('inf') or custo_total < 0:
        log.warning(f"projetar_dias_para_item: Custo total inválido ({custo_total}).")
        return float('inf')

    # Se custo for 0 (ex: item grátis hipotético), dias são 0
    if custo_total == 0:
        return 0

    # 3. Calcula os dias necessários
    dias_necessarios = custo_total / taxa_media_diaria
    dias_arredondados = math.ceil(dias_necessarios) # Arredonda para cima

    log.info(f"Projeção de dias: {dias_arredondados} (Custo: {custo_total} / Taxa: {taxa_media_diaria:.2f}/dia)")

    return dias_arredondados # Retorna apenas os dias

# --- Fim da Lógica de Projeções --


# --- Bloco de Teste ---
if __name__ == "__main__":
    print("Executando analysis.py como script principal (V4 com bônus detalhado)...")
    # Adicione aqui chamadas de teste se necessário, lembrando que
    # calculate_delivery_bonus agora retorna um dict.
    pass