# Full Focus — Amazon Advertising Analytics Project

Full Focus is an Amazon seller account. This project contains a browser-based analytics dashboard and the Python pipeline that builds its data from Amazon Advertising CSV exports.

## Project Structure

```
FullFocus/
├── index.html                          # Amazon Analytics Dashboard (open in browser)
├── dashboard-data.js                   # Generated data file — do not hand-edit
├── build_dashboard_data.py             # Python script that builds dashboard-data.js
└── FullFocus_SKU_Group_Mapping (1).xlsx  # SKU/ASIN → Product Name + Group mapping
```

## How to Rebuild the Dashboard Data

1. Download the latest Amazon Advertising CSV exports into `~/Downloads/`
2. Update the `FILES` list in `build_dashboard_data.py` if new files were added
3. Run:
   ```bash
   python3 "/Volumes/GISCH SSD/CLAUDE/FullFocus/build_dashboard_data.py"
   ```
4. Open `index.html` in a browser — it reads `dashboard-data.js` from the same folder

**Dependencies:** `openpyxl` (`pip install openpyxl`)

## Input CSV Files

Located in `~/Downloads/`. The `FILES` list in `build_dashboard_data.py` maps each file to its granularity:

| File | Granularity |
|------|-------------|
| `jan25.csv` | Monthly |
| `FullFocusAdsfeb-may25.csv` | Daily |
| `FullFocusAdsjun-aug25.csv` | Daily |
| `FullFocusAdssep-nov25_Copy.csv` | Daily |
| `FullFocusAdsDec25-feb26_Copy.csv` | Daily |
| `FullFocusAdsMar26.csv` | Daily |

When new monthly exports arrive, add them to `FILES` with `"monthly"` or `"daily"` as appropriate.

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
