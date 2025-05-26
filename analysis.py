# analysis.py
import logging
import math
import statistics
import time
from datetime import datetime, timedelta # Alterado para importar datetime diretamente da classe
from typing import Any, Dict, List, Optional

import config
import database_utils

log = logging.getLogger(__name__)

# --- FUNÇÃO PARA CALCULAR BÔNUS (Retorna Detalhes) ---
# ... (código existente de calculate_delivery_bonus - sem alterações) ...
def calculate_delivery_bonus(farm_data, config_buffs):
    if not farm_data:
        return {'total_bonus': 0, 'details': {}} # Retorna estrutura vazia
    total_bonus = 0
    active_buff_details = {} 
    current_time_ms = int(time.time() * 1000) 
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    vip_data = farm_data.get("vip", {})
    equipped_bumpkin = farm_data.get("bumpkin", {}).get("equipped", {})
    equipped_farmhands = farm_data.get("farmHands", {}).get("bumpkins", {})
    collectibles_home = farm_data.get("home", {}).get("collectibles", {})
    collectibles_farm = farm_data.get("collectibles", {})
    calendar_dates_from_api = farm_data.get("calendar", {}).get("dates", [])
    wearable_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "equipped"}
    collectible_buff_configs = {k: v for k, v in config_buffs.items() if v.get("type") == "collectible"}
    log.debug(f"Iniciando cálculo detalhado de bônus...")
    if "vip" in config_buffs and config_buffs["vip"]["type"] == "vip":
        if vip_data.get("expiresAt", 0) > current_time_ms:
            bonus_value = config_buffs["vip"].get("bonus_value", config_buffs["vip"].get("bonus", 0))
            total_bonus += bonus_value
            active_buff_details["vip"] = True 
            log.debug(f"  - Buff VIP Ativo (+{bonus_value})")
    all_equipped_items_names = set()
    if isinstance(equipped_bumpkin, dict): all_equipped_items_names.update(equipped_bumpkin.values())
    if isinstance(equipped_farmhands, dict):
        for hand_id, hand_data in equipped_farmhands.items():
            hand_equipped = hand_data.get("equipped", {})
            if isinstance(hand_equipped, dict): all_equipped_items_names.update(hand_equipped.values())
    log.debug(f"  - Itens equipados (total): {all_equipped_items_names}")
    for buff_key, buff_info in wearable_buff_configs.items():
         if buff_key.startswith("PLACEHOLDER_"): continue 
         if buff_key in all_equipped_items_names:
             if buff_key not in active_buff_details: 
                 bonus_value = buff_info.get("bonus_value", buff_info.get("bonus", 0))
                 total_bonus += bonus_value
                 active_buff_details[buff_key] = True 
                 log.debug(f"  - Buff Equipado '{buff_key}' Ativo (+{bonus_value})")
    all_placed_collectibles_names = set()
    if isinstance(collectibles_home, dict): all_placed_collectibles_names.update(collectibles_home.keys())
    if isinstance(collectibles_farm, dict): all_placed_collectibles_names.update(collectibles_farm.keys())
    log.debug(f"  - Colecionáveis colocados: {all_placed_collectibles_names}")
    for buff_key, buff_info in collectible_buff_configs.items():
        if buff_key.startswith("PLACEHOLDER_"): continue
        if buff_key in all_placed_collectibles_names:
            if buff_key not in active_buff_details: 
                bonus_value = buff_info.get("bonus_value", buff_info.get("bonus", 0))
                total_bonus += bonus_value
                active_buff_details[buff_key] = True 
                log.debug(f"  - Buff Colecionável '{buff_key}' Ativo (+{bonus_value})")
    if isinstance(calendar_dates_from_api, list):
        for event_date_obj in calendar_dates_from_api:
            if isinstance(event_date_obj, dict) and \
               event_date_obj.get("name") == "doubleDelivery" and \
               event_date_obj.get("date") == today_date_str:
                active_buff_details["is_double_delivery_active"] = True
                log.debug(f"  - Evento 'doubleDelivery' ATIVO HOJE ({today_date_str})")
                break 
    log.debug(f"Bônus total (aditivo): +{total_bonus}. Detalhes Ativos: {list(active_buff_details.keys())}")
    return {'total_bonus': total_bonus, 'details': active_buff_details}

