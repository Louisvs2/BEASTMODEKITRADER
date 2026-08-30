"""
Datenquelle: Hyperliquid (oeffentlich, ohne Account, ohne API-Key, ohne Registrierung).

Es werden genau drei oeffentliche Endpunkte benutzt, dieselben, die auch die
Website app.hyperliquid.xyz im Browser benutzt:

  1. https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
     -> die Liste der Trader (Rangliste), so wie sie unter
        app.hyperliquid.xyz/leaderboard oeffentlich zu sehen ist.
  2. POST https://api.hyperliquid.xyz/info  {"type": "clearinghouseState", "user": <adresse>}
     -> die aktuell OFFENEN Positionen dieses Traders (live).
  3. POST https://api.hyperliquid.xyz/info  {"type": "userFills", "user": <adresse>}
     -> die zuletzt AUSGEFUEHRTEN Trades dieses Traders (live).

Zusaetzlich {"type": "allMids"} fuer die aktuellen Marktpreise.

Alles nur ueber urllib aus der Standardbibliothek - keine Installation noetig.
"""

import gzip
import io
import json
import os
import ssl
import time
import urllib.error
import urllib.request

INFO_URL = "https://api.hyperliquid.xyz/info"
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
WEB_LEADERBOARD = "https://app.hyperliquid.xyz/leaderboard"

USER_AGENT = "WhaleTracker/1.0 (+desktop; stdlib-urllib)"
TIMEOUT = 45

# Die Rangliste ist eine grosse Datei. Sie wird lokal zwischengespeichert und
# nur auf Wunsch (oder wenn aelter als CACHE_MAX_AGE) neu geladen.
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".whaletracker")
CACHE_FILE = os.path.join(CACHE_DIR, "leaderboard.json")
CACHE_MAX_AGE = 60 * 60 * 6  # 6 Stunden
MAX_LEADERBOARD_BYTES = 400 * 1024 * 1024

WINDOWS = ("day", "week", "month", "allTime")
WINDOW_LABEL = {
    "day": "24 STUNDEN",
    "week": "7 TAGE",
    "month": "30 TAGE",
    "allTime": "ALL TIME",
}


class SourceError(Exception):
    """Fehler beim Holen der Daten - wird im UI als Klartext angezeigt."""


def _ssl_context():
    try:
        return ssl.create_default_context()
    except Exception:
        return None


def _open(req, timeout=TIMEOUT):
    ctx = _ssl_context()
    try:
        if ctx is not None:
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise SourceError("Server antwortete mit HTTP %s (%s)" % (exc.code, exc.reason))
    except urllib.error.URLError as exc:
        raise SourceError("Keine Verbindung: %s" % (exc.reason,))
    except Exception as exc:  # socket timeouts, ssl, ...
        raise SourceError("Verbindungsfehler: %s" % (exc,))


