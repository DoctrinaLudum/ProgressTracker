import datetime
from typing import Any, Dict, Optional

import bumpkin_utils


# ---> FUNÇÃO AUXILIAR PARA DETERMINAR TIPO DE ATIVIDADE DA BOUNTY <---
def get_bounty_activity_type(bounty_data: Dict[str, Any], config_module: Any, logger: Any) -> Optional[str]:
    """
    Determina o 'activity_type' para uma bounty com base em seu nome (item requisitado)
    e nas configurações e estrutura da recompensa.

    Args:
        bounty_data: Dicionário contendo os dados da bounty.
        config_module: O módulo 'config' importado.
        logger: Instância do logger.

    Returns:
        Uma string com o activity_type (ex: "animal_bounties", "generic_mega_board_bounties") 
        ou None se não categorizado para aplicação de bônus.
    """
    bounty_item_name = bounty_data.get("name")
    if not bounty_item_name:
        logger.debug(f"Bounty sem nome (item requisitado) não pode ser classificada para bônus: {bounty_data.get('id', 'N/A')}")
        return None

    # 1. Verificar se é uma bounty de animal que deve ser tratada com 'item_dict'
    if bounty_item_name in getattr(config_module, 'ANIMAL_NAMES_HEURISTIC', []):
        animal_rules = config_module.ACTIVITY_BONUS_RULES.get("animal_bounties", {})
        item_container = animal_rules.get("item_container_field")
        if animal_rules.get("reward_type") == "item_dict" and \
           item_container and item_container in bounty_data and \
           isinstance(bounty_data.get(item_container), dict):
            logger.debug(f"Bounty '{bounty_item_name}' classificada como 'animal_bounties' (item_dict).")
            return "animal_bounties"

    # 2. Verificar se é uma bounty genérica do Mega Board (que dá seasonalTicketReward)
    generic_rules = config_module.ACTIVITY_BONUS_RULES.get("generic_mega_board_bounties", {})
    #    Com a mudança no config, agora generic_mega_board_bounties também usa item_dict
    item_container_generic = generic_rules.get("item_container_field")
    if generic_rules.get("reward_type") == "item_dict" and \
       item_container_generic and item_container_generic in bounty_data and \
       isinstance(bounty_data.get(item_container_generic), dict) and \
       getattr(config_module, 'SEASONAL_TOKEN_NAME', 'Geniseed') in bounty_data[item_container_generic]:
        logger.debug(f"Bounty '{bounty_item_name}' classificada como 'generic_mega_board_bounties' (item_dict com Geniseed).")
        return "generic_mega_board_bounties"

    logger.debug(f"Bounty '{bounty_item_name}' não correspondeu a nenhuma regra de bônus conhecida ('animal_bounties' com item_dict ou 'generic_mega_board_bounties' com numeric_token).")
    return None

