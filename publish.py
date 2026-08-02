"""Subscription publishing module.

Turns the daily report into a newsletter with a FREE TEASER (counts +
public scorecard — your live track record IS the marketing) and a
MEMBERS-ONLY section (the actual names, prices, and evidence).

Platform: Ghost (ghost.org) — it handles subscriptions, Stripe payments,
paywall, and email delivery. Its Admin API is used here with a pure-stdlib
JWT implementation (no pip installs). The `<!--members-only-->` marker in
the HTML is Ghost's native paywall: everything above it is public,
everything below is for paying members.

Setup (when you're ready to launch):
  1. Create a Ghost site (Ghost(Pro) hosted, or self-host).
  2. Ghost Admin -> Settings -> Integrations -> Add custom integration.
  3. export GHOST_ADMIN_API_URL=https://yoursite.ghost.io
     export GHOST_ADMIN_API_KEY=<id:secret from the integration>
  4. python main.py publish            # creates a DRAFT post to review
     python main.py publish --send     # publishes + emails paid members

Substack note: Substack has no official posting API, so it cannot be
automated legitimately. Ghost is the automatable equivalent (or
Buttondown, if you ever want an email-only alternative).
"""
from __future__ import annotations
import base64
import html as _html
import hashlib
import hmac
import json
import os
import time
import datetime as dt
from urllib.request import Request, urlopen


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _ghost_jwt(api_key: str) -> str:
    kid, secret = api_key.split(":")
    header = _b64url(json.dumps(
        {"alg": "HS256", "typ": "JWT", "kid": kid}).encode())
    now = int(time.time())
    payload = _b64url(json.dumps(
        {"iat": now, "exp": now + 300, "aud": "/admin/"}).encode())
    msg = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(bytes.fromhex(secret), msg,
                           hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


# ---------- newsletter HTML (email-safe, inline styles, light theme) ----------
A = "#B4780F"   # amber, dark enough for white background
BUY, SELL = "#1F7A55", "#B3363E"


def _row(label: str, value: str) -> str:
    return (f'<tr><td style="padding:4px 10px 4px 0;color:#6B7480;'
            f'font-size:13px">{label}</td>'
            f'<td style="padding:4px 0;font-family:monospace;font-size:14px">'
            f'{value}</td></tr>')


def _sig_block(s: dict) -> str:
    color = {"BUY": BUY, "SELL": SELL, "WATCH": A}[s["call"]]
    co = _html.escape((s.get("company") or {}).get("name", s["ticker"]))
    px = f"${s['price_now']:.2f}" if s.get("price_now") else "—"
    since = (f"{s['pct_since_signal']:+.1f}%"
             if s.get("pct_since_signal") is not None else "—")
    ev = "".join(f'<li style="font-family:monospace;font-size:12px;'
                 f'margin:3px 0">{_html.escape(e)}</li>'
                 for e in s.get("evidence", [])[:5])
    short = ('<p style="color:#B3363E;font-size:12px;font-family:monospace;'
             'margin:6px 0"><strong>SHORT CANDIDATE</strong> &mdash; '
             'aggressive tier; unlimited-loss risk, size accordingly.</p>'
             if s.get("short_candidate") else "")
    warn = ('<p style="color:' + A + ';font-size:13px;margin:6px 0">'
            '&#9888; Earnings likely within ~2 weeks (estimated)</p>'
            if s.get("earnings_soon") else "")
    return f"""
<div style="border:1px solid #E4E0D8;border-left:4px solid {color};
border-radius:8px;padding:14px 16px;margin:14px 0;background:#FFFFFF">
  <p style="margin:0;font-family:monospace">
    <strong style="color:{color}">{s['call']}</strong>
    &nbsp;<strong style="font-size:17px">{s['ticker']}</strong>
    &nbsp;<span style="color:#6B7480">{co}</span></p>
  <table style="border-collapse:collapse;margin:8px 0">
    {_row("Price now", px)}{_row("Since signal", since)}
    {_row("Distinct buyers / sellers",
          f"{s['distinct_buyers']} / {s['distinct_sellers']}")}
    {_row("Score (buy / sell)", f"{s['buy_score']} / {s['sell_score']}")}
  </table>{short}{warn}
  <p style="margin:6px 0 2px;font-size:13px;color:#6B7480">Disclosed trades:</p>
  <ul style="margin:0 0 0 18px;padding:0">{ev}</ul>
</div>"""


def build_newsletter(signals: list[dict], sc: dict | None,
                     date_str: str) -> tuple[str, str]:
    """Returns (title, html). HTML contains Ghost's paywall marker."""
    buys = [s for s in signals if s["call"] == "BUY"]
    sells = [s for s in signals if s["call"] == "SELL"]
    watch = [s for s in signals if s["call"] == "WATCH"]
    verdict = ""
    if sc and sc["summary"]["scored"]:
        sm = sc["summary"]
        verdict = (f'<p style="font-family:monospace;font-size:14px;'
                   f'background:#F4F0E8;border-radius:8px;padding:10px 14px">'
                   f'Live track record: {sm["issued_total"]} buy signals '
                   f'issued &middot; <strong>{sm["beat_pct"]}% beat the '
                   f'S&amp;P 500</strong> &middot; avg excess '
                   f'{sm["avg_excess"]:+.2f}%. Every signal is scored '
                   f'publicly &mdash; wins and losses alike.</p>')
    title = f"InsiderEdge Daily — {date_str}"
    paid_blocks = "".join(_sig_block(s) for s in buys + sells + watch[:5])
    html = f"""
<div style="font-family:Georgia,serif;color:#20242B;max-width:640px">
<p style="font-size:15px">Good morning. Today the tracker flags
<strong style="color:{BUY}">{len(buys)} buy signal(s)</strong>,
<strong style="color:{SELL}">{len(sells)} sell/avoid</strong>, and
{len(watch)} watchlist name(s), drawn from every SEC Form 4, 13D activist
stake, and congressional disclosure filed in the window.</p>
{verdict}
<p style="font-size:14px;color:#6B7480">The names, prices, insider
histories, and evidence are below for members.</p>
<!--members-only-->
{paid_blocks if paid_blocks else '<p>No signals met the threshold today — sitting out is a position.</p>'}
<hr style="border:none;border-top:1px solid #E4E0D8;margin:18px 0">
<p style="font-size:12px;color:#6B7480">Form 4 filings lag trades by up to
2 business days; congressional disclosures by up to 45 days; political
amounts are range midpoints. This newsletter is impersonal research
published to all subscribers alike — it is not individualized investment
advice, and past performance does not guarantee future results.</p>
</div>"""
    return title, html


def publish(signals: list[dict], sc: dict | None,
            send: bool = False, preview_path: str | None = None) -> None:
    date_str = dt.date.today().strftime("%B %d, %Y")
    title, html = build_newsletter(signals, sc, date_str)
    if preview_path:
        wrapper = (f"<!doctype html><html><head><meta charset='utf-8'>"
                   f"<meta name='viewport' content='width=device-width,"
                   f"initial-scale=1'><title>{title}</title></head>"
                   f"<body style='background:#FAF8F4;padding:24px'>"
                   f"<h1 style='font-family:Georgia,serif;max-width:640px'>"
                   f"{title}</h1>"
                   + html.replace("<!--members-only-->",
                        "<div style='border:2px dashed #B4780F;border-radius:8px;"
                        "padding:10px 14px;color:#B4780F;font-family:monospace;"
                        "font-size:13px;max-width:640px'>&#128274; PAYWALL — "
                        "everything below this line is members-only</div>")
                   + "</body></html>")
        with open(preview_path, "w") as f:
            f.write(wrapper)
        print(f"[publish] preview written: {preview_path}")
        return
    url = os.environ.get("GHOST_ADMIN_API_URL", "").rstrip("/")
    key = os.environ.get("GHOST_ADMIN_API_KEY", "")
    if not url or not key:
        raise SystemExit("Set GHOST_ADMIN_API_URL and GHOST_ADMIN_API_KEY "
                         "(see insider_edge/publish.py docstring).")
    body = {"posts": [{"title": title, "html": html,
                       "status": "published" if send else "draft",
                       "visibility": "paid",
                       "email_segment": "status:paid" if send else None}]}
    req = Request(f"{url}/ghost/api/admin/posts/?source=html"
                  + ("&newsletter=default-newsletter" if send else ""),
                  data=json.dumps(body).encode(), method="POST",
                  headers={"Authorization": f"Ghost {_ghost_jwt(key)}",
                           "Content-Type": "application/json"})
    with urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    slug = res.get("posts", [{}])[0].get("slug", "?")
    print(f"[publish] {'PUBLISHED + emailed' if send else 'DRAFT created'}: "
          f"{url}/{slug}")
