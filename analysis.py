# analysis.py
import logging
import math
import statistics
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import config
import database_utils

log = logging.getLogger(__name__)

# ---> FUNÇÃO PARA CALCULAR BÔNUS (Retorna Detalhes) ---
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
# ---> FIM FUNÇÃO PARA CALCULAR BÔNUS (Retorna Detalhes) ---

# ---> Função Auxiliar Interna _get_period_change_v4 ---
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

# ---> FUNÇÃO PRINCIPAL DE ANÁLISE DE DELIVERIES ---
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
# ---> FIM FUNÇÃO PRINCIPAL DE ANÁLISE DE DELIVERIES ---

# ---> CALCULATE_BONUS_FOR_ACTIVITY e APPLY_BONUS_TO_REWARD ---
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
def calcular_custo_minimo_desbloqueio(tier_alvo, itens_loja, itens_ja_possuidos_nomes):
    """
    Calcula o custo mínimo em TICKETS SAZONAIS para desbloquear um tier_alvo.
    Considera que itens_ja_possuidos_nomes (de qualquer moeda) no tier anterior
    já preenchem slots de pré-requisito.
    Retorna um dicionário com 'unlock_cost' (custo em tickets) e
    'unlock_items_details' (lista dos itens de TICKET que compõem esse custo).
    """
    if not isinstance(itens_loja, dict) or not itens_loja:
        log.warning("calcular_custo_minimo_desbloqueio: itens_loja está vazio ou inválido.")
        return {'unlock_cost': float('inf'), 'unlock_items_details': []}
    if not isinstance(tier_alvo, int) or tier_alvo <= 1:
        return {'unlock_cost': 0, 'unlock_items_details': []}

    total_unlock_cost_tickets_acumulado = 0
    final_unlock_items_details_list_for_cost = []
    
    set_itens_ja_possuidos = set(itens_ja_possuidos_nomes) if itens_ja_possuidos_nomes else set()

    log.debug(f"DESBLOQUEIO V3.1: Iniciando para Tier Alvo {tier_alvo}. Itens já possuídos: {list(set_itens_ja_possuidos)}")

    for tier_necessario_para_desbloqueio in range(1, tier_alvo):
        custo_adicionado_neste_tier = 0
        itens_de_ticket_escolhidos_para_este_tier = []

        itens_possuidos_neste_tier_necessario = [
            nome_item for nome_item in set_itens_ja_possuidos
            if itens_loja.get(nome_item, {}).get('tier') == tier_necessario_para_desbloqueio
        ]
        num_slots_ja_preenchidos = len(itens_possuidos_neste_tier_necessario)
        
        log.debug(f"  DESBLOQUEIO V3.1: Analisando pré-requisitos do Tier {tier_necessario_para_desbloqueio} (para desbloquear T{tier_necessario_para_desbloqueio + 1}).")
        log.debug(f"    -> Slots já preenchidos no Tier {tier_necessario_para_desbloqueio}: {num_slots_ja_preenchidos} com {itens_possuidos_neste_tier_necessario}")

        itens_adicionais_necessarios = max(0, 4 - num_slots_ja_preenchidos)
        log.debug(f"    -> Itens adicionais necessários para Tier {tier_necessario_para_desbloqueio}: {itens_adicionais_necessarios}")

        if itens_adicionais_necessarios > 0:
            candidatos_para_compra_ticket = []
            for nome_item_loja, dados_item_loja in itens_loja.items():
                if (dados_item_loja.get('tier') == tier_necessario_para_desbloqueio and
                    dados_item_loja.get('currency') == 'ticket' and
                    isinstance(dados_item_loja.get('cost'), (int, float)) and dados_item_loja['cost'] >= 0 and
                    nome_item_loja not in set_itens_ja_possuidos):
                      candidatos_para_compra_ticket.append({
                          'name': nome_item_loja,
                          'cost': dados_item_loja['cost'],
                          'currency': 'ticket',
                          'tier': tier_necessario_para_desbloqueio,
                          'source': 'calculated_for_unlock' 
                      })
            
            log.debug(f"    -> Candidatos (TICKET, não possuídos) para Tier {tier_necessario_para_desbloqueio}: {len(candidatos_para_compra_ticket)} itens: {[c['name'] for c in candidatos_para_compra_ticket]}")

            if len(candidatos_para_compra_ticket) < itens_adicionais_necessarios:
                log.warning(f"DESBLOQUEIO V3.1: Impossível desbloquear Tier {tier_necessario_para_desbloqueio + 1}! Faltam itens de TICKET não possuídos no Tier {tier_necessario_para_desbloqueio}. "
                            f"Encontrados: {len(candidatos_para_compra_ticket)}, Necessários: {itens_adicionais_necessarios}.")
                final_unlock_items_details_list_for_cost.sort(key=lambda x: (x.get('tier', 0), x.get('name', '')))
                return {'unlock_cost': float('inf'), 'unlock_items_details': final_unlock_items_details_list_for_cost}

            candidatos_para_compra_ticket.sort(key=lambda item: item['cost'])
            
            itens_de_ticket_escolhidos_para_este_tier = candidatos_para_compra_ticket[:itens_adicionais_necessarios]
            custo_adicionado_neste_tier = sum(item['cost'] for item in itens_de_ticket_escolhidos_para_este_tier)
            
            log.debug(f"    -> Itens de TICKET escolhidos para custo de desbloqueio do Tier {tier_necessario_para_desbloqueio} ({itens_adicionais_necessarios}): {[item['name'] for item in itens_de_ticket_escolhidos_para_este_tier]} (Custo: {custo_adicionado_neste_tier})")
            
            final_unlock_items_details_list_for_cost.extend(itens_de_ticket_escolhidos_para_este_tier)
            total_unlock_cost_tickets_acumulado += custo_adicionado_neste_tier
        
        log.debug(f"  DESBLOQUEIO V3.1: Tier {tier_necessario_para_desbloqueio} - Custo em tickets adicionado nesta etapa: {custo_adicionado_neste_tier}")

        # Adiciona os itens (de ticket) escolhidos para este tier ao conjunto de "já possuídos"
        # para a próxima iteração do loop (para o próximo tier_necessario_para_desbloqueio)
        for item_comprado_para_desbloqueio in itens_de_ticket_escolhidos_para_este_tier:
             set_itens_ja_possuidos.add(item_comprado_para_desbloqueio['name'])

    log.debug(f"DESBLOQUEIO V3.1: Custo total de DESBLOQUEIO em Tickets para alcançar Tier {tier_alvo}: {total_unlock_cost_tickets_acumulado}.")
    final_unlock_items_details_list_for_cost.sort(key=lambda x: (x.get('tier', 0), x.get('name', '')))
    
    return {
        'unlock_cost': int(round(total_unlock_cost_tickets_acumulado)),
        'unlock_items_details': final_unlock_items_details_list_for_cost
    }

