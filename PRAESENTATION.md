# FitFridge – Abschlusspräsentation (Folienskript)

> **Kopfzeile (alle Folien):** FitFridge – KI-gestützter Rezeptplaner · ASaAI
> **Fußzeile (alle Folien):** Autoren · Folie X / N · Quelle(n) der Folie
> **Hinweis zur Nutzung:** Eine Überschrift = eine Folie. „FOLIE" = Inhalt auf der Folie, „SPRECHTEXT" = was ihr dazu sagt, „ABB./QUELLE" = Beleg in der Fußzeile. Platzhalter `‹…›` vor der Abgabe füllen.

---

## Folie 1 — Deckblatt

**FOLIE**
- Titel: **FitFridge – Makro-genaue Rezeptgenerierung aus Kühlschrank-Beständen mit einem lokalen Large Language Model (LLM)**
- Untertitel: Vergleich von ungeprüfter LLM-Ausgabe vs. validierter, nachgerechneter Ausgabe
- Autoren: ‹Vorname Nachname› (Matr.-Nr. ‹…›), ‹Vorname Nachname› (Matr.-Nr. ‹…›)
- Kurs: ASaAI (Angewandte Systeme & angewandte AI)
- Lehrende: Prof. ‹Putzar›, ‹Balzer›, ‹Maute›  *(akademische Titel vor Abgabe prüfen)*
- Datum: ‹Abgabedatum›

**SPRECHTEXT:** Kurz vorstellen, Projektname und die zentrale Idee in einem Satz: „Aus dem, was im Kühlschrank liegt, makro-genaue Rezepte erzeugen — lokal, ohne Cloud."

---

## Folie 2 — Inhaltsübersicht *(optional, aber empfohlen)*

**FOLIE** (Agenda, nummeriert)
1. Motivation & Forschungsfrage
2. Stand der Forschung / vergleichbare Ansätze
3. Datengrundlage (OpenFoodFacts + Seed)
4. Systemarchitektur
5. Algorithmus: LLM-Prompting + Validierung + Makro-Reparatur
6. Einordnung als adaptives System (Regelkreise)
7. Analyse / Ergebnisse
8. Lessons Learned
9. Fazit & Ausblick

**SPRECHTEXT:** Roter Faden ansagen, Dauer grob nennen.

---

## Folie 3 — Motivation

