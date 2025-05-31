# route_helpers.py
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional # List foi adicionado para type hinting

import bumpkin_utils # Certifique-se que bumpkin_utils está no mesmo diretório ou PYTHONPATH

# --->: GET_BOUNTY_ACTIVITY_TYPE
def get_bounty_activity_type(bounty_data: Dict[str, Any], config_module: Any, logger: Any) -> Optional[str]:
    """
    Determina o 'activity_type' para uma bounty com base em seu nome (item requisitado)
    e nas configurações e estrutura da recompensa.
    """
    bounty_item_name = bounty_data.get("name")
    if not bounty_item_name:
        logger.debug(f"Bounty sem nome (item requisitado) não pode ser classificada para bônus: {bounty_data.get('id', 'N/A')}")
        return None

    if bounty_item_name in getattr(config_module, 'ANIMAL_NAMES_HEURISTIC', []): #
        animal_rules = config_module.ACTIVITY_BONUS_RULES.get("animal_bounties", {}) #
        item_container = animal_rules.get("item_container_field")
        if animal_rules.get("reward_type") == "item_dict" and \
           item_container and item_container in bounty_data and \
           isinstance(bounty_data.get(item_container), dict):
            logger.debug(f"Bounty '{bounty_item_name}' classificada como 'animal_bounties' (item_dict).")
            return "animal_bounties"

    generic_rules = config_module.ACTIVITY_BONUS_RULES.get("generic_mega_board_bounties", {}) #
    item_container_generic = generic_rules.get("item_container_field")
    # A API sempre retorna Geniseed (ou o token sazonal) dentro de 'items' para bounties do megaboard.
    # Não é mais necessário verificar 'seasonalTicketReward'.
    if generic_rules.get("reward_type") == "item_dict" and \
       item_container_generic and item_container_generic in bounty_data and \
       isinstance(bounty_data.get(item_container_generic), dict) and \
       getattr(config_module, 'SEASONAL_TOKEN_NAME', 'Geniseed') in bounty_data[item_container_generic]: #
        logger.debug(f"Bounty '{bounty_item_name}' classificada como 'generic_mega_board_bounties' (item_dict com {getattr(config_module, 'SEASONAL_TOKEN_NAME', 'Geniseed')}).")
        return "generic_mega_board_bounties"

    logger.debug(f"Bounty '{bounty_item_name}' não correspondeu a nenhuma regra de bônus conhecida.")
    return None

