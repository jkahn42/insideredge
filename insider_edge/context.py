"""Build 'Who's trading' context: history notes per actor on each signal.

Insiders: official SEC filing history (live) + this bot's cumulative ledger.
Politicians: full track record computed from the complete disclosure dataset.
All lookups are best-effort; a missing note never blocks the report.
"""
from __future__ import annotations

from . import data_sec, data_congress


def _insider_note(name: str, ticker: str, info: dict, ledger: dict,
                  live: bool, sample_profiles: dict | None) -> str:
    parts = []
    if sample_profiles and name in sample_profiles:
        parts.append(sample_profiles[name])
    elif live and info.get("cik"):
        prof = data_sec.insider_profile(info["cik"])
        if prof:
            parts.append(prof)
    n_buys = ledger.get(f"{name}|{ticker}|P", 0)
    n_sells = ledger.get(f"{name}|{ticker}|S", 0)
    if n_buys or n_sells:
        seg = []
        if n_buys:
            seg.append(f"{n_buys} buy{'s' if n_buys > 1 else ''}")
        if n_sells:
            seg.append(f"{n_sells} sale{'s' if n_sells > 1 else ''}")
        parts.append(f"{' / '.join(seg)} of {ticker} in this tracker's ledger")
    return "; ".join(parts)


def build_actor_notes(signals: list[dict], ledger: dict, live: bool,
                      sample_profiles: dict | None = None) -> None:
    for s in signals:
        actors = []
        info = s.pop("actor_info", {"insiders": {}, "congress": []})
        for name, meta in info["insiders"].items():
            note = _insider_note(name, s["ticker"], meta, ledger,
                                 live, sample_profiles)
            actors.append({"name": name, "kind": meta.get("role", ""),
                           "note": note or "No prior history on record"})
        for name in sorted(info["congress"]):
            note = data_congress.stats_note(name, s["ticker"])
            actors.append({"name": name, "kind": "Congress",
                           "note": note or "No prior history on record"})
        s["actors"] = actors
