import html
import json
import os
from pathlib import Path

import gspread
import pandas as pd
import plotly.express as px
from oauth2client.service_account import ServiceAccountCredentials
from plotly.offline import plot as plot_div


SHEET_ID = os.environ["SHEET_ID"]
GOOGLE_SA_JSON = os.environ["GOOGLE_SA_JSON"]
SHEET_TAB_NAME = os.environ.get("SHEET_TAB_NAME", "OccupancyLog")
SITE_DIR = Path("site")


def log(message):
    print(f"[dashboard] {message}", flush=True)


def connect_sheet():
    sa_info = json.loads(GOOGLE_SA_JSON)
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB_NAME)


def load_df(ws):
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=["Timestamp_ET", "Area", "Occupancy", "Status"])

    df = pd.DataFrame(rows)
    for col in ["Timestamp_ET", "Area", "Occupancy", "Status"]:
        if col not in df.columns:
            df[col] = None

    df["Timestamp_ET"] = pd.to_datetime(df["Timestamp_ET"], errors="coerce")
    df["Area"] = df["Area"].astype(str).str.strip()
    df["Occupancy"] = pd.to_numeric(df["Occupancy"], errors="coerce")
    df["Status"] = df["Status"].fillna("").astype(str).str.strip()
    df = df.dropna(subset=["Timestamp_ET", "Area"])
    df = df[df["Area"] != ""]
    df["Hour"] = df["Timestamp_ET"].dt.strftime("%H:%M")
    df["Weekday"] = df["Timestamp_ET"].dt.strftime("%a")
    df["Date"] = df["Timestamp_ET"].dt.date
    return df.sort_values(["Timestamp_ET", "Area"])


