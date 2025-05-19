$(document).ready(function() {

    // --- Variável Global para Itens Marcados ---
    let markedUnlockItems = {};

    // --- Manipulação da Visibilidade da Loja Sazonal ---
    $('#analysisTabs button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
        if (e.target.id === 'shop-tab') {
            $('#results-area-shop').removeClass('d-none');
        } else {
            $('#results-area-shop').addClass('d-none');
        }
    });
    // --- Fim Manipulação Visibilidade Loja ---
    
    // --- Bloco Inicial: Formulário Principal e Tooltips Estáticos ---
    const farmForm = $('#farm-form');
    const loadingIndicator = $('#loading-indicator');
    const submitButton = farmForm.find('button[type="submit"]');
    const originalButtonHTML = submitButton.html();

    // Inicializa tooltips que já existem na página ao carregar
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    if (farmForm.length) {
        farmForm.on('submit', function() {
            if (loadingIndicator.length) { loadingIndicator.find('p').text('Buscando dados...'); loadingIndicator.show(); }
            if (submitButton.length) { submitButton.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Buscando...'); }
        });
    }
    if (submitButton.length) { submitButton.prop('disabled', false).html(originalButtonHTML); }
    // --- Fim Bloco Inicial ---

    // --- Handler Erro Imagem (Placeholder) ---
    $('.shop-item-image').each(function() {
        const $img = $(this);
        const placeholderSrc = $img.data('placeholder-src');
        const initialSrc = $img.attr('src');
        const altText = $img.attr('alt');
        const showPlaceholderOnError = function() {
            $img.off('error'); // Previne loop
            if (placeholderSrc && $img.attr('src') !== placeholderSrc) {
                $img.attr('src', placeholderSrc); $img.attr('alt', altText + ' (imagem não encontrada)');
            } else { $img.attr('alt', altText + ' (placeholder indisponível ou já em uso)'); }
        };
        $img.on('error', showPlaceholderOnError);
    });
    // --- FIM Handler Erro Imagem ---

    // --- Handler Checkbox: Marcar/Desmarcar Itens ---
    $(document).on('change', '#results-area-shop .unlock-item-marker', function() { // MODIFICADO
        const checkbox = $(this);
        const itemName = checkbox.data('item-name');
        const isChecked = checkbox.prop('checked');
        const $itemCard = checkbox.closest('.item-card');

        if (isChecked) {
            $itemCard.addClass('marked-for-unlock');
            markedUnlockItems[itemName] = true;
        } else {
            $itemCard.removeClass('marked-for-unlock');
            delete markedUnlockItems[itemName];
        }
        console.log("Itens Marcados Atualizados:", markedUnlockItems); // Log do estado atual
    });

    // --- Handler Click Checkbox: Impedir Propagação ---
    $(document).on('click', '#results-area-shop .unlock-item-marker', function(event) { // MODIFICADO
        event.stopPropagation(); // Impede que o clique no checkbox ative o clique do card
    });


    // --- Handler Click Item da Loja: Calcular Projeção e Detalhes ---
    $(document).on('click', '#results-area-shop .item-selectable', function(event) {
        event.preventDefault(); // Apenas para itens com '.item-selectable' (tickets)

        const $itemCard = $(this);
        const itemName = $itemCard.data('item-name');
        const farmId = $('#results-area h2 span.badge, #results-area-shop h2 span.badge').text().replace('ID:', '').trim();
        
        // --- Reset Visual ---
        $('.item-selectable').removeClass('border-primary shadow unlock-path-item').addClass('border-success');
        const resultsArea = $('#projection-results-area');
        const detailsArea = $('#calculation-details-area');
        const simulatorSection = $('#simulator-section');
        resultsArea.html('<p class="text-center"><span class="spinner-border spinner-border-sm"></span> Calculando...</p>');
        detailsArea.empty();    // Limpa detalhes antigos
        simulatorSection.hide(); // Esconde simulador

        if (itemName && farmId) {
            const markedItemsList = Object.keys(markedUnlockItems);

            // <<< NOVO: Pega a taxa histórica do data-attribute >>>
            let historicalRateData = $('#historical-daily-rate-info').data('historical-rate');
            let historicalRateNum = null;

            if (historicalRateData !== "" && historicalRateData !== undefined) {
                let parsedRate = parseFloat(historicalRateData);
                if (!isNaN(parsedRate) && parsedRate > 0) {
                    historicalRateNum = parsedRate;
                }
            }
            // <<< FIM NOVO >>>

            console.log(`Enviando AJAX Proj.: Item=${itemName}, Farm=${farmId}, Marcados:`, markedItemsList, `Taxa Histórica (do data-attr): ${historicalRateData}, Usada se válida: ${historicalRateNum}`);

            // Constrói o payload do AJAX
            let ajaxData = {
                item_name: itemName,
                farm_id: farmId,
                marked_items: markedItemsList
            };

            // <<< NOVO: Adiciona historical_rate ao payload AJAX se existir e for válido >>>
            if (historicalRateNum !== null) {
                ajaxData.historical_rate = historicalRateNum;
                console.log("Taxa histórica numérica válida encontrada e será enviada:", historicalRateNum);
            } else {
                console.log("Nenhuma taxa histórica numérica válida encontrada no data-attribute. Não será enviada.");
            }
            // <<< FIM NOVO >>>

             $.ajax({
                url: '/calculate_projection',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(ajaxData), // << MODIFICADO para usar o objeto ajaxData
                dataType: 'json',
                success: function(response) {
                    console.log("Resposta AJAX Proj.:", response);
                    if (response.success) {

                        // --- 1. Monta HTML da Projeção Principal ---
                        let resultHtml = `<h6>Resultado para: <strong class="text-success">${response.item_name || '??'}</strong></h6><ul class="list-unstyled small mb-0"><li>Custo Total Estimado <span class="text-muted" data-bs-toggle="tooltip" title="Inclui custo tickets p/ desbloquear (considerando marcados).">(c/ desbloqueio)</span>: <strong>${response.calculated_cost !== null ? response.calculated_cost + ' ' + (response.token_name || 'Tickets') : 'N/A'}</strong></li><li>Dias Estimados para Obter: <strong>`;
                        const remaining_days = response.remaining_season_days;
                        let daysWarning = '';
                        if (remaining_days !== null && response.projected_days !== null && response.projected_days > remaining_days) {
                            daysWarning = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede os ${remaining_days} dias restantes!">⚠️ Excede!</span>`;
                        }
                        if (response.projected_days !== null) { resultHtml += ` ~${response.projected_days} dia(s)${daysWarning} <small class="text-muted d-block">(Taxa: ${response.avg_daily_rate_used?.toFixed(1) || 'N/D'}/dia)</small>`; } else { resultHtml += `Incalculável`; }
                        resultHtml += `</strong></li></ul>`;
                        resultsArea.html(resultHtml);

                        // --- 2. Monta HTML dos Detalhes do Cálculo ---
                        if (response.calculated_cost !== null) {
                            let detailsHtml = `<h6 class="text-muted">Detalhes do Cálculo:</h6><ul class="list-unstyled small mb-0">`;
                            if (response.base_item_cost !== null) { detailsHtml += `<li>Custo Base: <strong>${response.base_item_cost} <span class="currency-ticket">${response.token_name || ''}</span></strong></li>`; }
                            let unlockCostDisplay = response.calculated_unlock_cost !== null ? response.calculated_unlock_cost : 0;
                            detailsHtml += `<li>Custo Desbloqueio: <strong>${unlockCostDisplay} <span class="currency-ticket">${response.token_name || ''}</span></strong></li>`;
                            const pathItems = response.unlock_path_items_details || [];
                            if (pathItems.length > 0) {
                                let firstTier = pathItems[0]?.tier || '?'; let lastTier = pathItems[pathItems.length - 1]?.tier || '?';
                                detailsHtml += `<li class="mt-2">Itens no Caminho (T${firstTier}-T${lastTier}):</li><ul class="list-unstyled ms-3">`;
                                pathItems.forEach(function(item) {
                                    detailsHtml += `<li class="py-1">`;
                                    if (item.source === 'marked') { detailsHtml += `<i class="bi bi-check-square-fill text-primary me-1" data-bs-toggle="tooltip" title="Marcado por você."></i> `; } else { detailsHtml += `<i class="bi bi-calculator text-muted me-1" data-bs-toggle="tooltip" title="Calculado (ticket mais barato)."></i> `; }
                                    detailsHtml += `${item.name} <span class="text-muted">(`;
                                    if (item.currency === 'ticket' && item.cost !== null) { detailsHtml += `${item.cost} <span class="currency-ticket">${response.token_name || ''}</span>`; } else if (item.currency === 'sfl') { detailsHtml += `<span class="currency-sfl">Flower</span>`; } else if (item.currency === 'broken_pillar') { detailsHtml += `<span class="currency-broken_pillar">Pillar</span>`; } else if (item.currency) { detailsHtml += `${item.currency}`; } else { detailsHtml += `?`; }
                                    detailsHtml += `)</span></li>`;
                                });
                                detailsHtml += `</ul>`;
                            } else if (unlockCostDisplay === 0) { detailsHtml += `<li class="mt-2 text-muted"><em>Item de Tier 1 (sem desbloqueio).</em></li>`; }
                            detailsHtml += `</ul>`;
                            detailsArea.html(detailsHtml);
                        } else { detailsArea.empty(); }

                        // --- 3. Inicializa TODOS os Tooltips Dinâmicos (Resultados + Detalhes) ---
                        // REATIVADO E UNIFICADO
                        $('#projection-results-area [data-bs-toggle="tooltip"], #calculation-details-area [data-bs-toggle="tooltip"]').each(function() {
                             if (!bootstrap.Tooltip.getInstance(this)) { // Evita reinicializar
                                 try { new bootstrap.Tooltip(this); } catch(e){ console.error("Erro ao inicializar tooltip dinâmico:", e, this); }
                             }
                        });
                        // --- Fim Inicializa Tooltips ---

                        // --- 4. Destaque do Caminho de Desbloqueio ---
                        const unlockItems = response.unlock_path_items || [];
                        $('.item-selectable.unlock-path-item').removeClass('unlock-path-item'); // Limpa anteriores
                        if (unlockItems.length > 0) {
                            // console.log("Itens de desbloqueio para destacar:", unlockItems); // Log opcional
                            unlockItems.forEach(function(unlockItemName) {
                                $('#results-area-shop .item-selectable[data-item-name="' + unlockItemName + '"]') // MODIFICADO
                                    .addClass('unlock-path-item')
                                    .removeClass('border-success');
                            });
                        }
                        // --- Fim Destaque Caminho ---

                        // --- 5. Destaque Principal (Item Clicado) ---
                        $itemCard.removeClass('border-success unlock-path-item').addClass('border-primary shadow');

                        // --- 6. Mostra e Prepara Simulador ---
                        simulatorSection.data('current-item', response.item_name);
                        simulatorSection.data('current-cost', response.calculated_cost !== Infinity ? response.calculated_cost : null);
                        simulatorSection.show();
                        $('#simulation-results-area').html(''); // Limpa resultado anterior
                        $('#simulated-rate-input').val('');     // Limpa input anterior

                    } else { // Erro retornado pelo backend
                        resultsArea.html(`<p class="text-danger small">Erro: ${response.error || 'Falha ao calcular.'}</p>`);
                        detailsArea.empty();
                        simulatorSection.hide();
                    }
                }, // Fim Success AJAX Projeção
                error: function(jqXHR, textStatus, errorThrown) { // Erro de conexão/servidor
                    console.error("Erro AJAX Projeção:", textStatus, errorThrown);
                    resultsArea.html('<p class="text-danger small">Erro de conexão ao calcular.</p>');
                    detailsArea.empty();
                    simulatorSection.hide();
                }
            }); // Fim AJAX
        } else { 
            console.warn("ItemName ou FarmID faltando. Cálculo de projeção não acionado.");
            resultsArea.html('<p class="text-warning small">Informações insuficientes para calcular (item ou ID da fazenda faltando).</p>');
        }
    }); // Fim .item-selectable click


    // --- Handler para o Botão Simular ---
    $(document).on('click', '#simulate-button', function() {
        console.log("Botão Simular Clicado!");
        // --- Pega Dados ---
        const simulatedRate = $('#simulated-rate-input').val();
        const currentItem = $('#simulator-section').data('current-item');
        const currentCost = $('#simulator-section').data('current-cost');
        const farmId = $('#results-area h2 span.badge, #results-area-shop h2 span.badge').text().replace('ID:', '').trim();
        const simulationResultsArea = $('#simulation-results-area');
        const tokenName = $('.currency-ticket').first().text() || 'Tickets';

        // --- Validações ---
        if (!currentItem || currentCost === null || currentCost === undefined) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Selecione um item válido primeiro.</p>'); return;
        }
        const rateNum = parseFloat(simulatedRate);
        if (isNaN(rateNum) || rateNum <= 0) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Insira taxa diária válida (> 0).</p>'); return;
        }
        // --- Fim Validações ---

        simulationResultsArea.html('<span class="spinner-border spinner-border-sm text-warning"></span> Recalculando...');
        console.log(`Enviando AJAX Simulação: ${currentItem}, Taxa: ${rateNum}`);

         $.ajax({
               url: '/calculate_projection',
               type: 'POST',
               contentType: 'application/json',
               data: JSON.stringify({ item_name: currentItem, farm_id: farmId, simulated_rate: rateNum }),
               dataType: 'json',
               success: function(response) {
                   console.log("Resposta AJAX Simulação:", response);
                   if (response.success && response.is_simulation) {
                       // --- Lógica Aviso Tempo Dinâmico (Simulação) ---
                       const remaining_days_sim = response.remaining_season_days;
                       let daysWarningSim = '';
                       if (remaining_days_sim !== null && response.projected_days !== null && response.projected_days > remaining_days_sim) {
                           daysWarningSim = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede ${remaining_days_sim} dias restantes!">⚠️ Excede!</span>`;
                       }

                       // Monta HTML resultado simulação (com item, taxa colorida e aviso)
                       let simResultHtml = `Para <strong>${currentItem}</strong>, com taxa de <strong>${response.avg_daily_rate_used.toFixed(1)}</strong> <span class="currency-ticket">${response.token_name || 'Tickets'}</span>/dia: `;
                       if (response.projected_days !== null) { simResultHtml += ` <strong>~${response.projected_days} dia(s)${daysWarningSim}</strong>`; } else { simResultHtml += ` <strong>Incalculável</strong>`; }

                       simulationResultsArea.html(simResultHtml).removeClass('text-muted').addClass('text-dark');

                       // --- Inicializa Tooltip do Aviso (Simulação) ---
                       $('#simulation-results-area [data-bs-toggle="tooltip"]').each(function() {
                           if (!bootstrap.Tooltip.getInstance(this)) { try { new bootstrap.Tooltip(this); } catch(e){ console.error("Erro tooltip sim:", e); } }
                       });

                   } else {
                       simulationResultsArea.html(`<span class="text-danger small">Erro: ${response.error || 'Falha sim.'}</span>`);
                   }
               },
               error: function(jqXHR, textStatus, errorThrown) {
                    console.error("Erro AJAX Simulação:", textStatus, errorThrown);
                    simulationResultsArea.html('<span class="text-danger small">Erro de conexão.</span>');
               }
           }); // Fim AJAX Simulação
    }); // Fim #simulate-button click
    // --- FIM Handler Botão Simular ---

    // --- Armazenar dados do calendário ideal inicial (se disponível) ---
    let initialIdealCalendarData = null;
    let initialSimBuffPriority = null;
    let initialConfigData = null;

    // Tenta pegar os dados iniciais embutidos pelo Jinja (se a tabela foi renderizada no servidor)
    // Isso assume que você tem uma forma de passar 'potential_calendar', 'sim_buff_item_purchase_priority'
    // e 'config' para o JavaScript quando a página é carregada inicialmente.
    // Uma forma comum é embutir como JSON em um script tag.
    // Por agora, vamos assumir que a função renderPotentialCalendarTable pode ser chamada
    // com dados que já estão "globalmente" disponíveis no JS após o carregamento da página,
    // ou que o backend sempre retorna os dados completos.
    // Se o #potentialCalendarTableContainer já tem conteúdo, podemos tentar extrair ou
    // idealmente, o backend deveria fornecer uma forma de obter o "ideal" via AJAX também,
    // ou embutir os dados iniciais de forma acessível ao JS.
    // Para simplificar aqui, o reset vai limpar a seleção e o usuário pode recalcular sem buffs.
    // Uma implementação mais robusta do reset para o "ideal" exigiria ter os dados ideais no cliente.

    // --- Lógica para Simulador de Impacto de Buffs no Calendário Potencial ---
    $('#recalculateCustomCalendarBtn').on('click', function() {
        const selectedBuffs = [];
        $('.custom-buff-checkbox:checked').each(function() {
            selectedBuffs.push($(this).val());
        });

        const $statusDiv = $('#customCalendarStatus');
        const $calendarContainer = $('#potentialCalendarTableContainer'); // Div que contém a tabela
        const $button = $(this);
        const originalButtonText = $button.html();

        $statusDiv.html('<span class="spinner-border spinner-border-sm text-primary" role="status" aria-hidden="true"></span> Recalculando, aguarde...');
        $button.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processando...');

        console.log("Recalculando calendário com buffs selecionados:", selectedBuffs);

        $.ajax({
            url: '/simulate_custom_calendar',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ selected_buffs: selectedBuffs }),
            dataType: 'json',
            success: function(response) {
                $button.prop('disabled', false).html(originalButtonText);
                if (response.success && response.potential_calendar) {
                    $statusDiv.html('<span class="text-success"><i class="bi bi-check-circle-fill"></i> Calendário recalculado com sucesso!</span>');
                    renderPotentialCalendarTable(response.potential_calendar, response.sim_buff_item_purchase_priority, response.config);
                    // Re-inicializar tooltips na tabela atualizada
                    $('#potentialCalendarTableContainer [data-bs-toggle="tooltip"]').each(function() {
                        if (bootstrap.Tooltip.getInstance(this)) {
                            bootstrap.Tooltip.getInstance(this).dispose(); // Remove o antigo para evitar duplicação
                        }
                        new bootstrap.Tooltip(this);
                    });
                } else {
                    $statusDiv.html(`<span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Erro: ${response.error || 'Falha ao recalcular.'}</span>`);
                     // Limpa a tabela em caso de erro na geração dos dados para não mostrar dados antigos/inconsistentes
                    $('#potentialCalendarTableContainer').find('table tbody').empty().append('<tr><td colspan="100%" class="text-center text-danger">Falha ao carregar dados do calendário customizado.</td></tr>');
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                $button.prop('disabled', false).html(originalButtonText);
                $statusDiv.html('<span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Erro de conexão ao recalcular.</span>');
                console.error("Erro AJAX ao recalcular calendário:", textStatus, errorThrown);
                 $('#potentialCalendarTableContainer').find('table tbody').empty().append('<tr><td colspan="100%" class="text-center text-danger">Erro de comunicação ao carregar dados.</td></tr>');
            }
        });
    });

    // --- Lógica para o Botão "Voltar à Simulação Ideal" ---
    $('#resetToIdealCalendarBtn').on('click', function() {
        const $statusDiv = $('#customCalendarStatus');
        const $button = $(this); // O botão de reset
        const originalButtonText = $button.html();

        // 1. Limpar checkboxes selecionados
        $('.custom-buff-checkbox:checked').prop('checked', false);
        $statusDiv.html('<span class="text-info"><i class="bi bi-info-circle-fill"></i> Checkboxes limpos. Clique em "Recalcular" para ver a simulação sem buffs ou selecione novos.</span>');

        // 2. Idealmente, aqui recarregaríamos a tabela com os dados da simulação ideal.
        //    Como não temos os dados ideais armazenados no cliente de forma simples neste momento,
        //    a ação mais direta é limpar os checkboxes e instruir o usuário.
        //    Se `initialIdealCalendarData` estivesse populado, faríamos:
        //    if (initialIdealCalendarData && initialSimBuffPriority && initialConfigData) {
        //        renderPotentialCalendarTable(initialIdealCalendarData, initialSimBuffPriority, initialConfigData);
        //        $statusDiv.html('<span class="text-success"><i class="bi bi-check-circle-fill"></i> Calendário restaurado para a simulação ideal!</span>');
        //    } else {
        //        $statusDiv.html('<span class="text-warning"><i class="bi bi-exclamation-triangle-fill"></i> Dados da simulação ideal não encontrados no cliente. Por favor, recarregue a página ou recalcule sem buffs.</span>');
        //    }
        //    Por enquanto, a mensagem acima já orienta o usuário.
        console.log("Botão Reset clicado. Checkboxes limpos.");
    });

    // Função para renderizar/atualizar a tabela do calendário potencial
    function renderPotentialCalendarTable(calendarData, buffPriorityList, configData) {
        const $tableBody = $('#potentialCalendarTableContainer').find('table tbody');
        $tableBody.empty(); 

        if (!calendarData || calendarData.length === 0) {
            $tableBody.append('<tr><td colspan="100%" class="text-center text-muted">Nenhum dado para exibir no calendário customizado.</td></tr>');
            return;
        }

        calendarData.forEach(function(day_data) {
            let rowHtml = `<tr class="week-${day_data.game_week_id % 2 === 0 ? 'even' : 'odd'} ${day_data.purchases_today.length > 0 ? 'highlight-purchase-day fw-bold' : ''}">`;
            rowHtml += `<td class="calendar-date-col">${day_data.date_display}</td>`;
            rowHtml += `<td>${day_data.day_of_week_str}</td>`;
            rowHtml += `<td>${day_data.day_in_season}</td>`;
            rowHtml += `<td>${parseFloat(day_data.balance_start_day).toFixed(0)}</td>`;
            rowHtml += `<td>${day_data.gains_chest > 0 ? parseFloat(day_data.gains_chest).toFixed(0) : '-'}</td>`;
            
            let deliveriesBaseHtml = day_data.gains_deliveries_base > 0 ? parseFloat(day_data.gains_deliveries_base).toFixed(0) : '-';
            if (day_data.is_double_delivery_day) {
                deliveriesBaseHtml += ` <span class="badge bg-danger-subtle text-danger-emphasis rounded-pill ms-1" title="Estimativa de Entregas em Dobro neste dia!">2x</span>`;
            }
            rowHtml += `<td>${deliveriesBaseHtml}</td>`;

            rowHtml += `<td>${day_data.gains_chores_base > 0 ? parseFloat(day_data.gains_chores_base).toFixed(0) : '-'}</td>`;
            rowHtml += `<td>${day_data.gains_megaboard_base > 0 ? parseFloat(day_data.gains_megaboard_base).toFixed(0) : '-'}</td>`;
            rowHtml += `<td>${day_data.gains_animals_base > 0 ? parseFloat(day_data.gains_animals_base).toFixed(0) : '-'}</td>`;
            rowHtml += `<td>${day_data.gains_megaboard_completion_bonus > 0 ? parseFloat(day_data.gains_megaboard_completion_bonus).toFixed(0) : '-'}</td>`;

            let vipTooltipParts = [];
            if (day_data.gains_deliveries_vip_bonus) vipTooltipParts.push("Entregas: +" + parseFloat(day_data.gains_deliveries_vip_bonus).toFixed(0));
            if (day_data.gains_chores_vip_bonus) vipTooltipParts.push("Chores: +" + parseFloat(day_data.gains_chores_vip_bonus).toFixed(0));
            let vipTooltipAttr = vipTooltipParts.length > 0 ? `data-bs-toggle="tooltip" data-bs-placement="top" title="${vipTooltipParts.join('; ')}"` : "";
            rowHtml += `<td ${vipTooltipAttr}>${day_data.gains_vip_total_bonus > 0 ? parseFloat(day_data.gains_vip_total_bonus).toFixed(0) : '-'}</td>`;

            buffPriorityList.forEach(function(buff_item_name) {
                const total_bonus_for_item_today = day_data.item_specific_bonus_totals[buff_item_name] || 0;
                const item_bonus_details_today = day_data.gains_item_bonuses_detailed[buff_item_name] || {};
                let itemTooltipParts = [];
                if (item_bonus_details_today.deliveries) itemTooltipParts.push("Entregas: +" + parseFloat(item_bonus_details_today.deliveries).toFixed(0));
                if (item_bonus_details_today.chores) itemTooltipParts.push("Chores: +" + parseFloat(item_bonus_details_today.chores).toFixed(0));
                if (item_bonus_details_today.megaboard_bounties) itemTooltipParts.push("B.Mega: +" + parseFloat(item_bonus_details_today.megaboard_bounties).toFixed(0));
                if (item_bonus_details_today.animal_bounties) itemTooltipParts.push("B.Anim: +" + parseFloat(item_bonus_details_today.animal_bounties).toFixed(0));
                let itemTooltipAttr = itemTooltipParts.length > 0 ? `data-bs-toggle="tooltip" data-bs-placement="top" title="${itemTooltipParts.join('; ')}"` : "";
                rowHtml += `<td ${itemTooltipAttr}>${total_bonus_for_item_today > 0 ? parseFloat(total_bonus_for_item_today).toFixed(0) : '-'}</td>`;
            });

            rowHtml += `<td class="fw-bold">${parseFloat(day_data.total_gains_today).toFixed(0)}</td>`;
            
            let purchasesHtml = '';
            day_data.purchases_today.forEach(function(purchase) {
                let badgeClass = 'bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle';
                if (purchase.type === 'buff_item_sfl') badgeClass = 'bg-success-subtle text-success-emphasis border border-success-subtle';
                else if (purchase.type === 'buff_item_token') badgeClass = 'bg-info-subtle text-info-emphasis border border-info-subtle';
                else if (purchase.type && purchase.type.includes('unlock')) badgeClass = 'bg-warning-subtle text-warning-emphasis border border-warning-subtle';
                purchasesHtml += `<span class="badge ${badgeClass} me-1 rounded-pill d-block mb-1">${purchase.name}</span>`;
            });
            rowHtml += `<td class="calendar-purchases-col">${purchasesHtml}</td>`;

            let costsHtml = '';
            day_data.purchases_today.forEach(function(purchase) {
                let currencySymbol = '';
                if (purchase.type === 'buff_item_sfl') currencySymbol = ' <span class="currency-sfl" style="font-size: 0.8em;">Flower</span>';
                if (purchase.cost !== undefined && (purchase.type === 'buff_item_token' || (purchase.type && purchase.type.includes('unlock')) || purchase.type === 'buff_item_sfl')) {
                     costsHtml += `<span class="text-danger d-block mb-1">(-${parseFloat(purchase.cost).toFixed(0)}${currencySymbol})</span>`;
                }
            });
            rowHtml += `<td>${costsHtml}</td>`;

            rowHtml += `<td class="fw-bold">${parseFloat(day_data.balance_end_day).toFixed(0)}</td>`;
            rowHtml += `<td class="calendar-buffs-col small">${day_data.active_buffs_str ? day_data.active_buffs_str.replace(/,/g, ",\n") : '-'}</td>`;
            rowHtml += `</tr>`;
            $tableBody.append(rowHtml);
        });
    }
    // --- Fim Lógica Simulador de Impacto de Buffs ---

}); // Fim $(document).ready geral


// --- Lógica para o Botão Voltar ao Topo ---
document.addEventListener('DOMContentLoaded', function() {
    var scrollTopButton = document.getElementById("scrollTopBtn");

    if (scrollTopButton) { // Verifica se o botão existe na página
        window.onscroll = function() {
            scrollFunction();
        };

        function scrollFunction() {
            if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
                scrollTopButton.style.display = "flex"; // Alterado de "block" para "flex"
            } else if (scrollTopButton.style.display !== "none") { // Evita redefinir se já estiver none
                scrollTopButton.style.display = "none";
            }
        }
    }
});

// Esta função pode ser global, pois é chamada pelo onclick no HTML
function scrollToTop() {
  window.scrollTo({top: 0, behavior: 'smooth'});
}
