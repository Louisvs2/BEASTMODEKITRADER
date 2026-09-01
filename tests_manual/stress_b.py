"""Stress part B: the copy engine under nonsense input, then failure modes."""
import os, sys, time
from stress_common import check, report, start, BOXES
import copyplan

app, wt, server, tmp = start()

def settle(n=30):
    for _ in range(n):
        app.update(); time.sleep(0.015)

settle(120)
app.open_trader(app.traders[0]); settle(100)
check("detail loaded", len(app.detail.pos_tree.get_children()) == 2)

print("\n[7] copy dialog with nonsense capital")
app.open_copy_dialog(); settle(20)
dlg = [w for w in app.winfo_children() if isinstance(w, wt.CopyDialog)][-1]
check("dialog opened", dlg is not None)

for value in ("abc", "", "-5", "0", "1e9", "1,000", "0.0001",
              "999999999999", "  50  ", "1.5.5", "-0", "NaN", "Infinity"):
    dlg.capital.set(value)
    try:
        dlg.render(); settle(2)
        plan = dlg.build()
    except Exception as exc:
        check("capital %r handled" % value, False, "%s: %s" % (type(exc).__name__, exc))
        continue
    budget = dlg._capital() * plan["exposure"]
    if plan["totalNotional"] > budget + 0.01:
        check("capital %r stays in budget" % value, False,
              "notional %.2f > budget %.2f" % (plan["totalNotional"], budget))
check("every capital input handled without crashing", True)

print("\n[8] risk tiers respect their own limits")
for tier in copyplan.TIER_ORDER:
    dlg.capital.set("5000"); dlg.set_tier(tier); settle(3)
    plan = dlg.build()
    cfg = copyplan.RISK_TIERS[tier]
    check("%s within exposure" % tier,
          plan["totalNotional"] <= 5000 * cfg["exposure"] + 0.01,
          "%.2f" % plan["totalNotional"])
    check("%s leverage capped" % tier,
          all(l["leverage"] <= cfg["maxLev"] for l in plan["legs"]))
    check("%s worst case below capital" % tier, plan["totalRisk"] < 5000,
          "%.2f" % plan["totalRisk"])
    check("%s margin <= notional" % tier, plan["totalMargin"] <= plan["totalNotional"] + 0.01)

print("\n[9] clipboard and file output")
dlg.capital.set("2500"); dlg.set_tier("BALANCED"); settle(4)
dlg.copy_plan(); settle(4)
clip = app.clipboard_get()
check("clipboard holds a real plan", "COPY PLAN" in clip and "Stop loss" in clip)
check("clipboard names the trader", app.traders[0]["address"] in clip)
out = os.path.join(tmp, "plan.txt")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(dlg.text.get("1.0", "end-1c"))
check("plan is substantial", os.path.getsize(out) > 500)
dlg.destroy(); settle(5)

print("\n[10] hammered refresh and navigation")
for _ in range(6):
    app.refresh_detail(); settle(8)
settle(90)
check("survives repeated refresh", bool(app.winfo_exists()))
check("refresh button re-enabled", app.detail.btn_refresh.enabled)
for _ in range(5):
    app.show_board(); settle(4)
    app.open_trader(app.traders[1]); settle(12)
settle(60)
check("navigation stable", bool(app.winfo_exists()))

print("\n[11] server dies mid-session")
server.shutdown(); server.server_close()
BOXES.clear()
app.load_leaderboard(force=True); settle(90)
check("network failure handled", bool(app.winfo_exists()))
check("status turns red or amber", app.status.cget("fg") in (wt.T.RED, wt.T.GOLD),
      "%s / %s" % (app.status.cget("fg"), app.status.cget("text")))
check("cached leaderboard still on screen", len(app.board.cards.items) > 0)

app.destroy()
sys.exit(report())
