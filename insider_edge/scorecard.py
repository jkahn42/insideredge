"""Signal scorecard: the honest mirror.

Every BUY signal ever issued is recorded automatically (ticker, date, price
at issue, SPY at issue) and re-evaluated daily against SPY over the same
window. The portal shows the running verdict: n signals, % that beat the
market, average excess return. State persists in scorecard_state.json.
"""
from __future__ import annotations
import json
import datetime as dt

STATE_FILE = "scorecard_state.json"


def load() -> dict:
    try:
        with open(STATE_FILE) as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("entries", [])
    return s


def save(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def record_new_buys(state: dict, signals: list[dict], spy_now,
                    today: dt.date) -> dict:
    seen = {(e["ticker"], e["issued"]) for e in state["entries"]}
    open_tickers = {e["ticker"] for e in state["entries"]
                    if not e.get("closed")}
    for s in signals:
        if s["call"] != "BUY" or s["ticker"] in open_tickers:
            continue
        if (s["ticker"], today.isoformat()) in seen or not s.get("price_now"):
            continue
        state["entries"].append({
            "ticker": s["ticker"], "issued": today.isoformat(),
            "px_issue": s["price_now"], "spy_issue": spy_now,
        })
        open_tickers.add(s["ticker"])
    return state


def evaluate(state: dict, price_lookup, spy_now, today: dt.date) -> dict:
    """Returns {summary, rows}. Mutates nothing destructive; fail-soft."""
    rows = []
    for e in state["entries"]:
        px_now = price_lookup(e["ticker"])
        age = (today - dt.date.fromisoformat(e["issued"])).days
        ret = spy_ret = excess = None
        if px_now and e.get("px_issue"):
            ret = round(100 * (px_now / e["px_issue"] - 1), 2)
        if spy_now and e.get("spy_issue"):
            spy_ret = round(100 * (spy_now / e["spy_issue"] - 1), 2)
        if ret is not None and spy_ret is not None:
            excess = round(ret - spy_ret, 2)
        rows.append({"ticker": e["ticker"], "issued": e["issued"],
                     "age": age, "ret": ret, "spy_ret": spy_ret,
                     "excess": excess})
    scored = [r for r in rows if r["excess"] is not None and r["age"] >= 5]
    n = len(scored)
    beat = sum(1 for r in scored if r["excess"] > 0)
    avg = round(sum(r["excess"] for r in scored) / n, 2) if n else None
    summary = {"issued_total": len(rows), "scored": n,
               "beat_pct": round(100 * beat / n, 1) if n else None,
               "avg_excess": avg}
    rows.sort(key=lambda r: r["issued"], reverse=True)
    return {"summary": summary, "rows": rows[:40]}
