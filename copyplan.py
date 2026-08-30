"""
Rechnet aus den ECHTEN offenen Positionen eines Traders einen konkreten,
nachbaubaren Plan fuer das eigene, viel kleinere Kapital.

Reine Rechenlogik, kein Netz, kein UI -> laesst sich direkt testen
(siehe test_copyplan.py).
"""

RISK_MODES = {
    # exposure: wie viel Gesamt-Nominalvolumen im Verhaeltnis zum Kapital
    # stop:     Stop-Abstand vom aktuellen Preis
    # maxLev:   Obergrenze fuer den Hebel
    # minTicket: unter diesem Betrag lohnt die Position nicht
    "VORSICHTIG":  {"exposure": 0.50, "stop": 0.05, "maxLev": 2.0, "minTicket": 25.0, "tranchen": 3},
    "AUSGEWOGEN":  {"exposure": 1.00, "stop": 0.08, "maxLev": 3.0, "minTicket": 20.0, "tranchen": 2},
    "AGGRESSIV":   {"exposure": 1.50, "stop": 0.12, "maxLev": 5.0, "minTicket": 15.0, "tranchen": 1},
}
DEFAULT_MODE = "AUSGEWOGEN"
MAX_SINGLE_WEIGHT = 0.40  # keine Einzelposition ueber 40 % des Plans


def _round_size(size):
    """Stueckzahl auf eine sinnvolle Stellenzahl runden."""
    if size >= 1000:
        return round(size, 1)
    if size >= 1:
        return round(size, 3)
    if size >= 0.01:
        return round(size, 4)
    return float("%.6g" % size)


def build_plan(positions, capital, mode=DEFAULT_MODE, mids=None):
    """
    positions: Liste aus hyperliquid_source.fetch_positions()["positions"]
    capital:   eigenes Kapital in USD
    mode:      Schluessel aus RISK_MODES
    mids:      aktuelle Marktpreise {coin: preis} (optional)

    Rueckgabe:
      {"mode","capital","exposure","legs":[...],"skipped":[...],
       "totalNotional","totalMargin","totalRisk"}
    """
    cfg = RISK_MODES.get(mode) or RISK_MODES[DEFAULT_MODE]
    mids = mids or {}
    capital = max(0.0, float(capital or 0.0))

    open_positions = [p for p in positions if p.get("notional", 0) > 0]
    total_notional = sum(p["notional"] for p in open_positions)
    if capital <= 0 or total_notional <= 0:
        return {
            "mode": mode, "capital": capital, "exposure": cfg["exposure"],
            "legs": [], "skipped": [], "totalNotional": 0.0,
            "totalMargin": 0.0, "totalRisk": 0.0,
        }

    budget = capital * cfg["exposure"]

    # Gewichte aus den echten Positionsgroessen, gedeckelt und neu normiert,
    # damit eine einzelne Riesenposition den Plan nicht komplett dominiert.
    weights = []
    for p in open_positions:
        weights.append(min(p["notional"] / total_notional, MAX_SINGLE_WEIGHT))
    wsum = sum(weights) or 1.0
    weights = [w / wsum for w in weights]

    legs, skipped = [], []
    for pos, weight in zip(open_positions, weights):
        coin = pos["coin"]
        price = mids.get(coin) or pos.get("entryPx") or 0.0
        notional = budget * weight
        if price <= 0:
            skipped.append({"coin": coin, "grund": "kein Preis verfuegbar"})
            continue
        if notional < cfg["minTicket"]:
            skipped.append({
                "coin": coin,
                "grund": "nur %.2f USD Anteil - unter Mindestgroesse %.0f USD"
                         % (notional, cfg["minTicket"]),
            })
            continue

        is_long = pos["side"] == "LONG"
        lev = max(1.0, min(pos.get("leverage") or 1.0, cfg["maxLev"]))
        stop_px = price * (1 - cfg["stop"]) if is_long else price * (1 + cfg["stop"])
        take_px = price * (1 + 2 * cfg["stop"]) if is_long else price * (1 - 2 * cfg["stop"])
        risk = notional * cfg["stop"]

        legs.append({
            "coin": coin,
            "side": pos["side"],
            "order": "LONG / KAUFEN" if is_long else "SHORT / VERKAUFEN",
            "weight": weight * 100.0,
            "notional": notional,
            "price": price,
            "size": _round_size(notional / price),
            "leverage": lev,
            "margin": notional / lev,
            "stop": stop_px,
            "take": take_px,
            "risk": risk,
            "tranchen": cfg["tranchen"],
            "whaleEntry": pos.get("entryPx", 0.0),
            "whaleNotional": pos.get("notional", 0.0),
            "whaleRoe": pos.get("roe", 0.0),
        })

    return {
        "mode": mode,
        "capital": capital,
        "exposure": cfg["exposure"],
        "stopPct": cfg["stop"],
        "legs": legs,
        "skipped": skipped,
        "totalNotional": sum(l["notional"] for l in legs),
        "totalMargin": sum(l["margin"] for l in legs),
        "totalRisk": sum(l["risk"] for l in legs),
    }


