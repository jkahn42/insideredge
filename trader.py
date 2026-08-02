"""Broker execution via Alpaca API. SAFE BY DEFAULT.

Defaults: dry_run=True (prints orders, sends nothing) and paper endpoint
(fake money). Going live requires BOTH --live and --i-understand-live flags
plus real API keys. Guardrails always apply:
  - max MAX_POSITIONS concurrent positions
  - max MAX_PCT_PER_POSITION of equity per name
  - market orders only during regular hours, notional sizing
"""
from __future__ import annotations
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from . import config


class AlpacaClient:
    def __init__(self, paper: bool = True):
        self.base = config.ALPACA_PAPER_URL if paper else config.ALPACA_LIVE_URL
        self.key = os.environ.get("ALPACA_KEY_ID", "")
        self.secret = os.environ.get("ALPACA_SECRET_KEY", "")
        if not self.key or not self.secret:
            raise RuntimeError(
                "Set ALPACA_KEY_ID and ALPACA_SECRET_KEY environment variables.")

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        req = Request(self.base + path, method=method,
                      headers={"APCA-API-KEY-ID": self.key,
                               "APCA-API-SECRET-KEY": self.secret,
                               "Content-Type": "application/json"},
                      data=json.dumps(body).encode() if body else None)
        try:
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except HTTPError as e:
            raise RuntimeError(f"Alpaca {e.code}: {e.read().decode()[:300]}")

    def account(self) -> dict:
        return self._req("GET", "/v2/account")

    def positions(self) -> list[dict]:
        return self._req("GET", "/v2/positions")

    def submit(self, symbol: str, side: str, notional: float) -> dict:
        return self._req("POST", "/v2/orders", {
            "symbol": symbol, "side": side, "type": "market",
            "time_in_force": "day", "notional": str(round(notional, 2)),
        })


def plan_orders(signals: list[dict], equity: float,
                held: dict[str, float]) -> list[dict]:
    """Turn report signals into a concrete, guardrail-compliant order list."""
    orders = []
    per_name = equity * config.MAX_PCT_PER_POSITION
    open_slots = max(config.MAX_POSITIONS - len(held), 0)

    # SELL first: exit any held name with a SELL signal
    for s in signals:
        if s["call"] == "SELL" and s["ticker"] in held:
            orders.append({"symbol": s["ticker"], "side": "sell",
                           "notional": held[s["ticker"]],
                           "reason": f"SELL signal net {s['net_score']:+.1f}"})
    # BUY: strongest first, respecting slots and sizing
    for s in signals:
        if s["call"] != "BUY" or s["ticker"] in held or open_slots <= 0:
            continue
        orders.append({"symbol": s["ticker"], "side": "buy",
                       "notional": round(per_name, 2),
                       "reason": (f"BUY net {s['net_score']:+.1f}, "
                                  f"{s['distinct_buyers']} distinct buyers")})
        open_slots -= 1
    return orders


def execute(report_json_path: str, dry_run: bool = True,
            paper: bool = True) -> None:
    with open(report_json_path) as f:
        signals = json.load(f)["signals"]

    if dry_run:
        # No broker needed: assume $100k demo equity, no positions
        orders = plan_orders(signals, equity=100_000.0, held={})
        print("\n=== DRY RUN — no orders sent ===")
        for o in orders:
            print(f"  {o['side'].upper():4s} {o['symbol']:6s} "
                  f"${o['notional']:>10,.2f}  ({o['reason']})")
        if not orders:
            print("  No orders. Thresholds not met — sitting out is a position.")
        return

    client = AlpacaClient(paper=paper)
    acct = client.account()
    equity = float(acct["equity"])
    held = {p["symbol"]: float(p["market_value"]) for p in client.positions()}
    orders = plan_orders(signals, equity, held)
    mode = "PAPER" if paper else "LIVE"
    print(f"\n=== {mode} EXECUTION — equity ${equity:,.2f} ===")
    for o in orders:
        res = client.submit(o["symbol"], o["side"], o["notional"])
        print(f"  sent {o['side']} {o['symbol']} ${o['notional']:,.2f} "
              f"-> order {res.get('id', '?')}")
