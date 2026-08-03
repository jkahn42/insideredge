"""Telegram morning ping: top signals + link to the full portal.

Setup (3 minutes):
1. Message @BotFather on Telegram -> /newbot -> copy the token.
2. Message your new bot anything, then open
   https://api.telegram.org/bot<TOKEN>/getUpdates and copy "chat":{"id": ...}
3. export TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...  PORTAL_URL=...
"""
from __future__ import annotations
import json
import os
from urllib.request import Request, urlopen


def _fmt_line(s: dict) -> str:
    flag = " \u26a0" if s.get("news_flags") else ""
    px = f" @ ${s['price_now']:.2f}" if s.get("price_now") else ""
    move = (f" ({s['pct_since_signal']:+.1f}% since signal)"
            if s.get("pct_since_signal") is not None else "")
    return (f"<b>{s['call']}</b> {s['ticker']}{flag}{px}{move} — "
            f"net {s['net_score']:+.1f}, "
            f"{s['distinct_buyers']}B/{s['distinct_sellers']}S")


def send_daily_ping(signals: list[dict], date: str,
                    tracked: list[dict] | None = None) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    portal = os.environ.get("PORTAL_URL", "")
    if not token or not chat:
        print("[telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — skipping ping")
        return False
    top = [s for s in signals if s["call"] in ("BUY", "SELL")][:6]
    watch_n = sum(1 for s in signals if s["call"] == "WATCH")
    lines = [f"📊 <b>InsiderEdge — {date}</b>", ""]
    lines += [_fmt_line(s) for s in top] or ["No BUY/SELL calls today."]
    if watch_n:
        lines.append(f"👀 {watch_n} on the watchlist")
    movers = [t for t in (tracked or []) if t.get("pct") is not None]
    if movers:
        lines.append("")
        lines.append("<b>Your tracked names</b>")
        for t in sorted(movers, key=lambda x: -abs(x["pct"]))[:5]:
            tf = " \u26a0 " + ", ".join(t["news_flags"][:2]) if t.get("news_flags") else ""
            lines.append(f"{t['ticker']} day {t['day']}/{t['days_total']}: "
                         f"{t['pct']:+.1f}% since your {t['action']} call{tf}")
    if portal:
        fresh = f"{portal}{'&' if '?' in portal else '?'}d={date}"
        lines += ["", f'<a href="{fresh}">Open full report →</a>']
    body = {"chat_id": chat, "text": "\n".join(lines),
            "parse_mode": "HTML", "disable_web_page_preview": True}
    req = Request(f"https://api.telegram.org/bot{token}/sendMessage",
                  data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=20) as r:
            ok = json.loads(r.read().decode()).get("ok", False)
        print(f"[telegram] ping {'sent' if ok else 'FAILED'}")
        return ok
    except Exception as e:
        print(f"[telegram] error: {e}")
        return False
