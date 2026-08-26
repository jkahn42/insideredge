"""Portal generator — v8 "Daylight" design.

Modern light fintech look: porcelain background, white rounded cards with
soft shadows, pill call-badges, an at-a-glance summary strip, gradient
sparklines, large tap-friendly decision buttons. Still zero JS frameworks,
native <details> folds, responsive, reduced-motion safe.
"""
from __future__ import annotations
import html
import os
import urllib.parse
import datetime as dt

P = {"bg": "#F1F7F3", "card": "#FFFFFF", "ink": "#183B31", "mut": "#5F7A6E",
     "line": "#DCE8DF", "brand": "#0E8F6E", "buy": "#17A374",
     "sell": "#E15A72", "watch": "#CE8A1B"}


def _repo() -> str:
    from . import config
    return os.environ.get("GITHUB_REPOSITORY", "") or config.GITHUB_REPO_FALLBACK


def _issue_url(title: str, body: str) -> str:
    repo = _repo()
    if not repo:
        return ""
    q = urllib.parse.urlencode({"title": title, "body": body})
    return f"https://github.com/{repo}/issues/new?{q}"


def _sparkline(closes: list[float], color: str, w=200, h=52) -> str:
    if len(closes) < 2:
        return '<span class="mut tiny">no price data</span>'
    lo, hi = min(closes), max(closes)
    rng = (hi - lo) or 1
    pts = [(i * w / (len(closes) - 1),
            h - 6 - (c - lo) / rng * (h - 12)) for i, c in enumerate(closes)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{h} " + line + f" {w},{h}"
    gid = f"g{abs(hash(color + str(closes[0]))) % 99999}"
    return (f'<svg viewBox="0 0 {w} {h}" class="spark" role="img" '
            f'aria-label="14 day price trend"><defs>'
            f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".22"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>'
            f'</linearGradient></defs>'
            f'<polygon points="{area}" fill="url(#{gid})"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" '
            f'stroke-width="2.25" stroke-linecap="round" '
            f'stroke-linejoin="round"/></svg>')


def _pct(v) -> str:
    if v is None:
        return '<span class="mut">—</span>'
    cls = "up" if v >= 0 else "dn"
    return f'<span class="num {cls}">{v:+.1f}%</span>'


def _ask_claude_url(s: dict) -> str:
    co = (s.get("company") or {}).get("name", s["ticker"])
    prompt = (f"Research {s['ticker']} ({co}) for me. My InsiderEdge bot "
              f"flagged it {s['call']} today based on insider/congressional "
              f"trading clusters ({s['distinct_buyers']} buyers, "
              f"{s['distinct_sellers']} sellers, net score "
              f"{s['net_score']:+.1f}). Please check today's news, recent "
              f"earnings, analyst moves, and any red flags, then give me the "
              f"case FOR and AGAINST acting on this signal.")
    return "https://claude.ai/new?q=" + urllib.parse.quote(prompt)


def _buttons(s: dict) -> str:
    tk = s["ticker"]
    body = f"Decision from portal on {dt.date.today().isoformat()}. Tap Submit."
    b = _issue_url(f"TRACK BUY {tk}", body)
    sl = _issue_url(f"TRACK SELL {tk}", body)
    rj = _issue_url(f"REJECT {tk}", body)
    ask = (f'<a class="btn bt-ask" href="{_ask_claude_url(s)}" '
           f'target="_blank" rel="noopener">Ask Claude</a>')
    if not b:
        return (f'<div class="btns">{ask}</div>'
                '<p class="mut tiny">Track/reject buttons activate once this '
                'runs from your GitHub repository.</p>')
    return (f'<div class="btns">'
            f'<a class="btn bt-buy" href="{b}">I\u2019ll buy</a>'
            f'<a class="btn bt-sell" href="{sl}">I\u2019ll sell</a>'
            f'{ask}'
            f'<a class="btn bt-skip" href="{rj}">Not interested</a></div>'
            f'<p class="mut tiny">Opens a pre-filled note \u2014 tap \u201cSubmit new '
            f'issue\u201d to confirm. Tomorrow starts a 21-day tracker (or hides it).</p>')


def _card(s: dict) -> str:
    color = {"BUY": P["buy"], "SELL": P["sell"], "WATCH": P["watch"]}[s["call"]]
    label = {"BUY": "Buy", "SELL": "Sell / avoid", "WATCH": "Watch"}[s["call"]]
    co = s.get("company", {})
    deep = s.get("deep", {}) or {}
    name = html.escape(co.get("name", s["ticker"]))
    ind = html.escape(co.get("industry", ""))
    about = html.escape(deep.get("about", ""))
    px = f"${s['price_now']:.2f}" if s.get("price_now") else "—"
    sig_px = f"${s['price_at_signal']:.2f}" if s.get("price_at_signal") else "—"
    evid = "".join(f"<li>{html.escape(e)}</li>" for e in s.get("evidence", []))
    actors = "".join(
        f'<li><b>{html.escape(a["name"])}</b> '
        f'<span class="mut">({html.escape(str(a["kind"]))})</span>'
        f'<div class="mut tiny">{html.escape(a["note"])}</div></li>'
        for a in s.get("actors", []))
    _leg = s.get("legislation", [])
    _bills = [x for x in _leg if not x.get("browse")]
    _browse = [x for x in _leg if x.get("browse")]
    laws = "".join(
        f'<li><a href="{html.escape(x["url"])}" target="_blank" rel="noopener">'
        f'{html.escape(x["label"])}</a>'
        + (f'<div class="mut tiny">{html.escape(x["desc"])}</div>'
           if x.get("desc") else "") + '</li>' for x in _bills)
    if not _bills:
        laws = ('<li class="mut">No bills matched this company by keyword \u2014 '
                'matched bills with plain-English summaries appear here once '
                'your Congress.gov API key is set (setup Part 6).</li>')
    if _browse:
        laws += ('<li class="mut tiny browse-head">Browse congress.gov:</li>'
                 + "".join(f'<li class="browse">'
                           f'<a href="{html.escape(x["url"])}" target="_blank" '
                           f'rel="noopener">{html.escape(x["label"])}</a></li>'
                           for x in _browse))
    filings = "".join(
        f'<li><a href="{html.escape(f["url"])}" target="_blank" rel="noopener">'
        f'{html.escape(f["form"])} \u00b7 {html.escape(f["date"])}</a>'
        + (f'<div class="mut tiny">{html.escape(f["summary"])}</div>'
           if f.get("summary") else "") + '</li>'
        for f in deep.get("recent_filings", []))
    closes = s.get("trend", {}).get("closes", [])
    news_items = "".join(
        f'<li><a href="{html.escape(n["url"])}" target="_blank" rel="noopener">'
        f'{html.escape(n["title"])}</a>'
        f'<div class="mut tiny">{html.escape(n.get("source",""))} \u00b7 '
        f'{html.escape(n.get("date",""))}</div></li>'
        for n in s.get("news", []))
    short = ('<span class="chip chip-short">Short candidate \u00b7 aggressive tier</span>'
             '<p class="mut tiny">Unplanned selling by multiple executives, zero '
             'offsetting buyers. Shorting has unlimited-loss, borrow and squeeze '
             'risk \u2014 never auto-traded by this bot.</p>'
             if s.get("short_candidate") else "")
    earn = ('<span class="chip chip-earn">\u26a0 Earnings likely \u2248 2 weeks '
            '(estimated)</span>' if s.get("earnings_soon") else "")
    nflags = "".join(f'<span class="chip chip-news">\u26a0 News: '
                     f'{html.escape(f)}</span>'
                     for f in s.get("news_flags", [])[:3])
    themes = "".join(f'<span class="chip chip-theme">{html.escape(t)}</span>'
                     for t in s.get("themes", []))
    herd = ('<span class="chip chip-herd">Herding pick \u2014 industry '
            'cluster, below signal threshold</span>'
            if s.get("herd_pick") else "")
    tm = s.get("timing")
    timing = (f'<span class="chip chip-{tm["cls"]}">'
              f'{html.escape(tm["label"])}</span>' if tm else "")
    return f"""
<article class="card" id="c-{s['ticker']}" style="--c:{color}">
  <header class="head">
    <span class="pill">{label}</span>
    <div class="title"><span class="tk">{s['ticker']}</span>
      <span class="co">{name}</span></div>
    <span class="net num">net {s['net_score']:+.1f}</span>
  </header>
  <div class="body">
    {f'<p class="mut ind">{ind}</p>' if ind else ''}
    {f'<p class="about">{about}</p>' if about else ''}
    <div class="stats">
      <div class="stat"><span class="lbl">Now</span><span class="num val">{px}</span></div>
      <div class="stat"><span class="lbl">At signal</span><span class="num val">{sig_px}</span></div>
      <div class="stat"><span class="lbl">Since signal</span>{_pct(s.get('pct_since_signal'))}</div>
      <div class="stat"><span class="lbl">14 day</span>{_pct(s.get('pct_14d'))}</div>
    </div>
    {_sparkline(closes, color)}
    <div class="chips">{timing}{herd}{themes}{short}{earn}{nflags}</div>
    <p class="mut meta">{s['distinct_buyers']} buyer(s) \u00b7 {s['distinct_sellers']} seller(s) \u00b7 score {s['buy_score']} / {s['sell_score']}</p>
    {_buttons(s)}
    <details><summary>Latest news <span class="cnt">{len(s.get('news', []))}</span></summary>
      <ul class="list">{news_items or '<li class="mut">No recent headlines fetched.</li>'}</ul>
      <p class="mut tiny">Headlines are auto-fetched; risk chips are keyword matches, not judgment \u2014 use Ask Claude for the read.</p></details>
    <details><summary>Disclosed trades <span class="cnt">{len(s.get('evidence', []))}</span></summary>
      <ul class="mono">{evid}</ul></details>
    <details><summary>Who\u2019s trading \u2014 history <span class="cnt">{len(s.get('actors', []))}</span></summary>
      <ul class="list">{actors or '<li class="mut">No actor history available.</li>'}</ul></details>
    <details><summary>Recent SEC filings</summary>
      <ul class="list">{filings or '<li class="mut">None fetched.</li>'}</ul></details>
    <details><summary>Related legislative activity</summary>
      <ul class="list">{laws or '<li class="mut">None found via keyword match.</li>'}</ul>
      <p class="mut tiny">Keyword matches for context only \u2014 not evidence a trade was motivated by any bill.</p></details>
  </div>
</article>"""


def _fmt_pct_cell(v, colored=False):
    if v is None:
        return "<td></td>"
    if colored:
        cls = "up" if v >= 0 else "dn"
        return '<td class="num ' + cls + '">' + f"{v:+.1f}%" + "</td>"
    return '<td class="num">' + f"{v:+.1f}%" + "</td>"


def _scorecard_section(sc: dict | None) -> str:
    if not sc:
        return ""
    sm = sc["summary"]
    if sm["issued_total"] == 0:
        verdict = ("No buy signals issued yet \u2014 the scorecard starts "
                   "scoring itself from the first one.")
    elif sm["scored"] == 0:
        verdict = (f"{sm['issued_total']} buy signal(s) issued; "
                   "scoring begins 5 days after issue.")
    else:
        verdict = (f"{sm['issued_total']} buy signals issued \u00b7 "
                   f"{sm['scored']} scored \u00b7 <b>{sm['beat_pct']}% beat "
                   f"SPY</b> \u00b7 avg excess {sm['avg_excess']:+.2f}%")
    rows = ""
    for r in sc["rows"]:
        rows += ('<tr><td class="tkr">' + r["ticker"] + "</td><td>"
                 + r["issued"] + '</td><td class="num">' + str(r["age"]) + "d</td>"
                 + _fmt_pct_cell(r["ret"]) + _fmt_pct_cell(r["spy_ret"])
                 + _fmt_pct_cell(r["excess"], colored=True) + "</tr>")
    table = ""
    if sc["rows"]:
        table = ('<div class="tablewrap"><table class="sc"><thead><tr>'
                 '<th>Ticker</th><th>Issued</th><th>Age</th><th>Return</th>'
                 '<th>SPY</th><th>Excess</th></tr></thead><tbody>'
                 + rows + '</tbody></table></div>')
    return ('<section><h2>Signal scorecard</h2>'
            '<div class="panel"><p class="verdict">' + verdict + '</p>'
            + table + '</div></section>')


CHART_COLORS = ["#0E8F6E", "#4C7FE0", "#E15A72", "#CE8A1B", "#7C4DBE",
                "#17A374", "#B4562F", "#3B8EA5", "#A44FB0", "#5C8A2E"]


def _consolidated_chart(tracked: list[dict]) -> str:
    lines = [t for t in tracked if len(t.get("series") or []) >= 2]
    if not lines:
        return ""
    W, H, L, R, T, B = 660, 250, 46, 60, 16, 30
    maxd = max(max(len(t["series"]) - 1 for t in lines), 5)
    vals = [v for t in lines for v in t["series"]] + [0.0]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.14 or 1.0
    lo, hi = lo - pad, hi + pad

    def X(i):
        return L + i * (W - L - R) / maxd

    def Y(v):
        return T + (hi - v) * (H - T - B) / (hi - lo)

    parts = [f'<line x1="{L}" y1="{Y(0):.1f}" x2="{W - R}" y2="{Y(0):.1f}" '
             f'stroke="var(--mut)" stroke-dasharray="3 4" stroke-width="1" '
             f'opacity=".55"/>']
    for lab, v in (("0%", 0.0), (f"{hi - pad:+.0f}%", hi - pad),
                   (f"{lo + pad:+.0f}%", lo + pad)):
        parts.append(f'<text x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" '
                     f'font-size="10" fill="var(--mut)">{lab}</text>')
    parts.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 6}" '
                 f'text-anchor="middle" font-size="10" fill="var(--mut)">'
                 f'days since decision</text>')
    legend = ""
    for n, t in enumerate(lines):
        col = CHART_COLORS[n % len(CHART_COLORS)]
        dash = ' stroke-dasharray="6 5"' if t["action"] == "SELL" else ""
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}"
                       for i, v in enumerate(t["series"]))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                     f'stroke-width="2.2" stroke-linecap="round" '
                     f'stroke-linejoin="round"{dash}/>')
        lx, ly = X(len(t["series"]) - 1), Y(t["series"][-1])
        parts.append(f'<text x="{lx + 5:.1f}" y="{ly + 4:.1f}" font-size="11" '
                     f'font-weight="700" fill="{col}">'
                     f'{html.escape(t["ticker"])}</text>')
        cur = t["series"][-1]
        good = (cur >= 0) if t["action"] == "BUY" else (cur <= 0)
        legend += (f'<span class="lg"><i style="background:{col}"></i>'
                   f'{html.escape(t["ticker"])} '
                   f'<span class="mut">({t["action"].title()})</span> '
                   f'<b class="{"up" if good else "dn"}">{cur:+.1f}%</b></span>')
    return (f'<div class="panel chartpanel">'
            f'<p class="mut tiny" style="margin-bottom:.4rem">All tracked '
            f'decisions, indexed to 0% on each decision day. Dashed = '
            f'sell/avoid calls (falling is good).</p>'
            f'<svg viewBox="0 0 {W} {H}" class="bigchart" role="img" '
            f'aria-label="Consolidated tracked performance">{"".join(parts)}'
            f'</svg><div class="legend">{legend}</div></div>')


