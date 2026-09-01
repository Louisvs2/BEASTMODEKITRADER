"""
Data source: Hyperliquid (public, no account, no API key, no registration).

Exactly three public endpoints are used - the same ones the website
app.hyperliquid.xyz calls from the browser:

  1. https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
     -> the trader ranking, as publicly shown on app.hyperliquid.xyz/leaderboard
  2. POST https://api.hyperliquid.xyz/info  {"type": "clearinghouseState", "user": <address>}
     -> that trader's currently OPEN positions (live)
  3. POST https://api.hyperliquid.xyz/info  {"type": "userFills", "user": <address>}
     -> that trader's most recently EXECUTED trades (live)

Plus {"type": "allMids"} for current mark prices.

Everything goes through urllib from the standard library - nothing to install.
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

# The ranking is a large file. It is cached on disk and only refetched on
# demand, or once it is older than CACHE_MAX_AGE.
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".whaletracker")
CACHE_FILE = os.path.join(CACHE_DIR, "leaderboard.json")
CACHE_MAX_AGE = 60 * 60 * 6  # 6 hours
MAX_LEADERBOARD_BYTES = 400 * 1024 * 1024

WINDOWS = ("day", "week", "month", "allTime")
WINDOW_LABEL = {
    "day": "24H",
    "week": "7D",
    "month": "30D",
    "allTime": "ALL TIME",
}


class SourceError(Exception):
    """Something went wrong fetching data - shown to the user as plain text."""


class CertificateError(SourceError):
    """TLS worked but no trusted root certificates were available."""


def _ssl_context():
    """
    A verifying TLS context.

    Python installed from python.org does not register the system root
    certificates, so every HTTPS call fails with CERTIFICATE_VERIFY_FAILED
    until either Apple's "Install Certificates.command" has been run or the
    certifi bundle is present. Prefer certifi when it is importable; fall
    back to the default store otherwise. Verification is never disabled.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        return None


CERT_HELP = (
    "No trusted certificates - macOS Python cannot verify HTTPS.\n"
    "Fix: double-click fix_certificates.command in the app folder."
)


def _is_cert_failure(exc):
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def _open(req, timeout=TIMEOUT):
    ctx = _ssl_context()
    try:
        if ctx is not None:
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise SourceError("Server replied HTTP %s (%s)" % (exc.code, exc.reason))
    except urllib.error.URLError as exc:
        if _is_cert_failure(exc.reason) or _is_cert_failure(exc):
            raise CertificateError(CERT_HELP)
        raise SourceError("No connection: %s" % (exc.reason,))
    except Exception as exc:  # socket timeouts, ssl, ...
        if _is_cert_failure(exc):
            raise CertificateError(CERT_HELP)
        raise SourceError("Connection failed: %s" % (exc,))


def _decode_body(resp, raw):
    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def post_info(payload):
    """One POST to the public /info endpoint."""
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
        raise SourceError("Response was not valid JSON (%s ...)" % text[:120])


# --------------------------------------------------------------------------
# 1) Trader ranking
# --------------------------------------------------------------------------

def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_leaderboard(data):
    """Raw response -> list of plain trader dicts, sorted by 30-day PnL."""
    rows = data.get("leaderboardRows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise SourceError("Unexpected leaderboard format.")

    traders = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        addr = row.get("ethAddress") or row.get("user") or ""
        if not addr:
            continue
        perf = {}
        for entry in row.get("windowPerformances") or []:
            # shape: ["day", {"pnl": "...", "roi": "...", "vlm": "..."}]
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
        raise SourceError("Leaderboard contained no traders.")
    traders.sort(key=lambda t: t["perf"]["month"]["pnl"], reverse=True)
    return traders


def cached_leaderboard_age():
    """Cache age in seconds, or None when there is no cache."""
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
    Fetch the ranking, reusing the local cache while it is fresh enough.
    `progress(text)` receives status lines during the download.
    """
    def say(text):
        if progress:
            progress(text)

    age = cached_leaderboard_age()
    if not force and age is not None and age < CACHE_MAX_AGE:
        cached = load_cached_leaderboard()
        if cached:
            say("Leaderboard from local cache (%d min old)." % int(age // 60))
            return cached[:limit], int(age)

    say("Fetching public leaderboard from stats-data.hyperliquid.xyz ...")
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
            raise SourceError("Leaderboard unexpectedly large (>400 MB) - aborted.")
        buf.write(chunk)
        if total:
            say("Downloading leaderboard ... %d%%  (%.1f MB)" % (read * 100 // total, read / 1048576.0))
        else:
            say("Downloading leaderboard ... %.1f MB" % (read / 1048576.0,))

    say("Parsing leaderboard ...")
    text = _decode_body(resp, buf.getvalue())
    try:
        traders = parse_leaderboard(json.loads(text))
    except ValueError:
        raise SourceError("Leaderboard was not valid JSON.")

    top = traders[:limit]
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(top, fh)
    except Exception:
        pass  # the cache is a convenience, not a requirement

    say("%d traders loaded." % len(top))
    return top, 0


# --------------------------------------------------------------------------
# 2) Live data for a single trader
# --------------------------------------------------------------------------

def fetch_mids():
    """Current mark prices: {"ETH": 3012.4, ...}"""
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
    """Raw response -> {"accountValue","totalNotional","withdrawable","positions"}."""
    if not isinstance(data, dict):
        raise SourceError("Unexpected response for positions.")

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
    """The trader's currently open perp positions (live)."""
    return _parse_clearinghouse(post_info({"type": "clearinghouseState", "user": address}))


def _parse_fills(data, limit=60):
    """Raw response -> most recent executed trades, newest first."""
    if not isinstance(data, list):
        return []
    fills = []
    for f in data[:limit]:
        if not isinstance(f, dict):
            continue
        fills.append({
            "time": int(f.get("time") or 0),
            "coin": f.get("coin", "?"),
            "side": "BUY" if f.get("side") == "B" else "SELL",
            "dir": f.get("dir", ""),
            "px": _num(f.get("px")),
            "sz": _num(f.get("sz")),
            "closedPnl": _num(f.get("closedPnl")),
            "hash": f.get("hash", ""),
        })
    fills.sort(key=lambda f: f["time"], reverse=True)
    return fills


def fetch_fills(address, limit=60):
    """The trader's most recently executed trades (live)."""
    return _parse_fills(post_info({"type": "userFills", "user": address}), limit)
