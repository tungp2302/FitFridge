let requestToken = 0;

function escHtml(value){
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function readGoalValue(id){
  const raw = document.getElementById(id).value.trim();
  if(raw === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function buildDailyGoal(){
  const dailyGoal = {};
  const protein = readGoalValue('protein');
  const kcal = readGoalValue('kcal');
  const carbs = readGoalValue('carbs');
  const fat = readGoalValue('fat');

  if(protein !== null) dailyGoal.protein = protein;
  if(kcal !== null) dailyGoal.kcal = kcal;
  if(carbs !== null) dailyGoal.carbs = carbs;
  if(fat !== null) dailyGoal.fat = fat;

  return dailyGoal;
}

function freestyleMacroLabel(macros){
  if(!macros) return 'Macros n/a';
  const parts = [];
  if(macros.kcal != null) parts.push(`${Math.round(macros.kcal)} kcal`);
  if(macros.protein != null) parts.push(`${Math.round(macros.protein)}g protein`);
  if(macros.carbs != null) parts.push(`${Math.round(macros.carbs)}g carbs`);
  if(macros.fat != null) parts.push(`${Math.round(macros.fat)}g fat`);
  return parts.length ? parts.join(' · ') : 'Macros n/a';
}

let currentRecipes = [];
let selectedIdx = 0;
let loadingMore = false;

const recipeStateLabel = (recipe) => recipe.warning === true ? 'Warnung' : 'LLM';

// Fuellt die rechte Detailspalte mit dem gewaehlten Rezept.
function renderDetail(recipe){
  const isWarning = recipe.warning === true;
  const ingredients = recipe.ingredients || [];
  const instructions = recipe.instructions || [];

  document.getElementById('detail-title').textContent = recipe.title || 'Freestyle-Rezept';
  document.getElementById('detail-subtitle').textContent = isWarning ? 'LLM-Anbindung oder Modellleistung prüfen' : 'Aus deinem Kühlschrank generiert';
  document.getElementById('detail-body').innerHTML = `
    <div class="recipe-meta" style="margin-bottom:10px;">
      <span>${freestyleMacroLabel(recipe.estimated_macros)}</span>
      <span>${recipeStateLabel(recipe)}</span>
    </div>
    <div style="margin-bottom:10px;">${(recipe.used_fridge_items || []).map(item => `<span class="pill">${escHtml(item)}</span>`).join('') || '<span class="muted">No fridge items used</span>'}</div>
    <div class="muted-box" style="margin-bottom:10px;">
      <strong>Warum</strong>
      <p style="white-space:pre-wrap;margin:.5rem 0 0;">${escHtml(recipe.why_this_works || 'Keine Begründung verfügbar.')}</p>
    </div>
    <div class="muted-box" style="margin-bottom:10px;">
      <strong>Zutaten</strong>
      <pre style="white-space:pre-wrap;margin:.5rem 0 0;">${ingredients.length ? ingredients.map(escHtml).join('\n') : 'Keine Zutaten angegeben.'}</pre>
    </div>
    <div class="muted-box">
      <strong>Zubereitung</strong>
      <pre style="white-space:pre-wrap;margin:.5rem 0 0;">${instructions.length ? instructions.map((step, idx) => `${idx + 1}. ${escHtml(step)}`).join('\n\n') : 'Keine Zubereitung angegeben.'}</pre>
    </div>
  `;
}

function normTitle(title){
  return (title || '').trim().toLowerCase();
}

// Zeichnet die Vorschlagskarten (plus optional einen "lädt"-Hinweis).
function renderRail(){
  const rail = document.getElementById('rail');
  let html = currentRecipes.map((recipe, idx) => `
    <article class="recipe-card${idx === selectedIdx ? ' active' : ''}" data-idx="${idx}" style="cursor:pointer;">
      <div class="recipe-meta">
        <strong>${escHtml(recipe.title || 'Freestyle-Rezept')}</strong>
        <span>${recipeStateLabel(recipe)}</span>
      </div>
      <p class="muted" style="margin:.35rem 0 .5rem;">${freestyleMacroLabel(recipe.estimated_macros)}</p>
      <div>${(recipe.used_fridge_items || []).map(item => `<span class="pill">${escHtml(item)}</span>`).join('') || '<span class="muted">No fridge items used</span>'}</div>
    </article>
  `).join('');
  if(loadingMore){
    html += '<div class="muted-box" id="more-loading">Weitere Vorschläge werden geladen…</div>';
  }
  if(!html){
    html = '<div class="muted-box">Kein Rezept erhalten.</div>';
  }
  rail.innerHTML = html;
  Array.from(rail.querySelectorAll('.recipe-card')).forEach(card => {
    card.addEventListener('click', () => selectRecipe(Number(card.getAttribute('data-idx'))));
  });
}

// Markiert die angetippte Karte und zeigt ihre Details.
function selectRecipe(idx){
  selectedIdx = idx;
  Array.from(document.querySelectorAll('.recipe-card')).forEach(card => {
    card.classList.toggle('active', Number(card.getAttribute('data-idx')) === idx);
  });
  if(currentRecipes[idx]) renderDetail(currentRecipes[idx]);
}

async function postRecipes(body){
  const response = await fetch('/asaai/recipes/freestyle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if(!response.ok) throw new Error(data.error || 'Freestyle generation failed');
  return data.recipes || (data.recipe ? [data.recipe] : []);
}

async function loadFreestyleRecipe(){
  const dailyGoal = buildDailyGoal();
  const recipeCategory = document.getElementById('recipe-category').value.trim();
  const status = document.getElementById('status');
  const btn = document.getElementById('run-freestyle');
  const token = ++requestToken;

  currentRecipes = [];
  selectedIdx = 0;
  loadingMore = false;
  btn.disabled = true;
  status.textContent = 'Erster Vorschlag wird erstellt…';

  try {
    // Phase 1: ein schneller Vorschlag, sofort anzeigen.
    const first = await postRecipes({ daily_goal: dailyGoal, recipe_category: recipeCategory, count: 1 });
    if(token !== requestToken) return;

    currentRecipes = first;
    selectedIdx = 0;
    const lead = currentRecipes[0] || {};
    const degraded = lead.warning === true;
    loadingMore = !degraded;            // bei LLM-Problemen keine weiteren laden
    renderRail();
    if(currentRecipes.length) selectRecipe(0);
    btn.disabled = false;               // erstes Rezept ist schon nutzbar
    status.textContent = degraded ? recipeStateLabel(lead) : '1 Vorschlag · weitere laden…';
    if(degraded) return;

    // Phase 2: zwei weitere im Hintergrund nachladen.
    const exclude = currentRecipes.map(r => r.title).filter(Boolean);
    let more = [];
    try {
      more = await postRecipes({ daily_goal: dailyGoal, recipe_category: recipeCategory, count: 2, exclude });
    } catch(e){ more = []; }
    if(token !== requestToken) return;

    const seen = new Set(currentRecipes.map(r => normTitle(r.title)));
    for(const recipe of more){
      if(recipe.warning) continue;
      if(seen.has(normTitle(recipe.title))) continue;
      seen.add(normTitle(recipe.title));
      currentRecipes.push(recipe);
    }
    loadingMore = false;
    renderRail();
    selectRecipe(selectedIdx);          // aktuelle Auswahl beibehalten
    status.textContent = `${currentRecipes.length} Vorschlag(e) · tippe zum Anzeigen`;
  } catch (error) {
    if(token === requestToken){
      status.textContent = error.message || 'Freestyle generation failed';
      document.getElementById('rail').innerHTML = `<div class="muted-box">${escHtml(error.message || 'Freestyle generation failed. Please try again.')}</div>`;
    }
  } finally {
    if(token === requestToken) btn.disabled = false;
  }
}

document.getElementById('run-freestyle').addEventListener('click', loadFreestyleRecipe);