def _tracking_section(tracked: list[dict]) -> str:
    if not tracked:
        return ""
    rows = ""
    for t in tracked:
        color = P["buy"] if t["action"] == "BUY" else P["sell"]
        spx = f"${t['start_price']:.2f}" if t.get("start_price") else "—"
        npx = f"${t['price_now']:.2f}" if t.get("price_now") else "—"
        pctdone = int(100 * t["day"] / t["days_total"])
        pv = t.get("pct")
        if pv is None:
            pcell = '<span class="mut">—</span>'
        else:
            good = (pv >= 0) if t["action"] == "BUY" else (pv <= 0)
            pcell = (f'<span class="num {"up" if good else "dn"}">'
                     f'{pv:+.1f}%</span>')
        sell_note = ('<p class="mut tiny">Sell/avoid call: a falling price '
                     'means the call is working.</p>'
                     if t["action"] == "SELL" else "")
        act = (f'<div class="chips" style="margin:.1rem 0 .45rem">'
               f'<span class="chip chip-fresh">\U0001f501 '
               f'{__import__("html").escape(t["activity"])}</span></div>'
               if t.get("activity") else "")
        tflags = "".join(f'<span class="chip chip-news">\u26a0 News: '
                         f'{__import__("html").escape(f)}</span>'
                         for f in t.get("news_flags", [])[:3])
        tflags = f'<div class="chips" style="margin-bottom:.4rem">{tflags}</div>' if tflags else ""
        rows += f"""
<article class="card slim" style="--c:{color}">
  <header class="head">
    <span class="pill">{t['action'].title()}</span>
    <div class="title"><span class="tk">{t['ticker']}</span></div>
    <span class="net">day {t['day']} / {t['days_total']}</span>
  </header>
  <div class="body">
    {tflags}{act}
    <div class="prog"><i style="width:{pctdone}%"></i></div>
    <div class="stats">
      <div class="stat"><span class="lbl">Decision \u00b7 {t['start_date']}</span><span class="num val">{spx}</span></div>
      <div class="stat"><span class="lbl">Now</span><span class="num val">{npx}</span></div>
      <div class="stat"><span class="lbl">Since decision</span>{pcell}</div>
    </div>
    {sell_note}
  </div>
</article>"""
    return ('<section><h2>Your tracked decisions</h2>'
            + _consolidated_chart(tracked)
            + f'<div class="grid">{rows}</div></section>')


