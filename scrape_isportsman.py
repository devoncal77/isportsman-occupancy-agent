import os
import json
import time
from datetime import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

# CONFIG (do not hardcode secrets here—use env vars)
ISPORTS_URL = "https://westpoint.isportsman.net/Areas.aspx"
SHEET_ID = os.environ["SHEET_ID"]                      # set in GitHub Actions secrets
GOOGLE_SA_JSON = os.environ["GOOGLE_SA_JSON"]          # service account JSON (entire file as a string)
SHEET_TAB_NAME = os.environ.get("SHEET_TAB_NAME", "OccupancyLog")

def connect_sheet():
    sa_info = json.loads(GOOGLE_SA_JSON)
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=10)
        ws.append_row(["Timestamp_ET", "Area", "Occupancy", "Status"])
    return ws

def parse_table(page):
    """
    Robustly locate the Areas table with headers 'Area' and 'Occupancy'.
    Falls back to scanning all <table> tags.
    """
    tables = page.locator("table")
    row_data = []
    try:
        count = tables.count()
    except Exception:
        count = 0

    for i in range(count):
        tbl = tables.nth(i)
        headers = [h.inner_text().strip() for h in tbl.locator("thead tr th, tr th").all()]
        if not headers:
            first_row_cells = tbl.locator("tr").nth(0).locator("th, td").all()
            headers = [c.inner_text().strip() for c in first_row_cells]
        hdr_lc = [h.lower() for h in headers]

        if ("area" in hdr_lc) and ("occupancy" in hdr_lc):
            area_idx = hdr_lc.index("area")
            occ_idx = hdr_lc.index("occupancy")
            status_idx = hdr_lc.index("status") if "status" in hdr_lc else None

            rows = tbl.locator("tr")
            for r in range(1, rows.count()):  # skip header row
                cells = rows.nth(r).locator("th, td")
                if cells.count() <= max(area_idx, occ_idx):
                    continue
                area = cells.nth(area_idx).inner_text().strip()
                occ = cells.nth(occ_idx).inner_text().strip()
                status = cells.nth(status_idx).inner_text().strip() if status_idx is not None else ""
                if area:
                    row_data.append((area, occ, status))
            if row_data:
                return row_data

    return row_data  # empty means page structure changed

def main():
    # timestamp in ET
    et = pytz.timezone("America/New_York")
    ts = datetime.now(et).strftime("%Y-%m-%d %H:%M:%S")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(ISPORTS_URL, wait_until="networkidle", timeout=90000)
        time.sleep(3)  # extra settle time for client-side rendering
        data = parse_table(page)
        browser.close()

    if not data:
        raise RuntimeError("Could not locate the Areas/Occupancy table—site structure may have changed.")

    ws = connect_sheet()
    rows = [[ts, area, occ, status] for (area, occ, status) in data]
    ws.append_rows(rows, value_input_option="USER_ENTERED")

if __name__ == "__main__":
    main()
