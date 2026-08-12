# Full Focus — Amazon Advertising Analytics Project

Full Focus is an Amazon seller account. This project contains a browser-based analytics dashboard and the Python pipeline that builds its data from Amazon Advertising CSV exports.

## Project Structure

```
FullFocus/
├── index.html                          # Amazon Analytics Dashboard (open in browser)
├── dashboard-data.js                   # Generated data file — do not hand-edit
├── build_dashboard_data.py             # Python script that builds dashboard-data.js
├── FullFocus_SKU_Group_Mapping (1).xlsx  # SKU/ASIN → Product Name + Group mapping
│
├── scrape_bsr_ff.py                    # Scrapes BSR from Amazon category page
├── bsr_updater_ff.py                   # Patches bsr_data into dashboard-data.js
│
├── scrape_sov_ff.py                    # Scrapes SOV from Amazon SERP
├── sov_updater_ff.py                   # Patches sov_data into dashboard-data.js
│
├── scrape_price_ff.py                  # Scrapes listing prices for 5 tracked ASINs
├── price_updater_ff.py                 # Patches price_data into dashboard-data.js
├── price_tracking_automation.md        # Docs for the price tracking automation
│
├── run_daily_ff.sh                     # ACTIVE cron script (6:25am PT): runs price+BSR+SOV scrapes, then ONE combined GitHub push
├── run_price_ff.sh / run_bsr_ff.sh / run_sov_ff.sh   # DEPRECATED — no longer scheduled (see below), kept only as rollback reference
│
└── logs/                               # Per-run logs: daily_YYYY-MM-DD.log (current); bsr/sov/price_YYYY-MM-DD.log (old, pre-2026-07-06)
```

## Daily Cron Schedule (all PT)

**Updated 2026-07-06:** the three separate cron jobs below were consolidated into a single script, `run_daily_ff.sh`, because each separate push was triggering its own GitHub Pages deployment — when two landed close together, GitHub rejected the second with `Deployment failed, try again later` and that commit's data never went live. See `~/.claude/projects/-Users-gisch/memory/project_daily_dashboard_automation.md` for the full incident writeup.

| Time | Script | What it does |
|------|--------|-------------|
| 6:25am | `run_daily_ff.sh` (active) | Scrapes prices, BSR, and SOV in sequence, updates `dashboard-data.js` for each, then pushes **one** combined commit to GitHub |

~~6:25/6:30/6:35am separate price/BSR/SOV cron jobs~~ — replaced by the single job above. Do not re-add separate cron entries for `run_price_ff.sh` / `run_bsr_ff.sh` / `run_sov_ff.sh` — that reintroduces the deploy-collision bug.

## Monthly Data Ingest (runs every month)

This is the standard process for adding a new month of data. Raw CSV files are downloaded, ingested, then deleted — they are never stored long-term.

### Files the user provides each month

| File | Source | Notes |
|------|--------|-------|
| `FullFocus[Month]AdData.csv` | Amazon Advertising Console → Search Term report → Daily | e.g. `FullFocusMayAdData.csv` |
| `FullFocus[Month]TotalSales.csv` | Amazon Seller Central → Business Reports → Sales & Traffic by Child ASIN | e.g. `FullFocusMayTotalSales.csv` |

Both files land in `~/Downloads/`. Raw files are deleted by the user after ingest — do not save them.

### What to do each month (run inline Python — no saved script needed)

1. **Check what month is being added** — confirm the ads CSV contains rows for the target month only.
2. **Sum `Ordered Product Sales`** from the total sales CSV → this becomes `Shipped Revenue` in `time_series`.
3. **Run the inline incremental ingest** (see template below) — it reads `dashboard-data.js`, appends the new month's data to every array, and writes back.
4. **Append the month's NTB %** — add `{"Month_Period":"YYYY-MM","ntb_pct":NN.N}` to the `ntb_data` array (see "NTB % (new to brand)" below).
5. **Update `index.html` date defaults** — change the two `value="YYYY-MM-DD"` inputs (startDate / endDate) to the new month (e.g. `value="2026-05-01"` and `value="2026-05-31"`).
6. **Push both files to GitHub** — `dashboard-data.js` and `index.html`.

