"""
Turns a trader's REAL open positions into a concrete, executable plan sized
for your own (much smaller) account.

Pure maths - no network, no UI - so it can be tested directly
(see test_copyplan.py).
"""

RISK_TIERS = {
    # exposure:  total notional as a multiple of your capital
    # stop:      stop distance from the current price
    # maxLev:    hard cap on leverage
    # minTicket: below this a position is not worth opening
    "SAFE":     {"exposure": 0.50, "stop": 0.05, "maxLev": 2.0, "minTicket": 25.0, "tranches": 3},
    "BALANCED": {"exposure": 1.00, "stop": 0.08, "maxLev": 3.0, "minTicket": 20.0, "tranches": 2},
    "DEGEN":    {"exposure": 1.50, "stop": 0.12, "maxLev": 5.0, "minTicket": 15.0, "tranches": 1},
}
TIER_ORDER = ("SAFE", "BALANCED", "DEGEN")
DEFAULT_TIER = "BALANCED"
MAX_SINGLE_WEIGHT = 0.40  # no single leg may exceed 40 % of the plan

TIER_BLURB = {
    "SAFE": "Half your capital at risk, tight 5 % stops, max 2x leverage.",
    "BALANCED": "Capital matched 1:1, 8 % stops, max 3x leverage.",
    "DEGEN": "1.5x your capital, wide 12 % stops, up to 5x leverage.",
}


def _capped_weights(raw, cap):
    """
    Turn raw position sizes into weights that sum to 1 and where none exceeds
    `cap`.

    Capping and then renormalising does NOT work: dividing by the reduced sum
    inflates the capped entry straight back over the limit. So the excess is
    poured into the entries that still have room, repeatedly, until every
    weight is under the cap.

    With few legs the cap can be arithmetically impossible (two legs cannot
    both stay under 40 %), so it is relaxed to an equal split in that case.
    """
    count = len(raw)
    if count == 0:
        return []
    cap = max(cap, 1.0 / count)
    total = float(sum(raw)) or 1.0
    weights = [value / total for value in raw]

    for _ in range(64):
        excess = 0.0
        room = 0.0
        for i, weight in enumerate(weights):
            if weight > cap + 1e-12:
                excess += weight - cap
                weights[i] = cap
            else:
                room += cap - weight
        if excess <= 1e-12 or room <= 1e-12:
            break
        # spread the overflow across the remaining headroom
        for i, weight in enumerate(weights):
            if weight < cap - 1e-12:
                weights[i] = weight + excess * (cap - weight) / room
    return weights


def _round_size(size):
    """Round a quantity to a sensible number of decimals."""
    if size >= 1000:
        return round(size, 1)
    if size >= 1:
        return round(size, 3)
    if size >= 0.01:
        return round(size, 4)
    return float("%.6g" % size)


def build_plan(positions, capital, tier=DEFAULT_TIER, mids=None):
    """
    positions: list from hyperliquid_source.fetch_positions()["positions"]
    capital:   your own capital in USD
    tier:      key of RISK_TIERS
    mids:      current mark prices {coin: price} (optional)

    Returns:
      {"tier","capital","exposure","legs":[...],"skipped":[...],
       "totalNotional","totalMargin","totalRisk"}
    """
    cfg = RISK_TIERS.get(tier) or RISK_TIERS[DEFAULT_TIER]
    mids = mids or {}
    capital = max(0.0, float(capital or 0.0))

    open_positions = [p for p in positions if p.get("notional", 0) > 0]
    total_notional = sum(p["notional"] for p in open_positions)
    if capital <= 0 or total_notional <= 0:
        return {
            "tier": tier, "capital": capital, "exposure": cfg["exposure"],
            "stopPct": cfg["stop"], "legs": [], "skipped": [], "trimmed": [],
            "totalNotional": 0.0, "totalMargin": 0.0, "totalRisk": 0.0,
        }

    budget = capital * cfg["exposure"]

    # Weights follow the trader's real position sizes, but no single leg may
    # swallow the plan - see _capped_weights for why a plain cap is not enough.
    raw = [p["notional"] for p in open_positions]
    weights = _capped_weights(raw, MAX_SINGLE_WEIGHT)

    # Note where the limit actually changed the mirroring, so the plan can say
    # so instead of quietly handing over a different allocation.
    raw_total = float(sum(raw)) or 1.0
    trimmed = [pos["coin"] for pos, w, r in zip(open_positions, weights, raw)
               if w < r / raw_total - 1e-9]

    legs, skipped = [], []
    for pos, weight in zip(open_positions, weights):
        coin = pos["coin"]
        price = mids.get(coin) or pos.get("entryPx") or 0.0
        notional = budget * weight
        if price <= 0:
            skipped.append({"coin": coin, "reason": "no price available"})
            continue
        if notional < cfg["minTicket"]:
            skipped.append({
                "coin": coin,
                "reason": "only $%.2f allocated - below the $%.0f minimum"
                          % (notional, cfg["minTicket"]),
            })
            continue

        is_long = pos["side"] == "LONG"
        lev = max(1.0, min(pos.get("leverage") or 1.0, cfg["maxLev"]))
        stop_px = price * (1 - cfg["stop"]) if is_long else price * (1 + cfg["stop"])
        take_px = price * (1 + 2 * cfg["stop"]) if is_long else price * (1 - 2 * cfg["stop"])

        legs.append({
            "coin": coin,
            "side": pos["side"],
            "action": "BUY / LONG" if is_long else "SELL / SHORT",
            "weight": weight * 100.0,
            "notional": notional,
            "price": price,
            "size": _round_size(notional / price),
            "leverage": lev,
            "margin": notional / lev,
            "stop": stop_px,
            "take": take_px,
            "risk": notional * cfg["stop"],
            "tranches": cfg["tranches"],
            "whaleEntry": pos.get("entryPx", 0.0),
            "whaleNotional": pos.get("notional", 0.0),
            "whaleRoe": pos.get("roe", 0.0),
        })

    return {
        "tier": tier,
        "capital": capital,
        "exposure": cfg["exposure"],
        "stopPct": cfg["stop"],
        "legs": legs,
        "skipped": skipped,
        "trimmed": [c for c in trimmed if any(l["coin"] == c for l in legs)],
        "totalNotional": sum(l["notional"] for l in legs),
        "totalMargin": sum(l["margin"] for l in legs),
        "totalRisk": sum(l["risk"] for l in legs),
    }


