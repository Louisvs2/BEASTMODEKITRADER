# WHALE TRACKER

Desktop-Programm fuer Windows, macOS und Linux. Es zeigt die oeffentliche
Trader-Rangliste von **Hyperliquid**, die **live offenen Positionen** der
groessten Trader, ihre **zuletzt ausgefuehrten Trades** — und rechnet daraus
einen **konkreten Copy-Plan** fuer das eigene Kapital.

Echte Daten. Kein Mock. Kein Account, kein API-Key, keine Registrierung,
keine Installation von Zusatzpaketen.

---

## Starten

**Windows** — Doppelklick auf `start.bat`
**macOS** — Doppelklick auf `start.command`
**Linux** — `./start.sh`

Oder in einem Terminal im Projektordner:

```
python3 whaletracker.py
```

### Voraussetzung

Python 3 (ab 3.8) muss auf dem Rechner sein.

* **Windows**: Python von [python.org](https://www.python.org/downloads/) installieren.
  Beim Installieren "Add python.exe to PATH" ankreuzen und "tcl/tk and IDLE"
  angehakt lassen.
* **macOS**: Python von python.org installieren (das mitgelieferte Apple-Python
  hat manchmal kein tkinter). Alternativ `brew install python-tk`.
* **Linux**: `sudo apt install python3 python3-tk`

Beim ersten macOS-Start meldet sich eventuell Gatekeeper. Dann einmal
Rechtsklick auf `start.command` → "Oeffnen" → "Oeffnen".

---

## Wie man es benutzt

1. **Startseite**: Die Rangliste laedt automatisch. Oben rechts laesst sich der
   Zeitraum umschalten — 24 Stunden, 7 Tage, 30 Tage, All Time. Sortiert wird
   immer nach Gewinn im gewaehlten Zeitraum.
2. **Doppelklick** auf einen Trader. Dann sieht man:
   * seine **offenen Positionen**: Asset, Long oder Short, Groesse, Einstiegspreis,
     Positionswert, Hebel, aktueller Gewinn/Verlust, Liquidationspreis;
   * seine **letzten Trades**: wann, welches Asset, gekauft oder verkauft, zu
     welchem Preis, welche Menge, welcher realisierte Gewinn.
   * "AKTUALISIEREN" holt den Stand neu.
3. **`>_ COPY NOW`**: Eigenes Kapital eintragen, Risiko waehlen
   (vorsichtig / ausgewogen / aggressiv). Das Programm rechnet die Positionen
   des Traders auf die eigene Kontogroesse herunter und schreibt pro Position
   konkret hin:

   * Long oder Short,
   * Einsatz in USD und **die Stueckzahl** zum aktuellen Marktpreis,
   * empfohlener Hebel und die noetige Margin,
   * **Stop-Loss** und **Take-Profit** als konkrete Preise,
   * wie viel man verliert, wenn der Stop greift,
   * und wie die Position des Traders selbst dasteht.

   Unten stehen die Summen und der maximale Verlust, wenn alle Stops greifen.
   Der Plan laesst sich per Knopfdruck in die Zwischenablage kopieren oder als
   Textdatei speichern.

---

## Woher die Daten kommen

Es werden genau die oeffentlichen Endpunkte benutzt, die auch die Website
`app.hyperliquid.xyz` im Browser aufruft:

| Was | Quelle |
| --- | --- |
| Rangliste der Trader | `stats-data.hyperliquid.xyz/Mainnet/leaderboard` |
| Offene Positionen | `api.hyperliquid.xyz/info` → `clearinghouseState` |
| Ausgefuehrte Trades | `api.hyperliquid.xyz/info` → `userFills` |
| Marktpreise | `api.hyperliquid.xyz/info` → `allMids` |

Warum Hyperliquid: es ist die einzige grosse Boerse, bei der jede Position
jedes Traders oeffentlich on-chain einsehbar ist. Bei Binance oder Coinbase
sieht man fremde Positionen nicht.

Die Rangliste ist eine grosse Datei. Sie wird nach dem ersten Laden unter
`~/.whaletracker/leaderboard.json` zwischengespeichert und erst nach 6 Stunden
oder auf Knopfdruck ("RANGLISTE NEU LADEN") neu geholt. Die Positionen und
Trades eines einzelnen Traders sind dagegen klein und immer live.

---

## Tests

```
python3 test_copyplan.py
```

15 Tests fuer das Auswerten der Antworten und fuer die Plan-Rechnung
(Richtung, Gewichtung, Stops, Hebelgrenze, Rundung, leere Eingaben).
Kein Netz noetig.

---

## Dateien

| Datei | Inhalt |
| --- | --- |
| `whaletracker.py` | Programm und Oberflaeche |
| `hyperliquid_source.py` | Datenabruf und Auswertung |
| `copyplan.py` | Rechenlogik fuer den Copy-Plan |
| `test_copyplan.py` | Tests |

---

## Wichtig

Das Programm **fuehrt keine Orders aus** und ist mit keinem Broker verbunden.
Es liest oeffentliche Daten und rechnet daraus einen Vorschlag, den man selbst
umsetzen muesste. Der Trader, den man kopiert, kann jederzeit aussteigen, ohne
dass man es mitbekommt, und er handelt mit einem Vielfachen des eigenen
Kapitals. Keine Anlageberatung.