# --->: EXTRACT_INVENTORY_AND_FARM_DETAILS
def _extract_inventory_and_farm_details(farm_data_api: Dict[str, Any], current_config: Any, logger: Any) -> Dict[str, Any]:
    """
    Extrai detalhes do inventário, facção e ilha para o card de identificação.
    """
    details = {
        "gems_amount": 0,
        "potion_tickets_amount": 0,
        "seasonal_token_amount": 0.0,
        "faction_name": "N/A",
        "faction_emblem_name": "N/A",
        "faction_emblems_amount": 0,
        "island_type": "N/A",
        "island_expansion_level": 0
    }
    inventory_data = farm_data_api.get('inventory', {})
    faction_data = farm_data_api.get('faction', {})
    island_data = farm_data_api.get('island', {})

    try:
        details["gems_amount"] = int(float(inventory_data.get('Gem', '0')))
        details["potion_tickets_amount"] = int(float(inventory_data.get('Potion Ticket', '0')))
        
        seasonal_token_key = current_config.SEASONAL_TOKEN_NAME #
        details["seasonal_token_amount"] = float(inventory_data.get(seasonal_token_key, '0.0'))

        # Lógica de fallback para "Mark" se o token do config não for "Mark" e for zero.
        if seasonal_token_key != "Mark" and details["seasonal_token_amount"] == 0.0:
            mark_amount_in_inventory = float(inventory_data.get('Mark', '0.0'))
            if mark_amount_in_inventory > 0:
                logger.info(f"Token sazonal '{seasonal_token_key}' não encontrado/zerado, mas 'Mark' ({mark_amount_in_inventory}) será usado como fallback para exibição no card de identificação.")
                # Se você quiser que "Mark" seja o token exibido neste caso:
                # details["seasonal_token_name_from_config"] = "Mark" # O nome já é passado ao dict principal
                # details["seasonal_token_amount"] = mark_amount_in_inventory
                # Por ora, a lógica no dict principal já passa o nome do config,
                # e aqui apenas atualizamos a quantidade se o fallback for desejado.
                # Para evitar confusão, vamos manter o token do config como prioridade.
                # Se "Mark" é o token da temporada, SEASONAL_TOKEN_NAME deve ser "Mark".
                pass


    except ValueError as ve:
        logger.warning(f"ValueError ao converter valores do inventário para números: {ve}")

    if isinstance(faction_data, dict) and faction_data:
        raw_faction_name = faction_data.get('name')
        if raw_faction_name:
            details["faction_name"] = raw_faction_name.replace("_", " ").title()
            
            faction_name_lower = raw_faction_name.lower()
            emblem_key_base = ""
            # Mapeamento de nomes de facção (plural da API) para base de chave de emblema (singular)
            faction_to_emblem_base = {
                "nightshades": "Nightshade",
                "sunflorians": "Sunflorian",
                "bumpkins": "Bumpkin",
                "goblins": "Goblin"
                # Adicione outras facções conforme necessário
            }
            emblem_key_base = faction_to_emblem_base.get(faction_name_lower)

            if emblem_key_base:
                emblem_key = f"{emblem_key_base} Emblem"
                details["faction_emblem_name"] = emblem_key # Nome da chave para debug ou referência interna
                try:
                    details["faction_emblems_amount"] = int(float(inventory_data.get(emblem_key, '0')))
                except ValueError:
                    logger.warning(f"Não foi possível converter a quantidade de emblemas '{emblem_key}' para número.")
            else:
                logger.warning(f"Nome de facção desconhecido '{raw_faction_name}' para construir chave de emblema.")
                details["faction_emblem_name"] = "Emblema Desconhecido" # Para exibição se a chave não for encontrada
        else:
            details["faction_name"] = "N/A (Sem Facção)"
    else:
        details["faction_name"] = "N/A (Sem Facção)"

    if isinstance(island_data, dict):
        details["island_type"] = island_data.get('type', 'N/A').capitalize()
        previous_expansions = island_data.get('previousExpansions', 0)
        try:
            previous_expansions_num = int(previous_expansions)
            details["island_expansion_level"] = max(0, previous_expansions_num - 1)
        except ValueError:
            logger.warning(f"Não foi possível converter 'previousExpansions' ({previous_expansions}) para número.")
    
    return details

# --->: PREPROCESS_ACTIVE_DELIVERIES
def _preprocess_active_deliveries(delivery_orders_from_api: List[Dict[str, Any]], 
                                  current_config: Any, 
                                  total_delivery_bonus: int, 
                                  is_double_delivery_active: bool, 
                                  logger: Any) -> Dict[str, Dict[str, Any]]:
    """
    Pré-processa a lista de entregas ativas da API, calculando recompensas.
    """
    active_deliveries_map = {}
    if not isinstance(delivery_orders_from_api, list):
        return active_deliveries_map

    for order in delivery_orders_from_api:
        if not (isinstance(order, dict) and order.get('from')):
            continue
        
        npc_name = order.get('from')
        order_reward_api = order.get('reward', {}) # Objeto da recompensa da API
        
        # Inicializa informações da recompensa
        is_seasonal_token = False
        calculated_tokens = 0
        sfl_value = None
        coin_value = None
        is_alternative_reward_for_token_npc = False

        # Verifica se o NPC está na lista de NPCs que dão token sazonal base
        is_npc_expected_to_give_token = npc_name in current_config.BASE_DELIVERY_REWARDS #

        if isinstance(order_reward_api, dict) and (order_reward_api.get('sfl') is not None or order_reward_api.get('coins') is not None):
            # A API explicitamente lista SFL ou Moedas
            sfl_value = order_reward_api.get('sfl')
            coin_value = order_reward_api.get('coins')
            if is_npc_expected_to_give_token:
                is_alternative_reward_for_token_npc = True
                logger.info(f"Entrega para {npc_name} (esperado token) está dando recompensa alternativa: SFL={sfl_value}, Coins={coin_value}")
        elif is_npc_expected_to_give_token: 
            # Se não há SFL/Moedas E o NPC é esperado dar token, calcula o token sazonal
            # Isso cobre o caso de `order_reward_api` ser `{}` ou não ter sfl/coins
            is_seasonal_token = True
            base_tokens = current_config.BASE_DELIVERY_REWARDS.get(npc_name, 0) #
            effective_reward = base_tokens + total_delivery_bonus
            if is_double_delivery_active:
                effective_reward *= 2
            calculated_tokens = effective_reward
        # Se não é um NPC de token e a recompensa da API não é SFL/Moedas, a recompensa permanece como desconhecida/não tratada

        active_deliveries_map[npc_name] = {
            "id": order.get('id'),
            "items_required": order.get('items', {}),
            "is_seasonal_token_reward": is_seasonal_token,
            "calculated_seasonal_token_reward": calculated_tokens,
            "sfl_reward": sfl_value,
            "coin_reward": coin_value,
            "is_alternative_reward": is_alternative_reward_for_token_npc,
            "completed_at_timestamp": order.get('completedAt') 
        }
    return active_deliveries_map

