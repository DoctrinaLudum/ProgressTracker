# analysis.py (Versão Final com Cálculo de Bônus DETALHADO Separado)
import logging
import math
import statistics
import time  # Importa time para checar VIP
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import config  # Importa o config inteiro
import database_utils  # Funções Firestore

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
    current_time_ms = int(time.time() * 1000) # Usado para VIP
    today_date_str = datetime.now().strftime('%Y-%m-%d') # Data de hoje para comparar com eventos

    # Dados relevantes do JSON
    vip_data = farm_data.get("vip", {})
    equipped_bumpkin = farm_data.get("bumpkin", {}).get("equipped", {})
    equipped_farmhands = farm_data.get("farmHands", {}).get("bumpkins", {})
    collectibles_home = farm_data.get("home", {}).get("collectibles", {})
    collectibles_farm = farm_data.get("collectibles", {})
    calendar_dates_from_api = farm_data.get("calendar", {}).get("dates", [])

    # Buffs configurados
    wearable_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "equipped"}
    collectible_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "collectible"}

    log.debug(f"Iniciando cálculo detalhado de bônus...")

    # 1. Check VIP
    if "vip" in config_buffs and config_buffs["vip"]["type"] == "vip":
        if vip_data.get("expiresAt", 0) > current_time_ms:
            # Tenta 'bonus_value' primeiro, depois 'bonus'
            bonus_value = config_buffs["vip"].get("bonus_value", config_buffs["vip"].get("bonus", 0))
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
             if buff_key not in active_buff_details: # Evita contar duas vezes o mesmo buff
                 bonus_value = buff_info.get("bonus_value", buff_info.get("bonus", 0))
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
            if buff_key not in active_buff_details: # Evita contar duas vezes o mesmo buff
                bonus_value = buff_info.get("bonus_value", buff_info.get("bonus", 0))
                total_bonus += bonus_value
                active_buff_details[buff_key] = True # <<< Adiciona detalhe do item
                log.debug(f"  - Buff Colecionável '{buff_key}' Ativo (+{bonus_value})")

    # 4. Check Calendar Events (e.g., doubleDelivery)
    if isinstance(calendar_dates_from_api, list):
        for event_date_obj in calendar_dates_from_api:
            if isinstance(event_date_obj, dict) and \
               event_date_obj.get("name") == "doubleDelivery" and \
               event_date_obj.get("date") == today_date_str:
                active_buff_details["is_double_delivery_active"] = True
                log.debug(f"  - Evento 'doubleDelivery' ATIVO HOJE ({today_date_str})")
                # Não adicionamos ao total_bonus aqui, pois é um multiplicador
                break # Encontrou o evento de hoje, pode parar

    log.info(f"Bônus total (aditivo): +{total_bonus}. Detalhes Ativos: {list(active_buff_details.keys())}")
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

# ---> Funçãos para Cálculo de Bônus em Atividades (Bounties, Chores, etc.) ---
def calculate_bonus_for_activity(
    active_player_bonus_names: List[str],
    activity_type: str,
    defined_player_bonuses: Dict[str, Any], # Ex: config.SEASONAL_DELIVERY_BUFFS
    activity_rules_config: Dict[str, Any],  # Ex: config.ACTIVITY_BONUS_RULES
) -> int:
    """
    Calcula o valor total do bônus aplicável para uma dada atividade
    com base nos bônus ativos do jogador e nas regras da atividade.

    Args:
        active_player_bonus_names: Lista de nomes dos bônus ativos (ex: ['vip', 'Flower Mask']).
        activity_type: String identificando a atividade (ex: 'animal_bounties', 'chores').
        defined_player_bonuses: Dicionário com as definições de todos os bônus possíveis (do config).
        activity_rules_config: Dicionário com as regras de aplicação de bônus por atividade (do config).

    Returns:
        O valor total do bônus (ex: 1, 2, etc.).
    """
    total_bonus_value = 0
    activity_rules = activity_rules_config.get(activity_type)

    if not activity_rules:
        log.warning(f"Nenhuma regra de bônus definida em ACTIVITY_BONUS_RULES para a atividade: {activity_type}")
        return 0

    applicable_bonus_sources_for_activity = activity_rules.get("applicable_bonuses", [])

    for bonus_name_from_player in active_player_bonus_names:
        if bonus_name_from_player in applicable_bonus_sources_for_activity:
            bonus_definition = defined_player_bonuses.get(bonus_name_from_player)
            if bonus_definition:
                # Usamos 'bonus_value' como definido em nosso config.py para SEASONAL_DELIVERY_BUFFS
                total_bonus_value += bonus_definition.get("bonus_value", bonus_definition.get("bonus", 0)) # Compatibilidade com 'bonus' ou 'bonus_value'
            else:
                log.warning(f"Definição não encontrada em SEASONAL_DELIVERY_BUFFS para o bônus '{bonus_name_from_player}' que é aplicável à atividade '{activity_type}'.")
    
    if total_bonus_value > 0:
        log.info(f"Bônus total de +{total_bonus_value} calculado para '{activity_type}' (Bônus ativos do jogador: {active_player_bonus_names}, Bônus aplicáveis à atividade: {applicable_bonus_sources_for_activity})")
    return total_bonus_value
