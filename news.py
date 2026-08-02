"""Automatic news awareness (v10).

Pulls recent headlines per signaled/tracked ticker from Google News RSS
(free, no key) and pattern-matches for risk keywords. This is deliberately
humble: the bot can FETCH and FLAG news, but it cannot UNDERSTAND it —
that judgment layer is the "Ask Claude" button on each card.
"""
from __future__ import annotations
import re
import urllib.parse
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

RISK_WORDS = {
    "lawsuit": "lawsuit", "sued": "lawsuit", "sues": "lawsuit",
    "investigation": "investigation", "probe": "investigation",
    "subpoena": "investigation", "sec charges": "SEC action",
    "fraud": "fraud allegation", "restatement": "restatement",
    "delisting": "delisting risk", "bankruptcy": "bankruptcy risk",
    "chapter 11": "bankruptcy risk", "default": "debt default",
    "downgrade": "analyst downgrade", "downgraded": "analyst downgrade",
    "offering": "share offering (dilution)", "dilution": "dilution",
    "recall": "product recall", "halted": "trading halt",
    "resigns": "executive resignation", "resignation": "executive resignation",
    "layoffs": "layoffs", "guidance cut": "guidance cut",
    "misses": "earnings miss", "shortfall": "revenue shortfall",
    "data breach": "data breach", "short seller": "short-seller report",
}


def fetch_news(ticker: str, company_name: str = "",
               limit: int = 5) -> list[dict]:
    """Latest headlines via Google News RSS. Empty list on any failure."""
    term = f'"{company_name}" stock' if company_name else f"{ticker} stock"
    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(term) + "&hl=en-US&gl=US&ceid=US:en")
    try:
        req = Request(url, headers={"User-Agent": "InsiderEdge/10.0"})
        with urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        out = []
        for item in root.findall(".//item")[:limit]:
            out.append({
                "title": (item.findtext("title") or "").strip(),
                "url": (item.findtext("link") or "").strip(),
                "date": (item.findtext("pubDate") or "")[:16],
                "source": (item.findtext("source") or "").strip(),
            })
        return out
    except Exception:
        return []


def risk_flags(headlines: list[dict]) -> list[str]:
    """Distinct risk labels found across headlines (pattern match only)."""
    found: list[str] = []
    for h in headlines:
        low = (h.get("title") or "").lower()
        for word, label in RISK_WORDS.items():
            if word in low and label not in found:
                found.append(label)
    return found


def annotate(signals: list[dict], sample: dict | None = None) -> None:
    for s in signals:
        if sample is not None:
            items = sample.get(s["ticker"], [])
        else:
            items = fetch_news(s["ticker"],
                               (s.get("company") or {}).get("name", ""))
        s["news"] = items
        s["news_flags"] = risk_flags(items)
