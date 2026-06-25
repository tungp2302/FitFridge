let requestToken = 0;

const jsonReq = (method, body) =>
  ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

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
let savedRecipes = [];
let selectedIdx = 0;
let loadingMore = false;

// Vorschläge + gespeicherte Rezepte als eine indizierbare Liste fürs Rail.
const allRecipes = () => currentRecipes.concat(savedRecipes);

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

// Eine Rezeptkarte; idx zeigt in die kombinierte Liste allRecipes().
function cardHtml(recipe, idx){
  return `
    <article class="recipe-card${idx === selectedIdx ? ' active' : ''}" data-idx="${idx}" style="cursor:pointer;">
      <div class="recipe-meta">
        <strong>${escHtml(recipe.title || 'Freestyle-Rezept')}</strong>
        <span>${recipeStateLabel(recipe)}</span>
      </div>
      <p class="muted" style="margin:.35rem 0 .5rem;">${freestyleMacroLabel(recipe.estimated_macros)}</p>
      <div>${(recipe.used_fridge_items || []).map(item => `<span class="pill">${escHtml(item)}</span>`).join('') || '<span class="muted">No fridge items used</span>'}</div>
      ${recipe.id ? `<div style="margin-top:.4rem;display:flex;gap:.6rem;">
        <a href="#" data-rename="${recipe.id}" class="muted">Umbenennen</a>
        <a href="#" data-delete="${recipe.id}" class="muted">Löschen</a>
      </div>` : ''}
    </article>`;
}

function railClick(e){
  const rename = e.target.closest('[data-rename]');
  const del = e.target.closest('[data-delete]');
  if(rename){ e.preventDefault(); renameSaved(Number(rename.dataset.rename)); return; }
  if(del){ e.preventDefault(); deleteSaved(Number(del.dataset.delete)); return; }
  const card = e.target.closest('.recipe-card');
  if(card) selectRecipe(Number(card.getAttribute('data-idx')));
}

// Zeichnet Vorschläge (#rail) und die eigene Gespeichert-Sektion (#saved-rail).
function renderRail(){
  if(currentRecipes.length || loadingMore){
    const rail = document.getElementById('rail');
    let html = currentRecipes.map(cardHtml).join('');
    if(loadingMore) html += '<div class="muted-box" id="more-loading">Weitere Vorschläge werden geladen…</div>';
    rail.innerHTML = html || '<div class="muted-box">Kein Rezept erhalten.</div>';
    rail.onclick = railClick;
  }

  document.getElementById('saved-title').style.display = savedRecipes.length ? '' : 'none';
  const savedRail = document.getElementById('saved-rail');
  savedRail.innerHTML = savedRecipes.map((r, i) => cardHtml(r, currentRecipes.length + i)).join('');
  savedRail.onclick = railClick;
}

async function mutateSaved(url, options){
  const response = await fetch(url, options);
  if(!response.ok) return;
  await loadSavedRecipes(true);
  selectRecipe(Math.min(selectedIdx, allRecipes().length - 1));
}

const deleteSaved = (id) =>
  confirm('Rezept löschen?') && mutateSaved(`/asaai/recipes/saved/${id}`, { method: 'DELETE' });

function renameSaved(id){
  const title = prompt('Neuer Name:');
  if(title) mutateSaved(`/asaai/recipes/saved/${id}`, jsonReq('PATCH', { title }));
}

// Markiert die angetippte Karte und zeigt ihre Details.
function selectRecipe(idx){
  selectedIdx = idx;
  Array.from(document.querySelectorAll('.recipe-card')).forEach(card => {
    card.classList.toggle('active', Number(card.getAttribute('data-idx')) === idx);
  });
  const recipe = allRecipes()[idx];
  if(recipe) renderDetail(recipe);
  // Speichern nur für frische Vorschläge, nicht für bereits gespeicherte.
  document.getElementById('save-recipe').style.display =
    recipe && !recipe.warning && idx < currentRecipes.length ? '' : 'none';
}

async function loadSavedRecipes(force){
  try {
    const response = await fetch('/asaai/recipes/saved');
    if(!response.ok) return;
    savedRecipes = (await response.json()).recipes || [];
    if(force || savedRecipes.length) renderRail();   // sonst den Start-Hinweis stehen lassen
  } catch(e){ /* ponytail: gespeicherte Rezepte sind optional */ }
}

function saveCurrentRecipe(){
  const recipe = currentRecipes[selectedIdx];
  if(recipe) mutateSaved('/asaai/recipes/saved', jsonReq('POST', recipe));
}

async function postRecipes(body){
  const response = await fetch('/asaai/recipes/freestyle', jsonReq('POST', body));
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
document.getElementById('save-recipe').addEventListener('click', saveCurrentRecipe);
loadSavedRecipes();
