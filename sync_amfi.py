import json
import urllib.request
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"
AMFI_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

def fetch_amfi_master():
    """Downloads and indexes AMFI NAV master file by ISIN directly."""
    print("Downloading AMFI master data from portal.amfiindia.com...")
    req = urllib.request.Request(
        AMFI_URL, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        content = resp.read().decode("utf-8", errors="ignore")

    lines = content.splitlines()
    nav_map = {}

    for line in lines:
        if not line or ";" not in line:
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 5:
            continue

        isin_growth = parts[1].upper() if len(parts) > 1 else ""
        isin_reinvest = parts[2].upper() if len(parts) > 2 else ""
        scheme_name = parts[3] if len(parts) > 3 else ""

        # Scan right-to-left before the date to grab the numeric NAV
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

    print(f"Indexed {len(nav_map)} active ISINs from AMFI.")
    return nav_map

def run_sync():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            portfolio = json.load(f)
    except Exception as e:
        print(f"Error loading {PORTFOLIO_FILE}: {e}")
        return

    nav_map = fetch_amfi_master()
    updated_count = 0

    for item in portfolio:
        isin = item.get("isin", "").strip().upper()
        if not isin:
            continue

        if isin in nav_map:
            latest_nav = nav_map[isin]["nav"]
            item["currentNav"] = latest_nav
            units = float(item.get("units", 0))
            buy_nav = float(item.get("buyNav", 0))

            item["investedCost"] = round(units * buy_nav, 2)
            item["valuation"] = round(units * latest_nav, 2)
            item["lastUpdated"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
            updated_count += 1
            print(f"Updated {item.get('name')}: NAV = {latest_nav}")
        else:
            print(f"ISIN {isin} not found in AMFI master file.")

    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)

    print(f"Sync complete. Successfully refreshed {updated_count} holdings.")

if __name__ == "__main__":
    run_sync()