**FOLIE**
- Problem: „Was koche ich aus dem, was da ist — und wie treffe ich dabei meine Tagesziele (kcal/Protein/Carbs/Fett)?"
- Manuelle Rezeptsuche ignoriert den realen Bestand und die Makroverteilung.
- Reine LLM-Rezepte klingen plausibel, aber **die genannten Nährwerte stimmen oft nicht** (Modell „rät" Zahlen).
- Ziel der Anwendung: Kühlschrank verwalten + Mahlzeiten tracken + Rezepte vorschlagen, die rechnerisch zum Ziel passen.

**SPRECHTEXT:** Den Schmerzpunkt betonen: LLM-Zahlen sind nicht vertrauenswürdig → genau das ist der Aufhänger der Arbeit.
**ABB.:** Screenshot Dashboard (Abb. 1).

---

## Folie 4 — Projektziel & Forschungsfrage

**FOLIE**
- **Zweck der Anwendung** (≠ Ziel der Projektarbeit): ein lauffähiger lokaler Rezeptplaner.
- **Ziel der Projektarbeit (Forschungsfrage):**
  > „Lässt sich die Nährwert-Genauigkeit LLM-generierter Rezepte signifikant verbessern, wenn die Modellzahlen **nicht** übernommen, sondern aus den Gramm-Mengen **selbst nachgerechnet** und Mengen per regelbasierter Reparatur an Zielwerte angepasst werden — verglichen mit der ungeprüften LLM-Ausgabe?"
- Teil-Fragen: (a) Wie oft liefert ein lokales LLM direkt valide, zielkonforme Rezepte? (b) Wie viel holt eine Validierungs-/Reparaturschicht heraus?
- **Bezug adaptive Systeme:** Die Reparatur-/Retry-Schicht ist ein **geschlossener Regelkreis** (Soll-/Istwert-Vergleich, Stellgröße) — vertieft in Folie 14.

**SPRECHTEXT:** Klar trennen: Kurs ist nicht das Ziel; das Ziel ist die Beantwortung der Vergleichsfrage „ungeprüft vs. nachgerechnet".

---

## Folie 5 — Stand der Forschung / vergleichbare Ansätze

**FOLIE**
- **Retrieval-/Constraint-basierte Rezeptempfehlung** (klassisch, ohne LLM): exakt, aber unflexibel bei freier Zutatenkombination. [Q1]
- **LLM-Rezeptgeneratoren / Chatbots** (z. B. cloudbasierte Assistenten): sehr flexibel, aber Nährwerte halluziniert, kein Bestandsbezug. [Q2]
- **Tool-/Function-Calling & strukturierte Ausgabe** (JSON-Mode): Grundlage unserer Architektur. [Q3]
- **Unsere Abgrenzung:** LLM nur als *Vorschlags-Generator*; **Ground Truth = eigene Berechnung** aus /100g-Werten; zusätzlich **regelbasierte Plausibilitätsprüfung** und **Makro-Reparatur**.

**SPRECHTEXT:** Wir bauen auf JSON-Mode-LLMs auf, lösen aber deren Kernschwäche (falsche Zahlen) durch eine nachgelagerte Rechen-/Reparaturschicht. Quellen in der Fußzeile.
**QUELLE:** [Q1]–[Q3] im Literaturverzeichnis.

---

## Folie 6 — Datengrundlage I: Quellen

**FOLIE**
- **OpenFoodFacts (OFF)** – offene Lebensmitteldatenbank, Zugriff per REST (`/api/v2`). Liefert Nährwerte pro 100 g, Marke, Packungsmenge. [Q4]
- **Lokaler Seed-Datensatz** – 24 kuratierte Demo-Produkte, bewusst gesplittet in **herzhaft** (Hähnchen, Steak, Reis, Spaghetti, Kartoffeln, Gemüse, Öl) und **süß** (Haferflocken, Banane, Honig, Mandeln, Whey …).
- **KI-Nährwertschätzung** als Fallback für Produkte ohne Barcode/OFF-Eintrag (LLM schätzt /100g).
- Warum dieser Seed? Reproduzierbare Test-„Spielwiese", die beide Rezeptarten (süß/herzhaft) abdeckt.

**SPRECHTEXT:** Begründen, warum nicht nur OFF: Offline-Demo, deterministische Tests, abgedeckte Kategorien.
**QUELLE:** [Q4] OpenFoodFacts.

---

## Folie 7 — Datengrundlage II: Quantitative Beschreibung

**FOLIE** (Tabelle 1)

| Merkmal | Wert |
|---|---|
| Demo-Produkte (Seed) | 24 |
| Kategorien | herzhaft / süß |
| Features je Produkt | name, brand, barcode, kcal/protein/fat/carbs je 100 g, grams_per_piece |
| Einheiten | g, ml, kg, cl, l, stk (Stück → über grams_per_piece) |
| Tagesziel-Default | 2200 kcal · 30/40/30 (P/C/F) |
| OFF-Zugriff | live, Relevanz-Ranking (exakt 60 / enthält 35 / Teilwort 15) |

- **Datenvorverarbeitung:** Text-Normalisierung (ASCII-Falten, Kleinschreibung), Mengen-Parsing aus Freitext (`"2 x 250 g"` → 500 g), kcal aus kJ-Fallback (÷ 4,184), Dedupliziertung per Barcode.

**SPRECHTEXT:** Tabelle 1 erläutern (Rubrik verlangt: Größe, Klassen, Features, Wertebereiche, Ausreißerbehandlung = unser Mengen-/Einheiten-Sanitizing).
**ABB./QUELLE:** Tabelle 1 (eigene Darstellung).

---

## Folie 8 — Systemarchitektur (Überblick)

**FOLIE** (Schaubild, Abb. 2 — Schichtenmodell)
```
Browser (Jinja2 + Vanilla-JS)
   │ HTML-Forms (SE)        │ fetch/JSON (KI)
   ▼                        ▼
routes.py                 asaai/routes_asaai.py  (/asaai/*)
   ▼                        ▼
*_service.py (Logik)      freestyle_recipe.py    (Orchestrierung)
   ▼                        ▼
*_repo.py (nur SQL)       freestyle_recipe_support.py (Validierung/Makros)
   ▼                        ▼
db.py (sqlite3)           ollama_client.py → lokales LLM (Ollama)
```
- Strikte Trennung: **repo = SQL**, **service = Fachlogik**, **routes = HTTP**.
- Externe Dienste (OFF, Ollama) in eigenen `urllib`-Clients (keine Fremd-Abhängigkeiten).
- Stack: Python 3.10+, Flask 3, SQLite (stdlib), lokales Ollama-LLM.

**SPRECHTEXT:** Abb. 2 von oben nach unten durchgehen; betonen: KI-Teil ist ein eigener Blueprint mit JSON-API.
**ABB.:** Abb. 2 (eigene Darstellung).

---

## Folie 9 — Algorithmus I: Gesamtpipeline

**FOLIE** (Ablauf, Abb. 3)
1. **Prompt bauen** aus Kühlschrank-Zutaten + Zielwerten + Rezeptart + Makro-Strategie-Hinweisen.
2. **LLM-Call** (Ollama, JSON-Mode, `stream=false`).
3. **Parsen** der JSON-Antwort (robust, auch eingebettete Arrays).
4. **Nachrechnen** der Makros aus Gramm × /100g (**nicht** Modellzahlen!).
5. **Validieren** (Plausibilitätsregeln + Zielbereiche).
6. **Reparieren** der Mengen, falls außerhalb der Zielbereiche.
7. **Retry-Schleife** mit konkretem Feedback, bis genug valide Rezepte.

**SPRECHTEXT:** Schritt 4 ist der Kern der Forschungsfrage. Schritte 5–6 sind die „Sicherung". Abb. 3 zeigt den Loop.
**ABB.:** Abb. 3 (eigene Darstellung).

---

## Folie 10 — Algorithmus II: Warum LLM + welche Parameter

**FOLIE**
- **Modellwahl:** lokales Ollama, default `qwen3.5:latest` (9B); Alternativen 4B / 1B. Begründung: Datenschutz (lokal), reproduzierbar, JSON-Mode.
- **Pro-Modell-Profil** (`MODEL_PROFILES`): `num_predict` (Token-Budget) und `max_items` (Zutatenanzahl) — kleinere Modelle bekommen weniger.
- **Temperatur:** `0.15` bei Einzel-Vorschlag (Genauigkeit), `0.7` bei Mehrfach-Vorschlägen (Vielfalt). → bewusst gewählt: präzise vs. divers.
- `format:"json"`, `think:false` für deterministisch parsebare Ausgabe.

**SPRECHTEXT:** Rubrik verlangt Parameterbegründung + reproduzierbare Angaben — hier alle nennen. Unterschiedliche Temperaturen = unterschiedliche Modellläufe, im Analyseteil verglichen.

---

## Folie 11 — Algorithmus III: Validierung (Plausibilität)

**FOLIE** (Regelwerk, Tabelle 2)
- **ID-/Mengenprüfung:** nur echte Kühlschrank-IDs; 0 < g ≤ 1200; Supplements ≤ 80 g.
- **Konflikte abgelehnt:** doppelte Protein- oder Stärkequelle, Süß-Herzhaft-Mix, Whey/Supplement nur in süßen Gerichten, Titel-↔-Zutaten-Konsistenz.
- **Qualität:** Mindest-Schrittzahl, realistische Portionsgrößen.
- **Wissensbasen:** Keyword-Listen (PROTEIN, STARCH, SWEET, SUPPLEMENT, MEAT_FISH, ALIASES …) — domänenspezifisch, der am ehesten nachzujustierende Teil.

**SPRECHTEXT:** Das ist die Analogie zur „Belohnungs-/Regelfunktion": gültig/ungültig statt Reward. Tabelle 2 = Regelübersicht.
**ABB.:** Tabelle 2 (eigene Darstellung).

---

## Folie 12 — Algorithmus IV: Makro-Berechnung (Ground Truth)

**FOLIE** (Formeln)
- **Formel 1 — Nährwert je Menge:**
  `nährwert(menge) = wert_pro_100g · menge_in_g / 100`
  (Stück → `menge_in_g = stück · grams_per_piece`; Volumen vereinfacht 1 ml = 1 g)
- **Formel 2 — Rezept-Makros (computed):**
  `M_rezept = Σ_zutaten ( wert_pro_100g · gramm / 100 ) + Öl-Pauschale`
- **Formel 3 — Zielbereiche:** kcal ≤ Ziel + 10 %; Protein nur Untergrenze; Fett/Carbs symmetrische Toleranz mit absolutem Floor.
- Angezeigt wird **immer** der berechnete Wert (`macro_source = computed_from_fridge_amounts`).

**SPRECHTEXT:** Variablen erklären (Rubrik: Formeln im Fließtext erläutern). Kernaussage: die Zahl auf dem Bildschirm kommt aus Formel 2, nie vom Modell.
**ABB.:** Formeln 1–3 (eigene Darstellung).

---

## Folie 13 — Algorithmus V: Makro-Reparatur (Koordinatenabstieg)

**FOLIE** (Abb. 4 — schematisch)
- Liegt ein Makro außerhalb des Zielbereichs → **eine Hebel-Zutat je Makro** wählen (dichteste Protein-/Carb-/Fettquelle).
- Deren Gramm-Menge per **Koordinatenabstieg** auf das Ziel lösen, Makro für Makro.
- Behebt **Verhältnisfehler**, die reines kcal-Skalieren nicht kann.
  - Beispiel Low-Carb: Stärke ↓, Fett ↑.
- Fallback: ganze Portion auf kcal-Ziel skalieren. Übernahme **nur**, wenn Ergebnis danach valide.

**SPRECHTEXT:** Das ist die eigentliche „Methodenänderung" gegenüber Standard-LLM-Nutzung — so genau erklären, dass es nachgebaut werden kann. Abb. 4 zeigt einen Reparaturschritt (z. B. Reis 200 g → 90 g, Öl 5 g → 15 g).
**ABB.:** Abb. 4 (eigene Darstellung).

---

## Folie 14 — Einordnung: FitFridge als adaptives System

**FOLIE** (Abb. 8 — Regelkreis)
- **Definition (Kurs-Bezug):** Ein adaptives System passt sein Verhalten zur Laufzeit an Eingaben, Umgebung und Rückmeldung an, um ein vorgegebenes Ziel zu erreichen.
- **Drei geschlossene Regelkreise im System:**
  1. **Kontext-Adaption:** `_macro_strategy_hint` passt den Prompt an den realen Bestand **und** die Zielwerte an — andere Zutaten/Ziele ⇒ andere Strategie.
  2. **Selbstkorrektur-Regelkreis:** Validierung erkennt Verstöße ⇒ konkretes `validation_feedback` ⇒ erneute Generierung (Retry), bis zielkonform.
  3. **Makro-Regler:** Koordinatenabstieg = Regler im Sinne der Regelungstechnik — **Sollwert** = Zielmakro, **Istwert** = berechnetes Makro, **Stellgröße** = Gramm der Hebel-Zutat; minimiert den Regelfehler `|Ist − Soll|`.
- **Weitere Adaptivität:** Modell-/Budget-Wahl nach Hardware (`MODEL_PROFILES`), temperaturabhängige Diversität, zustandsabhängiges Degradieren.
- **Ehrliche Abgrenzung:** regelbasiert-adaptiv (deterministischer Regelkreis), **kein** Online-Lernen zur Laufzeit — bewusst, zugunsten von Reproduzierbarkeit.

**SPRECHTEXT:** Bezug zum Kursthema explizit machen: FitFridge ist kein statischer Generator, sondern ein **geschlossener Regelkreis**. Die drei Schleifen — Kontextanpassung, Selbstkorrektur, Makro-Regelung — bilden die adaptive Kernidee. Die Makro-Reparatur (Folie 13) lässt sich formal als Regler beschreiben: Soll-, Ist-, Stellgröße, Regelfehler. Abb. 8 zeigt den Kreislauf Ziel → LLM → Berechnung → Vergleich → Reparatur/Retry → zurück.
**ABB.:** Abb. 8 (eigene Darstellung, Regelkreis-Schema).

---

## Folie 15 — UI / Live-Demo

**FOLIE**
- Dashboard (Bestand + Live-Nährwertsummen), Mahlzeiten-Tracker mit Kalender, Rezeptplaner.
- Gestaffeltes Laden: 1 Vorschlag sofort, 2 weitere im Hintergrund.
- Sauberes Degradieren: leerer Kühlschrank / LLM offline / „Makro-Kombination nicht erreichbar" → verständliche Hinweis-Karte statt Fehler.

**SPRECHTEXT:** Kurze Live-Demo oder Screenshots (Abb. 5–7). Falls live: Plan B = Screenshots zeigen.
**ABB.:** Abb. 5 Dashboard, Abb. 6 Tracker/Kalender, Abb. 7 Planner.

---

## Folie 16 — Analyse / Ergebnisse

**FOLIE** (Tabelle 3 — Vergleich beantwortet die Forschungsfrage)

| Variante | valide Rezepte | Makros im Zielbereich | Bemerkung |
|---|---|---|---|
| LLM ungeprüft (Modellzahlen) | ‹…› | ‹…› | Zahlen halluziniert |
| + eigene Berechnung | ‹…› | ‹…› | korrekte Anzeige |
| + Validierung & Reparatur | ‹…› | ‹…› | zielkonform |

- **End-to-End-Test (25.06.2026):** echtes LLM, Rezept in **33 s**, `computed_from_fridge_amounts`, keine Warnung. ✅
- **Test-Suite:** **39/39** grün (offline, Ollama/OFF gemockt).

**SPRECHTEXT:** Tabelle 3 ist das Herz des Analyseteils — ‹Messwerte aus einem Versuchslauf eintragen› (z. B. N=20 Generierungen je Variante zählen). Klar sagen: Reparaturschicht hebt Trefferquote deutlich.
**ABB./QUELLE:** Tabelle 3 (eigene Messung, ‹Datum›).

---

## Folie 17 — Lessons Learned *(optional)*

**FOLIE**
- LLM-Zahlen sind unzuverlässig → strikte Nachberechnung war zwingend (bestätigt die Hypothese).
- JSON-Mode allein reicht nicht: robustes Parsing + Retry mit konkretem Feedback nötig.
- Kleine Modelle brauchen engere Token-/Zutatenbudgets, sonst unvollständige JSON-Ausgabe.
- Domänen-Keyword-Listen sind der wartungsintensivste Teil bei neuen Zutaten/Modellen.

**SPRECHTEXT:** Sachlich, fachlich bleiben (keine persönlichen Hürden).

---

## Folie 18 — Fazit & Ausblick

**FOLIE**
- **Antwort auf die Forschungsfrage:** Die Validierungs-/Reparaturschicht verbessert Genauigkeit und Zielkonformität gegenüber ungeprüfter LLM-Ausgabe deutlich ‹konkrete Zahl aus Tabelle 3›.
- LLM als Ideengeber, deterministische Schicht als Garant für korrekte Nährwerte.
- **Adaptive-Systeme-Sicht:** Drei gekoppelte Regelkreise (Kontext-Adaption, Selbstkorrektur, Makro-Regler) machen das System zielgerichtet adaptiv statt statisch.
- **Ausblick:** systematische Messreihe (N je Modell), weitere Modelle, persistente DB, Portions-Optimierung über mehrere Makros gleichzeitig.

**SPRECHTEXT:** Mit der Forschungsfrage öffnen und schließen — Bogen zu Folie 4.

---

## Folie 19 — Literatur-, Abbildungs-, Tabellen- & Formelverzeichnis

**FOLIE**
**Literatur** (Zitierstandard wählen, URLs ausschreiben + Abrufdatum):
- [Q1] ‹Autor›, *Constraint-/Retrieval-basierte Rezeptempfehlung*, ‹Jahr›.
- [Q2] ‹Autor›, *LLM-basierte Rezeptgenerierung / Halluzination von Fakten*, ‹Jahr›.
- [Q3] ‹Anbieter›, *Structured Output / JSON-Mode*, URL: ‹…› (abgerufen ‹Datum›).
- [Q4] OpenFoodFacts, URL: https://world.openfoodfacts.org (abgerufen ‹Datum›).
- [Q5] Ollama, URL: https://ollama.com (abgerufen ‹Datum›).
- [Q6] ASaAI-Vorlesungsmaterialien, ‹Putzar/Balzer/Maute›, ‹Semester›.

**Abbildungen:** Abb. 1 Dashboard · Abb. 2 Architektur · Abb. 3 Pipeline · Abb. 4 Makro-Reparatur · Abb. 5–7 UI · Abb. 8 Regelkreis (adaptives System)
**Tabellen:** Tab. 1 Datensatz · Tab. 2 Validierungsregeln · Tab. 3 Ergebnisvergleich
**Formeln:** (1) Nährwert je Menge · (2) Rezept-Makros · (3) Zielbereiche

**SPRECHTEXT:** Nur einblenden; mündlich auf [Q4]/[Q5] als Kernquellen verweisen.

---

### Abgabe-Checkliste (nicht präsentieren)
- [ ] Namen, Matrikelnummern, Lehrenden-Titel eingesetzt
- [ ] Seitenzahlen + Kopf-/Fußzeile auf allen Folien
- [ ] Jede Abb./Tabelle im Sprechtext referenziert, Quelle in Fußzeile
- [ ] Tabelle 3 mit echten Messwerten gefüllt
- [ ] Einheitliche Begriffe (LLM, Makro, Zielbereich), kein „ich/wir/man", keine schmückenden Adjektive
- [ ] Akronyme einmalig eingeführt (LLM, OFF, SE, KI)
