import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ---------------------------------------------------------
# PAGE SETTINGS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Care Transition Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("Care Transition Efficiency & Placement Outcome Analytics")
st.markdown(
    "Analyze CBP transfers, HHS care, discharges, and potential bottlenecks."
)

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
DATA_FILE = Path(__file__).parent / "HHS_Unaccompanied_Alien_Children_Program.csv"

if not DATA_FILE.exists():
    st.error(
        "Dataset not found. Keep app.py and "
        "HHS_Unaccompanied_Alien_Children_Program.csv in the same folder."
    )
    st.stop()

df = pd.read_csv(DATA_FILE)
df = df.dropna(how="all").copy()

# Exact column names from the provided dataset
DATE_COL = "Date"
APPREHENSIONS = "Children apprehended and placed in CBP custody*"
CBP_CUSTODY = "Children in CBP custody"
TRANSFERS = "Children transferred out of CBP custody"
HHS_CARE = "Children in HHS Care"
DISCHARGES = "Children discharged from HHS Care"

NUMERIC_COLS = [
    APPREHENSIONS, CBP_CUSTODY, TRANSFERS, HHS_CARE, DISCHARGES
]

df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

for col in NUMERIC_COLS:
    df[col] = pd.to_numeric(
        df[col].astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    )

df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)

# Keep missing numeric values missing in the source table, but use zero
# for calculations/plots so the dashboard can run.
df[NUMERIC_COLS] = df[NUMERIC_COLS].fillna(0)

if df.empty:
    st.error("No valid dated records were found in the CSV.")
    st.stop()

st.sidebar.header("Dashboard Filters")

min_date = df[DATE_COL].min().date()
max_date = df[DATE_COL].max().date()


date_range = st.sidebar.date_input(
    "Select reporting date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
    key="date_filter"
)

if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
    st.info("Please select both a start date and an end date.")
    st.stop()

start_date, end_date = date_range


if start_date > end_date:
    st.error("Start date must be on or before end date.")
    st.stop()

data = df[
    (df[DATE_COL].dt.date >= start_date) &
    (df[DATE_COL].dt.date <= end_date)
].copy()

if data.empty:
    st.warning("No records are available for this date range.")
    st.stop()

st.success(f"Dataset loaded successfully — {len(data):,} reporting records in selected range.")

with st.expander("Dataset overview"):
    st.write(f"**Full dataset shape:** {df.shape[0]:,} rows × {df.shape[1]} columns")
    st.write(f"**Available date range:** {min_date} to {max_date}")
    st.dataframe(data.head(10), use_container_width=True)

# ---------------------------------------------------------
# KPI CALCULATIONS
# ---------------------------------------------------------
def ratio_percent(numerator, denominator):
    return (numerator / denominator * 100) if denominator else 0.0

# These are period-level aggregate ratios following the project brief.
transfer_efficiency = ratio_percent(data[TRANSFERS].sum(), data[CBP_CUSTODY].sum())
discharge_effectiveness = ratio_percent(data[DISCHARGES].sum(), data[HHS_CARE].sum())

# A transparent proxy for overall throughput: successful discharges
# relative to apprehensions during the selected reporting period.
# This is NOT cohort-based throughput.
total_apprehensions = data[APPREHENSIONS].sum()
total_discharges = data[DISCHARGES].sum()
pipeline_throughput = ratio_percent(total_discharges, total_apprehensions)

# Daily flow balance indicators. Positive values indicate more entries
# than exits during that reporting date; these are not individual wait times.
data["CBP Net Flow"] = data[APPREHENSIONS] - data[TRANSFERS]
data["HHS Net Flow"] = data[TRANSFERS] - data[DISCHARGES]

daily_discharge_mean = data[DISCHARGES].mean()
daily_discharge_std = data[DISCHARGES].std()

if pd.notna(daily_discharge_std) and daily_discharge_mean > 0:
    cv = daily_discharge_std / daily_discharge_mean
    outcome_stability = max(0, min(100, 100 * (1 - cv)))
else:
    outcome_stability = 0.0

st.header("Key Performance Indicators")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Transfer Efficiency", f"{transfer_efficiency:.2f}%")
k2.metric("Discharge Effectiveness", f"{discharge_effectiveness:.2f}%")
k3.metric("Pipeline Throughput (proxy)", f"{pipeline_throughput:.2f}%")
k4.metric("Outcome Stability (proxy)", f"{outcome_stability:.1f}/100")

st.caption(
    "KPIs are aggregate reporting-period ratios based on the project brief. "
    "They do not track individual children or measure individual waiting times. "
    "The throughput and stability values are analytical proxies."
)

# ---------------------------------------------------------
# CORE MODULE 1: CARE PIPELINE FLOW VISUALIZATION
# ---------------------------------------------------------
st.header("1. Care Pipeline Flow Visualization")
st.caption(
    "Illustrative aggregate flow: apprehensions → CBP transfers → HHS discharges. "
    "These totals are not a matched cohort."
)

flow_values = [
    max(float(data[APPREHENSIONS].sum()), 0),
    max(float(data[TRANSFERS].sum()), 0),
    max(float(data[DISCHARGES].sum()), 0)
]

