"""
Build dashboard-data.js for Full Focus dashboard.
Run: python3 build_dashboard_data.py
Add more CSV files to FILES list as new data arrives.
When business/sales data is ready, populate Shipped COGS/Revenue in time_series.
"""

import csv, json, openpyxl
from datetime import datetime, timedelta
from collections import defaultdict

# ── CONFIG ─────────────────────────────────────────────────────────────────
FILES = [
    ("/Users/gisch/Downloads/jan25.csv",                          "monthly"),
    ("/Users/gisch/Downloads/FullFocusAdsfeb-may25.csv",          "daily"),
    ("/Users/gisch/Downloads/FullFocusAdsjun-aug25.csv",          "daily"),
    ("/Users/gisch/Downloads/FullFocusAdssep-nov25_Copy.csv",     "daily"),
    ("/Users/gisch/Downloads/FullFocusAdsDec25-feb26_Copy.csv",   "daily"),
    ("/Users/gisch/Downloads/FullFocusAdsMar26.csv",              "daily"),
]
MAPPING_FILE = "/Volumes/GISCH SSD/CLAUDE/fullfocus/FullFocus_SKU_Group_Mapping (1).xlsx"
OUTPUT_FILE  = "/Volumes/GISCH SSD/CLAUDE/fullfocus/dashboard-data.js"

DAY_NAMES = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# ── PRODUCT MAPPING ─────────────────────────────────────────────────────────
wb = openpyxl.load_workbook(MAPPING_FILE)
ws = wb.active
sku_lookup  = {}   # sku  → (product_name, group)
asin_lookup = {}   # asin → (product_name, group)
for row in ws.iter_rows(min_row=2, values_only=True):
    if not row[0]: continue
    sku   = str(row[0]).strip()
    asin  = str(row[1]).strip() if row[1] else ""
    name  = str(row[2]).strip() if row[2] else sku
    group = str(row[3]).strip() if row[3] else "Other"
    sku_lookup[sku] = (name, group)
    if asin:
        asin_lookup[asin] = (name, group)

def get_product_info(sku, asin="", campaign=""):
    if sku  and sku  in sku_lookup:  return sku_lookup[sku]
    if asin and asin in asin_lookup: return asin_lookup[asin]
    # No product attribution — classify by campaign type
    nm = campaign.upper()
    group = "SB Video" if ("SBV" in nm or "VIDEO" in nm) else "SB Campaigns"
    return (group, group)

# ── HELPERS ─────────────────────────────────────────────────────────────────
def pf(v):
    try:
        return float(str(v).replace(",","").replace("%","").strip() or 0)
    except: return 0.0

def parse_date(s):
    try:
        return datetime.strptime(s.strip().strip('"'), "%b %d, %Y").strftime("%Y-%m-%d")
    except: return None

