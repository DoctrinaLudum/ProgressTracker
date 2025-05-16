# ProgressTracker/season_calendar_simulator.py
import datetime
import logging
import math 
import config 

log = logging.getLogger(__name__)

# --- (Seus PARÂMETROS DE SIMULAÇÃO no topo do arquivo - Mantidos) ---
TIER_UNLOCK_RULES = 4
SIM_DAILY_CHEST_REWARD_TOKENS = 1
SIM_DAILY_NPC_DELIVERIES_BASE_TOKENS = 35 
SIM_DAILY_NPC_DELIVERIES_COUNT = 11     
SIM_WEEKLY_CHORES_BASE_TOKENS = 42
SIM_WEEKLY_CHORES_COUNT = 21            
SIM_WEEKLY_MEGABOARD_BOUNTIES_BASE_TOKENS = 189 
SIM_WEEKLY_MEGABOARD_BOUNTIES_COUNT = 21 
SIM_WEEKLY_ANIMAL_BOUNTIES_BASE_TOKENS = 48 
SIM_WEEKLY_ANIMAL_BOUNTIES_COUNT = 16   
SIM_WEEKLY_MEGABOARD_COMPLETION_BONUS_TOKENS = 50 
SIM_IDEAL_PLAYER_HAS_VIP = True
SIM_IDEAL_PLAYER_ACHIEVES_MEGA_BOUNTY_BONUS = True 
SIM_BUFF_ITEM_PURCHASE_PRIORITY = [
    "Flower Mask",      
    "Love Charm Shirt",
    "Heart Air Balloon" 
]
_SIM_ACTIVITY_MAP_FOR_BONUS_RULES = {
    "deliveries": "deliveries",
    "chores": "chores",
    "megaboard_bounties": "generic_mega_board_bounties",
    "animal_bounties": "animal_bounties"
}
# --------------------------------------------------------------------

def get_tier_unlock_status_and_cost(
    target_tier_to_unlock,
    all_items_in_shop,
    seasonal_token_name,
    all_currently_purchased_item_names 
):
    tier_to_buy_from = target_tier_to_unlock - 1
    if tier_to_buy_from < 1:
        return False, [], 0, []

    all_tier_candidates = []
    for name, data in all_items_in_shop.items():
        is_seasonal_token_currency = (data.get('currency', '').lower() == seasonal_token_name.lower() or
                                      data.get('currency', '').lower() == 'ticket')
        if (data.get('tier') == tier_to_buy_from and
                is_seasonal_token_currency and
                isinstance(data.get('cost'), (int, float)) and data.get('cost', 0) >= 0):
            all_tier_candidates.append({
                'name': name,
                'cost': data['cost'],
                'tier': tier_to_buy_from,  
                'already_purchased': name in all_currently_purchased_item_names
            })

    num_needed_for_unlock_rule = 4 
    if hasattr(config, 'TIER_UNLOCK_RULES') and isinstance(TIER_UNLOCK_RULES, dict):
        num_needed_for_unlock_rule = TIER_UNLOCK_RULES.get(str(tier_to_buy_from), 4)

    if len(all_tier_candidates) < num_needed_for_unlock_rule:
        log.warning(f"Não existem {num_needed_for_unlock_rule} itens distintos no Tier {tier_to_buy_from} (que custam {seasonal_token_name}) para desbloquear Tier {target_tier_to_unlock}.")
        return True, [], float('inf'), []

    purchased_candidates_for_unlock = [item for item in all_tier_candidates if item['already_purchased']]
    not_purchased_candidates = [item for item in all_tier_candidates if not item['already_purchased']]
    not_purchased_candidates.sort(key=lambda x: x['cost'])

    num_already_contributing = len(purchased_candidates_for_unlock)
    num_still_needed = max(0, num_needed_for_unlock_rule - num_already_contributing)

    items_to_purchase_for_unlock = []
    cost_to_complete_unlock = 0
    fulfilling_items_list = list(purchased_candidates_for_unlock)

    if num_still_needed > 0:
        if len(not_purchased_candidates) < num_still_needed:
            log.warning(f"Faltam itens não comprados no Tier {tier_to_buy_from} para completar o desbloqueio do Tier {target_tier_to_unlock}.")
            return True, [], float('inf'), [item['name'] for item in fulfilling_items_list] 
        items_to_purchase_for_unlock = not_purchased_candidates[:num_still_needed]
        cost_to_complete_unlock = sum(item['cost'] for item in items_to_purchase_for_unlock)
        fulfilling_items_list.extend(items_to_purchase_for_unlock)
        needs_unlocking = True
    else:
        needs_unlocking = False

    fulfilling_items_list.sort(key=lambda x: (0 if x['already_purchased'] else 1, x['cost']))
    final_fulfilling_item_names = [item['name'] for item in fulfilling_items_list[:num_needed_for_unlock_rule]]
    
    if not needs_unlocking and len(final_fulfilling_item_names) < num_needed_for_unlock_rule and len(all_tier_candidates) >= num_needed_for_unlock_rule :
        log.error(f"Lógica inconsistente em get_tier_unlock_status_and_cost para Tier {target_tier_to_unlock}.")
              
    return needs_unlocking, items_to_purchase_for_unlock, cost_to_complete_unlock, final_fulfilling_item_names

