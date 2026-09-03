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
├── scrape_sov_ff.py                    # Scrapes SOV from Amazon SERP for every keyword in its KEYWORDS list
├── sov_updater_ff.py                   # Patches sov_data into dashboard-data.js (all keywords)
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

## Share of Voice (SOV) Tracking

### Tracked keywords

`scrape_sov_ff.py` has a `KEYWORDS` list — the single source of truth for what gets scraped:

| Keyword | Status | Since |
|---------|--------|-------|
| `full focus planner` | active | 2026-09-03 |
| `michael hyatt` | active | 2026-09-03 |
| `daily planner` | **retired** — history kept, no new points | tracked 2026-05-08 → 2026-09-03 |

To add a keyword: append it to `KEYWORDS` in `scrape_sov_ff.py`. The updater creates its
`sov_data` entry automatically, backfilled with empty slots, and the dashboard's keyword
dropdown picks it up with no HTML change.

To retire a keyword: remove it from `KEYWORDS`, add it to `RETIRED_KEYWORDS` in
`sov_updater_ff.py`, and add it to `SOV_RETIRED` in `index.html` (which appends the
"(paused)" label and sorts it below the active keywords).

### Data shape and the alignment rule

`sov_data` is `{"dates": [...], "keywords": [{keyword, organic_positions, paid_positions,
organic_total, paid_total, organic_sov, paid_sov, total_sov, organic_asins, paid_asins}]}`.

**`dates` is one array shared by every keyword entry.** Every per-keyword array must stay
exactly `len(dates)` long, so appending a date means appending a slot to EVERY keyword —
including retired keywords and keywords whose scrape failed that day (they get an empty
slot: `[]` / `0` / `null`). Skip that padding and the arrays drift out of alignment with the
date axis, and every chart silently misplots against the wrong dates. `sov_updater_ff.py`
enforces this: it realigns short arrays on load and aborts without writing if any array
length mismatches after the update.

SOV % is always "Full Focus's share of that page" — the same `FF_ASINS` set is used for
every keyword.

### Partial success and re-runs

`scrape_sov_ff.py` scrapes each keyword in one browser session, spaced 20-40s apart, and
returns `{"<keyword>": {"organic": [...], "paid": [...]} | null}`. A keyword that fails all
3 retries comes back `null`; the keywords that succeeded are still recorded. The scraper
exits non-zero only when EVERY keyword failed.

If today's date is already in `dates` (e.g. the morning cron ran, or a keyword is being
re-run after a partial scrape), the updater **fills the existing slot in place** rather than
appending a duplicate date. A keyword that already has data for today is left untouched.

### Known failure mode

Amazon soft-blocks the `/s` search endpoint (HTTP 503, "Sorry! Something went wrong!") far
more aggressively than the `/dp` and `/gp/bestsellers` endpoints price/BSR use. When
`sov-scrape` is the ONLY failure in the daily run, `run_daily_ff.sh` suppresses the alert
email and logs `"sov-only failure — alert suppressed"`. It still alerts if SOV fails
alongside price/BSR/push, which would suggest a broader block. Do not "fix" the scraper in
response to an isolated SOV failure — confirm the 503 signature first.

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

`ntb_data` holds one row per month: `{"Month_Period":"2026-08","ntb_pct":68.7}`.

**The value is the Sponsored Brands NTB sales rate — and it IS computable from the search-term
CSV** (discovered 2026-09-02, correcting the earlier "not in the CSV, read it off the console"
note). The export carries `Sales (new to brand)` and `Purchases (new to brand)` columns, but
**Amazon only populates them on Sponsored Brands rows** — SP and SD rows are always blank. So:

```
ntb_pct = sum(Sales (new to brand)) / sum(Sales)   over rows where Ad product == "Sponsored Brands"
```

Aug 2026 checks out at 68.70%, squarely inside the 57.7–73.7% band of the chart-read Jan–Jul
seeds, whereas the account-wide figure (NTB sales / *all* sales) is only 10.69% — an order of
magnitude off. That gap is what identifies the console's Performance chart metric as the
SB-only rate. Compute it during ingest; no screenshot needed.

`index.html` merges `ntb_data` onto matching `time_series` rows as an `NTB %` field at page load,
which feeds two places:
- **Overview → Custom Trend Analysis** — `NTB (%)` metric option, Monthly view only (plots on the right axis; months with no value are gapped, not zeroed)
- **Annual Plan** — `NTB % Goal` (65%, constant `NTB_GOAL` in `renderAnnualPlanTable`) and `NTB % (Actual)` rows; the TOTAL column is weighted by ad sales, matching how Amazon aggregates the metric