# --->  FUNÇÃO: Custo de Item (Loja,Calendario) <---
def calcular_custo_total_item(nome_item_alvo: str, 
                              itens_loja: Dict[str, Any], 
                              marked_item_names: List[str]) -> Dict[str, Any]:
    if not isinstance(itens_loja, dict) or not itens_loja:
        return {'total_cost_tickets': float('inf'), 'item_cost_original': None, 'item_currency_original': None, 'unlock_cost_tickets': float('inf'), 'unlock_items_details': [], 'is_tier_unlockable': False}

    item_data = itens_loja.get(nome_item_alvo)
    if not item_data:
        return {'total_cost_tickets': float('inf'), 'item_cost_original': None, 'item_currency_original': None, 'unlock_cost_tickets': float('inf'), 'unlock_items_details': [], 'is_tier_unlockable': False}

    item_cost_original = item_data.get('cost')
    item_currency_original = item_data.get('currency')
    item_tier = item_data.get('tier')

    if not all(isinstance(val, (int, float)) or val is not None for val in [item_cost_original]) or \
       not isinstance(item_currency_original, str) or \
       not (isinstance(item_tier, int) and item_tier >= 1):
        log.warning(f"Dados inválidos para o item '{nome_item_alvo}': Custo={item_cost_original}, Moeda={item_currency_original}, Tier={item_tier}")
        return {'total_cost_tickets': float('inf'), 'item_cost_original': item_cost_original, 'item_currency_original': item_currency_original, 'unlock_cost_tickets': float('inf'), 'unlock_items_details': [], 'is_tier_unlockable': False}

    # Calcula o custo de desbloqueio EM TICKETS para o tier do item_alvo
    unlock_info = calcular_custo_minimo_desbloqueio(item_tier, itens_loja, marked_item_names)
    custo_desbloqueio_tickets_para_tier_alvo = unlock_info['unlock_cost']
    unlock_items_details_list_para_tier_alvo = unlock_info['unlock_items_details']

    is_tier_unlockable_flag = custo_desbloqueio_tickets_para_tier_alvo != float('inf')

    log.debug(f"Análise de custo para '{nome_item_alvo}' (Moeda: {item_currency_original}, Tier: {item_tier}):")
    log.debug(f"  Custo original do item: {item_cost_original} {item_currency_original}")
    log.debug(f"  Custo de desbloqueio (Tickets) para alcançar Tier {item_tier}: {custo_desbloqueio_tickets_para_tier_alvo if is_tier_unlockable_flag else 'Impossível'}")
    if is_tier_unlockable_flag and unlock_items_details_list_para_tier_alvo:
        log.debug(f"  Itens de Ticket para desbloqueio: {[item['name'] for item in unlock_items_details_list_para_tier_alvo]}")

    # O 'total_cost_tickets' representa o custo total em tickets que seria debitado
    # se o usuário confirmasse a aquisição (incluindo o item alvo se for de ticket + desbloqueio).
    total_cost_tickets_final = float('inf')

    if not is_tier_unlockable_flag:
        # Se o tier não é desbloqueável, o custo total em tickets é infinito.
        total_cost_tickets_final = float('inf')
    elif item_currency_original == 'ticket':
        # Se o item é de ticket e o tier é desbloqueável
        item_base_cost_tickets = item_cost_original if isinstance(item_cost_original, (int, float)) else 0
        total_cost_tickets_final = item_base_cost_tickets + custo_desbloqueio_tickets_para_tier_alvo
    else:
        # Se o item não é de ticket, mas o tier é desbloqueável,
        # o 'total_cost_tickets' é apenas o custo de desbloqueio do tier.
        total_cost_tickets_final = custo_desbloqueio_tickets_para_tier_alvo
        
    return {
        'total_cost_tickets': total_cost_tickets_final, # Custo total EM TICKETS a ser debitado (item de ticket + desbloqueio OU só desbloqueio)
        'item_cost_original': item_cost_original,       # Custo do item na sua moeda original
        'item_currency_original': item_currency_original, # Moeda original do item
        'unlock_cost_tickets': custo_desbloqueio_tickets_para_tier_alvo, # Custo apenas de desbloqueio do tier, em tickets
        'unlock_items_details': unlock_items_details_list_para_tier_alvo, # Itens de TICKET para o desbloqueio
        'is_tier_unlockable': is_tier_unlockable_flag # Flag crucial
    }
