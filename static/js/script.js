$(document).ready(function() {

    // --- Variáveis Globais para Funcionalidades ---
    let markedUnlockItems = {}; // Para a loja sazonal
    let comprasSimuladasPeloUsuarioJS = []; // Para o calendário interativo

    // --- Constantes Globais do Frontend (passadas do backend via HTML) ---
    // Certifique-se de que estas variáveis são definidas no seu HTML antes deste script.
    // Ex: <script>
    // const SEASONAL_SHOP_ITEMS_DATA = JSON.parse('{{ seasonal_shop_items_json|safe }}');
    // const CALENDAR_BONUS_ITEM_PURCHASE_PRIORITY_DATA = JSON.parse('{{ calendar_bonus_priority_json|safe }}');
    // const SEASONAL_DELIVERY_BUFFS_DATA = JSON.parse('{{ seasonal_delivery_buffs_json|safe }}');
    // </script>

    // --- Manipulação da Visibilidade da Loja Sazonal ---
    $('#analysisTabs button[data-bs-toggle="tab"]').on('shown.bs.tab', function(e) {
        if (e.target.id === 'shop-tab') {
            $('#results-area-shop').removeClass('d-none');
            $('#results-area-shop [data-bs-toggle="tooltip"]').each(function() {
                if (!bootstrap.Tooltip.getInstance(this)) {
                    new bootstrap.Tooltip(this);
                }
            });
        } else {
            $('#results-area-shop').addClass('d-none');
        }
    });

    // --- Bloco Inicial: Formulário Principal e Tooltips Estáticos ---
    const farmForm = $('#farm-form');
    const submitButton = farmForm.find('button[type="submit"]');
    if (farmForm.length) {
        farmForm.on('submit', function(event) {
            if (submitButton.length) {
                const loadingGifUrl = submitButton.data('loading-gif-url');
                if (loadingGifUrl && loadingGifUrl.trim() !== '') {
                    submitButton.prop('disabled', true).html(
                        '<img src="' + loadingGifUrl + '" alt="Carregando..." style="height: 24px; width: auto; margin-right: 8px; vertical-align: middle;"> Buscando...'
                    );
                } else {
                    submitButton.prop('disabled', true).html(
                        '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Buscando...'
                    );
                }
            }
        });
    }
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));


    // --- Handler Erro Imagem (Placeholder) ---
    // Delegar para futuros '.shop-item-image' também, se adicionados dinamicamente
    $(document).on('error', '.shop-item-image', function() {
        const $img = $(this);
        const placeholderSrc = $img.data('placeholder-src');
        const altText = $img.attr('alt');
        $img.off('error'); // Evita loop se o placeholder também falhar
        if (placeholderSrc && $img.attr('src') !== placeholderSrc) {
            $img.attr('src', placeholderSrc);
            $img.attr('alt', altText + ' (imagem não encontrada)');
        } else {
            $img.attr('alt', altText + ' (placeholder indisponível ou já em uso)');
        }
    });

    // --- Lógica da Loja Sazonal (Cálculo de Projeção) ---
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
        // console.log("Itens Marcados Atualizados:", markedUnlockItems);
    });

    $(document).on('click', '#results-area-shop .unlock-item-marker', function(event) {
        event.stopPropagation();
    });

    $(document).on('click', '#results-area-shop .item-selectable', function(event) {
        event.preventDefault();
        const $itemCard = $(this);
        const itemName = $itemCard.data('item-name');
        const resultsAreaShop = $('#results-area-shop #projection-results-area');
        const detailsAreaShop = $('#results-area-shop #calculation-details-area');
        const simulatorSectionShop = $('#results-area-shop #simulator-section');

        $('#results-area-shop .item-selectable').removeClass('border-primary shadow unlock-path-item').addClass('border-success');
        resultsAreaShop.html('<p class="text-center text-muted small"><i class="bi bi-arrow-clockwise"></i> Carregando projeção...</p>');
        detailsAreaShop.empty();
        simulatorSectionShop.hide().data({ 'current-item': null, 'current-cost': null });
        $('#results-area-shop #simulated-rate-input').val('');
        $('#results-area-shop #simulation-results-area').html('');

        const farmIdElement = $('#current-farm-id-data'); //
        const farmId = farmIdElement.length ? farmIdElement.data('farm-id') : null; //

        if (!farmId) {
            resultsAreaShop.html('<p class="text-danger small text-center">Erro: ID da Fazenda não encontrado. Realize uma busca primeiro.</p>');
            return;
        }
        if (!itemName) {
            resultsAreaShop.html('<p class="text-warning small text-center">Erro: Item não especificado.</p>');
            return;
        }

        const markedItemsList = Object.keys(markedUnlockItems);
        const historicalRateElementShop = $('#results-area-shop #historical-daily-rate-info'); //
        let historicalRateData = historicalRateElementShop.length ? historicalRateElementShop.data('historical-rate') : '';
        let historicalRateNum = null;
        if (historicalRateData !== "" && historicalRateData !== undefined) {
            let parsedRate = parseFloat(historicalRateData);
            if (!isNaN(parsedRate) && parsedRate > 0) historicalRateNum = parsedRate;
        }

        let ajaxData = { item_name: itemName, farm_id: farmId, marked_items: markedItemsList };
        if (historicalRateNum !== null && !isNaN(historicalRateNum)) ajaxData.historical_rate = historicalRateNum;

        resultsAreaShop.html(`<p class="text-center"><span class="spinner-border spinner-border-sm"></span> Calculando para ${itemName}...</p>`);
        $.ajax({
            url: '/calculate_projection', //
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(ajaxData),
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    let resultHtml = `<h6>Resultado para: <strong class="text-success">${response.item_name || '??'}</strong></h6><ul class="list-unstyled small mb-0"><li>Custo Total Estimado <span class="text-muted" data-bs-toggle="tooltip" title="Inclui custo tickets p/ desbloquear (considerando marcados).">(c/ desbloqueio)</span>: <strong>${response.calculated_cost !== null ? response.calculated_cost + ' ' + (response.token_name || 'Tickets') : 'N/A'}</strong></li><li>Dias Estimados para Obter: <strong>`;
                    const remaining_days = response.remaining_season_days;
                    let daysWarning = '';
                    if (remaining_days !== null && response.projected_days !== null && response.projected_days > remaining_days) {
                        daysWarning = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede os ${remaining_days} dias restantes!">⚠️ Excede!</span>`;
                    }
                    resultHtml += response.projected_days !== null ? ` ~${response.projected_days} dia(s)${daysWarning} <small class="text-muted d-block">(Taxa: ${response.avg_daily_rate_used?.toFixed(1) || 'N/D'}/dia)</small>` : `Incalculável`;
                    resultHtml += `</strong></li></ul>`;
                    resultsAreaShop.html(resultHtml);

                    if (response.calculated_cost !== null) {
                        let detailsHtml = `<h6 class="text-muted mt-2">Detalhes do Cálculo:</h6><ul class="list-unstyled small mb-0">`;
                        if (response.base_item_cost !== null) detailsHtml += `<li>Custo Base: <strong>${response.base_item_cost} <span class="currency-ticket">${response.token_name || ''}</span></strong></li>`;
                        let unlockCostDisplay = response.calculated_unlock_cost !== null ? response.calculated_unlock_cost : 0;
                        detailsHtml += `<li>Custo Desbloqueio: <strong>${unlockCostDisplay} <span class="currency-ticket">${response.token_name || ''}</span></strong></li>`;
                        const pathItems = response.unlock_path_items_details || [];
                        if (pathItems.length > 0) {
                            let firstTier = pathItems[0]?.tier || '?'; let lastTier = pathItems[pathItems.length - 1]?.tier || '?';
                            detailsHtml += `<li class="mt-2">Itens no Caminho (T${firstTier}-T${lastTier}):</li><ul class="list-unstyled ms-3">`;
                            pathItems.forEach(function(item) {
                                detailsHtml += `<li class="py-1">`;
                                detailsHtml += item.source === 'marked' ? `<i class="bi bi-check-square-fill text-primary me-1" data-bs-toggle="tooltip" title="Marcado por você."></i> ` : `<i class="bi bi-calculator text-muted me-1" data-bs-toggle="tooltip" title="Calculado (ticket mais barato)."></i> `;
                                detailsHtml += `${item.name} <span class="text-muted">(`;
                                if (item.currency === 'ticket' && item.cost !== null) detailsHtml += `${item.cost} <span class="currency-ticket">${response.token_name || ''}</span>`;
                                else if (item.currency === 'sfl') detailsHtml += `<span class="currency-sfl">Flower</span>`;
                                else if (item.currency === 'broken_pillar') detailsHtml += `<span class="currency-broken_pillar">Pillar</span>`;
                                else detailsHtml += item.currency || `?`;
                                detailsHtml += `)</span></li>`;
                            });
                            detailsHtml += `</ul>`;
                        } else if (unlockCostDisplay === 0 && response.base_item_cost !== null) {
                            detailsHtml += `<li class="mt-2 text-muted small"><em>Item de Tier 1 (sem custo de desbloqueio).</em></li>`;
                        }
                        detailsHtml += `</ul>`;
                        detailsAreaShop.html(detailsHtml);
                    } else { detailsAreaShop.empty(); }

                    $('#results-area-shop [data-bs-toggle="tooltip"]').each(function() { if (!bootstrap.Tooltip.getInstance(this)) new bootstrap.Tooltip(this); });
                    const unlockItems = response.unlock_path_items || [];
                    $('#results-area-shop .item-selectable.unlock-path-item').removeClass('unlock-path-item');
                    unlockItems.forEach(function(unlockItemName) { $('#results-area-shop .item-selectable[data-item-name="' + unlockItemName + '"]').addClass('unlock-path-item').removeClass('border-success'); });
                    $itemCard.removeClass('border-success unlock-path-item').addClass('border-primary shadow');
                    if (response.calculated_cost !== null && response.calculated_cost !== Infinity) {
                        simulatorSectionShop.data({ 'current-item': response.item_name, 'current-cost': response.calculated_cost }).show();
                    } else { simulatorSectionShop.hide(); }
                    $('#results-area-shop #simulation-results-area').html('');
                    $('#results-area-shop #simulated-rate-input').val('');
                } else {
                    resultsAreaShop.html(`<p class="text-danger small text-center">Erro ao calcular: ${response.error || 'Falha desconhecida.'}</p>`);
                    detailsAreaShop.empty(); simulatorSectionShop.hide();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error("LOJA - Erro AJAX Projeção:", textStatus, errorThrown);
                resultsAreaShop.html('<p class="text-danger small text-center">Erro de conexão ao calcular projeção.</p>');
                detailsAreaShop.empty(); simulatorSectionShop.hide();
            }
        });
    });

    // --- Handler para o Botão Simular (Loja) ---
    $(document).on('click', '#results-area-shop #simulate-button', function() { // Mais específico para evitar conflito se houver outro #simulate-button
        const simulatedRate = $('#results-area-shop #simulated-rate-input').val();
        const currentItem = $('#results-area-shop #simulator-section').data('current-item');
        const currentCost = $('#results-area-shop #simulator-section').data('current-cost');
        const farmId = $('#current-farm-id-data').data('farm-id'); // Pegar de forma consistente
        const simulationResultsArea = $('#results-area-shop #simulation-results-area');
        const tokenName = typeof GLOBAL_SEASONAL_TOKEN_NAME !== 'undefined' ? GLOBAL_SEASONAL_TOKEN_NAME : 'Tickets';


        if (!farmId) { simulationResultsArea.html('<p class="text-danger small mb-0">Farm ID não encontrado.</p>'); return; }
        if (!currentItem || currentCost === null || currentCost === undefined) { simulationResultsArea.html('<p class="text-danger small mb-0">Selecione um item válido primeiro.</p>'); return; }
        const rateNum = parseFloat(simulatedRate);
        if (isNaN(rateNum) || rateNum <= 0) { simulationResultsArea.html('<p class="text-danger small mb-0">Insira taxa diária válida (> 0).</p>'); return; }

        simulationResultsArea.html('<span class="spinner-border spinner-border-sm text-warning"></span> Recalculando...');
        $.ajax({
            url: '/calculate_projection', //
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ item_name: currentItem, farm_id: farmId, simulated_rate: rateNum }),
            dataType: 'json',
            success: function(response) {
                if (response.success && response.is_simulation) {
                    const remaining_days_sim = response.remaining_season_days;
                    let daysWarningSim = '';
                    if (remaining_days_sim !== null && response.projected_days !== null && response.projected_days > remaining_days_sim) {
                        daysWarningSim = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede ${remaining_days_sim} dias restantes!">⚠️ Excede!</span>`;
                    }
                    let simResultHtml = `Para <strong>${currentItem}</strong>, com taxa de <strong>${response.avg_daily_rate_used.toFixed(1)}</strong> <span class="currency-ticket">${response.token_name || tokenName}</span>/dia: `;
                    simResultHtml += response.projected_days !== null ? ` <strong>~${response.projected_days} dia(s)${daysWarningSim}</strong>` : ` <strong>Incalculável</strong>`;
                    simulationResultsArea.html(simResultHtml).removeClass('text-muted').addClass('text-dark');
                    $('#results-area-shop #simulation-results-area [data-bs-toggle="tooltip"]').each(function() { if (!bootstrap.Tooltip.getInstance(this)) new bootstrap.Tooltip(this); });
                } else {
                    simulationResultsArea.html(`<span class="text-danger small">Erro: ${response.error || 'Falha sim.'}</span>`);
                }
            },
            error: function() { simulationResultsArea.html('<span class="text-danger small">Erro de conexão.</span>'); }
        });
    });


    // --- Início da Lógica para Calendário Interativo ---
    function getBuffSourceKeyForItem(itemName) {
        if (window.CALENDAR_BONUS_ITEM_PURCHASE_PRIORITY_DATA) {
            const foundItem = window.CALENDAR_BONUS_ITEM_PURCHASE_PRIORITY_DATA.find(item => item.name === itemName);
            if (foundItem && foundItem.buff_source_key) return foundItem.buff_source_key;
        }
        if (window.SEASONAL_DELIVERY_BUFFS_DATA && window.SEASONAL_DELIVERY_BUFFS_DATA[itemName]) return itemName;
        return '';
    }

    function populateDraggableShopItems() {
        const panel = $('#draggable-shop-items-panel');
        if (typeof SEASONAL_SHOP_ITEMS_DATA === 'undefined') {
            console.error("[JS] Erro: SEASONAL_SHOP_ITEMS_DATA não definida.");
            if (panel.length) panel.html('<p class="text-danger small">Erro: Dados da loja não disponíveis.</p>');
            return;
        }
        if (!panel.length) { console.error("[JS] Painel #draggable-shop-items-panel não encontrado."); return; }

        let itemsHtml = '<ul class="list-group list-group-flush draggable-items-list">';
        const sortedItemNames = Object.keys(SEASONAL_SHOP_ITEMS_DATA).sort((a, b) => {
            const itemA = SEASONAL_SHOP_ITEMS_DATA[a]; const itemB = SEASONAL_SHOP_ITEMS_DATA[b];
            return (itemA.tier || 0) - (itemB.tier || 0) || a.localeCompare(b);
        });

        sortedItemNames.forEach(function(itemName) {
            const item = SEASONAL_SHOP_ITEMS_DATA[itemName];
            let currencySymbol = item.currency, currencyClass = 'text-muted', currencyTitle = item.currency ? item.currency.toUpperCase() : 'N/A';
            if (item.currency === 'ticket') { currencySymbol = `<i class="bi bi-ticket-perforated-fill text-success"></i>`; currencyClass = 'text-success'; currencyTitle = 'Tickets Sazonais'; }
            else if (item.currency === 'sfl') { currencySymbol = `<i class="bi bi-droplet-fill" style="color: #E83E8C;"></i>`; currencyClass = 'text-sfl'; currencyTitle = 'SFL'; }
            else if (item.currency === 'broken_pillar') { currencySymbol = `<i class="bi bi-bricks text-secondary"></i>`; currencyClass = 'text-secondary'; currencyTitle = 'Broken Pillars'; }
            
            let buffKeyForItem = getBuffSourceKeyForItem(itemName);
            itemsHtml += `
                <li class="list-group-item list-group-item-action draggable-shop-item p-2" draggable="true" 
                    data-item-name="${itemName}" data-item-cost="${item.cost}" data-item-currency="${item.currency}"
                    data-item-tier="${item.tier || 0}" data-buff-source-key="${buffKeyForItem || ''}">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <span class="draggable-item-name small fw-medium">${itemName} <span class="text-muted" style="font-size:0.8em;">(T${item.tier || 'N/A'})</span></span>
                        <small class="${currencyClass}" title="${currencyTitle}">${currencySymbol} ${item.cost}</small>
                    </div>
                </li>`;
        });
        itemsHtml += '</ul>';
        panel.html(itemsHtml);

        $('.draggable-shop-item').on('dragstart', function(event) {
            const itemData = {
                name: $(this).data('item-name'), cost: $(this).data('item-cost'), currency: $(this).data('item-currency'),
                tier: $(this).data('item-tier'), buff_source_key: $(this).data('buff-source-key')
            };
            try {
                event.originalEvent.dataTransfer.setData('application/json', JSON.stringify(itemData));
                event.originalEvent.dataTransfer.effectAllowed = "copy";
            } catch (e) {
                event.originalEvent.dataTransfer.setData('text/plain', $(this).data('item-name'));
            }
        });
    }

    const calendarTabButton = document.getElementById('calendar-tab-btn'); //
    if (calendarTabButton) {
        calendarTabButton.addEventListener('shown.bs.tab', function(event) {
            if ($('#draggable-shop-items-panel').children().length <= 1 || $('#draggable-shop-items-panel').find('ul.draggable-items-list').length === 0) {
                populateDraggableShopItems();
            }
        });
        if ($('#calendar-tab-pane').hasClass('show active')) { //
            populateDraggableShopItems();
        }
    }

    $('#reset-calendar-sim-btn').on('click', function() {
        if (confirm("Tem certeza que deseja resetar todas as compras simuladas no calendário e voltar ao \"caminho de ouro\" inicial?")) {
            comprasSimuladasPeloUsuarioJS = [];
            $('#load-calendar-btn').trigger('click');
        }
    });
    
    //o> Handler do clique para o botão de carregar o calendário
    $('#load-calendar-btn').on('click', function() {
        const vipActiveForSim = $('#vip-active-for-calendar-sim').is(':checked');
        const calendarContainer = $('#seasonal-calendar-container');
        const summaryContainer = $('#seasonal-calendar-summary');
        
        calendarContainer.html('<div id="calendar-loading-placeholder" class="text-center p-5"><span class="spinner-border spinner-border-sm text-info" role="status"></span> Carregando...</div>');
        summaryContainer.empty();

        $.ajax({
            url: '/get_seasonal_calendar',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ vip: vipActiveForSim, compras_simuladas: comprasSimuladasPeloUsuarioJS }),
            dataType: 'json',
            success: function(response) {
                calendarContainer.find('#calendar-loading-placeholder').remove();
                if (response.success) {
                    const calendarData = response.calendar_data;
                    const tokenName = response.token_name || 'Tokens'; // Usado no título do badge de compra, se necessário
                    
                    if (calendarData && calendarData.length > 0) {
                        if (calendarData[0].erro) {
                            calendarContainer.html(`<p class="text-danger text-center mt-3">Erro: ${calendarData[0].erro}</p>`);
                            return;
                        }
                        let tableHtml = '<table class="table table-sm table-hover table-bordered" style="font-size: 0.78rem;">';
                        tableHtml += `
                            <thead class="table-info text-center">
                                <tr>
                                    <th style="min-width: 120px; vertical-align: middle;">Data</th>
                                    <th class="text-end" style="vertical-align: middle;" title="Tickets base de Entregas">Entregas (Base)</th>
                                    <th class="text-end" style="vertical-align: middle;" title="Tickets base de Bounties (semanal)">Bounties (Base)</th>
                                    <th class="text-end" style="vertical-align: middle;" title="Tickets base de Chores (semanal)">Chores (Base)</th>
                                    <th class="text-start" style="vertical-align: middle; min-width: 190px;" title="Detalhes dos bônus aplicados no dia">Bônus Detalhado Dia</th>
                                    <th class="text-end" style="vertical-align: middle;">Baú</th>
                                    <th class="text-end table-secondary" style="vertical-align: middle; font-weight:bold;">Total Dia</th>
                                    <th class="text-end table-light" style="vertical-align: middle;">Acum. Bruto</th>
                                    <th class="text-end text-muted" style="font-size:0.7rem; vertical-align: middle;" title="Saldo de tickets após compras simuladas.">Saldo p/ Compra</th>
                                    <th style="min-width: 200px; vertical-align: middle;">Eventos / Compras Simuladas</th>
                                </tr>
                            </thead><tbody>`;
                        
                        let grandTotalTicketsBruto = 0;

                        calendarData.forEach(function(day) {
                            let rowClass = '';
                            // Verifica se há alguma compra neste dia para aplicar a classe de destaque na linha
                            if (day.compras_do_dia_list && day.compras_do_dia_list.length > 0) {
                                rowClass = 'table-light font-monospace';
                            }

                            // Coluna: Bônus Detalhado Dia
                            let bonusDetailHtml = '<div style="font-size: 0.7rem; line-height: 1.2;">';
                            if (day.bonus_diario_detalhado_display && day.bonus_diario_detalhado_display.length > 0) {
                                bonusDetailHtml += '<ul class="list-unstyled mb-0">';
                                day.bonus_diario_detalhado_display.forEach(b => bonusDetailHtml += `<li><small>${b.fonte}:</small> <strong class="text-primary">+${b.valor}</strong></li>`);
                                bonusDetailHtml += '</ul>';
                            } else {
                                bonusDetailHtml += (day.total_bonus_diario_display && day.total_bonus_diario_display > 0) ? `<strong class="text-primary">+${day.total_bonus_diario_display}</strong>` : '<span class="text-muted">0</span>';
                            }
                            bonusDetailHtml += '</div>';

                            // Coluna: Eventos / Compras Simuladas
                            let cellDisplayItemsHTML = [];
                            // Usa a nova chave 'eventos_compras_display_final' que é uma lista de strings
                            if (day.eventos_compras_display_final && Array.isArray(day.eventos_compras_display_final)) {
                                day.eventos_compras_display_final.forEach(text_string => {
                                    let badgeClass = 'bg-light text-dark border'; // Badge padrão para texto genérico
                                    let titleAttr = '';

                                    if (text_string.startsWith('Adquiriu:')) {
                                        badgeClass = 'bg-success-subtle text-success-emphasis';
                                        titleAttr = 'Item Simulado';
                                    } else if (text_string.includes('Double Delivery!')) {
                                        badgeClass = 'bg-danger-subtle text-danger-emphasis';
                                    } else if (text_string.includes('Reset Semanal')) {
                                        badgeClass = 'bg-warning-subtle text-warning-emphasis';
                                    } else if (text_string.includes('Pré-atividades')) {
                                        badgeClass = 'bg-secondary-subtle text-secondary-emphasis';
                                    }
                                    // Adiciona d-block mb-1 para empilhar os badges
                                    cellDisplayItemsHTML.push(
                                        `<span class="badge ${badgeClass} rounded-pill d-block mb-1" title="${titleAttr}">${text_string}</span>`
                                    );
                                });
                            }
                            let finalEventDisplayContent = cellDisplayItemsHTML.length > 0 ? cellDisplayItemsHTML.join('') : '<span class="text-muted small">-</span>';

                            // Construção da linha da tabela
                            tableHtml += `<tr class="${rowClass}" data-date-value="${day.data}">`;
                            tableHtml += `<td class="text-nowrap">${day.data_display}</td>`;
                            tableHtml += `<td class="text-end">${day.tickets_entregas_base_display || 0}</td>`;
                            tableHtml += `<td class="text-end">${day.tickets_bounties_base_display || 0}</td>`;
                            tableHtml += `<td class="text-end">${day.tickets_chores_base_display || 0}</td>`;
                            tableHtml += `<td class="text-start py-1 px-2">${bonusDetailHtml}</td>`;
                            tableHtml += `<td class="text-end">${day.tickets_bau || 0}</td>`;
                            tableHtml += `<td class="text-end fw-bold table-secondary">${day.total_tickets_dia}</td>`;
                            tableHtml += `<td class="text-end table-light fw-medium">${day.tickets_acumulados_brutos}</td>`;
                            tableHtml += `<td class="text-end text-muted" style="font-size:0.7rem;">${day.tickets_liquidos_compra}</td>`;
                            tableHtml += `<td><div style="min-width: 180px; font-size: 0.75rem;">${finalEventDisplayContent}</div></td>`;
                            tableHtml += '</tr>';
                            
                            grandTotalTicketsBruto = day.tickets_acumulados_brutos;
                        });
                        tableHtml += '</tbody></table>';
                        calendarContainer.html(tableHtml);

                        // Reanexar handlers de drag-and-drop para as novas linhas da tabela
                        $('#seasonal-calendar-container table tbody tr').on('dragover', function(event) { event.preventDefault(); $(this).addClass('calendar-drop-hover'); });
                        $('#seasonal-calendar-container table tbody tr').on('dragleave', function() { $(this).removeClass('calendar-drop-hover'); });
                        $('#seasonal-calendar-container table tbody tr').on('drop', function(event) {
                            event.preventDefault(); $(this).removeClass('calendar-drop-hover');
                            const droppedItemDataString = event.originalEvent.dataTransfer.getData('application/json');
                            if (!droppedItemDataString) return;
                            const droppedItemData = JSON.parse(droppedItemDataString);
                            const targetDate = $(this).data('date-value');
                            if (!targetDate) { alert("Erro: Data alvo não encontrada."); return; }
                            handleSimulatedPurchase(droppedItemData, targetDate); // handleSimulatedPurchase permanece como está
                        });

                        let summaryText = `Potencial máximo bruto total de <strong>${grandTotalTicketsBruto}</strong> ${tokenName} na temporada (${response.season_start} a ${response.season_end}). Simulado com VIP ${response.vip_simulated ? '<strong>ATIVO</strong>' : '<strong>INATIVO</strong>'}.`;
                        summaryContainer.html(summaryText);
                    } else { 
                        calendarContainer.html('<p class="text-warning text-center mt-3">Nenhum dado para exibir.</p>'); 
                    }
                } else { 
                    calendarContainer.html(`<p class="text-danger text-center mt-3">Erro: ${response.error || 'Falha ao carregar dados do calendário.'}</p>`); 
                }
            },
            error: function() { 
                calendarContainer.html('<p class="text-danger text-center mt-3">Erro de conexão ao carregar o calendário.</p>'); 
            }
        });
    }); // o> Fim do #load-calendar-btn handler

    function handleSimulatedPurchase(itemData, targetDate) {
    // itemData é o objeto do item arrastado
    // targetDate é a string da data onde o item foi solto (ex: "2025-05-05")

    console.log("[JS-SIM] handleSimulatedPurchase - itemData:", itemData);
    console.log("[JS-SIM] handleSimulatedPurchase - itemData.name:", itemData ? itemData.name : "itemData is null");
    console.log("[JS-SIM] handleSimulatedPurchase - targetDate:", targetDate);
    
    // Prepara o payload para o backend
    // Envia a lista completa de compras simuladas atuais e a data alvo
    const payload = {
        item_name: itemData.name,
        simulated_purchases_up_to_date: comprasSimuladasPeloUsuarioJS, 
        target_date_for_unlock_check: targetDate 
    };
    console.log("[JS-SIM] handleSimulatedPurchase - Payload a ser enviado:", payload); // Log do payload completo
    $.ajax({
        url: '/calculate_purchase_details_for_calendar',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload), // Usa o payload corrigido
        dataType: 'json',
        success: function(detailsResponse) {
            console.log("[JS-SIM-DETAILS] Resposta de detalhes da compra:", detailsResponse);
            if (detailsResponse.success) {
                const { 
                    item_name, // Nome do item principal confirmado pelo backend
                    // item_cost_original, // Custo do item principal na sua moeda (vem de 'total_cost' se não ticket, ou do config)
                    total_cost, // Custo principal para exibir no diálogo (pode ser custo do item ou custo total em tickets)
                    currency, 
                    tier, 
                    unlock_cost_tickets, 
                    unlock_items_details, 
                    token_name,
                    total_tickets_to_debit, // O que realmente será debitado em tickets
                    is_tier_unlockable 
                } = detailsResponse;

                let confirmMsg = `Simular aquisição de "${item_name}" (Tier ${tier || 'N/A'})`;
                let costStringForDialog = "";

                // Constrói a string de custo para o diálogo de confirmação
                if (total_cost !== null) { // 'total_cost' do JSON é o 'json_cost_for_dialog' do backend
                    costStringForDialog = `${total_cost} ${currency ? currency.toUpperCase() : '?'}`;
                    if (currency === 'ticket' && total_tickets_to_debit !== total_cost) {
                         // Caso especial: item é de ticket, mas total_cost (para diálogo) pode ser só o item
                         // e total_tickets_to_debit inclui desbloqueio.
                         // A lógica do backend já deve ter tornado 'total_cost' (para diálogo) o valor final em tickets se o item é de ticket.
                    }
                } else { // total_cost é null (geralmente se is_tier_unlockable é false)
                    costStringForDialog = `N/A (Tier ${tier} não desbloqueável)`;
                }
                confirmMsg += ` por ${costStringForDialog}?`;
                
                // Adiciona detalhes sobre o desbloqueio do tier
                if (tier > 1) {
                    if (!is_tier_unlockable) {
                        confirmMsg += `\n\nATENÇÃO: O Tier ${tier} não pode ser desbloqueado!`;
                        if (unlock_items_details && unlock_items_details.length > 0) {
                             const unlockItemsStrings = unlock_items_details.map(itemDetail => 
                                `${itemDetail.name} (${itemDetail.cost}${token_name.substring(0,1)})`
                            );
                            confirmMsg += `\nSeriam necessários (mas não há como obter todos): ${unlockItemsStrings.join(', ')}.`;
                        } else if (unlock_cost_tickets === null && tier > 1) { 
                             confirmMsg += `\nNão há itens de ${token_name} suficientes nos tiers anteriores para comprar e desbloquear este tier.`;
                        }
                    } else if (unlock_cost_tickets !== null && unlock_cost_tickets > 0) {
                        const unlockItemsStrings = unlock_items_details.map(itemDetail => 
                            `${itemDetail.name} (${itemDetail.cost}${token_name.substring(0,1)})`
                        );
                        if (currency === 'ticket') { // Item principal é de ticket
                            confirmMsg += `\n\nItens de ${token_name} para desbloqueio (custo já incluído no total acima): ${unlockItemsStrings.join(', ')}.`;
                        } else { // Item principal não é de ticket
                            confirmMsg += `\n\nPara liberar este Tier, também é necessário adquirir (será simulado se confirmar): ${unlockItemsStrings.join(', ')} (Custo total desbloqueio: ${unlock_cost_tickets} ${token_name}).`;
                        }
                    } else if (is_tier_unlockable && (unlock_cost_tickets === 0 || unlock_cost_tickets === null) ) {
                         confirmMsg += `\n\n(Desbloqueio de Tier ${tier} já satisfeito ou não requer custo adicional em ${token_name}).`;
                    }
                }
                
                // Permitir confirmação APENAS se o tier for desbloqueável
                if (is_tier_unlockable && confirm(confirmMsg)) {
                    const buffKey = itemData.buff_source_key || getBuffSourceKeyForItem(item_name); // Usa item_name da resposta
                    let novasComprasParaAdicionar = [];

                    // Adiciona o item principal que foi arrastado
                    novasComprasParaAdicionar.push({
                        name: item_name, 
                        data_compra: targetDate,
                        // custo_real_gasto é o 'total_tickets_to_debit' se o item principal for de ticket,
                        // ou 0 se o item principal não for de ticket (pois seu custo é em outra moeda).
                        custo_real_gasto: (currency === 'ticket' && total_tickets_to_debit !== null) ? total_tickets_to_debit : 0,
                        buff_source_key: buffKey,
                        // display_cost_in_badge: (currency === 'ticket' && total_tickets_to_debit !== null) ? total_tickets_to_debit : item_cost_original // Para o Ponto 2
                    });

                    // Adiciona os itens de DESBLOQUEIO DE TIER (que são sempre de ticket)
                    // O custo deles só é debitado se o item principal NÃO FOR DE TICKET.
                    // Se o item principal FOR DE TICKET, o custo de desbloqueio já está em 'total_tickets_to_debit'.
                    if (unlock_cost_tickets !== null && unlock_cost_tickets > 0 && unlock_items_details && unlock_items_details.length > 0) {
                        unlock_items_details.forEach(unlockItem => {
                            if (unlockItem.currency === 'ticket' && unlockItem.cost > 0) { 
                                if (unlockItem.name !== item_name && 
                                    !comprasSimuladasPeloUsuarioJS.some(c => c.name === unlockItem.name && c.data_compra === targetDate)) {
                                    
                                     let custoRealDebitadoParaItemDesbloqueio = 0;
                                    if (currency !== 'ticket') { // Se o item principal NÃO é de ticket
                                        custoRealDebitadoParaItemDesbloqueio = unlockItem.cost;
                                    }
                                    // Se o item principal é de ticket, custoRealDebitadoParaItemDesbloqueio permanece 0

                                    novasComprasParaAdicionar.push({
                                        name: unlockItem.name,
                                        data_compra: targetDate, 
                                        custo_real_gasto: custoRealDebitadoParaItemDesbloqueio, 
                                        buff_source_key: getBuffSourceKeyForItem(unlockItem.name),
                                        original_cost_for_display: unlockItem.cost // NOVA PROPRIEDADE
                                    });
                                     console.log(`[JS-SIM] -> Adicionando/Registrando item de desbloqueio: ${unlockItem.name}, Custo REAL DEBITADO: ${custoRealDebitadoParaItemDesbloqueio}T`);
                                }
                            }
                        });
                    }
                    
                    novasComprasParaAdicionar.forEach(novaCompra => {
                        const compraExistenteIndex = comprasSimuladasPeloUsuarioJS.findIndex(
                            c => c.name === novaCompra.name && c.data_compra === novaCompra.data_compra
                        );
                        if (compraExistenteIndex === -1) {
                            comprasSimuladasPeloUsuarioJS.push(novaCompra);
                        } else {
                            // Lógica para lidar com duplicatas se necessário (ex: substituir)
                            // Por agora, para evitar confusão, se já existe na mesma data, não adiciona de novo.
                            console.warn(`[JS-SIM] Tentativa de adicionar ${novaCompra.name} novamente em ${novaCompra.data_compra}. Ignorando para evitar duplicata exata na lista de simulação.`);
                        }
                    });
                    
                    comprasSimuladasPeloUsuarioJS.sort((a, b) => new Date(a.data_compra) - new Date(b.data_compra));
                    console.log("[JS-SIM] Lista de compras simuladas atualizada:", comprasSimuladasPeloUsuarioJS);
                    $('#load-calendar-btn').trigger('click');

                } else if (!is_tier_unlockable) {
                    alert(confirmMsg); 
                    console.log(`[JS-SIM] Simulação de '${item_name}' impedida: Tier não desbloqueável.`);
                } else {
                    console.log("[JS-SIM] Compra cancelada pelo usuário.");
                }
            } else {
                let errorMsg = "[JS-SIM-DETAILS] Resposta de detalhes não foi sucesso";
                if(detailsResponse && detailsResponse.error) errorMsg += ": " + detailsResponse.error;
                console.error(errorMsg, detailsResponse);
                alert(`Erro ao obter detalhes da compra: ${ (detailsResponse && detailsResponse.error) || 'Resposta inválida do servidor.'}`);
            }
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error("[JS-SIM-DETAILS] Erro AJAX em detalhes da compra:", textStatus, errorThrown, jqXHR.status, jqXHR.responseText);
            alert("Erro de comunicação (ver console) ao tentar obter detalhes da compra. Tente novamente.");
        }
    });
    }
}); // Fim $(document).ready geral

// ---> Lógica para o Botão Voltar ao Topo (Global) ---
function scrollFunctionForButton(buttonElement) {
    if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
        buttonElement.style.display = "flex";
    } else if (buttonElement.style.display !== "none") {
        buttonElement.style.display = "none";
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const scrollTopButtonGlobal = document.getElementById("scrollTopBtn");
    if (scrollTopButtonGlobal) {
        window.onscroll = function() { scrollFunctionForButton(scrollTopButtonGlobal); };
    }
});

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}