# --- Função Auxiliar Interna _get_period_change_v4 ---
# ... (código existente - sem alterações) ...
def _get_period_change_v4(farm_id, npc_id, data_inicio_str, data_fim_str, primeira_data_farm_str):
    try:
        farm_id_int = int(farm_id); data_final_periodo = data_fim_str
        data_anterior_inicio = (datetime.strptime(data_inicio_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        snapshot_final_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_final_periodo) #
        if snapshot_final_data is None:
            snapshot_ontem = database_utils.get_snapshot_from_db(farm_id_int, npc_id, (datetime.strptime(data_fim_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')) #
            if snapshot_ontem: log.warning(f"Snapshot final ({data_final_periodo}) não encontrado. Usando dia anterior."); snapshot_final_data = snapshot_ontem
            else: erro_msg = f"Snapshot final ({data_final_periodo}) não encontrado."; log.error(f"{erro_msg} para {farm_id_int}/{npc_id}."); return {'erro': erro_msg, 'used_zero_base_fallback': False}
        count_fim = snapshot_final_data.get('deliveryCount', 0); skips_fim = snapshot_final_data.get('skipCount', 0)
        count_base = 0; skips_base = 0; used_zero_base_fallback = False
        snapshot_anterior_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_anterior_inicio) #
        if snapshot_anterior_data is not None:
            count_base = snapshot_anterior_data.get('deliveryCount', 0); skips_base = snapshot_anterior_data.get('skipCount', 0)
            log.debug(f"Snapshot base ({data_anterior_inicio}) encontrado: {count_base}")
        else:
            if data_inicio_str == primeira_data_farm_str:
                log.debug(f"Dia anterior {data_anterior_inicio} não encontrado, {data_inicio_str} é o primeiro dia.")
                snapshot_inicio_data = database_utils.get_snapshot_from_db(farm_id_int, npc_id, data_inicio_str) #
                if snapshot_inicio_data: count_base = snapshot_inicio_data.get('deliveryCount', 0); skips_base = snapshot_inicio_data.get('skipCount', 0); log.debug(f"Usando base do 1º dia ({data_inicio_str}): {count_base}")
                else: log.warning(f"Snapshots anterior ({data_anterior_inicio}) e 1º dia ({data_inicio_str}) não encontrados. Usando base 0."); count_base = 0; skips_base = 0; used_zero_base_fallback = True
            else: erro_msg = f"Snapshot base ({data_anterior_inicio}) não encontrado."; log.warning(f"{erro_msg} para {farm_id_int}/{npc_id}."); return {'erro': erro_msg, 'used_zero_base_fallback': False}
        deliveries_change = max(0, count_fim - count_base); skips_change = max(0, skips_fim - skips_base)
        log.debug(f"Calculo V4 {farm_id_int}/{npc_id}: Fim({data_fim_str})={count_fim} / Base={count_base} -> Change={deliveries_change}")
        return {'deliveries_change': deliveries_change, 'skips_change': skips_change, 'used_zero_base_fallback': used_zero_base_fallback}
    except Exception as e: log.exception(f"Erro mudança V4 {farm_id}/{npc_id}:"); return {'erro': f'Erro cálculo mudança V4 {npc_id}', 'used_zero_base_fallback': False}

# --- FUNÇÃO PRINCIPAL DE ANÁLISE DE DELIVERIES ---
# ... (código existente de calcular_estimativa_token_deliveries - sem alterações) ...
def calcular_estimativa_token_deliveries(farm_id, data_inicio_str, data_fim_str, primeira_data_farm_str, total_bonus_per_delivery):
    if not database_utils.db: return {'erro': 'Cliente DB não inicializado', 'dados_completos': False} #
    try: farm_id_int = int(farm_id) 
    except (ValueError, TypeError): return {'erro': 'Farm ID inválido', 'dados_completos': False}
    npcs_e_tokens_base = config.BASE_DELIVERY_REWARDS #
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
            elif conclusoes_npc_periodo >= 0: # Este log.info foi mantido pois é um resumo importante por NPC dentro da função principal de análise.
                detalhes_npc['conclusoes'] = conclusoes_npc_periodo
                if conclusoes_npc_periodo > 0: effective_reward_per_delivery = base_token_reward + total_bonus_per_delivery; tokens_estimados_npc = conclusoes_npc_periodo * effective_reward_per_delivery; detalhes_npc['tokens_estimados'] = tokens_estimados_npc; total_tokens_estimados_geral += tokens_estimados_npc
                else: detalhes_npc['tokens_estimados'] = 0
                total_conclusoes_geral += conclusoes_npc_periodo
                daily_costs_list = database_utils.get_daily_costs_for_npc(farm_id_int, npc_id, data_inicio_str, data_fim_str); custo_total_npc_periodo = sum(daily_costs_list); detalhes_npc['custo_total_estimado_sfl'] = round(custo_total_npc_periodo, 4); total_custo_estimado_geral_sfl += custo_total_npc_periodo #
                if daily_costs_list:
                    try: detalhes_npc['custo_medio_diario'] = round(statistics.mean(daily_costs_list), 4)
                    except: pass
                    if len(daily_costs_list) < num_days_in_period: detalhes_npc['custo_status'] = 'parcial'
                    else: detalhes_npc['custo_status'] = 'completo'
                else:
                     if conclusoes_npc_periodo == 0 and not is_accumulated_flag: detalhes_npc['custo_status'] = 'nao_aplicavel'
                     elif is_accumulated_flag: detalhes_npc['custo_status'] = 'nao_aplicavel'
                     else: detalhes_npc['custo_status'] = 'sem_registros'
                log.debug(f"  -> Detalhes NPC {farm_id_int}/{npc_id}: {conclusoes_npc_periodo} C (M V4; Base0: {detalhes_npc['is_accumulated']}) -> ~{detalhes_npc['tokens_estimados']} {config.SEASONAL_TOKEN_NAME} (Base {base_token_reward}+Bônus {total_bonus_per_delivery}) -> ~{custo_total_npc_periodo:.2f} SFL Custo Status: {detalhes_npc['custo_status']}")
        else:
            erro_msg = resultado_mudanca.get('erro', "Erro") if resultado_mudanca else "Erro interno"; log.warning(f"Erro cálculo mudança V4 {npc_id}: {erro_msg}");
            if "não encontrado" in erro_msg: detalhes_npc['status'] = 'dados_insuficientes'
            else: detalhes_npc['status'] = 'erro_calculo'; detalhes_npc['mensagem_erro'] = erro_msg
            detalhes_npc['is_accumulated'] = False; dados_completos_geral = False; detalhes_npc['custo_status'] = 'erro_calculo_base'
        detalhes[npc_id] = detalhes_npc
    log.info(f"Análise V4 concluída Farm {farm_id}. Conc (Mudança Real):{total_conclusoes_geral}, TokEst:{total_tokens_estimados_geral}, SFLEst:{total_custo_estimado_geral_sfl:.2f}, Completos:{dados_completos_geral}")
    return { 'total_conclusoes': total_conclusoes_geral, 'total_tokens_estimados': total_tokens_estimados_geral, 'total_custo_estimado_sfl': round(total_custo_estimado_geral_sfl, 4), 'detalhes_por_npc': detalhes, 'dados_completos': dados_completos_geral }

# ---> CALCULATE_BONUS_FOR_ACTIVITY e APPLY_BONUS_TO_REWARD ---
# ... (código existente - sem alterações) ...
def calculate_bonus_for_activity(
    active_player_bonus_names: List[str],
    activity_type: str,
    defined_player_bonuses: Dict[str, Any], 
    activity_rules_config: Dict[str, Any],
) -> int:
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
                total_bonus_value += bonus_definition.get("bonus_value", bonus_definition.get("bonus", 0)) 
            else:
                log.warning(f"Definição não encontrada em SEASONAL_DELIVERY_BUFFS para o bônus '{bonus_name_from_player}' que é aplicável à atividade '{activity_type}'.")
    if total_bonus_value > 0:
        log.debug(f"Bônus total de +{total_bonus_value} calculado para '{activity_type}' (Bônus ativos do jogador: {active_player_bonus_names}, Bônus aplicáveis à atividade: {applicable_bonus_sources_for_activity})")
    return total_bonus_value

def apply_bonus_to_reward(
    reward_object: Dict[str, Any], 
    bonus_value: int,
    activity_rule: Dict[str, Any], 
    seasonal_token_name: str, 
) -> Dict[str, Any]:
    if bonus_value == 0:
        return reward_object 
    reward_type = activity_rule.get("reward_type")
    if reward_type == "numeric_token":
        target_field = activity_rule.get("target_field_name")
        if target_field and target_field in reward_object and isinstance(reward_object[target_field], (int, float)):
            original_value = reward_object[target_field]
            reward_object[target_field] = original_value + bonus_value
            reward_object['applied_bonus_value'] = reward_object.get('applied_bonus_value', 0) + bonus_value
            reward_object['base_reward_value'] = original_value
            reward_object['is_bonus_applied'] = True
            log.debug(f"Bônus de +{bonus_value} aplicado ao campo '{target_field}' da recompensa '{reward_object.get('name', 'N/A')}' (era {original_value}, agora {reward_object[target_field]})")
    elif reward_type == "item_dict":
        item_container_field = activity_rule.get("item_container_field")
        target_item_keys = activity_rule.get("target_item_keys", [])
        if item_container_field and item_container_field in reward_object and isinstance(reward_object.get(item_container_field), dict):
            items_dict = reward_object[item_container_field]
            bonus_applied_this_call = False
            for item_key_to_buff in target_item_keys:
                if item_key_to_buff in items_dict and isinstance(items_dict[item_key_to_buff], (int, float)):
                    original_value = items_dict[item_key_to_buff]
                    items_dict[item_key_to_buff] += bonus_value
                    log.debug(f"Bônus de +{bonus_value} aplicado ao item '{item_key_to_buff}' em '{item_container_field}' da recompensa '{reward_object.get('name', 'N/A')}'. Era {original_value}, agora {items_dict[item_key_to_buff]}")
                    if item_key_to_buff == seasonal_token_name: 
                        reward_object['base_reward_value'] = original_value
                    bonus_applied_this_call = True
            if bonus_applied_this_call:
                reward_object['applied_bonus_value'] = reward_object.get('applied_bonus_value', 0) + bonus_value
                reward_object['is_bonus_applied'] = True
    else:
        log.warning(f"Tipo de recompensa desconhecido ou não suportado: '{reward_type}' nas regras da atividade '{activity_rule.get('description', 'N/A')}'.")
    return reward_object

# --- LÓGICA PARA PROJEÇÕES SAZONAIS ---
# ... (código existente de calcular_custo_minimo_desbloqueio, calcular_custo_total_item, projetar_dias_para_item - sem alterações) ...
def calcular_custo_minimo_desbloqueio(tier_alvo, itens_loja, marked_item_names):
    if not isinstance(itens_loja, dict) or not itens_loja:
        return {'unlock_cost': float('inf'), 'unlock_items_details': []}
    if not isinstance(tier_alvo, int) or tier_alvo <= 1:
        return {'unlock_cost': 0, 'unlock_items_details': []}
    total_unlock_cost_tickets = 0
    final_unlock_items_details_list = [] 
    marked_item_names_set = set(marked_item_names)
    log.debug(f"Calculando custo desbloqueio detalhado para Tier {tier_alvo} com marcados: {marked_item_names}")
    for tier_a_comprar in range(1, tier_alvo):
        log.debug(f" -> Analisando Tier {tier_a_comprar}...")
        preselected_in_tier_names = [
            name for name in marked_item_names_set
            if itens_loja.get(name, {}).get('tier') == tier_a_comprar
        ]
        num_preselected = len(preselected_in_tier_names)
        log.debug(f"    Itens pré-selecionados: {num_preselected} ({preselected_in_tier_names})")
        for name in preselected_in_tier_names:
            data = itens_loja.get(name, {})
            final_unlock_items_details_list.append({
                'name': name,
                'cost': data.get('cost'),
                'currency': data.get('currency'),
                'tier': tier_a_comprar,
                'source': 'marked' 
            })
        needed = max(0, 4 - num_preselected)
        log.debug(f"    Itens adicionais necessários: {needed}")
        cost_of_preselected_tickets = sum(
            itens_loja[name]['cost'] for name in preselected_in_tier_names
            if itens_loja[name].get('currency') == 'ticket' and isinstance(itens_loja[name].get('cost'), (int, float))
        )
        log.debug(f"    Custo (Tickets) dos pré-selecionados: {cost_of_preselected_tickets}")
        cost_of_needed_tickets = 0
        names_of_needed = []
        if needed > 0:
            candidates = []
            for name, data in itens_loja.items():
                if (data.get('tier') == tier_a_comprar and
                    data.get('currency') == 'ticket' and
                    isinstance(data.get('cost'), (int, float)) and data['cost'] > 0 and
                    name not in marked_item_names_set): 
                      candidates.append({'name': name, 'cost': data['cost'], 'currency': 'ticket', 'tier': tier_a_comprar, 'source': 'calculated'})
            log.debug(f"    Candidatos (ticket, não marcados): {len(candidates)}")
            if len(candidates) < needed:
                log.warning(f"Impossível desbloquear Tier {tier_a_comprar + 1}! Faltam itens de TICKET não marcados no Tier {tier_a_comprar}.")
                return {'unlock_cost': float('inf'), 'unlock_items_details': []}
            candidates.sort(key=lambda item: item['cost'])
            cheapest_needed_details = candidates[:needed] 
            cost_of_needed_tickets = sum(item['cost'] for item in cheapest_needed_details)
            names_of_needed = [item['name'] for item in cheapest_needed_details] 
            log.debug(f"    Itens mais baratos escolhidos para completar ({needed}): {names_of_needed} (Custo: {cost_of_needed_tickets})")
            final_unlock_items_details_list.extend(cheapest_needed_details)
        cost_tier_atual_tickets = cost_of_preselected_tickets + cost_of_needed_tickets
        total_unlock_cost_tickets += cost_tier_atual_tickets
        log.debug(f"    Custo total de TICKETS adicionado para Tier {tier_a_comprar}: {cost_tier_atual_tickets}")
    log.debug(f"Custo total de DESBLOQUEIO (Tickets) para Tier {tier_alvo}: {total_unlock_cost_tickets}.")
    final_unlock_items_details_list.sort(key=lambda x: (x.get('tier', 0), x.get('name', '')))
    return {'unlock_cost': int(round(total_unlock_cost_tickets)), 'unlock_items_details': final_unlock_items_details_list}

def calcular_custo_total_item(nome_item_alvo, itens_loja, marked_item_names):
    if not isinstance(itens_loja, dict) or not itens_loja: 
        return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    item_data = itens_loja.get(nome_item_alvo)
    if not item_data: 
        return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    item_cost = item_data.get('cost')
    item_currency = item_data.get('currency')
    item_tier = item_data.get('tier')
    base_item_cost_tickets = 0 
    if item_currency != 'ticket': 
         log.warning(f"Item alvo '{nome_item_alvo}' não é de ticket.")
         return {'total_cost': float('inf'), 'item_cost': item_cost, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    if not isinstance(item_cost, (int, float)) or item_cost <= 0: 
         return {'total_cost': float('inf'), 'item_cost': None, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    else:
        base_item_cost_tickets = item_cost 
    if not isinstance(item_tier, int) or item_tier < 1: 
         return {'total_cost': float('inf'), 'item_cost': base_item_cost_tickets, 'unlock_cost': float('inf'), 'unlock_items_details': []}
    log.debug(f"Calculando custo total detalhado para '{nome_item_alvo}' com marcados: {marked_item_names}")
    unlock_info = calcular_custo_minimo_desbloqueio(item_tier, itens_loja, marked_item_names)
    custo_desbloqueio_tickets = unlock_info['unlock_cost']
    unlock_items_details_list = unlock_info['unlock_items_details']
    log.debug(f" -> Custo desbloqueio (Tickets): {custo_desbloqueio_tickets}. Itens caminho: {len(unlock_items_details_list)} itens.")
    if custo_desbloqueio_tickets == float('inf'):
        log.warning(f"Não é possível calcular custo total para '{nome_item_alvo}', tier não desbloqueável.")
        return {'total_cost': float('inf'), 'item_cost': base_item_cost_tickets, 'unlock_cost': float('inf'), 'unlock_items_details': unlock_items_details_list}
    custo_total_tickets = custo_desbloqueio_tickets + base_item_cost_tickets
    log.debug(f"Custo total estimado (Tickets) para '{nome_item_alvo}': {custo_total_tickets} (Item: {base_item_cost_tickets}, Desbloq: {custo_desbloqueio_tickets})")
    return {
        'total_cost': int(round(custo_total_tickets)),
        'item_cost': int(round(base_item_cost_tickets)),
        'unlock_cost': int(round(custo_desbloqueio_tickets)),
        'unlock_items_details': unlock_items_details_list 
    }

def projetar_dias_para_item(custo_total, taxa_media_diaria):
    if not isinstance(taxa_media_diaria, (int, float)) or taxa_media_diaria <= 0:
        log.warning(f"projetar_dias_para_item: Taxa média diária inválida ou zero ({taxa_media_diaria}).")
        return float('inf')
    if not isinstance(custo_total, (int, float)) or custo_total == float('inf') or custo_total < 0:
        log.warning(f"projetar_dias_para_item: Custo total inválido ({custo_total}).")
        return float('inf')
    if custo_total == 0:
        return 0
    dias_necessarios = custo_total / taxa_media_diaria
    dias_arredondados = math.ceil(dias_necessarios) 
    log.debug(f"Projeção de dias: {dias_arredondados} (Custo: {custo_total} / Taxa: {taxa_media_diaria:.2f}/dia)")
    return dias_arredondados 

# ---> NOVA FUNÇÃO: _get_chores_completions_in_period <---
def _get_chores_completions_in_period(farm_id, data_inicio_str, data_fim_str, primeira_data_farm_str, current_db_utils, logger, seasonal_token_name):
    """
    Calcula o número de chores concluídos e os tokens base ganhos em um período.
    Compara snapshots diários do 'chores_board_state'.
    """
    total_chores_completed_period = 0
    total_base_tokens_from_chores_period = 0
    
    try:
        date_format = '%Y-%m-%d'
        current_date_obj = datetime.strptime(data_inicio_str, date_format) # Renomeado para evitar conflito
        end_date_obj = datetime.strptime(data_fim_str, date_format) # Renomeado para evitar conflito
        
        previous_day_chores_state = {} # Sempre inicializa como dict
        if data_inicio_str != primeira_data_farm_str:
            date_anterior_inicio_obj = current_date_obj - timedelta(days=1)
            date_anterior_inicio_str = date_anterior_inicio_obj.strftime(date_format)
            # A função get_snapshot_chore_board_state já retorna None ou dict
            retrieved_previous_state = current_db_utils.get_snapshot_chore_board_state(farm_id, date_anterior_inicio_str) #
            if retrieved_previous_state is not None:
                previous_day_chores_state = retrieved_previous_state
            else:
                logger.debug(f"Snapshot do dia anterior ({date_anterior_inicio_str}) para chores não encontrado para Farm {farm_id}. Assumindo sem chores completos anteriormente para o início do período.")
        else:
            logger.debug(f"Análise de chores começando no primeiro dia de snapshot ({data_inicio_str}) para Farm {farm_id}. Todos os chores completados neste dia serão contados.")

        while current_date_obj <= end_date_obj:
            current_date_str = current_date_obj.strftime(date_format)
            logger.debug(f"Analisando chores para {farm_id} no dia: {current_date_str}")
            
            current_day_chores_state = current_db_utils.get_snapshot_chore_board_state(farm_id, current_date_str) #

            if current_day_chores_state is None: # Se não há snapshot para o dia atual
                logger.warning(f"Snapshot de chores para {current_date_str} não encontrado para Farm {farm_id}. Pulando dia.")
                # Mantém o previous_day_chores_state do dia anterior válido ou {}
            else: # Snapshot do dia atual existe
                for npc_giver, current_chore_info in current_day_chores_state.items():
                    current_completed_at = current_chore_info.get('completedAt')
                    
                    if current_completed_at is not None: 
                        previous_chore_info = previous_day_chores_state.get(npc_giver, {}) # Garante que é um dict
                        previous_completed_at = previous_chore_info.get('completedAt')
                        
                        # Mudança na lógica de detecção: conta se está completo hoje E (não existia no dia anterior OU estava incompleto no dia anterior)
                        # E o timestamp de conclusão é efetivamente do dia atual (ou seja, maior que o do dia anterior, se ambos existirem)
                        # Para simplificar, vamos contar se:
                        # 1. Está completo hoje (current_completed_at is not None)
                        # 2. E (NPC não estava no estado anterior OU no estado anterior completedAt era None)
                        # Esta lógica é para contar uma transição de "não completo" para "completo".
                        if npc_giver not in previous_day_chores_state or previous_completed_at is None:
                            total_chores_completed_period += 1
                            base_tokens = current_chore_info.get('seasonal_token_reward', 0)
                            total_base_tokens_from_chores_period += base_tokens
                            logger.debug(f"Chore '{current_chore_info.get('description')}' por '{npc_giver}' marcado como concluído em {current_date_str} (não completo anteriormente). Tokens base: {base_tokens}")
                
                previous_day_chores_state = current_day_chores_state # Avança o estado anterior para o próximo loop

            current_date_obj += timedelta(days=1) # Avança para o próximo dia
            
    except Exception as e:
        logger.exception(f"Erro em _get_chores_completions_in_period para Farm {farm_id}: {e}")
        return {'erro': str(e), 'total_chores_completed': 0, 'total_base_tokens': 0}
        
    return {
        'total_chores_completed': total_chores_completed_period,
        'total_base_tokens': total_base_tokens_from_chores_period
    }
# ---> FIM _get_chores_completions_in_period <---


# ---> NOVA FUNÇÃO: calcular_estimativa_token_chores <---
def calcular_estimativa_token_chores(farm_id, data_inicio_str, data_fim_str, primeira_data_farm_str, active_player_bonus_names, current_db_utils, current_analysis_module, current_config_module, logger):
    resultado_base = {
        'status': 'ok',
        'total_conclusoes': 0,
        'total_tokens_estimados': 0, 
        'total_tokens_base': 0,    
        'detalhes_por_dia_ou_chore': [], 
        'dados_completos': True, 
        'periodo_analisado': f"{data_inicio_str} a {data_fim_str}" 
    }

    completions_info = _get_chores_completions_in_period(
        farm_id, data_inicio_str, data_fim_str, primeira_data_farm_str, 
        current_db_utils, logger, current_config_module.SEASONAL_TOKEN_NAME #
    )

    if 'erro' in completions_info:
        resultado_base['status'] = 'erro_calculo_base'
        resultado_base['mensagem_erro'] = completions_info['erro']
        resultado_base['dados_completos'] = False
        return resultado_base

    total_chores_concluidos_que_deram_tokens = completions_info.get('total_chores_completed', 0) # Assumindo que esta função conta os que deram token
    total_base_tokens_chores = completions_info.get('total_base_tokens', 0)

    resultado_base['total_conclusoes'] = total_chores_concluidos_que_deram_tokens # Renomeado para clareza
    resultado_base['total_tokens_base'] = total_base_tokens_chores

    bonus_adicional_por_chore_activity = current_analysis_module.calculate_bonus_for_activity(
        active_player_bonus_names,
        "chores", 
        current_config_module.SEASONAL_DELIVERY_BUFFS, #
        current_config_module.ACTIVITY_BONUS_RULES   #
    )
    
    # O bônus é por chore que deu token.
    total_bonus_aplicado_chores = total_chores_concluidos_que_deram_tokens * bonus_adicional_por_chore_activity
    tokens_finais_estimados = total_base_tokens_chores + total_bonus_aplicado_chores
    
    resultado_base['total_tokens_estimados'] = tokens_finais_estimados
    
    logger.info(f"Análise de Chores para Farm {farm_id} ({data_inicio_str}-{data_fim_str}): "
                f"{total_chores_concluidos_que_deram_tokens} chores (com tokens) concluídos, "
                f"{total_base_tokens_chores} tokens base, "
                f"+{total_bonus_aplicado_chores} tokens de bônus (bônus por chore que deu token: {bonus_adicional_por_chore_activity}), "
                f"Total Estimado: {tokens_finais_estimados} tokens.")

    return resultado_base
# ---> FIM calcular_estimativa_token_chores <---

# --- Bloco de Teste ---
if __name__ == "__main__":
    # ... (bloco de teste existente) ...
    print("Executando analysis.py como script principal (V4 com bônus detalhado)...")
    pass