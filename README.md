# Leiterplatte: welche Verlegeregel bekommt alle Netze unter? – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-leiterplatte-demo.streamlit.app/)** -->

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`). Ein synthetisches **Sensorboard** (zwei Stecker, bis zu 8 ICs, je IC ein Kondensator, Pull-up-Widerstände) wird auf einem Raster mit **zwei Lagen** platziert und verlegt. Jedes **Netz** muss seine Pads verbinden, zwei Netze dürfen keine Zelle teilen, ein **Via** wechselt die Lage. Verglichen werden drei Verlegeregeln: **sequentiell** (ein Netz nach dem anderen, kürzester Weg), **Rip-up and Reroute** (fremde Netze durchqueren, aufreißen, um das neue herum neu verlegen) und **Negotiated Congestion** (alle Netze dürfen zunächst Zellen teilen, das Teilen wird mit jeder Iteration teurer). Drei Platzierungsarten (Zufall, quadratisch, Simulated Annealing) liefern die Ausgangslage; auf einem **Mini-Brett** prüft ein exakter Löser (OR-Tools CP-SAT) die Aussagen. Als zweiter Teil wird dieselbe Platine **bestückt**: ein Portalautomat holt die Bauteile von Zuführplätzen und setzt sie; **welcher Typ auf welchen Platz** und **in welcher Reihenfolge** entscheiden über die Fahrstrecke, und bei einem Kopf mit mehreren Düsen hängen die beiden Entscheidungen zusammen.

## Warum dieses Problem

Jedes Netz für sich ist ein einfacher kürzester Weg. **Zusammen** blockieren sich die Netze: was ein früheres Netz zubaut, fehlt dem späteren, und die **Reihenfolge** entscheidet mit. Die Kernfrage: **Entscheidet die Reihenfolge, ob alle Netze auf die Platine passen, und was ändert sich, wenn die Netze miteinander verhandeln dürfen?** Die Antwort ist hier gemessen (siehe Befunde), nicht behauptet; die Mini-Bretter zeigen zusätzlich, dass es lösbare Bretter gibt, an denen **keine** Reihenfolge klappt.

Die Demo ist die erste Fall-Demo zum **Mehrnetz-Routing**. Verwandt, aber anderes Modell: [astar-demo](https://github.com/sebastian-hanisch/astar-demo) sucht **einen** kürzesten Weg, [steiner-tree-demo](https://github.com/sebastian-hanisch/steiner-tree-demo) die Topologie **eines** Netzes, [dock_door-demo](https://github.com/sebastian-hanisch/dock_door-demo) löst ein quadratisches Zuordnungsproblem (hier nur als Vorstufe der Platzierung).

## Modell

- **Instanz** (`lpl_scenario.py`): Stecker J1 am linken, J2 am rechten Rand (je 6 Pins), n ICs mit 6 bis 12 Pins in zwei Reihen, je IC ein Abblockkondensator, mindestens zwei Pull-up-Widerstände. VCC und GND sind gewöhnliche Netze (alle Versorgungspins); Signalnetze haben 2 bis 4 Pins und bleiben meist in einem von zwei Clustern; ein einstellbarer Anteil der freien IC-Pins hängt in Signalnetzen (Pin-Nutzung). Alle Zufallsentscheidungen laufen über SplitMix64 (`lpl_rng.py`), damit die Zahlen auf jeder Plattform gleich sind.
- **Brett**: Seitenverhältnis etwa 4 : 3, Größe aus der **Dichte** (Bauteilfläche samt Mindestabstand von 2 Zellen geteilt durch die Brettfläche). Raster mit zwei Lagen; **Pads** sind Durchsteckpads (beide Lagen, nur ihr Netz darf hindurch); Gehäuse von ICs sperren nur die Oberseite.
- **Kosten**: Schritt in der Ebene 1, Via-Schritt 1 plus Via-Kosten. Gesucht: knotendisjunkte Bäume, die alle Pads jedes Netzes verbinden; zuerst möglichst viele Netze verlegen, dann geringe Kosten. Das ist NP-schwer; die drei Regeln sind Heuristiken. Formeln im 📐-Expander der App.
- **Platzierung**: Ziel ist die Summe der Halbumfänge der Netze (HPWL). *Zufall*: legale Zufallslagen. *Quadratisch*: Federmodell (Clique, Feder 1 / (k − 1)) als lineares Gleichungssystem, danach Legalisierung. *Simulated Annealing*: 20 000 Züge (Verschieben, Drehen, Tauschen), geometrische Abkühlung, Delta nur über die Netze der bewegten Bauteile.

- **Bestückung** (`lpl_bestueck.py`): Bestückorte sind alle Bauteile außer den Steckern (Lage = Bauteilmitte), Typen sind die Gehäusearten (ICs nach Pinzahl, Kondensator, Widerstand), je Typ **ein** Zuführplatz in einer Reihe unter dem Brett (Abstand 3 Zellen, vier freie Plätze über die Typenzahl hinaus). Der Kopf trägt k Düsen (1 bis 4): erst k Teile holen, dann k setzen; die Reihenfolge der Bestückorte ergibt die Runden. Fahrstrecke im Tschebyscheff-Abstand (beide Achsen gleichzeitig), je Runde die beste von zwei Holrichtungen auf der Zuführgeraden und allen k! Setzreihenfolgen. Gesucht: injektive Zuordnung Typ zu Platz und Reihenfolge. Bei k = 1 und fester Reihenfolge ist die Zuordnung ein **lineares** Zuordnungsproblem (Ungarische Methode), bei fester Zuordnung die Reihenfolge ein asymmetrisches Rundreiseproblem; die Frage ist die **Kopplung**.

## Methodik

| Abschnitt der App | Was gerechnet wird |
|---|---|
| Ergebnis | Platzierung, dann alle drei Verlegeregeln auf derselben Platzierung; Kennzahlen, Zeichnung beider Lagen, unabhängiger Prüfer für jede Verlegung |
| Kernfrage | dieselbe Platzierung sequentiell in 20 Zufallsreihenfolgen und den drei festen Reihenfolgen; Vergleich mit Rip-up und Negotiated Congestion |
| Methodenvergleich, Platzierung | dieselbe Instanz mit allen drei Platzierungsarten (auf Klick) |
| Methodenvergleich, Via-Kosten | Negotiated Congestion bei Via-Kosten 1, 4, 12, 30 (auf Klick) |
| Methodenvergleich, Exakt | Mini-Brett: alle Reihenfolgen (n!), Rip-up, Negotiated Congestion und CP-SAT (auf Klick) |
| Bestückung | vier Verfahren bei gleichem Budget an Kostenauswertungen (600 je Bestückort, auf Klick): **Maschinenpraxis** (häufigste Typen auf die mittleren Plätze, nächstes Teil zuerst), **erst Plätze, dann Reihenfolge** (Ungarische Methode nach Schwerpunkten, danach Simulated Annealing nur über die Reihenfolge), **abwechselnd** (Reihenfolge, Plätze, Reihenfolge …), **gemeinsam** (Simulated Annealing über beides) |

Qualitätsmaß ist die **Zahl der unverlegten Netze**. Länge, Vias und Umweg (Länge geteilt durch HPWL) zählen nur die verlegten Netze und sind zwischen Regeln nur vergleichbar, wenn gleich viele Netze verlegt sind. Rechenaufwand wird als Zahl der Suchläufe ausgewiesen (plattformunabhängig), nicht als Zeit.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen: 6 ICs, Pin-Nutzung 85 %, Via-Kosten 4, Simulated Annealing, kurze Netze zuerst, Negotiated Congestion mit 60 Iterationen, **20 feste Instanzen** (Seeds 100000 bis 100019), sofern nicht anders angegeben. Jede Zahl steht in `tests/test_claims.py`.

**1. Welche Regel verlegt alle Netze?** Anteil der 20 Instanzen, in denen **alle** Netze verlegt sind:

| Dichte | sequentiell | bestes von 20 Zufallsreihenfolgen | Rip-up and Reroute | Negotiated Congestion |
|---|---|---|---|---|
| 50 % | 0 von 20 | 2 von 20 | 14 von 20 | 17 von 20 |
| 60 % | 1 von 20 | 1 von 20 | 8 von 20 | 17 von 20 |
| 70 % | 0 von 20 | 0 von 20 | 7 von 20 | 12 von 20 |

Mittlere Zahl unverlegter Netze je Instanz (sequentiell / Rip-up / Negotiated Congestion): 50 %: 2,80 / 0,70 / 0,25; 60 %: 2,90 / 1,10 / 0,20; 70 %: 3,05 / 1,85 / 1,30. Negotiated Congestion konvergiert (ohne doppelt belegte Zelle) in 17, 17 und 12 von 20 Instanzen; wo es nicht konvergiert, zeigt die App die größte konfliktfreie Teilmenge und sagt es. Rip-up lässt nie mehr Netze unverlegt als der sequentielle Start (es gibt den besten Stand zurück).

**2. Wie stark entscheidet die Reihenfolge?** Bei 60 % Dichte, dieselbe Platzierung, sequentiell in 20 Zufallsreihenfolgen: der Unterschied zwischen schlechtester und bester Reihenfolge beträgt im Median **5 Netze** (größter Wert 8 Netze, auf jeder der 20 Instanzen mindestens 1). Die Regel „kurze Netze zuerst“ ist in 9 von 20 Instanzen schlechter als die beste der 20 Zufallsreihenfolgen.

**3. Platzierung** (Dichte 60 %, Mittel über die 20 Instanzen):

| Platzierung | HPWL | unverlegt sequentiell | unverlegt Rip-up | unverlegt Negotiated Congestion | alle Netze verlegt (Negotiated Congestion) |
|---|---|---|---|---|---|
| Zufall | 525 | 4,70 | 2,90 | 0,45 | 16 von 20 |
| Quadratisch | 346 | 3,45 | 1,95 | 0,10 | 18 von 20 |
| Simulated Annealing | 296 | 2,90 | 1,10 | 0,20 | 17 von 20 |

Die Platzierung mit der kleinsten HPWL lässt in allen 20 Instanzen höchstens so viele Netze unverlegt (Negotiated Congestion) wie die beste der drei Platzierungen: kürzeste Netze und beste Verlegbarkeit gehen hier zusammen. Dass die quadratische Platzierung trotz größerer HPWL im Mittel etwas weniger Netze unverlegt lässt als Simulated Annealing (0,10 gegen 0,20), ist ein Unterschied von einer Instanz und **kein Befund**.

**4. Via-Kosten** (Negotiated Congestion, Dichte 60 %, Mittel über 20 Instanzen):

| Via-Kosten | Vias | Länge (Zellen) |
|---|---|---|
| 1 | 16,1 | 511 |
| 4 | 12,7 | 541 |
| 12 | 10,2 | 541 |
| 30 | 9,4 | 554 |

Teure Vias sparen Vias bis zu einem Sockel und kosten Länge; die Zahl unverlegter Netze ändert sich dabei nicht systematisch (Summe über 20 Instanzen: 7, 4, 5, 5).

**5. Mini-Bretter gegen den exakten Löser** (je 150 zufällige Bretter, Seeds 300000 bis 300149, Via-Kosten 4; der Löser hat in allen Fällen entweder das Optimum bewiesen oder Unlösbarkeit):

| Brett | unlösbar (bewiesen) | lösbar | davon: alle Reihenfolgen klappen | nur manche klappen | keine Reihenfolge klappt | Rip-up scheitert | Negotiated Congestion scheitert |
|---|---|---|---|---|---|---|---|
| 6 × 5, 5 Netze, 1 Sperrzelle | 108 | 42 | 32 | 9 | 1 | 2 | 0 |
| 5 × 5, 4 Netze, 1 Sperrzelle | 73 | 77 | 64 | 12 | 1 | 1 | 0 |
| 6 × 6, 6 Netze, 0 Sperrzellen | 104 | 46 | 29 | 14 | 3 | 0 | 0 |

Von 165 lösbaren Brettern gibt es also **5, an denen keine Reihenfolge funktioniert**, obwohl eine Lösung existiert; Rip-up scheitert an 3, Negotiated Congestion an keinem. Das **Handbeispiel** der App (6 × 5, 5 Netze, 1 Sperrzelle, Koordinaten in `lpl_mini.py`) ist so ein Brett: **0 von 120 Reihenfolgen** klappen, der Löser beweist das Optimum **25** (20 Schritte und ein Via-Schritt zu 5), Rip-up und Negotiated Congestion finden beide 25. Beim Zufalls-Seed 300057 (6 × 5) und bei 300020 (5 × 5 und 6 × 6) klappt ebenfalls keine Reihenfolge. Wo ein Verfahren oder eine Reihenfolge die Lösung findet, trifft die beste von ihnen auf den 5 × 5- und 6 × 5-Brettern immer das Optimum; auf den 6 × 6-Brettern liegen die besten Kosten im Mittel 0,4 % über dem Optimum (größter Abstand 13,5 %).

**6. Die Presets** (jeweils unverlegte Netze sequentiell / Rip-up / Negotiated Congestion):

| Preset | sequentiell | Rip-up | Negotiated Congestion |
|---|---|---|---|
| Standardfall (Voreinstellung) | 4 | 1 | 0 |
| Reihenfolge-Falle (lange Netze zuerst; mit kurzen zuerst bleiben auf demselben Brett 3) | 10 | 1 | 0 |
| Dichtes Brett (72 %) | 3 | 2 | 0 |
| Zu dicht (72 %, 25 Netze; Negotiated Congestion konvergiert nicht) | 7 | 5 | 3 |
| Zufällige Platzierung (55 %) | 5 | 3 | 0 |
| Lockeres Brett (4 ICs, 45 %) | 0 | 0 | 0 |

**7. Bestückung** (6 ICs, Dichte 60 %, Simulated-Annealing-Platzierung, 18 Bestückorte, **20 feste Instanzen**, Seeds 100000 bis 100019, 600 Kostenauswertungen je Bestückort und Suchverfahren): mittlere Fahrstrecke in Prozent über der kürzesten gefundenen Fahrt der Instanz.

| Düsen am Kopf | Maschinenpraxis | erst Plätze, dann Reihenfolge | abwechselnd | gemeinsam |
|---|---|---|---|---|
| 1 | 7,41 % | 0,39 % | 0,09 % | 0,01 % |
| 2 | 12,48 % | 1,87 % | 1,12 % | 0,28 % |
| 3 | 15,65 % | 3,45 % | 1,57 % | 0,59 % |
| 4 | 18,77 % | 3,84 % | 1,70 % | 0,65 % |

Bei **einer Düse** reicht die Trennung (0,39 %): erst die Plätze per Ungarischer Methode, dann die Reihenfolge. Je mehr Düsen, desto mehr verschenkt die Trennung (bei vier Düsen im Mittel 3,84 %, in einer Instanz 13,62 %), und gemeinsames Suchen ist in 15 von 20 Instanzen die kürzeste gefundene Fahrt (abwechselnd in 5, die Trennung in keiner). Die Maschinenpraxis liegt bei vier Düsen im Mittel 18,77 % über der kürzesten gefundenen Fahrt (größter Wert 35,73 %). Alle Zahlen sind Prozent über der besten **gefundenen** Fahrt, nicht über dem Optimum; auf Mini-Instanzen (6 Bestückorte, 3 Typen, 4 Plätze) trifft das gemeinsame Annealing das aufgezählte Optimum in allen 10 Instanzen bei einer Düse und in 8 von 10 bei zwei (`tests/test_bestueck.py`), die anderen Verfahren höchstens so oft (die Maschinenpraxis nie), keines unterschreitet es.

## Ehrliche Grenzen

- **Kein reales Layout.** Synthetische Netzlisten; keine Impedanz, kein Takt, keine EMV, keine Wärme, keine Leiterbahnbreiten, keine Innenlagen und keine Versorgungsflächen. Das Raster **ist** die Entwurfsregel; Pads sind Durchsteckpads auf beiden Lagen, Gehäuse sperren nur die Oberseite.
- **Heuristiken beweisen nichts.** Bleibt in der Hauptansicht ein Netz unverlegt, kann es an der Regel oder am Brett liegen; die Demo weiß es nicht. Nur der exakte Löser kann Unlösbarkeit beweisen, und der nur auf Mini-Brettern mit 2-Pin-Netzen und höchstens 6 Netzen.
- **Negotiated Congestion ist nicht vollständig** und braucht eine Iterationsgrenze: auf dem Handbeispiel und den 165 lösbaren Mini-Brettern hat es nie versagt, auf den Sensorboards konvergiert es bei 70 % Dichte nur in 12 von 20 Instanzen. Ob die übrigen 8 unlösbar sind, ist offen.
- **Stichprobe.** 20 Instanzen eines Generators und 150 Mini-Bretter je Form sind Messreihen, keine Schätzungen mit Unsicherheitsangabe; Aussagen wie „17 von 20 gegen 16 von 20“ sind keine Rangfolge.
- **Reihenfolge-Aussagen** gelten für sequentielles Verlegen mit kürzesten Wegen und die untersuchten Reihenfolgen; andere Reihenfolgeregeln (zum Beispiel nach Engstellen) sind nicht untersucht.
- **Bestückung ist ein Spielzeugmodell.** Ein Bestückort je Bauteil, ein Typ je Gehäuseart, ein Zuführplatz je Typ, 18 Bestückorte beim Standardbrett; keine Beschleunigung, keine Düsenwechsel, keine Teilehöhen, keine Bandbreiten, keine Zweiseitenbestückung, kein Nutzen mit mehreren Platinen. Die Zahlen sind Fahrstrecken in Rasterzellen, keine Maschinenzeiten. Die Rangfolge der gekoppelten Verfahren hängt am Budget (ein Probelauf mit anderem Budget, nicht als Test festgehalten, zeigte dasselbe Bild mit anderen Abständen; die Tabelle gilt für 600 Auswertungen je Bestückort).
- **Rechenzeit** ist nicht gemessen, nur die Zahl der Suchläufe. **Rip-up hängt an seiner Aktionsgrenze** (3 Aufreißvorgänge je Netz): mit 12 bleiben auf 6 festen Instanzen bei 70 % Dichte zusammen 2 statt 5 Netze unverlegt, bei 2,9-mal so vielen Suchläufen (12 235 gegen 4 225). Rip-up ist in den Tabellen also eher schlechter dargestellt, als es mit großzügigem Budget wäre; Negotiated Congestion kommt mit weniger Suchläufen aus (im Standardfall 550 gegen 1130 bei Rip-up).
- **Platzierung** ist kein Layouter: drei einfache Verfahren auf der Netzlänge; keine Platzierung nach Verlegbarkeit, keine Gruppen, keine Randabstände.

## Befunde und Korrekturen gegenüber dem Plan

- **Bestückung als Teil dieser Demo statt eigener Demo.** Der Plan (`bestueckung-planung/PLAN-01-bestueckung.md`) sah eine eigene Demo mit zufälligen Instanzen vor; gebaut wurde ein Abschnitt hier, der die Bauteile der platzierten Platine als Bestückorte nimmt. Die Phase-0-Zahlen (40 bis 100 zufällige Orte) stimmen deshalb nicht mit den README-Zahlen überein, und die Rangfolge hat sich verschoben: in Phase 0b (40 Orte, vier Düsen) war abwechselndes Verbessern besser als gemeinsames Annealing, hier (18 Orte, gleiches Budget je Ort, Zwischenspeicher für Runden) ist gemeinsames Annealing bei allen Düsenzahlen im Mittel am kürzesten. Geblieben ist: bei einer Düse genügt die Trennung, mit mehr Düsen verschenkt sie mehr.

- **Phase-0-Zahlen waren andere.** Die Vorabmessung (`leiterplatte-planung/`) lief mit Wegwerfcode, Python-`random` und 5 Instanzen. Im Bau wurden Generator (SplitMix64, Steckerpins, Pull-ups), Platzierung (Drehung bei der Legalisierung, große Bauteile zuerst) und Aktionsgrenze geändert, alle Zahlen neu an 20 Instanzen gemessen. Die Ergebnisse trugen sich nicht eins zu eins: auf Mini-Brettern waren es in Phase 0 rund 8 von 138 lösbaren, an denen keine Reihenfolge klappt, und Negotiated Congestion scheiterte an 3; jetzt sind es 5 von 165 und 0. Die Richtung (es gibt solche Bretter, Verhandeln schlägt Reihenfolge) ist geblieben, die Größen nicht.
- **Rip-up-Aktionsgrenze 3 statt 12 je Netz.** Zwölf verdreifachen den Aufwand (2,9-fache Zahl Suchläufe, einige Sekunden je Instanz in der App) und lassen auf 6 Instanzen bei 70 % Dichte 2 statt 5 Netze unverlegt; die App behält 3, damit sie reaktionsfähig bleibt, und weist die Abhängigkeit in den Grenzen aus.
- **Platzierungs-Hypothese weiter nicht belegt.** Phase 0 vermutete, die Platzierung mit der kleinsten Netzlänge sei nicht die am besten verlegbare; an 20 Instanzen trifft das nicht zu (Befund 3). Deshalb wurde auch keine Platzierung nach Verlegbarkeit gebaut (Plan E8).

## Verifikation

- **Kern gegen Handrechnung:** Pin- und Gehäusekoordinaten in beiden Drehungen, Brettgröße, HPWL, quadratische Zielpunkte gegen die geschlossene Formel, Kosten von Zeilen, Kreuzung und erzwungenem Via, Kosten- und Suchfunktion je Modus (`tests/test_scenario.py`, `test_placement.py`, `test_router.py`).
- **Bestückung (`tests/test_bestueck.py`, `test_bestueck_eval.py`):** Kosten einer Runde gegen die vollständige Aufzählung aller Hol- und Setzreihenfolgen (ohne die Geometrie der Zuführgeraden auszunutzen, 40 Fälle), Ungarische Methode gegen Aufzählung aller Zuordnungen, die Aussage „bei einer Düse und fester Reihenfolge ist die Fahrt eine Summe von Matrixeinträgen“ für alle Zuordnungen einer Instanz, Optimum durch Aufzählung aller Zuordnungen und Reihenfolgen auf Mini-Instanzen (kein Verfahren unterschreitet es), Spiegelung des Bretts, Verdikte an handgesetzten Werten, unabhängiger Prüfer `check_plan` auch in der App.
- **Orakel (`tests/test_oracle_leiterplatte.py`):** Kosten eines einzelnen Netzes gegen `networkx` (40 Bretter mit Sperrzellen), CP-SAT gegen Handrechnung (Optimum 6 und 25) und auf 16 Mini-Brettern gegen Aufzählung und beide Heuristiken (kein Verfahren unterschreitet das Optimum; wo der Löser Unlösbarkeit beweist, melden alle Verfahren unverlegte Netze).
- **Unabhängige Prüfer:** `check_feasible` (Kanten, Knotenbesitz, gesperrte Zellen, Anschluss aller Pads) läuft in jeder Analyse und in der App, `check_placement` für jede Platzierung; beide werden an gezielt verletzten Verlegungen geprüft.
- **Randfälle:** Reglerecken (Minimum und Maximum aller Regler, drei Platzierungen), kleinste und größte Instanz über viele Seeds, keine Netze, ein Netz, Iterationsgrenze 1, ungültige Namen.
- **Zweig-Tests:** sequentiell, Rip-up und Negotiated Congestion weichen auf dichten Brettern voneinander ab; die Platzierungsarten weichen voneinander ab; Via-Kosten verändern die Via-Zahl.
- **Verdikte** sind reine Funktionen und an handgesetzten Werten für jeden Zweig und jede Zahl im Text geprüft; **Presets** auf Vollständigkeit, gültige Werte und Standardgleichheit.
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler an Minimum und Maximum), Layout (Schnellstart oben, fester Kopf, aktives Preset hervorgehoben), Footer, Laufzeit-Importe gegen `requirements.txt`, PDF-Bericht, Determinismus über zwei Prozesse mit verschiedener Hash-Randomisierung.
- **Aussagen:** `tests/test_claims.py` rechnet jede Zahl dieses READMEs (Messreihen über 20 Instanzen und 3 × 150 Mini-Bretter) nach.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App: Ergebnis, Kernfrage, Methodenvergleich, Formeln, Grenzen |
| `lpl_constants.py` | Regler-Grenzen, feste Annahmen, Farben, Presets |
| `lpl_rng.py` | SplitMix64 |
| `lpl_scenario.py` | Bauteile, Netzliste, Brettgröße |
| `lpl_placement.py` | Zufall, quadratisch, Simulated Annealing, Platzierungsprüfer |
| `lpl_grid.py` | Raster, gesperrte Zellen und Pads |
| `lpl_search.py` | Mehrquellen-Dijkstra, drei Kostenmodi, Zustand eines Laufs |
| `lpl_router.py` | die drei Verlegeregeln, Kennzahlen, unabhängiger Verlegeprüfer |
| `lpl_mini.py` | Mini-Bretter, Handbeispiel, Aufzählung aller Reihenfolgen |
| `lpl_exact.py` | CP-SAT-Modell für Mini-Bretter |
| `lpl_evaluation.py` | Kennzahlen, Experimente über feste Instanzen, Verdikte |
| `lpl_bestueck.py` | Bestückung: Instanz aus der Platzierung, Rundenkosten, Zuordnung (Ungarische Methode), vier Verfahren, Prüfer |
| `lpl_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `lpl_pdf_export.py` | PDF-Bericht (fpdf2) |
| `lpl_layout.py` | Fester Kopf (Stylesheet) |
| `lpl_presets.py` | Permalink (Begrenzen), Presets, Zufalls-Seed-Button |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt) |
| `requirements-dev.txt` | Laufzeit plus pytest |
| `tests/` | Handrechnung, Orakel, Randfälle, Verdikte, Presets, Layout, Oberfläche, Footer, Laufzeit-Importe, PDF, Determinismus, Aussagen |

