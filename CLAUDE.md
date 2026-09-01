# Arbeitsanweisungen für Claude in diesem Projekt

## Wie ich mit dem Nutzer rede

**Sprache:** Antworten auf Deutsch. Das Programm selbst — Oberfläche, Code,
Kommentare, README — auf Englisch.

**Anleitungen: immer als nummerierte Schritte, nie als Fließtext.**

Wenn der Nutzer etwas tun soll, gilt ohne Ausnahme:

1. Nummerierte Liste, ein Handgriff pro Punkt.
2. Jeder Befehl in einem eigenen Codeblock, zum Kopieren.
3. Kein Vorwissen voraussetzen — „Terminal öffnen" ist ein eigener Schritt.
4. Pro Schritt eine Zeile, die sagt, was danach passieren sollte
   („Es geht ein Fenster auf", „Die Liste füllt sich").
5. Erklärungen, Hintergrund und Warnungen kommen **nach** den Schritten,
   nicht zwischen sie.

Falsch:

> Zieh dir erst mit git pull die neue Version, dann kannst du im Finder auf
> WhaleTracker.app doppelklicken, aber beim ersten Mal musst du Rechtsklick
> machen wegen Gatekeeper.

Richtig:

> 1. Terminal öffnen (⌘ + Leertaste → „Terminal")
> 2. Diesen Befehl einfügen:
>    ```
>    cd ~/Desktop/BEASTMODEKITRADER && git pull
>    ```
> 3. Im Finder auf `WhaleTracker.app` doppelklicken
>    → Beim allerersten Mal stattdessen: Rechtsklick → „Öffnen" → „Öffnen"
>
> Warum der Rechtsklick: die App ist nicht von Apple signiert.

Wenn es Fehlerfälle gibt, kommen die als eigener Block **danach**:
„Falls X passiert → mach Y."

## Das Projekt

Whale Tracker: Desktop-App (macOS/Windows/Linux), zeigt die öffentliche
Trader-Rangliste von Hyperliquid, deren Live-Positionen und letzte Trades, und
rechnet daraus einen Copy-Plan für das Kapital des Nutzers.

- Nur Standardbibliothek, keine Abhängigkeiten. Das bleibt so.
- Der Nutzer ist auf einem **Mac**. Startet per Doppelklick auf
  `WhaleTracker.app`, nicht über das Terminal.
- Der Nutzer ist kein Entwickler. Keine Fachbegriffe ohne Erklärung.

### Starten

```
python3 whaletracker.py
```

### Tests

```
python3 test_copyplan.py                        # Unit-Tests
python3 test_integration.py                     # gegen lokalen Server
python3 tests_manual/property_test.py           # Zufallsdaten
cd tests_manual && xvfb-run python3 stress_a.py # GUI-Härtetest
cd tests_manual && xvfb-run python3 stress_b.py
```

## Was hier gilt

- **Keine Mock-Daten.** Der Nutzer hat das ausdrücklich verworfen. Alles kommt
  aus echten öffentlichen Quellen.
- **Zertifikatsprüfung bleibt an.** Sie abzuschalten würde Fehler verstecken
  und gefälschte Kursdaten ermöglichen.
- **Diese Umgebung hat kein Internet.** Der echte Abruf gegen Hyperliquid ist
  hier nicht testbar — das dem Nutzer sagen, statt Erfolg zu behaupten.
- **Entwickelt wird auf** `claude/trading-tool-asset-tracking-47nwwv`.
