"""Pull and parse SEC Form 4 (insider trading) filings from EDGAR.

Strategy: walk EDGAR's daily index for the lookback window, grab every Form 4,
parse the ownershipDocument XML, and normalize into transaction dicts:

    {ticker, insider_name, role, date, type: "P"|"S", shares, price, value_usd}

Transaction codes used: P = open-market purchase, S = open-market sale.
We deliberately ignore option exercises (M), grants (A), gifts (G) etc. —
they are compensation mechanics, not conviction signals.
"""
from __future__ import annotations
import json
import re
import time
import datetime as dt
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen

from . import config

HEADERS = {"User-Agent": config.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _get(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=30) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                return data
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return b""


def _quarter(d: dt.date) -> str:
    return f"QTR{(d.month - 1) // 3 + 1}"


def _classify_role(rel: ET.Element | None) -> str:
    if rel is None:
        return "OTHER"
    title = (rel.findtext("officerTitle") or "").upper()
    if rel.findtext("isOfficer") == "1" or title:
        for key in ("CEO", "CHIEF EXECUTIVE"):
            if key in title:
                return "CEO"
        if "CFO" in title or "FINANCIAL" in title:
            return "CFO"
        if "COO" in title or "OPERATING" in title:
            return "COO"
        if "PRESIDENT" in title:
            return "PRESIDENT"
        return "OFFICER"
    if rel.findtext("isDirector") == "1":
        return "DIRECTOR"
    if rel.findtext("isTenPercentOwner") == "1":
        return "10% OWNER"
    return "OTHER"


def parse_form4_xml(xml_bytes: bytes) -> list[dict]:
    """Parse one ownershipDocument XML into normalized transactions."""
    out: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    ticker = (root.findtext(".//issuerTradingSymbol") or "").upper().strip()
    from .data_congress import _valid_ticker
    if not _valid_ticker(ticker):
        return out
    planned = (root.findtext(".//aff10b5One") or "").strip() in ("1", "true")
    owner = root.find(".//reportingOwner")
    name = ""
    role = "OTHER"
    owner_cik = ""
    if owner is not None:
        name = owner.findtext(".//rptOwnerName") or ""
        owner_cik = (owner.findtext(".//rptOwnerCik") or "").strip()
        role = _classify_role(owner.find(".//reportingOwnerRelationship"))
    for txn in root.findall(".//nonDerivativeTransaction"):
        code = txn.findtext(".//transactionCode") or ""
        if code not in ("P", "S"):
            continue
        try:
            shares = float(txn.findtext(".//transactionShares/value") or 0)
            price = float(txn.findtext(".//transactionPricePerShare/value") or 0)
        except (TypeError, ValueError):
            continue
        date = txn.findtext(".//transactionDate/value") or ""
        value = shares * price
        if value < config.MIN_INSIDER_TRADE_USD:
            continue
        out.append({
            "ticker": ticker, "insider_name": name.strip(), "role": role,
            "owner_cik": owner_cik, "date": date[:10], "type": code,
            "planned": planned and code == "S",
            "shares": shares, "price": price, "value_usd": round(value, 2),
        })
    return out


def fetch_form4_transactions(lookback_days: int | None = None) -> list[dict]:
    """Fetch all Form 4 transactions filed in the lookback window."""
    lookback = lookback_days or config.INSIDER_LOOKBACK_DAYS
    today = dt.date.today()
    txns: list[dict] = []
    for offset in range(lookback):
        day = today - dt.timedelta(days=offset)
        if day.weekday() >= 5:  # markets/EDGAR closed weekends
            continue
        idx_url = (f"{config.SEC_DAILY_INDEX}/{day.year}/{_quarter(day)}/"
                   f"form.{day.strftime('%Y%m%d')}.idx")
        try:
            idx = _get(idx_url).decode("latin-1")
        except Exception:
            continue  # holiday or index not yet published
        for line in idx.splitlines():
            if not line.startswith("4 ") and not line.startswith("4/A "):
                continue
            m = re.search(r"(edgar/data/\S+\.txt)\s*$", line)
            if not m:
                continue
            filing_url = f"https://www.sec.gov/Archives/{m.group(1)}"
            try:
                raw = _get(filing_url).decode("latin-1", errors="ignore")
            except Exception:
                continue
            xm = re.search(r"<XML>(.*?)</XML>", raw, re.S)
            if xm:
                txns.extend(parse_form4_xml(xm.group(1).strip().encode()))
            time.sleep(0.12)  # respect SEC's 10 req/sec limit with margin
    return txns


def load_sample(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


# --- SC 13D activist stake tracker (v3) ---
def _cik_to_ticker_map() -> dict[int, str]:
    data = json.loads(_get("https://www.sec.gov/files/company_tickers.json"))
    return {int(v["cik_str"]): v["ticker"].upper() for v in data.values()}


def fetch_13d_signals(lookback_days: int | None = None) -> list[dict]:
    """SC 13D filings = investor crossed 5% WITH activist intent.

    Emitted as pseudo-transactions (role ACTIVIST, nominal value) so they
    flow through the same scoring pipeline. A lone 13D therefore lands on
    the WATCH list by design — corroboration promotes it to BUY.
    """
    lookback = lookback_days or config.INSIDER_LOOKBACK_DAYS
    today = dt.date.today()
    try:
        cikmap = _cik_to_ticker_map()
    except Exception:
        return []
    out: list[dict] = []
    for offset in range(lookback):
        day = today - dt.timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        idx_url = (f"{config.SEC_DAILY_INDEX}/{day.year}/{_quarter(day)}/"
                   f"form.{day.strftime('%Y%m%d')}.idx")
        try:
            idx = _get(idx_url).decode("latin-1")
        except Exception:
            continue
        for line in idx.splitlines():
            if not line.startswith("SC 13D"):
                continue
            m = re.search(r"(edgar/data/\S+\.txt)\s*$", line)
            if not m:
                continue
            try:
                head = _get(f"https://www.sec.gov/Archives/{m.group(1)}"
                            ).decode("latin-1", errors="ignore")[:6000]
            except Exception:
                continue
            sub = re.search(r"SUBJECT COMPANY:.*?CENTRAL INDEX KEY:\s*(\d+)",
                            head, re.S)
            filer = re.search(r"FILED BY:.*?COMPANY CONFORMED NAME:\s*(.+)",
                              head, re.S)
            if not sub:
                continue
            tk = cikmap.get(int(sub.group(1)))
            if not tk:
                continue
            who = (filer.group(1).splitlines()[0].strip()
                   if filer else "Activist investor")
            out.append({"ticker": tk, "insider_name": f"13D: {who}",
                        "role": "ACTIVIST", "date": day.isoformat(),
                        "type": "P", "shares": 0, "price": 0,
                        "value_usd": config.NOMINAL_13D_VALUE})
            time.sleep(0.12)
    return out


# --- Trader history (v4) ---
HISTORY_FILE = "insider_history.json"


def update_history(txns: list[dict]) -> dict:
    """Accumulate every observed insider txn into a persistent ledger.
    Returns counts: {"NAME|TICKER|P": n_buys_on_record, ...}"""
    try:
        with open(HISTORY_FILE) as f:
            hist = json.load(f)
    except Exception:
        hist = {"txns": []}
    seen = {(t["insider_name"], t["ticker"], t["date"], t["value_usd"])
            for t in hist["txns"]}
    for t in txns:
        key = (t["insider_name"], t["ticker"], t["date"], t["value_usd"])
        if key not in seen:
            hist["txns"].append({k: t[k] for k in
                ("insider_name", "ticker", "date", "type", "value_usd")})
            seen.add(key)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f)
    counts: dict[str, int] = {}
    for t in hist["txns"]:
        k = f"{t['insider_name']}|{t['ticker']}|{t['type']}"
        counts[k] = counts.get(k, 0) + 1
    return counts


def insider_profile(owner_cik: str) -> str:
    """One-line official history for an insider from their SEC filing index."""
    if not owner_cik:
        return ""
    try:
        sub = json.loads(_get(
            f"https://data.sec.gov/submissions/CIK{int(owner_cik):010d}.json"))
        forms = sub.get("filings", {}).get("recent", {}).get("form", [])
        dates = sub.get("filings", {}).get("recent", {}).get("filingDate", [])
        n4 = sum(1 for f in forms if f in ("4", "4/A"))
        since = min(dates)[:4] if dates else ""
        if n4:
            return f"{n4} Form 4 filings on record since {since}"
    except Exception:
        pass
    return ""