def generate_max_potential_season_calendar():
    calendar_data_list = []
    log.info("Iniciando geração do calendário de potencial máximo da temporada...")

    try:
        start_date_obj = datetime.datetime.strptime(config.SEASON_START_DATE, "%Y-%m-%d").date()
        end_date_obj = datetime.datetime.strptime(config.SEASON_END_DATE, "%Y-%m-%d").date()
        activities_start_date_obj = datetime.datetime.strptime(config.DATE_ACTIVITIES_START_YIELDING_TOKENS, "%Y-%m-%d").date()
        
        seasonal_token_name_global = config.SEASONAL_TOKEN_NAME
        shop_items_global = config.SEASONAL_SHOP_ITEMS
        buff_definitions_global = config.SEASONAL_DELIVERY_BUFFS
        activity_rules_global = config.ACTIVITY_BONUS_RULES
        
        dd_start_date_str = getattr(config, 'DOUBLE_DELIVERY_DATE', None) 
        dd_interval = getattr(config, 'DOUBLE_DELIVERY_INTERVAL_DAYS', 8)

        dd_first_occurrence_obj = None
        if dd_start_date_str:
            try:
                dd_first_occurrence_obj = datetime.datetime.strptime(dd_start_date_str, "%Y-%m-%d").date()
            except ValueError:
                log.warning(f"Formato de data inválido em DOUBLE_DELIVERY_DATE: {dd_start_date_str}.")
        
        if not all([shop_items_global, buff_definitions_global, activity_rules_global]):
            log.error("Erro crítico: Configs essenciais não encontradas ou vazias.")
            return []
    except Exception as e: 
        log.error(f"Erro ao carregar configs ou datas: {e}")
        return []

    current_token_balance = 0.0
    day_in_season_counter = 0
    game_week_id_counter = 1 
    
    purchased_buff_items_globally = {} 
    purchased_unlock_items_globally = {}
    unlocked_tiers_state = {1: True} 
    buffs_for_current_chores_week = set()
    buffs_for_current_bounties_week = set()
    vip_bonus_val = 0
    if SIM_IDEAL_PLAYER_HAS_VIP:
        vip_def = buff_definitions_global.get("vip", {})
        vip_bonus_val = vip_def.get("bonus_value", 0)

    # CORREÇÃO: Definir all_buffs_to_track_totals aqui, no escopo da função
    all_buffs_to_track_totals = set(SIM_BUFF_ITEM_PURCHASE_PRIORITY) 
    if "Heart Air Balloon" in buff_definitions_global:
         all_buffs_to_track_totals.add("Heart Air Balloon")

    current_date_iterator = start_date_obj
    
    while current_date_iterator <= end_date_obj:
        day_in_season_counter += 1
        day_of_week_num = current_date_iterator.weekday()
        
        if day_of_week_num == 0 and current_date_iterator != start_date_obj: 
            game_week_id_counter +=1
            
        active_buffs_at_day_start = set(purchased_buff_items_globally.keys()) 
        
        is_double_day = False
        if dd_first_occurrence_obj and current_date_iterator >= dd_first_occurrence_obj:
            delta_days = (current_date_iterator - dd_first_occurrence_obj).days
            if delta_days >= 0 and dd_interval > 0 and delta_days % dd_interval == 0:
                is_double_day = True
        
        delivery_multiplier = 1 # Inicializa aqui para estar sempre definida

        daily_log_entry = {
            "date_display": current_date_iterator.strftime("%d/%m/%y"), 
            "date_iso": current_date_iterator.strftime("%Y-%m-%d"), 
            "day_of_week_str": current_date_iterator.strftime("%a"),
            "day_in_season": day_in_season_counter,
            "game_week_id": game_week_id_counter,
            "is_double_delivery_day": is_double_day,
            "balance_start_day": round(current_token_balance, 2),
            "gains_chest": 0, "gains_deliveries_base": 0, "gains_deliveries_vip_bonus": 0, 
            "gains_chores_base": 0, "gains_chores_vip_bonus": 0, "gains_vip_total_bonus": 0,  
            "gains_megaboard_base": 0, "gains_megaboard_completion_bonus": 0, "gains_animals_base": 0,
            "gains_item_bonuses_detailed": {}, "item_specific_bonus_totals": {}, 
            "total_gains_today": 0, "purchases_today": [], "balance_end_day": 0, "active_buffs_str": ""
        }
        
        # Usa a variável definida no escopo da função
        for buff_item_name_init in all_buffs_to_track_totals:
            daily_log_entry["item_specific_bonus_totals"][buff_item_name_init] = 0

        daily_log_entry["gains_chest"] = SIM_DAILY_CHEST_REWARD_TOKENS
        current_day_vip_deliveries_bonus = 0
        current_day_vip_chores_bonus = 0

        if current_date_iterator >= activities_start_date_obj and day_of_week_num == 6: 
            buffs_for_current_chores_week = set(active_buffs_at_day_start) 
            buffs_for_current_bounties_week = set(active_buffs_at_day_start)
        
        if current_date_iterator >= activities_start_date_obj:
            base_delivery_gains_today = SIM_DAILY_NPC_DELIVERIES_BASE_TOKENS
            vip_delivery_bonus_for_day = 0
            if SIM_IDEAL_PLAYER_HAS_VIP and "vip" in activity_rules_global.get("deliveries",{}).get("applicable_bonuses",[]):
                vip_delivery_bonus_for_day = vip_bonus_val * SIM_DAILY_NPC_DELIVERIES_COUNT
            
            delivery_multiplier = 2 if is_double_day else 1 # Agora está definida corretamente antes de ser usada
            
            daily_log_entry["gains_deliveries_base"] = base_delivery_gains_today * delivery_multiplier
            current_day_vip_deliveries_bonus = vip_delivery_bonus_for_day * delivery_multiplier
            daily_log_entry["gains_deliveries_vip_bonus"] = current_day_vip_deliveries_bonus
            
            for buff_name in active_buffs_at_day_start: 
                item_def = buff_definitions_global.get(buff_name, {})
                item_bonus_value = item_def.get("bonus_value", 0)
                if item_bonus_value > 0 and buff_name in activity_rules_global.get("deliveries",{}).get("applicable_bonuses",[]):
                    bonus_amount_for_item_delivery = (item_bonus_value * SIM_DAILY_NPC_DELIVERIES_COUNT) * delivery_multiplier
                    daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["deliveries"] = bonus_amount_for_item_delivery
            
            if day_of_week_num == 6: 
                daily_log_entry["gains_chores_base"] = SIM_WEEKLY_CHORES_BASE_TOKENS
                if SIM_IDEAL_PLAYER_HAS_VIP and "vip" in activity_rules_global.get("chores",{}).get("applicable_bonuses",[]):
                    current_day_vip_chores_bonus = vip_bonus_val * SIM_WEEKLY_CHORES_COUNT
                    daily_log_entry["gains_chores_vip_bonus"] = current_day_vip_chores_bonus
                for buff_name in buffs_for_current_chores_week: 
                    item_def = buff_definitions_global.get(buff_name, {})
                    item_bonus_value = item_def.get("bonus_value", 0)
                    if item_bonus_value > 0 and buff_name in activity_rules_global.get("chores",{}).get("applicable_bonuses",[]):
                        bonus_amount_for_chores = item_bonus_value * SIM_WEEKLY_CHORES_COUNT
                        daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["chores"] = bonus_amount_for_chores
            
            if day_of_week_num == 0: 
                daily_log_entry["gains_megaboard_base"] = SIM_WEEKLY_MEGABOARD_BOUNTIES_BASE_TOKENS
                if SIM_IDEAL_PLAYER_ACHIEVES_MEGA_BOUNTY_BONUS:
                    daily_log_entry["gains_megaboard_completion_bonus"] = SIM_WEEKLY_MEGABOARD_COMPLETION_BONUS_TOKENS
                daily_log_entry["gains_animals_base"] = SIM_WEEKLY_ANIMAL_BOUNTIES_BASE_TOKENS
                for buff_name in buffs_for_current_bounties_week: 
                    item_def = buff_definitions_global.get(buff_name, {})
                    item_bonus_value = item_def.get("bonus_value", 0)
                    if item_bonus_value > 0:
                        rule_key_megaboard = _SIM_ACTIVITY_MAP_FOR_BONUS_RULES.get("megaboard_bounties", "generic_mega_board_bounties")
                        if buff_name in activity_rules_global.get(rule_key_megaboard,{}).get("applicable_bonuses",[]):
                            bonus_mega = item_bonus_value * SIM_WEEKLY_MEGABOARD_BOUNTIES_COUNT
                            daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["megaboard_bounties"] = bonus_mega
                        rule_key_animal = _SIM_ACTIVITY_MAP_FOR_BONUS_RULES.get("animal_bounties", "animal_bounties")
                        if buff_name in activity_rules_global.get(rule_key_animal,{}).get("applicable_bonuses",[]):
                            bonus_animal = item_bonus_value * SIM_WEEKLY_ANIMAL_BOUNTIES_COUNT
                            daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["animal_bounties"] = bonus_animal
        
        # --- Loop de Compra e Ativação ---
        # (Lógica como na versão anterior - ID: ft3zf2m0x)
        action_taken_this_day_in_purchase_loop = True 
        while action_taken_this_day_in_purchase_loop:
            action_taken_this_day_in_purchase_loop = False 
            current_owned_for_unlock_check = set(purchased_buff_items_globally.keys()) | set(purchased_unlock_items_globally.keys())
            for target_buff_item_name in SIM_BUFF_ITEM_PURCHASE_PRIORITY:
                if purchased_buff_items_globally.get(target_buff_item_name): continue 
                target_buff_shop_info = shop_items_global.get(target_buff_item_name)
                if not target_buff_shop_info:
                    log.error(f"Item de buff '{target_buff_item_name}' não encontrado.")
                    continue 
                required_tier = target_buff_shop_info.get("tier", 1)
                buff_cost = target_buff_shop_info.get("cost", float('inf'))
                buff_currency = target_buff_shop_info.get("currency", "ticket").lower()
                is_sfl_item = buff_currency == "sfl"
                
                if not unlocked_tiers_state.get(required_tier):
                    needs_unlock, items_to_buy_list, cost_to_unlock, _ = get_tier_unlock_status_and_cost(
                        required_tier, shop_items_global, seasonal_token_name_global, current_owned_for_unlock_check
                    )
                    if needs_unlock and cost_to_unlock != float('inf') and current_token_balance >= cost_to_unlock:
                        current_token_balance -= cost_to_unlock
                        for item_dict_to_buy in items_to_buy_list:
                            purchased_unlock_items_globally[item_dict_to_buy['name']] = True
                            current_owned_for_unlock_check.add(item_dict_to_buy['name']) 
                            daily_log_entry["purchases_today"].append({'name': item_dict_to_buy['name'], 'cost': item_dict_to_buy['cost'], 'type': f'unlock_T{required_tier}'})
                            if item_dict_to_buy['name'] in SIM_BUFF_ITEM_PURCHASE_PRIORITY and not purchased_buff_items_globally.get(item_dict_to_buy['name']):
                                purchased_buff_items_globally[item_dict_to_buy['name']] = True 
                        unlocked_tiers_state[required_tier] = True
                        action_taken_this_day_in_purchase_loop = True
                        break 
                if action_taken_this_day_in_purchase_loop: break 
                if unlocked_tiers_state.get(required_tier) and not purchased_buff_items_globally.get(target_buff_item_name):
                    if is_sfl_item: 
                        log.info(f"Dia {day_in_season_counter}: Ativando buff (SFL) '{target_buff_item_name}' (Tier {required_tier}).")
                        purchased_buff_items_globally[target_buff_item_name] = True
                        daily_log_entry["purchases_today"].append({'name': target_buff_item_name, 'cost': buff_cost, 'type': 'buff_item_sfl'}) 
                        action_taken_this_day_in_purchase_loop = True
                        break 
                    elif (buff_currency == 'ticket' or buff_currency == seasonal_token_name_global.lower()) and current_token_balance >= buff_cost:
                        current_token_balance -= buff_cost
                        purchased_buff_items_globally[target_buff_item_name] = True
                        daily_log_entry["purchases_today"].append({'name': target_buff_item_name, 'cost': buff_cost, 'type': 'buff_item_token'})
                        action_taken_this_day_in_purchase_loop = True
                        break 
            if not action_taken_this_day_in_purchase_loop: break

        # Recalcula bônus e totais APÓS todas as compras/ativações do dia
        active_buffs_at_day_start = set(purchased_buff_items_globally.keys()) 
        
        daily_log_entry["gains_item_bonuses_detailed"] = {} 
        for buff_item_name_init in all_buffs_to_track_totals:
            daily_log_entry["item_specific_bonus_totals"][buff_item_name_init] = 0

        # Recalcula bônus VIP e de itens com os buffs ATUAIS do dia
        current_day_vip_deliveries_bonus = 0 
        current_day_vip_chores_bonus = 0     

        if current_date_iterator >= activities_start_date_obj:
            vip_delivery_bonus_for_day_final = 0
            if SIM_IDEAL_PLAYER_HAS_VIP and "vip" in activity_rules_global.get("deliveries",{}).get("applicable_bonuses",[]):
                vip_delivery_bonus_for_day_final = vip_bonus_val * SIM_DAILY_NPC_DELIVERIES_COUNT
            # delivery_multiplier já foi definido antes com base em is_double_day
            current_day_vip_deliveries_bonus = vip_delivery_bonus_for_day_final * delivery_multiplier
            daily_log_entry["gains_deliveries_vip_bonus"] = current_day_vip_deliveries_bonus

            for buff_name in active_buffs_at_day_start: 
                item_def = buff_definitions_global.get(buff_name, {})
                item_bonus_value = item_def.get("bonus_value", 0)
                if item_bonus_value > 0 and buff_name in activity_rules_global.get("deliveries",{}).get("applicable_bonuses",[]):
                    bonus_val = (item_bonus_value * SIM_DAILY_NPC_DELIVERIES_COUNT) * delivery_multiplier
                    daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["deliveries"] = bonus_val
            
            if day_of_week_num == 6:
                if SIM_IDEAL_PLAYER_HAS_VIP and "vip" in activity_rules_global.get("chores",{}).get("applicable_bonuses",[]):
                    current_day_vip_chores_bonus = vip_bonus_val * SIM_WEEKLY_CHORES_COUNT
                    daily_log_entry["gains_chores_vip_bonus"] = current_day_vip_chores_bonus
                for buff_name in buffs_for_current_chores_week: 
                    item_def = buff_definitions_global.get(buff_name, {})
                    item_bonus_value = item_def.get("bonus_value", 0)
                    if item_bonus_value > 0 and buff_name in activity_rules_global.get("chores",{}).get("applicable_bonuses",[]):
                        daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["chores"] = item_bonus_value * SIM_WEEKLY_CHORES_COUNT

            if day_of_week_num == 0:
                for buff_name in buffs_for_current_bounties_week: 
                    item_def = buff_definitions_global.get(buff_name, {})
                    item_bonus_value = item_def.get("bonus_value", 0)
                    if item_bonus_value > 0:
                        rule_key_megaboard = _SIM_ACTIVITY_MAP_FOR_BONUS_RULES.get("megaboard_bounties", "generic_mega_board_bounties")
                        if buff_name in activity_rules_global.get(rule_key_megaboard,{}).get("applicable_bonuses",[]):
                            daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["megaboard_bounties"] = item_bonus_value * SIM_WEEKLY_MEGABOARD_BOUNTIES_COUNT
                        rule_key_animal = _SIM_ACTIVITY_MAP_FOR_BONUS_RULES.get("animal_bounties", "animal_bounties")
                        if buff_name in activity_rules_global.get(rule_key_animal,{}).get("applicable_bonuses",[]):
                            daily_log_entry["gains_item_bonuses_detailed"].setdefault(buff_name, {})["animal_bounties"] = item_bonus_value * SIM_WEEKLY_ANIMAL_BOUNTIES_COUNT
        
        for buff_item_name_recalc in all_buffs_to_track_totals: 
            if buff_item_name_recalc in daily_log_entry["gains_item_bonuses_detailed"]:
                for source_bonus_value in daily_log_entry["gains_item_bonuses_detailed"][buff_item_name_recalc].values():
                    daily_log_entry["item_specific_bonus_totals"][buff_item_name_recalc] += source_bonus_value
        
        daily_log_entry["gains_vip_total_bonus"] = current_day_vip_deliveries_bonus + current_day_vip_chores_bonus
        total_gains_from_all_item_buffs_today = sum(daily_log_entry["item_specific_bonus_totals"].values())

        # O daily_log_entry["gains_deliveries_base"] já está multiplicado se for double_day
        # Ganhos totais BRUTOS do dia (sem descontar compras)
        gains_today_gross = round(
            daily_log_entry["gains_chest"] +
            daily_log_entry["gains_deliveries_base"] + 
            daily_log_entry["gains_chores_base"] + 
            daily_log_entry["gains_vip_total_bonus"] + 
            daily_log_entry["gains_megaboard_base"] + daily_log_entry["gains_megaboard_completion_bonus"] +
            daily_log_entry["gains_animals_base"] +
            total_gains_from_all_item_buffs_today, 
            2
        )
        daily_log_entry["total_gains_today"] = gains_today_gross # Armazena o ganho bruto
        
        # Saldo final é o saldo no início do dia + ganhos brutos do dia - custos de tokens das compras do dia
        cost_of_token_purchases_today = 0
        for purchase in daily_log_entry["purchases_today"]:
            # Considera apenas compras que custam tokens sazonais para deduzir do saldo de tokens
            purchase_type = purchase.get('type', '')
            if purchase_type == 'buff_item_token' or 'unlock' in purchase_type:
                cost_of_token_purchases_today += purchase.get('cost', 0)
        
        current_token_balance = daily_log_entry["balance_start_day"] + gains_today_gross - cost_of_token_purchases_today
        daily_log_entry["balance_end_day"] = round(current_token_balance, 2)
        
        daily_log_entry["active_buffs_str"] = ", ".join(sorted(list(purchased_buff_items_globally.keys())))
        calendar_data_list.append(daily_log_entry)
        current_date_iterator += datetime.timedelta(days=1)
    
    log.info(f"Geração do calendário finalizada. {len(calendar_data_list)} dias processados.")
    return calendar_data_list