def _money(value):
    return "{:,.2f}".format(value).replace(",", " ")


def plan_as_text(plan, trader_address, trader_name="", account_value=0.0):
    """Der Plan als reiner Text - genau das, was in die Zwischenablage geht."""
    lines = []
    lines.append("=" * 66)
    lines.append("COPY-PLAN  -  WHALE TRACKER")
    lines.append("=" * 66)
    lines.append("Trader   : %s%s" % (trader_address, (" (%s)" % trader_name) if trader_name else ""))
    if account_value:
        lines.append("Dessen Kontowert: %s USD" % _money(account_value))
    lines.append("Dein Kapital    : %s USD" % _money(plan["capital"]))
    lines.append("Risikomodus     : %s  (Gesamt-Exposure %.0f %% des Kapitals)"
                 % (plan["mode"], plan["exposure"] * 100))
    lines.append("")

    if not plan["legs"]:
        lines.append("Kein umsetzbarer Plan: der Trader hat gerade keine offenen")
        lines.append("Positionen, oder dein Kapital ist zu klein fuer sinnvolle Groessen.")
        return "\n".join(lines)

    lines.append("KONKRETE ORDERS")
    lines.append("-" * 66)
    for i, leg in enumerate(plan["legs"], 1):
        lines.append("%d) %s  %s" % (i, leg["coin"], leg["order"]))
        lines.append("   Einsatz      : %s USD Nominal  (%.1f %% des Plans)"
                     % (_money(leg["notional"]), leg["weight"]))
        lines.append("   Menge        : %s %s  zum Preis von %s USD"
                     % (leg["size"], leg["coin"], _money(leg["price"])))
        lines.append("   Hebel        : %.1fx  ->  Margin %s USD"
                     % (leg["leverage"], _money(leg["margin"])))
        lines.append("   Stop-Loss    : %s USD   (Verlust dann ca. %s USD)"
                     % (_money(leg["stop"]), _money(leg["risk"])))
        lines.append("   Take-Profit  : %s USD" % _money(leg["take"]))
        if leg["tranchen"] > 1:
            lines.append("   Einstieg     : in %d gleich grossen Tranchen kaufen, nicht auf einmal"
                         % leg["tranchen"])
        lines.append("   Der Trader   : Einstieg %s USD, Position %s USD, aktuell %+.1f %%"
                     % (_money(leg["whaleEntry"]), _money(leg["whaleNotional"]), leg["whaleRoe"]))
        lines.append("")

    lines.append("-" * 66)
    lines.append("Summe Nominal : %s USD" % _money(plan["totalNotional"]))
    lines.append("Summe Margin  : %s USD" % _money(plan["totalMargin"]))
    lines.append("Max. Verlust wenn alle Stops greifen: %s USD (%.1f %% vom Kapital)"
                 % (_money(plan["totalRisk"]),
                    (plan["totalRisk"] / plan["capital"] * 100) if plan["capital"] else 0))
    lines.append("")

    if plan["skipped"]:
        lines.append("NICHT UEBERNOMMEN")
        for s in plan["skipped"]:
            lines.append("  - %s: %s" % (s["coin"], s["grund"]))
        lines.append("")

    lines.append("REGELN")
    lines.append("  1. Stop-Loss sofort mit der Order setzen, nicht spaeter.")
    lines.append("  2. Nie nachkaufen, wenn der Preis unter dem Stop steht.")
    lines.append("  3. Der Trader kann jederzeit aussteigen, ohne dass du es merkst.")
    lines.append("     Position taeglich gegen seine Live-Position pruefen.")
    lines.append("  4. Er handelt mit Hebel und einem Vielfachen deines Kapitals -")
    lines.append("     seine Verlusttoleranz ist nicht deine.")
    lines.append("")
    lines.append("Hinweis: Dieses Programm fuehrt nichts aus. Es liest oeffentliche")
    lines.append("Daten und rechnet. Keine Anlageberatung.")
    return "\n".join(lines)
