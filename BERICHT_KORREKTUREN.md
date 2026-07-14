# Bericht-Korrekturen — copy-paste-fertig

Alle technischen Angaben wurden gegen den Repo-Stand geprüft. Ersatztexte können direkt ins Google Doc übernommen werden.

---

## A) Repo-Check: Was stimmt bereits ✅

| Angabe im Bericht | Repo-Beleg |
|---|---|
| 39 Tests (14/6/5/5/3/2/4) | exakt bestätigt (`tests/`) |
| Standardmodell `qwen3.5:latest` | `ollama_client.py:11`, `schema.sql:76` |
| Dateien routes_asaai / freestyle_recipe / ollama_client / freestyle_recipe_support / food_estimate / app_settings_repo | alle vorhanden in `flaskr_new/asaai/` |
| 7 Validierungs-Checks, Portionsgrößen 0–1200 g, Öl ≤30 g, Salz ≤5 g | `freestyle_recipe_support.py:200,211,213` |
| MAPE-K-Funktionen (`computed_macros`, `macros_within_targets`, `_fit_amounts`, `_scale_fridge_amounts`, `MACRO_TOLERANCES`) | alle vorhanden |
| `estimate_food()` liefert OFF-kompatibles Format | `food_estimate.py` |
| Retry-Schleife mit `validation_feedback()` + Titel-Exclude | `freestyle_recipe.py:253-280` |
| Meldung bei unerreichbaren Makrozielen („Makro-Kombination nicht erreichbar") | `freestyle_recipe.py:305` |

**Diagramme:** Alle vier Diagramme liegen neu erstellt im Repo-Root (Berichts-Stil, druckfähig ~2600 px breit). Wo welches eingefügt wird → **Abschnitt D**.

| Datei | Inhalt |
|---|---|
| `FitFridge_Schichtenmodell.png` | Architekturübersicht als Schichtenmodell (farbige Schicht-Bänder) |
| `FitFridge_UML.png` | klassisches UML-Klassendiagramm (3 Kompartimente, +/−, «Stereotypen») |
| `FitFridge_Sequenz_SE.png` | Sequenzdiagramm Teil A: Produkt suchen & zum Kühlschrank hinzufügen |
| `FitFridge_Sequenz.png` | Sequenzdiagramm Teil B: Freestyle-Rezeptgenerierung (loop/Retry, RAG, MAPE-K) |

---

## B) Inhaltliche Korrekturen (nach deinen Notizen)

### 1 Einleitung

**B1 — „KI-basierte Nährwertschätzung" präzisieren (S. 3, Abs. 3):**

> Alt: „Der ASaAI-Teil der Anwendung nutzt diese Daten für zwei Funktionen: eine KI-basierte Nährwertschätzung und einen KI-gestützten Freestyle-Rezeptgenerator."

Neu:
> Der ASaAI-Teil der Anwendung umfasst zwei Funktionen: eine KI-Schätzung, die bei der Produktsuche neben den OpenFoodFacts-Treffern eine geschätzte Nährwertangabe für den eingegebenen Suchbegriff liefert, und einen KI-gestützten Freestyle-Rezeptgenerator, der aus dem aktuellen Kühlschrankbestand und den vorgegebenen Makrozielen passende und kulinarisch logische Rezepte erzeugt.

**B2 — „Benutzerverwaltung" abschwächen:**

> Alt: „Der Software-Engineering-Teil umfasst unter anderem Benutzerverwaltung, Kühlschrankverwaltung, Produktsuche und Mahlzeiten-Tracker."

Neu:
> Der Software-Engineering-Teil umfasst unter anderem eine einfache Authentifizierung mit Registrierung und Login sowie strikt getrennten Nutzerdaten, die Kühlschrankverwaltung, eine Produktsuche über OpenFoodFacts und einen Mahlzeiten-Tracker.

**B3 — Adaptivität in der Zielsetzung ergänzen (nach „…Rezeptgenerierung miteinander verbinden."):**

> Die Anwendung verhält sich dabei adaptiv: Jede Änderung des Kühlschrankbestands, etwa durch Hinzufügen, Verbrauchen oder Entfernen von Lebensmitteln, verändert unmittelbar den Kontext der nächsten Rezeptgenerierung.

**B4 — Aufbau des Berichts (1.3), MAPE-K/RAG begründen:**

> Alt: „…kontextgestützter Generierung und MAPE-K."

Neu:
> …kontextgestützter, RAG-ähnlicher Generierung sowie MAPE-K. RAG ist relevant, weil die Kühlschrankdaten als externer Kontext in den Prompt injiziert werden; MAPE-K dient als Referenzmodell für die adaptive Makro-Reparatur im Backend.

### 2 Grundlagen und Einordnung

**B5 — Kühlschrank hat keine KI-Schätzung; Mahlzeiten-Tracker-Verzahnung ergänzen (2.1, letzter Absatz vor 2.2):**

> Alt: „FitFridge kombiniert einen digitalen Kühlschrank mit KI-basierter Nährwertschätzung, einem KI-gestützten Rezeptplaner und einem Mahlzeiten-Tracker."

Neu:
> FitFridge kombiniert einen digitalen Kühlschrank, einen KI-gestützten Rezeptplaner und einen Mahlzeiten-Tracker. Die Nährwerte im Kühlschrank stammen aus festen Produktdaten, nicht aus einer KI-Schätzung. Nur wenn die Produktsuche keinen passenden Eintrag in der OpenFoodFacts-Datenbank findet, kann auf die KI-Schätzung in der Suche zurückgegriffen werden, die besonders bei unverarbeiteten Lebensmitteln wie Obst, Gemüse oder Fleisch genaue Näherungen liefert. Der Mahlzeiten-Tracker ist zudem direkt mit dem Kühlschrank verzahnt: Produkte können unmittelbar aus dem Kühlschrankbestand zu einer Mahlzeit hinzugefügt werden, wobei der Bestand automatisch angepasst wird.

**B6 — Fine-Tuning erklären (2.2):**

> Alt: „In FitFridge wird kein eigenes Modell trainiert und kein Fine-Tuning durchgeführt. Stattdessen wird ein bereits vorhandenes Modell lokal über Ollama genutzt."

Neu:
> In FitFridge wird kein eigenes Modell trainiert und keine Anpassung der Modellgewichte durch Fine-Tuning vorgenommen. Stattdessen wird ein vorhandenes Modell lokal über Ollama genutzt und ausschließlich über den Prompt gesteuert: Ein ausführlicher, iterativ verfeinerter Rezept-Prompt, regelbasierte Backend-Validierung und eine Retry-Schleife übernehmen die Steuerung, die andernfalls über ein Training erfolgen müsste.

**B7 — Kleine Modelle = Debug (2.2):**

> Alt: „Zusätzlich sind kleinere Modelle wie qwen3:4b und gemma3:1b vorgesehen."

Neu:
> Zusätzlich sind die kleineren Modelle qwen3:4b und gemma3:1b hinterlegt. Diese dienen ausschließlich schnellen Tests und dem Debugging auf schwächerer Hardware wie Laptops; für die Rezeptgenerierung sind sie zu schwach und liefern häufig unbrauchbare Antworten.

**B7.1 — Prompt-Kontext-Beispiel in 2.3 an das echte Format anpassen (Repo-Abgleich!):**

Das Beispiel im Bericht (und auf Präsi-Folie 11) entspricht nicht dem tatsächlichen `item_label()`-Format: Es gibt kein „(id=3)", kein „300g verfügbar", und die Reihenfolge ist kcal/P/F/C. Die verfügbaren Mengen stehen überhaupt nicht im Prompt — Mengensteuerung erfolgt über Prompt-Regeln und Backend-Validierung. Die IDs sind laufende Nummern pro Prompt (1…n), keine Datenbank-IDs.

> Alt: „1. Hähnchenbrust (id=3): 300g verfügbar | 165 kcal, 31g Protein, 0g Kohlenhydrate, 4g Fett je 100g …"

Neu (echtes Format aus `item_label()`):
> 1 Hähnchenbrust (165kcal 31P 4F 0C /100g)
> 2 Reis (130kcal 2P 0F 28C /100g)
> 3 Paprika (31kcal 1P 0F 6C /100g)

Dazu den erläuternden Satz anpassen:
> Die Nummern sind dabei laufende IDs, die den Kühlschrankprodukten für diesen Prompt zugewiesen werden. Das LLM soll nicht nur Namen von Zutaten nennen, sondern diese IDs in seiner Antwort referenzieren. Gibt das Modell eine unbekannte ID zurück, erkennt das Backend das Rezept als ungültig. Die verfügbaren Mengen werden bewusst nicht in den Prompt geschrieben; realistische Portionsgrößen und die Einhaltung des Vorrats werden über Prompt-Regeln und die Backend-Validierung sichergestellt.

Außerdem in 2.3: „…der sich ausschließlich an den bereitgestellten Kühlschrankdaten orientieren soll" ergänzen um die Pantry-Ausnahme:
> …der sich ausschließlich an den bereitgestellten Kühlschrankdaten orientieren soll; zusätzlich sind nur Basiszutaten wie Wasser, Öl, Salz, Gewürze und gängige Saucen erlaubt.

**B7.2 — 2.4:** „Rezeptart" → „Rezeptkategorie" (konsistent zu B9/B17). Die MAPE-K-Zuordnung selbst ist korrekt und deckt sich mit dem Code (computed_macros / macros_within_targets / _fit_amounts / _set_/_scale_fridge_amounts / MACRO_TOLERANCES + PROTEIN/STARCH/SWEET-Listen).

### 3 Projektkontext und technische Grundlage

**B8 — Warum KI-Schätzung (3.1, erster Absatz ergänzen):**

> Der Grund liegt in der Struktur der OpenFoodFacts-Daten: Die Datenbank enthält überwiegend verarbeitete Markenprodukte. Wer etwa nach „Mango" sucht, erhält Treffer wie Mango-Lassi oder Mango-Sorbet, aber selten die Frucht selbst. Die KI-Schätzung betrachtet dagegen ausschließlich den eingegebenen Suchtext — in diesem Fall „Mango" — und liefert dafür eine Schätzung pro 100 g. Besonders für Obst, Gemüse und Fleisch bietet sich das an, da deren Nährwerte weitgehend konstant sind.

**B9 — Makroziele + Kategorie statt Rezeptart (3.1):**

> Alt: „Dabei geben Nutzerinnen und Nutzer Zielwerte für Kalorien, Protein, Fett oder Kohlenhydrate sowie eine gewünschte Rezeptart an. Bereits eine Makroangabe reicht aus…"

Neu:
> Dabei geben Nutzerinnen und Nutzer Zielwerte für Kalorien, Protein, Fett oder Kohlenhydrate an. Es müssen nicht alle vier Werte angegeben werden, mindestens einer ist jedoch erforderlich — beispielsweise genügt ein Protein- und ein Kalorienziel. Zusätzlich wird eine Rezeptkategorie gewählt: Hauptspeise, Frühstück, Abendessen, Nachspeise oder Snack.

**B10 — Rezeptvorschlag-Bestandteile (3.1):**

> Alt: „Funktional soll ein Rezeptvorschlag Titel, Zutaten, verwendete Kühlschrankprodukte, Mengen, Zubereitungsschritte und berechnete Makros enthalten."

Neu:
> Funktional soll ein Rezeptvorschlag Titel, Zutaten, verwendete Kühlschrankprodukte, Mengen, Zubereitungsschritte, berechnete Makros sowie eine kurze Begründung enthalten, warum das Gericht kulinarisch funktioniert („Warum"). Zusätzlich können erzeugte Rezepte gespeichert werden.

**B11 — Git-Workflow (3.2):**

> Alt: „Zusätzlich wurden Git-Feature-Branches genutzt, um einzelne Arbeitspakete getrennt voneinander zu entwickeln."

Neu:
> Zusätzlich wurden Git-Feature-Branches genutzt, um einzelne Arbeitspakete getrennt voneinander zu entwickeln. Die Integration in den Main-Branch erfolgte nach Absprache und gegenseitiger Prüfung über einen Merge-Branch.

**B12 — Claude als Werkzeug (3.3, ans Ende des ersten Absatzes):**

> Ergänzend wurde Claude (Anthropic) als Entwicklungsunterstützung in Bereichen eingesetzt, in denen Vorwissen fehlte, insbesondere bei der Frontend-Umsetzung.

**B13 — OFF-Rezepte-Satz streichen (3.3):**

> Streichen: „Für FitFridge ist wichtig, dass OpenFoodFacts keine fertigen Rezepte liefert."
> Ersetzen durch: „Die Rezepte werden ausschließlich vom lokalen LLM generiert."

**B14 — Bild Kühlschrank-Übersicht:** Nach „…tatsächliche Produktmenge im Kühlschrank angepasst." (dort steht noch ein verwaistes „[" — entfernen!) Screenshot der Kühlschrank-Übersicht einfügen (aus Präsi Folie 6), mit Beschriftung:
> Abbildung X: Kühlschrank-Übersicht mit live berechneten Nährwerten
> Quelle: Eigene Darstellung

### 4 Entwurf und Implementierung

**B15 — Kapitel 4.1 komplett ersetzen (integriert Schichtenmodell + UML, beseitigt die Redundanz):**

Die beiden Icon-Grafiken in 4.1 („Der vereinfachte Ablauf des Freestyle-Rezeptgenerators" und Nutzereingabe → Prompt → Ollama → JSON → Validierung → Rezeptanzeige) **beide löschen** — sie zeigen denselben Ablauf wie das neue Sequenzdiagramm in 4.5, nur ungenauer. Der Satz „Diese Trennung ist wichtig…" geht im neuen Schlussabsatz auf. Neuer Text für 4.1 (Dateitabelle bleibt an ihrer Stelle):

> Grundlage der gesamten Anwendung ist ein durchgängiges Schichtenmodell: Im Browser laufen Jinja2-Templates und Vanilla-JavaScript, darunter folgen Flask-Routen, Fachlogik-Services und Repositories mit reinem SQL auf einer SQLite-Datenbank. Abhängigkeiten verlaufen ausschließlich von oben nach unten. Diese Architekturentscheidung trennt HTTP-Verarbeitung, Fachlogik und Datenzugriff voneinander und ist der Grund, warum alle 39 automatisierten Tests ohne laufenden Webserver auskommen. Abbildung A zeigt dieses Schichtenmodell mit dem Software-Engineering-Teil (links) und dem ASaAI-Teil (rechts).
>
> **[Abbildung A: FitFridge-Architektur als Schichtenmodell — Quelle: Eigene Darstellung]**
>
> Die daraus resultierende statische Struktur der Module dokumentiert das UML-Klassendiagramm in Abbildung B. Es zeigt die wichtigsten Module mit Attributen, Methoden und «uses»-Abhängigkeiten — darunter auch Querbeziehungen, die im Schichtenmodell nicht sichtbar sind, etwa den Zugriff der Produktsuche (unified_search) auf die KI-Schätzung (food_estimate).
>
> **[Abbildung B: Statische Struktur der FitFridge-Module als UML-Klassendiagramm — Quelle: Eigene Darstellung]**
>
> Der ASaAI-Teil ist innerhalb dieses Modells als eigener Pfad umgesetzt: ein separater Blueprint (routes_asaai.py) unter /asaai. Während der Software-Engineering-Teil klassisch mit HTML-Formularen und serverseitigem Rendering arbeitet, kommuniziert der ASaAI-Bereich über fetch-Anfragen und JSON. KI-bezogene Anfragen werden dadurch getrennt verarbeitet und strukturiert an das Frontend zurückgegeben.
>
> Die wichtigsten Dateien sind: **[Dateitabelle wie bisher, mit Tabellenbeschriftung oberhalb]**
>
> Zentral ist, dass Modellantworten nie direkt angezeigt werden: Zwischen LLM und Frontend liegt mit freestyle_recipe_support.py eine Kontrollschicht, die Antworten prüft, die Nährwerte selbst berechnet und ungültige Ergebnisse verwirft (Kapitel 4.5). Den zeitlichen Ablauf zeigen die Sequenzdiagramme: Abbildung C für den Software-Engineering-Teil am Beispiel der Produktsuche mit anschließendem Kühlschrank-Hinzufügen, Abbildung D (Kapitel 4.5) für die Freestyle-Rezeptgenerierung mit Retry-Schleife.
>
> **[Abbildung C: Sequenzdiagramm — Produkt suchen und zum Kühlschrank hinzufügen (Teil A) — Quelle: Eigene Darstellung]**

**B16 — Grafik KI-Schätzung vs. Suche (4.2):** Nach „…nicht außerhalb der App recherchieren möchte." Screenshot aus Präsi Folie 7 (KI-Schätzung als erster Treffer neben OFF-Ergebnissen) mit Beschriftung + Quelle einfügen.

**B17 — 4.3 Makroziele/„Warum" (erster Absatz):**

> Alt: „Nutzerinnen und Nutzer geben Makroziele für Kalorien, Protein, Fett oder Kohlenhydrate sowie eine gewünschte Rezeptart an."

Neu:
> Nutzerinnen und Nutzer geben mindestens ein Makroziel für Kalorien, Protein, Fett oder Kohlenhydrate sowie eine Rezeptkategorie an; es reicht beispielsweise ein Protein- und ein Kalorienziel. Jeder Vorschlag enthält neben Titel, Zutaten, Mengen, Kochschritten und berechneten Makros auch eine kurze Begründung, warum das Gericht kulinarisch zusammenpasst.

**B18 — 4.4 Realistischeres Prompt-Beispiel:** Zuerst den Einleitungssatz korrigieren (Repo-Abgleich, vgl. B7.1 — die verfügbaren Mengen stehen nicht im Prompt):

> Alt: „Er enthält Produkt-IDs, Namen, verfügbare Mengen und Nährwerte pro 100g."

Neu:
> Er enthält je Kühlschrankprodukt eine laufende ID, den Namen und die Nährwerte pro 100 g. Die vorhandenen Mengen werden nicht in den Prompt geschrieben; realistische Portionen und der Vorratsabgleich werden über Prompt-Regeln und die Backend-Validierung sichergestellt.

Dann den stark vereinfachten Prompt ersetzen durch einen echten (gekürzten) Auszug aus `build_prompt()`:

> Der tatsächliche Prompt ist deutlich umfangreicher und in Regelblöcke gegliedert (Rezeptlogik, Gerichtsart, Zutatenregeln, Mengen, Konsistenzregeln, Qualität, Nährwerte, Ausgabe). Ein gekürzter Auszug:

```
Erzeuge genau 3 verschiedene, einfache und realistisch kochbare
FitFridge-Rezepte als JSON-Array. Rezeptart: hauptspeise.
Zielwerte: kcal=900, protein=60. Erlaubte berechnete Bereiche:
kcal 810-990, protein ab 54. Diese Zielbereiche sind harte
Validierungsregeln.
Kühlschrank-Zutaten, nur diese IDs erlaubt:
1 Hähnchenbrust (165kcal 31P 4F 0C /100g),
2 Reis (130kcal 2P 0F 28C /100g), 3 Paprika (31kcal 1P 0F 6C /100g).
Zusätzlich erlaubt sind nur Wasser, Öl, Salz, Zucker, Süßungsmittel,
Pfeffer, Gewürze und Saucen wie Ketchup, Mayonnaise und Senf.
[...]
REZEPTLOGIK: Wähle zuerst ein real existierendes, kulinarisch
plausibles Gericht [...] GERICHTSART: Wähle genau EINE Haupt-
proteinquelle und genau EINE Haupt-Stärkebeilage pro Gericht. [...]
MENGEN: Typische Mengen sind 50-160g trockenes Getreide [...]
KONSISTENZREGELN: Jede verwendete Kühlschrank-Zutat muss in
fridge_ingredients stehen mit exakter id, amount_g und label. [...]
Antworte ausschließlich mit einem JSON-Array aus genau 3 Objekten
dieser Form: [{"title":"string","why_this_works":"string",...}]
```

> Zusätzlich passt sich der Prompt dynamisch an: Bei gesetzten Zielwerten wird eine zutatenspezifische Makro-Strategie eingefügt (z. B. welche vorhandene Zutat als Protein- oder Stärkehebel dient), bei Wiederholungsversuchen ein Feedback-Hinweis mit dem konkreten Fehlergrund, und bereits vorgeschlagene Titel werden ausgeschlossen.

**B19 — 4.5:** Grafik links vom Absatz „Dadurch bleibt die fachliche Kontrolle im Backend…" entfernen (deine eigene Notiz).

### 5 Evaluation

**B20 — 5.3 kleine Modelle:**

> Alt: „Kleinere Modelle sind leichter auszuführen, können aber häufiger unstrukturierte oder unpassende Antworten erzeugen."

Neu:
> Kleinere Modelle sind leichter auszuführen, dienen im Projekt aber nur für einfache Debug-Läufe und die KI-Schätzung; für die Rezeptgenerierung sind sie ungeeignet.

### 6 Diskussion

**B21 — Unlogische Makroziele (6.2, nach dem OpenFoodFacts-Satz):**

> Auch bei unlogischen Makrozielkombinationen — etwa 100 g Protein bei nur 300 kcal — kann kein Rezept erstellt werden. Das System zeigt in diesem Fall den Hinweis „Makro-Kombination nicht erreichbar" mit einer Anpassungsempfehlung an, statt ein geschöntes Rezept auszugeben.

**B22 — Schwache Hardware (6.2):**

> Alt: „Auf schwächeren Geräten können Antwortzeiten lang sein."

Neu:
> Auf schwächeren Geräten können Antwortzeiten lang sein; die kleinen Modelle eignen sich dort nur für die KI-Schätzung oder Debug-Zwecke, nicht für die Rezeptgenerierung.

---

## C) Formatierung (Abgleich mit der HAW-Vorlage)

Fehlt komplett / muss ergänzt werden:

1. **Seitenzahlen** (deine Notiz) — in Google Docs: Einfügen → Seitenzahlen.
2. **Deckblatt nach Vorlage:** „Bericht/Dokumentation eingereicht von Nachname, Vorname + Matrikelnummer", „im Rahmen der Vorlesung ASaAI", „im Studiengang Media Systems", „am Department Medientechnik der Fakultät DMI", „Lehrende: Prof. Dr. Larissa Putzar, Sune Maute, Jörg Balzer", „Eingereicht am: TT.MM.JJJJ". (Namen/Matrikelnummern stehen bereits drauf, der Rest fehlt.)
3. **Zusammenfassung** (max. 1000 Zeichen) auf eigener Seite vor dem Inhaltsverzeichnis: Fragestellung, Methodik, wichtigste Ergebnisse, Fazit. Vorschlag:

   > FitFridge ist eine Ernährungs-Webanwendung, die einen digitalen Kühlschrank, Mahlzeiten-Tracking und ein lokal über Ollama ausgeführtes Large Language Model verbindet. Untersucht wurde, wie ein lokales LLM und regelbasierte Backend-Validierung kombiniert werden können, um plausible Rezeptvorschläge und Nährwertschätzungen auf Basis vorhandener Lebensmittel zu erzeugen. Der Kühlschrankbestand wird dazu RAG-ähnlich als Kontext in den Prompt injiziert; eine Retry-Schleife mit Feedback, eine MAPE-K-basierte Makro-Reparatur und sieben regelbasierte Validierungsprüfungen kontrollieren die Modellantworten. Die Nährwerte werden nie vom Modell übernommen, sondern im Backend aus Mengen und /100g-Werten berechnet. Der Prototyp zeigt: Generative KI liefert brauchbare Rezeptideen, wird aber erst durch deterministische Validierung zuverlässig — das LLM liefert Kreativität, der Code Präzision. 39 automatisierte Tests sichern die Kernlogik offline ab.

4. **Abbildungsverzeichnis** (Pflicht laut Vorlage) und bei der Menge an Tabellen auch ein **Tabellenverzeichnis**.
5. **Alle Abbildungen und Tabellen:** nummerieren, beschriften (Tabellen: Beschriftung oberhalb, Abbildungen: unterhalb), Quelle angeben („Quelle: Eigene Darstellung"), und im Fließtext referenzieren („Abbildung 3 zeigt…"). Aktuell hat keine einzige Grafik eine Beschriftung.
6. **Literaturverzeichnis alphabetisch sortieren** (aktuell in Auftretensreihenfolge [1]–[7]): Arcaini → Brown → Lewis → MyFitnessPal → Ollama → OpenFoodFacts → Yazio. Außerdem Doppelung vermeiden: entweder Fußnoten ODER nummeriertes Verzeichnis, konsistent halten; „abgerufen am"-Datum ist überall vorhanden ✅.
7. **Eigenständigkeitserklärung** als letzte Seite (Text aus der Vorlage, Datum + Unterschriften beider Autoren).
8. **Kleinkram:** Verwaistes „[" auf S. 9 („…angepasst.["), „[8]"-Referenzen in 4.5 prüfen (Literaturverzeichnis endet bei [7]), Komma auf dem Deckblatt unter dem Betreuer-Block entfernen.

---

## D) Diagramm-Platzierung — welche Abbildung wohin

Nummerierung fortlaufend mit den Screenshots; hier als Abb. A–D bezeichnet, finale Nummern beim Einfügen vergeben. Jede Abbildung im Text davor referenzieren („Abbildung X zeigt…").

| Abb. | Datei | Kapitel & Stelle | Zweck |
|---|---|---|---|
| A | `FitFridge_Schichtenmodell.png` | **4.1**, direkt nach dem neuen Schichtenmodell-Absatz (B15), VOR der Dateitabelle | Architekturübersicht: 5 Schichten, SE links / ASaAI rechts, Abhängigkeiten nur nach unten |
| B | `FitFridge_UML.png` | **4.1**, direkt nach Abb. A | Statische Struktur als klassisches UML-Klassendiagramm (Module, Attribute, Methoden) |
| C | `FitFridge_Sequenz_SE.png` | **4.1**, am Kapitelende — nach dem Absatz „Diese Trennung ist wichtig…" (ersetzt/ergänzt die dortige Icon-Grafik) | Dynamischer Ablauf Teil A: Produktsuche über `unified_search` (lokale DB + OFF) und Hinzufügen mit `alt`-Rahmen (`create_product`) |
| D | `FitFridge_Sequenz.png` | **4.5**, direkt nach „Der Ablauf ist:" (ersetzt die bisherige Generate→Repair→Validate-Icon-Grafik oder steht davor) | Dynamischer Ablauf Teil B: Freestyle-Generierung mit `loop`-Rahmen (Retry), RAG-Kontextinjektion und MAPE-K-Reparatur |

**Bildunterschriften (copy-paste):**

> Abbildung A: FitFridge-Architektur als Schichtenmodell
> Quelle: Eigene Darstellung

> Abbildung B: Statische Struktur der FitFridge-Module als UML-Klassendiagramm
> Quelle: Eigene Darstellung

> Abbildung C: Sequenzdiagramm — Produkt suchen und zum Kühlschrank hinzufügen (Teil A)
> Quelle: Eigene Darstellung

> Abbildung D: Sequenzdiagramm — Freestyle-Rezeptgenerierung mit Retry-Schleife und Makro-Reparatur (Teil B)
> Quelle: Eigene Darstellung

**Textbezüge zum Einfügen:**

- Vor Abb. A/B (4.1): „Abbildung A zeigt die Architektur als Schichtenmodell; Abbildung B dokumentiert die daraus resultierende statische Struktur der Module als UML-Klassendiagramm."
- Vor Abb. C (4.1-Ende): „Abbildung C zeigt den zeitlichen Ablauf der zentralen SE-User-Story: Ein Produkt wird gesucht und dem Kühlschrank hinzugefügt."
- Vor Abb. D (4.5): „Abbildung D zeigt den vollständigen Ablauf der Rezeptgenerierung inklusive Retry-Schleife: Der loop-Rahmen entspricht dem Feedback-Mechanismus, der alt-Pfad der MAPE-K-Makro-Reparatur."
- In 2.4 (MAPE-K) und 4.5 kann zusätzlich auf Abb. D verwiesen werden statt eine weitere Grafik einzufügen; die bestehende MAPE-K-Folien-Grafik aus der Präsi kann bleiben.

**Weiter einzufügende Screenshots (aus App/Präsi, keine Diagramme):** Kühlschrank-Übersicht (B14, Kapitel 3.3) und KI-Schätzung vs. normale Suche (B16, Kapitel 4.2) — Beschriftung + „Quelle: Eigene Darstellung" nicht vergessen.