# --- (Bloco if __name__ == '__main__' como estava antes) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
    
    class MockConfig: 
        SEASON_START_DATE = "2025-05-01"
        SEASON_END_DATE = "2025-06-10" 
        DATE_ACTIVITIES_START_YIELDING_TOKENS = "2025-05-01" 
        SEASONAL_TOKEN_NAME = "TestSeed"
        TIER_UNLOCK_RULES = {'1': 4, '2': 4} 
        
        DOUBLE_DELIVERY_DATE = "2025-05-06" 
        DOUBLE_DELIVERY_INTERVAL_DAYS = 8

        SEASONAL_SHOP_ITEMS = {
            "Flower Mask":       {"cost": 100, "currency": "ticket", "tier": 1}, 
            "NonBuffItemT1_1":   {"cost": 10, "currency": "ticket", "tier": 1}, 
            "NonBuffItemT1_2":   {"cost": 10, "currency": "ticket", "tier": 1}, 
            "NonBuffItemT1_3":   {"cost": 10, "currency": "ticket", "tier": 1}, 
            "NonBuffItemT1_4":   {"cost": 10, "currency": "ticket", "tier": 1}, 
            "Love Charm Shirt":  {"cost": 150, "currency": "ticket", "tier": 2}, 
            "NonBuffItemT2_1":   {"cost": 20, "currency": "ticket", "tier": 2},
            "NonBuffItemT2_2":   {"cost": 20, "currency": "ticket", "tier": 2},
            "NonBuffItemT2_3":   {"cost": 20, "currency": "ticket", "tier": 2},
            "NonBuffItemT2_4":   {"cost": 20, "currency": "ticket", "tier": 2}, 
            "Heart Air Balloon": {"cost": 200, "currency": "sfl", "tier": 3}, 
        }
        SEASONAL_DELIVERY_BUFFS = { 
            "vip": {"type": "vip", "bonus_value": 2},
            "Flower Mask": {"type": "equipped", "bonus_value": 1}, 
            "Love Charm Shirt": {"type": "equipped", "bonus_value": 2}, 
            "Heart Air Balloon": {"type": "collectible", "bonus_value": 1} 
        }
        _all_buffs = list(SEASONAL_DELIVERY_BUFFS.keys()) 
        _all_buffs_no_vip = [b for b in _all_buffs if b != "vip"]
        ACTIVITY_BONUS_RULES = { 
            "deliveries": {"applicable_bonuses": _all_buffs}, 
            "chores": {"applicable_bonuses": _all_buffs},     
            "generic_mega_board_bounties": {"applicable_bonuses": _all_buffs_no_vip}, 
            "animal_bounties": {"applicable_bonuses": _all_buffs_no_vip},            
        }
    _actual_config_module = config 
    globals()['config'] = MockConfig() 
    generated_calendar = generate_max_potential_season_calendar()
    globals()['config'] = _actual_config_module  
    if generated_calendar:
        for day_entry in generated_calendar:
            double_day_marker = "✨DD✨" if day_entry.get("is_double_delivery_day") else ""
            purchase_marker = "🛍️" if day_entry["purchases_today"] else ""
            hab_active_marker = "🎈" if "Heart Air Balloon" in day_entry["active_buffs_str"] else ""
            print(f"Dia {day_entry['day_in_season']:<2} ({day_entry['date_display']} {day_entry['day_of_week_str']}) W:{day_entry['game_week_id']}{double_day_marker}{purchase_marker}{hab_active_marker} | SaldoIn: {day_entry['balance_start_day']:.0f} | Ganhos VIP: {day_entry['gains_vip_total_bonus']:.0f} (D:{day_entry['gains_deliveries_vip_bonus']:.0f},C:{day_entry['gains_chores_vip_bonus']:.0f}) | Itens: {sum(day_entry.get('item_specific_bonus_totals', {}).values()):.0f} | TotalDia: {day_entry['total_gains_today']:.0f} | SaldoFim: {day_entry['balance_end_day']:.0f} | Buffs: {day_entry['active_buffs_str']}")
            if day_entry["purchases_today"]: print(f"  Compras: {day_entry['purchases_today']}")
            item_bonus_details_str = []
            for item_name_det, details_det in day_entry.get("gains_item_bonuses_detailed", {}).items():
                if sum(details_det.values()) > 0: 
                    parts_det = [f"{src_det[:1]}:{val_det:.0f}" for src_det, val_det in details_det.items() if val_det > 0]
                    item_bonus_details_str.append(f"{item_name_det.replace(' ','')[:6]}: {', '.join(parts_det)}")
            if item_bonus_details_str : print(f"  ItemBnsDet: {'; '.join(item_bonus_details_str)}")
    else:
        log.warning("Calendário de teste gerado está vazio.")