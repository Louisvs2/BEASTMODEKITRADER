"""
Property test for the plan maths: thousands of random position sets checked
against invariants that must hold no matter what the exchange returns.
A copy plan drives real money, so 'it looked right in one screenshot' is not
enough.
"""
import math
import os
import re
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import copyplan

COINS = ["BTC", "ETH", "SOL", "kPEPE", "@142", "HYPE", "X" * 20]
PROBLEMS = []


def note(case, msg):
    PROBLEMS.append((case, msg))


def finite(*values):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def random_positions(rng):
    out = []
    for _ in range(rng.randint(1, 12)):
        price = rng.choice([
            rng.uniform(1e-8, 1e-4),      # meme-coin dust
            rng.uniform(0.01, 5),
            rng.uniform(100, 5000),
            rng.uniform(20000, 150000),   # BTC
        ])
        notional = rng.choice([
            rng.uniform(1, 100),
            rng.uniform(1e3, 1e6),
            rng.uniform(1e7, 5e8),        # whale size
        ])
        out.append({
            "coin": rng.choice(COINS),
            "side": rng.choice(["LONG", "SHORT"]),
            "notional": notional,
            "entryPx": price * rng.uniform(0.5, 1.5),
            "leverage": rng.choice([0, 1, 1.5, 3, 5, 10, 20, 50]),
            "roe": rng.uniform(-95, 400),
            "uPnl": rng.uniform(-1e6, 1e6),
            "size": notional / price,
        })
    return out


def run(iterations=20000):
    rng = random.Random(20260901)
    for i in range(iterations):
        positions = random_positions(rng)
        capital = rng.choice([0, 1, 25, 100, 1000, 25000, 1e6, 1e9])
        tier = rng.choice(copyplan.TIER_ORDER)
        mids = {p["coin"]: p["entryPx"] * rng.uniform(0.6, 1.6)
                for p in positions if rng.random() > 0.2}  # some prices missing

        plan = copyplan.build_plan(positions, capital, tier, mids)
        cfg = copyplan.RISK_TIERS[tier]
        case = "i=%d tier=%s capital=%s legs=%d" % (i, tier, capital, len(plan["legs"]))

        budget = capital * cfg["exposure"]
        if plan["totalNotional"] > budget + 1e-6:
            note(case, "notional %.6f exceeds budget %.6f" % (plan["totalNotional"], budget))

        if not finite(plan["totalNotional"], plan["totalMargin"], plan["totalRisk"]):
            note(case, "non-finite totals")

        if plan["totalMargin"] > plan["totalNotional"] + 1e-6:
            note(case, "margin above notional")

        if capital > 0 and plan["totalRisk"] > capital * cfg["exposure"] * cfg["stop"] + 1e-6:
            note(case, "risk %.6f above the tier's own ceiling" % plan["totalRisk"])

        weight_sum = 0.0
        for leg in plan["legs"]:
            weight_sum += leg["weight"]
            if not finite(leg["size"], leg["price"], leg["notional"], leg["stop"],
                          leg["take"], leg["margin"], leg["risk"], leg["leverage"]):
                note(case, "non-finite leg %s" % leg["coin"]); continue
            if leg["size"] <= 0 or leg["price"] <= 0 or leg["notional"] <= 0:
                note(case, "non-positive leg %s" % leg["coin"])
            if abs(leg["size"] * leg["price"] - leg["notional"]) > leg["notional"] * 0.05:
                note(case, "size x price != notional for %s" % leg["coin"])
            if not (1.0 <= leg["leverage"] <= cfg["maxLev"] + 1e-9):
                note(case, "leverage %s out of range" % leg["leverage"])
            if abs(leg["margin"] * leg["leverage"] - leg["notional"]) > 1e-6 * max(1, leg["notional"]):
                note(case, "margin x leverage != notional for %s" % leg["coin"])
            if leg["side"] == "LONG":
                if not (leg["stop"] < leg["price"] < leg["take"]):
                    note(case, "long stop/take wrong for %s" % leg["coin"])
            else:
                if not (leg["take"] < leg["price"] < leg["stop"]):
                    note(case, "short stop/take wrong for %s" % leg["coin"])
            if leg["notional"] < cfg["minTicket"] - 1e-9:
                note(case, "leg below the minimum ticket")
            allowed = max(40.0, 100.0 / len(plan["legs"]))
            if leg["weight"] > allowed + 1e-6:
                note(case, "weight %.2f above the %.1f %% cap" % (leg["weight"], allowed))

        if plan["legs"] and not plan["skipped"] and abs(weight_sum - 100.0) > 0.01:
            note(case, "weights sum to %.4f, not 100" % weight_sum)

        # the renderer must survive anything the builder produced
        try:
            text = copyplan.plan_as_text(plan, "0xabc", "name", 1234.5)
            # whole words only - "financial" contains "inf"
            if re.search(r"\b(nan|inf|infinity)\b", text, re.I):
                note(case, "nan/inf leaked into the printed plan")
        except Exception as exc:
            note(case, "renderer raised %s: %s" % (type(exc).__name__, exc))

    return iterations


count = run()
print("checked %d random position sets" % count)
if PROBLEMS:
    print("\n%d PROBLEMS (first 12):" % len(PROBLEMS))
    for case, msg in PROBLEMS[:12]:
        print("  %-46s %s" % (case, msg))
    sys.exit(1)
print("all invariants hold")