def _money(value):
    return "{:,.2f}".format(value)


def plan_as_text(plan, trader_address, trader_name="", account_value=0.0):
    """The plan as plain text - exactly what lands on the clipboard."""
    lines = []
    lines.append("=" * 68)
    lines.append("COPY PLAN  ·  WHALE TRACKER")
    lines.append("=" * 68)
    lines.append("Trader        : %s%s" % (trader_address,
                                           (" (%s)" % trader_name) if trader_name else ""))
    if account_value:
        lines.append("Their equity  : $%s" % _money(account_value))
    lines.append("Your capital  : $%s" % _money(plan["capital"]))
    lines.append("Risk tier     : %s  (total exposure %.0f %% of capital)"
                 % (plan["tier"], plan["exposure"] * 100))
    lines.append("")

    if not plan["legs"]:
        lines.append("No executable plan: this trader currently holds no open")
        lines.append("positions, or your capital is too small for sensible sizes.")
        return "\n".join(lines)

    lines.append("ORDERS")
    lines.append("-" * 68)
    for i, leg in enumerate(plan["legs"], 1):
        lines.append("%d) %s  %s" % (i, leg["coin"], leg["action"]))
        lines.append("   Size       : %s %s  at $%s"
                     % (leg["size"], leg["coin"], _money(leg["price"])))
        lines.append("   Notional   : $%s  (%.1f %% of the plan)"
                     % (_money(leg["notional"]), leg["weight"]))
        lines.append("   Leverage   : %.1fx  ->  $%s margin"
                     % (leg["leverage"], _money(leg["margin"])))
        lines.append("   Stop loss  : $%s   (loses about $%s)"
                     % (_money(leg["stop"]), _money(leg["risk"])))
        lines.append("   Take profit: $%s" % _money(leg["take"]))
        if leg["tranches"] > 1:
            lines.append("   Entry      : split into %d equal tranches, not all at once"
                         % leg["tranches"])
        lines.append("   Their side : entry $%s, position $%s, currently %+.1f %%"
                     % (_money(leg["whaleEntry"]), _money(leg["whaleNotional"]),
                        leg["whaleRoe"]))
        lines.append("")

    lines.append("-" * 68)
    lines.append("Total notional : $%s" % _money(plan["totalNotional"]))
    lines.append("Total margin   : $%s" % _money(plan["totalMargin"]))
    lines.append("Worst case if every stop hits: $%s  (%.1f %% of capital)"
                 % (_money(plan["totalRisk"]),
                    (plan["totalRisk"] / plan["capital"] * 100) if plan["capital"] else 0))
    lines.append("")

    if plan.get("trimmed"):
        lines.append("POSITION LIMIT APPLIED")
        lines.append("  %s held a larger share of their book than this plan gives"
                     % ", ".join(plan["trimmed"]))
        lines.append("  it. No single position may exceed %.0f %% here, so the"
                     % (MAX_SINGLE_WEIGHT * 100))
        lines.append("  surplus went to the others. Your mix is deliberately less")
        lines.append("  concentrated than theirs.")
        lines.append("")

    if plan["skipped"]:
        lines.append("SKIPPED")
        for item in plan["skipped"]:
            lines.append("  - %s: %s" % (item["coin"], item["reason"]))
        lines.append("")

    lines.append("RULES")
    lines.append("  1. Place the stop loss with the order, not later.")
    lines.append("  2. Never add to a position trading below its stop.")
    lines.append("  3. This trader can exit at any moment without you noticing.")
    lines.append("     Re-check their live position daily.")
    lines.append("  4. They trade with leverage and many times your capital -")
    lines.append("     their pain tolerance is not yours.")
    lines.append("")
    lines.append("This program executes nothing. It reads public data and does")
    lines.append("the maths. Not financial advice.")
    return "\n".join(lines)