# ---> PROCESSAMENTO DOS DADOS DA FAZENDA <---
def process_farm_data_on_submit(
        farm_id_submitted,
        api_response_data, 
        current_config, 
        current_analysis, 
        current_db_utils, 
        gerar_bumpkin_url_func, 
        logger):
    """
    Processa os dados da fazenda obtidos da API, calcula bônus,
    processa NPCs, atualiza estado no DB e cria snapshots.
    Retorna um dicionário com dados para o template e mensagens de erro.
    """
    processed_data = {
        "farm_data_display": None,
        "npc_completion_rates": {},
        "live_completions": 0,
        "live_tokens": 0,
        "live_cost_sfl": 0.0,
        "total_delivery_bonus": 0,
        "active_bonus_details": {}, # Detalhes dos bônus ativos (ex: {'vip': True, 'Flower Mask': True})
        "bounties_data": {},
        "chores_data": [], # Nova estrutura para chores
        "bumpkin_image_url": None,
        "processing_error_message": None
    }
    try:
        farm_data_display = api_response_data['farm']
        processed_data["farm_data_display"] = farm_data_display
        npc_data_completo = farm_data_display.get('npcs', {})
        delivery_orders_from_api = farm_data_display.get('delivery', {}).get('orders', [])
        bumpkin_data_from_api = farm_data_display.get("bumpkin")
        if bumpkin_data_from_api and isinstance(bumpkin_data_from_api, dict):
            equipped_items = bumpkin_data_from_api.get("equipped")
            if equipped_items and isinstance(equipped_items, dict):
                processed_data["bumpkin_image_url"] = gerar_bumpkin_url_func(equipped_items)
                logger.info(f"URL da imagem do Bumpkin gerada para {farm_id_submitted}: {processed_data['bumpkin_image_url']}")
            else:
                logger.warning(f"Dados de 'equipped' não encontrados ou em formato incorreto para Farm ID {farm_id_submitted}.")
        else:
            logger.warning(f"Dados de 'bumpkin' não encontrados ou em formato incorreto para Farm ID {farm_id_submitted}.")

        # --- Cálculo de Bônus de Entrega (já existente) ---
        try:
            bonus_info = current_analysis.calculate_delivery_bonus(farm_data_display, current_config.SEASONAL_DELIVERY_BUFFS)
            processed_data["total_delivery_bonus"] = bonus_info.get('total_bonus', 0)
            processed_data["active_bonus_details"] = bonus_info.get('details', {})
            logger.info(f"Bônus de entrega calculado para Farm {farm_id_submitted}: +{processed_data['total_delivery_bonus']}")
        except Exception as e_bonus:
            logger.exception(f"Erro ao calcular bônus para Farm {farm_id_submitted}: {e_bonus}")

        # --- Processamento de NPCs e Estado (já existente) ---
        if npc_data_completo:
            npcs_processed_for_state = []
            state_update_failed = False
            prices_now = current_db_utils.get_sfl_world_prices() or {}
            for npc_name in current_config.BASE_DELIVERY_REWARDS:
                npc_info = npc_data_completo.get(npc_name)
                if not isinstance(npc_info, dict):
                    logger.warning(f"Dados do NPC '{npc_name}' não encontrados ou inválidos para Farm {farm_id_submitted}.")
                    continue
                current_delivery_count = npc_info.get('deliveryCount')
                current_skipped_count = npc_info.get('skippedCount', 0)
                if current_delivery_count is not None:
                    total = current_delivery_count + current_skipped_count
                    processed_data["npc_completion_rates"][npc_name] = round((current_delivery_count / total) * 100, 1) if total > 0 else 0.0
                else:
                    processed_data["npc_completion_rates"][npc_name] = 'N/A'
                if current_delivery_count is not None:
                    try:
                        previous_state_data = current_db_utils.get_npc_state(farm_id_submitted, npc_name)
                        if previous_state_data:
                            previous_count = previous_state_data.get('last_delivery_count', 0)
                            if current_delivery_count > previous_count:
                                completions_now = current_delivery_count - previous_count
                                processed_data["live_completions"] += completions_now
                                base_token_reward = current_config.BASE_DELIVERY_REWARDS.get(npc_name, 0)
                                
                                # Calcula recompensa efetiva por entrega (base + bônus aditivo)
                                effective_reward_per_delivery = base_token_reward + processed_data["total_delivery_bonus"]
                                
                                # Aplica multiplicador de "doubleDelivery" se estiver ativo
                                if processed_data["active_bonus_details"].get("is_double_delivery_active"):
                                    effective_reward_per_delivery *= 2
                                    logger.info(f"Evento 'doubleDelivery' ativo. Recompensa por entrega para {npc_name} dobrada para {effective_reward_per_delivery} (Base: {base_token_reward}, Bônus Aditivo: {processed_data['total_delivery_bonus']}).")
                                
                                processed_data["live_tokens"] += completions_now * effective_reward_per_delivery
                                reward_info = npc_info.get('reward', {})
                                if isinstance(reward_info, dict) and not reward_info:
                                     delivery_info = npc_info.get('delivery')
                                     cost_current_delivery = 0.0
                                     if prices_now and delivery_info and isinstance(delivery_info.get('items'), dict):
                                         items_needed = delivery_info.get('items')
                                         if items_needed:
                                             try:
                                                 cost = sum((amount or 0) * prices_now.get(item, 0.0) for item, amount in items_needed.items())
                                                 cost_current_delivery = cost
                                             except Exception as e_cost:
                                                  logger.exception(f"Erro ao calcular custo da entrega de {npc_name} para Farm {farm_id_submitted}: {e_cost}")
                                     processed_data["live_cost_sfl"] += cost_current_delivery
                        update_success = current_db_utils.update_npc_state(
                            farm_id_submitted, npc_name,
                            current_delivery_count, current_skipped_count,
                            npc_info.get('deliveryCompletedAt')
                        )
                        if update_success:
                            npcs_processed_for_state.append(npc_name)
                        else:
                            state_update_failed = True
                            logger.error(f"Falha ao salvar estado para {farm_id_submitted}/{npc_name}")
                    except Exception as e_state:
                        logger.exception(f"Erro ao processar estado/live para {farm_id_submitted}/{npc_name}: {e_state}")
                        state_update_failed = True
            if state_update_failed:
                processed_data["processing_error_message"] = "Atenção: Erro parcial ao salvar estado das entregas."
            elif npcs_processed_for_state:
                logger.info(f"Estado atualizado para NPCs: {', '.join(npcs_processed_for_state)}")
            try:
                current_db_utils.create_snapshot_if_needed(
                    farm_id_submitted, 
                    npc_data_completo, 
                    delivery_orders_from_api)
            except Exception as e_snap:
                logger.exception(f"Erro ao criar snapshot para Farm {farm_id_submitted}: {e_snap}")
                if not processed_data["processing_error_message"]:
                     processed_data["processing_error_message"] = "Aviso: Falha ao registrar snapshot diário."
        else:
            logger.warning(f"Chave 'npcs' vazia/ausente para Farm {farm_id_submitted}. NPCs e snapshot pulados.")
    except KeyError as ke:
        logger.exception(f"KeyError ao processar dados da API para Farm {farm_id_submitted}: Chave {ke} ausente.")
        processed_data["processing_error_message"] = "Erro ao processar dados da fazenda: formato inesperado."
    except Exception as e_proc:
        logger.exception(f"Erro inesperado processando dados da fazenda {farm_id_submitted}: {e_proc}")
        processed_data["processing_error_message"] = "Erro interno ao processar os dados da fazenda."

    # --- Processamento de Bounties (Mega Board) com Aplicação de Bônus ---
    # Estrutura para o template, seguindo BOUNTY_CATEGORY_ORDER de config.py
    categorized_bounties_for_template = {
        "categories": {category: [] for category in current_config.BOUNTY_CATEGORY_ORDER},
        "order": current_config.BOUNTY_CATEGORY_ORDER
    }
    
    active_player_bonus_names = list(processed_data["active_bonus_details"].keys())
    
    # <<< CORREÇÃO: Usar bounties da resposta da API >>>
    # farm_data_display já é api_response_data['farm']
    bounties_object_from_api = processed_data["farm_data_display"].get('bounties')
    raw_bounties_from_api = [] # Inicializa como lista vazia

    if isinstance(bounties_object_from_api, dict):
        raw_bounties_from_api = bounties_object_from_api.get('requests', [])
        if not isinstance(raw_bounties_from_api, list):
            logger.warning(f"A chave 'requests' dentro de 'bounties' não é uma lista para Farm ID {farm_id_submitted}. Dados: {raw_bounties_from_api}")
            raw_bounties_from_api = []
    elif bounties_object_from_api is not None: # Se 'bounties' existe mas não é um dict
        logger.warning(f"Dados de 'bounties' da API não são um dicionário esperado para Farm ID {farm_id_submitted}. Bounties puladas. Dados: {bounties_object_from_api}")
        raw_bounties_from_api = []
    logger.info(f"DEBUG: Raw bounties from API ({len(raw_bounties_from_api)}): {raw_bounties_from_api}")

    if raw_bounties_from_api:
        logger.info(f"Processando {len(raw_bounties_from_api)} bounties (da API) para Farm ID {farm_id_submitted} com bônus.")
        for bounty in raw_bounties_from_api:
            current_bounty = bounty.copy() # Trabalha com uma cópia
            bounty_item_name = current_bounty.get("name")
            logger.info(f"DEBUG: Processing bounty (original): {current_bounty}") # << NOVO LOG

            activity_type = get_bounty_activity_type(current_bounty, current_config, logger)
            logger.info(f"DEBUG: Bounty '{bounty_item_name}' classified as activity_type: {activity_type}") # << NOVO LOG

            if activity_type and activity_type in current_config.ACTIVITY_BONUS_RULES:
                bonus_value = current_analysis.calculate_bonus_for_activity(
                    active_player_bonus_names,
                    activity_type,
                    current_config.SEASONAL_DELIVERY_BUFFS,
                    current_config.ACTIVITY_BONUS_RULES
                )
                if bonus_value > 0:
                    current_bounty = current_analysis.apply_bonus_to_reward(
                        current_bounty,
                        bonus_value,
                        current_config.ACTIVITY_BONUS_RULES[activity_type],
                        current_config.SEASONAL_TOKEN_NAME
                    )
            logger.info(f"DEBUG: Bounty after bonus attempt: {current_bounty}") # << NOVO LOG
            
            # Determinar categoria da bounty para exibição no frontend
            display_category = "Exotic" # Categoria padrão
            if bounty_item_name:
                if bounty_item_name in current_config.FLOWER_BOUNTY_NAMES: display_category = "Flores"
                elif bounty_item_name in current_config.FISH_BOUNTY_NAMES: display_category = "Peixes"
                elif bounty_item_name in current_config.MARK_BOUNTY_NAMES: display_category = "Mark"
                elif bounty_item_name in current_config.OBSIDIAN_BOUNTY_NAMES: display_category = "Obsidiana"
            
            if display_category in categorized_bounties_for_template["categories"]:
                categorized_bounties_for_template["categories"][display_category].append(current_bounty)
            else: # Fallback para Exotic se a categoria não estiver na ordem (improvável com a config atual)
                logger.warning(f"Categoria de display '{display_category}' para bounty '{bounty_item_name}' não está em BOUNTY_CATEGORY_ORDER. Adicionando a 'Exotic'.")
                categorized_bounties_for_template["categories"]["Exotic"].append(current_bounty)
        
        processed_data["bounties_data"] = categorized_bounties_for_template
        logger.info(f"DEBUG: Final categorized bounties for template: {processed_data['bounties_data']}") # << NOVO LOG
    else:
        logger.info(f"Nenhuma bounty encontrada na API para Farm ID {farm_id_submitted} ou a lista de bounties estava vazia.")
        processed_data["bounties_data"] = categorized_bounties_for_template # Envia estrutura vazia

    # ---> Processamento de Chores (Afazeres) ---
    processed_chores_for_template = []
    raw_chores_data_from_api = processed_data["farm_data_display"].get('choreBoard', {}).get('chores', {})

    if isinstance(raw_chores_data_from_api, dict) and raw_chores_data_from_api:
        logger.info(f"Processando {len(raw_chores_data_from_api)} chores para Farm ID {farm_id_submitted} com bônus.")
        for npc_giver_name, chore_details_api in raw_chores_data_from_api.items():
            if not isinstance(chore_details_api, dict):
                logger.warning(f"Detalhes do chore para NPC '{npc_giver_name}' não são um dicionário. Pulando.")
                continue

            # Estrutura de dados para o template
            chore_display_data = {
                "npc_key_for_filename": npc_giver_name,
                "npc_name": npc_giver_name.replace("_", " ").title(),
                "description": chore_details_api.get("name", "Descrição não disponível"),
                "reward_items_original": chore_details_api.get("reward", {}).get("items", {}), # Guardamos o original
                "started_at_timestamp": chore_details_api.get("startedAt"),
                "completed_at_timestamp": chore_details_api.get("completedAt"),
                "is_completed_api": chore_details_api.get("completedAt") is not None,
                "started_at_formatted": None,
                "completed_at_formatted": None,
                "base_seasonal_tickets": 0,
                "final_seasonal_tickets": 0, # Será atualizado com bônus
                "bonus_applied_to_tickets": False,
                "bonus_amount_tickets": 0,
                "other_rewards_formatted": [] # Para SFL, Coins, outros itens
            }

            # Formatar timestamps
            if chore_display_data["started_at_timestamp"]:
                try:
                    dt_started = datetime.fromtimestamp(chore_display_data["started_at_timestamp"] / 1000)
                    chore_display_data["started_at_formatted"] = dt_started.strftime('%d/%m/%y %H:%M')
                except Exception as e_ts_start:
                    logger.error(f"Erro ao formatar started_at para chore de {npc_giver_name}: {e_ts_start}")
                    chore_display_data["started_at_formatted"] = "Data inválida"
            
            if chore_display_data["completed_at_timestamp"]:
                try:
                    dt_completed = datetime.fromtimestamp(chore_display_data["completed_at_timestamp"] / 1000)
                    chore_display_data["completed_at_formatted"] = dt_completed.strftime('%d/%m/%y %H:%M')
                except Exception as e_ts_comp:
                    logger.error(f"Erro ao formatar completed_at para chore de {npc_giver_name}: {e_ts_comp}")
                    chore_display_data["completed_at_formatted"] = "Data inválida"

            # Extrair recompensas
            original_reward_items = chore_display_data["reward_items_original"]
            seasonal_token_key = current_config.SEASONAL_TOKEN_NAME # Ex: "Geniseed"
            token_icon_filename = None
            if current_config.SEASONAL_TOKEN_NAME:
                token_icon_filename = f"images/misc/{current_config.SEASONAL_TOKEN_NAME.lower()}.png"

            
            base_tickets = 0
            if isinstance(original_reward_items.get(seasonal_token_key), (int, float)):
                base_tickets = original_reward_items[seasonal_token_key]
            
            chore_display_data["base_seasonal_tickets"] = base_tickets
            chore_display_data["final_seasonal_tickets"] = base_tickets # Inicializa com o base

            for item_name, amount in original_reward_items.items():
                if item_name != seasonal_token_key:
                    chore_display_data["other_rewards_formatted"].append(f"{amount} {item_name.replace('_', ' ').title()}")

            # Aplicar bônus aos tickets sazonais
            activity_type_chore = "chores"
            # O objeto de recompensa que contém o 'item_container_field' ("items")
            # é o dicionário chore_details_api.get("reward", {})
            chore_reward_object_api = chore_details_api.get("reward", {})
            
            if activity_type_chore in current_config.ACTIVITY_BONUS_RULES and \
               isinstance(chore_reward_object_api.get('items'), dict) and \
               base_tickets > 0:
                
                bonus_value_chore = current_analysis.calculate_bonus_for_activity(
                    active_player_bonus_names,
                    activity_type_chore,
                    current_config.SEASONAL_DELIVERY_BUFFS,
                    current_config.ACTIVITY_BONUS_RULES
                )

                if bonus_value_chore > 0:
                    # Criamos uma cópia do objeto de recompensa para passar para apply_bonus_to_reward
                    # A função apply_bonus_to_reward espera que o objeto passado tenha um campo 'items'
                    # que ela irá modificar.
                    reward_object_for_bonus_application = {
                        "items": original_reward_items.copy() # Passa uma cópia dos itens originais
                    }
                    
                    # apply_bonus_to_reward modificará reward_object_for_bonus_application['items'][seasonal_token_key]
                    # e adicionará chaves como 'applied_bonus_value', 'is_bonus_applied'.
                    modified_reward_details = current_analysis.apply_bonus_to_reward(
                        reward_object_for_bonus_application, # Este objeto agora tem "items" no nível raiz
                        bonus_value_chore,
                        current_config.ACTIVITY_BONUS_RULES[activity_type_chore], # Passa a regra específica para 'chores'
                        seasonal_token_key # Passa o nome do token para que saiba qual item buffar
                    )
                    
                    # Atualizar nossos dados de display com base no que foi modificado
                    if modified_reward_details.get('is_bonus_applied'):
                        chore_display_data["final_seasonal_tickets"] = modified_reward_details.get("items", {}).get(seasonal_token_key, base_tickets)
                        chore_display_data["bonus_applied_to_tickets"] = True
                        # apply_bonus_to_reward adiciona 'applied_bonus_value' ao objeto que ela modifica
                        chore_display_data["bonus_amount_tickets"] = modified_reward_details.get('applied_bonus_value', 0) 
                        logger.info(f"Bônus de +{chore_display_data['bonus_amount_tickets']} aplicado ao chore '{chore_display_data['description']}'. Base: {base_tickets}, Final: {chore_display_data['final_seasonal_tickets']}")
            
            processed_chores_for_template.append(chore_display_data)
        
        processed_data["chores_data"] = processed_chores_for_template
    else:
        logger.info(f"Nenhum chore encontrado para Farm ID {farm_id_submitted} ou dados não disponíveis.")
        processed_data["chores_data"] = []

    # ---> FIM Processamento de Chores com Aplicação de Bônus ---


    return processed_data

