# InsiderEdge — Novice Setup Guide (no coding, no command line)

Good news: **you never run Python yourself.** GitHub (a free website) runs
the code in the cloud every morning. Your entire setup happens in a web
browser, tapping and pasting. Budget ~25 minutes once, then it's automatic
forever.

What you're building: GitHub stores the code and runs it each weekday →
it publishes your report as a web page → Telegram messages you the link.

---

## Part 1 — Telegram bot (5 min, on your phone)

1. Open Telegram, search for **@BotFather** (blue checkmark), tap Start.
2. Send the message: `/newbot`
3. It asks for a name — type anything, e.g. `My InsiderEdge`.
4. It asks for a username — must end in "bot", e.g. `myinsideredge_bot`.
5. BotFather replies with a **token** that looks like
   `7123456789:AAHxxxxxxxxxxxxxxxx`. **Copy it somewhere safe.**
6. Tap the link to your new bot and send it any message ("hi").
7. In your phone's web browser, go to (paste your real token in):
   `https://api.telegram.org/bot<YOUR-TOKEN>/getUpdates`
8. You'll see text on screen. Find `"chat":{"id":` followed by a number
   like `6234567890`. **Copy that number.** That's your Chat ID.

You now have 2 things saved: **token** and **chat id**.

## Part 2 — Congress.gov key (2 min)

1. Go to **api.congress.gov/sign-up** — enter name + email, submit.
2. The key arrives by email. **Copy it.** (3 things saved now.)

## Part 3 — GitHub account + upload the code (8 min, easier on a computer)

1. Go to **github.com** → Sign up (free) → verify your email.
2. Top-right **+** button → **New repository**.
3. Repository name: `insideredge`. Keep it **Public** (this makes the
   daily automation and web page free; note the report page will be
   viewable by anyone who has the link — it only contains public data).
4. Check the box **"Add a README file"** → green **Create repository**.
5. Unzip `insider_edge_v2.zip` on your computer.
6. On your repository page: **Add file → Upload files**. Drag in
   **everything inside** the unzipped `insider_edge` folder (the
   `insider_edge` code folder, `sample_data`, `docs`, `main.py`,
   `README.md`, the report files). Green **Commit changes** button.
   - If `.github` didn't upload (it's a hidden folder — common), don't
     worry: Part 5 creates it by hand in 1 minute.

## Part 4 — Put your email in the code (1 min)

The SEC requires a contact email on data requests.

1. In your repository, click the `insider_edge` folder → `config.py`.
2. Click the **pencil icon** (top right of the file) to edit.
3. Find the line with `SEC_USER_AGENT` and replace
   `yourname@example.com` with your real email.
4. While you're here: change `INSIDER_LOOKBACK_DAYS = 14` to `= 3`
   (makes daily runs fast).
5. Green **Commit changes** button.

## Part 5 — The automation file (2 min)

1. Repository home → **Add file → Create new file**.
2. In the filename box type exactly:
   `.github/workflows/daily.yml`
   (typing the `/` characters automatically creates the folders)
3. Paste the entire contents of the `daily.yml` file from your unzipped
   download (open it with Notepad/TextEdit to copy). If it's already in
   your repo from Part 3, skip this step.
4. Green **Commit changes**.

## Part 6 — Give GitHub your 3 secret keys (3 min)

1. Repository → **Settings** tab → left menu:
   **Secrets and variables → Actions**.
2. Green **New repository secret** button. Add these three, one at a time
   (Name must match EXACTLY, paste the value, Add secret):
   - Name: `TELEGRAM_BOT_TOKEN` → value: your token from Part 1
   - Name: `TELEGRAM_CHAT_ID` → value: your chat id number
   - Name: `CONGRESS_API_KEY` → value: your key from Part 2

## Part 7 — Turn on your web page (2 min)

1. Still in **Settings** → left menu: **Pages**.
2. Under "Build and deployment": Source = **Deploy from a branch**,
   Branch = **main**, folder = **/docs** → **Save**.
3. Wait ~1 minute, refresh — a box appears: "Your site is live at
   `https://YOURNAME.github.io/insideredge/`". **Copy that URL.**
4. Back to **Settings → Secrets and variables → Actions** → click the
   **Variables** tab → **New repository variable**:
   - Name: `PORTAL_URL` → value: the URL you just copied.

## Part 8 — Test it (2 min)

1. Click the **Actions** tab. If it asks to enable workflows, enable them.
2. Left side: click **Daily InsiderEdge report** → right side:
   **Run workflow** button → green **Run workflow**.
3. Watch it run (yellow dot → green check). First run takes a while —
   it's downloading SEC filings. Get coffee.
4. When it's green: check Telegram — your bot messaged you. Tap the link.
   That's your portal. From now on it happens automatically every
   weekday morning.

---

## If something goes wrong

- **Red X on the run:** click into it, click the failed step — the error
  text is at the bottom. Copy it and paste it to Claude; I'll tell you
  the fix.
- **No Telegram message but green run:** secret names must match exactly
  (all caps, underscores). Re-check Part 6.
- **Page shows 404:** Pages can take 5 minutes after the first run.
  Also confirm Part 7 selected `/docs`.

## What you do each morning (the whole routine)

1. Telegram pings you: top BUY/SELL calls with prices.
2. Tap the link → read the evidence, prices, and legislation for each.
3. Decide. The bot proposes; you dispose. Nothing trades automatically
   unless you deliberately set up Alpaca later — leave that off for now.

---

## Using the Buy / Sell / Not-interested buttons (v3)

Each stock card now has three buttons:
- **I'll buy** / **I'll sell** — tap it, a pre-filled GitHub note opens,
  tap the green **Submit new issue** button. Done. Tomorrow morning that
  stock appears in a new **"Your tracked decisions"** section at the top
  of your portal, showing the price on your decision day, today's price,
  and % change — updated daily for 21 days, then it retires itself.
  Your Telegram ping also includes your biggest tracked movers.
- **Not interested** — same one-tap flow; that ticker is hidden from all
  future reports permanently (it's remembered in a file in your repo —
  delete the ticker from `tracking_state.json` if you change your mind).

Tip: stay logged into GitHub on your phone browser and the whole flow is
two taps per decision.