## Bewusst nicht umgesetzt

- **Platzierung nach Verlegbarkeit** (Dichte- oder Stauschätzung im Simulated Annealing): die Messung (Befund 3) liefert keinen Anlass.
- **Mehrpin-Netze im exakten Löser:** das Modell kennt nur 2-Pin-Netze; ein Löser für Bäume (Steiner) wäre ein eigenes Stück.
- **Entwurfsregeln, Leiterbahnbreiten, Innenlagen, Versorgungsflächen, Impedanz und Takt, Wärme:** das Raster ist die Regel.
- **Weitere Fertigungsschritte:** Bohrweg (reine Rundreise, im Portfolio schon vertreten) und Nutzenaufteilung (zweidimensionales Packen). Bei der Bestückung fehlen mehrere Platinen im Nutzen (der Rechenaufwand wächst, in Phase 0 kein zusätzlicher Befund), Düsenwechsel, Teilehöhen und Bandbreiten.
- **Schnellere Verfahren** (A* mit Heuristik, gerichtete Suche, parallele Verlegung): hier zählt die Aussage, nicht die Rechenzeit.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Die Aussagen-Tests (`tests/test_claims.py`) rechnen mehrere Minuten (Messreihen auf mehreren Prozessen); alle anderen laufen in wenigen Minuten. Die CI läuft mit Python 3.12, lokal läuft die jeweils neueste Version; die Streamlit-Cloud-Version steht in den App-Einstellungen.

Gebaut mit Streamlit, Plotly, NumPy, SciPy, OR-Tools und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zu den Demos: [Interaktive Demos](https://sebastianhanisch.net/demos.html).