def _decode_body(resp, raw):
    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def post_info(payload):
    """Ein POST an den oeffentlichen /info Endpunkt."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        INFO_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    resp = _open(req)
    text = _decode_body(resp, resp.read())
    try:
        return json.loads(text)
    except ValueError:
        raise SourceError("Antwort war kein gueltiges JSON (%s ...)" % text[:120])


# --------------------------------------------------------------------------
# 1) Rangliste der Trader
# --------------------------------------------------------------------------

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_leaderboard(data):
    """Rohantwort -> Liste einfacher Trader-Dicts, absteigend nach 30-Tage-PnL."""
    rows = data.get("leaderboardRows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise SourceError("Unerwartetes Format der Rangliste.")

    traders = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        addr = row.get("ethAddress") or row.get("user") or ""
        if not addr:
            continue
        perf = {}
        for entry in row.get("windowPerformances") or []:
            # Format: ["day", {"pnl": "...", "roi": "...", "vlm": "..."}]
            if isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[1], dict):
                perf[entry[0]] = {
                    "pnl": _num(entry[1].get("pnl")),
                    "roi": _num(entry[1].get("roi")),
                    "vlm": _num(entry[1].get("vlm")),
                }
        for win in WINDOWS:
            perf.setdefault(win, {"pnl": 0.0, "roi": 0.0, "vlm": 0.0})

        traders.append({
            "address": addr,
            "name": row.get("displayName") or "",
            "accountValue": _num(row.get("accountValue")),
            "perf": perf,
        })

    if not traders:
        raise SourceError("Rangliste enthielt keine Trader.")
    traders.sort(key=lambda t: t["perf"]["month"]["pnl"], reverse=True)
    return traders


def cached_leaderboard_age():
    """Alter des Caches in Sekunden, oder None wenn kein Cache da ist."""
    if not os.path.exists(CACHE_FILE):
        return None
    return time.time() - os.path.getmtime(CACHE_FILE)


def load_cached_leaderboard():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def fetch_leaderboard(progress=None, force=False, limit=250):
    """
    Holt die Rangliste. Nutzt den lokalen Cache, wenn er frisch genug ist.
    `progress(text)` wird waehrend des Downloads mit Statusmeldungen gerufen.
    """
    def say(text):
        if progress:
            progress(text)

    age = cached_leaderboard_age()
    if not force and age is not None and age < CACHE_MAX_AGE:
        cached = load_cached_leaderboard()
        if cached:
            say("Rangliste aus lokalem Cache (%d Min alt)." % int(age // 60))
            return cached[:limit], int(age)

    say("Lade oeffentliche Rangliste von stats-data.hyperliquid.xyz ...")
    req = urllib.request.Request(
        LEADERBOARD_URL,
        headers={"Accept": "application/json", "Accept-Encoding": "gzip", "User-Agent": USER_AGENT},
    )
    resp = _open(req, timeout=180)

    total = resp.headers.get("Content-Length")
    total = int(total) if total and total.isdigit() else 0
    buf = io.BytesIO()
    read = 0
    while True:
        chunk = resp.read(1024 * 256)
        if not chunk:
            break
        read += len(chunk)
        if read > MAX_LEADERBOARD_BYTES:
            raise SourceError("Rangliste unerwartet gross (>400 MB) - abgebrochen.")
        buf.write(chunk)
        if total:
            say("Lade Rangliste ... %d %%  (%.1f MB)" % (read * 100 // total, read / 1048576.0))
        else:
            say("Lade Rangliste ... %.1f MB" % (read / 1048576.0,))

    say("Werte Rangliste aus ...")
    text = _decode_body(resp, buf.getvalue())
    try:
        traders = parse_leaderboard(json.loads(text))
    except ValueError:
        raise SourceError("Rangliste war kein gueltiges JSON.")

    top = traders[:limit]
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(top, fh)
    except Exception:
        pass  # Cache ist Komfort, kein Muss

    say("%d Trader geladen." % len(top))
    return top, 0


# --------------------------------------------------------------------------
# 2) Live-Daten eines einzelnen Traders
# --------------------------------------------------------------------------

def fetch_mids():
    """Aktuelle Marktpreise: {"ETH": 3012.4, ...}"""
    data = post_info({"type": "allMids"})
    if not isinstance(data, dict):
        return {}
    out = {}
    for coin, px in data.items():
        val = _num(px, None)
        if val is not None:
            out[coin] = val
    return out


def _parse_clearinghouse(data):
    """Rohantwort -> {"accountValue","totalNotional","withdrawable","positions"}."""
    if not isinstance(data, dict):
        raise SourceError("Unerwartete Antwort fuer Positionen.")

    summary = data.get("marginSummary") or {}
    account_value = _num(summary.get("accountValue"))
    total_notional = _num(summary.get("totalNtlPos"))

    positions = []
    for item in data.get("assetPositions") or []:
        pos = item.get("position") if isinstance(item, dict) else None
        if not isinstance(pos, dict):
            continue
        size = _num(pos.get("szi"))
        if size == 0:
            continue
        lev = pos.get("leverage") or {}
        positions.append({
            "coin": pos.get("coin", "?"),
            "size": size,
            "side": "LONG" if size > 0 else "SHORT",
            "entryPx": _num(pos.get("entryPx")),
            "notional": abs(_num(pos.get("positionValue"))),
            "uPnl": _num(pos.get("unrealizedPnl")),
            "roe": _num(pos.get("returnOnEquity")) * 100.0,
            "leverage": _num(lev.get("value"), 1.0) if isinstance(lev, dict) else 1.0,
            "levType": (lev.get("type") if isinstance(lev, dict) else "") or "",
            "liqPx": _num(pos.get("liquidationPx")),
        })

    positions.sort(key=lambda p: p["notional"], reverse=True)
    return {
        "accountValue": account_value,
        "totalNotional": total_notional or sum(p["notional"] for p in positions),
        "withdrawable": _num(data.get("withdrawable")),
        "positions": positions,
    }


def fetch_positions(address):
    """Aktuell offene Perp-Positionen des Traders (live)."""
    return _parse_clearinghouse(post_info({"type": "clearinghouseState", "user": address}))


def _parse_fills(data, limit=60):
    """Rohantwort -> Liste der zuletzt ausgefuehrten Trades, neueste zuerst."""
    if not isinstance(data, list):
        return []
    fills = []
    for f in data[:limit]:
        if not isinstance(f, dict):
            continue
        fills.append({
            "time": int(f.get("time") or 0),
            "coin": f.get("coin", "?"),
            "side": "KAUF" if f.get("side") == "B" else "VERKAUF",
            "dir": f.get("dir", ""),
            "px": _num(f.get("px")),
            "sz": _num(f.get("sz")),
            "closedPnl": _num(f.get("closedPnl")),
            "hash": f.get("hash", ""),
        })
    fills.sort(key=lambda f: f["time"], reverse=True)
    return fills


def fetch_fills(address, limit=60):
    """Die zuletzt ausgefuehrten Trades des Traders (live)."""
    return _parse_fills(post_info({"type": "userFills", "user": address}), limit)