# ---> FIM Função para Cálculo de Bônus em Atividades (Bounties, Chores, etc.) ---

# ---> Função Aplicação de Bônus em Atividades (Bounties, Chores, etc.) ---

def apply_bonus_to_reward(
    reward_object: Dict[str, Any], 
    bonus_value: int,
    activity_rule: Dict[str, Any], # A entrada específica de config.ACTIVITY_BONUS_RULES[activity_type]
    seasonal_token_name: str, 
) -> Dict[str, Any]:
    """
    Aplica um bônus calculado a um objeto de recompensa, modificando-o.
    Suporta 'numeric_token' e 'item_dict' como reward_type.

    Args:
        reward_object: O dicionário da bounty ou da recompensa a ser modificado.
        bonus_value: O valor do bônus a ser aplicado.
        activity_rule: As regras da atividade (de config.ACTIVITY_BONUS_RULES) que definem
                       como aplicar o bônus (reward_type, target_field_name, etc.).
        seasonal_token_name: O nome do token sazonal (ex: "Geniseed").

    Returns:
        O dicionário reward_object modificado.
    """
    if bonus_value == 0:
        return reward_object # Sem alterações se não há bônus

    reward_type = activity_rule.get("reward_type")
    # Modificaremos o objeto diretamente, pois em route_helpers.py já se espera que
    # uma cópia seja feita antes de chamar esta função, se necessário.

    if reward_type == "numeric_token":
        target_field = activity_rule.get("target_field_name")
        if target_field and target_field in reward_object and isinstance(reward_object[target_field], (int, float)):
            original_value = reward_object[target_field]
            reward_object[target_field] = original_value + bonus_value
            reward_object['applied_bonus_value'] = reward_object.get('applied_bonus_value', 0) + bonus_value
            reward_object['base_reward_value'] = original_value
            reward_object['is_bonus_applied'] = True
            log.info(f"Bônus de +{bonus_value} aplicado ao campo '{target_field}' da recompensa '{reward_object.get('name', 'N/A')}' (era {original_value}, agora {reward_object[target_field]})")
        # Adicionar logs de erro/aviso se target_field não existir ou não for numérico

    elif reward_type == "item_dict":
        # Implementação para item_dict (como discutido anteriormente)
        item_container_field = activity_rule.get("item_container_field")
        target_item_keys = activity_rule.get("target_item_keys", [])
        if item_container_field and item_container_field in reward_object and isinstance(reward_object.get(item_container_field), dict):
            items_dict = reward_object[item_container_field]
            bonus_applied_this_call = False
            for item_key_to_buff in target_item_keys:
                if item_key_to_buff in items_dict and isinstance(items_dict[item_key_to_buff], (int, float)):
                    original_value = items_dict[item_key_to_buff]
                    items_dict[item_key_to_buff] += bonus_value
                    log.info(f"Bônus de +{bonus_value} aplicado ao item '{item_key_to_buff}' em '{item_container_field}' da recompensa '{reward_object.get('name', 'N/A')}'. Era {original_value}, agora {items_dict[item_key_to_buff]}")
                    if item_key_to_buff == seasonal_token_name: # Guarda o valor base do token sazonal
                        reward_object['base_reward_value'] = original_value
                    bonus_applied_this_call = True
            if bonus_applied_this_call:
                reward_object['applied_bonus_value'] = reward_object.get('applied_bonus_value', 0) + bonus_value
                reward_object['is_bonus_applied'] = True
        # Adicionar logs de erro/aviso se campos não existirem ou não forem do tipo esperado

    else:
        log.warning(f"Tipo de recompensa desconhecido ou não suportado: '{reward_type}' nas regras da atividade '{activity_rule.get('description', 'N/A')}'.")

    return reward_object