# --->: PROCESS_NPC_DELIVERY_STATE_AND_LIVE_UPDATES
def _process_npc_delivery_state_and_live_updates(
    farm_id_submitted: str, npc_data_completo: Dict[str, Any], current_config: Any, 
    processed_data_ref: Dict[str, Any], # Passa a referência para modificar diretamente
    active_deliveries_info_map: Dict[str, Any], 
    current_db_utils: Any, logger: Any):
    """
    Processa o estado dos NPCs de entrega, calcula taxas, atualizações ao vivo e custos.
    Modifica `processed_data_ref` diretamente.
    """
    if not npc_data_completo:
        logger.warning(f"Chave 'npcs' vazia/ausente. Pulando processamento de estado e live updates para Farm {farm_id_submitted}.")
        return

    npcs_processed_for_state = []
    state_update_failed = False
    prices_now = current_db_utils.get_sfl_world_prices() or {} #

    for npc_name in current_config.BASE_DELIVERY_REWARDS: #
        npc_info_hist = npc_data_completo.get(npc_name)
        if not isinstance(npc_info_hist, dict):
            logger.warning(f"Dados históricos do NPC '{npc_name}' não encontrados para Farm {farm_id_submitted}.")
            continue

        current_delivery_count = npc_info_hist.get('deliveryCount')
        current_skipped_count = npc_info_hist.get('skippedCount', 0)

        if current_delivery_count is not None:
            total = current_delivery_count + (current_skipped_count or 0)
            processed_data_ref["npc_rates"][npc_name] = round((current_delivery_count / total) * 100, 1) if total > 0 else 0.0
            
            try:
                previous_state_data = current_db_utils.get_npc_state(farm_id_submitted, npc_name) #
                if previous_state_data:
                    previous_count = previous_state_data.get('last_delivery_count', 0)
                    if current_delivery_count > previous_count:
                        completions_now = current_delivery_count - previous_count
                        processed_data_ref["live_completions"] += completions_now
                        
                        # Verifica a recompensa da entrega que FOI completada (baseado no estado ATIVO anterior)
                        # Esta lógica assume que a entrega ativa no momento do snapshot anterior é a que foi completada
                        active_order_details = active_deliveries_info_map.get(npc_name, {})
                        
                        if active_order_details.get("is_seasonal_token_reward"):
                            # Usa o valor de token já calculado (que inclui bônus e evento de dobro)
                            tokens_for_this_completion = active_order_details.get("calculated_seasonal_token_reward", 0)
                            processed_data_ref["live_tokens"] += completions_now * tokens_for_this_completion
                            
                            # Calcula custo SFL apenas se a recompensa foi em token
                            items_needed_live = active_order_details.get('items_required', {})
                            cost_this_completion_sfl = 0.0
                            if prices_now and items_needed_live:
                                try:
                                    cost_this_completion_sfl = sum((amount or 0) * prices_now.get(item, 0.0) for item, amount in items_needed_live.items())
                                except Exception as e_cost_live:
                                    logger.exception(f"Erro ao calcular custo (live) de {npc_name} para Farm {farm_id_submitted}: {e_cost_live}")
                            processed_data_ref["live_cost_sfl"] += completions_now * cost_this_completion_sfl
                        # Se a recompensa não foi token (foi SFL/Moedas), não adiciona a processed_data_ref["live_tokens"]
                        # nem a processed_data_ref["live_cost_sfl"] (a menos que queira rastrear custo de entregas não-token também)

                update_success = current_db_utils.update_npc_state( #
                    farm_id_submitted, npc_name,
                    current_delivery_count, current_skipped_count or 0,
                    npc_info_hist.get('deliveryCompletedAt')
                )
                if update_success:
                    npcs_processed_for_state.append(npc_name)
                else:
                    state_update_failed = True
                    logger.error(f"Falha ao salvar estado para {farm_id_submitted}/{npc_name}")
            except Exception as e_state:
                logger.exception(f"Erro ao processar estado/live para {farm_id_submitted}/{npc_name}: {e_state}")
                state_update_failed = True
        else:
            processed_data_ref["npc_rates"][npc_name] = 'N/A'

    if state_update_failed and not processed_data_ref.get("processing_error_message"):
        processed_data_ref["processing_error_message"] = "Atenção: Erro parcial ao salvar estado das entregas."
    elif npcs_processed_for_state:
        logger.debug(f"Estado atualizado para NPCs: {', '.join(npcs_processed_for_state)} em Farm {farm_id_submitted}.")

