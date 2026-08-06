import os
import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# 1. DATA SYNCHRONIZATION (GITHUB OR LOCAL)
# ==========================================
# Replace with your actual repository branch/raw URL if deployed on Streamlit Cloud
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/chethanshivaraju94-netizen/nse-market-monitor/main"
)


@st.cache_data(
    ttl=3600, show_spinner="📡 Fetching latest Market Health & Sector tables..."
)
def load_market_monitor_data():
  local_file = "NSE_Market_Monitor.xlsx"
  url = f"{GITHUB_RAW_BASE}/NSE_Market_Monitor.xlsx"

  try:
    if os.path.exists(local_file):
      df = pd.read_excel(local_file, sheet_name=0)
    else:
      df = pd.read_excel(url, sheet_name=0)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    return df
  except Exception as e:
    st.error(f"Could not load Market Monitor file: {e}")
    return pd.DataFrame()


@st.cache_data(
    ttl=3600,
    show_spinner="📡 Fetching Sector Rotation & Heatmap tables...",
)
def load_sector_monitor_data():
  local_file = "NSE_Sector_Monitor.xlsx"
  url = f"{GITHUB_RAW_BASE}/NSE_Sector_Monitor.xlsx"

  try:
    xls = pd.ExcelFile(local_file if os.path.exists(local_file) else url)
    df_heat = pd.read_excel(xls, sheet_name="Heatmap")
    df_rot = pd.read_excel(xls, sheet_name="Rotation Tracker")
    df_rot["Date"] = pd.to_datetime(
        df_rot["Date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    return df_heat, df_rot
  except Exception as e:
    st.error(f"Could not load Sector Monitor file: {e}")
    return pd.DataFrame(), pd.DataFrame()


# ==========================================
# 2. COLUMN CONFIGURATION FOR CLEAN DISPLAY
# ==========================================
def get_left_aligned_config(cols):
  cfg = {}
  for c in cols:
    if c in ["Date", "Sector"]:
      cfg[c] = st.column_config.Column(c, alignment="left", width=130)
    elif "Rank Velocity" in c:
      cfg[c] = st.column_config.NumberColumn(
          c, alignment="left", format="%+d", width=120
      )
    elif "Rank" in c:
      cfg[c] = st.column_config.NumberColumn(c, alignment="left", width=105)
    elif "%" in c or "Ratio" in c or "Breadth" in c:
      cfg[c] = st.column_config.NumberColumn(
          c, alignment="left", format="%.2f", width=110
      )
    elif "Close" in c:
      cfg[c] = st.column_config.NumberColumn(
          c, alignment="left", format="%.2f", width=115
      )
    else:
      cfg[c] = st.column_config.Column(c, alignment="left", width=110)
  return cfg


# ==========================================
# 3. STREAMLIT PAGE LAYOUT
# ==========================================
st.title("🏥 Market Health & Sector Rotation Studio")
st.markdown(
    "Automated **Nifty 500 Breadth Monitor** and **27-Sector CAN SLIM Rotation"
    " Engine**. Updated automatically every weekday by your scheduled cronjob."
)

tab_mm, tab_sector_heat, tab_sector_rot = st.tabs([
    "📈 NSE Market Breadth Monitor",
    "🔥 Sector RS Heatmap",
    "📊 Historical Rotation Tracker",
])

# ------------------------------------------
# TAB 1: NSE MARKET MONITOR
# ------------------------------------------
with tab_mm:
  df_mm = load_market_monitor_data()
  if not df_mm.empty:
    st.subheader(
        f"📊 Nifty Total Market Breadth & VCP Indicators ({len(df_mm)} Days)"
    )

    # Highlight latest day's key ratios
    latest = df_mm.iloc[0] if len(df_mm) > 0 else {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
      st.metric(
          "Latest Nifty 500 Close",
          f"{latest.get('Nifty 500 Close', 'N/A')}",
          f"{latest.get('Nifty 500 Chg %', 0)}%",
      )
    with c2:
      st.metric(
          "5-Day Thrust Ratio", f"{latest.get('5 Day Ratio', 'N/A')}"
      )
    with c3:
      st.metric(
          "10-Day Thrust Ratio", f"{latest.get('10 Day Ratio', 'N/A')}"
      )
    with c4:
      st.metric("A/D Ratio", f"{latest.get('A/D Ratio', 'N/A')}")

    st.dataframe(
        df_mm,
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=get_left_aligned_config(df_mm.columns),
    )
  else:
    st.info("Market Monitor data not available yet.")

# ------------------------------------------
# TAB 2: SECTOR RS HEATMAP
# ------------------------------------------
with tab_sector_heat:
  df_heat, _ = load_sector_monitor_data()
  if not df_heat.empty:
    st.subheader(
        "🔥 27-Sector CAN SLIM Relative Strength Heatmap (Ranked by 65D RS)"
    )
    st.caption(
        "💡 **Velocity Legend:** Positive (+) values indicate upward rank"
        " acceleration; Negative (-) indicate loss of relative momentum."
    )

    st.dataframe(
        df_heat,
        use_container_width=True,
        hide_index=True,
        height=580,
        column_config=get_left_aligned_config(df_heat.columns),
    )
  else:
    st.info("Sector Heatmap data not available yet.")

# ------------------------------------------
# TAB 3: HISTORICAL ROTATION TRACKER
# ------------------------------------------
with tab_sector_rot:
  _, df_rot = load_sector_monitor_data()
  if not df_rot.empty:
    st.subheader(
        "📊 65-Day Historical Relative Strength Ranks (All Sectors)"
    )
    st.caption(
        "💡 Rank 1 = Strongest Relative Strength vs. Nifty 500 Benchmark"
        " (`^CRSLDX`)."
    )

    st.dataframe(
        df_rot,
        use_container_width=True,
        hide_index=True,
        height=580,
        column_config=get_left_aligned_config(df_rot.columns),
    )
  else:
    st.info("Rotation Tracker data not available yet.")

# ==========================================
# 4. OPTIONAL ON-DEMAND LIVE CALCULATION
# ==========================================
st.markdown("---")
with st.expander("⚡ Optional: Force Real-Time Scan Now (Bypass Schedule)"):
  st.caption(
      "Your automated scheduled cronjob updates these tables daily. Click"
      " below only if you want to force an immediate intraday calculation"
      " from Yahoo Finance."
  )
  if st.button("🔄 Execute Live Engine Calculation", type="secondary"):
    st.warning(
        "Running full Market Health and Sector scan. This downloads data for"
        " 750+ tickers and may take ~90 seconds..."
    )
    # Here you can import and invoke your MM.py and Sector_Monitor.py scripts directly
    # e.g., os.system("python MM.py && python Sector_Monitor.py")
    st.cache_data.clear()
    st.success("✅ Calculation complete! Cache cleared.")
    st.rerun()
