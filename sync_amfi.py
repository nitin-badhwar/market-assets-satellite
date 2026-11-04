import json
import os
import urllib.request
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def fetch_amfi_master():
    url = "https://portal.amfiindia.com/spages/NAVAll.txt"
    print("Connecting to portal.amfiindia.com...")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8", errors="ignore")

    nav_map = {}
    for line in content.splitlines():
        if not line or ";" not in line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 5:
            continue

        isin_growth = parts[1].upper() if len(parts) > 1 else ""
        isin_reinvest = parts[2].upper() if len(parts) > 2 else ""
        scheme_name = parts[3] if len(parts) > 3 else ""

        nav = None
        for i in range(len(parts) - 2, 2, -1):
            try:
                nav = float(parts[i])
                break
            except ValueError:
                continue

        if nav is not None:
            entry = {"name": scheme_name, "nav": nav}
            if isin_growth and isin_growth != "-":
                nav_map[isin_growth] = entry
            if isin_reinvest and isin_reinvest != "-":
                nav_map[isin_reinvest] = entry

    print(f"Loaded {len(nav_map)} active scheme ISINs from AMFI.")
    return nav_map

def fetch_fallback_catalog():
    print("Falling back to secondary catalog...")
    req = urllib.request.Request("https://api.mfapi.in/mf", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        catalog = json.loads(resp.read().decode("utf-8"))
    
    isin_map = {}
    for item in catalog:
        code = str(item.get("schemeCode"))
        if item.get("isinGrowth"):
            isin_map[item["isinGrowth"].upper()] = code
        if item.get("isinDivReinvestment"):
            isin_map[item["isinDivReinvestment"].upper()] = code
    return isin_map

def fetch_nav_by_code(code):
    url = f"https://api.mfapi.in/mf/{code}/latest"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("data") and len(data["data"]) > 0:
            return float(data["data"][0]["nav"])
    return None

def run():
    if not os.path.exists(PORTFOLIO_FILE):
        print("portfolio.json not found.")
        return

    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            portfolio = json.load(f)
    except Exception as e:
        print(f"Error reading {PORTFOLIO_FILE}: {e}")
        return

    nav_map = {}
    try:
        nav_map = fetch_amfi_master()
    except Exception as e:
        print(f"AMFI primary download failed: {e}")

    backup_catalog = {}
    if not nav_map:
        try:
            backup_catalog = fetch_fallback_catalog()
        except Exception as e:
            print(f"Backup catalog failed: {e}")

    updated = 0
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

    for item in portfolio:
        isin = item.get("isin", "").strip().upper()
        if not isin:
            continue

        latest_nav = None
        if isin in nav_map:
            latest_nav = nav_map[isin]["nav"]
        elif isin in backup_catalog:
            try:
                latest_nav = fetch_nav_by_code(backup_catalog[isin])
            except Exception as e:
                print(f"Failed to fetch NAV for {isin}: {e}")

        if latest_nav is not None:
            units = float(item.get("units", 0))
            buy_nav = float(item.get("buyNav", 0))
            old_nav = float(item.get("currentNav") or buy_nav)

            # Preserve yesterday's closing rate if NAV has updated
            if latest_nav != old_nav:
                item["previousNav"] = old_nav
            elif "previousNav" not in item:
                item["previousNav"] = old_nav

            item["currentNav"] = latest_nav
            item["investedCost"] = round(units * buy_nav, 2)
            item["valuation"] = round(units * latest_nav, 2)
            item["lastUpdated"] = now_str
            updated += 1
            print(f"Updated {item.get('name')}: NAV = {latest_nav} (Prev: {item.get('previousNav')})")

    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)

    print(f"Execution complete. Updated {updated} holdings.")

if __name__ == "__main__":
    run()