# ---> FIM Função Aplicação de Bônus em Atividades (Bounties, Chores, etc.) ---

# --- LÓGICA PARA PROJEÇÕES SAZONAIS (MODIFICADA) ---

# Custo Minimo (MODIFICADO para retornar detalhes dos itens no caminho)
def calcular_custo_minimo_desbloqueio(tier_alvo, itens_loja, marked_item_names):
    """
    Calcula o custo mínimo em TICKETS para desbloquear um tier, considerando itens
    pré-marcados (Opção B). Retorna custo de desbloqueio e lista detalhada
    de todos os itens usados no caminho.

    Args:
        tier_alvo (int): Tier a alcançar.
        itens_loja (dict): Dicionário de itens.
        marked_item_names (list[str]): Lista de nomes dos itens marcados.

    Returns:
        dict: {'unlock_cost': int | float('inf'), 'unlock_items_details': list[dict]}
              Retorna custo de desbloqueio (só tickets) e lista de dicionários
              com detalhes de cada item no caminho [{'name':..., 'cost':..., 'currency':...}].
    """
    if not isinstance(itens_loja, dict) or not itens_loja:
        # ... (validação loja) ...
        return {'unlock_cost': float('inf'), 'unlock_items_details': []}
    if not isinstance(tier_alvo, int) or tier_alvo <= 1:
        return {'unlock_cost': 0, 'unlock_items_details': []}

    total_unlock_cost_tickets = 0
    final_unlock_items_details_list = [] # Lista para guardar dicts de detalhes
    marked_item_names_set = set(marked_item_names)

    log.debug(f"Calculando custo desbloqueio detalhado para Tier {tier_alvo} com marcados: {marked_item_names}")

    for tier_a_comprar in range(1, tier_alvo):
        log.debug(f" -> Analisando Tier {tier_a_comprar}...")

        # 1. Itens pré-selecionados neste tier
        preselected_in_tier_names = [
            name for name in marked_item_names_set
            if itens_loja.get(name, {}).get('tier') == tier_a_comprar
        ]
        num_preselected = len(preselected_in_tier_names)
        log.debug(f"    Itens pré-selecionados: {num_preselected} ({preselected_in_tier_names})")

        # Adiciona detalhes dos pré-selecionados à lista final
        for name in preselected_in_tier_names:
            data = itens_loja.get(name, {})
            final_unlock_items_details_list.append({
                'name': name,
                'cost': data.get('cost'),
                'currency': data.get('currency'),
                'tier': tier_a_comprar,
                'source': 'marked' # Indica que foi marcado pelo usuário
            })

        # 2. Calcula quantos itens AINDA são necessários
        needed = max(0, 4 - num_preselected)
        log.debug(f"    Itens adicionais necessários: {needed}")

        # 3. Calcula custo (TICKETS) dos pré-selecionados
        cost_of_preselected_tickets = sum(
            itens_loja[name]['cost'] for name in preselected_in_tier_names
            if itens_loja[name].get('currency') == 'ticket' and isinstance(itens_loja[name].get('cost'), (int, float))
        )
        log.debug(f"    Custo (Tickets) dos pré-selecionados: {cost_of_preselected_tickets}")

        # 4. Encontra e calcula custo dos itens de ticket mais baratos para completar
        cost_of_needed_tickets = 0
        names_of_needed = []
        if needed > 0:
            candidates = []
            for name, data in itens_loja.items():
                if (data.get('tier') == tier_a_comprar and
                    data.get('currency') == 'ticket' and
                    isinstance(data.get('cost'), (int, float)) and data['cost'] > 0 and
                    name not in marked_item_names_set): # Não pode estar pré-selecionado
                      candidates.append({'name': name, 'cost': data['cost'], 'currency': 'ticket', 'tier': tier_a_comprar, 'source': 'calculated'})

            log.debug(f"    Candidatos (ticket, não marcados): {len(candidates)}")
            if len(candidates) < needed:
                log.warning(f"Impossível desbloquear Tier {tier_a_comprar + 1}! Faltam itens de TICKET não marcados no Tier {tier_a_comprar}.")
                return {'unlock_cost': float('inf'), 'unlock_items_details': []}

            candidates.sort(key=lambda item: item['cost'])
            cheapest_needed_details = candidates[:needed] # Lista de dicts
            cost_of_needed_tickets = sum(item['cost'] for item in cheapest_needed_details)
            names_of_needed = [item['name'] for item in cheapest_needed_details] # Pega só nomes se precisar, mas já temos detalhes
            log.debug(f"    Itens mais baratos escolhidos para completar ({needed}): {names_of_needed} (Custo: {cost_of_needed_tickets})")

            # Adiciona detalhes dos itens necessários à lista final
            final_unlock_items_details_list.extend(cheapest_needed_details)

        # 5. Soma os custos de tickets para este tier
        cost_tier_atual_tickets = cost_of_preselected_tickets + cost_of_needed_tickets
        total_unlock_cost_tickets += cost_tier_atual_tickets
        log.debug(f"    Custo total de TICKETS adicionado para Tier {tier_a_comprar}: {cost_tier_atual_tickets}")

    log.info(f"Custo total de DESBLOQUEIO (Tickets) para Tier {tier_alvo}: {total_unlock_cost_tickets}.")
    # Ordena a lista final por tier e depois por nome para consistência (opcional)
    final_unlock_items_details_list.sort(key=lambda x: (x.get('tier', 0), x.get('name', '')))

    return {'unlock_cost': int(round(total_unlock_cost_tickets)), 'unlock_items_details': final_unlock_items_details_list}