### NTB % (new to brand)

`ntb_data` holds one row per month: `{"Month_Period":"2026-07","ntb_pct":71.3}`. The value is
**Percent of sales new to brand** from the Amazon Advertising Console Performance chart (same
place the Total cost / CPC toggles live). It is not in the search-term CSV — read it per month
from the console, or from the monthly screenshot the user provides.

`index.html` merges `ntb_data` onto matching `time_series` rows as an `NTB %` field at page load,
which feeds two places:
- **Overview → Custom Trend Analysis** — `NTB (%)` metric option, Monthly view only (plots on the right axis; months with no value are gapped, not zeroed)
- **Annual Plan** — `NTB % Goal` (65%, constant `NTB_GOAL` in `renderAnnualPlanTable`) and `NTB % (Actual)` rows; the TOTAL column is weighted by ad sales, matching how Amazon aggregates the metric

**Seed values Jan–Jul 2026 were read off a chart image, not exported numbers** — they are
approximate (±1pt) except Jun (73.74%, from a tooltip). Replace any month with an exact figure
when one is available.

### Key ingest logic (same as build_dashboard_data.py)

- Parse dates from Amazon format: `"May 31, 2026"` → `"2026-05-31"`
- Product lookup: SKU first, then ASIN, then campaign-name fallback (`SB Video` / `SB Campaigns`)
- Strategy classification matches `classify_strategy()` in `build_dashboard_data.py`
- `search_term_data` keeps top-50 terms by lifetime spend (recalculated each ingest)
- **Monthly arrays** (`campaign_data`, `sku_data`, `asin_performance`, `time_series`, `ad_type_monthly`, `strategy_monthly`, `match_monthly`, `search_term_data`): strip any existing rows for the target Month_Period, then append new rows
- **Daily/weekly arrays** (`daily_series`, `weekly_series`, `daily_asin_series`, `weekly_asin_series`, `strategy_daily`, `strategy_weekly`): append new date-range rows (no stripping needed if month is new)
- **Lifetime arrays** (`strategy_by_group`, `match_by_group`, `campaign_by_group`, `dow_summary`): add the month's delta to existing values

### Shipped Revenue source

`Shipped Revenue` in `time_series` comes from the total sales CSV. Sum the `Ordered Product Sales` column across all ASIN rows for the month. `Shipped COGS` and `TACoS` remain 0 unless COGS data is separately provided.

### Data already ingested (historical)

All months through **2026-05** are in `dashboard-data.js`. Historical raw CSVs no longer exist — always use incremental ingest going forward, never a full rebuild.

| Period covered | Notes |
|----------------|-------|
| Jan 2025 | Monthly granularity |
| Feb–Dec 2025 | Daily granularity |
| Jan–May 2026 | Daily granularity; Jan–May have Shipped Revenue populated |

## Product Mapping

`FullFocus_SKU_Group_Mapping (1).xlsx` maps each SKU and ASIN to a human-readable **Product Name** and **Product Group**. The script looks up SKU first, then ASIN. Campaigns with no SKU/ASIN match are bucketed into `SB Video` or `SB Campaigns` based on campaign name patterns.

To add new products: add rows to the Excel file (columns: SKU, ASIN, Product Name, Product Group).

## Ad Strategy Classification

The script classifies campaigns into these strategies automatically from the campaign name:

| Strategy | Pattern |
|----------|---------|
| `Auto SP` | `SP-A`, `AUTO` in name |
| `Manual SP - COMP` | `COMPETITOR`, `OFFENSIVE`, `PT TO CATEGORY` |
| `Manual SP - NB` | `NON-BRANDED`, `NON-BRAND` |
| `Manual SP - BR` | `BRANDED`, `DEFENSIVE-PAT` |
| `SB - BR` | Sponsored Brands (branded) |
| `SB - NB` | Sponsored Brands with `NON-BRANDED`/`NON-BRAND` |
| `SB Video` | `SBV` or `VIDEO` in name |
| `SD` | Sponsored Display |