**Jan–Jul 2026 were read off a chart image and remain approximate (±1pt)** except Jun (73.74%,
from a tooltip). Aug 2026 onward are exact CSV-derived figures. If a raw ads CSV for any Jan–Jul
month ever resurfaces, recompute that month with the formula above and overwrite the seed.

> **Do not confuse `ntb_data` with `incrementality_data`'s `ntb_pct`.** They are different
> metrics from different exports. `incrementality_data` comes from a campaign-level export whose
> NTB columns are populated across SP *and* SB (Aug branded ntb_sales alone exceeds the entire
> SB-only NTB sales for the month), so it cannot be rebuilt from the search-term CSV.

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

Data covers **Jan 2025 through 2026-08**. Historical raw CSVs no longer exist — always use
incremental ingest, never a full rebuild. This table goes stale fast; trust the live
`time_series` array's last `Month_Period` over anything written here.

| Period covered | Notes |
|----------------|-------|
| Jan 2025 | Monthly granularity |
| Feb–Dec 2025 | Daily granularity, no Shipped Revenue |
| Jan–Aug 2026 | Daily granularity; Shipped Revenue populated |

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
| `incrementality_data` | Monthly NTB %, CAC, ROAS split Branded vs Non-Branded — powers the Incrementality Trends tab |
| `daily_series` / `weekly_series` | Daily/weekly ad totals |
| `daily_asin_series` / `weekly_asin_series` | Daily/weekly per-SKU |
| `ad_type_monthly` | SP / SB / SD breakdown by month |
| `strategy_monthly` / `strategy_daily` / `strategy_weekly` | By strategy |
| `match_monthly` | By match type (Exact/Phrase/Broad/PAT/Auto) |
| `strategy_by_group` / `match_by_group` | Lifetime cross-tabs |
| `dow_summary` | Day-of-week performance averages |

## Incrementality Trends Tab

The **🚀 Incrementality Trends** tab (`index.html` → `<div id="incrementality">`, rendered by
`renderIncrementalityTab()`) shows NTB %, CAC and ROAS by month, split Branded vs Non-Branded.
It reads `incrementality_data` in `dashboard-data.js` and **ignores the sidebar date filter** —
it always shows its own full range, because the sidebar defaults to a single month.

**This array does NOT update from the normal monthly ingest.** It was built from a separate
campaign-level export (columns: `report_month, campaign_id_string, campaign, spend, sales,
ntb_sales, ntb_sales_pct, roas, cpc, cac, clicks, ntb_purchases, total_purchases`). Current
coverage: **2025-12 through 2026-08** (Aug flagged `"partial": true`). To add a month, re-run
the same aggregation over a fresh export and append two rows (one per targeting group).

### Metric definitions (re-aggregated from raw counts, never averaged)

| Metric | Formula |
|--------|---------|
| NTB %  | `sum(ntb_sales) / sum(sales) * 100` |
| CAC    | `sum(spend) / sum(ntb_purchases)` |
| ROAS   | `sum(sales) / sum(spend)` |

### Branded vs Non-Branded split (from campaign name, in this order)

1. `NON-BRANDED` / `NON-BRAND` in the name, or `NB` as a delimited token → **Non-Branded**
2. `BRANDED` in the name, or `BR` as a delimited token → **Branded**
3. `DEFENSIVE` → **Branded**
4. `AUTO` or `SP-A` → **Non-Branded** (all auto campaigns count as non-branded)
5. `OFFENSIVE` / `COMPETITOR` / `CATEGORY` → **Non-Branded**
6. Anything left over → **Branded** — this only catches the three unlabeled Sponsored Display
   remarketing/awareness campaigns (~2% of spend), which retarget people already exposed to
   the brand. Revisit this fallback if new unlabeled campaigns appear.

Rows carry a `"partial"` flag for in-progress months; the tab marks those with `*` in the table,
dashes the trailing chart segment, and notes it in the footnote.

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

- `dashboard-data.js` is generated — never hand-edit. Do **not** re-run `build_dashboard_data.py` either; it is a full-rebuild script and the historical raw CSVs are gone. Use the incremental inline ingest above.
- `Shipped COGS` and `TACoS` in `time_series` are still `0`; `Shipped Revenue` is populated from the monthly total-sales CSV
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
