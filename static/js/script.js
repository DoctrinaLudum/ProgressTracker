$(document).ready(function() {

    // --- Variável Global para Itens Marcados ---
    let markedUnlockItems = {};

    // --- Manipulação da Visibilidade da Loja Sazonal ---
    $('#analysisTabs button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
        if (e.target.id === 'shop-tab') {
            $('#results-area-shop').removeClass('d-none');
            // Quando a aba da loja é mostrada, podemos re-inicializar tooltips dentro dela se necessário
            $('#results-area-shop [data-bs-toggle="tooltip"]').each(function() {
                if (!bootstrap.Tooltip.getInstance(this)) {
                    new bootstrap.Tooltip(this);
                }
            });
        } else {
            $('#results-area-shop').addClass('d-none');
        }
    });
    // --- Fim Manipulação Visibilidade Loja ---
    
    // --- Bloco Inicial: Formulário Principal e Tooltips Estáticos ---
    const farmForm = $('#farm-form');
    const submitButton = farmForm.find('button[type="submit"]');
    let originalButtonHTML = ''; 

    if (submitButton.length) {
        originalButtonHTML = submitButton.html(); 
    }

    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    if (farmForm.length) {
        farmForm.on('submit', function(event) { 
            if (submitButton.length) {
                const loadingGifUrl = submitButton.data('loading-gif-url'); 
                if (loadingGifUrl && loadingGifUrl.trim() !== '') { 
                    submitButton.prop('disabled', true).html(
                        '<img src="' + loadingGifUrl + '" alt="Carregando..." style="height: 24px; width: auto; margin-right: 8px; vertical-align: middle;"> Buscando...'
                    );
                } else { 
                    console.warn("URL do GIF de carregamento não encontrada no data-attribute do botão. Usando spinner padrão.");
                    submitButton.prop('disabled', true).html(
                        '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Buscando...'
                    );
                }
            }
        });
    }
    // --- Fim Bloco Inicial ---

    // --- Handler Erro Imagem (Placeholder) ---
    // Garantir que este handler funcione para imagens adicionadas dinamicamente também, se necessário.
    // Usar $(document).on('error', '.shop-item-image', function() { ... }); pode ser mais robusto
    // se as imagens da loja forem carregadas via AJAX, mas como é include, .each() no ready é ok.
    $('.shop-item-image').each(function() {
        const $img = $(this);
        const placeholderSrc = $img.data('placeholder-src');
        // const initialSrc = $img.attr('src'); // Não usado
        const altText = $img.attr('alt');
        const showPlaceholderOnError = function() {
            $img.off('error'); 
            if (placeholderSrc && $img.attr('src') !== placeholderSrc) {
                $img.attr('src', placeholderSrc); $img.attr('alt', altText + ' (imagem não encontrada)');
            } else { $img.attr('alt', altText + ' (placeholder indisponível ou já em uso)'); }
        };
        $img.on('error', showPlaceholderOnError);
    });
    // --- FIM Handler Erro Imagem ---

    // --- Handler Checkbox: Marcar/Desmarcar Itens ---
    $(document).on('change', '#results-area-shop .unlock-item-marker', function() {
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
        console.log("Itens Marcados Atualizados:", markedUnlockItems);
    });

    // --- Handler Click Checkbox: Impedir Propagação ---
    $(document).on('click', '#results-area-shop .unlock-item-marker', function(event) {
        event.stopPropagation();
    });

    // --- Handler Click Item da Loja: Calcular Projeção e Detalhes ---
    $(document).on('click', '#results-area-shop .item-selectable', function(event) {
        event.preventDefault();

        const $itemCard = $(this);
        const itemName = $itemCard.data('item-name');
        
        // Elementos de resultado específicos da LOJA
        const resultsAreaShop = $('#results-area-shop #projection-results-area');
        const detailsAreaShop = $('#results-area-shop #calculation-details-area');
        const simulatorSectionShop = $('#results-area-shop #simulator-section');

        // --- Reset Visual e de Conteúdo da LOJA---
        $('#results-area-shop .item-selectable').removeClass('border-primary shadow unlock-path-item').addClass('border-success');
        resultsAreaShop.html('<p class="text-center text-muted small"><i class="bi bi-arrow-clockwise"></i> Carregando projeção...</p>');
        detailsAreaShop.empty();
        simulatorSectionShop.hide().data('current-item', null).data('current-cost', null);
        $('#results-area-shop #simulated-rate-input').val(''); // Target input específico da loja
        $('#results-area-shop #simulation-results-area').html(''); // Target área de simulação específica da loja

        // --- Obtenção Segura do Farm ID ---
        const farmIdElement = $('#current-farm-id-data'); // ID do span que criamos no index.html
        const farmId = farmIdElement.length ? farmIdElement.data('farm-id') : null;

        if (!farmId) {
            console.error("LOJA: Farm ID não encontrado em #current-farm-id-data.");
            resultsAreaShop.html('<p class="text-danger small text-center">Erro: ID da Fazenda não encontrado. Realize uma busca primeiro.</p>');
            return;
        }

        if (!itemName) {
            console.warn("LOJA: Nome do item não encontrado.");
            resultsAreaShop.html('<p class="text-warning small text-center">Erro: Item não especificado.</p>');
            return;
        }

        const markedItemsList = Object.keys(markedUnlockItems);

        const historicalRateElementShop = $('#results-area-shop #historical-daily-rate-info');
        let historicalRateData = historicalRateElementShop.length ? historicalRateElementShop.data('historical-rate') : '';
        let historicalRateNum = null;

        if (historicalRateData !== "" && historicalRateData !== undefined) {
            let parsedRate = parseFloat(historicalRateData);
            if (!isNaN(parsedRate) && parsedRate > 0) {
                historicalRateNum = parsedRate;
            } else {
                console.warn(`LOJA: historicalRateData ('${historicalRateData}') da loja não é um número positivo válido.`);
            }
        } else {
            console.warn("LOJA: #historical-daily-rate-info da loja não encontrado ou `data-historical-rate` vazio.");
        }

        console.log(`LOJA - Enviando AJAX Proj.: Item=${itemName}, Farm=${farmId}, Marcados:`, markedItemsList, `Taxa Hist. do Attr: ${historicalRateData}, Usada: ${historicalRateNum}`);

        let ajaxData = {
            item_name: itemName,
            farm_id: farmId,
            marked_items: markedItemsList
        };

        if (historicalRateNum !== null && !isNaN(historicalRateNum)) {
            ajaxData.historical_rate = historicalRateNum;
        }

        resultsAreaShop.html('<p class="text-center"><span class="spinner-border spinner-border-sm"></span> Calculando para ' + itemName + '...</p>');

        $.ajax({
            url: '/calculate_projection',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(ajaxData),
            dataType: 'json',
            success: function(response) {
                console.log("LOJA - Resposta AJAX Proj.:", response);
                if (response.success) {
                    let resultHtml = `<h6>Resultado para: <strong class="text-success">${response.item_name || '??'}</strong></h6><ul class="list-unstyled small mb-0"><li>Custo Total Estimado <span class="text-muted" data-bs-toggle="tooltip" title="Inclui custo tickets p/ desbloquear (considerando marcados).">(c/ desbloqueio)</span>: <strong>${response.calculated_cost !== null ? response.calculated_cost + ' ' + (response.token_name || 'Tickets') : 'N/A'}</strong></li><li>Dias Estimados para Obter: <strong>`;
                    const remaining_days = response.remaining_season_days;
                    let daysWarning = '';
                    if (remaining_days !== null && response.projected_days !== null && response.projected_days > remaining_days) {
                        daysWarning = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede os ${remaining_days} dias restantes!">⚠️ Excede!</span>`;
                    }
                    if (response.projected_days !== null) { resultHtml += ` ~${response.projected_days} dia(s)${daysWarning} <small class="text-muted d-block">(Taxa: ${response.avg_daily_rate_used?.toFixed(1) || 'N/D'}/dia)</small>`; } else { resultHtml += `Incalculável`; }
                    resultHtml += `</strong></li></ul>`;
                    resultsAreaShop.html(resultHtml);

                    if (response.calculated_cost !== null) {
                        let detailsHtml = `<h6 class="text-muted mt-2">Detalhes do Cálculo:</h6><ul class="list-unstyled small mb-0">`; // Adicionado mt-2
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
                        } else if (unlockCostDisplay === 0 && response.base_item_cost !== null) { // Apenas se for item de tier 1 com custo
                             detailsHtml += `<li class="mt-2 text-muted small"><em>Item de Tier 1 (sem custo de desbloqueio).</em></li>`;
                        }
                        detailsHtml += `</ul>`;
                        detailsAreaShop.html(detailsHtml);
                    } else { detailsAreaShop.empty(); }

                    $('#results-area-shop [data-bs-toggle="tooltip"]').each(function() { // Target tooltips específicos da loja
                         if (!bootstrap.Tooltip.getInstance(this)) { 
                             try { new bootstrap.Tooltip(this); } catch(e){ console.error("LOJA - Erro ao inicializar tooltip dinâmico:", e, this); }
                         }
                    });

                    const unlockItems = response.unlock_path_items || [];
                    $('#results-area-shop .item-selectable.unlock-path-item').removeClass('unlock-path-item'); 
                    if (unlockItems.length > 0) {
                        unlockItems.forEach(function(unlockItemName) {
                            $('#results-area-shop .item-selectable[data-item-name="' + unlockItemName + '"]')
                                .addClass('unlock-path-item')
                                .removeClass('border-success');
                        });
                    }
                    $itemCard.removeClass('border-success unlock-path-item').addClass('border-primary shadow');

                    if (response.calculated_cost !== null && response.calculated_cost !== Infinity) {
                        simulatorSectionShop.data('current-item', response.item_name);
                        simulatorSectionShop.data('current-cost', response.calculated_cost);
                        simulatorSectionShop.show();
                    } else {
                        simulatorSectionShop.hide();
                    }
                    $('#results-area-shop #simulation-results-area').html(''); 
                    $('#results-area-shop #simulated-rate-input').val('');     

                } else { 
                    resultsAreaShop.html(`<p class="text-danger small text-center">Erro ao calcular: ${response.error || 'Falha desconhecida.'}</p>`);
                    detailsAreaShop.empty();
                    simulatorSectionShop.hide();
                }
            }, 
            error: function(jqXHR, textStatus, errorThrown) { 
                console.error("LOJA - Erro AJAX Projeção:", textStatus, errorThrown);
                resultsAreaShop.html('<p class="text-danger small text-center">Erro de conexão ao calcular projeção.</p>');
                detailsAreaShop.empty();
                simulatorSectionShop.hide();
            }
        });
    }); 


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

    // --- INÍCIO: Lógica para Compra Manual no Calendário Potencial ---
    const manualPurchaseModalElement = document.getElementById('manualPurchaseModal');
    let manualPurchaseModalInstance; // Declarar aqui

    if (manualPurchaseModalElement) { // Inicializar somente se o elemento existir
        console.log("Tentativa de inicialização do manualPurchaseModal no carregamento.");
        manualPurchaseModalInstance = new bootstrap.Modal(manualPurchaseModalElement, {
            keyboard: false
        });
    } else {
        console.warn("Elemento #manualPurchaseModal não encontrado no DOM durante o carregamento inicial. Será inicializado no primeiro clique, se encontrado.");
    }

    let currentCalendarData = [];
    if (window.potentialCalendarData && Array.isArray(window.potentialCalendarData) && window.potentialCalendarData.length > 0) {
        currentCalendarData = JSON.parse(JSON.stringify(window.potentialCalendarData)); // Cópia profunda
        currentCalendarData.forEach(dayData => {
            dayData.user_display_active_buffs = []; // Buffs que o usuário realmente "tem"
            // Adicionar VIP global se aplicável e não for um item comprável explicitamente aqui
            if (window.seasonalBuffsConfiguration && window.seasonalBuffsConfiguration.vip && window.config_simIdealPlayerHasVip === true) {
                dayData.user_display_active_buffs.push('VIP'); // Assumindo 'VIP' como ID/nome do buff VIP
            }
            dayData.manual_purchases = []; // Compras feitas pelo usuário neste dia
            dayData.manual_cost_total_day = 0; // Custo total das compras manuais neste dia
            dayData.active_buffs_str = dayData.user_display_active_buffs.join(', '); // String para exibição
        });
        // Recalcular saldos iniciais após limpar buffs/compras da simulação ideal original
        for (let i = 0; i < currentCalendarData.length; i++) {
            if (i > 0) {
                currentCalendarData[i].balance_start_day = parseFloat(currentCalendarData[i-1].balance_end_day);
            }
            // O total_gains_today vem da simulação ideal e não muda com compras manuais
            currentCalendarData[i].balance_end_day = parseFloat(currentCalendarData[i].balance_start_day) + parseFloat(currentCalendarData[i].total_gains_today) - (currentCalendarData[i].manual_cost_total_day || 0);
        }
    } else {
        console.warn("window.potentialCalendarData não está disponível ou está vazio. Funcionalidade de compra manual pode não funcionar corretamente.");
    }

    // Abrir o modal de compra manual
    $(document).on('click', '.open-manual-purchase-modal', function() {
        console.log("Botão '.open-manual-purchase-modal' clicado.");
        const dayIndex = parseInt($(this).data('day-index'));
        const dateDisplay = $(this).data('date-display');

        if (isNaN(dayIndex) || !currentCalendarData || !currentCalendarData[dayIndex]) {
            console.error("Índice do dia inválido ou dados do calendário não encontrados para o dia:", dayIndex, currentCalendarData);
            alert("Erro ao obter dados para este dia do calendário.");
            return;
        }

        // Garantir que o modal esteja instanciado
        if (!manualPurchaseModalInstance) {
            const modalElem = document.getElementById('manualPurchaseModal');
            if (modalElem) {
                console.log("Inicializando manualPurchaseModalInstance no clique.");
                manualPurchaseModalInstance = new bootstrap.Modal(modalElem, { keyboard: false });
            } else {
                console.error("Elemento #manualPurchaseModal não encontrado no DOM ao tentar abrir.");
                alert("Erro: Componente de compra não pôde ser carregado. Tente recarregar a aba 'Potencial da Temporada'.");
                return;
            }
        }

        const dayData = currentCalendarData[dayIndex];
        const currentDayBalance = parseFloat(dayData.balance_end_day); // Saldo final ANTES desta nova compra no dia

        $('#manualPurchaseModalDate').text(dateDisplay);
        $('#modalBalanceInfo').text(currentDayBalance.toFixed(0));
        $('#modalTokenName').text(window.seasonalTokenName || 'Tokens');
        $('#manualPurchaseDayIndex').val(dayIndex);

        const $itemSelect = $('#manualPurchaseItemSelect');
        $itemSelect.empty().append('<option selected disabled value="">Selecione um item...</option>');

        console.log("Populando select com itens:", window.shopItemsForCalendarPurchase);
        if (window.shopItemsForCalendarPurchase && window.shopItemsForCalendarPurchase.length > 0) {
            window.shopItemsForCalendarPurchase.forEach(item => {
                // Certifique-se que a moeda do item é o token sazonal
                if (item.currency === window.seasonalTokenName) {
                    $itemSelect.append(`<option value="${item.name}" data-cost="${item.cost}" data-buff-id="${item.buff_id || ''}">${item.name} (${item.cost} ${window.seasonalTokenName})</option>`);
                }
            });
        } else {
            $itemSelect.append('<option disabled>Nenhum item da loja disponível para compra com tokens.</option>');
        }
        $('#manualPurchaseItemDetails').text('Selecione um item para ver os detalhes.');
        console.log("Tentando mostrar o modal.");
        manualPurchaseModalInstance.show();
    });

    // Atualizar detalhes do item ao selecionar no modal
    $('#manualPurchaseItemSelect').on('change', function() {
        const selectedOption = $(this).find('option:selected');
        const cost = selectedOption.data('cost');
        const buffId = selectedOption.data('buff-id');
        let detailsText = `Custo: ${cost} ${window.seasonalTokenName}.`;
        if (buffId && window.seasonalBuffsConfiguration && window.seasonalBuffsConfiguration[buffId]) {
            detailsText += ` Ativa o buff: ${buffId}.`;
        }
        $('#manualPurchaseItemDetails').text(detailsText);
    });

    // Confirmar a compra manual
    $('#confirmManualPurchaseBtn').on('click', function() {
        console.log("Botão '#confirmManualPurchaseBtn' clicado.");
        const dayIndex = parseInt($('#manualPurchaseDayIndex').val());
        const selectedItemOption = $('#manualPurchaseItemSelect').find('option:selected');
        const itemName = selectedItemOption.val();
        const itemCost = parseFloat(selectedItemOption.data('cost'));
        const itemBuffId = selectedItemOption.data('buff-id');

        if (!itemName || isNaN(itemCost) || isNaN(dayIndex) || !currentCalendarData || !currentCalendarData[dayIndex]) {
            console.warn("Seleção de item inválida, índice do dia ausente ou dados do calendário corrompidos.");
            alert("Por favor, selecione um item válido.");
            return;
        }

        let dayData = currentCalendarData[dayIndex];
        if (parseFloat(dayData.balance_end_day) < itemCost) {
            alert("Saldo insuficiente para comprar este item neste dia.");
            console.warn(`Saldo insuficiente: ${dayData.balance_end_day} < ${itemCost}`);
            return;
        }

        // Adicionar a compra ao dia
        dayData.manual_purchases.push({ name: itemName, cost: itemCost, buff_id: itemBuffId });

        // Deduzir custo e atualizar buffs ativos
        dayData.balance_end_day = parseFloat(dayData.balance_end_day) - itemCost;
        dayData.manual_cost_total_day = (dayData.manual_cost_total_day || 0) + itemCost;
        
        if (itemBuffId && !dayData.user_display_active_buffs.includes(itemBuffId) && window.seasonalBuffsConfiguration && window.seasonalBuffsConfiguration[itemBuffId]) {
            dayData.user_display_active_buffs.push(itemBuffId);
            dayData.user_display_active_buffs.sort(); // Manter ordenado para consistência
        }
        dayData.active_buffs_str = dayData.user_display_active_buffs.join(', ');

        console.log(`Compra registrada para o dia ${dayIndex}: ${itemName}, Custo: ${itemCost}. Saldo final dia: ${dayData.balance_end_day}`);
        console.log(`Buffs ativos do usuário para o dia ${dayIndex}: ${dayData.active_buffs_str}`);

        // Recalcular saldos para dias subsequentes e propagar buffs
        for (let i = dayIndex + 1; i < currentCalendarData.length; i++) {
            currentCalendarData[i].balance_start_day = parseFloat(currentCalendarData[i-1].balance_end_day);
            
            let dailyManualCostSubsequent = currentCalendarData[i].manual_cost_total_day || 0;
            currentCalendarData[i].balance_end_day = parseFloat(currentCalendarData[i].balance_start_day) + parseFloat(currentCalendarData[i].total_gains_today) - dailyManualCostSubsequent;
            
            // Propagar buffs ativos do usuário
            // Herda todos os buffs do dia anterior e garante que o novo buff (itemBuffId) esteja lá, se aplicável à compra original
            // E mantém quaisquer buffs que já foram comprados manualmente para este dia futuro.
            let previousDayUserBuffs = [...(currentCalendarData[i-1].user_display_active_buffs || [])];
            let currentDayAlreadyActiveUserBuffs = [...(currentCalendarData[i].user_display_active_buffs || [])];

            let mergedBuffs = [...new Set([...previousDayUserBuffs, ...currentDayAlreadyActiveUserBuffs])];

            // Se o item comprado (itemBuffId) ainda não estiver na lista de buffs propagados/existentes para este dia futuro, adicione-o.
            if (itemBuffId && !mergedBuffs.includes(itemBuffId) && window.seasonalBuffsConfiguration && window.seasonalBuffsConfiguration[itemBuffId]) {
                 // Este if garante que o buff só é propagado se foi o buff da compra atual.
                 // Se a compra original não tinha buff, não há nada a propagar além do que já existia.
            }
            // A lógica de propagação de buffs precisa ser cuidadosa.
            // Os buffs do dia anterior devem ser herdados.
            // Se um buff foi comprado no 'dayIndex', ele deve ser ativo em 'dayIndex' e todos os dias subsequentes.
            currentCalendarData[i].user_display_active_buffs = [...new Set([...(currentCalendarData[i-1].user_display_active_buffs || []), ...(currentCalendarData[i].user_display_active_buffs || [])])].sort();
            currentCalendarData[i].active_buffs_str = currentCalendarData[i].user_display_active_buffs.join(', ');
        }

        // Atualizar a tabela na interface
        updatePotentialCalendarTableUI(currentCalendarData);
        manualPurchaseModalInstance.hide();
    });

    // Função para atualizar a tabela do calendário na UI
    function updatePotentialCalendarTableUI(calendarData) {
        console.log("Atualizando UI da tabela do calendário...");
        if (!calendarData || !Array.isArray(calendarData)) {
            console.error("Dados do calendário inválidos para atualização da UI.");
            return;
        }
        calendarData.forEach((dayData, index) => {
            const $row = $(`#potentialCalendarTableContainer tbody tr:eq(${index})`);
            if ($row.length === 0) {
                console.warn(`Linha da tabela não encontrada para o índice ${index}`);
                return;
            }
            $row.find('td[data-field="balance_start_day"]').text(parseFloat(dayData.balance_start_day).toFixed(0));
            $row.find('td[data-field="balance_end_day"]').text(parseFloat(dayData.balance_end_day).toFixed(0));
            $row.find('td[data-field="active_buffs_str"]').text(dayData.active_buffs_str ? dayData.active_buffs_str.replace(/,/g, ",\n") : '-');
            
            let purchasesHtml = '';
            if (dayData.manual_purchases) {
                dayData.manual_purchases.forEach(p => {
                    purchasesHtml += `<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle me-1 rounded-pill d-block mb-1">${p.name}</span>`;
                });
            }
            $row.find('div[data-field="manual_purchases_display"]').html(purchasesHtml);
            $row.find('td[data-field="manual_cost_display"]').html(
                (dayData.manual_cost_total_day && dayData.manual_cost_total_day > 0) ? `(-${parseFloat(dayData.manual_cost_total_day).toFixed(0)})` : ''
            );
        });
         // Re-inicializar tooltips na tabela atualizada, se necessário
        $('#potentialCalendarTableContainer [data-bs-toggle="tooltip"]').each(function() {
            if (bootstrap.Tooltip.getInstance(this)) {
                bootstrap.Tooltip.getInstance(this).dispose();
            }
            new bootstrap.Tooltip(this);
        });
    }
    // --- FIM: Lógica para Compra Manual no Calendário Potencial ---

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