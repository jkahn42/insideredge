"""Track / Reject workflow.

Portal buttons open pre-filled GitHub issues titled:
    TRACK BUY NVAX   |   TRACK SELL XOM   |   REJECT TSLA
Each daily run: reads open issues, applies decisions, closes the issues,
expires tracked names after TRACK_DAYS, and suppresses rejected tickers
from all future reports. State persists in tracking_state.json (committed
by the workflow, so it survives between cloud runs).
"""
from __future__ import annotations
import json
import os
import re
import datetime as dt
from urllib.request import Request, urlopen

from . import config

STATE_FILE = "tracking_state.json"
TITLE_RE = re.compile(r"^(TRACK BUY|TRACK SELL|REJECT)\s+([A-Z][A-Z.\-]{0,5})$")


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("tracked", {})
    s.setdefault("rejected", [])
    return s


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _gh(path: str, method: str = "GET", body: dict | None = None):
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return None
    req = Request(f"https://api.github.com/repos/{repo}{path}", method=method,
                  headers={"Authorization": f"Bearer {token}",
                           "Accept": "application/vnd.github+json",
                           "User-Agent": "InsiderEdge/3.0"},
                  data=json.dumps(body).encode() if body else None)
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def ingest_decisions(state: dict, price_lookup, today: dt.date) -> dict:
    """Read open issues -> apply TRACK/REJECT -> close them. Fail-safe."""
    try:
        issues = _gh("/issues?state=open&per_page=50") or []
    except Exception as e:
        print(f"[tracking] issue ingest skipped: {e}")
        return state
    for iss in issues:
        m = TITLE_RE.match((iss.get("title") or "").strip().upper())
        if not m:
            continue
        verb, tk = m.groups()
        if verb == "REJECT":
            if tk not in state["rejected"]:
                state["rejected"].append(tk)
            state["tracked"].pop(tk, None)
            print(f"[tracking] rejected {tk}")
        else:
            px = price_lookup(tk)
            state["tracked"][tk] = {
                "action": "BUY" if verb == "TRACK BUY" else "SELL",
                "start_date": today.isoformat(),
                "start_price": px,
            }
            print(f"[tracking] now tracking {tk} ({verb}) @ {px}")
        try:
            _gh(f"/issues/{iss['number']}", "PATCH", {"state": "closed"})
        except Exception:
            pass
    return state


def expire(state: dict, today: dt.date) -> dict:
    keep = {}
    for tk, rec in state["tracked"].items():
        try:
            start = dt.date.fromisoformat(rec["start_date"])
        except Exception:
            continue
        if (today - start).days <= config.TRACK_DAYS:
            keep[tk] = rec
        else:
            print(f"[tracking] {tk} expired after {config.TRACK_DAYS} days")
    state["tracked"] = keep
    return state


def suppress_rejected(signals: list[dict], state: dict) -> list[dict]:
    rej = set(state["rejected"])
    return [s for s in signals if s["ticker"] not in rej]


def tracked_cards(state: dict, price_lookup, today: dt.date) -> list[dict]:
    """Build display records for the portal's Tracking section."""
    out = []
    for tk, rec in sorted(state["tracked"].items()):
        now = price_lookup(tk)
        start_px = rec.get("start_price")
        pct = (round(100 * (now / start_px - 1), 2)
               if now and start_px else None)
        day = (today - dt.date.fromisoformat(rec["start_date"])).days + 1
        out.append({"ticker": tk, "action": rec["action"], "day": day,
                    "days_total": config.TRACK_DAYS,
                    "start_date": rec["start_date"],
                    "start_price": start_px, "price_now": now, "pct": pct})
    return out
