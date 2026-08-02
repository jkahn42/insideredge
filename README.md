# InsiderEdge v2

Tracks SEC Form 4 insider trades + congressional (STOCK Act) disclosures,
scores them, and every weekday morning: builds a web portal with company
info, prices, 14-day trends, and related legislation — then pings your
Telegram with the top calls and a link. Optional Alpaca execution
(paper by default). Zero pip dependencies — Python 3.10+ stdlib only.

## 10-minute setup (recommended path: GitHub Actions)

**1. Test locally first**
```bash
python3 main.py report --demo     # builds docs/index.html from sample data
```
Open `docs/index.html` in a browser — that's your portal.

**2. SEC identity (required for live data)**
Edit `insider_edge/config.py` -> put your real email in `SEC_USER_AGENT`.

**3. Telegram bot (3 min)**
- Message **@BotFather** -> `/newbot` -> copy the token.
- Send your new bot any message, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the
  `"chat":{"id": ...}` number.

**4. Congress.gov API key (2 min)**
Sign up free at https://api.congress.gov/sign-up — key arrives by email.
(Skip it and the portal still gives working congress.gov search links.)

**5. GitHub (5 min)**
- Create a repo, push this folder.
- Settings -> Pages -> Source: *Deploy from branch* -> `main` / `/docs`.
  Your portal URL becomes `https://<you>.github.io/<repo>/`.
- Settings -> Secrets and variables -> Actions ->
  **Secrets:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `CONGRESS_API_KEY`
  **Variables:** `PORTAL_URL` = your Pages URL.
- Actions tab -> "Daily InsiderEdge report" -> **Run workflow** to test.

Done. Every weekday ~7:30 AM ET: fresh portal + Telegram ping, laptop
open or not.

**Local-only alternative:** export the same env vars and cron
`python3 main.py report` — identical output, but only runs while your
machine is on.

## What the portal shows per stock

Company name and industry (SEC registry) - current price - price at the
earliest disclosed trade - **% since signal** (if it already ran, the edge
is partly spent — this number keeps you honest) - 14-day trend sparkline -
every disclosed trade with who/role/size/date - related bills and hearings
(Congress.gov keyword matches + direct search links).

## Trading

```bash
python3 main.py trade                                    # dry-run plan
export ALPACA_KEY_ID=... ALPACA_SECRET_KEY=...
python3 main.py trade --send                             # paper account
python3 main.py trade --live --i-understand-live --send  # real money
```
Guardrails always on: 10 positions max, 10% of equity per name, no
shorting. Run paper 60-90 days and beat SPY before going live.

## Scoring (moderate risk)

Insiders 60% / Congress 40%. Open-market P/S codes only (option exercises
and grants excluded as compensation noise). Role-weighted (CEO 2.0x),
log-scaled size, 21-day recency half-life, cluster bonuses. **BUY needs
score >=60 AND >=2 distinct buyers** — a lone whale only makes the watchlist.

## Known limitations — read before trusting it

1. **You trade behind the disclosers**: Form 4s lag <=2 business days,
   congressional filings <=45 days. The edge, if any, is cluster
   follow-through, not speed.
2. **Legislation matches are keyword correlation, not causation.** The
   portal says so on every card.
3. **House Stock Watcher mirror has update gaps**; bot warns and continues
   on Senate data. Quiver Quantitative API key is the paid fix.
4. Political amounts are **range midpoints** — estimates.
5. Scores normalize against the day's strongest signal; on quiet days,
   read the evidence lines before acting.
6. First live EDGAR pull is slow (30-60 min). After that, set
   `INSIDER_LOOKBACK_DAYS = 3` for fast daily runs.
7. Insider **sales** are noisy (10b5-1 scheduled plans); treat SELL as
   "avoid/trim," not panic. Insider *buys* are the quality signal.
8. Not financial advice; academic backtests of insider-following show
   modest, inconsistent alpha. Position sizing is your real risk control.
