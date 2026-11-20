(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const form = document.getElementById('pac-builder-form');
        const formList = document.getElementById('form-list');
        const addBtn = document.getElementById('add-btn');
        const totalForms = document.getElementById('id_form-TOTAL_FORMS');
        const submitBtn = document.getElementById('submit-btn');
        const summaryBar = document.getElementById('live-summary');
        const loadingOverlay = document.getElementById('loading-overlay');
        const emptyTemplateEl = document.getElementById('empty-form');

        if (!form || !formList || !totalForms) return;

        let validateTimers = new WeakMap();
        let searchTimers = new WeakMap();

        function formatDateITA(isoDate) {
            if (!isoDate) return '';
            const parts = isoDate.split('-');
            if (parts.length !== 3) return isoDate;
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }

        function formatEuroSimple(val) {
            const num = Number(val) || 0;
            return num.toLocaleString('it-IT', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' €';
        }

        function updateLiveSummary() {
            if (!summaryBar) return;
            const rows = formList.querySelectorAll('.pac-row-card');
            let totalInitial = 0;
            let monthlyEq = 0;

            rows.forEach(function (row) {
                const initEl = row.querySelector('input[name$="-importo_iniziale"]');
                const rataEl = row.querySelector('input[name$="-importo_periodico"]');
                const freqEl = row.querySelector('select[name$="-frequenza"]');
                const initVal = parseFloat(initEl ? initEl.value : 0) || 0;
                const rataVal = parseFloat(rataEl ? rataEl.value : 0) || 0;
                const freqVal = parseInt(freqEl ? freqEl.value : 1, 10) || 1;
                totalInitial += initVal;
                monthlyEq += rataVal / freqVal;
            });

            summaryBar.innerHTML =
                `<span>Portafoglio: <strong>${rows.length} ETF</strong></span>` +
                `<span>Capitale iniziale: <strong>${formatEuroSimple(totalInitial)}</strong></span>` +
                `<span>Impegno mensile equivalente: <strong>${monthlyEq.toLocaleString('it-IT', { maximumFractionDigits: 0 })} €/mese</strong></span>`;
        }

        function updateFormIndices() {
            const rows = formList.querySelectorAll('.pac-row-card');
            totalForms.value = rows.length;

            rows.forEach(function (row, index) {
                const title = row.querySelector('.row-title');
                if (title) title.textContent = `ETF #${index + 1}`;

                const delBtn = row.querySelector('.btn-delete');
                if (delBtn) delBtn.disabled = rows.length <= 1;

                row.querySelectorAll('input, select').forEach(function (input) {
                    if (input.name) {
                        input.name = input.name.replace(/form-\d+-/, `form-${index}-`);
                    }
                    if (input.id) {
                        input.id = input.id.replace(/id_form-\d+-/, `id_form-${index}-`);
                    }
                });
            });
            updateLiveSummary();
        }

        function updateButtonState() {
            if (!submitBtn) return;
            const inputs = formList.querySelectorAll('.ticker-input');
            const hasValues = Array.from(inputs).some((inp) => inp.value.trim().length > 0);
            const allValid = Array.from(inputs).every((inp) => {
                const val = inp.value.trim();
                return val === '' || inp.dataset.valid !== 'false';
            });
            submitBtn.disabled = !(hasValues && allValid);
        }

        function closeAllDropdowns() {
            document.querySelectorAll('.autocomplete-dropdown.open').forEach((dd) => {
                dd.classList.remove('open');
            });
        }

        function validateTicker(inputField) {
            const row = inputField.closest('.pac-row-card');
            if (!row) return;
            const feedbackDiv = row.querySelector('.ticker-feedback');
            const dateFeedbackDiv = row.querySelector('.date-feedback');
            const dateInput = row.querySelector('input[type="date"]');
            const taxSelect = row.querySelector('select[name$="-aliquota_fiscale"]');
            const ticker = inputField.value.trim().toUpperCase();

            if (ticker.length < 2) {
                if (feedbackDiv) feedbackDiv.textContent = '';
                inputField.dataset.valid = 'false';
                updateButtonState();
                return;
            }

            if (feedbackDiv) {
                feedbackDiv.textContent = 'Verifica ticker...';
                feedbackDiv.className = 'ticker-feedback text-gray';
            }

            fetch(`/api/validate-ticker/?ticker=${encodeURIComponent(ticker)}`)
                .then((res) => res.json())
                .then((data) => {
                    if (data.valid) {
                        if (feedbackDiv) {
                            feedbackDiv.textContent = `${data.name} (${data.currency})`;
                            feedbackDiv.className = 'ticker-feedback text-green';
                        }
                        inputField.dataset.valid = 'true';
                        if (data.first_date && dateInput) {
                            dateInput.min = data.first_date;
                            if (dateFeedbackDiv) {
                                dateFeedbackDiv.textContent = `Dati dal: ${formatDateITA(data.first_date)}`;
                            }
                            if (dateInput.value && dateInput.value < data.first_date) {
                                dateInput.value = data.first_date;
                            }
                        }
                        if (data.suggested_tax_rate && taxSelect && inputField.dataset.userEditedTax !== 'true') {
                            taxSelect.value = data.suggested_tax_rate;
                        }
                    } else {
                        if (feedbackDiv) {
                            feedbackDiv.textContent = data.error || 'Ticker non trovato';
                            feedbackDiv.className = 'ticker-feedback text-red';
                        }
                        inputField.dataset.valid = 'false';
                        if (dateFeedbackDiv) dateFeedbackDiv.textContent = '';
                        if (dateInput) dateInput.removeAttribute('min');
                    }
                    updateButtonState();
                })
                .catch(function () {
                    if (feedbackDiv) {
                        feedbackDiv.textContent = 'Errore di rete durante la verifica';
                        feedbackDiv.className = 'ticker-feedback text-red';
                    }
                    inputField.dataset.valid = 'false';
                    updateButtonState();
                });
        }

        function showAutocomplete(inputField, items) {
            const group = inputField.closest('.form-group');
            const dropdown = group ? group.querySelector('.autocomplete-dropdown') : null;
            if (!dropdown) return;

            if (!items || items.length === 0) {
                dropdown.classList.remove('open');
                dropdown.innerHTML = '';
                return;
            }

            dropdown.innerHTML = '';
            items.forEach(function (item) {
                const option = document.createElement('div');
                option.className = 'autocomplete-item';
                option.innerHTML =
                    `<div class="ac-top"><span class="ac-ticker">${item.ticker}</span><span class="ac-cat">${item.category}</span></div>` +
                    `<div class="ac-name">${item.name}</div>`;

                option.addEventListener('mousedown', function (ev) {
                    ev.preventDefault();
                    inputField.value = item.ticker;
                    inputField.dataset.valid = 'true';

                    const row = inputField.closest('.pac-row-card');
                    const feedbackDiv = row.querySelector('.ticker-feedback');
                    const dateInput = row.querySelector('input[type="date"]');
                    const dateFeedbackDiv = row.querySelector('.date-feedback');
                    const taxSelect = row.querySelector('select[name$="-aliquota_fiscale"]');

                    if (feedbackDiv) {
                        feedbackDiv.textContent = `${item.name} (${item.currency})`;
                        feedbackDiv.className = 'ticker-feedback text-green';
                    }
                    if (item.first_date && dateInput) {
                        dateInput.min = item.first_date;
                        if (dateFeedbackDiv) {
                            dateFeedbackDiv.textContent = `Dati dal: ${formatDateITA(item.first_date)}`;
                        }
                        if (dateInput.value && dateInput.value < item.first_date) {
                            dateInput.value = item.first_date;
                        }
                    }
                    if (taxSelect && item.tax_rate) {
                        taxSelect.value = item.tax_rate;
                    }
                    dropdown.classList.remove('open');
                    updateButtonState();
                });
                dropdown.appendChild(option);
            });
            dropdown.classList.add('open');
        }

        function fetchAutocomplete(inputField) {
            const q = inputField.value.trim();
            fetch(`/api/search-etf/?q=${encodeURIComponent(q)}`)
                .then((res) => res.json())
                .then((data) => showAutocomplete(inputField, data.results || []))
                .catch(function () {});
        }

        if (addBtn && emptyTemplateEl) {
            addBtn.addEventListener('click', function () {
                const formCount = parseInt(totalForms.value, 10);
                const newHtml = emptyTemplateEl.innerHTML.replace(/__prefix__/g, formCount);
                const wrapper = document.createElement('div');
                wrapper.innerHTML = newHtml;
                while (wrapper.firstElementChild) {
                    formList.appendChild(wrapper.firstElementChild);
                }
                updateFormIndices();
                updateButtonState();
            });
        }

        formList.addEventListener('click', function (e) {
            const deleteBtn = e.target.closest('.btn-delete');
            if (deleteBtn) {
                if (formList.querySelectorAll('.pac-row-card').length <= 1) return;
                const row = deleteBtn.closest('.pac-row-card');
                if (row) row.remove();
                updateFormIndices();
                updateButtonState();
            }
        });

        formList.addEventListener('focusin', function (e) {
            if (e.target.classList.contains('ticker-input')) {
                fetchAutocomplete(e.target);
            }
        });

        formList.addEventListener('change', function (e) {
            if (e.target.name && e.target.name.endsWith('-aliquota_fiscale')) {
                const row = e.target.closest('.pac-row-card');
                const tickerInp = row ? row.querySelector('.ticker-input') : null;
                if (tickerInp) tickerInp.dataset.userEditedTax = 'true';
            }
            updateLiveSummary();
        });

        formList.addEventListener('input', function (e) {
            if (e.target.classList.contains('ticker-input')) {
                const inputField = e.target;
                inputField.dataset.valid = 'pending';
                updateButtonState();

                clearTimeout(searchTimers.get(inputField));
                searchTimers.set(inputField, setTimeout(() => fetchAutocomplete(inputField), 180));

                clearTimeout(validateTimers.get(inputField));
                validateTimers.set(inputField, setTimeout(() => validateTicker(inputField), 550));
            } else {
                updateLiveSummary();
            }
        });

        document.addEventListener('click', function (e) {
            if (!e.target.closest('.form-group')) {
                closeAllDropdowns();
            }
        });

        form.addEventListener('submit', function () {
            if (loadingOverlay) loadingOverlay.classList.add('active');
            if (submitBtn) submitBtn.disabled = true;
        });

        // Validazione iniziale sui campi precompilati
        formList.querySelectorAll('.ticker-input').forEach(function (inp) {
            if (inp.value.trim().length > 0) {
                validateTicker(inp);
            }
        });

        updateFormIndices();
        updateButtonState();
    });
})();