def fig_div(fig):
    fig.update_layout(
        margin=dict(l=20, r=20, t=55, b=35),
        font=dict(family="Arial, sans-serif", size=13),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    return plot_div(fig, include_plotlyjs="cdn", output_type="div")


def metric_card(label, value, note=""):
    note_html = f'<span class="note">{html.escape(note)}</span>' if note else ""
    return f"""
    <div class="metric">
      <div class="label">{html.escape(label)}</div>
      <div class="value">{html.escape(str(value))}</div>
      {note_html}
    </div>
    """


def render_empty_site():
    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>iSportsman Occupancy Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{base_css()}</style>
</head>
<body>
  <main>
    <h1>iSportsman Occupancy Dashboard</h1>
    <p class="muted">No rows are available in {html.escape(SHEET_TAB_NAME)} yet.</p>
  </main>
</body>
</html>"""
    (SITE_DIR / "index.html").write_text(html_doc, encoding="utf-8")


def base_css():
    return """
body {
  margin: 0;
  color: #17202a;
  background: #f6f8fa;
  font-family: Arial, sans-serif;
}
main {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 42px;
}
h1, h2 {
  margin: 0;
}
h1 {
  font-size: 30px;
}
h2 {
  font-size: 19px;
  margin-top: 28px;
}
.muted {
  color: #667085;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin: 18px 0;
}
.metric, .panel {
  background: white;
  border: 1px solid #d0d7de;
  border-radius: 8px;
}
.metric {
  padding: 14px;
}
.label {
  color: #667085;
  font-size: 12px;
  text-transform: uppercase;
}
.value {
  font-size: 24px;
  font-weight: 700;
  margin-top: 5px;
}
.note {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-top: 4px;
}
.panel {
  margin-top: 12px;
  padding: 14px;
  overflow-x: auto;
}
.links a {
  color: #0969da;
  margin-right: 14px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th, td {
  border-bottom: 1px solid #d8dee4;
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
}
th {
  background: #f6f8fa;
}
"""


def latest_table(latest_df):
    rows = []
    for _, row in latest_df.iterrows():
        rows.append(
            "<tr>"
            f"<td>{html.escape(row['Area'])}</td>"
            f"<td>{'' if pd.isna(row['Occupancy']) else int(row['Occupancy'])}</td>"
            f"<td>{html.escape(row['Status'])}</td>"
            "</tr>"
        )

    return f"""
    <table>
      <thead><tr><th>Area</th><th>Occupancy</th><th>Status</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def render_site(df):
    SITE_DIR.mkdir(exist_ok=True)

    if df.empty:
        render_empty_site()
        log("Rendered empty dashboard")
        return

    latest_ts = df["Timestamp_ET"].max()
    latest_df = df[df["Timestamp_ET"] == latest_ts].sort_values("Area")
    numeric_df = df.dropna(subset=["Occupancy"]).copy()

    areas_tracked = df["Area"].nunique()
    samples = len(df)
    latest_total = int(latest_df["Occupancy"].fillna(0).sum())
    latest_zero = int((latest_df["Occupancy"].fillna(0) == 0).sum())
    first_sample = df["Timestamp_ET"].min().strftime("%Y-%m-%d")
    last_sample = latest_ts.strftime("%Y-%m-%d %H:%M:%S")

    avg_by_area = (
        numeric_df.groupby("Area", as_index=False)["Occupancy"]
        .mean()
        .rename(columns={"Occupancy": "AvgOccupancy"})
        .sort_values("AvgOccupancy", ascending=True)
    )

    low_areas = avg_by_area["Area"].head(8).tolist()
    df_low = numeric_df[numeric_df["Area"].isin(low_areas)].sort_values("Timestamp_ET")

    heat = numeric_df.groupby(["Area", "Hour"], as_index=False)["Occupancy"].mean()
    pivot = heat.pivot(index="Area", columns="Hour", values="Occupancy").fillna(0)

    by_day = numeric_df.groupby(["Weekday"], as_index=False)["Occupancy"].mean()
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    by_day["Weekday"] = pd.Categorical(by_day["Weekday"], categories=day_order, ordered=True)
    by_day = by_day.sort_values("Weekday")

    avg_by_area.to_csv(SITE_DIR / "avg_by_area.csv", index=False)
    latest_df.to_csv(SITE_DIR / "latest_snapshot.csv", index=False)
    df.to_csv(SITE_DIR / "occupancy_log_export.csv", index=False)

    fig_avg = px.bar(
        avg_by_area,
        x="AvgOccupancy",
        y="Area",
        orientation="h",
        title="Average Occupancy by Area",
        labels={"AvgOccupancy": "Avg occupancy", "Area": "Area"},
    )

    fig_time = px.line(
        df_low,
        x="Timestamp_ET",
        y="Occupancy",
        color="Area",
        title="Least-Used Areas Over Time",
        labels={"Timestamp_ET": "Time (ET)", "Occupancy": "Occupancy"},
    )

    fig_heat = px.imshow(
        pivot,
        aspect="auto",
        title="Average Occupancy by Area and Time",
        labels=dict(x="Hour (ET)", y="Area", color="Avg occupancy"),
    )

    fig_day = px.bar(
        by_day,
        x="Weekday",
        y="Occupancy",
        title="Average Occupancy by Day of Week",
        labels={"Occupancy": "Avg occupancy", "Weekday": "Day"},
    )

    metrics = "\n".join(
        [
            metric_card("Last run", last_sample, "America/New_York"),
            metric_card("Latest total", latest_total, "People checked in"),
            metric_card("Open areas", latest_zero, "Areas with zero occupancy"),
            metric_card("Areas tracked", areas_tracked),
            metric_card("Samples", samples, f"Since {first_sample}"),
        ]
    )

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>iSportsman Occupancy Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{base_css()}</style>
</head>
<body>
  <main>
    <h1>iSportsman Occupancy Dashboard</h1>
    <p class="muted">Built from {html.escape(SHEET_TAB_NAME)}. Scheduled for 12:00 and 16:00 America/New_York.</p>
    <section class="metrics">{metrics}</section>
    <section class="panel links">
      <a href="avg_by_area.csv">Average by area CSV</a>
      <a href="latest_snapshot.csv">Latest snapshot CSV</a>
      <a href="occupancy_log_export.csv">Full export CSV</a>
    </section>
    <h2>Latest Snapshot</h2>
    <section class="panel">{latest_table(latest_df)}</section>
    <section class="panel">{fig_div(fig_avg)}</section>
    <section class="panel">{fig_div(fig_time)}</section>
    <section class="panel">{fig_div(fig_heat)}</section>
    <section class="panel">{fig_div(fig_day)}</section>
  </main>
</body>
</html>"""

    (SITE_DIR / "index.html").write_text(html_doc, encoding="utf-8")
    log(f"Rendered dashboard with {samples} rows and {areas_tracked} areas")


def main():
    ws = connect_sheet()
    df = load_df(ws)
    render_site(df)


if __name__ == "__main__":
    main()