sankey = go.Figure(data=[go.Sankey(
    node=dict(
        pad=24,
        thickness=22,
        label=["CBP Apprehensions", "CBP Transfers to HHS", "HHS Discharges"],
    ),
    link=dict(
        source=[0, 1],
        target=[1, 2],
        value=[flow_values[0], flow_values[1]]
    )
)])

sankey.update_layout(
    title="Aggregate Care Pipeline Flow",
    height=420,
    margin=dict(l=10, r=10, t=55, b=10)
)
st.plotly_chart(sankey, use_container_width=True)

# ---------------------------------------------------------
# CORE MODULE 2: TRANSFER & DISCHARGE EFFICIENCY
# ---------------------------------------------------------
st.header("2. Transfer & Discharge Efficiency")

show_transfer = st.sidebar.checkbox("Show Transfer Efficiency", value=True)
show_discharge = st.sidebar.checkbox("Show Discharge Effectiveness", value=True)
show_throughput = st.sidebar.checkbox("Show Throughput Proxy", value=True)

efficiency_rows = []
if show_transfer:
    efficiency_rows.append({"Metric": "Transfer Efficiency", "Value (%)": transfer_efficiency})
if show_discharge:
    efficiency_rows.append({"Metric": "Discharge Effectiveness", "Value (%)": discharge_effectiveness})
if show_throughput:
    efficiency_rows.append({"Metric": "Pipeline Throughput (proxy)", "Value (%)": pipeline_throughput})

if efficiency_rows:
    efficiency_df = pd.DataFrame(efficiency_rows)
    fig_eff = px.bar(
        efficiency_df,
        x="Metric",
        y="Value (%)",
        text_auto=".2f",
        title="Selected Efficiency Ratios"
    )
    fig_eff.update_layout(yaxis_title="Percentage (%)")
    st.plotly_chart(fig_eff, use_container_width=True)
else:
    st.info("Select at least one ratio metric from the sidebar.")

# ---------------------------------------------------------
# CORE MODULE 3: BOTTLENECK DETECTION
# ---------------------------------------------------------
st.header("3. Bottleneck Detection")

st.write(
    "Net flow compares reported inflows and outflows for each stage. "
    "Positive net flow may indicate potential accumulation during that reporting period."
)

fig_net = px.line(
    data,
    x=DATE_COL,
    y=["CBP Net Flow", "HHS Net Flow"],
    markers=True,
    title="Daily Net Flow by Stage",
    labels={"value": "Net flow (reported count)", "variable": "Stage"}
)
fig_net.add_hline(y=0, line_dash="dash")
st.plotly_chart(fig_net, use_container_width=True)

st.subheader("Threshold-based visual alerts")

threshold = st.sidebar.number_input(
    "Net flow alert threshold",
    min_value=0,
    value=100,
    step=25
)

alerts = data[
    (data["CBP Net Flow"] > threshold) |
    (data["HHS Net Flow"] > threshold)
].copy()

if alerts.empty:
    st.success(f"No dates exceeded the selected threshold ({threshold}).")
else:
    st.warning(
        f"{len(alerts)} reporting date(s) exceeded the net-flow threshold of {threshold}."
    )
    st.dataframe(
        alerts[[DATE_COL, "CBP Net Flow", "HHS Net Flow"]],
        use_container_width=True
    )

# ---------------------------------------------------------
# CORE MODULE 4: OUTCOME TREND ANALYSIS
# ---------------------------------------------------------
st.header("4. Outcome Trend Analysis")

fig_daily = px.line(
    data,
    x=DATE_COL,
    y=DISCHARGES,
    markers=True,
    title="Daily HHS Discharges"
)
fig_daily.update_layout(yaxis_title="Children discharged (reported count)")
st.plotly_chart(fig_daily, use_container_width=True)

# Monthly trend
monthly = (
    data.set_index(DATE_COL)[[APPREHENSIONS, TRANSFERS, DISCHARGES]]
    .resample("ME")
    .sum()
    .reset_index()
)

fig_monthly = px.line(
    monthly,
    x=DATE_COL,
    y=[APPREHENSIONS, TRANSFERS, DISCHARGES],
    markers=True,
    title="Monthly Apprehensions, Transfers, and Discharges"
)
fig_monthly.update_layout(yaxis_title="Reported count")
st.plotly_chart(fig_monthly, use_container_width=True)

# Weekday/weekend comparison
data["Day Type"] = data[DATE_COL].dt.dayofweek.map(
    lambda day: "Weekend" if day >= 5 else "Weekday"
)

weekday_summary = (
    data.groupby("Day Type")[[TRANSFERS, DISCHARGES]]
    .mean()
    .reset_index()
)

fig_weekday = px.bar(
    weekday_summary,
    x="Day Type",
    y=[TRANSFERS, DISCHARGES],
    barmode="group",
    title="Average Transfers and Discharges: Weekday vs Weekend"
)
st.plotly_chart(fig_weekday, use_container_width=True)

# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------
st.header("Download filtered data")

download_df = data.copy()
download_df[DATE_COL] = download_df[DATE_COL].dt.strftime("%Y-%m-%d")
csv_bytes = download_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download filtered CSV",
    data=csv_bytes,
    file_name="care_transition_filtered_data.csv",
    mime="text/csv"
)

st.divider()
st.caption("Care Transition Efficiency & Placement Outcome Analytics | Unified Mentor")
