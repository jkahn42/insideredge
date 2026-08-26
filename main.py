#!/usr/bin/env python3
"""InsiderEdge v2 — insider + congressional trading signal bot.

  python main.py report            # live data -> report + portal + Telegram
  python main.py report --demo     # sample data, no network
  python main.py trade             # dry-run order plan
  python main.py trade --send                              # Alpaca PAPER
  python main.py trade --live --i-understand-live --send   # real money
"""
from __future__ import annotations
import argparse
import re
import datetime as dt
import json
import sys

from insider_edge import (data_sec, data_congress, scoring, report,
                          enrich, legislation, html_report, notify, trader,
                          tracking, context, scorecard, publish,
                          news, trends)

REPORT_MD, REPORT_JSON = "daily_report.md", "daily_report.json"
PORTAL_HTML = "docs/index.html"


def cmd_report(demo: bool) -> None:
    if demo:
        ins = data_sec.load_sample("sample_data/form4_sample.json")
        con = data_congress.load_sample("sample_data/congress_sample.json")
        sp = json.load(open("sample_data/prices_sample.json"))
        sc = json.load(open("sample_data/companies_sample.json"))
        sl = json.load(open("sample_data/legislation_sample.json"))
        sd = json.load(open("sample_data/deep_sample.json"))
        spf = json.load(open("sample_data/profiles_sample.json"))
        sn = json.load(open("sample_data/news_sample.json"))
        ins += data_sec.load_sample("sample_data/13d_sample.json")
        data_congress.seed_stats_from_txns(con)
        print(f"[demo] {len(ins)} insider+13D txns, {len(con)} congress txns")
    else:
        print("Fetching SEC Form 4 filings...")
        ins = data_sec.fetch_form4_transactions()
        print(f"  {len(ins)} insider transactions")
        print("Fetching congressional disclosures...")
        con = data_congress.fetch_congress_transactions()
        print(f"  {len(con)} congressional transactions")
        print("Fetching SC 13D activist filings...")
        ins += data_sec.fetch_13d_signals()
        sp = sc = sl = sd = spf = sn = None

    today = dt.date.today()
    state = tracking.load_state()
    lookup = lambda tk: enrich.spot_price(tk, sample_prices=sp)
    state = tracking.ingest_decisions(state, lookup, today)
    state = tracking.expire(state, today)

    # heal tracked entries whose decision price failed to record
    for _tk, _rec in state["tracked"].items():
        if _rec.get("start_price") is None:
            _h = ((sp or {}).get(_tk) if sp is not None
                  else enrich.price_history(_tk, days=45))
            _h = _h or {"dates": [], "closes": []}
            for _d2, _c2 in zip(_h.get("dates", []), _h.get("closes", [])):
                if _d2 >= _rec["start_date"]:
                    _rec["start_price"] = _c2
                    print(f"[tracking] backfilled {_tk} decision price {_c2}")
                    break

    _icache = {}
    def _industry(tk):
        if tk not in _icache:
            if sc is not None:
                _icache[tk] = (sc.get(tk) or {}).get("industry", "")
            else:
                _icache[tk] = enrich.company_info(tk).get("industry", "")
        return _icache[tk]
    momentum = trends.sector_momentum(ins, _industry)
    herd_set, _budget = set(), 10
    for _row in momentum:
        for _tk in _row["tickers"]:
            if _budget > 0:
                herd_set.add(_tk)
                _budget -= 1

    signals = scoring.score_universe(ins, con, force_watch=herd_set)
    signals = tracking.suppress_rejected(signals, state)
    print(f"Scoring done: {len(signals)} signals. Enriching...")
    enrich.enrich_signals(signals, sample_prices=sp, sample_companies=sc)
    enrich.deep_enrich(signals, sample_deep=sd)
    ledger = data_sec.update_history(ins)
    context.build_actor_notes(signals, ledger, live=not demo,
                              sample_profiles=spf)
    news.annotate(signals, sample=sn)
    trends.annotate_themes(signals)

    # timing/freshness: insider-following edge decays within weeks
    for s in signals:
        dates = [e[:10] for e in s.get("evidence", [])
                 if re.match(r"\d{4}-\d{2}-\d{2}", e)]
        age = (today - dt.date.fromisoformat(max(dates))).days if dates else 99
        drift = s.get("pct_since_signal")
        if drift is not None and drift >= 10:
            s["timing"] = {"label": f"Edge partly spent \u2014 already "
                           f"{drift:+.0f}% since disclosure", "cls": "spent"}
        elif age <= 3:
            s["timing"] = {"label": f"Fresh \u2014 latest filing "
                           f"{age} day(s) ago", "cls": "fresh"}
        elif age <= 8:
            s["timing"] = {"label": f"Recent \u2014 latest filing "
                           f"{age} days ago", "cls": "mid"}
        else:
            s["timing"] = {"label": f"Aging \u2014 latest filing "
                           f"{age} days ago; edge decays over weeks",
                           "cls": "spent"}

    # earnings-soon heuristic: >=80 days since last quarterly filing
    for s in signals:
        qdates = [f["date"] for f in (s.get("deep") or {}).get("recent_filings", [])
                  if f["form"] in ("10-Q", "10-K")]
        s["earnings_soon"] = bool(qdates) and \
            (today - dt.date.fromisoformat(max(qdates))).days >= 80

    # sector concentration banner
    banner = None
    buys = [s for s in signals if s["call"] == "BUY"]
    if len(buys) >= 2:
        from collections import Counter
        secs = Counter((s.get("company") or {}).get("industry") or "Unknown"
                       for s in buys)
        top, n = secs.most_common(1)[0]
        if n / len(buys) >= 0.5 and n >= 2:
            banner = (f"Concentration: {n} of {len(buys)} buy signals are "
                      f"{top} \u2014 treat them as one thematic bet, not {n} "
                      f"independent ideas.")

    # scorecard: record today's buys, evaluate everything vs SPY
    spy_now = enrich.spot_price("SPY", sample_prices=sp)
    sc_state = scorecard.load()
    sc_state = scorecard.record_new_buys(sc_state, signals, spy_now, today)
    sc = scorecard.evaluate(sc_state, lookup, spy_now, today)
    scorecard.save(sc_state)
    for s in signals:
        s["legislation"] = legislation.legislative_context(s, sample=sl)

    tracked = tracking.tracked_cards(state, lookup, today)
    for t in tracked:
        _h = ((sp or {}).get(t["ticker"]) if sp is not None
              else enrich.price_history(t["ticker"], days=45))
        _h = _h or {"dates": [], "closes": []}
        _ds, _cs = _h.get("dates", []), _h.get("closes", [])
        _i = next((i for i, dd in enumerate(_ds)
                   if dd >= t["start_date"]), None)
        if _i is not None and _i < len(_cs) and _cs[_i]:
            _base = _cs[_i]
            t["series"] = [round(100 * (c / _base - 1), 2)
                           for c in _cs[_i:]]
        else:
            t["series"] = []

    _active = {s["ticker"]: s for s in signals
               if s["ticker"] in state["tracked"]}
    signals = [s for s in signals if s["ticker"] not in state["tracked"]]
    for t in tracked:
        _m2 = _active.get(t["ticker"])
        if _m2:
            t["activity"] = (f"{_m2['call']} signal again today "
                             f"(net {_m2['net_score']:+.1f}, "
                             f"{_m2['distinct_buyers']}B/"
                             f"{_m2['distinct_sellers']}S)")
            if _m2.get("news_flags"):
                t["news_flags"] = _m2["news_flags"]

    _adj = [t["pct"] if t["action"] == "BUY" else -t["pct"]
            for t in tracked if t.get("pct") is not None]
    portfolio = round(sum(_adj) / len(_adj), 2) if _adj else None
    for t in tracked:
        match = next((s for s in signals if s["ticker"] == t["ticker"]), None)
        if match:
            t["news_flags"] = match.get("news_flags", [])
        elif sn is not None:
            t["news_flags"] = news.risk_flags(sn.get(t["ticker"], []))
        else:
            t["news_flags"] = news.risk_flags(news.fetch_news(t["ticker"]))
    tracking.save_state(state)
    report.build_report(signals, REPORT_MD, REPORT_JSON)
    html_report.build_portal(signals, PORTAL_HTML,
                             tracked=tracked, rejected=state["rejected"],
                             sc=sc, banner=banner, momentum=momentum,
                             portfolio=portfolio)
    _archive_snapshot(today)
    print(f"Saved: {REPORT_MD}, {REPORT_JSON}, {PORTAL_HTML}")
    notify.send_daily_ping(signals, today.isoformat(), tracked=tracked,
                           portfolio=portfolio)