# --->: PROCESS_FARM_DATA_ON_SUBMIT
def process_farm_data_on_submit(
        farm_id_submitted: str,
        api_response_data: Dict[str, Any], 
        current_config: Any, 
        current_analysis: Any, 
        current_db_utils: Any, 
        gerar_bumpkin_url_func: Any, 
        logger: Any) -> Dict[str, Any]:
    """
    Processa os dados da fazenda da API, calcula bônus, processa NPCs, 
    atualiza estado no DB e cria snapshots.
    """
    processed_data = {
        "farm_data_display": None, "npc_rates": {}, "live_completions": 0, "live_tokens": 0,
        "live_cost_sfl": 0.0, "total_delivery_bonus": 0, "active_bonus_details": {},
        "bounties_data": {}, "chores_data": [], "bumpkin_image_url": None,
        "processing_error_message": None, "seasonal_token_name_from_config": current_config.SEASONAL_TOKEN_NAME, #
        "active_deliveries_info": {} # Para informações de entrega pré-processadas
    }
    # Adiciona os campos extraídos para o card de identificação
    processed_data.update(_extract_inventory_and_farm_details(api_response_data.get('farm', {}), current_config, logger))

    try:
        farm_data_api = api_response_data.get('farm')
        if not farm_data_api:
            logger.error(f"Chave 'farm' ausente na resposta da API para Farm ID {farm_id_submitted}.")
            processed_data["processing_error_message"] = "Resposta da API incompleta."
            return processed_data
        processed_data["farm_data_display"] = farm_data_api

        delivery_orders_from_api = farm_data_api.get('delivery', {}).get('orders', [])
        
        # Imagem do Bumpkin
        bumpkin_data_from_api = farm_data_api.get("bumpkin")
        if bumpkin_data_from_api and isinstance(bumpkin_data_from_api, dict):
            equipped_items = bumpkin_data_from_api.get("equipped")
            if equipped_items and isinstance(equipped_items, dict):
                processed_data["bumpkin_image_url"] = gerar_bumpkin_url_func(equipped_items) #
        
        # Bônus de Entrega
        bonus_info = current_analysis.calculate_delivery_bonus(farm_data_api, current_config.SEASONAL_DELIVERY_BUFFS) #
        processed_data["total_delivery_bonus"] = bonus_info.get('total_bonus', 0)
        processed_data["active_bonus_details"] = bonus_info.get('details', {})

        # Pré-processa entregas ativas
        processed_data["active_deliveries_info"] = _preprocess_active_deliveries(
            delivery_orders_from_api, current_config,
            processed_data["total_delivery_bonus"],
            processed_data["active_bonus_details"].get("is_double_delivery_active", False),
            logger
        )
        
        # Estado dos NPCs e Live Updates
        _process_npc_delivery_state_and_live_updates(
            farm_id_submitted, farm_data_api.get('npcs', {}), current_config,
            processed_data, processed_data["active_deliveries_info"], 
            current_db_utils, logger
        )
        
        # Criação do Snapshot
        try:
            current_db_utils.create_snapshot_if_needed(farm_id_submitted, farm_data_api, delivery_orders_from_api) #
        except Exception as e_snap:
            logger.exception(f"Erro ao criar snapshot para Farm {farm_id_submitted}: {e_snap}")
            if not processed_data.get("processing_error_message"):
                processed_data["processing_error_message"] = "Aviso: Falha ao registrar snapshot diário."

    except KeyError as ke: # Captura KeyErrors mais amplos no processamento inicial
        logger.exception(f"KeyError processando dados da API para Farm {farm_id_submitted}: Chave {ke}.")
        processed_data["processing_error_message"] = "Erro ao processar dados da fazenda (formato inesperado)."
        return processed_data
    except Exception as e_global_proc: # Captura outras exceções gerais
        logger.exception(f"Erro inesperado processando dados da fazenda {farm_id_submitted}: {e_global_proc}")
        processed_data["processing_error_message"] = "Erro interno ao processar dados."
        return processed_data

    # --- Processamento de Bounties e Chores (mantido mais enxuto) ---
    active_player_bonus_names = list(processed_data["active_bonus_details"].keys())

    # Bounties
    bounties_from_api = farm_data_api.get('bounties', {}).get('requests', []) if farm_data_api else []
    processed_bounties_categories = {category: [] for category in current_config.BOUNTY_CATEGORY_ORDER} #
    for bounty_raw in bounties_from_api:
        bounty = bounty_raw.copy()
        activity_type = get_bounty_activity_type(bounty, current_config, logger)
        if activity_type:
            bonus_val = current_analysis.calculate_bonus_for_activity(active_player_bonus_names, activity_type, current_config.SEASONAL_DELIVERY_BUFFS, current_config.ACTIVITY_BONUS_RULES) #
            if bonus_val > 0:
                bounty = current_analysis.apply_bonus_to_reward(bounty, bonus_val, current_config.ACTIVITY_BONUS_RULES[activity_type], current_config.SEASONAL_TOKEN_NAME) #
        
        b_name = bounty.get("name", "")
        cat = "Exotic"
        if b_name in current_config.FLOWER_BOUNTY_NAMES: cat = "Flores" #
        elif b_name in current_config.FISH_BOUNTY_NAMES: cat = "Peixes" #
        elif b_name in current_config.MARK_BOUNTY_NAMES: cat = "Mark" #
        elif b_name in current_config.OBSIDIAN_BOUNTY_NAMES: cat = "Obsidiana" #
        
        if cat in processed_bounties_categories: processed_bounties_categories[cat].append(bounty)
        else: processed_bounties_categories["Exotic"].append(bounty)
    processed_data["bounties_data"] = {"categories": processed_bounties_categories, "order": current_config.BOUNTY_CATEGORY_ORDER} #

    # Chores
    chores_from_api = farm_data_api.get('choreBoard', {}).get('chores', {}) if farm_data_api else {}
    processed_chores_list = []
    if isinstance(chores_from_api, dict):
        for npc_name, chore_api_data in chores_from_api.items():
            if not isinstance(chore_api_data, dict): continue
            chore_data = {
                "npc_key_for_filename": npc_name, "npc_name": npc_name.replace("_", " ").title(),
                "description": chore_api_data.get("name", "N/A"),
                "reward_items_original": chore_api_data.get("reward", {}).get("items", {}),
                "is_completed_api": chore_api_data.get("completedAt") is not None,
                "base_seasonal_tickets": 0, "final_seasonal_tickets": 0,
                "bonus_applied_to_tickets": False, "bonus_amount_tickets": 0,
                "other_rewards_formatted": []
            }
            # Timestamps formatados
            for ts_key, formatted_key in [("startedAt", "started_at_formatted"), ("completedAt", "completed_at_formatted")]:
                if chore_api_data.get(ts_key):
                    try: chore_data[formatted_key] = datetime.fromtimestamp(chore_api_data[ts_key] / 1000).strftime('%d/%m/%y %H:%M')
                    except: chore_data[formatted_key] = "Data Inválida"
            
            rewards_orig = chore_data["reward_items_original"]
            token_key = current_config.SEASONAL_TOKEN_NAME #
            base_tokens_chore = rewards_orig.get(token_key, 0)
            if not isinstance(base_tokens_chore, (int, float)): base_tokens_chore = 0
            
            chore_data["base_seasonal_tickets"] = base_tokens_chore
            chore_data["final_seasonal_tickets"] = base_tokens_chore

            for item, amt in rewards_orig.items():
                if item != token_key: chore_data["other_rewards_formatted"].append(f"{amt} {item.replace('_', ' ').title()}")

            if base_tokens_chore > 0:
                bonus_val_chore = current_analysis.calculate_bonus_for_activity(active_player_bonus_names, "chores", current_config.SEASONAL_DELIVERY_BUFFS, current_config.ACTIVITY_BONUS_RULES) #
                if bonus_val_chore > 0:
                    reward_obj_for_bonus = {"items": rewards_orig.copy()}
                    modified_rewards = current_analysis.apply_bonus_to_reward(reward_obj_for_bonus, bonus_val_chore, current_config.ACTIVITY_BONUS_RULES["chores"], token_key) #
                    if modified_rewards.get('is_bonus_applied'):
                        chore_data["final_seasonal_tickets"] = modified_rewards.get("items", {}).get(token_key, base_tokens_chore)
                        chore_data["bonus_applied_to_tickets"] = True
                        chore_data["bonus_amount_tickets"] = modified_rewards.get('applied_bonus_value', 0)
            processed_chores_list.append(chore_data)
    processed_data["chores_data"] = processed_chores_list
    
    return processed_data

