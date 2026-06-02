# iSportsman Occupancy Agent

This project records West Point iSportsman area occupancy twice daily and publishes a simple dashboard from the collected data.

## What It Does

The GitHub Actions workflow:

1. Opens `https://westpoint.isportsman.net/Areas.aspx` in headless Chromium.
2. Finds the table with `Area`, `Occupancy`, and optional `Status` columns.
3. Appends rows to a Google Sheet tab named `OccupancyLog`.
4. Builds a static Plotly dashboard from the sheet.
5. Publishes the dashboard to the `gh-pages` branch.

Rows are appended with this schema:

```text
Timestamp_ET | Area | Occupancy | Status
```

## Schedule

The intended local run times are:

```text
12:00 and 16:00 America/New_York
```

GitHub Actions schedules run in UTC, so the workflow runs at the UTC hours that can map to those local times during standard time or daylight saving time:

```yaml
0 16,17,20,21 * * *
```

A schedule gate inside the workflow checks the actual `America/New_York` hour and only continues when the local hour is `12` or `16`. Manual `workflow_dispatch` runs always continue.

## Required Secrets

Configure these in GitHub under **Settings -> Secrets and variables -> Actions**:

| Secret | Purpose |
| --- | --- |
| `SHEET_ID` | Target Google Sheet ID |
| `GOOGLE_SA_JSON` | Full Google service-account JSON key |

Share the target Google Sheet with the service account email as an Editor.

## Files

| File | Purpose |
| --- | --- |
| `scrape_isportsman.py` | Playwright scraper and Google Sheets writer |
| `build_dashboard.py` | Static dashboard and CSV export builder |
| `requirements.txt` | Python dependencies |
| `.github/workflows/schedule.yml` | Scheduled runner and GitHub Pages publisher |

## Manual Run

1. Open the repository on GitHub.
2. Go to **Actions -> iSportsman Occupancy Logger**.
3. Select **Run workflow**.
4. Check the run logs for parsed row counts.
5. Open the Google Sheet or GitHub Pages dashboard to verify the new data.

## Dashboard Outputs

The dashboard build publishes:

| File | Purpose |
| --- | --- |
| `index.html` | Main dashboard |
| `avg_by_area.csv` | Average occupancy by area |
| `latest_snapshot.csv` | Most recent scrape only |
| `occupancy_log_export.csv` | Full cleaned export from the sheet |

## Troubleshooting

### Could not locate the Areas/Occupancy table

The site may be down or the table markup may have changed. The scraper retries three times. If it still fails, the workflow uploads debug artifacts for 14 days:

```text
artifacts/areas_page.html
artifacts/areas_page.png
```

Use those files to update `parse_table()` in `scrape_isportsman.py`.

### Permission denied from Google Sheets

Confirm:

- `SHEET_ID` points to the correct Google Sheet.
- The service account email has Editor access.
- `GOOGLE_SA_JSON` contains the entire unmodified JSON key.

### Workflow runs at the wrong local time

The workflow should only continue at 12:00 or 16:00 `America/New_York`. Check the **Check target run time** step logs; it prints the detected local time and whether the run continued.

### Action succeeds but no rows appear

Confirm:

- You are checking the `OccupancyLog` tab, or the tab set in `SHEET_TAB_NAME`.
- The scrape step log reports a nonzero parsed row count.
- The target sheet is the one referenced by `SHEET_ID`.

## Maintenance

- Rotate the Google service-account key periodically.
- Keep Playwright reasonably current in `requirements.txt`.
- Review debug artifacts when the site layout changes.
- Keep the README and workflow schedule comments in sync when changing run times.
