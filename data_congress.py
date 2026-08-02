"""Pull congressional (STOCK Act) trading disclosures.

Primary free sources: Senate Stock Watcher + House Stock Watcher public JSON
dumps (mirrors of official House Clerk / Senate eFD disclosures).
Optional: Quiver Quantitative API if config.QUIVER_API_KEY is set.

Normalized transaction dict:
    {ticker, politician, chamber, date, type: "P"|"S", value_usd (range midpoint)}

Reality check baked in: disclosures lag trades by up to 45 days, and amounts
are reported as ranges — we use the midpoint, which is an estimate.
"""
from __future__ import annotations
import json
import re
import datetime as dt
from urllib.request import Request, urlopen

from . import config

# STOCK Act amount ranges -> midpoints
RANGE_MIDPOINTS = {
    "$1,001 - $15,000": 8_000, "$15,001 - $50,000": 32_500,
    "$50,001 - $100,000": 75_000, "$100,001 - $250,000": 175_000,
    "$250,001 - $500,000": 375_000, "$500,001 - $1,000,000": 750_000,
    "$1,000,001 - $5,000,000": 3_000_000, "$5,000,001 - $25,000,000": 15_000_000,
    "$25,000,001 - $50,000,000": 37_500_000, "$50,000,000 +": 50_000_000,
}


def _midpoint(amount_str: str) -> float:
    amount_str = (amount_str or "").strip()
    if amount_str in RANGE_MIDPOINTS:
        return RANGE_MIDPOINTS[amount_str]
    nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+", amount_str)]
    if len(nums) >= 2:
        return (nums[0] + nums[1]) / 2
    return nums[0] if nums else 0.0


def _fetch_json(url: str) -> list:
    req = Request(url, headers={"User-Agent": "InsiderEdge/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


POLITICIAN_STATS: dict[str, dict] = {}


def _normalize(rows: list, chamber: str, cutoff: dt.date,
               stats: dict | None = None) -> list[dict]:
    out = []
    for row in rows:
        ticker = (row.get("ticker") or "").upper().strip()
        if not ticker or ticker in ("--", "N/A") or len(ticker) > 6:
            continue
        ttype = (row.get("type") or row.get("transaction_type") or "").lower()
        if "purchase" in ttype:
            side = "P"
        elif "sale" in ttype:
            side = "S"
        else:
            continue  # exchanges/other
        date_str = row.get("transaction_date") or ""
        try:
            tdate = dt.datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        except ValueError:
            try:
                tdate = dt.datetime.strptime(date_str, "%m/%d/%Y").date()
            except ValueError:
                continue
        value = _midpoint(row.get("amount", ""))
        if value < config.MIN_CONGRESS_TRADE_USD:
            continue
        who = (row.get("senator") or row.get("representative") or "Unknown").strip()
        if stats is not None:
            rec = stats.setdefault(who, {"total": 0, "buys": 0, "sells": 0,
                                         "by_ticker": {}})
            rec["total"] += 1
            rec["buys" if side == "P" else "sells"] += 1
            bt = rec["by_ticker"].setdefault(ticker, {"P": 0, "S": 0})
            bt[side] += 1
        if tdate < cutoff:
            continue
        out.append({
            "ticker": ticker, "politician": who.strip(), "chamber": chamber,
            "date": tdate.isoformat(), "type": side, "value_usd": value,
        })
    return out


def fetch_congress_transactions(lookback_days: int | None = None) -> list[dict]:
    lookback = lookback_days or config.CONGRESS_LOOKBACK_DAYS
    cutoff = dt.date.today() - dt.timedelta(days=lookback)
    txns: list[dict] = []
    POLITICIAN_STATS.clear()
    for url, chamber in ((config.SENATE_WATCHER_URL, "Senate"),
                         (config.HOUSE_WATCHER_URL, "House")):
        try:
            txns.extend(_normalize(_fetch_json(url), chamber, cutoff,
                                   stats=POLITICIAN_STATS))
        except Exception as e:
            print(f"[warn] {chamber} feed unavailable: {e}")
    return txns


def stats_note(politician: str, ticker: str) -> str:
    rec = POLITICIAN_STATS.get(politician)
    if not rec:
        return ""
    bt = rec["by_ticker"].get(ticker, {"P": 0, "S": 0})
    parts = [f"{rec['total']} disclosed trades on record "
             f"({rec['buys']} buys / {rec['sells']} sells)"]
    if bt["P"] + bt["S"] > 1:
        parts.append(f"{bt['P'] + bt['S']}x in {ticker}")
    return "; ".join(parts)


def load_sample(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def seed_stats_from_txns(txns: list[dict]) -> None:
    """Demo/local helper: build stats from already-normalized transactions."""
    POLITICIAN_STATS.clear()
    for t in txns:
        rec = POLITICIAN_STATS.setdefault(t["politician"],
            {"total": 0, "buys": 0, "sells": 0, "by_ticker": {}})
        rec["total"] += 1
        rec["buys" if t["type"] == "P" else "sells"] += 1
        bt = rec["by_ticker"].setdefault(t["ticker"], {"P": 0, "S": 0})
        bt[t["type"]] += 1