# --->  FIM FUNÇÃO: Custo de Item (Loja,Calendario) <---


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

# ---> CALENADRIO SAZONAL <---
DIAS_SEMANA_PT_COMPLETO = {
    0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta",
    4: "Sexta", 5: "Sábado", 6: "Domingo"
}

def _get_config_dates():
    """Helper para buscar e parsear datas de configuração da temporada."""
    data_inicio_str = getattr(config, 'SEASON_START_DATE', None)
    data_fim_str = getattr(config, 'SEASON_END_DATE', None)
    date_activities_start_str = getattr(config, 'DATE_ACTIVITIES_START_YIELDING_TOKENS', data_inicio_str)

    if not data_inicio_str or not data_fim_str:
        log.error("Datas de início ou fim da temporada não configuradas.")
        return None, None, None, "Configuração de data da temporada ausente."

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
        date_activities_start = datetime.strptime(date_activities_start_str, '%Y-%m-%d')
        return data_inicio, data_fim, date_activities_start, None
    except ValueError as e:
        log.error(f"Formato de data inválido nas configurações da temporada: {e}")
        return None, None, None, "Configuração de data da temporada inválida."

def _get_double_delivery_dates(data_inicio_temporada, data_fim_temporada):
    """Helper para calcular as datas de Double Delivery na temporada."""
    dates_set = set()
    dd_config_date_str = getattr(config, 'DOUBLE_DELIVERY_DATE', None)
    dd_interval = getattr(config, 'DOUBLE_DELIVERY_INTERVAL_DAYS', 0)

    if dd_config_date_str and dd_interval > 0:
        try:
            data_base_dd = datetime.strptime(dd_config_date_str, '%Y-%m-%d')
            current_dd_check = data_base_dd
            while current_dd_check <= data_fim_temporada:
                if current_dd_check >= data_inicio_temporada:
                    dates_set.add(current_dd_check.date())
                current_dd_check += timedelta(days=dd_interval)
        except ValueError as e:
            log.error(f"Formato de data inválido em config.DOUBLE_DELIVERY_DATE: {e}")
    return dates_set