# --->: GET_HISTORICAL_ANALYSIS_RESULTS (Análise Histórica de Entregas)
def get_historical_analysis_results(farm_id: str, total_delivery_bonus_for_analysis: int, current_db_utils: Any, current_analysis: Any, logger: Any, datetime_cls: Any) -> Dict[str, Any]:
    # ... (código existente, apenas verificando se já foi otimizado) ...
    # Esta função já parece relativamente otimizada para sua tarefa.
    # A principal carga está nas chamadas ao banco de dados e no `calcular_estimativa_token_deliveries`.
    analise_historica_data = {
        'status': 'ok', 'total_conclusoes': 0, 'total_tokens_estimados': 0,
        'total_custo_estimado_sfl': 0.0, 'detalhes_por_npc': {},
        'dados_completos': False, 'periodo_analisado': "N/A",
        'dias_analisados': 0, 'taxa_media_diaria_real': 0.0
    }
    try:
        farm_id_int = int(farm_id) 
        primeira_data_str, ultima_data_str = current_db_utils.get_first_and_last_snapshot_date(farm_id_int) #
        
        if primeira_data_str and ultima_data_str:
            resultado_analysis_py = current_analysis.calcular_estimativa_token_deliveries(farm_id, primeira_data_str, ultima_data_str, primeira_data_str, total_delivery_bonus_for_analysis) #
            if resultado_analysis_py: analise_historica_data.update(resultado_analysis_py)
            else:
                analise_historica_data['status'] = 'erro_analise'
                analise_historica_data['mensagem'] = "Não foi possível gerar os dados da análise histórica."

            if 'erro' not in analise_historica_data and analise_historica_data.get('status') != 'erro_analise':
                try:
                    dt_inicio = datetime_cls.strptime(primeira_data_str, '%Y-%m-%d')
                    dt_fim = datetime_cls.strptime(ultima_data_str, '%Y-%m-%d')
                    dias_no_periodo = (dt_fim - dt_inicio).days + 1
                    analise_historica_data['dias_analisados'] = dias_no_periodo
                    analise_historica_data['periodo_analisado'] = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
                    total_tokens = analise_historica_data.get('total_tokens_estimados', 0)
                    if dias_no_periodo > 0 and total_tokens is not None and total_tokens > 0 : # Adicionado total_tokens > 0
                        analise_historica_data['taxa_media_diaria_real'] = round(total_tokens / dias_no_periodo, 2)
                    else: # Se não há tokens ou dias, a taxa é 0 ou indefinida
                        analise_historica_data['taxa_media_diaria_real'] = 0.0
                except ValueError: 
                    analise_historica_data['periodo_analisado'] = f"{primeira_data_str} a {ultima_data_str}"
        else: 
            analise_historica_data['status'] = 'sem_historico'
            analise_historica_data['mensagem'] = "Nenhum histórico de entregas encontrado para análise."
    except ValueError: analise_historica_data['erro'] = "Farm ID inválido para consulta de histórico."
    except Exception as e:
        logger.exception(f"Erro durante busca/análise de snapshots para Farm {farm_id}: {e}")
        analise_historica_data['erro'] = "Falha ao calcular o histórico de entregas."
    return analise_historica_data