# ---> FIM PROCESSAMENTO DOS DADOS DA FAZENDA <---

# ---> ANÁLISE HISTÓRICA DE ENTREGAS (MODIFICADA PARA INCLUIR TAXA MÉDIA) <---
def get_historical_analysis_results(farm_id, total_delivery_bonus_for_analysis, current_db_utils, current_analysis, logger, datetime_cls):
    """
    Realiza a análise histórica de entregas e tokens para um farm_id.
    Retorna um dicionário com os resultados da análise, incluindo o número de dias 
    analisados e a taxa média diária de tokens.
    """
    # Valores padrão para o retorno
    analise_historica_data = {
        'status': 'ok', # Default status
        'total_conclusoes': 0,
        'total_tokens_estimados': 0,
        'total_custo_estimado_sfl': 0.0,
        'detalhes_por_npc': {},
        'dados_completos': False, # Default para indicar se todos os dados foram processados
        'periodo_analisado': "N/A",
        'dias_analisados': 0,
        'taxa_media_diaria_real': 0.0
    }

    try:
        farm_id_int = int(farm_id) 
        primeira_data_str, ultima_data_str = current_db_utils.get_first_and_last_snapshot_date(farm_id_int)
        
        if primeira_data_str and ultima_data_str:
            logger.info(f"Iniciando análise histórica para Farm {farm_id} ({primeira_data_str} a {ultima_data_str}) com Bônus por entrega: +{total_delivery_bonus_for_analysis}")
            
            # Chama a função de análise principal
            resultado_analysis_py = current_analysis.calcular_estimativa_token_deliveries(
                farm_id, primeira_data_str, ultima_data_str, primeira_data_str, total_delivery_bonus_for_analysis
            )

            if resultado_analysis_py:
                # Atualiza analise_historica_data com os resultados, mantendo os defaults se chaves não existirem
                analise_historica_data.update(resultado_analysis_py)
            else:
                logger.warning(f"Função 'calcular_estimativa_token_deliveries' retornou None para Farm {farm_id}.")
                analise_historica_data['status'] = 'erro_analise'
                analise_historica_data['mensagem'] = "Não foi possível gerar os dados da análise histórica."
                # Mantém dados_completos como False e os valores numéricos como 0

            # Prossegue apenas se não houver erro explícito da função de análise
            if 'erro' not in analise_historica_data and analise_historica_data.get('status') != 'erro_analise':
                try:
                    dt_inicio = datetime_cls.strptime(primeira_data_str, '%Y-%m-%d')
                    dt_fim = datetime_cls.strptime(ultima_data_str, '%Y-%m-%d')
                    
                    # Calcula o número de dias no período
                    dias_no_periodo = (dt_fim - dt_inicio).days + 1
                    analise_historica_data['dias_analisados'] = dias_no_periodo
                    
                    periodo_formatado = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"
                    analise_historica_data['periodo_analisado'] = periodo_formatado
                    
                    # Calcula a taxa média diária de tokens
                    total_tokens = analise_historica_data.get('total_tokens_estimados', 0)
                    if dias_no_periodo > 0 and total_tokens is not None: # total_tokens pode ser 0
                        taxa_calculada = round(total_tokens / dias_no_periodo, 2)
                        analise_historica_data['taxa_media_diaria_real'] = taxa_calculada
                        logger.info(f"Farm {farm_id}: Total Tokens={total_tokens}, Dias Analisados={dias_no_periodo}, Taxa Média Diária Real={taxa_calculada}")
                    else:
                        # Mantém taxa_media_diaria_real como 0.0 se não puder calcular
                        logger.warning(f"Farm {farm_id}: Não foi possível calcular taxa média diária (dias_analisados={dias_no_periodo} ou total_tokens={total_tokens} inválido).")
                    
                except ValueError: 
                    analise_historica_data['periodo_analisado'] = f"{primeira_data_str} a {ultima_data_str}" # Fallback
                    # dias_analisados e taxa_media_diaria_real permanecem 0 como default
                    logger.error(f"Erro ao converter datas para análise em Farm {farm_id}. Datas: {primeira_data_str}, {ultima_data_str}")
            # Se 'erro' em analise_historica_data, os defaults de dias e taxa são mantidos
        else: 
            logger.warning(f"Nenhum snapshot encontrado para análise histórica do Farm {farm_id}.")
            analise_historica_data['status'] = 'sem_historico'
            analise_historica_data['mensagem'] = "Nenhum histórico de entregas encontrado para análise."
            # dias_analisados e taxa_media_diaria_real permanecem 0
            
    except ValueError:
         logger.error(f"Farm ID '{farm_id}' inválido para consulta histórica.")
         analise_historica_data['erro'] = "Farm ID inválido para consulta de histórico."
         # dias_analisados e taxa_media_diaria_real permanecem 0
    except Exception as e_analise:
        logger.exception(f"Erro durante busca/análise de snapshots para Farm {farm_id}: {e_analise}")
        analise_historica_data['erro'] = "Falha ao calcular o histórico de entregas."
        # dias_analisados e taxa_media_diaria_real permanecem 0
        
    return analise_historica_data
