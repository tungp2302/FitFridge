(function () {
  // ----- Elemente -----
  const settingsModal = document.getElementById('settings-modal');
  const addModal = document.getElementById('add-modal');
  const editAmountModal = document.getElementById('edit-amount-modal');
  const calModal = document.getElementById('cal-modal');

  const tabButtons = Array.from(document.querySelectorAll('[data-add-tab]'));
  const newPanel = document.getElementById('add-panel-new');
  const fridgePanel = document.getElementById('add-panel-fridge');

  const protein = document.getElementById('protein_pct');
  const carbs = document.getElementById('carbs_pct');
  const fat = document.getElementById('fat_pct');
  const dailyKcal = document.getElementById('daily_kcal');
  const pValue = document.getElementById('protein_pct_value');
  const cValue = document.getElementById('carbs_pct_value');
  const fValue = document.getElementById('fat_pct_value');
  const pGramValue = document.getElementById('protein_g_value');
  const cGramValue = document.getElementById('carbs_g_value');
  const fGramValue = document.getElementById('fat_g_value');

  const nameInput = document.getElementById('search_name');
  const searchButton = document.getElementById('search-button');
  const scanButton = document.getElementById('scan-button');
  const results = document.getElementById('search-results');
  const selectedDiv = document.getElementById('selected-product');
  const clearSelection = document.getElementById('clear-selection');
  const searchForm = document.getElementById('new-product-form');
  const pendingItemsContainer = document.getElementById('pending-items');
  const selectedPayloadInput = document.getElementById('selected_payload');

  const editAmountTitle = document.getElementById('edit-amount-subtitle');
  const editAmountEntryId = document.getElementById('edit-meal-entry-id');
  const editAmountInput = document.getElementById('edit-meal-amount');

  let currentController = null;
  let pendingItems = [];
  let currentSelection = null;

  const macroWeights = { protein: 4, carbs: 4, fat: 9 };

  // ----- Modale -----
  const openSettings = () => setModalOpen(settingsModal, true);
  const closeSettings = () => setModalOpen(settingsModal, false);
  const closeAdd = () => setModalOpen(addModal, false);
  const closeEditAmountModal = () => setModalOpen(editAmountModal, false);

  function activateAddTab(tabName) {
    tabButtons.forEach((button) => {
      button.classList.toggle('is-active', button.getAttribute('data-add-tab') === tabName);
    });
    newPanel.classList.toggle('is-active', tabName === 'new');
    fridgePanel.classList.toggle('is-active', tabName === 'fridge');
  }

  function openAdd(tabName = 'new') {
    setModalOpen(addModal, true);
    activateAddTab(tabName);
  }

  function openEditAmountModal(entryId, mealName, amount) {
    editAmountEntryId.value = entryId;
    editAmountTitle.textContent = mealName || 'Produkt';
    editAmountInput.value = amount || '';
    setModalOpen(editAmountModal, true);
    setTimeout(() => editAmountInput.focus(), 0);
  }

  // ----- Makro-Slider -----
  function roundWhole(value) {
    return Math.round(Number(value) || 0);
  }

  function gramsFor(slider, pct) {
    const kcal = Number(dailyKcal.value || 0);
    return roundWhole((kcal * pct) / 100 / macroWeights[slider]);
  }

  function updateLabels() {
    const proteinPct = roundWhole(protein.value);
    const carbsPct = roundWhole(carbs.value);
    const fatPct = roundWhole(fat.value);
    pValue.textContent = proteinPct;
    cValue.textContent = carbsPct;
    fValue.textContent = fatPct;
    pGramValue.textContent = gramsFor('protein', proteinPct);
    cGramValue.textContent = gramsFor('carbs', carbsPct);
    fGramValue.textContent = gramsFor('fat', fatPct);
  }

  function distributeRemainder(changedKey, changedValue) {
    const sliders = { protein, carbs, fat };
    const otherKeys = Object.keys(sliders).filter((key) => key !== changedKey);
    const remaining = 100 - changedValue;
    const currentOtherTotal = otherKeys.reduce((sum, key) => sum + roundWhole(sliders[key].value), 0);

    if (remaining <= 0) {
      otherKeys.forEach((key) => {
        sliders[key].value = 0;
      });
      return;
    }

    if (currentOtherTotal <= 0) {
      const base = Math.floor(remaining / otherKeys.length);
      let leftover = remaining - base * otherKeys.length;
      otherKeys.forEach((key) => {
        sliders[key].value = base + (leftover > 0 ? 1 : 0);
        if (leftover > 0) leftover -= 1;
      });
      return;
    }

    const provisional = otherKeys.map((key) => {
      const oldValue = roundWhole(sliders[key].value);
      const exact = (remaining * oldValue) / currentOtherTotal;
      const floorValue = Math.floor(exact);
      return { key, floorValue, remainder: exact - floorValue };
    });

    let missing = remaining - provisional.reduce((sum, entry) => sum + entry.floorValue, 0);
    provisional.sort((a, b) => b.remainder - a.remainder);
    provisional.forEach((entry) => {
      sliders[entry.key].value = entry.floorValue + (missing > 0 ? 1 : 0);
      if (missing > 0) missing -= 1;
    });
  }

  function syncFrom(sourceKey) {
    const source = { protein, carbs, fat }[sourceKey];
    const nextValue = Math.max(0, Math.min(100, roundWhole(source.value)));
    source.value = nextValue;
    distributeRemainder(sourceKey, nextValue);
    updateLabels();
  }

  // ----- Produktsuche / Pending-Liste -----
  function setLoading() {
    results.style.display = 'block';
    results.innerHTML = `<div class="search-loading"><div class="search-loading__spinner"></div><div>Produkte werden gesucht…</div></div>`;
  }

  function clearSearchSelection() {
    selectedDiv.style.display = 'none';
    selectedDiv.innerHTML = '';
    results.style.display = 'none';
    results.innerHTML = '';
    currentSelection = null;
  }

  function updatePendingItems() {
    if (!pendingItems.length) {
      pendingItemsContainer.innerHTML = '<div class="pending-items__empty muted">Noch nichts zur Liste hinzugefuegt.</div>';
      return;
    }

    pendingItemsContainer.innerHTML = pendingItems.map((item, index) => `
      <div class="pending-item" data-index="${index}">
        <div class="pending-item__main">
          <strong>${escHtml(item.name || '(no name)')}</strong>
          <div class="pending-item__meta">${item.brand ? escHtml(item.brand) + ' · ' : ''}${escHtml(item.kcal_per_100g || '')} kcal / 100g${item.ai ? ' · AI' : ''}</div>
        </div>
        <div class="pending-item__controls">
          <div class="pending-item__field">
            <label>amount</label>
            <input type="number" step="0.1" min="0" class="pending-item__amount" value="${escHtml(item.amount || 100)}" aria-label="Amount for ${escHtml(item.name || 'product')}">
          </div>
          <div class="pending-item__field">
            <label>uebrig</label>
            <input type="number" step="0.1" min="0" class="pending-item__remaining" value="${escHtml(item.remaining_amount || '')}" aria-label="Remaining for ${escHtml(item.name || 'product')}">
          </div>
          <button type="button" class="clear-x-button pending-item__remove" aria-label="Remove ${escHtml(item.name || 'product')}">×</button>
        </div>
      </div>
    `).join('');

    Array.from(pendingItemsContainer.querySelectorAll('.pending-item')).forEach((element) => {
      const index = Number(element.getAttribute('data-index'));
      const amountField = element.querySelector('.pending-item__amount');
      const remainingField = element.querySelector('.pending-item__remaining');
      const removeButton = element.querySelector('.pending-item__remove');
      amountField.addEventListener('input', () => {
        pendingItems[index].amount = Number(amountField.value) || 0;
      });
      remainingField.addEventListener('input', () => {
        pendingItems[index].remaining_amount = Number(remainingField.value) || 0;
      });
      removeButton.addEventListener('click', () => {
        pendingItems.splice(index, 1);
        updatePendingItems();
      });
    });
  }

  function addCurrentSelectionToPendingList() {
    if (!currentSelection) return;
    pendingItems.push({ ...currentSelection, amount: 100, remaining_amount: 0 });
    updatePendingItems();
    clearSearchSelection();
  }

  function syncHiddenPayload() {
    selectedPayloadInput.value = JSON.stringify(pendingItems);
  }

  function render(items) {
    if (!items || items.length === 0) {
      results.style.display = 'none';
      results.innerHTML = '';
      return;
    }

    results.style.display = 'block';
    results.innerHTML = items.map((item, index) => `
      <div class="search-item" data-idx="${index}">
        <div class="search-item__top">
          <strong>${escHtml(item.name || '(no name)')}</strong>
          <span class="search-item__badge ${item.ai ? 'is-ai' : 'is-off'}">${item.ai ? 'AI' : 'OFF'}</span>
        </div>
        <div class="search-item__brand muted">${escHtml(item.brand || '')}</div>
        <small>${item.ai ? 'AI estimate' : 'Open Food Facts'} · ${escHtml(item.kcal_per_100g || '')} kcal/100g</small>
      </div>
    `).join('');

    Array.from(results.querySelectorAll('.search-item')).forEach((element) => {
      element.addEventListener('click', () => {
        const item = items[Number(element.getAttribute('data-idx'))];
        currentSelection = {
          name: item.name || '(no name)',
          brand: item.brand || '',
          barcode: item.barcode || '',
          kcal_per_100g: Number(item.kcal_per_100g || 0),
          protein_per_100g: Number(item.protein_per_100g || 0),
          fat_per_100g: Number(item.fat_per_100g || 0),
          carbs_per_100g: Number(item.carbs_per_100g || 0),
          unit: item.unit || 'g',
          ai: Boolean(item.ai),
        };
        selectedDiv.innerHTML = `
          <div class="selected-product-panel__title">
            <strong>${escHtml(currentSelection.name)}</strong>
            <span class="selected-product-panel__badge ${currentSelection.ai ? 'is-ai' : 'is-off'}">${currentSelection.ai ? 'AI' : 'OFF'}</span>
          </div>
          <div class="selected-product-panel__meta">${currentSelection.brand ? escHtml(currentSelection.brand) + ' · ' : ''}${currentSelection.ai ? 'AI estimate' : 'Open Food Facts'} · ${escHtml(currentSelection.kcal_per_100g || '')} kcal / 100g</div>
          <div class="selected-product-panel__actions">
            <button type="button" class="search-action-button" id="log-selected-button">Add</button>
            <button type="button" class="clear-x-button" id="reset-selected-button" aria-label="Clear selected product">×</button>
          </div>
        `;
        selectedDiv.style.display = 'block';
        results.style.display = 'none';

        document.getElementById('log-selected-button').addEventListener('click', addCurrentSelectionToPendingList);
        document.getElementById('reset-selected-button').addEventListener('click', clearSearchSelection);
      });
    });
  }

  function doSearch(query) {
    setLoading();
    if (currentController) {
      currentController.abort();
    }
    currentController = new AbortController();
    fetch(`/api/products/search?q=${encodeURIComponent(query)}`, { signal: currentController.signal })
      .then((response) => response.json())
      .then((items) => {
        currentController = null;
        render(items);
      })
      .catch((error) => {
        if (error && error.name === 'AbortError') return;
        results.innerHTML = `<div style="padding:.75rem;color:#666;">Fehler bei der Suche</div>`;
      });
  }

  function runSearch() {
    const query = nameInput.value.trim();
    if (query) doSearch(query);
  }

  // ----- Verdrahtung -----
  document.getElementById('open-settings')?.addEventListener('click', openSettings);
  document.getElementById('open-add')?.addEventListener('click', () => openAdd('new'));
  document.getElementById('close-settings').addEventListener('click', closeSettings);
  document.getElementById('cancel-settings').addEventListener('click', closeSettings);
  document.getElementById('settings-modal-backdrop').addEventListener('click', closeSettings);
  document.getElementById('close-add').addEventListener('click', closeAdd);
  document.getElementById('add-modal-backdrop').addEventListener('click', closeAdd);
  tabButtons.forEach((button) => {
    button.addEventListener('click', () => activateAddTab(button.getAttribute('data-add-tab')));
  });

  protein.addEventListener('input', () => syncFrom('protein'));
  carbs.addEventListener('input', () => syncFrom('carbs'));
  fat.addEventListener('input', () => syncFrom('fat'));
  dailyKcal.addEventListener('input', updateLabels);
  updateLabels();

  searchButton.addEventListener('click', runSearch);
  scanButton.addEventListener('click', () => {
    window.startBarcodeScan((code) => {
      nameInput.value = code;
      doSearch(code);
    });
  });
  nameInput.addEventListener('input', clearSearchSelection);
  nameInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      runSearch();
    }
  });
  clearSelection.addEventListener('click', clearSearchSelection);

  Array.from(document.querySelectorAll('.today-food-card__edit')).forEach((button) => {
    button.addEventListener('click', () => {
      openEditAmountModal(
        button.getAttribute('data-meal-id') || '',
        button.getAttribute('data-meal-name') || 'Produkt',
        button.getAttribute('data-current-amount') || ''
      );
    });
  });

  document.getElementById('close-edit-amount').addEventListener('click', closeEditAmountModal);
  document.getElementById('cancel-edit-amount').addEventListener('click', closeEditAmountModal);
  document.getElementById('edit-amount-backdrop').addEventListener('click', closeEditAmountModal);
  editAmountInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      const parsed = Number(editAmountInput.value);
      if (!Number.isFinite(parsed) || parsed <= 0) {
        event.preventDefault();
      }
    }
  });

  searchForm.addEventListener('submit', (event) => {
    if (currentSelection) {
      addCurrentSelectionToPendingList();
    }
    syncHiddenPayload();
    if (!pendingItems.length) {
      event.preventDefault();
    }
  });

  updatePendingItems();

  // ----- Kalender / Verlauf -----
  const MONTHS_DE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  const DAYS_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth() + 1;
  let trackedDays = new Set();
  let selectedDate = null;
  let calInitialized = false;

  const openCalBtn = document.getElementById('open-cal');
  const calTitle = document.getElementById('cal-title');
  const calGrid = document.getElementById('cal-grid');
  const calDetail = document.getElementById('cal-detail');

  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  function openCal() {
    setModalOpen(calModal, true);
    if (!calInitialized) {
      calInitialized = true;
      fetchTrackedDays(viewYear, viewMonth);
    }
  }

  const closeCal = () => setModalOpen(calModal, false);

  function fetchTrackedDays(year, month) {
    fetch(`/api/meal-tracker/tracked-days?year=${year}&month=${month}`)
      .then((r) => r.json())
      .then((days) => {
        trackedDays = new Set(days);
        renderCalendar();
      });
  }

  function renderCalendar() {
    calTitle.textContent = `${MONTHS_DE[viewMonth - 1]} ${viewYear}`;

    const firstWeekday = (new Date(viewYear, viewMonth - 1, 1).getDay() + 6) % 7;
    const daysInMonth = new Date(viewYear, viewMonth, 0).getDate();

    let html = DAYS_SHORT.map((d) => `<div class="cal-weekday">${d}</div>`).join('');
    for (let i = 0; i < firstWeekday; i++) html += `<div class="cal-day is-empty"></div>`;
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${viewYear}-${String(viewMonth).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      let cls = 'cal-day';
      if (trackedDays.has(d)) cls += ' is-tracked';
      if (dateStr === todayStr) cls += ' is-today';
      if (dateStr === selectedDate) cls += ' is-selected';
      html += `<div class="${cls}" data-date="${dateStr}">${d}</div>`;
    }

    calGrid.innerHTML = html;
    calGrid.querySelectorAll('.cal-day.is-tracked').forEach((el) => {
      el.addEventListener('click', () => selectDay(el.getAttribute('data-date')));
    });
  }

  function selectDay(dateStr) {
    selectedDate = dateStr;
    renderCalendar();
    calDetail.style.display = 'block';
    calDetail.innerHTML = '<p class="muted" style="padding:.5rem 0 0;">Wird geladen…</p>';
    fetch(`/api/meal-tracker/day/${dateStr}`)
      .then((r) => r.json())
      .then((data) => renderDayDetail(dateStr, data));
  }

  function renderDayDetail(dateStr, data) {
    const { meals, totals } = data;
    const [y, m, d] = dateStr.split('-');
    const label = `${parseInt(d)}. ${MONTHS_DE[parseInt(m) - 1]} ${y}`;

    const totalsHtml = `
      <div class="cal-detail__totals">
        <div class="cal-detail__macro">${Math.round(totals.kcal)} <span>kcal</span></div>
        <div class="cal-detail__macro">${Math.round(totals.protein_g)} g <span>protein</span></div>
        <div class="cal-detail__macro">${Math.round(totals.carbs_g)} g <span>carbs</span></div>
        <div class="cal-detail__macro">${Math.round(totals.fat_g)} g <span>fat</span></div>
      </div>`;

    const mealsHtml = meals.length === 0
      ? '<p class="muted">Keine Einträge.</p>'
      : `<div class="today-foods-list">${meals.map((meal) => `
          <div class="today-food-card">
            <div class="today-food-card__main">
              <strong>${escHtml(meal.meal_name)}</strong>
              <div class="today-food-card__meta">${meal.amount ?? ''} ${escHtml(meal.unit ?? '')}</div>
              <div class="today-food-card__nutri">${Math.round(meal.protein_g)} p / ${Math.round(meal.carbs_g)} c / ${Math.round(meal.fat_g)} f</div>
            </div>
            <div class="today-food-card__side">
              <div class="today-food-card__kcal">${Math.round(meal.kcal)} kcal</div>
            </div>
          </div>`).join('')}</div>`;

    calDetail.innerHTML = `<hr style="margin:.75rem 0;"><div class="cal-detail__date">${label}</div>${totalsHtml}${mealsHtml}`;
  }

  openCalBtn.addEventListener('click', openCal);
  document.getElementById('close-cal').addEventListener('click', closeCal);
  document.getElementById('cal-modal-backdrop').addEventListener('click', closeCal);

  document.getElementById('cal-prev').addEventListener('click', () => {
    viewMonth--; if (viewMonth < 1) { viewMonth = 12; viewYear--; }
    selectedDate = null; calDetail.style.display = 'none';
    fetchTrackedDays(viewYear, viewMonth);
  });

  document.getElementById('cal-next').addEventListener('click', () => {
    viewMonth++; if (viewMonth > 12) { viewMonth = 1; viewYear++; }
    selectedDate = null; calDetail.style.display = 'none';
    fetchTrackedDays(viewYear, viewMonth);
  });

  // ----- Gemeinsamer Escape-Handler -----
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (settingsModal.classList.contains('is-open')) closeSettings();
    if (addModal.classList.contains('is-open')) closeAdd();
    if (calModal.classList.contains('is-open')) closeCal();
  });
})();