# --->: DETERMINE_ACTIVE_DAILY_RATE
def determine_active_daily_rate(simulated_rate_str: Optional[str], historical_rate_str: Optional[str], logger: Any, default_placeholder_rate: float = 10.0) -> tuple[float, bool]:
    # ... (código existente, já parece eficiente) ...
    rate_to_use = None; is_simulated = False
    if simulated_rate_str:
        try: parsed_sim_rate = float(simulated_rate_str)
        except (ValueError, TypeError): parsed_sim_rate = -1 
        if parsed_sim_rate > 0: rate_to_use, is_simulated = parsed_sim_rate, True
    if rate_to_use is None and historical_rate_str:
        try: parsed_hist_rate = float(historical_rate_str)
        except (ValueError, TypeError): parsed_hist_rate = -1
        if parsed_hist_rate > 0: rate_to_use = parsed_hist_rate
    final_rate = rate_to_use if rate_to_use is not None else default_placeholder_rate
    logger.debug(f"Taxa diária determinada: {final_rate:.2f} (Simulada: {is_simulated})")
    return final_rate, is_simulated

# --->: CALCULATE_REMAINING_SEASON_DAYS
def calculate_remaining_season_days(season_end_date_str: Optional[str], datetime_cls: Any, logger: Any) -> Optional[int]:
    # ... (código existente, já parece eficiente) ...
    if not season_end_date_str: logger.warning("SEASON_END_DATE não definida."); return None
    try: end_date = datetime_cls.strptime(season_end_date_str, '%Y-%m-%d').date(); return max(0, (end_date - datetime_cls.now().date()).days)
    except (ValueError, TypeError) as e: logger.error(f"Erro ao parsear SEASON_END_DATE '{season_end_date_str}': {e}"); return None