# ---> FIM ANÁLISE HISTÓRICA DE ENTREGAS <---

# ---> DETERMINAÇÃO DA TAXA DE GANHO DIÁRIO ATIVA <---
def determine_active_daily_rate(simulated_rate_str_from_request, historical_rate_from_request, logger, default_placeholder_rate=10.0):
    """
    Determina a taxa de ganho diário a ser usada para projeções.
    Prioridade: 1. Taxa Simulada, 2. Taxa Histórica, 3. Placeholder.
    Retorna a taxa a ser usada e um booleano indicando se é uma simulação do usuário.
    """
    rate_actually_used = None
    is_user_simulated_rate = False # True apenas se a taxa simulada explícita for usada

    # 1. Tenta usar a taxa simulada (maior prioridade)
    if simulated_rate_str_from_request is not None and simulated_rate_str_from_request != '':
        try:
            parsed_simulated_rate = float(simulated_rate_str_from_request)
            if parsed_simulated_rate > 0:
                rate_actually_used = parsed_simulated_rate
                is_user_simulated_rate = True # É uma simulação explícita do usuário
                logger.info(f"Taxa determinada: Usando taxa SIMULADA explícita: {rate_actually_used:.2f}")
            else:
                logger.warning(f"Taxa simulada fornecida ('{simulated_rate_str_from_request}') não é positiva.")
        except (ValueError, TypeError):
            logger.warning(f"Taxa simulada fornecida ('{simulated_rate_str_from_request}') não é um número válido.")

    # 2. Se não for simulação explícita, tenta usar a taxa histórica passada pelo request
    if rate_actually_used is None and historical_rate_from_request is not None:
        # historical_rate_from_request já deve ser um número (float) se chegou do JS corretamente
        try:
            # Re-validar caso o JS envie algo inesperado, embora já tenha sido parseado no JS
            parsed_historical_rate = float(historical_rate_from_request)
            if parsed_historical_rate > 0:
                rate_actually_used = parsed_historical_rate
                # is_user_simulated_rate permanece False, pois não é uma simulação explícita "E se"
                logger.info(f"Taxa determinada: Usando taxa HISTÓRICA calculada (recebida via request): {rate_actually_used:.2f}")
            else:
                logger.warning(f"Taxa histórica (do request) fornecida ('{historical_rate_from_request}') não é positiva.")
        except (ValueError, TypeError):
            logger.warning(f"Taxa histórica (do request) fornecida ('{historical_rate_from_request}') não é um número válido.")

    # 3. Se nenhuma das anteriores (simulada ou histórica válida) foi usada, recorre ao placeholder default
    if rate_actually_used is None:
        rate_actually_used = default_placeholder_rate
        # is_user_simulated_rate permanece False
        logger.info(f"Taxa determinada: Nenhuma taxa simulada ou histórica válida. Usando taxa PLACEHOLDER/DEFAULT global: {rate_actually_used:.2f}")
        # Poderíamos adicionar uma flag aqui para o frontend saber que é placeholder
        # por exemplo, retornando um terceiro valor: `source_of_rate = 'placeholder'`
        # Mas o frontend já tem o avg_daily_rate_status da carga inicial.

    return rate_actually_used, is_user_simulated_rate
