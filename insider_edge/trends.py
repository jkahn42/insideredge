"""Macro themes & sector momentum (v16).

Two complementary lenses:
1. THEMES — curated watchlists for live macro/social trends. A signal on a
   member company gets a theme badge: the macro story behind the trade.
   Edit freely; membership is context, never an automatic recommendation.
2. sector_momentum — bottom-up trend detection: aggregate unplanned insider
   cluster-buying by industry. When executives across one industry all buy
   at once, that IS the economic trend, reported by the people who know
   first. No opinions, just filings.

Discipline note: themes are context, insiders are confirmation. A hot theme
with no insider buying is a story; a quiet industry full of insider buying
is a signal.
"""
from __future__ import annotations
import math
from collections import defaultdict

THEMES = {
    "Rare earths & magnets": ["MP", "UUUU", "NB", "USAR", "TMC"],
    "Robotics & automation": ["ROK", "TER", "CGNX", "SYM", "RRX", "ISRG",
                              "NVDA"],
    "AI datacenter buildout": ["NVDA", "AVGO", "VRT", "ETN", "SMCI", "MU",
                               "ANET", "PWR", "TSM", "MSFT"],
    "Defense modernization": ["LMT", "RTX", "NOC", "GD", "KTOS", "AVAV",
                              "LHX"],
    "Nuclear renaissance": ["CCJ", "CEG", "UEC", "SMR", "BWXT", "VST",
                            "LEU", "OKLO"],
}


def themes_for(ticker: str) -> list[str]:
    return [name for name, tks in THEMES.items() if ticker in tks]


def annotate_themes(signals: list[dict]) -> None:
    for s in signals:
        s["themes"] = themes_for(s["ticker"])


def sector_momentum(insider_txns: list[dict], industry_lookup,
                    min_buyers: int = 2, top: int = 5) -> list[dict]:
    """Top industries by unplanned insider cluster-buying in the window."""
    buyers: dict[str, set] = defaultdict(set)
    weight: dict[str, float] = defaultdict(float)
    for t in insider_txns:
        if t.get("type") != "P" or t.get("planned"):
            continue
        buyers[t["ticker"]].add(t.get("insider_name", "?"))
        weight[t["ticker"]] += math.log10(max(t.get("value_usd", 1), 1))
    ind_w: dict[str, float] = defaultdict(float)
    ind_t: dict[str, set] = defaultdict(set)
    ind_b: dict[str, int] = defaultdict(int)
    for tk, names in buyers.items():
        if len(names) < min_buyers:
            continue
        try:
            ind = industry_lookup(tk) or "Unclassified"
        except Exception:
            ind = "Unclassified"
        ind_w[ind] += weight[tk]
        ind_t[ind].add(tk)
        ind_b[ind] += len(names)
    rows = [{"industry": i, "weight": round(w, 1),
             "tickers": sorted(ind_t[i])[:8], "buyers": ind_b[i]}
            for i, w in ind_w.items()]
    rows.sort(key=lambda r: -r["weight"])
    return rows[:top]