# --->: GET_PROJECTION_CALCULATION_DETAILS
def get_projection_calculation_details(item_name: str, 
                                     shop_items: Dict[str, Any], 
                                     marked_items: List[str], 
                                     rate: float, 
                                     analysis_module: Any, 
                                     logger: Any) -> Dict[str, Any]:
    results = {
        "custo_total_calculado_tickets": float('inf'), # O que a loja usará para projetar dias (item de ticket + desbloqueio)
        "custo_item_base_ticket": None,             # Custo base do item de ticket em si
        "custo_desbloqueio_tickets": float('inf'), # Custo de desbloqueio em tickets para o tier do item
        "unlock_items_detalhados": [],
        "unlock_items_list": [],
        "dias_projetados": float('inf'),
        "is_tier_unlockable": False,
        "item_currency_original": None # Para saber a moeda do item clicado
    }    
    try:
        cost_info = analysis_module.calcular_custo_total_item(item_name, shop_items, marked_items)

        results["is_tier_unlockable"] = cost_info.get('is_tier_unlockable', False)
        results["item_currency_original"] = cost_info.get('item_currency_original')
        results["custo_desbloqueio_tickets"] = cost_info.get('unlock_cost_tickets', float('inf'))
        results["unlock_items_detalhados"] = cost_info.get('unlock_items_details', [])
        results["unlock_items_list"] = [item['name'] for item in results["unlock_items_detalhados"]]

        item_currency = cost_info.get('item_currency_original')
        
        if item_currency == 'ticket':
            # Para itens de ticket, o "custo_total_calculado_tickets" para a loja é o custo do item + desbloqueio
            results["custo_total_calculado_tickets"] = cost_info.get('total_cost_tickets', float('inf'))
            results["custo_item_base_ticket"] = cost_info.get('item_cost_original') # Custo base do item de ticket
        else:
            # Para itens NÃO-TICKET, a loja não deve projetar "dias para obter" com base em tickets para o item em si.
            # O custo_total_calculado_tickets (para o item) permanece float('inf').
            # O custo_item_base_ticket permanece None.
            # No entanto, o custo_desbloqueio_tickets ainda é relevante e já foi setado.
            results["custo_total_calculado_tickets"] = float('inf') 
            results["custo_item_base_ticket"] = None
            # Se você quisesse mostrar "dias para desbloquear o tier" para um item não-ticket,
            # você poderia usar results["custo_desbloqueio_tickets"] para calcular os dias,
            # mas a UI precisaria ser clara sobre o que esses "dias" significam.
            # Por enquanto, a loja foca em "dias para obter o item de ticket".

        if results["custo_total_calculado_tickets"] != float('inf') and rate > 0:
            results["dias_projetados"] = analysis_module.projetar_dias_para_item(results["custo_total_calculado_tickets"], rate)
        else:
            results["dias_projetados"] = float('inf')

        logger.debug(f"Projeção Loja para '{item_name}' (Moeda: {results['item_currency_original']}): "
                     f"CustoTotalTickets={results['custo_total_calculado_tickets']}, "
                     f"DiasProjetados={results['dias_projetados']}, "
                     f"CustoDesbloqueioTickets={results['custo_desbloqueio_tickets']}")

    except Exception as e:
        logger.exception(f"Erro no cálculo da projeção (loja) para {item_name}: {e}")
    return results