# ---> FIM DETERMINAÇÃO DA TAXA DE GANHO DIÁRIO ATIVA <---

# ---> CÁLCULO DOS DIAS RESTANTES DA TEMPORADA <---
def calculate_remaining_season_days(season_end_date_str_from_config, datetime_cls, logger):
    """
    Calcula os dias restantes na temporada com base na data final fornecida.
    Retorna o número de dias restantes ou None em caso de erro/data não definida.
    """
    days_left = None
    if not season_end_date_str_from_config:
        logger.warning("SEASON_END_DATE não definida. Não é possível calcular dias restantes.")
        return None
    try:
        end_date = datetime_cls.strptime(season_end_date_str_from_config, '%Y-%m-%d').date()
        today = datetime_cls.now().date()
        if end_date >= today:
            days_left = (end_date - today).days
        else:
            days_left = 0
        logger.debug(f"Data final: '{season_end_date_str_from_config}', Hoje: {today}, Dias restantes: {days_left}")
    except (ValueError, TypeError) as e_date:
        logger.error(f"Erro ao parsear SEASON_END_DATE ('{season_end_date_str_from_config}'): {e_date}")
    except Exception as e_general:
        logger.error(f"Erro inesperado ao calcular dias restantes (SEASON_END_DATE='{season_end_date_str_from_config}'): {e_general}")
    return days_left