def week_monday(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
    except: return None

def classify_strategy(ad_product, campaign):
    ap, nm = (ad_product or "").strip(), campaign.upper()
    if ap == "Sponsored Display":  return "SD"
    if ap == "Sponsored Brands":
        return "SB - NB" if ("NON-BRANDED" in nm or "NON-BRAND" in nm) else "SB - BR"
    # Sponsored Products
    if "SP-A " in nm or "SP-A|" in nm or " AUTO " in nm or "SP AUTO" in nm or "AUTO -" in nm:
        return "Auto SP"
    if "COMPETITOR" in nm or "OFFENSIVE" in nm or "PT TO CATEGORY" in nm:
        return "Manual SP - COMP"
    if "NON-BRANDED" in nm or "NON-BRAND" in nm or "NON BRAND" in nm:
        return "Manual SP - NB"
    if "BRANDED" in nm:
        return "Manual SP - BR"
    if "DEFENSIVE-PAT" in nm:
        return "Manual SP - BR"
    return "Manual SP - NB"

def classify_match(tmt):
    return {"PHRASE":"Phrase","EXACT":"Exact","BROAD":"Broad",
            "TARGETING_EXPRESSION":"PAT","TARGETING_EXPRESSION_PREDEFINED":"Auto",
            "THEME":"Theme"}.get((tmt or "").upper().strip(), "Other")

def classify_ad_type(ap):
    return {"Sponsored Products":"SP","Sponsored Brands":"SB","Sponsored Display":"SD"}.get(ap, ap or "Unknown")

def r2(v): return round(float(v), 2)

# ── ACCUMULATORS ─────────────────────────────────────────────────────────────
def dd_metrics():  return defaultdict(lambda: {"Total cost":0,"Sales":0,"Purchases":0,"Clicks":0,"Impressions":0})
def dd_small():    return defaultdict(lambda: {"Total cost":0,"Sales":0,"Purchases":0})
def dd_series():   return defaultdict(lambda: {"spend":0,"sales":0,"purchases":0,"impressions":0,"clicks":0})
def dd_asin_s():   return defaultdict(lambda: {"spend":0,"sales":0,"purchases":0})

camp_monthly   = dd_metrics()    # month_period
camp_detail    = dd_metrics()    # (month_period, campaign_name, group)
sku_monthly    = dd_metrics()    # (month, sku, name, group)
term_monthly   = dd_metrics()    # (month, term, sku, group)
ts_monthly     = dd_metrics()    # month_period
ts_daily       = dd_series()     # date
ts_weekly      = dd_series()     # week_monday
asin_daily_d   = dd_asin_s()     # (date, sku, group)
asin_weekly_d  = dd_asin_s()     # (week, sku, group)
adtype_mon     = dd_metrics()    # (month, ad_type)
strat_mon      = dd_metrics()    # (month, strategy)
strat_daily_d  = dd_small()      # (date, strategy)
strat_weekly_d = dd_small()      # (week, strategy)
match_mon      = dd_small()      # (month, match_type)
strat_grp      = dd_metrics()    # (strategy, group)
match_grp      = dd_small()      # (match_type, group)
camp_grp       = dd_metrics()    # (strategy, group)
dow_d          = defaultdict(lambda: {"spend":0,"sales":0,"purchases":0,"clicks":0,"dates":set()})

# ── PROCESS FILES ────────────────────────────────────────────────────────────
total_rows = 0
for filepath, ftype in FILES:
    print(f"Reading {filepath.split('/')[-1]} ...")
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku      = (row.get("Advertised product SKU") or "").strip()
            asin     = (row.get("Advertised product ID")  or "").strip()
            ap       = (row.get("Ad product")             or "").strip()
            camp     = (row.get("Campaign name")          or "").strip()
            tmt      = (row.get("Target match type")      or "").strip()
            term     = (row.get("Search term")            or "").strip()

            spend     = pf(row.get("Total cost"))
            sales     = pf(row.get("Sales"))
            purchases = pf(row.get("Purchases"))
            clicks    = pf(row.get("Clicks"))
            impressions = pf(row.get("Impressions"))

            if spend == 0 and sales == 0 and purchases == 0 and impressions == 0:
                continue

            pname, pgroup = get_product_info(sku, asin, camp)
            strategy  = classify_strategy(ap, camp)
            match_type = classify_match(tmt)
            ad_type   = classify_ad_type(ap)

            # Date
            if ftype == "monthly":
                mo = int(row.get("Month", 0) or 0)
                yr = int(row.get("Year",  0) or 0)
                if not mo or not yr: continue
                month_period = f"{yr:04d}-{mo:02d}"
                date_str = None
                week_str = None
            else:
                date_str = parse_date(row.get("Date") or "")
                if not date_str: continue
                month_period = date_str[:7]
                week_str = week_monday(date_str)

            # Monthly accumulators
            def add(d, k):
                d[k]["Total cost"]  += spend
                d[k]["Sales"]       += sales
                d[k]["Purchases"]   += purchases
                d[k]["Clicks"]      += clicks
                d[k]["Impressions"] += impressions

            add(camp_monthly,  month_period)
            add(camp_detail,   (month_period, camp, pgroup))
            add(sku_monthly,   (month_period, sku, pname, pgroup))
            add(ts_monthly,    month_period)
            add(adtype_mon,    (month_period, ad_type))
            add(strat_mon,     (month_period, strategy))
            add(strat_grp,     (strategy, pgroup))
            add(camp_grp,      (strategy, pgroup))

            match_mon[(month_period, match_type)]["Total cost"] += spend
            match_mon[(month_period, match_type)]["Sales"]      += sales
            match_mon[(month_period, match_type)]["Purchases"]  += purchases

            match_grp[(match_type, pgroup)]["Total cost"] += spend
            match_grp[(match_type, pgroup)]["Sales"]      += sales
            match_grp[(match_type, pgroup)]["Purchases"]  += purchases

            if term and (spend > 0 or sales > 0 or purchases > 0):
                term_monthly[(month_period, term, sku, pgroup)]["Total cost"]  += spend
                term_monthly[(month_period, term, sku, pgroup)]["Sales"]       += sales
                term_monthly[(month_period, term, sku, pgroup)]["Purchases"]   += purchases
                term_monthly[(month_period, term, sku, pgroup)]["Clicks"]      += clicks
                term_monthly[(month_period, term, sku, pgroup)]["Impressions"] += impressions

            # Daily / weekly accumulators
            if ftype == "daily" and date_str:
                ts_daily[date_str]["spend"]       += spend
                ts_daily[date_str]["sales"]        += sales
                ts_daily[date_str]["purchases"]    += purchases
                ts_daily[date_str]["impressions"]  += impressions
                ts_daily[date_str]["clicks"]       += clicks

                if week_str:
                    ts_weekly[week_str]["spend"]      += spend
                    ts_weekly[week_str]["sales"]       += sales
                    ts_weekly[week_str]["purchases"]   += purchases
                    ts_weekly[week_str]["impressions"] += impressions
                    ts_weekly[week_str]["clicks"]      += clicks

                asin_daily_d[(date_str, sku, pgroup)]["spend"]     += spend
                asin_daily_d[(date_str, sku, pgroup)]["sales"]      += sales
                asin_daily_d[(date_str, sku, pgroup)]["purchases"]  += purchases

                if week_str:
                    asin_weekly_d[(week_str, sku, pgroup)]["spend"]     += spend
                    asin_weekly_d[(week_str, sku, pgroup)]["sales"]      += sales
                    asin_weekly_d[(week_str, sku, pgroup)]["purchases"]  += purchases

                strat_daily_d[(date_str, strategy)]["Total cost"] += spend
                strat_daily_d[(date_str, strategy)]["Sales"]      += sales
                strat_daily_d[(date_str, strategy)]["Purchases"]  += purchases

                if week_str:
                    strat_weekly_d[(week_str, strategy)]["Total cost"] += spend
                    strat_weekly_d[(week_str, strategy)]["Sales"]      += sales
                    strat_weekly_d[(week_str, strategy)]["Purchases"]  += purchases

                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    day = DAY_NAMES[dt.weekday()]
                    dow_d[day]["spend"]     += spend
                    dow_d[day]["sales"]      += sales
                    dow_d[day]["purchases"]  += purchases
                    dow_d[day]["clicks"]     += clicks
                    dow_d[day]["dates"].add(date_str)
                except: pass

            total_rows += 1

print(f"Processed {total_rows:,} rows\n")

# ── BUILD OUTPUT ARRAYS ──────────────────────────────────────────────────────
def safe_roas(sales, cost): return r2(sales / cost) if cost > 0 else 0
def safe_cac(cost, purch):  return r2(cost / purch) if purch > 0 else 0

# campaign_data — per-campaign monthly rows (enables campaign table + date filtering)
campaign_data = sorted([
    {"Month_Period": mp, "Campaign name": camp_name, "Product Group": pgroup,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Clicks": int(d["Clicks"]),
     "Impressions": int(d["Impressions"])}
    for (mp, camp_name, pgroup), d in camp_detail.items()
], key=lambda x: (x["Month_Period"], x["Campaign name"]))

# sku_data
sku_data = sorted([
    {"Month_Period": mp, "Advertised product SKU": sku, "Product Name": pname,
     "Product Group": pgroup, "Total cost": r2(d["Total cost"]),
     "Sales": r2(d["Sales"]), "Purchases": int(d["Purchases"]),
     "Clicks": int(d["Clicks"]), "Impressions": int(d["Impressions"])}
    for (mp, sku, pname, pgroup), d in sku_monthly.items()
], key=lambda x: (x["Month_Period"], x["Advertised product SKU"]))

# search_term_data — top 100 terms by lifetime spend, then monthly rows for those terms only
term_lifetime = {}
for (mp, term, sku, pgroup), d in term_monthly.items():
    if term not in term_lifetime:
        term_lifetime[term] = 0
    term_lifetime[term] += d["Total cost"]
top_500_terms = set(sorted(term_lifetime, key=lambda t: -term_lifetime[t])[:100])

search_term_data = sorted([
    {"Month_Period": mp, "Search term": term, "Advertised product SKU": sku,
     "Product Group": pgroup, "Total cost": r2(d["Total cost"]),
     "Sales": r2(d["Sales"]), "Purchases": int(d["Purchases"]),
     "Clicks": int(d["Clicks"]), "Impressions": int(d["Impressions"])}
    for (mp, term, sku, pgroup), d in term_monthly.items()
    if term in top_500_terms and (d["Total cost"] > 0 or d["Sales"] > 0 or d["Purchases"] > 0)
], key=lambda x: -x["Sales"])

# asin_performance — monthly by SKU (same grain as sku_data + CAC)
asin_performance = sorted([
    {"Month_Period": mp, "Advertised product SKU": sku, "Product Name": pname,
     "Product Group": pgroup, "Total cost": r2(d["Total cost"]),
     "Sales": r2(d["Sales"]), "Purchases": int(d["Purchases"]),
     "CAC": safe_cac(d["Total cost"], d["Purchases"])}
    for (mp, sku, pname, pgroup), d in sku_monthly.items()
], key=lambda x: (x["Month_Period"], x["Advertised product SKU"]))

# time_series — monthly ad totals (Shipped COGS/Revenue added when biz data arrives)
time_series = sorted([
    {"Month_Period": mp,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Impressions": int(d["Impressions"]),
     "Clicks": int(d["Clicks"]),
     "ROAS": safe_roas(d["Sales"], d["Total cost"]),
     "CAC":  safe_cac(d["Total cost"], d["Purchases"]),
     "CTR":  r2(d["Clicks"] / d["Impressions"] * 100) if d["Impressions"] > 0 else 0,
     "Shipped COGS": 0, "Shipped Revenue": 0, "TACoS": 0}
    for mp, d in ts_monthly.items()
], key=lambda x: x["Month_Period"])

# daily_series
daily_series = [
    {"date": dt, "spend": r2(d["spend"]), "sales": r2(d["sales"]),
     "purchases": int(d["purchases"]), "impressions": int(d["impressions"]),
     "clicks": int(d["clicks"])}
    for dt, d in sorted(ts_daily.items())
]

# weekly_series
weekly_series = [
    {"week": wk, "spend": r2(d["spend"]), "sales": r2(d["sales"]),
     "purchases": int(d["purchases"]), "impressions": int(d["impressions"]),
     "clicks": int(d["clicks"])}
    for wk, d in sorted(ts_weekly.items())
]

# daily_asin_series (only rows with activity)
daily_asin_series = [
    {"date": dt, "sku": sku, "Product Group": pg,
     "spend": r2(d["spend"]), "sales": r2(d["sales"]),
     "purchases": int(d["purchases"]),
     "CAC": safe_cac(d["spend"], d["purchases"])}
    for (dt, sku, pg), d in sorted(asin_daily_d.items())
    if d["spend"] > 0 or d["sales"] > 0
]

# weekly_asin_series
weekly_asin_series = [
    {"week": wk, "sku": sku, "Product Group": pg,
     "spend": r2(d["spend"]), "sales": r2(d["sales"]),
     "purchases": int(d["purchases"]),
     "CAC": safe_cac(d["spend"], d["purchases"])}
    for (wk, sku, pg), d in sorted(asin_weekly_d.items())
    if d["spend"] > 0 or d["sales"] > 0
]

# ad_type_monthly
ad_type_monthly = sorted([
    {"Month_Period": mp, "ad_type": at,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Impressions": int(d["Impressions"]),
     "Clicks": int(d["Clicks"]), "ROAS": safe_roas(d["Sales"], d["Total cost"])}
    for (mp, at), d in adtype_mon.items()
], key=lambda x: (x["Month_Period"], x["ad_type"]))

# strategy_monthly
strategy_monthly = sorted([
    {"Month_Period": mp, "strategy": st,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Impressions": int(d["Impressions"]),
     "Clicks": int(d["Clicks"]), "ROAS": safe_roas(d["Sales"], d["Total cost"])}
    for (mp, st), d in strat_mon.items()
], key=lambda x: (x["Month_Period"], x["strategy"]))

# strategy_daily
strategy_daily = [
    {"DateStr": dt, "strategy": st,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]),
     "ROAS": safe_roas(d["Sales"], d["Total cost"])}
    for (dt, st), d in sorted(strat_daily_d.items())
]

