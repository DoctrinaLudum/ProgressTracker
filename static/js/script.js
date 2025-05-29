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
    $('.shop-item-image').each(function() {
        const $img = $(this);
        const placeholderSrc = $img.data('placeholder-src');
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
        
        const resultsAreaShop = $('#results-area-shop #projection-results-area');
        const detailsAreaShop = $('#results-area-shop #calculation-details-area');
        const simulatorSectionShop = $('#results-area-shop #simulator-section');

        $('#results-area-shop .item-selectable').removeClass('border-primary shadow unlock-path-item').addClass('border-success');
        resultsAreaShop.html('<p class="text-center text-muted small"><i class="bi bi-arrow-clockwise"></i> Carregando projeção...</p>');
        detailsAreaShop.empty();
        simulatorSectionShop.hide().data('current-item', null).data('current-cost', null);
        $('#results-area-shop #simulated-rate-input').val('');
        $('#results-area-shop #simulation-results-area').html('');

        const farmIdElement = $('#current-farm-id-data');
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
                        let detailsHtml = `<h6 class="text-muted mt-2">Detalhes do Cálculo:</h6><ul class="list-unstyled small mb-0">`;
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
                        } else if (unlockCostDisplay === 0 && response.base_item_cost !== null) {
                             detailsHtml += `<li class="mt-2 text-muted small"><em>Item de Tier 1 (sem custo de desbloqueio).</em></li>`;
                        }
                        detailsHtml += `</ul>`;
                        detailsAreaShop.html(detailsHtml);
                    } else { detailsAreaShop.empty(); }

                    $('#results-area-shop [data-bs-toggle="tooltip"]').each(function() {
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
        const simulatedRate = $('#simulated-rate-input').val();
        const currentItem = $('#simulator-section').data('current-item');
        const currentCost = $('#simulator-section').data('current-cost');
        const farmId = $('#results-area h2 span.badge, #results-area-shop h2 span.badge').text().replace('ID:', '').trim();
        const simulationResultsArea = $('#simulation-results-area');
        const tokenName = $('.currency-ticket').first().text() || 'Tickets'; // Isso pode ser pego de window.seasonalTokenName

        if (!currentItem || currentCost === null || currentCost === undefined) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Selecione um item válido primeiro.</p>'); return;
        }
        const rateNum = parseFloat(simulatedRate);
        if (isNaN(rateNum) || rateNum <= 0) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Insira taxa diária válida (> 0).</p>'); return;
        }

        simulationResultsArea.html('<span class="spinner-border spinner-border-sm text-warning"></span> Recalculando...');
        console.log(`Enviando AJAX Simulação: ${currentItem}, Taxa: ${rateNum}, FarmID: ${farmId}`);

         $.ajax({
               url: '/calculate_projection',
               type: 'POST',
               contentType: 'application/json',
               data: JSON.stringify({ item_name: currentItem, farm_id: farmId, simulated_rate: rateNum }),
               dataType: 'json',
               success: function(response) {
                   console.log("Resposta AJAX Simulação:", response);
                   if (response.success && response.is_simulation) {
                       const remaining_days_sim = response.remaining_season_days;
                       let daysWarningSim = '';
                       if (remaining_days_sim !== null && response.projected_days !== null && response.projected_days > remaining_days_sim) {
                           daysWarningSim = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" title="Prazo (${response.projected_days}d) excede ${remaining_days_sim} dias restantes!">⚠️ Excede!</span>`;
                       }
                       let simResultHtml = `Para <strong>${currentItem}</strong>, com taxa de <strong>${response.avg_daily_rate_used.toFixed(1)}</strong> <span class="currency-ticket">${response.token_name || 'Tickets'}</span>/dia: `;
                       if (response.projected_days !== null) { simResultHtml += ` <strong>~${response.projected_days} dia(s)${daysWarningSim}</strong>`; } else { simResultHtml += ` <strong>Incalculável</strong>`; }
                       simulationResultsArea.html(simResultHtml).removeClass('text-muted').addClass('text-dark');
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
           });
    });
    // --- FIM Handler Botão Simular ---

}); // Fim $(document).ready geral


// --- Lógica para o Botão Voltar ao Topo ---
document.addEventListener('DOMContentLoaded', function() {
    var scrollTopButton = document.getElementById("scrollTopBtn");
    if (scrollTopButton) {
        window.onscroll = function() { scrollFunction(); };
        function scrollFunction() {
            if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
                scrollTopButton.style.display = "flex";
            } else if (scrollTopButton.style.display !== "none") {
                scrollTopButton.style.display = "none";
            }
        }
    }
});
function scrollToTop() {
  window.scrollTo({top: 0, behavior: 'smooth'});
}