import json
import os
import urllib.request
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"

# Realistic browser headers to bypass server-side bot blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

def fetch_amfi_master():
    """Downloads official AMFI NAV master text file."""
    url = "https://portal.amfiindia.com/spages/NAVAll.txt"
    print("Fetching official AMFI master list...")
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

        # Find numeric NAV from right to left before the date column
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

    print(f"Indexed {len(nav_map)} active schemes by ISIN from AMFI.")
    return nav_map

def fetch_fallback_scheme_catalog():
    """Fallback: Maps ISIN to scheme code using MFAPI catalog if AMFI text times out."""
    print("Fetching backup scheme catalog...")
    req = urllib.request.Request("https://api.mfapi.in/mf", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        catalog = json.loads(resp.read().decode("utf-8"))
    
    isin_to_code = {}
    for item in catalog:
        code = str(item.get("schemeCode"))
        if item.get("isinGrowth"):
            isin_to_code[item["isinGrowth"].upper()] = code
        if item.get("isinDivReinvestment"):
            isin_to_code[item["isinDivReinvestment"].upper()] = code
    return isin_to_code

def fetch_nav_by_code(scheme_code):
    """Fetches latest NAV for a specific AMFI code via JSON."""
    url = f"https://api.mfapi.in/mf/{scheme_code}/latest"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("data") and len(data["data"]) > 0:
            return float(data["data"][0]["nav"])
    return None

def run():
    # 1. Initialize portfolio.json if not present
    if not os.path.exists(PORTFOLIO_FILE):
        print("portfolio.json not found. Initializing starter template...")
        starter = [
            {
                "id": "mf_1",
                "category": "Mutual Fund",
                "planType": "Direct - Growth",
                "name": "Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
                "isin": "INF879O01027",
                "identifier": "12345678",
                "owner": "Self",
                "units": 500.0,
                "buyNav": 45.20,
                "currentNav": 45.20,
                "investedCost": 22600.0,
                "valuation": 22600.0,
                "lastUpdated": ""
            }
        ]
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(starter, f, indent=2)

    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        portfolio = json.load(f)

    # 2. Try fetching primary AMFI master
    nav_map = {}
    try:
        nav_map = fetch_amfi_master()
    except Exception as e:
        print(f"Warning: Primary AMFI download failed ({e}). Switching to secondary resolver...")

    # 3. Fallback catalog if AMFI master failed
    backup_catalog = {}
    if not nav_map:
        try:
            backup_catalog = fetch_fallback_scheme_catalog()
        except Exception as e:
            print(f"Error fetching secondary catalog: {e}")

    updated = 0
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

    for item in portfolio:
        isin = item.get("isin", "").strip().upper()
        if not isin:
            continue

        latest_nav = None

        # Check primary map
        if isin in nav_map:
            latest_nav = nav_map[isin]["nav"]
        # Check secondary map
        elif isin in backup_catalog:
            code = backup_catalog[isin]
            latest_nav = fetch_nav_by_code(code)

        if latest_nav is not None:
            units = float(item.get("units", 0))
            buy_nav = float(item.get("buyNav", 0))
            item["currentNav"] = latest_nav
            item["investedCost"] = round(units * buy_nav, 2)
            item["valuation"] = round(units * latest_nav, 2)
            item["lastUpdated"] = now_str
            updated += 1
            print(f"Updated {item.get('name')}: NAV = {latest_nav}")
        else:
            print(f"Skipping {item.get('name')}: No NAV found for ISIN {isin}")

    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)

    print(f"Execution complete. Updated {updated} holdings.")

if __name__ == "__main__":
    run()
