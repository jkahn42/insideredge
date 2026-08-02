"""Central configuration. Tuned for MODERATE risk profile."""

# --- Data windows ---
INSIDER_LOOKBACK_DAYS = 3      # Form 4 filings arrive within 2 business days of trade
CONGRESS_LOOKBACK_DAYS = 60     # STOCK Act allows up to 45-day disclosure lag

# --- Signal weights (must sum to 1.0) ---
WEIGHT_INSIDER = 0.6
WEIGHT_CONGRESS = 0.4

# Role weights: an officer buying with their own money is a stronger signal
ROLE_WEIGHTS = {
    "CEO": 2.0, "CFO": 1.8, "COO": 1.5, "PRESIDENT": 1.8,
    "OFFICER": 1.3, "ACTIVIST": 2.2, "DIRECTOR": 1.0, "10% OWNER": 0.8, "OTHER": 0.7,
}

# --- Moderate-risk thresholds (0-100 normalized scores) ---
BUY_SCORE_MIN = 60
BUY_MIN_DISTINCT_BUYERS = 2     # cluster requirement: never chase a lone buyer
WATCH_SCORE_MIN = 35
SELL_SCORE_MIN = 60
CLUSTER_BONUS = 1.35            # multiplier when >=3 distinct insiders buy same ticker
CONGRESS_CLUSTER_BONUS = 1.25   # >=2 politicians, same ticker, same direction

# Recency decay: half-life in days (older disclosures matter less)
RECENCY_HALF_LIFE_DAYS = 21

# Ignore trivial trades (noise floor)
MIN_INSIDER_TRADE_USD = 25_000
MIN_CONGRESS_TRADE_USD = 15_000

# --- Trading guardrails (apply to dry-run AND live) ---
MAX_POSITIONS = 10
MAX_PCT_PER_POSITION = 0.10     # 10% of equity max per name
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"

# --- Data source URLs ---
SEC_DAILY_INDEX = "https://www.sec.gov/Archives/edgar/daily-index"
SEC_USER_AGENT = "InsiderEdge research bot jkahn@jk-legalconsulting.com"  # SEC REQUIRES a real contact
SENATE_WATCHER_URL = (
    "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/aggregate/all_transactions.json"
)
HOUSE_WATCHER_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com"
    "/data/all_transactions.json"
)
QUIVER_API_KEY = None  # optional: set to use Quiver Quantitative congress endpoint

# --- v3 additions ---
TRACK_DAYS = 21                     # follow a tracked name this many days
NOMINAL_13D_VALUE = 1_000_000       # 13D has no dollar size; presence signal
GITHUB_REPO_FALLBACK = ""           # "owner/repo" for local runs (buttons)

# --- SHORT candidate (aggressive tier, display-only; never auto-traded) ---
SHORT_SELL_SCORE_MIN = 80
SHORT_MIN_SELLERS = 3
SHORT_MIN_EXEC_SELLERS = 2       # unplanned C-suite sellers required
PLANNED_SALE_DISCOUNT = 0.4      # 10b5-1 scheduled sales carry less signal
EXEC_ROLES = {"CEO", "CFO", "COO", "PRESIDENT", "OFFICER"}
