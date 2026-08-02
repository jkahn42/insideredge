"""Scoring engine: turn raw transactions into BUY / SELL / WATCHLIST calls.

Design (moderate risk):
- Log-scale dollar values (a $5M buy is not 200x more informative than $25k).
- Role-weight insiders (CEO buy > director buy).
- Recency decay with 21-day half-life.
- Cluster bonuses: multiple independent actors agreeing is the strongest
  documented predictor in the insider-trading literature.
- BUY requires score >= 60 AND >= 2 distinct buyers (no lone-wolf chasing).
- Buy-side and sell-side are scored independently per ticker; a ticker with
  heavy two-way traffic nets out and lands on the watchlist, not a call.
"""
from __future__ import annotations
import math
import datetime as dt
from collections import defaultdict

from . import config


def _decay(date_str: str, today: dt.date) -> float:
    try:
        d = dt.datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0.5
    age = max((today - d).days, 0)
    return 0.5 ** (age / config.RECENCY_HALF_LIFE_DAYS)


def _log_dollar(v: float) -> float:
    return math.log10(max(v, 1.0))


def score_universe(insider_txns: list[dict], congress_txns: list[dict],
                   today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    # raw[ticker][side] -> accumulated weight; actors[ticker][side] -> set of names
    raw = defaultdict(lambda: {"P": 0.0, "S": 0.0})
    craw = defaultdict(lambda: {"P": 0.0, "S": 0.0})
    actors = defaultdict(lambda: {"P": set(), "S": set()})
    cactors = defaultdict(lambda: {"P": set(), "S": set()})
    iinfo = defaultdict(dict)
    cnames = defaultdict(set)
    exec_sellers = defaultdict(set)
    evidence = defaultdict(list)

    for t in insider_txns:
        w = (config.ROLE_WEIGHTS.get(t["role"], 0.7)
             * _log_dollar(t["value_usd"]) * _decay(t["date"], today))
        if t.get("planned"):
            w *= config.PLANNED_SALE_DISCOUNT
        elif t["type"] == "S" and t["role"] in config.EXEC_ROLES:
            exec_sellers[t["ticker"]].add(t["insider_name"])
        raw[t["ticker"]][t["type"]] += w
        actors[t["ticker"]][t["type"]].add(t["insider_name"])
        iinfo[t["ticker"]][t["insider_name"]] = {
            "role": t["role"], "cik": t.get("owner_cik", "")}
        evidence[t["ticker"]].append(
            f"{t['date']} {t['role']} {t['insider_name']} "
            f"{'BUY' if t['type'] == 'P' else 'SELL'} ${t['value_usd']:,.0f}"
            + (" (10b5-1 planned sale — discounted)" if t.get("planned") else ""))

    for t in congress_txns:
        w = _log_dollar(t["value_usd"]) * _decay(t["date"], today)
        craw[t["ticker"]][t["type"]] += w
        cactors[t["ticker"]][t["type"]].add(t["politician"])
        cnames[t["ticker"]].add(t["politician"])
        evidence[t["ticker"]].append(
            f"{t['date']} {t['chamber']} {t['politician']} "
            f"{'BUY' if t['type'] == 'P' else 'SELL'} ~${t['value_usd']:,.0f}")

    # cluster bonuses
    for tk in raw:
        for side in ("P", "S"):
            if len(actors[tk][side]) >= 3:
                raw[tk][side] *= config.CLUSTER_BONUS
    for tk in craw:
        for side in ("P", "S"):
            if len(cactors[tk][side]) >= 2:
                craw[tk][side] *= config.CONGRESS_CLUSTER_BONUS

    # normalize buy-side and sell-side INDEPENDENTLY (a huge sell cluster
    # elsewhere must not drown out a legitimate buy signal), then blend
    tickers = set(raw) | set(craw)
    max_ib = max((v["P"] for v in raw.values()), default=1) or 1
    max_is = max((v["S"] for v in raw.values()), default=1) or 1
    max_cb = max((v["P"] for v in craw.values()), default=1) or 1
    max_cs = max((v["S"] for v in craw.values()), default=1) or 1
    activists = {t["ticker"] for t in insider_txns
                 if t.get("role") == "ACTIVIST" and t["type"] == "P"}

    results = []
    for tk in tickers:
        buy = (config.WEIGHT_INSIDER * 100 * raw[tk]["P"] / max_ib
               + config.WEIGHT_CONGRESS * 100 * craw[tk]["P"] / max_cb)
        sell = (config.WEIGHT_INSIDER * 100 * raw[tk]["S"] / max_is
                + config.WEIGHT_CONGRESS * 100 * craw[tk]["S"] / max_cs)
        buyers = len(actors[tk]["P"]) + len(cactors[tk]["P"])
        sellers = len(actors[tk]["S"]) + len(cactors[tk]["S"])
        net = buy - sell

        if (buy >= config.BUY_SCORE_MIN and net > 15
                and buyers >= config.BUY_MIN_DISTINCT_BUYERS):
            call = "BUY"
        elif sell >= config.SELL_SCORE_MIN and net < -15 and sellers >= 2:
            call = "SELL"
        elif max(buy, sell) >= config.WATCH_SCORE_MIN:
            call = "WATCH"
        elif tk in activists:
            call = "WATCH"   # a fresh 13D always earns at least a watch slot
        else:
            continue
        short_flag = (call == "SELL"
                      and sell >= config.SHORT_SELL_SCORE_MIN
                      and sellers >= config.SHORT_MIN_SELLERS
                      and buyers == 0
                      and len(exec_sellers[tk]) >= config.SHORT_MIN_EXEC_SELLERS)
        results.append({
            "ticker": tk, "call": call, "short_candidate": short_flag,
            "buy_score": round(buy, 1),
            "sell_score": round(sell, 1), "net_score": round(net, 1),
            "distinct_buyers": buyers, "distinct_sellers": sellers,
            "evidence": sorted(evidence[tk], reverse=True)[:8],
            "actor_info": {"insiders": dict(iinfo[tk]),
                           "congress": sorted(cnames[tk])},
        })
    order = {"BUY": 0, "SELL": 1, "WATCH": 2}
    results.sort(key=lambda r: (order[r["call"]], -abs(r["net_score"])))
    return results