def _summary_strip(groups: dict, sc: dict | None,
                   portfolio: float | None = None) -> str:
    port = ""
    if portfolio is not None:
        pc = P["buy"] if portfolio >= 0 else P["sell"]
        port = (f'<div class="kpi" style="--c:{pc}">'
                f'<span class="num big">{portfolio:+.1f}%</span>'
                f'<span class="lbl">your calls \u00b7 avg</span></div>')
    beat = ""
    if sc and sc["summary"]["scored"]:
        beat = (f'<div class="kpi" style="--c:var(--brand)">'
                f'<span class="num big">{sc["summary"]["beat_pct"]}%</span>'
                f'<span class="lbl">beat SPY</span></div>')
    return (f'<div class="strip">'
            f'<div class="kpi" style="--c:{P["buy"]}">'
            f'<span class="num big">{len(groups["BUY"])}</span><span class="lbl">buy</span></div>'
            f'<div class="kpi" style="--c:{P["sell"]}">'
            f'<span class="num big">{len(groups["SELL"])}</span><span class="lbl">sell / avoid</span></div>'
            f'<div class="kpi" style="--c:{P["watch"]}">'
            f'<span class="num big">{len(groups["WATCH"])}</span><span class="lbl">watchlist</span></div>'
            f'{port}{beat}</div>')


