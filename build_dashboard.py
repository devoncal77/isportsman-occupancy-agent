import os, json, math
from datetime import datetime
import pandas as pd
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from plotly.offline import plot as plot_div

SHEET_ID = os.environ["SHEET_ID"]
GOOGLE_SA_JSON = os.environ["GOOGLE_SA_JSON"]
SHEET_TAB_NAME = os.environ.get("SHEET_TAB_NAME", "OccupancyLog")
SITE_DIR = "site"

def connect_sheet():
    sa_info = json.loads(GOOGLE_SA_JSON)
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scope)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB_NAME)
    return ws

def load_df(ws):
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=["Timestamp_ET","Area","Occupancy","Status"])
    df = pd.DataFrame(rows)
    for col in ["Timestamp_ET","Area","Occupancy","Status"]:
        if col not in df.columns:
            df[col] = None
    df["Timestamp_ET"] = pd.to_datetime(df["Timestamp_ET"], errors="coerce")
    df["Area"] = df["Area"].astype(str)
    df["Occupancy"] = pd.to_numeric(df["Occupancy"], errors="coerce")
    df["Status"] = df["Status"].astype(str)
    df = df.dropna(subset=["Timestamp_ET","Area"])
    df["Hour"] = df["Timestamp_ET"].dt.strftime("%H:%M")
    df["Weekday"] = df["Timestamp_ET"].dt.strftime("%a")
    return df

def fig_div(fig):
    return plot_div(fig, include_plotlyjs="cdn", output_type="div")

def render_site(df):
    os.makedirs(SITE_DIR, exist_ok=True)

    if df.empty:
        html = f"""<!doctype html><html><head><meta charset="utf-8">
        <title>iSportsman Occupancy Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>body{{font-family:system-ui,Segoe UI,Arial;margin:24px;max-width:1100px}}
        .card{{padding:14px 16px;border:1px solid #ddd;border-radius:12px;margin:8px 0}}
        h1{{margin:0 0 10px}} h2{{margin:24px 0 8px}} .muted{{color:#666}}</style></head><body>
        <h1>iSportsman Occupancy Dashboard</h1>
        <p class="muted">No data yet. The scraper runs at 12:00 & 16:00 ET.</p>
        </body></html>"""
        with open(os.path.join(SITE_DIR,"index.html"),"w",encoding="utf-8") as f:
            f.write(html)
        return

    latest_ts = df["Timestamp_ET"].max()
    latest_df = df[df["Timestamp_ET"] == latest_ts].sort_values("Area")
    areas_tracked = df["Area"].nunique()
    samples = len(df)

    # Averages by area
    avg_by_area = (
        df.groupby("Area", as_index=False)["Occupancy"]
          .mean(numeric_only=True)
          .rename(columns={"Occupancy":"AvgOccupancy"})
          .sort_values("AvgOccupancy", ascending=True)
    )

    # Least-used areas (top 8 with lowest average)
    low_areas = avg_by_area["Area"].head(8).tolist()
    df_low = df[df["Area"].isin(low_areas)].sort_values("Timestamp_ET")

    # Heatmap (Area x Hour)
    heat = (df
        .groupby(["Area","Hour"], as_index=False)["Occupancy"]
        .mean(numeric_only=True))
    pivot = heat.pivot(index="Area", columns="Hour", values="Occupancy").fillna(0)

    # Figures
    fig_avg = px.bar(
        avg_by_area, x="AvgOccupancy", y="Area",
        orientation="h", title="Average Occupancy by Area (all samples)",
        labels={"AvgOccupancy":"Avg occupancy","Area":"Area"},
    )

    fig_time = px.line(
        df_low, x="Timestamp_ET", y="Occupancy", color="Area",
        title="Occupancy over time — least-used areas",
        labels={"Timestamp_ET":"Time (ET)","Occupancy":"Occupancy"},
    )

    fig_heat = px.imshow(
        pivot, aspect="auto", title="Average Occupancy by Hour (Area × Time)",
        labels=dict(x="Hour (ET)", y="Area", color="Avg occupancy"),
    )

    # Tables to CSV for download
    avg_by_area.to_csv(os.path.join(SITE_DIR,"avg_by_area.csv"), index=False)
    latest_df.to_csv(os.path.join(SITE_DIR,"latest_snapshot.csv"), index=False)

    # Build HTML
    ts_str = latest_ts.strftime("%Y-%m-%d %H:%M:%S")
    kpis = f"""
    <div class="card"><strong>Last run:</strong> {ts_str} ET &nbsp; | &nbsp;
    <strong>Areas:</strong> {areas_tracked} &nbsp; | &nbsp;
    <strong>Samples:</strong> {samples}</div>
    <div class="card"><a href="avg_by_area.csv">avg_by_area.csv</a> ·
    <a href="latest_snapshot.csv">latest_snapshot.csv</a></div>
    """

    html = f"""<!doctype html><html><head><meta charset="utf-8">
    <title>iSportsman Occupancy Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body{{font-family:system-ui,Segoe UI,Arial;margin:24px;max-width:1150px}}
      h1{{margin:0 0 10px}} .muted{{color:#666}}
      .card{{padding:14px 16px;border:1px solid #ddd;border-radius:12px;margin:10px 0}}
      .section{{margin:26px 0}}
    </style></head><body>
    <h1>iSportsman Occupancy Dashboard</h1>
    <div class="muted">Auto-built at 12:00 & 16:00 ET from {SHEET_TAB_NAME}</div>
    {kpis}
    <div class="section">{fig_avg and fig_div(fig_avg)}</div>
    <div class="section">{fig_time and fig_div(fig_time)}</div>
    <div class="section">{fig_heat and fig_div(fig_heat)}</div>
    </body></html>"""

    with open(os.path.join(SITE_DIR,"index.html"),"w",encoding="utf-8") as f:
        f.write(html)

def main():
    ws = connect_sheet()
    df = load_df(ws)
    render_site(df)

if __name__ == "__main__":
    main()