# strategy_weekly
strategy_weekly = [
    {"Week": wk, "strategy": st,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]),
     "ROAS": safe_roas(d["Sales"], d["Total cost"])}
    for (wk, st), d in sorted(strat_weekly_d.items())
]

# match_monthly
match_monthly = sorted([
    {"Month_Period": mp, "match_type_clean": mt,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "ROAS": safe_roas(d["Sales"], d["Total cost"])}
    for (mp, mt), d in match_mon.items()
], key=lambda x: (x["Month_Period"], x["match_type_clean"]))

# strategy_by_group — lifetime totals
strategy_by_group = sorted([
    {"strategy": st, "Product Group": pg,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Clicks": int(d["Clicks"]),
     "Impressions": int(d["Impressions"])}
    for (st, pg), d in strat_grp.items()
], key=lambda x: (x["strategy"], x["Product Group"]))

# match_by_group — lifetime totals
match_by_group = sorted([
    {"match_type_clean": mt, "Product Group": pg,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"])}
    for (mt, pg), d in match_grp.items()
], key=lambda x: (x["match_type_clean"], x["Product Group"]))

# campaign_by_group — lifetime totals (same grain as strategy_by_group)
campaign_by_group = sorted([
    {"strategy": st, "Product Group": pg,
     "Total cost": r2(d["Total cost"]), "Sales": r2(d["Sales"]),
     "Purchases": int(d["Purchases"]), "Clicks": int(d["Clicks"]),
     "Impressions": int(d["Impressions"])}
    for (st, pg), d in camp_grp.items()
], key=lambda x: (x["strategy"], x["Product Group"]))

# dow_summary
dow_summary = []
for day in DAY_NAMES:
    if day not in dow_d: continue
    d = dow_d[day]
    nd = len(d["dates"])
    if nd == 0: continue
    dow_summary.append({
        "day": day, "spend": r2(d["spend"]), "sales": r2(d["sales"]),
        "purchases": int(d["purchases"]), "clicks": int(d["clicks"]),
        "avg_spend": r2(d["spend"] / nd), "avg_sales": r2(d["sales"] / nd),
        "cpc":  r2(d["spend"] / d["clicks"])    if d["clicks"]    > 0 else 0,
        "roas": r2(d["sales"] / d["spend"])      if d["spend"]     > 0 else 0,
        "cac":  r2(d["spend"] / d["purchases"])  if d["purchases"] > 0 else 0,
        "num_days": nd, "groups": []
    })

# ── ASSEMBLE & WRITE ─────────────────────────────────────────────────────────
dashboard_data = {
    "campaign_data":    campaign_data,
    "sku_data":         sku_data,
    "search_term_data": search_term_data,
    "asin_performance": asin_performance,
    "time_series":      time_series,
    "daily_series":     daily_series,
    "weekly_series":    weekly_series,
    "daily_asin_series":  daily_asin_series,
    "weekly_asin_series": weekly_asin_series,
    "ad_type_monthly":  ad_type_monthly,
    "strategy_monthly": strategy_monthly,
    "strategy_daily":   strategy_daily,
    "strategy_weekly":  strategy_weekly,
    "match_monthly":    match_monthly,
    "strategy_by_group": strategy_by_group,
    "match_by_group":   match_by_group,
    "campaign_by_group": campaign_by_group,
    "dow_summary":      dow_summary,
}

print("Array sizes:")
for k, v in dashboard_data.items():
    print(f"  {k:<25} {len(v):>7,} rows")

js = "const dashboardData = " + json.dumps(dashboard_data, separators=(",",":")) + ";\n"
with open(OUTPUT_FILE, "w") as f:
    f.write(js)

size_mb = len(js.encode()) / 1024 / 1024
print(f"\nFile size: {size_mb:.1f} MB")
print(f"Saved to: {OUTPUT_FILE}")
