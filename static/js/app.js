/**
 * Budget Tracker — Interactive features.
 * Month navigation, transaction filtering, category correction.
 */

// ===== Month Navigation =====

function initMonthNav(months, currentMonth) {
    const prevBtn = document.getElementById('prev-month');
    const nextBtn = document.getElementById('next-month');
    const titleEl = document.getElementById('current-month');

    if (!prevBtn || !nextBtn || !titleEl) return;

    // Format month for display
    titleEl.textContent = formatMonth(currentMonth);

    const idx = months.indexOf(currentMonth);
    prevBtn.disabled = idx >= months.length - 1;
    nextBtn.disabled = idx <= 0;

    prevBtn.addEventListener('click', function() {
        if (idx < months.length - 1) navigateMonth(months[idx + 1]);
    });
    nextBtn.addEventListener('click', function() {
        if (idx > 0) navigateMonth(months[idx - 1]);
    });
}

function navigateMonth(month) {
    const url = new URL(window.location);
    url.searchParams.set('month', month);
    window.location.href = url.toString();
}

function formatMonth(yyyymm) {
    const [y, m] = yyyymm.split('-');
    const names = ['', 'Janvier', 'Fevrier', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Aout', 'Septembre', 'Octobre', 'Novembre', 'Decembre'];
    return names[parseInt(m)] + ' ' + y;
}


// ===== Transaction Filtering =====

function initFilters() {
    const catFilter = document.getElementById('filter-category');
    const searchFilter = document.getElementById('filter-search');
    if (!catFilter && !searchFilter) return;

    function applyFilters() {
        const catId = catFilter ? catFilter.value : '';
        const search = searchFilter ? searchFilter.value.toLowerCase() : '';
        const rows = document.querySelectorAll('.tx-row');
        let visible = 0;

        rows.forEach(function(row) {
            const matchCat = !catId || row.dataset.category === catId;
            const matchSearch = !search || row.dataset.libelle.includes(search);
            row.style.display = (matchCat && matchSearch) ? '' : 'none';
            if (matchCat && matchSearch) visible++;
        });

        const countEl = document.getElementById('tx-count');
        if (countEl) countEl.textContent = visible + ' transaction' + (visible !== 1 ? 's' : '');
    }

    if (catFilter) catFilter.addEventListener('change', applyFilters);
    if (searchFilter) searchFilter.addEventListener('input', applyFilters);
}


// ===== Category Correction =====

let selectedTxId = null;

function initCategoryCorrection() {
    const overlay = document.getElementById('modal-overlay');
    const cancelBtn = document.getElementById('modal-cancel');
    const saveBtn = document.getElementById('modal-save');
    const catSelect = document.getElementById('modal-category-select');
    const txInfo = document.getElementById('modal-tx-info');

    if (!overlay) return;

    // Open modal on category badge click
    document.querySelectorAll('.category-badge').forEach(function(badge) {
        badge.addEventListener('click', function() {
            selectedTxId = this.dataset.txId;
            const row = this.closest('.tx-row');
            const libelle = row ? row.querySelector('.tx-libelle').textContent : '';
            txInfo.textContent = libelle;
            catSelect.value = this.dataset.currentCat;
            overlay.style.display = 'flex';
        });
    });

    // Close modal
    cancelBtn.addEventListener('click', function() {
        overlay.style.display = 'none';
        selectedTxId = null;
    });
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.style.display = 'none';
            selectedTxId = null;
        }
    });

    // Save category
    saveBtn.addEventListener('click', function() {
        if (!selectedTxId) return;
        const newCatId = catSelect.value;
        saveBtn.disabled = true;
        saveBtn.textContent = '...';

        fetch('/api/transactions/' + selectedTxId + '/category', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category_id: parseInt(newCatId) }),
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.ok) {
                // Update row in table
                const badge = document.querySelector('.category-badge[data-tx-id="' + selectedTxId + '"]');
                if (badge && data.transaction) {
                    badge.innerHTML = data.transaction.category_icon + ' ' + data.transaction.category_name;
                    badge.style.borderColor = data.transaction.category_color;
                    badge.style.color = data.transaction.category_color;
                    badge.dataset.currentCat = data.transaction.category_id;
                    var row = badge.closest('.tx-row');
                    if (row) row.dataset.category = data.transaction.category_id;
                }
                showToast('Categorie mise a jour');
            } else {
                showToast('Erreur: ' + (data.error || 'unknown'), true);
            }
        })
        .catch(function() {
            showToast('Erreur reseau', true);
        })
        .finally(function() {
            overlay.style.display = 'none';
            selectedTxId = null;
            saveBtn.disabled = false;
            saveBtn.textContent = 'Enregistrer';
        });
    });
}


// ===== Toast Notification =====

function showToast(message, isError) {
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' error' : '');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}