# ---> FIM CÁLCULO DOS DIAS RESTANTES DA TEMPORADA <---

# ---> CÁLCULO DETALHADO DA PROJEÇÃO DE ITEM <---
def get_projection_calculation_details(item_name_to_calc, all_shop_items, marked_item_names_list, rate_to_use_for_calc, current_analysis, logger):
    """
    Calcula o custo total, itens de desbloqueio e dias projetados para um item.
    Retorna um dicionário com os detalhes do cálculo.
    """
    calculation_results = {
        "custo_total_calculado": float('inf'), "custo_item_base": None,
        "custo_desbloqueio_calculado": float('inf'), "unlock_items_detalhados": [],
        "unlock_items_list": [], "dias_projetados": float('inf')
    }
    try:
        custo_info = current_analysis.calcular_custo_total_item(item_name_to_calc, all_shop_items, marked_item_names_list)
        calculation_results["custo_total_calculado"] = custo_info['total_cost']
        calculation_results["custo_item_base"] = custo_info['item_cost'] 
        calculation_results["custo_desbloqueio_calculado"] = custo_info['unlock_cost']
        calculation_results["unlock_items_detalhados"] = custo_info['unlock_items_details']
        calculation_results["unlock_items_list"] = [item['name'] for item in calculation_results["unlock_items_detalhados"]] 
        if calculation_results["custo_total_calculado"] != float('inf'):
            calculation_results["dias_projetados"] = current_analysis.projetar_dias_para_item(
                calculation_results["custo_total_calculado"], rate_to_use_for_calc
            )
        logger.info(f"Cálculo de projeção para '{item_name_to_calc}': Custo={calculation_results['custo_total_calculado']}, Dias={calculation_results['dias_projetados']}")
    except Exception as e_calc:
        logger.exception(f"Erro no cálculo detalhado da projeção para {item_name_to_calc}: {e_calc}")
    return calculation_results
# ---> FIM CÁLCULO DETALHADO DA PROJEÇÃO DE ITEM <---