def _archive_snapshot(today: dt.date) -> None:
    """Copy today's portal into docs/archive/ and rebuild the archive index."""
    import os, shutil
    os.makedirs("docs/archive", exist_ok=True)
    shutil.copy(PORTAL_HTML, f"docs/archive/{today.isoformat()}.html")
    days = sorted((f[:-5] for f in os.listdir("docs/archive")
                   if f.endswith(".html") and f != "index.html"), reverse=True)
    links = "".join(f'<li><a href="{d}.html">{d}</a></li>' for d in days)
    with open("docs/archive/index.html", "w") as f:
        f.write("<!doctype html><html><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>InsiderEdge Archive</title><style>body{background:#F4F6FA;"
                "color:#1A2433;font:16px/1.8 Inter,system-ui,sans-serif;padding:2rem}"
                "a{color:#5457C9;font-weight:600;text-decoration:none}"
                "h1 b{color:#5457C9}li{margin:.3rem 0}</style></head><body>"
                "<h1>Insider<b>Edge</b> archive</h1>"
                "<p><a href='../index.html'>\u2190 Today</a></p>"
                f"<ul>{links}</ul></body></html>")


def cmd_trade(args) -> None:
    if args.live and not args.i_understand_live:
        sys.exit("Refusing LIVE mode without --i-understand-live flag.")
    trader.execute(REPORT_JSON, dry_run=not args.send, paper=not args.live)


def main() -> None:
    p = argparse.ArgumentParser(prog="InsiderEdge")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--demo", action="store_true")
    t = sub.add_parser("trade")
    t.add_argument("--send", action="store_true")
    t.add_argument("--live", action="store_true")
    t.add_argument("--i-understand-live", action="store_true")
    pub = sub.add_parser("publish")
    pub.add_argument("--demo", action="store_true",
                     help="write newsletter_preview.html instead of posting")
    pub.add_argument("--send", action="store_true",
                     help="publish + email members (default: Ghost draft)")
    a = p.parse_args()
    if a.cmd == "report":
        cmd_report(a.demo)
    elif a.cmd == "trade":
        cmd_trade(a)
    else:
        with open(REPORT_JSON) as f:
            signals = json.load(f)["signals"]
        sc_state = scorecard.load()
        sp = (json.load(open("sample_data/prices_sample.json"))
              if a.demo else None)
        lookup = lambda tk: enrich.spot_price(tk, sample_prices=sp)
        sc = scorecard.evaluate(sc_state, lookup, lookup("SPY"),
                                dt.date.today())
        publish.publish(signals, sc,
                        send=a.send,
                        preview_path="newsletter_preview.html"
                        if a.demo else None)


if __name__ == "__main__":
    main()