def _momentum_section(momentum: list[dict] | None,
                      have: set | None = None) -> str:
    if not momentum:
        return ""
    have = have or set()
    mx = max(r["weight"] for r in momentum) or 1
    rows = ""
    for r in momentum:
        pct = int(100 * r["weight"] / mx)
        tks = ", ".join(
            (f'<a class="mtk" href="#c-{t}">{t}</a>' if t in have else t)
            for t in r["tickers"])
        rows += (f'<div class="mrow"><div class="mtop">'
                 f'<span class="mname">{html.escape(r["industry"])}</span>'
                 f'<span class="mut tiny">{r["buyers"]} distinct buyers \u00b7 '
                 f'{tks}</span></div>'
                 f'<div class="prog"><i style="width:{pct}%;'
                 f'background:var(--brand)"></i></div></div>')
    return ('<section><h2>Where insiders are herding</h2>'
            '<div class="panel">'
            '<p class="mut tiny" style="margin-bottom:.6rem">Industries with '
            'the heaviest unplanned insider cluster-buying this window \u2014 '
            'bottom-up trend detection from the people who know first.</p>'
            + rows + '</div></section>')


def build_portal(signals: list[dict], out_path: str,
                 tracked: list[dict] | None = None,
                 rejected: list[str] | None = None,
                 sc: dict | None = None,
                 banner: str | None = None,
                 momentum: list[dict] | None = None,
                 portfolio: float | None = None) -> None:
    today = dt.date.today().strftime("%A, %B %d, %Y")
    groups = {"BUY": [], "SELL": [], "WATCH": []}
    for s in signals:
        groups[s["call"]].append(s)
    sections = _summary_strip(groups, sc, portfolio)
    sections += _momentum_section(momentum,
                                  have={s["ticker"] for s in signals})
    if banner:
        sections += (f'<section><p class="banner">\u26a0 {html.escape(banner)}'
                     '</p></section>')
    sections += _tracking_section(tracked or [])
    titles = {"BUY": "Buy signals", "SELL": "Sell / avoid", "WATCH": "Watchlist"}
    for call in ("BUY", "SELL", "WATCH"):
        cards = "".join(_card(s) for s in groups[call]) or \
            '<p class="mut empty">No names met the threshold today. Sitting out is a position.</p>'
        sections += (f'<section><h2>{titles[call]} '
                     f'<span class="cnt">{len(groups[call])}</span></h2>'
                     f'<div class="grid">{cards}</div></section>')
    sections += _scorecard_section(sc)
    rej_note = (f' \u00b7 {len(rejected)} hidden by your not-interested list'
                if rejected else "")
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>InsiderEdge \u2014 {today}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--bg:{P['bg']};--card:{P['card']};--ink:{P['ink']};--mut:{P['mut']};
--line:{P['line']};--brand:{P['brand']};--buy:{P['buy']};--sell:{P['sell']};
--watch:{P['watch']}}}
@media (prefers-color-scheme:dark){{
:root{{--bg:#0E1F1A;--card:#163028;--ink:#E9F2EC;--mut:#93AC9F;
--line:#25443A;--brand:#4FC79E;--buy:#3BC48F;--sell:#F2848F;--watch:#E4B45C}}
.card,.kpi,.panel{{box-shadow:0 1px 2px rgba(0,0,0,.28),0 10px 28px rgba(0,0,0,.24)}}
body{{-webkit-font-smoothing:antialiased}}}}
*{{box-sizing:border-box;margin:0}}
body{{background:var(--bg);color:var(--ink);
font:15.5px/1.6 Nunito,system-ui,sans-serif;padding:1.1rem;
-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1060px;margin:0 auto}}
.masthead{{display:flex;align-items:center;gap:.8rem;padding:.4rem 0 1.1rem}}
.logo{{font:700 1.35rem 'Quicksand',sans-serif;letter-spacing:-.02em}}
.logo b{{color:var(--brand)}}
.date{{color:var(--mut);font-size:.85rem}}
.arch{{margin-left:auto;font-size:.82rem;font-weight:600;color:var(--brand);
text-decoration:none;background:color-mix(in srgb,var(--brand) 10%,var(--card));
padding:.4rem .8rem;border-radius:999px}}
.num{{font-family:'Quicksand',sans-serif;font-variant-numeric:tabular-nums}}
.strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
gap:.7rem;margin-bottom:1.4rem}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:20px;
padding:.85rem 1rem;display:flex;flex-direction:column;gap:.1rem;
box-shadow:0 1px 2px rgba(23,32,43,.05)}}
.kpi .big{{font-size:1.7rem;font-weight:700;color:var(--c)}}
.kpi .lbl{{color:var(--mut);font-size:.76rem;text-transform:uppercase;
letter-spacing:.07em;font-weight:600}}
section{{margin:0 0 1.8rem}}
h2{{font:700 1.02rem 'Quicksand',sans-serif;margin:0 0 .8rem;
letter-spacing:-.01em}}
.cnt{{color:var(--mut);font-weight:500;font-size:.9rem}}
.grid{{display:grid;gap:.9rem;grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:22px;
box-shadow:0 1px 2px rgba(23,32,43,.05),0 10px 28px rgba(23,32,43,.05);
overflow:hidden}}
.head{{display:flex;align-items:center;gap:.7rem;padding:.85rem 1rem;
background:color-mix(in srgb,var(--c) 7%,var(--card));
border-bottom:1px solid color-mix(in srgb,var(--c) 18%,var(--line))}}
.pill{{background:var(--c);color:#fff;font:700 .72rem Nunito;
padding:.28rem .65rem;border-radius:999px;white-space:nowrap}}
.title{{display:flex;flex-direction:column;min-width:0}}
.tk{{font:700 1.12rem 'Quicksand',sans-serif;letter-spacing:-.01em}}
.co{{color:var(--mut);font-size:.78rem;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}}
.net{{margin-left:auto;color:var(--mut);font-size:.82rem}}
.body{{padding:.95rem 1rem 1.05rem}}
.ind{{font-size:.78rem;margin-bottom:.35rem}}
.about{{font-size:.85rem;color:color-mix(in srgb,var(--ink) 82%,var(--mut));margin:.2rem 0 .65rem}}
.stats{{display:flex;gap:1.15rem;flex-wrap:wrap;margin:.4rem 0 .5rem}}
.stat{{display:flex;flex-direction:column;gap:.05rem}}
.lbl{{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;
color:var(--mut);font-weight:600}}
.val{{font-size:.98rem;font-weight:500}}
.up{{color:var(--buy)}}.dn{{color:var(--sell)}}
.spark{{width:100%;height:52px;margin:.25rem 0;display:block}}
.chips{{display:flex;gap:.45rem;flex-wrap:wrap}}
.chip{{font:700 .72rem Nunito;padding:.3rem .6rem;border-radius:999px}}
.chip-short{{background:color-mix(in srgb,var(--sell) 12%,var(--card));color:var(--sell)}}
.chip-earn{{background:color-mix(in srgb,var(--watch) 14%,var(--card));color:var(--watch)}}
.meta{{font-size:.8rem;margin:.45rem 0 .1rem}}
.mut{{color:var(--mut)}}
.tiny{{font-size:.73rem;margin-top:.3rem}}
.btns{{display:flex;gap:.5rem;margin:.7rem 0 .1rem;flex-wrap:wrap}}
.btn{{font:800 .84rem Nunito;text-decoration:none;padding:.55rem 1rem;
border-radius:14px;flex:1;text-align:center;min-width:96px}}
.bt-buy{{background:color-mix(in srgb,var(--buy) 13%,var(--card));color:var(--buy)}}
.bt-sell{{background:color-mix(in srgb,var(--sell) 12%,var(--card));color:var(--sell)}}
.bt-skip{{background:color-mix(in srgb,var(--mut) 12%,var(--card));color:var(--mut)}}
.bt-ask{{background:var(--brand);color:#fff}}
.browse-head{{margin-top:.55rem;text-transform:uppercase;letter-spacing:.07em;
font-size:.66rem;font-weight:700;list-style:none}}
.browse a{{font-weight:400;font-size:.8rem;color:var(--mut)}}
.chartpanel{{margin-bottom:1rem}}
.bigchart{{width:100%;height:auto;display:block}}
.legend{{display:flex;gap:.9rem;flex-wrap:wrap;margin-top:.5rem;font-size:.82rem}}
.lg{{display:inline-flex;align-items:center;gap:.35rem}}
.lg i{{width:10px;height:10px;border-radius:3px;display:inline-block}}
.chip-herd{{background:color-mix(in srgb,var(--brand) 9%,var(--card));
color:var(--brand);border:1px dashed color-mix(in srgb,var(--brand) 45%,var(--card))}}
.mtk{{color:var(--brand);font-weight:700;text-decoration:none}}
html{{scroll-behavior:smooth}}
.chip-theme{{background:color-mix(in srgb,var(--brand) 12%,var(--card));color:var(--brand)}}
.mrow{{margin:.55rem 0}}
.mtop{{display:flex;justify-content:space-between;gap:.8rem;align-items:baseline;flex-wrap:wrap}}
.mname{{font-weight:700;font-size:.9rem}}
.chip-fresh{{background:color-mix(in srgb,var(--buy) 13%,var(--card));color:var(--buy)}}
.chip-mid{{background:color-mix(in srgb,var(--watch) 14%,var(--card));color:var(--watch)}}
.chip-spent{{background:color-mix(in srgb,var(--mut) 14%,var(--card));color:var(--mut)}}
.chip-news{{background:color-mix(in srgb,var(--sell) 10%,var(--card));
color:var(--sell);border:1px dashed color-mix(in srgb,var(--sell) 45%,var(--card))}}
.btn:focus-visible,summary:focus-visible{{outline:2px solid var(--brand);
outline-offset:2px}}
details{{border-top:1px solid var(--line);margin-top:.7rem;padding-top:.6rem}}
summary{{cursor:pointer;font-size:.86rem;font-weight:600;color:var(--brand);
list-style:none;display:flex;align-items:center;gap:.4rem}}
summary::before{{content:"\u203a";display:inline-block;transition:transform .15s;
font-size:1rem;color:var(--mut)}}
details[open] summary::before{{transform:rotate(90deg)}}
.mono li{{font-family:'Quicksand',sans-serif;font-size:.76rem;margin:.3rem 0}}
.mono,.list{{margin:.5rem 0 0 1.15rem;font-size:.83rem;padding:0}}
.list li{{margin:.4rem 0}}
.list a{{color:var(--ink);font-weight:500}}
.empty{{padding:.4rem 0}}
.banner{{background:color-mix(in srgb,var(--watch) 12%,var(--card));
border:1px solid color-mix(in srgb,var(--watch) 40%,var(--card));border-radius:14px;
padding:.75rem 1rem;color:color-mix(in srgb,var(--watch) 70%,var(--ink));font-size:.88rem}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:22px;
padding:1rem 1.1rem;box-shadow:0 1px 2px rgba(23,32,43,.05)}}
.verdict{{font-size:.92rem;margin-bottom:.7rem}}
.tablewrap{{overflow-x:auto}}
.sc{{width:100%;border-collapse:collapse;font-size:.82rem}}
.sc th{{text-align:left;color:var(--mut);font-weight:600;font-size:.68rem;
text-transform:uppercase;letter-spacing:.07em;padding:.35rem .55rem;
border-bottom:1px solid var(--line)}}
.sc td{{padding:.42rem .55rem;border-bottom:1px solid var(--line)}}
.tkr{{font-weight:600}}
.prog{{height:6px;background:color-mix(in srgb,var(--mut) 12%,var(--card));border-radius:999px;margin:.2rem 0 .6rem;
overflow:hidden}}
.prog i{{display:block;height:100%;background:var(--c);border-radius:999px}}
.slim .body{{padding-top:.7rem}}
footer{{border-top:1px solid var(--line);padding-top:1rem;margin-top:1.5rem;
color:var(--mut);font-size:.76rem}}
@media (prefers-reduced-motion:no-preference){{
.card{{transition:box-shadow .18s,transform .18s}}
.card:hover{{box-shadow:0 2px 4px rgba(23,32,43,.06),0 16px 36px rgba(23,32,43,.09)}}}}
</style></head><body><div class="wrap">
<header class="masthead"><span class="logo">Insider<b>Edge</b></span>
<span class="date">{today}{rej_note}</span>
<a class="arch" href="archive/">Archive</a></header>
{sections}
<footer>Form 4 filings lag trades by up to 2 business days; congressional
disclosures by up to 45 days; 13D filings within 5 business days of crossing
5%. Political amounts are range midpoints. \u201cSince signal\u201d measures drift
after the earliest disclosed trade \u2014 a big positive number means the edge is
partly spent. Research tooling, not financial advice.</footer>
</div></body></html>"""
    with open(out_path, "w") as f:
        f.write(doc)
