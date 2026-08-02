"""Generate the daily report (markdown + machine-readable JSON)."""
from __future__ import annotations
import json
import datetime as dt


def build_report(results: list[dict], out_md: str, out_json: str) -> str:
    today = dt.date.today().isoformat()
    buys = [r for r in results if r["call"] == "BUY"]
    sells = [r for r in results if r["call"] == "SELL"]
    watch = [r for r in results if r["call"] == "WATCH"]

    lines = [f"# InsiderEdge Daily Report — {today}", ""]
    lines.append(f"Signals: **{len(buys)} BUY** / **{len(sells)} SELL** / "
                 f"**{len(watch)} WATCH**")
    lines.append("")

    def section(title: str, rows: list[dict]):
        lines.append(f"## {title}")
        if not rows:
            lines.append("_None today — no cluster met the threshold. "
                         "That is a feature, not a bug._")
            lines.append("")
            return
        for r in rows:
            lines.append(
                f"### {r['ticker']}  (net {r['net_score']:+.1f} | "
                f"buy {r['buy_score']} / sell {r['sell_score']} | "
                f"{r['distinct_buyers']} buyers, {r['distinct_sellers']} sellers)")
            for ev in r["evidence"]:
                lines.append(f"- {ev}")
            lines.append("")

    section("BUY", buys)
    section("SELL / AVOID", sells)
    section("WATCHLIST", watch)

    lines += [
        "---",
        "**Read this every day:** Form 4s lag trades by up to 2 business days; "
        "congressional disclosures lag by up to 45 days. Amounts on political "
        "trades are range midpoints (estimates). Insider signals are one input, "
        "not a guarantee — position sizing and diversification are your risk "
        "controls. This is research tooling, not financial advice.",
    ]
    md = "\n".join(lines)
    with open(out_md, "w") as f:
        f.write(md)
    with open(out_json, "w") as f:
        json.dump({"date": today, "signals": results}, f, indent=2)
    return md
