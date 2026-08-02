"""Enrich signals with company identity, prices, and 14-day trend.

Sources (all free, no keys):
- SEC company_tickers.json  -> company name + CIK
- SEC submissions API       -> industry (SIC description)
- Stooq daily CSV           -> closing prices (current, at-signal, 14-day trend)
"""
from __future__ import annotations
import csv
import io
import json
import re
import datetime as dt
from urllib.request import Request, urlopen

from . import config

_TICKER_MAP: dict[str, dict] | None = None


def _get(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers={"User-Agent": config.SEC_USER_AGENT})
    with urlopen(req, timeout=timeout) as r:
        return r.read()


def _ticker_map() -> dict[str, dict]:
    global _TICKER_MAP
    if _TICKER_MAP is None:
        data = json.loads(_get("https://www.sec.gov/files/company_tickers.json"))
        _TICKER_MAP = {v["ticker"].upper(): {"cik": v["cik_str"], "name": v["title"]}
                       for v in data.values()}
    return _TICKER_MAP


def company_info(ticker: str) -> dict:
    info = {"name": ticker, "industry": ""}
    try:
        rec = _ticker_map().get(ticker)
        if rec:
            info["name"] = rec["name"]
            sub = json.loads(_get(
                f"https://data.sec.gov/submissions/CIK{rec['cik']:010d}.json"))
            info["industry"] = sub.get("sicDescription", "") or ""
    except Exception:
        pass
    return info


def price_history(ticker: str, days: int = 20) -> dict:
    """Return {dates: [...], closes: [...]} for the last `days` sessions."""
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    try:
        rows = list(csv.DictReader(io.StringIO(_get(url).decode())))[-days:]
        return {"dates": [r["Date"] for r in rows],
                "closes": [float(r["Close"]) for r in rows]}
    except Exception:
        return {"dates": [], "closes": []}


def _earliest_evidence_date(signal: dict) -> str:
    dates = [m.group(0) for ev in signal.get("evidence", [])
             if (m := re.match(r"\d{4}-\d{2}-\d{2}", ev))]
    return min(dates) if dates else ""


def enrich_signals(signals: list[dict],
                   sample_prices: dict | None = None,
                   sample_companies: dict | None = None) -> list[dict]:
    for s in signals:
        tk = s["ticker"]
        s["company"] = (sample_companies or {}).get(tk) or company_info(tk)
        hist = (sample_prices or {}).get(tk) or price_history(tk)
        closes, dates = hist.get("closes", []), hist.get("dates", [])
        s["trend"] = {"dates": dates[-14:], "closes": closes[-14:]}
        s["price_now"] = closes[-1] if closes else None
        # price on (or first session after) the earliest disclosed trade
        sig_date = _earliest_evidence_date(s)
        s["price_at_signal"] = None
        if sig_date and dates:
            for d, c in zip(dates, closes):
                if d >= sig_date:
                    s["price_at_signal"] = c
                    break
        if s["price_now"] and s["price_at_signal"]:
            s["pct_since_signal"] = round(
                100 * (s["price_now"] / s["price_at_signal"] - 1), 2)
        else:
            s["pct_since_signal"] = None
        if len(closes) >= 2 and closes[-14 if len(closes) >= 14 else 0] > 0:
            base = closes[-14] if len(closes) >= 14 else closes[0]
            s["pct_14d"] = round(100 * (closes[-1] / base - 1), 2)
        else:
            s["pct_14d"] = None
    return signals


# --- Deeper company background (v3) ---
FORM_DESC = {
    "10-K": "Annual report: full-year financials, risks, and business overview.",
    "10-Q": "Quarterly report: unaudited quarterly financials.",
    "DEF 14A": "Proxy statement: executive pay, board slate, shareholder votes.",
    "SC 13D": "Activist stake: investor crossed 5% with intent to influence.",
    "SC 13D/A": "Amended activist stake disclosure.",
}
ITEM_8K = {
    "1.01": "entered a material agreement", "1.02": "terminated a material agreement",
    "1.03": "bankruptcy/receivership", "2.01": "completed acquisition or disposal of assets",
    "2.02": "announced results of operations (earnings)",
    "2.03": "took on new debt or obligations", "2.04": "triggered events on existing debt",
    "2.05": "exit or disposal costs (restructuring)", "2.06": "material impairments",
    "3.01": "listing/delisting notice", "3.02": "unregistered share sale",
    "4.01": "changed auditors", "4.02": "financials can no longer be relied on (restatement)",
    "5.01": "change in control", "5.02": "executive/director departure or appointment",
    "5.03": "amended bylaws or changed fiscal year", "5.07": "shareholder vote results",
    "7.01": "Reg FD disclosure (investor materials)", "8.01": "other notable events",
    "9.01": "exhibits/financial statements attached",
}


def _filing_summary(form: str, items: str) -> str:
    if form == "8-K" and items:
        parts = [ITEM_8K.get(i.strip()) for i in items.split(",")]
        parts = [p for p in parts if p]
        if parts:
            return "Company " + "; ".join(parts[:3]) + "."
        return "Current report on material events."
    if form == "8-K":
        return "Current report on material events."
    return FORM_DESC.get(form, "")

def company_deep(ticker: str) -> dict:
    """Recent SEC filings + business summary. Every field degrades to empty."""
    deep = {"recent_filings": [], "about": ""}
    rec = None
    try:
        rec = _ticker_map().get(ticker)
    except Exception:
        pass
    if rec:
        try:
            sub = json.loads(_get(
                f"https://data.sec.gov/submissions/CIK{rec['cik']:010d}.json"))
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accnos = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            itemses = recent.get("items", [""] * len(forms))
            for f, d, a, doc, it in list(zip(forms, dates, accnos, docs,
                                             itemses))[:40]:
                if f in ("8-K", "10-K", "10-Q", "DEF 14A", "SC 13D", "SC 13D/A"):
                    acc = a.replace("-", "")
                    deep["recent_filings"].append({
                        "form": f, "date": d,
                        "summary": _filing_summary(f, it or ""),
                        "url": (f"https://www.sec.gov/Archives/edgar/data/"
                                f"{rec['cik']}/{acc}/{doc}")})
                if len(deep["recent_filings"]) >= 5:
                    break
        except Exception:
            pass
        # Business summary via Wikipedia REST (free, no key); best-effort
        try:
            import urllib.parse
            slug = urllib.parse.quote(rec["name"].title().replace(" ", "_"))
            data = json.loads(_get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"))
            ex = data.get("extract", "")
            if ex and "may refer to" not in ex:
                deep["about"] = ex[:420]
        except Exception:
            pass
    return deep


def deep_enrich(signals: list[dict], sample_deep: dict | None = None) -> None:
    for s in signals:
        s["deep"] = ((sample_deep or {}).get(s["ticker"])
                     or (company_deep(s["ticker"]) if sample_deep is None
                         else {"recent_filings": [], "about": ""}))


def spot_price(ticker: str, sample_prices: dict | None = None):
    """Latest close for one ticker (used by the tracking dataset)."""
    hist = ((sample_prices or {}).get(ticker)
            or (price_history(ticker, days=3) if sample_prices is None
                else {"closes": []}))
    closes = hist.get("closes", [])
    return closes[-1] if closes else None
