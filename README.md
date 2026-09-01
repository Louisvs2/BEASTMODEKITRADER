# BEASTMODE AI TOOL

A desktop app that shows Hyperliquid's public trader leaderboard, each
trader's **live open positions**, their **most recent trades** — and turns
those real positions into a **concrete copy plan** sized for your own capital.

Real data. No mock. No account, no API key, no signup, nothing to install
beyond Python itself.

---

## Run it on a Mac

**Double-click `BEASTMODE AI TOOL.app`.**

That is the whole thing. The bundle finds a usable Python on your Mac by
itself and starts the app. If none exists it tells you exactly what to install.

First launch may show a Gatekeeper warning, because the app is not signed by
Apple. Right-click `BEASTMODE AI TOOL.app` → **Open** → **Open**. Once only.

Prefer the Terminal? `./start.command`, or `python3 beastmode.py`.

### If it starts but loads nothing

A red line at the bottom saying

```
[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate
```

means this Mac's Python has no trusted root certificates — a python.org
install does not register them — so it cannot verify any HTTPS connection.

**Double-click `fix_certificates.command`.** It runs the official
`Install Certificates.command` from your Python installation, falls back to
installing the `certifi` bundle, and then actually tests the connection so
you know whether it worked. Certificate checking is never switched off.

### If it will not start

Double-click **`check_mac.command`**. It prints every Python on this Mac, says
which of them can open a window, and why the others cannot. That output
answers the question in one glance.

### If it says no Python was found

You need a Python whose Tk actually works on your macOS version. The newest
Python is not always the right one — Python 3.14 ships a Tk that demands
macOS 15.7 and aborts on anything older with:

```
macOS 15 (1507) or later required, have instead 15 (1506) !
```

Two ways out:

1. **Update macOS** — System Settings → General → Software Update.
2. **Install [Python 3.12](https://www.python.org/downloads/release/python-3128/)**
   (macOS 64-bit universal2 installer). Its Tk runs on older macOS. You can
   keep 3.14 installed; the launcher picks whichever one works.

Check it in one line:

```
python3.12 -c "import tkinter; tkinter.Tk(); print('window works')"
```

### Building the version you sell

```
./build_release.sh
```

Must run on a Mac. It bundles Python and Tk into `dist/BEASTMODE AI TOOL.app`
and packs it into `dist/BEASTMODE AI TOOL.dmg` — the file to put on your
website. A buyer needs nothing installed.

Set two variables first and the build is also signed, notarised and stapled,
which is what stops macOS warning your buyers:

```
export CODESIGN_ID="Developer ID Application: Your Name (TEAMID)"
export NOTARY_PROFILE="beastmode"
```

Without them the build still works, but buyers must allow the app once under
System Settings → Privacy & Security. That path is documented in
`BEASTMODE_AI_TOOL_Tutorial.pdf`, the guide to ship alongside the download.

## Windows and Linux

`start.bat` on Windows, `./start.sh` on Linux
(`sudo apt install python3-tk` first).

---

## How to use it

**1 · Ranks.** The leaderboard loads on start. Switch the timeframe with
**24H / 7D / 30D / ALL TIME** — traders are always ranked by profit over the
window you picked. Search filters by wallet address.

**2 · Click a trader.** You get their live state:

* **Open positions** — asset, long or short, size, entry price, position
  value, leverage, unrealised PnL, liquidation price.
* **Recent fills** — when, which asset, bought or sold, at what price, in what
  size, and what they realised. This is the "what did they just buy" view.
* **REFRESH** pulls it again.

**3 · `⚡ COPY NOW`.** Enter your capital, pick a risk tier:

| Tier | Exposure | Stop | Max leverage |
| --- | --- | --- | --- |
| SAFE | 50 % of capital | 5 % | 2x |
| BALANCED | 100 % | 8 % | 3x |
| DEGEN | 150 % | 12 % | 5x |

The app scales their positions down onto your account and writes out, per
position:

* buy or sell, long or short,
* the **quantity** to trade at the current mark price,
* notional, suggested leverage and the margin it needs,
* a concrete **stop loss** and **take profit** price,
* what you lose if that stop is hit,
* and how their own position is doing.

Below that: totals, and your worst case if every stop triggers at once.
Copy it to the clipboard or save it as a text file.

---

## Where the data comes from

The app calls exactly the public endpoints that `app.hyperliquid.xyz` itself
calls from the browser:

| What | Source |
| --- | --- |
| Trader ranking | `stats-data.hyperliquid.xyz/Mainnet/leaderboard` |
| Open positions | `api.hyperliquid.xyz/info` → `clearinghouseState` |
| Executed trades | `api.hyperliquid.xyz/info` → `userFills` |
| Mark prices | `api.hyperliquid.xyz/info` → `allMids` |

Why Hyperliquid: it is the one large exchange where every trader's position is
publicly visible on-chain. On Binance or Coinbase you cannot see anyone else's
book.

The ranking is a large file. It is cached at `~/.beastmode/leaderboard.json`
after the first load and only refetched after 6 hours, or when you press
**REFRESH RANKS**. Positions and fills for a single trader are small and always
live.

---

## Tests

```
python3 test_copyplan.py       # 21 unit tests
python3 test_integration.py    # 15 end-to-end tests against a local server
```

The integration suite starts a small HTTP server that answers with real
Hyperliquid response shapes, so the download, gzip handling, streaming parse,
disk cache and error paths all run for real. No internet needed.

Deeper checks live in `tests_manual/`:

```
python3 tests_manual/property_test.py                 # 20,000 random books
cd tests_manual && xvfb-run python3 stress_a.py       # GUI under hostile input
cd tests_manual && xvfb-run python3 stress_b.py
```

---

## Files

| File | Contents |
| --- | --- |
| `beastmode.py` | app and screens |
| `widgets.py` | the custom neon canvas widgets |
| `theme.py` | colours, fonts, number formatting |
| `hyperliquid_source.py` | fetching and parsing |
| `copyplan.py` | the plan maths |
| `test_copyplan.py` | unit tests for parsing and the plan maths |
| `test_integration.py` | end-to-end tests against a local stand-in server |
| `tests_manual/` | GUI stress runs and a property test over random books |
| `check_mac.command` | double-click: lists every Python here and which one works |
| `fix_certificates.command` | double-click: repairs the HTTPS certificate store |
| `make_icon.py` | regenerates the app icon |
| `make_tutorial.py` | regenerates the customer tutorial PDF |
| `build_release.sh` | builds the sellable .app and .dmg |

---

## Important

This program **places no orders** and is connected to no broker. It reads
public data and does arithmetic on it; acting on the result is entirely on
you. The trader you mirror can close out at any moment without you noticing,
and they trade with many times your capital — their tolerance for a drawdown
is not yours. Not financial advice.