# ---> GERAR CALENADARIO SAZONAL
def gerar_dados_calendario_sazonal(vip_ativo_param: bool = False, compras_simuladas_usuario: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Gera os dados dia a dia para o calendário sazonal, simulando ganhos de tickets,
    bônus e compras de itens.
    """
    log.info(f"Gerando calendário sazonal: VIP={vip_ativo_param}, Compras Iniciais: {len(compras_simuladas_usuario) if compras_simuladas_usuario else 0}")

    if compras_simuladas_usuario is None:
        compras_simuladas_usuario = []
    
    # Ordena as compras por data para processamento cronológico
    compras_simuladas_usuario.sort(key=lambda x: datetime.strptime(x["data_compra"], '%Y-%m-%d'))

    data_inicio_temporada, data_fim_temporada, date_activities_start, error_msg = _get_config_dates()
    if error_msg:
        return [{"erro": error_msg}]

    # --- Constantes da Configuração para Cálculos Diários/Semanais ---
    dia_reset_semanal = getattr(config, 'WEEKLY_RESET_DAY', 0) # Segunda-feira
    base_total_entregas_dia = getattr(config, 'DAILY_DELIVERY_TICKETS_BASE', 0)
    num_npcs_entrega_tickets = len(getattr(config, 'BASE_DELIVERY_REWARDS', {})) #
    base_semanal_bounties = getattr(config, 'MAX_WEEKLY_BOUNTY_TICKETS_BASE', 0)
    base_semanal_chores = getattr(config, 'MAX_WEEKLY_CHORE_TICKETS_BASE', 0)
    tickets_bau_diario = getattr(config, 'DAILY_CHEST_TICKETS', 1)
    num_chores_semanais_componentes = getattr(config, 'NUM_CHORES_COMPONENTES_SEMANAIS', 0)
    num_bounties_semanais_componentes = getattr(config, 'NUM_BOUNTIES_COMPONENTES_SEMANAIS', 0)
    double_delivery_dates_in_season = _get_double_delivery_dates(data_inicio_temporada, data_fim_temporada)

    # --- Estado da Simulação ---
    dados_calendario: List[Dict[str, Any]] = []
    bonus_ativos_simulacao_nomes: set[str] = set()
    if vip_ativo_param and "vip" in config.SEASONAL_DELIVERY_BUFFS: #
        bonus_ativos_simulacao_nomes.add("vip")

    tickets_acumulados_para_compra_liquido = 0
    tickets_acumulados_brutos_temporada = 0
    idx_proxima_compra_usuario = 0
    dia_atual_loop = data_inicio_temporada

    while dia_atual_loop <= data_fim_temporada:
        data_atual_str = dia_atual_loop.strftime('%Y-%m-%d')
        dia_da_semana_num = dia_atual_loop.weekday()
        nome_dia_semana_pt = DIAS_SEMANA_PT_COMPLETO.get(dia_da_semana_num, dia_atual_loop.strftime('%a'))
        
        tickets_do_dia: Dict[str, Any] = {
            "data": data_atual_str,
            "data_display": f"{dia_atual_loop.strftime('%d/%m/%y')} ({nome_dia_semana_pt})",
            "tickets_entregas_base_display": 0, "tickets_bounties_base_display": 0,
            "tickets_chores_base_display": 0, "tickets_bau": 0,
            "bonus_diario_detalhado_display": [], "total_bonus_diario_display": 0,
            "total_tickets_dia": 0, "tickets_acumulados_brutos": 0,
            "tickets_liquidos_compra": 0,
            "eventos_do_dia_list": [],
            "compras_do_dia_list": [],
            "eventos_compras_display_final": None
        }
        ganhos_atividades_ativos = dia_atual_loop >= date_activities_start

        # 1. Processar compras simuladas agendadas para ESTE dia
        # Ativa bônus e deduz custos de tickets
        while idx_proxima_compra_usuario < len(compras_simuladas_usuario) and \
              datetime.strptime(compras_simuladas_usuario[idx_proxima_compra_usuario]["data_compra"], '%Y-%m-%d').date() == dia_atual_loop.date():
            
            compra_atual = compras_simuladas_usuario[idx_proxima_compra_usuario]
            log.info(f"Processando compra simulada de '{compra_atual['name']}' para o dia {data_atual_str}")
            
            if compra_atual.get("buff_source_key"):
                bonus_ativos_simulacao_nomes.add(compra_atual["buff_source_key"])
                log.debug(f"  -> Buff '{compra_atual['buff_source_key']}' ativado para simulação.")

            # Determina o custo a ser mostrado no badge
            custo_para_badge = compra_atual.get('original_cost_for_display', compra_atual.get('custo_real_gasto', 'N/A'))

            tickets_do_dia["compras_do_dia_list"].append(
                f"Adquiriu: {compra_atual['name']} ({custo_para_badge}T)" # Usa custo_para_badge
            )

            item_comprado_data_loja_loop = config.SEASONAL_SHOP_ITEMS.get(compra_atual["name"])
            # A dedução do custo_real_gasto (que já está correto na lista 'comprasSimuladasPeloUsuarioJS')
            # deve ser feita aqui.
            if item_comprado_data_loja_loop: # Verifica se o item existe na loja para pegar a moeda
                # O custo_real_gasto no objeto compra_atual já foi definido corretamente pelo JS
                # (0 para desbloqueios de itens de ticket, ou o custo real para outros casos)
                custo_a_debitar_nesta_compra = compra_atual.get('custo_real_gasto', 0)

                # Só debita se o custo_a_debitar_nesta_compra for referente a tickets.
                # No entanto, o objeto 'compra_atual' não tem a 'currency' do item.
                # Precisamos pegar do item_shop_data_config (ou similar) ou assumir que
                # 'custo_real_gasto' já é sempre em tickets (o que é a intenção).
                # Se 'custo_real_gasto' pode ser de outra moeda, essa lógica de débito precisa de ajuste.
                # Assumindo que 'custo_real_gasto' no objeto 'compra_atual' é sempre o valor em tickets a ser debitado:
                if isinstance(custo_a_debitar_nesta_compra, (int, float)) and custo_a_debitar_nesta_compra > 0 :
                    tickets_acumulados_para_compra_liquido -= custo_a_debitar_nesta_compra
                    log.debug(f"  -> Custo de {custo_a_debitar_nesta_compra}T deduzido para '{compra_atual['name']}'. Saldo líquido agora: {tickets_acumulados_para_compra_liquido}")
                elif isinstance(custo_a_debitar_nesta_compra, (int, float)) and custo_a_debitar_nesta_compra == 0 and item_comprado_data_loja_loop.get("currency") == "ticket":
                    log.debug(f"  -> Custo de 0T (já incluso anteriormente ou item de desbloqueio) para '{compra_atual['name']}'. Saldo líquido: {tickets_acumulados_para_compra_liquido}")

            idx_proxima_compra_usuario += 1

        # 2. Calcular bônus detalhado com base nos bônus ATIVOS AGORA
        lista_bonus_detalhado_dia_temp = []
        for nome_buff_ativo in bonus_ativos_simulacao_nomes:
            definicao_buff = config.SEASONAL_DELIVERY_BUFFS.get(nome_buff_ativo) #
            if not definicao_buff: continue
            
            valor_bonus_individual = definicao_buff.get("bonus_value", 0)
            if valor_bonus_individual == 0: continue
            nome_display_buff = nome_buff_ativo.replace("_", " ").title()

            if ganhos_atividades_ativos:
                bonus_entregas_calc = num_npcs_entrega_tickets * valor_bonus_individual
                if bonus_entregas_calc > 0:
                    lista_bonus_detalhado_dia_temp.append({"fonte": f"{nome_display_buff} (Entregas)", "valor": bonus_entregas_calc})
            
            if dia_da_semana_num == dia_reset_semanal and ganhos_atividades_ativos:
                regras_chores = config.ACTIVITY_BONUS_RULES.get("chores", {}) #
                if nome_buff_ativo in regras_chores.get("applicable_bonuses", []):
                    bonus_chores_calc = num_chores_semanais_componentes * valor_bonus_individual
                    if bonus_chores_calc > 0:
                         lista_bonus_detalhado_dia_temp.append({"fonte": f"{nome_display_buff} (Chores)", "valor": bonus_chores_calc})

                regras_bounties = config.ACTIVITY_BONUS_RULES.get("generic_mega_board_bounties", {}) #
                if nome_buff_ativo in regras_bounties.get("applicable_bonuses", []):
                    bonus_bounties_calc = num_bounties_semanais_componentes * valor_bonus_individual
                    if bonus_bounties_calc > 0:
                        lista_bonus_detalhado_dia_temp.append({"fonte": f"{nome_display_buff} (Bounties)", "valor": bonus_bounties_calc})
        
        is_double_delivery_today = ganhos_atividades_ativos and (dia_atual_loop.date() in double_delivery_dates_in_season)
        if is_double_delivery_today:
            tickets_do_dia["eventos_do_dia_list"].append("Double Delivery!")
            for item_bonus_detalhe in lista_bonus_detalhado_dia_temp:
                if "Entregas" in item_bonus_detalhe["fonte"]: 
                    item_bonus_detalhe["valor"] *= 2 # Dobra o bônus específico de entregas
        
        tickets_do_dia["bonus_diario_detalhado_display"] = lista_bonus_detalhado_dia_temp
        tickets_do_dia["total_bonus_diario_display"] = sum(b['valor'] for b in lista_bonus_detalhado_dia_temp)

        # 3. Calcular ganhos base do dia e adicionar eventos
        tickets_do_dia["tickets_bau"] = tickets_bau_diario
        current_base_entregas_hoje = 0
        current_base_bounties_hoje = 0
        current_base_chores_hoje = 0

        if ganhos_atividades_ativos:
            # Ganhos de entrega são diários, dobrados se for dia de evento
            base_entregas_este_dia = base_total_entregas_dia * 2 if is_double_delivery_today else base_total_entregas_dia
            current_base_entregas_hoje = base_entregas_este_dia
            
            if dia_da_semana_num == dia_reset_semanal:
                current_base_bounties_hoje = base_semanal_bounties
                current_base_chores_hoje = base_semanal_chores
                tickets_do_dia["eventos_do_dia_list"].append("Reset Semanal")
        else:
            tickets_do_dia["eventos_do_dia_list"].append("Pré-atividades")
        
        tickets_do_dia["tickets_entregas_base_display"] = current_base_entregas_hoje
        tickets_do_dia["tickets_bounties_base_display"] = current_base_bounties_hoje
        tickets_do_dia["tickets_chores_base_display"] = current_base_chores_hoje

        # 4. Calcular total ganho no dia e atualizar acumulados
        total_ganho_bruto_dia = (
            current_base_entregas_hoje +
            current_base_bounties_hoje +
            current_base_chores_hoje +
            tickets_do_dia["total_bonus_diario_display"] + # Bônus já considera o double delivery para entregas
            tickets_bau_diario
        )
        tickets_do_dia["total_tickets_dia"] = total_ganho_bruto_dia
        
        tickets_acumulados_brutos_temporada += total_ganho_bruto_dia
        tickets_acumulados_para_compra_liquido += total_ganho_bruto_dia
        
        # Atribui saldos finais do dia
        tickets_do_dia["tickets_acumulados_brutos"] = tickets_acumulados_brutos_temporada
        tickets_do_dia["tickets_liquidos_compra"] = tickets_acumulados_para_compra_liquido
        
        # 5. Formatar a lista final para exibição (eventos + compras)
        eventos_compras_finais_para_js = []
        if tickets_do_dia["eventos_do_dia_list"]:
            eventos_compras_finais_para_js.extend(sorted(list(set(tickets_do_dia["eventos_do_dia_list"]))))
        if tickets_do_dia["compras_do_dia_list"]:
            eventos_compras_finais_para_js.extend(tickets_do_dia["compras_do_dia_list"])
        
        if "Pré-atividades" in eventos_compras_finais_para_js and len(eventos_compras_finais_para_js) > 1:
            eventos_compras_finais_para_js = [e for e in eventos_compras_finais_para_js if e != "Pré-atividades"]
        
        tickets_do_dia["eventos_compras_display_final"] = eventos_compras_finais_para_js if eventos_compras_finais_para_js else None
        
        dados_calendario.append(tickets_do_dia)
        dia_atual_loop += timedelta(days=1)
        
    log.info(f"Geração do calendário sazonal concluída. Total de dias processados: {len(dados_calendario)}")
    return dados_calendario
# ---> FIM CALENADRIO SAZONAL <---

# --- Bloco de Teste ---
if __name__ == "__main__":
    print("Executando analysis.py como script principal (V4 com bônus detalhado)...")
    pass