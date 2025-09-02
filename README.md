Awesome—here’s a clean “Agent Instructions” package you can **copy-paste into a `README.md`** in your repo. It tells exactly how the agent runs, what it logs, how to verify it, and how to tweak/maintain it.

---

# iSportsman Occupancy Agent — Runbook

## What this agent does

Twice daily at **12:00 and 16:00 America/New\_York**, a GitHub Actions workflow:

1. Opens `https://westpoint.isportsman.net/Areas.aspx` in a headless Chromium browser.
2. Scrapes the table with columns **Area**, **Occupancy**, and (if present) **Status**.
3. Appends rows to your Google Sheet tab **`OccupancyLog`** with:

```
Timestamp_ET | Area | Occupancy | Status
```

---

## Schedule (cron)

The workflow uses UTC cron:

```
0 16,20 * * *
```

That equals **12:00 and 16:00 ET** (handles DST automatically).
To change times, convert ET → UTC and edit `.github/workflows/schedule.yml`.

---

## One-time configuration (already done)

* Secrets in **Settings → Secrets and variables → Actions**:

  * `SHEET_ID` = `1ifqiCcyoCT922IKKhQcP6fovDNyltleVtmAv2uk5-bA`
  * `GOOGLE_SA_JSON` = entire contents of your Google service-account JSON key
* Share the target Google Sheet with the **service account email** (Editor).

---

## Files in this repo

* `scrape_isportsman.py` — Playwright scraper + Google Sheets writer
* `requirements.txt` — Python deps
* `.github/workflows/schedule.yml` — Scheduled runner (GitHub Actions)

---

## How to run it now (manual test)

1. Go to **Actions** tab → **iSportsman Occupancy Logger** → **Run workflow**.
2. Open the Google Sheet. You should see (or have) a tab **`OccupancyLog`** and new rows with today’s timestamp.
3. If the run fails, open the run → expand **Run scraper** step → read the error (see Troubleshooting below).

---

## Data dictionary

* **Timestamp\_ET**: Local timestamp (`America/New_York`) when the scrape occurred.
* **Area**: Training area name as shown on iSportsman.
* **Occupancy**: Number of people “checked in” at that time. (Stored as text; cast to number in queries.)
* **Status**: Optional status column if present (may be blank).

---

## Quick analysis (copy into new Sheet tabs)

### A) Least-used areas (overall)

Create a tab **LowUse** and put in A1:

```excel
=QUERY(OccupancyLog!A:D,
 "select B, avg(Cast(C as number)) 
  where C is not null 
  group by B 
  order by avg(Cast(C as number)) asc", 1)
```

### B) Weekday vs weekend comparison

1. In `OccupancyLog` column **E**, add:

```excel
=IF(A2<>"", TEXT(A2,"ddd"), )
```

2. New tab **ByDay**:

```excel
=QUERY(OccupancyLog!A:E,
 "select B, E, avg(Cast(C as number))
  where C is not null
  group by B, E
  order by B, E", 1)
```

### C) Noon vs 1600 comparison

Add column **F** in `OccupancyLog`:

```excel
=IF(A2<>"", TEXT(A2,"HH:mm"), )
```

New tab **ByTime**:

```excel
=QUERY(OccupancyLog!A:F,
 "select B, F, avg(Cast(C as number))
  where C is not null
  group by B, F
  order by B, F", 1)
```

---

## Common tweaks

### Change target Sheet tab name

Set env var `SHEET_TAB_NAME` in the workflow:

```yaml
env:
  SHEET_ID: ${{ secrets.SHEET_ID }}
  GOOGLE_SA_JSON: ${{ secrets.GOOGLE_SA_JSON }}
  SHEET_TAB_NAME: "OccupancyLog"
```

### Change run times

Edit the cron(s) in `.github/workflows/schedule.yml` (UTC).
Example: add 08:00 ET (→ 12:00 UTC):

```yaml
on:
  schedule:
    - cron: "0 12,16,20 * * *"
```

### Add a simple success/failure notification (optional)

Append a step using GitHub’s job status, or wire to Slack/Email via your preferred Action.

---

## Troubleshooting

**Error:** “Could not locate the Areas/Occupancy table”

* The site may have changed. Fix `parse_table()` selector logic in `scrape_isportsman.py`.
* Temporary site outage → rerun later.

**Error:** “PERMISSION\_DENIED” or “The caller does not have permission”

* The **service account email** must be shared on the Sheet with **Editor**.
* Confirm `SHEET_ID` is correct and matches the current Sheet.

**Error:** “Invalid JSON” for `GOOGLE_SA_JSON`

* Ensure you pasted the **entire** JSON file content, unmodified, into the GitHub Secret.

**Action succeeds but no rows in Sheet**

* Confirm you’re inspecting the correct tab (`SHEET_TAB_NAME`).
* Check the run logs to see how many rows were parsed.

**Playwright errors on dependencies**

* The workflow installs Chromium with `--with-deps`; if a future image changes, re-run.
* As a fallback, pin `ubuntu-22.04` in `runs-on`.

---

## Maintenance

* Rotate the service-account key annually (create new key → update `GOOGLE_SA_JSON` secret → delete old key).
* If iSportsman markup changes, update `parse_table()` to find headers “Area” and “Occupancy”.
* Keep `playwright` reasonably current by bumping the version in `requirements.txt`.

---

## Extending (optional ideas)

* Extra run times during peak season (just add more cron hours).
* Add a “Season” or “Notes” column and filter queries by date ranges.
* Trigger a Slack/email alert when a favorite area’s **Occupancy = 0** at 1600.

---

That’s the full operator guide. If you want, I can also add a small **“health check”** step to the workflow that writes a heartbeat row (or posts a status comment) so you know immediately if a scrape ever fails.
