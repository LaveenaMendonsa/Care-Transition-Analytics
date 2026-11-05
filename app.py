
import streamlit as st
import pandas as pd
import plotly.express as px
import os

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Care Transition Analytics",
    page_icon="📊",
    layout="wide"
)

# ---------------- TITLE ----------------
st.title("Care Transition Efficiency & Placement Outcome Analytics")
st.write(
    "Analyze CBP transfers, HHS care, discharges, and potential bottlenecks."
)

# ---------------- LOAD DATA ----------------
FILE_PATH = "HHS_Unaccompanied_Alien_Children_Program.csv"

if not os.path.exists(FILE_PATH):
    st.error("CSV file not found. Keep the CSV and app.py in the same folder.")
    st.stop()

df = pd.read_csv(FILE_PATH)

# ---------------- CLEAN DATA ----------------
df = df.dropna(how="all")

date_col = "Date"

df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
df = df.dropna(subset=[date_col])

numeric_cols = [
    "Children apprehended and placed in CBP custody*",
    "Children in CBP custody",
    "Children transferred out of CBP custody",
    "Children in HHS Care",
    "Children discharged from HHS Care"
]

for col in numeric_cols:
    df[col] = (
        df[col]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.sort_values("Date").reset_index(drop=True)

# ---------------- SIDEBAR FILTERS ----------------
st.sidebar.header("Dashboard Filters")

min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

date_range = st.sidebar.date_input(
    "Select reporting date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = df[
        (df["Date"].dt.date >= start_date) &
        (df["Date"].dt.date <= end_date)
    ].copy()
else:
    filtered_df = df.copy()

threshold = st.sidebar.slider(
    "Net flow alert threshold",
    min_value=0,
    max_value=1000,
    value=50,
    step=10,
    key="net_flow_threshold"
)

st.sidebar.write("Selected threshold:", threshold)

if filtered_df.empty:
    st.warning("No records found for the selected date range.")
    st.stop()

# ---------------- MAIN DATA ----------------
st.success("Dataset loaded successfully!")

st.caption(
    f"Showing {len(filtered_df)} reporting dates from "
    f"{filtered_df['Date'].min().strftime('%d-%b-%Y')} to "
    f"{filtered_df['Date'].max().strftime('%d-%b-%Y')}."
)

# ---------------- KPI CALCULATIONS ----------------
total_apprehensions = filtered_df[numeric_cols[0]].sum()
total_cbp_custody = filtered_df[numeric_cols[1]].sum()
total_transfers = filtered_df[numeric_cols[2]].sum()
total_hhs_care = filtered_df[numeric_cols[3]].sum()
total_discharges = filtered_df[numeric_cols[4]].sum()

transfer_efficiency = (
    total_transfers / total_cbp_custody * 100
    if total_cbp_custody else 0
)

discharge_effectiveness = (
    total_discharges / total_hhs_care * 100
    if total_hhs_care else 0
)

pipeline_throughput = (
    (total_transfers + total_discharges) /
    total_apprehensions * 100
    if total_apprehensions else 0
)

discharge_cv = (
    filtered_df[numeric_cols[4]].std() /
    filtered_df[numeric_cols[4]].mean()
    if filtered_df[numeric_cols[4]].mean() != 0
    and filtered_df[numeric_cols[4]].std() == filtered_df[numeric_cols[4]].std()
    else 0
)

outcome_stability = 100 / (1 + discharge_cv)

# ---------------- KPI DISPLAY ----------------
st.header("Key Performance Indicators")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Transfer Efficiency", f"{transfer_efficiency:.2f}%")
c2.metric("Discharge Effectiveness", f"{discharge_effectiveness:.2f}%")
c3.metric("Pipeline Throughput (Proxy)", f"{pipeline_throughput:.2f}%")
c4.metric("Outcome Stability (Proxy)", f"{outcome_stability:.1f}/100")

st.caption(
    "These are aggregate activity ratios, not individual child transition "
    "probabilities or measured waiting times. Throughput and stability are exploratory proxies."
)

# ---------------- DATASET OVERVIEW ----------------
st.header("Dataset Overview")

a, b, c = st.columns(3)

a.metric("Total Records", len(filtered_df))
b.metric("Start Date", filtered_df["Date"].min().strftime("%d-%b-%Y"))
c.metric("End Date", filtered_df["Date"].max().strftime("%d-%b-%Y"))

with st.expander("View Dataset"):
    st.dataframe(filtered_df, use_container_width=True)

# ---------------- PIPELINE VISUALIZATION ----------------
st.header("Care Pipeline Visualization")

pipeline = pd.DataFrame({
    "Stage": [
        "Children apprehended",
        "Children in CBP custody",
        "Children transferred",
        "Children in HHS care",
        "Children discharged"
    ],
    "Total": [
        total_apprehensions,
        total_cbp_custody,
        total_transfers,
        total_hhs_care,
        total_discharges
    ]
})

fig = px.bar(
    pipeline,
    x="Stage",
    y="Total",
    color="Stage",
    title="Total Reported Activity by Care Stage",
    text_auto=".2s"
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Stage totals are reported activity measures. They are not a "
    "deduplicated count of unique children moving through the full pipeline."
)

# ---------------- TRANSFER AND DISCHARGE ANALYSIS ----------------
st.header("Transfer and Discharge Analysis")

fig = px.line(
    filtered_df,
    x="Date",
    y=[
        numeric_cols[2],
        numeric_cols[4]
    ],
    markers=True,
    title="Daily Transfers and Discharges"
)

st.plotly_chart(fig, use_container_width=True)

# ---------------- MONTHLY TREND ----------------
st.header("Monthly Trend Analysis")

monthly_df = filtered_df.copy()
monthly_df["Month"] = monthly_df["Date"].dt.to_period("M").astype(str)

monthly = monthly_df.groupby("Month")[numeric_cols].sum().reset_index()

fig = px.line(
    monthly,
    x="Month",
    y=[numeric_cols[0], numeric_cols[2], numeric_cols[4]],
    markers=True,
    title="Monthly Apprehensions, Transfers and Discharges"
)

st.plotly_chart(fig, use_container_width=True)

# ---------------- BOTTLENECK ANALYSIS ----------------
st.header("Bottleneck Analysis")

bottleneck_df = filtered_df[["Date"] + numeric_cols].copy()

bottleneck_df["Entry-Discharge Difference"] = (
    bottleneck_df[numeric_cols[0]] -
    bottleneck_df[numeric_cols[4]]
)

fig = px.bar(
    bottleneck_df,
    x="Date",
    y="Entry-Discharge Difference",
    title="Daily Entry-Discharge Difference",
    color="Entry-Discharge Difference"
)

st.plotly_chart(fig, use_container_width=True)

# ---------------- THRESHOLD ALERTS ----------------

# ---------------- THRESHOLD ALERTS ----------------
st.header("Threshold-Based Alerts")

st.write("Adjust the threshold to identify reporting dates with larger entry-discharge differences.")

bottleneck_df = filtered_df[["Date"] + numeric_cols].copy()

bottleneck_df["Entry-Discharge Difference"] = (
    bottleneck_df[numeric_cols[0]] -
    bottleneck_df[numeric_cols[4]]
)

bottleneck_df["Absolute Difference"] = (
    bottleneck_df["Entry-Discharge Difference"].abs()
)

alert_df = bottleneck_df[
    bottleneck_df["Absolute Difference"] >= threshold
].copy()

alert_count = len(alert_df)

total_dates = len(bottleneck_df)

col1, col2, col3 = st.columns(3)

col1.metric("Selected Threshold", threshold)
col2.metric("Alert Dates", alert_count)
col3.metric("Dates Analyzed", total_dates)

st.progress(
    alert_count / total_dates if total_dates > 0 else 0
)

if alert_count > 0:
    st.warning(f"{alert_count} dates crossed the selected threshold.")

    st.subheader("Alert Details")

    st.dataframe(
        alert_df[
            ["Date", "Entry-Discharge Difference", "Absolute Difference"]
        ].sort_values(
            "Absolute Difference",
            ascending=False
        ),
        use_container_width=True
    )

    fig = px.bar(
        alert_df,
        x="Date",
        y="Absolute Difference",
        title="Dates Crossing the Selected Threshold"
    )

    fig.add_hline(
        y=threshold,
        line_dash="dash",
        annotation_text=f"Threshold: {threshold}"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.success("No dates crossed the selected threshold.")

    st.info(
        "Try lowering the threshold to identify more reporting dates."
    )

st.caption(
    "This is an exploratory entry-discharge difference indicator, "
    "not a measured backlog."
)

# ---------------- FOOTER ----------------
st.divider()

st.write("Care Transition Analytics Dashboard")
st.caption(
    "Exploratory analysis based on the supplied reporting dataset."
)
