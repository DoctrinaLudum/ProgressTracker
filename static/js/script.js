$(document).ready(function() {

    // --- Bloco Original: Formulário Principal ---
    const farmForm = $('#farm-form');
    const loadingIndicator = $('#loading-indicator');
    const submitButton = farmForm.find('button[type="submit"]');
    const originalButtonHTML = submitButton.html();

    // --- Inicialização Tooltips (Estáticos na Carga da Página) ---
    // Mantemos esta inicialização global
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Handler para submit do formulário principal
    if (farmForm.length) { /* ... */ }
    if (submitButton.length) { /* ... */ }
    // --- Fim Bloco Formulário Principal ---

    // --- Handler Erro Imagem (Placeholder) ---
    $('.shop-item-image').each(function() { /* ... (como antes) ... */ });
    // --- FIM Handler Erro Imagem ---

    // --- Interação Loja (AJAX) -> Calculadora ---
    $(document).on('click', '#analysisTabsContent .item-selectable', function(event) {
        event.preventDefault();

        const $itemCard = $(this);
        const itemName = $itemCard.data('item-name');
        const farmId = $('#results-area h2 span.badge').text().replace('ID:', '').trim();

        // --- Reset Visual ---
        $('.item-selectable').removeClass('border-primary shadow unlock-path-item').addClass('border-success');

        // --- Prepara Áreas de Resultado ---
        const resultsArea = $('#projection-results-area');
        resultsArea.html('<p class="text-center"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Calculando...</p>');
        $('#simulator-section').hide();

        if (itemName && farmId) {
            console.log(`Enviando AJAX (Item Click): item=${itemName}, farm=${farmId}`);
            $.ajax({
                url: '/calculate_projection',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ item_name: itemName, farm_id: farmId }),
                dataType: 'json',
                success: function(response) {
                    console.log("Resposta AJAX Projeção:", response);
                    if (response.success) {
                        // --- Monta HTML da Projeção Principal (Corrigido) ---
                        let resultHtml = `<h6>Resultado para: <strong class="text-success">${response.item_name || 'Item Desconhecido'}</strong></h6> <ul class="list-unstyled mb-0 small"> <li> Custo Total Estimado <span class="text-muted" data-bs-toggle="tooltip" data-bs-placement="top" title="Inclui o custo em tickets dos 4 itens mais baratos dos tiers anteriores, necessários para liberar este.">(c/ desbloqueio)</span>: <strong> ${response.calculated_cost !== null && response.calculated_cost !== Infinity ? response.calculated_cost + ' ' + (response.token_name || 'Tickets') : 'Incalculável/Inválido'} </strong> </li> <li> Dias Estimados para Obter: <strong>`;
                        const remaining_days = response.remaining_season_days;
                        let daysWarning = '';
                        if (remaining_days !== null && response.projected_days !== null && response.projected_days > remaining_days) {
                            daysWarning = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="Prazo estimado (${response.projected_days}d) excede os ${remaining_days} dias restantes da temporada!">⚠️ Excede Temporada!</span>`;
                        }
                        if (response.projected_days !== null && response.projected_days !== Infinity) { resultHtml += ` ~${response.projected_days} dia(s)${daysWarning} <small class="text-muted d-block">(Taxa usada: ${response.avg_daily_rate_used ? response.avg_daily_rate_used.toFixed(1) : 'N/D'}/dia)</small>`; } else if (response.calculated_cost === Infinity) { resultHtml += `Item/Tier Inalcançável ou Inválido`; } else { resultHtml += `Taxa diária inválida ou zero`; }
                        resultHtml += `</strong></li></ul>`;
                        // --- Fim Montagem HTML Projeção ---

                        resultsArea.html(resultHtml);

                        // --- Inicializa Tooltips Dinâmicos (Projeção) ---
                        // TEMPORARIAMENTE COMENTADO PARA DEBUG
                        /*
                        console.log("Tentando inicializar tooltips em #projection-results-area...");
                        const projectionTooltips = $('#projection-results-area [data-bs-toggle="tooltip"]');
                        console.log(` -> Encontrados ${projectionTooltips.length} elementos (Proj).`);
                        projectionTooltips.each(function(index) {
                             // ... (código de inicialização com try/catch) ...
                             if (!bootstrap.Tooltip.getInstance(this)) { try { new bootstrap.Tooltip(this); } catch(e) { console.error('Erro tooltip proj:', e); } }
                        });
                        */
                        console.log("Inicialização de tooltips dinâmicos (projeção) comentada para teste.");
                        // --- Fim Inicializa Tooltips ---

                        // --- Destaque do Caminho de Desbloqueio Mínimo ---
                        // (Este código foi adicionado na versão anterior, mas pode não funcionar ainda)
                        const unlockItems = response.unlock_path_items || [];
                        if (unlockItems.length > 0) {
                            console.log("Itens de desbloqueio mínimo recebidos:", unlockItems);
                            unlockItems.forEach(function(unlockItemName) {
                                const $unlockCard = $('#analysisTabsContent .item-selectable[data-item-name="' + unlockItemName + '"]');
                                console.log(` -> Tentando destacar: ${unlockItemName}. Encontrado(s): ${$unlockCard.length}`); // Log de depuração
                                $unlockCard.addClass('unlock-path-item').removeClass('border-success');
                            });
                        } else {
                             console.log("Nenhum item de desbloqueio mínimo recebido do backend.");
                        }
                        // --- Fim Destaque Caminho ---


                        // --- Destaque Principal (Item Clicado) ---
                         $itemCard.removeClass('border-success unlock-path-item').addClass('border-primary shadow');

                        // --- Mostra e Prepara Simulador ---
                        $('#simulator-section').data('current-item', response.item_name);
                        $('#simulator-section').data('current-cost', response.calculated_cost !== Infinity ? response.calculated_cost : null);
                        $('#simulator-section').show();
                        $('#simulation-results-area').html('');
                        $('#simulated-rate-input').val('');

                    } else { /* ... erro projeção ... */ }
                },
                error: function() { /* ... erro ajax projeção ... */ }
            }); // Fim AJAX Item Click

        } else { /* ... erro item/farmId ... */ }
    }); // Fim .item-selectable click


    // --- Handler para o Botão Simular ---
    $(document).on('click', '#simulate-button', function() {
        console.log("--- Botão Simular Clicado! ---"); // Log inicial

        // --- Pega Dados ---
        const simulatedRate = $('#simulated-rate-input').val();
        const currentItem = $('#simulator-section').data('current-item');
        const currentCost = $('#simulator-section').data('current-cost');
        const farmId = $('#results-area h2 span.badge').text().replace('ID:', '').trim();
        const simulationResultsArea = $('#simulation-results-area');
        const tokenName = $('.currency-ticket').first().text() || 'Tickets';

        // Log dos dados pegos
        console.log("Simulador - Dados:", { simulatedRate, currentItem, currentCost, farmId });

        // --- Validações ---
        if (!currentItem) {
            simulationResultsArea.html('<p class="text-danger small mb-0">Selecione um item na loja primeiro.</p>');
            console.error("Simulador - Erro: Nenhum item selecionado.");
            return;
        }
        const rateNum = parseFloat(simulatedRate);
        if (isNaN(rateNum) || rateNum <= 0) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Insira uma taxa diária válida (> 0).</p>');
             console.error("Simulador - Erro: Taxa inválida.");
             return;
        }
        if (currentCost === null || currentCost === undefined) {
             simulationResultsArea.html('<p class="text-danger small mb-0">Não é possível simular para este item (custo inválido).</p>');
             console.error("Simulador - Erro: Custo inválido.");
             return;
        }
        // --- Fim Validações ---

        simulationResultsArea.html('<span class="spinner-border spinner-border-sm text-warning" role="status" aria-hidden="true"></span> Recalculando...');
        console.log("Simulador - Enviando AJAX...");

         // --- Envia AJAX para Simulação ---
         $.ajax({
               url: '/calculate_projection',
               type: 'POST',
               contentType: 'application/json',
               data: JSON.stringify({ item_name: currentItem, farm_id: farmId, simulated_rate: rateNum }),
               dataType: 'json',
               success: function(response) {
                   console.log("Resposta AJAX Simulação:", response);
                   if (response.success && response.is_simulation) {
                       // ... (Lógica Aviso Tempo Dinâmico Simulação - como antes) ...
                       const remaining_days_sim = response.remaining_season_days;
                       let daysWarningSim = '';
                       if (remaining_days_sim !== null && response.projected_days !== null && response.projected_days > remaining_days_sim) {
                           daysWarningSim = ` <span class="text-danger small ms-1" data-bs-toggle="tooltip" ...>⚠️ Excede Temporada!</span>`;
                       }

                       // Monta HTML resultado simulação
                       let simResultHtml = `Para <strong>${currentItem}</strong>, com taxa simulada de <strong>${response.avg_daily_rate_used.toFixed(1)}</strong> <span class="currency-ticket">${response.token_name || 'Tickets'}</span>/dia: `;
                       if (response.projected_days !== null) { simResultHtml += ` <strong>~${response.projected_days} dia(s)${daysWarningSim}</strong>`; } else { simResultHtml += ` <strong>Incalculável</strong>`; }

                       simulationResultsArea.html(simResultHtml).removeClass('text-muted').addClass('text-dark');

                       // --- Inicializa Tooltip do Aviso (Simulação) ---
                       // TEMPORARIAMENTE COMENTADO PARA DEBUG
                       /*
                       console.log("Tentando initializar tooltips em #simulation-results-area...");
                       const warningTooltipSim = $('#simulation-results-area [data-bs-toggle="tooltip"]');
                       console.log(` -> Encontrados ${warningTooltipSim.length} tooltips (Sim).`);
                       if (warningTooltipSim.length > 0) {
                           warningTooltipSim.each(function() {
                               // ... (código de inicialização com try/catch) ...
                               if (!bootstrap.Tooltip.getInstance(this)) { try { new bootstrap.Tooltip(this); } catch(e) { console.error('Erro tooltip sim:', e); } }
                           });
                       }
                       */
                       console.log("Inicialização de tooltips dinâmicos (simulação) comentada para teste.");
                       // --- Fim Inicializa Tooltip Simulação ---

                   } else {
                       console.error("Simulador - Resposta backend inválida ou erro:", response.error);
                       simulationResultsArea.html(`<span class="text-danger small">Erro: ${response.error || 'Falha na simulação.'}</span>`);
                   }
               },
               error: function(jqXHR, textStatus, errorThrown) {
                    console.error("Erro AJAX Simulação:", textStatus, errorThrown);
                    simulationResultsArea.html('<span class="text-danger small">Erro de conexão ao simular.</span>');
               }
           }); // Fim AJAX Simulação
    }); // Fim #simulate-button click
    // --- FIM: Handler para o Botão Simular ---

}); // Fim $(document).ready geral