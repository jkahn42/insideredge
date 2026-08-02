"""Related legislative activity via the official Congress.gov API.

Free key: https://api.congress.gov/sign-up  ->  export CONGRESS_API_KEY=...

Honesty by design: this is KEYWORD matching against bill titles/summaries.
It surfaces "related legislative activity" for context — it cannot and does
not assert that a politician's trade was motivated by a specific bill.
Every company card also gets direct search links to congress.gov, which
always work even if the API is down or the key is missing.
"""
from __future__ import annotations
import json
import os
import re
import urllib.parse
from urllib.request import Request, urlopen

BASE = "https://api.congress.gov/v3"


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _bill_summary(congress, btype, number) -> str:
    """Official CRS summary for a bill; empty string on any failure."""
    if not _key():
        return ""
    try:
        url = (f"{BASE}/bill/{congress}/{str(btype).lower()}/{number}/summaries"
               f"?format=json&api_key={_key()}")
        req = Request(url, headers={"User-Agent": "InsiderEdge/2.0"})
        with urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        summs = data.get("summaries", [])
        if summs:
            return _strip_html(summs[-1].get("text", ""))[:320]
    except Exception:
        pass
    return ""


def _key() -> str:
    return os.environ.get("CONGRESS_API_KEY", "")


def _search_terms(company_name: str, ticker: str, industry: str) -> list[str]:
    # strip corp suffixes: "NVIDIA CORP" -> "NVIDIA"
    clean = re.sub(r"\b(INC|CORP|CO|LTD|PLC|LP|HOLDINGS?|GROUP|COMPANY|/DE|/MD)\b\.?",
                   "", company_name, flags=re.I).strip(" ,.")
    terms = [clean] if len(clean) >= 4 else [ticker]
    if industry:
        terms.append(industry)
    return terms[:2]


def search_links(company_name: str, ticker: str, industry: str) -> list[dict]:
    """Always-available deep links into congress.gov search."""
    out = []
    for term in _search_terms(company_name, ticker, industry):
        q = urllib.parse.quote(term)
        out.append({"label": f"Bills mentioning \u201c{term}\u201d", "browse": True,
                    "url": f"https://www.congress.gov/search?q={q}&source=legislation"})
        out.append({"label": f"Hearings mentioning \u201c{term}\u201d", "browse": True,
                    "url": f"https://www.congress.gov/search?q={q}&source=committeemeetings"})
    return out


def api_bills(term: str, limit: int = 4) -> list[dict]:
    """Recent bills matching term via the API (empty list on any failure)."""
    if not _key():
        return []
    try:
        url = (f"{BASE}/bill?format=json&limit={limit}&sort=updateDate+desc"
               f"&q={urllib.parse.quote(term)}&api_key={_key()}")
        req = Request(url, headers={"User-Agent": "InsiderEdge/2.0"})
        with urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        out = []
        for b in data.get("bills", []):
            title = b.get("title", "")
            if term.lower() not in title.lower():
                continue  # API q-matching is loose; require the term in title
            la = b.get("latestAction", {}) or {}
            desc = _bill_summary(b.get("congress"), b.get("type"),
                                 b.get("number"))
            if la.get("text"):
                act = f"Latest action {la.get('actionDate','')}: {la['text'][:140]}"
                desc = f"{desc} \u2014 {act}" if desc else act
            out.append({
                "desc": desc,
                "label": f"{b.get('type','')}{b.get('number','')}: {title[:90]}",
                "url": (f"https://www.congress.gov/bill/"
                        f"{b.get('congress','')}th-congress/"
                        f"{'senate' if str(b.get('type','')).upper().startswith('S') else 'house'}-bill/"
                        f"{b.get('number','')}"),
                "updated": b.get("updateDate", ""),
            })
        return out
    except Exception:
        return []


def legislative_context(signal: dict,
                        sample: dict | None = None) -> list[dict]:
    tk = signal["ticker"]
    name = signal.get("company", {}).get("name", tk)
    industry = signal.get("company", {}).get("industry", "")
    if sample is not None:
        return sample.get(tk, []) + search_links(name, tk, industry)
    items: list[dict] = []
    for term in _search_terms(name, tk, industry)[:1]:
        items.extend(api_bills(term))
    return items + search_links(name, tk, industry)
