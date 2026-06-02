import json
import os
import re
import time
from datetime import datetime

import gspread
import pytz
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright


# CONFIG (do not hardcode secrets here - use env vars)
ISPORTS_URL = "https://westpoint.isportsman.net/Areas.aspx"
SHEET_ID = os.environ["SHEET_ID"]                      # set in GitHub Actions secrets
GOOGLE_SA_JSON = os.environ["GOOGLE_SA_JSON"]          # service account JSON as a string
SHEET_TAB_NAME = os.environ.get("SHEET_TAB_NAME", "OccupancyLog")
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "artifacts")


def log(message):
    print(f"[isportsman] {message}", flush=True)


def normalize_header(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def clean_occupancy(value):
    match = re.search(r"\d+", value or "")
    return match.group(0) if match else (value or "").strip()


def connect_sheet():
    sa_info = json.loads(GOOGLE_SA_JSON)
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        log(f"Creating worksheet {SHEET_TAB_NAME!r}")
        ws = sh.add_worksheet(title=SHEET_TAB_NAME, rows=1000, cols=10)
        ws.append_row(["Timestamp_ET", "Area", "Occupancy", "Status"])
    return ws


def parse_table(page):
    """
    Locate the Areas table by headers so small layout changes do not break the run.
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

        normalized_headers = [normalize_header(h) for h in headers]
        if "area" not in normalized_headers or "occupancy" not in normalized_headers:
            continue

        area_idx = normalized_headers.index("area")
        occ_idx = normalized_headers.index("occupancy")
        status_idx = normalized_headers.index("status") if "status" in normalized_headers else None
        log(f"Found occupancy table at index {i} with headers: {headers}")

        rows = tbl.locator("tr")
        for r in range(1, rows.count()):
            cells = rows.nth(r).locator("th, td")
            if cells.count() <= max(area_idx, occ_idx):
                continue

            area = cells.nth(area_idx).inner_text().strip()
            occ = clean_occupancy(cells.nth(occ_idx).inner_text().strip())
            status = cells.nth(status_idx).inner_text().strip() if status_idx is not None else ""
            if area:
                row_data.append((area, occ, status))

        if row_data:
            return row_data

    return row_data


def save_failure_artifacts(page):
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    html_path = os.path.join(ARTIFACT_DIR, "areas_page.html")
    screenshot_path = os.path.join(ARTIFACT_DIR, "areas_page.png")

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        page.screenshot(path=screenshot_path, full_page=True)
        log(f"Saved debug artifacts to {ARTIFACT_DIR}")
    except Exception as exc:
        log(f"Could not save debug artifacts: {exc}")


def scrape_occupancy():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        try:
            for attempt in range(1, 4):
                log(f"Loading page, attempt {attempt}/3")
                page.goto(ISPORTS_URL, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(3)
                data = parse_table(page)
                if data:
                    return data
                log("No occupancy rows found yet; retrying")

            save_failure_artifacts(page)
            raise RuntimeError("Could not locate the Areas/Occupancy table - site structure may have changed.")
        finally:
            browser.close()


def main():
    et = pytz.timezone("America/New_York")
    ts = datetime.now(et).strftime("%Y-%m-%d %H:%M:%S")
    log(f"Starting scrape for {ISPORTS_URL} at {ts} ET")

    data = scrape_occupancy()
    log(f"Parsed {len(data)} occupancy rows")

    ws = connect_sheet()
    rows = [[ts, area, occ, status] for (area, occ, status) in data]
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    log(f"Appended {len(rows)} rows to {SHEET_TAB_NAME!r}")


if __name__ == "__main__":
    main()