# --->: GET_CHORES_HISTORICAL_ANALYSIS_RESULTS
def get_chores_historical_analysis_results(farm_id: str, bonus_names: List[str], db_utils: Any, analysis_module: Any, config_module: Any, logger: Any, datetime_cls: Any) -> Dict[str, Any]:
    # ... (código existente, já parece eficiente) ...
    results = {'status': 'ok', 'total_conclusoes': 0, 'total_tokens_estimados': 0, 'total_tokens_base': 0, 'periodo_analisado': "N/A", 'dias_analisados': 0, 'dados_completos': False}
    try:
        first_date, last_date = db_utils.get_first_and_last_snapshot_date(int(farm_id)) #
        if first_date and last_date:
            analysis_output = analysis_module.calcular_estimativa_token_chores(farm_id, first_date, last_date, first_date, bonus_names, db_utils, analysis_module, config_module, logger) #
            if analysis_output: results.update(analysis_output)
            else: results.update({'status': 'erro_analise_chores', 'mensagem': "Falha na análise de chores."})
            if 'erro' not in results and results.get('status') not in ['erro_analise_chores', 'erro_calculo_base']:
                try:
                    dt_start = datetime_cls.strptime(first_date, '%Y-%m-%d'); dt_end = datetime_cls.strptime(last_date, '%Y-%m-%d')
                    results['dias_analisados'] = (dt_end - dt_start).days + 1
                    results['periodo_analisado'] = f"{dt_start.strftime('%d/%m/%Y')} a {dt_end.strftime('%d/%m/%Y')}"
                    results['dados_completos'] = True
                except ValueError: results['periodo_analisado'] = f"{first_date} a {last_date}"
        else: results.update({'status': 'sem_historico', 'mensagem': "Sem histórico para análise de chores."})
    except ValueError: results.update({'erro': "Farm ID inválido."})
    except Exception as e: logger.exception(f"Erro na análise histórica de chores para Farm {farm_id}: {e}"); results.update({'erro': "Falha no cálculo do histórico de chores."})
    return results