# Custo Total (MODIFICADO para retornar mais detalhes)
def calcular_custo_total_item(nome_item_alvo, itens_loja, marked_item_names):
    """
    Calcula o custo total em TICKETS, custo base, custo de desbloqueio e
    retorna lista detalhada de itens do caminho de desbloqueio.

    Args:
        nome_item_alvo (str): Nome do item.
        itens_loja (dict): Dicionário de itens.
        marked_item_names (list[str]): Lista de nomes marcados.

    Returns:
        dict: {
            'total_cost': int | float('inf'),
            'item_cost': int | None,
            'unlock_cost': int | float('inf'),
            'unlock_items_details': list[dict]
        }
    """
    if not isinstance(itens_loja, dict) or not itens_loja: # ... validação loja ...
        return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    item_data = itens_loja.get(nome_item_alvo)
    if not item_data: # ... validação item existe ...
        return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}

    item_cost = item_data.get('cost')
    item_currency = item_data.get('currency')
    item_tier = item_data.get('tier')
    base_item_cost_tickets = 0 # Custo base do item alvo em tickets

    # Validações do item alvo
    if item_currency != 'ticket': # ... validação moeda ...
         # Se o item alvo não for de ticket, o custo total é infinito para nosso cálculo
         log.warning(f"Item alvo '{nome_item_alvo}' não é de ticket.")
         return {'total_cost': float('inf'), 'item_cost': item_cost, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    if not isinstance(item_cost, (int, float)) or item_cost <= 0: # ... validação custo ...
         return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    else:
        base_item_cost_tickets = item_cost # Guarda o custo base se for de ticket

    if not isinstance(item_tier, int) or item_tier < 1: # ... validação tier ...
         return {'total_cost': float('inf'), 'item_cost': base_item_cost_tickets, 'unlock_cost': float('inf'), 'unlock_items_details': []}

    log.debug(f"Calculando custo total detalhado para '{nome_item_alvo}' com marcados: {marked_item_names}")

    # Calcula custo de desbloqueio E pega lista detalhada de itens do caminho
    unlock_info = calcular_custo_minimo_desbloqueio(item_tier, itens_loja, marked_item_names)
    custo_desbloqueio_tickets = unlock_info['unlock_cost']
    unlock_items_details_list = unlock_info['unlock_items_details']

    log.debug(f" -> Custo desbloqueio (Tickets): {custo_desbloqueio_tickets}. Itens caminho: {len(unlock_items_details_list)} itens.")

    if custo_desbloqueio_tickets == float('inf'):
        log.warning(f"Não é possível calcular custo total para '{nome_item_alvo}', tier não desbloqueável.")
        # Retorna infinito, mas inclui custo base e detalhes parciais se houver
        return {'total_cost': float('inf'), 'item_cost': base_item_cost_tickets, 'unlock_cost': float('inf'), 'unlock_items_details': unlock_items_details_list}

    # Custo total em tickets = custo do próprio item + custo de tickets do desbloqueio
    custo_total_tickets = custo_desbloqueio_tickets + base_item_cost_tickets

    log.info(f"Custo total estimado (Tickets) para '{nome_item_alvo}': {custo_total_tickets} (Item: {base_item_cost_tickets}, Desbloq: {custo_desbloqueio_tickets})")
    return {
        'total_cost': int(round(custo_total_tickets)),
        'item_cost': int(round(base_item_cost_tickets)),
        'unlock_cost': int(round(custo_desbloqueio_tickets)),
        'unlock_items_details': unlock_items_details_list # Lista detalhada
    }
    """
    Calcula o custo total em TICKETS para adquirir um item, considerando itens
    pré-marcados para o desbloqueio (Opção B). Retorna custo total e lista de
    todos os itens usados no caminho.

    Args:
        nome_item_alvo (str): O nome do item desejado.
        itens_loja (dict): Dicionário de itens.
        marked_item_names (list[str]): Lista de nomes dos itens marcados.

    Returns:
        dict: {'cost': int | float('inf'), 'unlock_items': list[str]}
    """
    if not isinstance(itens_loja, dict) or not itens_loja: # ... (validação loja) ...
        return {'cost': float('inf'), 'unlock_items': []}
    item_data = itens_loja.get(nome_item_alvo)
    if not item_data: # ... (validação item existe) ...
        return {'cost': float('inf'), 'unlock_items': []}

    item_cost = item_data.get('cost')
    item_currency = item_data.get('currency')
    item_tier = item_data.get('tier')

    # Validações do item alvo
    if item_currency != 'ticket': # ... (validação moeda) ...
        return {'cost': float('inf'), 'unlock_items': []}
    if not isinstance(item_cost, (int, float)) or item_cost <= 0: # ... (validação custo) ...
        return {'cost': float('inf'), 'unlock_items': []}
    if not isinstance(item_tier, int) or item_tier < 1: # ... (validação tier) ...
        return {'cost': float('inf'), 'unlock_items': []}

    log.debug(f"Calculando custo total para '{nome_item_alvo}' com marcados: {marked_item_names}")

    # Calcula o custo de desbloqueio (agora considera marcados) E pega a lista de itens
    unlock_info = calcular_custo_minimo_desbloqueio(item_tier, itens_loja, marked_item_names)
    custo_desbloqueio_tickets = unlock_info['cost']
    unlock_items_list = unlock_info['unlock_items'] # Lista COMPLETA do caminho

    log.debug(f" -> Custo desbloqueio (Tickets): {custo_desbloqueio_tickets}. Itens caminho: {unlock_items_list}")

    if custo_desbloqueio_tickets == float('inf'):
        log.warning(f"Não é possível calcular custo total para '{nome_item_alvo}', tier não desbloqueável com itens marcados/disponíveis.")
        return {'cost': float('inf'), 'unlock_items': []}

    # Custo total em tickets = custo do próprio item + custo de tickets do desbloqueio
    custo_total_tickets = custo_desbloqueio_tickets + item_cost

    log.info(f"Custo total estimado (Tickets) para '{nome_item_alvo}': {custo_total_tickets}. Itens caminho: {unlock_items_list}")
    # Retorna custo total e a lista de itens DO CAMINHO (para destaque no JS)
    return {'cost': int(round(custo_total_tickets)), 'unlock_items': unlock_items_list}

# --- Fim da Lógica de Projeções ---

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