## Dashboard Data Arrays

`dashboard-data.js` exports a single `dashboardData` object with these arrays:

| Key | Description |
|-----|-------------|
| `campaign_data` | Per-campaign monthly rows |
| `sku_data` | Per-SKU monthly rows |
| `search_term_data` | Top 50 terms by lifetime spend, monthly |
| `asin_performance` | Monthly per-SKU with CAC |
| `time_series` | Monthly ad totals (ROAS, CAC, CTR) |
| `ntb_data` | Monthly % of sales new to brand — merged onto `time_series` as `NTB %` at load |
| `daily_series` / `weekly_series` | Daily/weekly ad totals |
| `daily_asin_series` / `weekly_asin_series` | Daily/weekly per-SKU |
| `ad_type_monthly` | SP / SB / SD breakdown by month |
| `strategy_monthly` / `strategy_daily` / `strategy_weekly` | By strategy |
| `match_monthly` | By match type (Exact/Phrase/Broad/PAT/Auto) |
| `strategy_by_group` / `match_by_group` | Lifetime cross-tabs |
| `dow_summary` | Day-of-week performance averages |

## Pushing Files Live to GitHub

The project is hosted at **GitHub repo: `jgisch17/full-focus`** (branch: `main`). Pushes go through the **GitHub Contents API** using a personal access token stored at:

```
/Volumes/GISCH SSD/CLAUDE/FullFocus/.github_token
```

**To push any file live (e.g. `index.html`):**

```bash
GITHUB_TOKEN=$(cat "/Volumes/GISCH SSD/CLAUDE/FullFocus/.github_token")
GITHUB_REPO="jgisch17/full-focus"
GITHUB_FILE="index.html"   # change per file
GITHUB_BRANCH="main"
API_URL="https://api.github.com/repos/$GITHUB_REPO/contents/$GITHUB_FILE"

# 1. Get current SHA (required by API to update existing file)
SHA=$(curl -s -H "Authorization: token $GITHUB_TOKEN" "$API_URL?ref=$GITHUB_BRANCH" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))")

# 2. Build payload (base64-encode the file)
python3 -c "
import base64, json
with open('/Volumes/GISCH SSD/CLAUDE/FullFocus/$GITHUB_FILE', 'rb') as f:
    content = base64.b64encode(f.read()).decode()
payload = {'message': 'Your commit message here', 'content': content, 'sha': '$SHA', 'branch': '$GITHUB_BRANCH'}
print(json.dumps(payload))
" > /tmp/ff_github_payload.json

# 3. Push
curl -s -o /tmp/ff_github_response.json -w "%{http_code}" \
    -X PUT "$API_URL" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    --data @/tmp/ff_github_payload.json
```

HTTP 200 = updated, 201 = created. The same token is shared with the Stargazer project.

## Important Notes

- `dashboard-data.js` is generated — always rebuild via `build_dashboard_data.py`, never edit manually
- `Shipped COGS` and `Shipped Revenue` in `time_series` are currently `0` — populate from business data when available
- The search term table is capped at the top 50 terms by lifetime spend to keep file size manageable
- No web server needed; `index.html` loads `dashboard-data.js` from the same directory

## Superpowers & Skills

Always use the Skill tool for the following before reporting work complete:

| Situation | Skill to invoke |
|-----------|----------------|
| After any data ingest or dashboard update | `verify` — spin up `python3 -m http.server 8765` from the project dir, open `http://localhost:8765/index.html` in GStack Browser, enter the password, and confirm all key metrics match expected values before pushing to GitHub |
| Bugs or unexpected data | `investigate` |
| Reviewing code/script changes | `review` |
| Pushing live | confirm via `verify` first |

**Dashboard password:** ask the user — do not store in this file.
**Key rule:** never push to GitHub and declare "done" without first running `verify` to confirm the live dashboard shows accurate data.
