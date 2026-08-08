st.title("📈 India Equities Screener & Watchlist Studio")
st.markdown(
    "Professional **CAN SLIM Screener**, **Hierarchical Sector Rotation**, "
    "**Multi-Watchlist Studio**, and **Tradebook Risk Journal**."
)

# ==========================================
# 1. OFFICIAL 22 SECTORS & 59 INDUSTRIES
# ==========================================
# [ !!! KEEP YOUR EXISTING INDIAN_SECTOR_HIERARCHY DICTIONARY HERE !!! ]
# [ !!! KEEP YOUR EXISTING TV_TO_INDIAN_MAP DICTIONARY HERE !!! ]

def map_to_indian_classification(tv_industry, tv_sector):
  mapped = TV_TO_INDIAN_MAP.get((tv_sector, tv_industry))
  if mapped:
    return mapped
  return "Diversified", "Diversified Commercial Services"

def parse_chart_selection_multi(event):
  if event and isinstance(event, dict):
    sel = event.get("selection", {})
    points = sel.get("points", [])
    if points:
      return [p.get("label") for p in points if p.get("label")]
  return []

def parse_table_selection_multi(event, df_source, col_name):
  if event and isinstance(event, dict):
    sel = event.get("selection", {})
    rows = sel.get("rows", [])
    if rows:
      selected_vals = []
      for idx in rows:
        if idx < len(df_source):
          selected_vals.append(df_source.iloc[idx][col_name])
      return selected_vals
  return []

def parse_pasted_tickers(raw_text):
  if not raw_text:
    return []
  tokens = re.split(r"[,\\n\\r\\t;]+", raw_text)
  cleaned = []
  for t in tokens:
    t = t.strip().upper()
    t = re.sub(r"[^A-Z0-9:]", "", t)
    if not t:
      continue
    if ":" not in t:
      t = f"NSE:{t}"
    if t not in cleaned:
      cleaned.append(t)
  return cleaned

# ==========================================
# MULTI-ALIAS COALESCING HELPER
# ==========================================
def coalesce_columns(df, col_list):
  res = pd.Series(index=df.index, dtype="float64")
  for c in col_list:
    if c in df.columns:
      s = pd.to_numeric(df[c], errors="coerce")
      res = res.fillna(s)
  return res

# ==========================================
# ROBUST MULTI-ALIAS IPO DATE HELPER
# ==========================================
def clean_tv_date_col(val_series):
  num_s = pd.to_numeric(val_series, errors="coerce")
  num_valid = num_s.where(num_s > 0)
  dt_unix_s = pd.to_datetime(
      num_valid.where(num_valid <= 1e11), unit="s", errors="coerce"
  )
  dt_unix_ms = pd.to_datetime(
      num_valid.where(num_valid > 1e11), unit="ms", errors="coerce"
  )
  dt_unix = dt_unix_s.fillna(dt_unix_ms)
  dt_iso = pd.to_datetime(val_series, errors="coerce")
  dt_combined = dt_unix.fillna(dt_iso)
  return dt_combined.where(dt_combined >= pd.Timestamp("1980-01-01"), pd.NaT)

def add_clean_ipo_date_col(df):
  ipo_cols = [
      c
      for c in [
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
      ]
      if c in df.columns
  ]
  if ipo_cols:
    clean_dt_df = pd.DataFrame(index=df.index)
    for c in ipo_cols:
      clean_dt_df[c] = clean_tv_date_col(df[c])
    df["IPO_Date_DT"] = clean_dt_df.max(axis=1)
  else:
    df["IPO_Date_DT"] = pd.NaT
  df["IPO Date"] = df["IPO_Date_DT"].dt.strftime("%Y-%m-%d").fillna("N/A")
  return df

# ==========================================
# 2. BACKEND API QUERIES
# ==========================================
EPS_Q_ALIASES = [
    "earnings_per_share_diluted_yoy_growth_fq",
    "earnings_per_share_fq_yoy_growth",
    "earnings_per_share_diluted_yoy_growth_quarterly",
    "basic_eps_yoy_growth_fq",
]

SALES_Q_ALIASES = [
    "revenue_yoy_growth_fq",
    "total_revenue_yoy_growth_fq",
    "revenue_yoy_growth_quarterly",
    "sales_yoy_growth_fq",
]

def fetch_screener_data(
    exchanges, min_mcap, vol_period_days, ma_columns_to_fetch, limit_rows
):
  if not exchanges:
    return pd.DataFrame()
  min_mcap_inr = min_mcap * 10_000_000
  tv_vol_col = f"average_volume_{vol_period_days}d_calc"
  select_cols = (
      [
          "name",
          "close",
          "change",
          "high",
          "low",
          "open",
          "volume",
          "market_cap_basic",
          tv_vol_col,
          "ADR",
          "price_52_week_high",
          "price_52_week_low",
          "exchange",
          "type",
          "industry",
          "sector",
          "index",
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
          "Perf.W",
          "Perf.1M",
          "Perf.3M",
          "Perf.6M",
          "Perf.YTD",
          "Perf.Y",
      ]
      + EPS_Q_ALIASES
      + SALES_Q_ALIASES
  )

  for c in ma_columns_to_fetch:
    if c not in select_cols:
      select_cols.append(c)
  q = (
      Query()
      .set_markets("india")
      .select(*select_cols)
      .where(col("market_cap_basic") >= min_mcap_inr)
      .order_by("volume", ascending=False)
      .limit(limit_rows)
  )
  try:
    _, df = q.get_scanner_data()
    return df
  except Exception as e:
    st.error(f"Error fetching data from TradingView API: {e}")
    return pd.DataFrame()

def fetch_watchlist_enrichMENT(symbol_list):
  if not symbol_list:
    return pd.DataFrame()
  bare_names = [s.split(":")[-1].strip().upper() for s in symbol_list]
  select_cols = (
      [
          "name",
          "close",
          "change",
          "ADR",
          "market_cap_basic",
          "exchange",
          "industry",
          "sector",
          "index",
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
          "Perf.W",
          "Perf.1M",
          "Perf.3M",
          "Perf.6M",
          "Perf.YTD",
          "Perf.Y",
      ]
      + EPS_Q_ALIASES
      + SALES_Q_ALIASES
  )

  q = (
      Query()
      .set_markets("india")
      .select(*select_cols)
      .where(col("name").isin(bare_names))
      .limit(max(len(bare_names) * 5, 1500))
  )
  try:
    _, df = q.get_scanner_data()
    if not df.empty:
      df["ADR_pct"] = ((df["ADR"] / df["close"]) * 100).round(2)
      df["Close"] = df["close"].round(2)
      df["Change %"] = df["change"].round(2)
      df["Market Cap (₹ Cr)"] = (df["market_cap_basic"] / 10_000_000).round(2)
      df["EPS Q YoY %"] = coalesce_columns(df, EPS_Q_ALIASES).round(2)
      df["Sales Q YoY %"] = coalesce_columns(df, SALES_Q_ALIASES).round(2)
      df = add_clean_ipo_date_col(df)

      if "Perf.W" in df.columns:
        df["Perf % 1W"] = pd.to_numeric(df["Perf.W"], errors="coerce").round(2)
      if "Perf.1M" in df.columns:
        df["Perf % 1M"] = pd.to_numeric(df["Perf.1M"], errors="coerce").round(2)
      if "Perf.3M" in df.columns:
        df["Perf % 3M"] = pd.to_numeric(df["Perf.3M"], errors="coerce").round(2)
      if "Perf.6M" in df.columns:
        df["Perf % 6M"] = pd.to_numeric(df["Perf.6M"], errors="coerce").round(2)
      if "Perf.YTD" in df.columns:
        df["Perf % YTD"] = pd.to_numeric(
            df["Perf.YTD"], errors="coerce"
        ).round(2)
      if "Perf.Y" in df.columns:
        df["Perf % 1Y"] = pd.to_numeric(df["Perf.Y"], errors="coerce").round(2)

      df = df.drop_duplicates(subset=["name"], keep="first")

      mapped_sectors, mapped_industries = [], []
      for _, row in df.iterrows():
        sec, ind = map_to_indian_classification(
            row.get("industry", ""), row.get("sector", "")
        )
        mapped_sectors.append(sec)
        mapped_industries.append(ind)
      df["Sector"] = mapped_sectors
      df["Industry"] = mapped_industries
    return df
  except Exception:
    return pd.DataFrame()

# ==========================================
# 3. SIDEBAR CONTROLS & STRATEGY PRESETS
# ==========================================
st.sidebar.markdown("### 💾 Saved Filter Presets")
preset_names = list(st.session_state.filter_presets.keys())
selected_preset_name = st.sidebar.selectbox(
    "Load or Update Strategy Preset:",
    options=preset_names,
    index=0 if preset_names else None,
    key="sb_preset_selector",
)

col_load, col_update, col_del = st.sidebar.columns([1.2, 1.2, 0.9])
with col_load:
  if st.sidebar.button("⚡ Load", use_container_width=True, type="primary"):
    if selected_preset_name in st.session_state.filter_presets:
      p = st.session_state.filter_presets[selected_preset_name]
      st.session_state["f_exchanges"] = p.get("exchanges", ["NSE", "BSE"])
      st.session_state["f_sectors"] = p.get("sectors", [])
      st.session_state["f_industries"] = p.get("industries", [])
      st.session_state["f_indices"] = p.get("indices", [])
      st.session_state["f_min_mcap"] = p.get("min_mcap_cr", 1000)
      st.session_state["f_vol_period"] = p.get("vol_period_days", 60)
      st.session_state["f_min_vol"] = p.get("min_vol_cr", 5.0)
      st.session_state["f_en_ipo"] = p.get("en_ipo", False)
      st.session_state["f_ipo"] = p.get(
          "ipo_filter", "All Stocks (No IPO Filter)"
      )
      st.session_state["f_en_eps_q"] = p.get("en_eps_q", False)
      st.session_state["f_min_eps_q"] = p.get("min_eps_q", 10.0)
      st.session_state["f_en_sales_q"] = p.get("en_sales_q", False)
      st.session_state["f_min_sales_q"] = p.get("min_sales_q", 10.0)
      st.session_state["f_allow_na_growth"] = p.get("allow_na_growth", True)
      st.session_state["f_en_rs_rating"] = p.get("en_rs_rating", True)
      st.session_state["f_min_rs_rating"] = p.get("min_rs_rating", 80)
      st.session_state["f_en_adr"] = p.get("en_adr", True)
      st.session_state["f_min_adr"] = p.get("min_adr", 2.25)
      st.session_state["f_en_52l"] = p.get("en_above_52l", True)
      st.session_state["f_min_52l"] = p.get("min_above_52l", 20)
      st.session_state["f_en_52h"] = p.get("en_below_52h", True)
      st.session_state["f_max_52h"] = p.get("max_below_52h", 30)
      st.session_state["f_en_circuit"] = p.get("en_circuit", True)

      c_val = p.get("circuit_val", ["2%", "5%", "10%"])
      if isinstance(c_val, str):
        c_val = ["2%", "5%", "10%"]
      st.session_state["f_circuit_val"] = c_val

      st.session_state["f_perf_labels"] = p.get(
          "selected_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
      )
      st.session_state["f_max_res"] = p.get("max_results", 4000)

      ma_cfgs = p.get("ma_configs", [])
      for i, cfg in enumerate(ma_cfgs, 1):
        st.session_state[f"ma_{i}_en"] = cfg.get("en", False)
        st.session_state[f"ma_{i}_type"] = cfg.get("type", "SMA")
        st.session_state[f"ma_{i}_len"] = cfg.get("len", 50)

      perf_cfgs = p.get("perf_configs", {})
      for c_key, p_val in perf_cfgs.items():
        st.session_state[f"en_perf_{c_key}"] = p_val.get("en", False)
        st.session_state[f"val_perf_{c_key}"] = p_val.get("val", 0.0)

      st.success(f"Loaded '{selected_preset_name}'!")
      st.rerun()

with col_update:
  if st.sidebar.button("🔄 Update", use_container_width=True):
    if selected_preset_name in st.session_state.filter_presets:
      st.session_state.filter_presets[selected_preset_name] = {
          "exchanges": st.session_state.get("f_exchanges", ["NSE", "BSE"]),
          "sectors": st.session_state.get("f_sectors", []),
          "industries": st.session_state.get("f_industries", []),
          "indices": st.session_state.get("f_indices", []),
          "min_mcap_cr": st.session_state.get("f_min_mcap", 1000),
          "vol_period_days": st.session_state.get("f_vol_period", 60),
          "min_vol_cr": st.session_state.get("f_min_vol", 5.0),
          "en_ipo": st.session_state.get("f_en_ipo", False),
          "ipo_filter": st.session_state.get(
              "f_ipo", "All Stocks (No IPO Filter)"
          ),
          "en_eps_q": st.session_state.get("f_en_eps_q", False),
          "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
          "en_sales_q": st.session_state.get("f_en_sales_q", False),
          "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
          "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
          "en_rs_rating": st.session_state.get("f_en_rs_rating", True),
          "min_rs_rating": st.session_state.get("f_min_rs_rating", 80),
          "en_adr": st.session_state.get("f_en_adr", True),
          "min_adr": st.session_state.get("f_min_adr", 2.25),
          "en_above_52l": st.session_state.get("f_en_52l", True),
          "min_above_52l": st.session_state.get("f_min_52l", 20),
          "en_below_52h": st.session_state.get("f_en_52h", True),
          "max_below_52h": st.session_state.get("f_max_52h", 30),
          "en_circuit": st.session_state.get("f_en_circuit", True),
          "circuit_val": st.session_state.get(
              "f_circuit_val", ["2%", "5%", "10%"]
          ),
          "selected_perf_labels": st.session_state.get(
              "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
          ),
          "max_results": st.session_state.get("f_max_res", 4000),
          "ma_configs": [
              {
                  "en": st.session_state.get(f"ma_{i}_en", False),
                  "type": st.session_state.get(f"ma_{i}_type", "SMA"),
                  "len": st.session_state.get(f"ma_{i}_len", 50),
              }
              for i in range(1, 6)
          ],
          "perf_configs": {
              col: {
                  "en": st.session_state.get(f"en_perf_{col}", False),
                  "val": st.session_state.get(f"val_perf_{col}", 0.0),
              }
              for col in [
                  "Perf.W",
                  "Perf.1M",
                  "Perf.3M",
                  "Perf.6M",
                  "Perf.YTD",
                  "Perf.Y",
              ]
          },
      }
      save_filter_presets(st.session_state.filter_presets)
      st.success(f"Updated '{selected_preset_name}'!")
      st.rerun()

with col_del:
  if st.sidebar.button("🗑️ Del", use_container_width=True):
    if (
        len(preset_names) > 1
        and selected_preset_name in st.session_state.filter_presets
    ):
      del st.session_state.filter_presets[selected_preset_name]
      save_filter_presets(st.session_state.filter_presets)
      st.rerun()

with st.sidebar.expander("➕ Save Current Filters as New Preset"):
  with st.form("save_preset_form", clear_on_submit=True):
    new_preset_name = st.text_input(
        "Preset Name:", placeholder="e.g., Breakout Momentum"
    )
    if st.form_submit_button("💾 Save Preset", use_container_width=True):
      if new_preset_name:
        st.session_state.filter_presets[new_preset_name] = {
            "exchanges": st.session_state.get("f_exchanges", ["NSE", "BSE"]),
            "sectors": st.session_state.get("f_sectors", []),
            "industries": st.session_state.get("f_industries", []),
            "indices": st.session_state.get("f_indices", []),
            "min_mcap_cr": st.session_state.get("f_min_mcap", 1000),
            "vol_period_days": st.session_state.get("f_vol_period", 60),
            "min_vol_cr": st.session_state.get("f_min_vol", 5.0),
            "en_ipo": st.session_state.get("f_en_ipo", False),
            "ipo_filter": st.session_state.get(
                "f_ipo", "All Stocks (No IPO Filter)"
            ),
            "en_eps_q": st.session_state.get("f_en_eps_q", False),
            "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
            "en_sales_q": st.session_state.get("f_en_sales_q", False),
            "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
            "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
            "en_rs_rating": st.session_state.get("f_en_rs_rating", True),
            "min_rs_rating": st.session_state.get("f_min_rs_rating", 80),
            "en_adr": st.session_state.get("f_en_adr", True),
            "min_adr": st.session_state.get("f_min_adr", 2.25),
            "en_above_52l": st.session_state.get("f_en_52l", True),
            "min_above_52l": st.session_state.get("f_min_52l", 20),
            "en_below_52h": st.session_state.get("f_en_52h", True),
            "max_below_52h": st.session_state.get("f_max_52h", 30),
            "en_circuit": st.session_state.get("f_en_circuit", True),
            "circuit_val": st.session_state.get(
                "f_circuit_val", ["2%", "5%", "10%"]
            ),
            "selected_perf_labels": st.session_state.get(
                "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
            ),
            "max_results": st.session_state.get("f_max_res", 4000),
            "ma_configs": [
                {
                    "en": st.session_state.get(f"ma_{i}_en", False),
                    "type": st.session_state.get(f"ma_{i}_type", "SMA"),
                    "len": st.session_state.get(f"ma_{i}_len", 50),
                }
                for i in range(1, 6)
            ],
            "perf_configs": {
                col: {
                    "en": st.session_state.get(f"en_perf_{col}", False),
                    "val": st.session_state.get(f"val_perf_{col}", 0.0),
                }
                for col in [
                    "Perf.W",
                    "Perf.1M",
                    "Perf.3M",
                    "Perf.6M",
                    "Perf.YTD",
                    "Perf.Y",
                ]
            },
        }
        save_filter_presets(st.session_state.filter_presets)
        st.success(f"Saved preset '{new_preset_name}'!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚡ **Auto-Update Enabled:** Adjusting any filter below updates results"
    " instantly."
)

# ----------------------------------------------------
# 1. EXCHANGE & UNIVERSE
# ----------------------------------------------------
st.sidebar.header("1. Exchange & Universe")
exchange_choice = st.sidebar.multiselect(
    "Select Exchanges:",
    options=["NSE", "BSE"],
    default=st.session_state.get("f_exchanges", ["NSE", "BSE"]),
    key="f_exchanges",
)

st.sidebar.markdown("---")
st.sidebar.header("🏛️ Official NSE Filters & Indices")
sector_options = list(INDIAN_SECTOR_HIERARCHY.keys())
sector_choice = st.sidebar.multiselect(
    "NSE Sector (22 Economic Sectors):",
    options=sector_options,
    default=st.session_state.get("f_sectors", []),
    key="f_sectors",
)

if sector_choice:
  industry_options = []
  for sec in sector_choice:
    industry_options.extend(INDIAN_SECTOR_HIERARCHY.get(sec, []))
  industry_options = sorted(list(set(industry_options)))
else:
  all_industries = [
      ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds
  ]
  industry_options = sorted(list(set(all_industries)))

industry_choice = st.sidebar.multiselect(
    "NSE Industry (59 Distinct Classifications):",
    options=industry_options,
    default=st.session_state.get("f_industries", []),
    key="f_industries",
)

exhaustive_indices = [
    "NIFTY 50",
    "NIFTY NEXT 50",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY 500",
    "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50",
    "NIFTY SMALLCAP 100",
    "NIFTY SMALLCAP 250",
    "NIFTY MICROCAP 250",
    "NIFTY TOTAL MARKET",
    "NIFTY LARGEMIDCAP 250",
    "NIFTY BANK",
    "NIFTY AUTO",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY MEDIA",
    "NIFTY METAL",
    "NIFTY PHARMA",
    "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK",
    "NIFTY REALTY",
    "NIFTY HEALTHCARE",
    "NIFTY CONSUMER DURABLES",
    "NIFTY OIL & GAS",
    "NIFTY COMMODITIES",
    "NIFTY INDIA CONSUMPTION",
    "NIFTY CPSE",
    "NIFTY INFRASTRUCTURE",
    "NIFTY MNC",
    "NIFTY PSE",
    "NIFTY SERVICES SECTOR",
    "NIFTY ENERGY",
    "NIFTY HOUSING",
    "NIFTY INDIA DEFENCE",
    "NIFTY INDIA DIGITAL",
    "NIFTY INDIA MANUFACTURING",
    "NIFTY MOBILITY",
    "BSE SENSEX",
    "BSE 100",
    "BSE 200",
    "BSE 500",
]
index_choice = st.sidebar.multiselect(
    "Index Membership (45+ Available):",
    options=exhaustive_indices,
    default=st.session_state.get("f_indices", []),
    key="f_indices",
)

st.sidebar.markdown("---")
st.sidebar.header("2. Fundamental, Liquidity & IPO Date")
min_mcap_cr = st.sidebar.number_input(
    "Min Market Cap (₹ Crores):",
    min_value=0,
    value=st.session_state.get("f_min_mcap", 1000),
    step=100,
    key="f_min_mcap",
)
vol_period_days = st.sidebar.selectbox(
    "Average Volume Period:",
    options=[10, 30, 60, 90],
    index=[10, 30, 60, 90].index(st.session_state.get("f_vol_period", 60)),
    format_func=lambda x: f"{x} Days",
    key="f_vol_period",
)
min_vol_cr = st.sidebar.number_input(
    f"Min {vol_period_days}D Avg Rupee Volume (₹ Cr):",
    min_value=0.0,
    value=st.session_state.get("f_min_vol", 5.0),
    step=0.5,
    key="f_min_vol",
)

en_ipo = st.sidebar.checkbox(
    "Filter by IPO Listing Age",
    value=st.session_state.get("f_en_ipo", False),
    key="f_en_ipo",
)
ipo_filter_options = [
    "All Stocks (No IPO Filter)",
    "Recent IPO: Past 1 Month",
    "Recent IPO: Past 3 Months",
    "Recent IPO: Past 6 Months",
    "Recent IPO: Past 1 Year",
    "Recent IPO: Past 2 Years",
    "Seasoned: Listed > 1 Year Ago",
    "Seasoned: Listed > 3 Years Ago",
    "Seasoned: Listed > 5 Years Ago",
]
ipo_filter_choice = st.sidebar.selectbox(
    "IPO Date / Listing Age Filter:",
    options=ipo_filter_options,
    index=ipo_filter_options.index(
        st.session_state.get("f_ipo", "All Stocks (No IPO Filter)")
    ),
    key="f_ipo",
    disabled=not en_ipo,
)

# ----------------------------------------------------
# 2B. QUARTERLY YOY FUNDAMENTAL GROWTH
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("2B. Quarterly YoY Fundamental Growth")

en_eps_q = st.sidebar.checkbox(
    "Filter by Min Quarterly YoY EPS Growth %",
    value=st.session_state.get("f_en_eps_q", False),
    key="f_en_eps_q",
)
min_eps_q = st.sidebar.slider(
    "Min Quarterly YoY EPS Growth %:",
    min_value=-50.0,
    max_value=200.0,
    value=float(st.session_state.get("f_min_eps_q", 10.0)),
    step=5.0,
    key="f_min_eps_q",
    disabled=not en_eps_q,
)

en_sales_q = st.sidebar.checkbox(
    "Filter by Min Quarterly YoY Sales Growth %",
    value=st.session_state.get("f_en_sales_q", False),
    key="f_en_sales_q",
)
min_sales_q = st.sidebar.slider(
    "Min Quarterly YoY Sales Growth %:",
    min_value=-50.0,
    max_value=200.0,
    value=float(st.session_state.get("f_min_sales_q", 10.0)),
    step=5.0,
    key="f_min_sales_q",
    disabled=not en_sales_q,
)

allow_na_growth = st.sidebar.checkbox(
    "Pass stocks with missing (N/A) TradingView growth data",
    value=st.session_state.get("f_allow_na_growth", True),
    key="f_allow_na_growth",
    help=(
        "TradingView sometimes lags on quarterly data for Indian small-caps."
        " Checking this ensures great technical setups aren't dropped."
    ),
)

st.sidebar.markdown("---")
st.sidebar.header("3. Trend & Moving Averages (5 MAs)")
default_ma_configs = [
    {"en": True, "type": "EMA", "len": 21},
    {"en": True, "type": "SMA", "len": 50},
    {"en": False, "type": "SMA", "len": 200},
    {"en": False, "type": "EMA", "len": 10},
    {"en": False, "type": "SMA", "len": 150},
]
ma_filters = []
for i, cfg in enumerate(default_ma_configs, 1):
  c1, c2, c3 = st.sidebar.columns([1.8, 1.6, 1.6])
  with c1:
    en = st.checkbox(
        f"MA {i} >",
        value=st.session_state.get(f"ma_{i}_en", cfg["en"]),
        key=f"ma_{i}_en",
    )
  with c2:
    m_type = st.selectbox(
        "Type",
        ["EMA", "SMA"],
        index=0 if st.session_state.get(f"ma_{i}_type", cfg["type"]) == "EMA" else 1,
        key=f"ma_{i}_type",
        label_visibility="collapsed",
    )
  with c3:
    m_len = st.number_input(
        "Len",
        min_value=1,
        max_value=500,
        value=st.session_state.get(f"ma_{i}_len", cfg["len"]),
        step=1,
        key=f"ma_{i}_len",
        label_visibility="collapsed",
    )
  col_name = f"{m_type}{m_len}"
  ma_filters.append({
      "enabled": en,
      "type": m_type,
      "length": m_len,
      "col_name": col_name,
      "label": f"{m_type} {m_len}",
  })

# ----------------------------------------------------
# 4. VOLATILITY & 52-WEEK RANGE
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("4. Volatility & 52-Week Range")

en_adr = st.sidebar.checkbox(
    "Filter by Min ADR %",
    value=st.session_state.get("f_en_adr", True),
    key="f_en_adr",
)
min_adr = st.sidebar.slider(
    "Min ADR % (TradingView Standard):",
    min_value=0.0,
    max_value=10.0,
    value=st.session_state.get("f_min_adr", 2.25),
    step=0.25,
    key="f_min_adr",
    disabled=not en_adr,
)

en_52l = st.sidebar.checkbox(
    "Filter by Min % Above 52-Week Low",
    value=st.session_state.get("f_en_52l", True),
    key="f_en_52l",
)
min_above_52l = st.sidebar.slider(
    "Min % Above 52-Week Low:",
    min_value=0,
    max_value=100,
    value=st.session_state.get("f_min_52l", 20),
    step=5,
    key="f_min_52l",
    disabled=not en_52l,
)

en_52h = st.sidebar.checkbox(
    "Filter by Max % Below 52-Week High",
    value=st.session_state.get("f_en_52h", True),
    key="f_en_52h",
)
max_below_52h = st.sidebar.slider(
    "Max % Below 52-Week High:",
    min_value=0,
    max_value=50,
    value=st.session_state.get("f_max_52h", 30),
    step=5,
    key="f_max_52h",
    disabled=not en_52h,
)

# ----------------------------------------------------
# 4B. CIRCUIT LIMIT & FREEZE PROTECTION (MULTI-SELECT)
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("4B. Circuit Limit Protection")

c_cb, c_sb = st.sidebar.columns([1.1, 1.4])
with c_cb:
  en_circuit = st.checkbox(
      "Exclude Circuit:",
      value=st.session_state.get("f_en_circuit", True),
      key="f_en_circuit",
  )
with c_sb:
  circuit_options = ["2%", "5%", "10%"]
  default_circuits = st.session_state.get("f_circuit_val", ["2%", "5%", "10%"])
  if isinstance(default_circuits, str):
    default_circuits = ["2%", "5%", "10%"]

  circuit_choice = st.multiselect(
      "Circuit Bands to Exclude:",
      options=circuit_options,
      default=default_circuits,
      key="f_circuit_val",
      disabled=not en_circuit,
      label_visibility="collapsed",
      placeholder="Select bands...",
  )

st.sidebar.markdown("---")
st.sidebar.header("5. Performance % & IBD RS Rating")

en_rs_rating = st.sidebar.checkbox(
    "Filter by Min IBD RS Rating (1-99)",
    value=st.session_state.get("f_en_rs_rating", True),
    key="f_en_rs_rating",
)
min_rs_rating = st.sidebar.slider(
    "Min IBD RS Rating (1-99 Market Percentile):",
    min_value=1,
    max_value=99,
    value=st.session_state.get("f_min_rs_rating", 80),
    step=1,
    key="f_min_rs_rating",
    disabled=not en_rs_rating,
)

perf_options = {
    "1 Week": ("Perf.W", "Perf % 1W"),
    "1 Month": ("Perf.1M", "Perf % 1M"),
    "3 Months": ("Perf.3M", "Perf % 3M"),
    "6 Months": ("Perf.6M", "Perf % 6M"),
    "YTD": ("Perf.YTD", "Perf % YTD"),
    "1 Year": ("Perf.Y", "Perf % 1Y"),
}
selected_perf_labels = st.sidebar.multiselect(
    "Display Perf % Columns in Table:",
    options=list(perf_options.keys()),
    default=st.session_state.get(
        "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
    ),
    key="f_perf_labels",
)

st.sidebar.caption("Optional Minimum Performance % Thresholds:")
perf_filters = []
p_cols = st.sidebar.columns(2)
for idx, (label, (tv_col, disp_label)) in enumerate(perf_options.items()):
  with p_cols[idx % 2]:
    en_p = st.checkbox(
        f"Min {label} >",
        value=st.session_state.get(f"en_perf_{tv_col}", False),
        key=f"en_perf_{tv_col}",
    )
    min_val = st.number_input(
        f"Min % ({label})",
        min_value=-100.0,
        max_value=10000.0,
        value=st.session_state.get(f"val_perf_{tv_col}", 0.0),
        step=5.0,
        key=f"val_perf_{tv_col}",
        label_visibility="collapsed",
    )
    perf_filters.append({
        "enabled": en_p,
        "label": label,
        "col_name": tv_col,
        "display_label": disp_label,
        "min_val": min_val,
    })

st.sidebar.markdown("---")
st.sidebar.header("6. Display Settings")
max_results = st.sidebar.slider(
    "Max Results to Fetch (4000+ Covers Entire Liquid Universe):",
    min_value=1000,
    max_value=5000,
    value=st.session_state.get("f_max_res", 4000),
    step=250,
    key="f_max_res",
)

# ==========================================
# 4. TOP-LEVEL WORKSPACE TABS (4 TABS NOW)
# ==========================================
tab_screener, tab_watchlists, tab_tradebook, tab_market_health = st.tabs([
    "🔎 CAN SLIM Screener & Rotation",
    "⭐ Multi-Watchlist Studio & TV Free-Tier Bridge",
    "📓 Tradebook & Portfolio Journal",
    "🏥 Market Health & Sector Rotation",
])

# ==========================================
# TAB 1: CAN SLIM SCREENER & ROTATION
# ==========================================
with tab_screener:
  ma_cols_to_fetch = list(set([m["col_name"] for m in ma_filters]))
  tv_vol_col = f"average_volume_{vol_period_days}d_calc"

  with st.spinner("⚡ Scanning Indian Equities & Applying Active Filters..."):
    results_df = fetch_screener_data(
        exchange_choice,
        min_mcap_cr,
        vol_period_days,
        ma_cols_to_fetch,
        max_results,
    )
    nse_bands_map = get_nse_circuit_bands()

    if not results_df.empty:
      p_3m = pd.to_numeric(results_df.get("Perf.3M"), errors="coerce").fillna(0)
      p_6m = pd.to_numeric(results_df.get("Perf.6M"), errors="coerce").fillna(0)
      p_1y = pd.to_numeric(results_df.get("Perf.Y"), errors="coerce").fillna(0)

      results_df["_ibd_raw_score"] = (2 * p_3m) + p_6m + p_1y
      rs_pct = results_df["_ibd_raw_score"].rank(pct=True, na_option="keep")
      results_df["RS Rating"] = (
          (rs_pct * 98 + 1).round().fillna(1).astype(int)
      )

      st.session_state.rs_rating_map = dict(
          zip(results_df["name"].str.upper(), results_df["RS Rating"])
      )

  if results_df.empty:
    st.warning(
        "No stocks matched your criteria. Adjust your sidebar filters or switch"
        " to another Preset."
    )
  else:
    df = results_df.copy()
    df = df[df["exchange"].isin(exchange_choice)]
    if "type" in df.columns:
      df = df[df["type"] == "stock"]
    df = df.drop_duplicates(subset=["name"], keep="first")

    mapped_sectors, mapped_industries = [], []
    for _, row in df.iterrows():
      sec, ind = map_to_indian_classification(
          row.get("industry", ""), row.get("sector", "")
      )
      mapped_sectors.append(sec)
      mapped_industries.append(ind)
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries

    total_sector_counts = df["Sector"].value_counts()
    total_industry_counts = df["Industry"].value_counts()

    if sector_choice:
      df = df[df["Sector"].isin(sector_choice)]
    if industry_choice:
      df = df[df["Industry"].isin(industry_choice)]

    if "index" in df.columns:
      df["Index"] = df["index"].fillna("N/A")
    else:
      df["Index"] = "N/A"

    if index_choice:
      def matches_index(val):
        if pd.isna(val) or val == "N/A" or not val:
          return False
        val_str = str(val).upper()
        for idx_name in index_choice:
          if idx_name.upper() in val_str:
            return True
        return False
      df = df[df["Index"].apply(matches_index)]

    df["EPS Q YoY %"] = coalesce_columns(df, EPS_Q_ALIASES).round(2)
    df["Sales Q YoY %"] = coalesce_columns(df, SALES_Q_ALIASES).round(2)

    if en_eps_q:
      if allow_na_growth:
        df = df[(df["EPS Q YoY %"] >= min_eps_q) | (df["EPS Q YoY %"].isna())]
      else:
        df = df[df["EPS Q YoY %"] >= min_eps_q]

    if en_sales_q:
      if allow_na_growth:
        df = df[
            (df["Sales Q YoY %"] >= min_sales_q) | (df["Sales Q YoY %"].isna())
        ]
      else:
        df = df[df["Sales Q YoY %"] >= min_sales_q]

    if en_rs_rating and "RS Rating" in df.columns:
      df = df[df["RS Rating"] >= min_rs_rating]

    df = add_clean_ipo_date_col(df)

    if en_ipo and ipo_filter_choice != "All Stocks (No IPO Filter)":
      now_dt = pd.Timestamp.now()
      if ipo_filter_choice == "Recent IPO: Past 1 Month":
        cutoff = now_dt - pd.DateOffset(months=1)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 3 Months":
        cutoff = now_dt - pd.DateOffset(months=3)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 6 Months":
        cutoff = now_dt - pd.DateOffset(months=6)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 1 Year":
        cutoff = now_dt - pd.DateOffset(years=1)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 2 Years":
        cutoff = now_dt - pd.DateOffset(years=2)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Seasoned: Listed > 1 Year Ago":
        cutoff = now_dt - pd.DateOffset(years=1)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]
      elif ipo_filter_choice == "Seasoned: Listed > 3 Years Ago":
        cutoff = now_dt - pd.DateOffset(years=3)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]
      elif ipo_filter_choice == "Seasoned: Listed > 5 Years Ago":
        cutoff = now_dt - pd.DateOffset(years=5)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]

    numeric_cols = [
        "market_cap_basic",
        "close",
        "change",
        "high",
        "low",
        "open",
        "volume",
        tv_vol_col,
        "ADR",
        "price_52_week_high",
        "price_52_week_low",
    ] + ma_cols_to_fetch
    for c in numeric_cols:
      if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["ADR_pct"] = (df["ADR"] / df["close"]) * 100
    if en_adr:
      df = df[df["ADR_pct"] >= min_adr]

    for ma in ma_filters:
      c_name = ma["col_name"]
      if ma["enabled"] and c_name in df.columns:
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df[c_name] = pd.to_numeric(df[c_name], errors="coerce")
        df = df[df["close"] > df[c_name]]

    if tv_vol_col in df.columns:
      df["val_traded_inr"] = df["close"] * df[tv_vol_col]
      df = df[df["val_traded_inr"] >= (min_vol_cr * 10_000_000)]

    if "price_52_week_low" in df.columns:
      pct_above_low = (
          (df["close"] - df["price_52_week_low"]) / df["price_52_week_low"]
      ) * 100
      if en_52l:
        df = df[pct_above_low >= min_above_52l]

    if "price_52_week_high" in df.columns:
      pct_below_high = (
          (df["price_52_week_high"] - df["close"]) / df["price_52_week_high"]
      ) * 100
      if en_52h:
        df = df[pct_below_high <= max_below_52h]

    for pf in perf_filters:
      if pf["enabled"] and pf["col_name"] in df.columns:
        df[pf["col_name"]] = pd.to_numeric(df[pf["col_name"]], errors="coerce")
        df = df[df[pf["col_name"]] >= pf["min_val"]]

    if en_circuit and circuit_choice:
      df["high"] = pd.to_numeric(df["high"], errors="coerce")
      df["low"] = pd.to_numeric(df["low"], errors="coerce")
      df["open"] = pd.to_numeric(df["open"], errors="coerce")
      df["change_abs"] = df["change"].abs()

      is_full_day_freeze = df["high"] == df["low"]
      is_at_high_lock = (df["close"] == df["high"]) & (df["high"] > df["open"])
      is_at_low_lock = (df["close"] == df["low"]) & (df["low"] < df["open"])
      is_locked_extreme = is_at_high_lock | is_at_low_lock

      selected_band_nums = [b.replace("%", "") for b in circuit_choice]

      def is_circuit_hit(row):
        sym = str(row["name"]).strip().upper()
        band_val = nse_bands_map.get(sym, "")
        c_abs = row["change_abs"]
        is_locked = row["high"] == row["low"] or (
            (row["close"] == row["high"] or row["close"] == row["low"])
            and row["high"] != row["open"]
        )

        if band_val in selected_band_nums:
          return True

        if is_locked:
          if "2" in selected_band_nums and 1.97 <= c_abs <= 2.00:
            return True
          if "5" in selected_band_nums and 4.97 <= c_abs <= 5.00:
            return True
          if "10" in selected_band_nums and 9.97 <= c_abs <= 10.00:
            return True

        return False

      df["_is_circuit_excluded"] = df.apply(is_circuit_hit, axis=1)
      df = df[~df["_is_circuit_excluded"] & ~is_full_day_freeze]
      df = df.drop(columns=["_is_circuit_excluded"])

    if df.empty:
      st.warning(
          "No stocks passed all criteria. Try broadening your NSE"
          " Sector/Industry selections or RS Rating slider."
      )
    else:
      total_passed = len(df)
      rc = st.session_state.reset_counter

      st.subheader("📊 Scan Summary & Market Rotation")
      tab_sector_sum, tab_industry_sum = st.tabs(
          ["🛠️ Sector Summary", "🏢 Basic Industry Summary"]
      )

      with tab_sector_sum:
        sec_counts = df["Sector"].value_counts().reset_index()
        sec_counts.columns = ["Sector", "Stocks Passed"]
        sec_counts["% Share"] = (
            (sec_counts["Stocks Passed"] / total_passed) * 100
        ).round(1)
        sec_counts["% of Sector Total"] = sec_counts.apply(
            lambda r: round(
                (
                    r["Stocks Passed"]
                    / total_sector_counts.get(r["Sector"], 1)
                )
                * 100,
                1,
            ),
            axis=1,
        )
        c_chart1, c_table1 = st.columns([1.1, 1.3])
        with c_chart1:
          fig_sec = px.pie(
              sec_counts, names="Sector", values="Stocks Passed", hole=0.55
          )
          fig_sec.update_traces(textinfo="percent", textposition="inside")
          fig_sec.update_layout(
              annotations=[
                  dict(
                      text=f"<b>Total Stocks:<br>{total_passed}</b>",
                      x=0.5,
                      y=0.5,
                      font_size=16,
                      showarrow=False,
                  )
              ],
              showlegend=False,
              margin=dict(t=20, b=10, l=20, r=20),
              height=360,
          )
          chart_ev_sec = st.plotly_chart(
              fig_sec,
              use_container_width=True,
              on_select="rerun",
              selection_mode="points",
              key=f"sec_chart_{rc}",
          )
        with c_table1:
          table_ev_sec = st.dataframe(
              sec_counts,
              use_container_width=True,
              hide_index=True,
              height=360,
              on_select="rerun",
              selection_mode="multi-row",
              column_config=get_left_aligned_column_config(sec_counts.columns),
              key=f"sec_table_{rc}",
          )
        sel_sec_chart = parse_chart_selection_multi(chart_ev_sec)
        sel_sec_table = parse_table_selection_multi(
            table_ev_sec, sec_counts, "Sector"
        )
        active_sectors = sel_sec_table if sel_sec_table else sel_sec_chart

      with tab_industry_sum:
        if active_sectors:
          df_ind_source = df[df["Sector"].isin(active_sectors)]
          ind_total_passed = len(df_ind_source)
          st.info(
              "🏢 **Hierarchical View:** Showing Basic Industries inside"
              f" **{', '.join(active_sectors)}** ({ind_total_passed} Stocks)"
          )
        else:
          df_ind_source = df
          ind_total_passed = total_passed
        ind_counts = df_ind_source["Industry"].value_counts().reset_index()
        ind_counts.columns = ["Basic Industry", "Stocks Passed"]
        ind_counts["% Share"] = (
            (ind_counts["Stocks Passed"] / max(ind_total_passed, 1)) * 100
        ).round(1)
        ind_counts["% of Industry Total"] = ind_counts.apply(
            lambda r: round(
                (
                    r["Stocks Passed"]
                    / total_industry_counts.get(r["Basic Industry"], 1)
                )
                * 100,
                1,
            ),
            axis=1,
        )
        sec_hash = "_".join(sorted(active_sectors)) if active_sectors else "all"
        c_chart2, c_table2 = st.columns([1.1, 1.3])
        with c_chart2:
          fig_ind = px.pie(
              ind_counts,
              names="Basic Industry",
              values="Stocks Passed",
              hole=0.55,
          )
          fig_ind.update_traces(textinfo="percent", textposition="inside")
          fig_ind.update_layout(
              annotations=[
                  dict(
                      text=f"<b>Total Stocks:<br>{ind_total_passed}</b>",
                      x=0.5,
                      y=0.5,
                      font_size=16,
                      showarrow=False,
                  )
              ],
              showlegend=False,
              margin=dict(t=20, b=10, l=20, r=20),
              height=360,
          )
          chart_ev_ind = st.plotly_chart(
              fig_ind,
              use_container_width=True,
              on_select="rerun",
              selection_mode="points",
              key=f"ind_chart_{rc}_{sec_hash}",
          )
        with c_table2:
          table_ev_ind = st.dataframe(
              ind_counts,
              use_container_width=True,
              hide_index=True,
              height=360,
              on_select="rerun",
              selection_mode="multi-row",
              column_config=get_left_aligned_column_config(ind_counts.columns),
              key=f"ind_table_{rc}_{sec_hash}",
          )
        sel_ind_chart = parse_chart_selection_multi(chart_ev_ind)
        sel_ind_table = parse_table_selection_multi(
            table_ev_ind, ind_counts, "Basic Industry"
        )
        active_industries = (
            sel_ind_table if sel_ind_table else sel_ind_chart
        )

      st.session_state.active_scan_summary = {
          "total_passed": total_passed,
          "sectors": sec_counts.head(10).to_dict(orient="records"),
          "industries": ind_counts.head(10).to_dict(orient="records"),
      }

      st.markdown("---")
      df_display = df.copy()
      if active_sectors:
        df_display = df_display[df_display["Sector"].isin(active_sectors)]
      if active_industries:
        df_display = df_display[df_display["Industry"].isin(active_industries)]

      if active_sectors or active_industries:
        filter_labels = []
        if active_sectors:
          filter_labels.append(f"**Sector:** {', '.join(active_sectors)}")
        if active_industries:
          filter_labels.append(f"**Industry:** {', '.join(active_industries)}")
        col_info, col_reset = st.columns([3, 1])
        with col_info:
          st.info(
              f"🔍 **Active Drilldown:** {' | '.join(filter_labels)} ({len(df_display)} Stocks)"
          )
        with col_reset:
          if st.button(
              "🔄 Reset Scan Results (Show All)",
              type="primary",
              use_container_width=True,
          ):
            st.session_state.reset_counter += 1
            st.rerun()

      df_display["S.No._num"] = range(1, len(df_display) + 1)
      df_display["Market Cap (₹ Cr)"] = (
          df_display["market_cap_basic"] / 10_000_000
      ).round(2)
      vol_display_label = f"{vol_period_days}D Close×AvgVol (₹ Cr)"
      df_display[vol_display_label] = (
          df_display["val_traded_inr"] / 10_000_000
      ).round(2)
      df_display["Close"] = df_display["close"].round(2)
      df_display["Change %"] = df_display["change"].round(2)
      df_display["ADR %"] = df_display["ADR_pct"].round(2)
      df_display["TV_Symbol"] = df_display["exchange"] + ":" + df_display["name"]
      df_display["TV_Link"] = (
          "https://www.tradingview.com/chart/?symbol=NSE:" + df_display["name"]
      )
      df_display["Screener_Link"] = (
          "https://www.screener.in/company/"
          + df_display["name"]
          + "/consolidated/"
      )

      wl_dot_map = {}
      for wl_name, sym_list in st.session_state.watchlists.items():
        dot = (
            "🔵"
            if "breakout" in wl_name.lower()
            else (
                "🟢"
                if "focus" in wl_name.lower()
                else (
                    "🟡"
                    if "weekly" in wl_name.lower()
                    else (
                        "🟠"
                        if "bulk" in wl_name.lower()
                        else "🔴" if "sold" in wl_name.lower() else "🟣"
                    )
                )
            )
        )
        for s in sym_list:
          bare_s = s.split(":")[-1].strip().upper()
          wl_dot_map[bare_s] = wl_dot_map.get(bare_s, "") + dot

      df_display["WL_Dots"] = (
          df_display["name"].str.upper().map(wl_dot_map).fillna("")
      )
      df_display["S.No."] = df_display.apply(
          lambda r: (
              f"{r['S.No._num']} {r['WL_Dots']}".strip()
              if r["WL_Dots"]
              else str(r["S.No._num"])
          ),
          axis=1,
      )

      df_display["_in_band"] = (
          df_display["name"].str.upper().map(nse_bands_map)
      )
      cond1 = df_display["_in_band"].isin(["2", "5", "10"])
      cond2 = (
          (df_display["high"] == df_display["low"])
          & (df_display["high"] > 0)
          & (df_display["change"].abs() > 1.5)
      )
      df_display["_is_circuit_badge"] = cond1 | cond2
      df_display["name"] = df_display["name"].where(
          ~df_display["_is_circuit_badge"], df_display["name"] + " 🚨"
      )

      fund_badge_map = {
          k: f"{v.get('verdict')} ({v.get('date', '')})"
          for k, v in st.session_state.fundamental_reports.items()
      }
      df_display["Fundamental"] = (
          df_display["name"].str.replace(" 🚨", "").str.upper().map(
              fund_badge_map
          ).fillna("⚪ Not Analyzed")
      )

      canonical_perf_order = [
          "Perf % 1W",
          "Perf % 1M",
          "Perf % 3M",
          "Perf % 6M",
          "Perf % YTD",
          "Perf % 1Y",
      ]
      for label, (tv_col, disp_label) in perf_options.items():
        if tv_col in df_display.columns:
          df_display[disp_label] = pd.to_numeric(
              df_display[tv_col], errors="coerce"
          ).round(2)

      active_perf_labels = [
          p
          for p in canonical_perf_order
          if p in [perf_options[lbl][1] for lbl in selected_perf_labels]
          and p in df_display.columns
      ]

      active_ma_labels = []
      for ma in ma_filters:
        if ma["enabled"] and ma["col_name"] in df_display.columns:
          df_display[ma["label"]] = df_display[ma["col_name"]].round(2)
          active_ma_labels.append(ma["label"])

      table_columns = (
          [
              "S.No.",
              "TV_Symbol",
              "name",
              "RS Rating",
              "Fundamental",
              "Close",
              "Change %",
              "ADR %",
              "EPS Q YoY %",
              "Sales Q YoY %",
          ]
          + active_perf_labels
          + active_ma_labels
          + [
              vol_display_label,
              "Market Cap (₹ Cr)",
              "IPO Date",
              "Sector",
              "Industry",
              "TV_Link",
              "Screener_Link",
          ]
      )

      st.subheader(f"📋 Scan Results ({len(df_display)} Stocks Found)")
      st.caption(
          "💡 **RS Rating:** IBD-Style 1-99 Percentile Score calculated across"
          " 4,000+ listed Indian equities before filters."
      )

      sc = st.session_state.scan_sel_counter
      table_ev_scan = st.dataframe(
          df_display[table_columns],
          use_container_width=True,
          hide_index=True,
          on_select="rerun",
          selection_mode="multi-row",
          column_config=get_left_aligned_column_config(table_columns),
          key=f"scan_table_{rc}_{sc}",
      )

      selected_rows = parse_table_selection_multi(
          table_ev_scan, df_display, "TV_Symbol"
      )

      st.markdown("---")
      f_col1, f_col2, f_col3 = st.columns([2.0, 1.3, 1.7])

      with f_col1:
        if len(selected_rows) == 1:
          active_sym = selected_rows[0]
          clean_sym_name = active_sym.split(":")[-1].strip().upper()
          if st.button(
              f"📖 Open Saved Report Modal ({clean_sym_name})",
              type="primary",
              use_container_width=True,
              key=f"fund_btn_view_scan_{rc}_{sc}",
          ):
            show_fundamental_modal(active_sym)
        else:
          st.button(
              "📖 Select a Single Stock Row to Open Report",
              type="secondary",
              disabled=True,
              use_container_width=True,
              key=f"fund_btn_view_scan_dis_{rc}_{sc}",
          )

      with f_col2:
        force_reanalyze_scan = st.checkbox(
            "Force Re-Analyze Existing",
            value=False,
            key=f"force_scan_{rc}_{sc}",
            help="If checked, AI will re-fetch Screener PDFs even if a report already exists.",
        )

      with f_col3:
        run_batch_scan = st.button(
            f"⚡ Analyze Selected ({len(selected_rows)})",
            type="primary",
            use_container_width=True,
            disabled=len(selected_rows) == 0,
            key=f"fund_btn_run_scan_{rc}_{sc}",
        )

      if run_batch_scan and len(selected_rows) > 0:
        with st.status(
            "🧠 Minervini Fundamental AI Analyst — Active Queue",
            expanded=True,
        ) as status_box:
          p_bar = st.progress(0.0)
          for idx, sym in enumerate(selected_rows):
            clean_sym = sym.split(":")[-1].strip().upper()
            if (
                clean_sym in st.session_state.fundamental_reports
                and not force_reanalyze_scan
            ):
              status_box.write(
                  f"⏩ **[{idx + 1}/{len(selected_rows)}] {clean_sym}:** Report"
                  " already exists in Gist. (Check 'Force Re-Analyze' to"
                  " overwrite)"
              )
            else:
              status_box.write(
                  f"⚙️ **[{idx + 1}/{len(selected_rows)}] {clean_sym}:**"
                  " Downloading Screener.in PDFs & Running Gemini 2.5"
                  " Flash..."
              )
              run_gemini_fundamental_analysis(
                  clean_sym,
                  st.session_state.fundamental_reports,
                  status_log=status_box,
              )

            p_bar.progress((idx + 1) / len(selected_rows))

          status_box.update(
              label="✅ Batch AI Analysis Complete! Updating Table...",
              state="complete",
              expanded=True,
          )
          time.sleep(1.5)
          st.rerun()

      st.markdown("---")
      cw1, cw2, cw3, cw4 = st.columns([1.8, 1.5, 2.0, 0.9])
      with cw1:
        wl_keys = list(st.session_state.watchlists.keys())
        target_wl = st.selectbox(
            "Select Target Watchlist to Add Setups:",
            options=wl_keys,
            index=(
                wl_keys.index(st.session_state.active_watchlist_name)
                if st.session_state.active_watchlist_name in wl_keys
                else 0
            ),
            key="wl_table_target_select",
        )
      with cw2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(
            f"➕ Add Selected ({len(selected_rows)}) to Watchlist",
            type="primary",
            use_container_width=True,
            disabled=len(selected_rows) == 0,
        ):
          current_list = st.session_state.watchlists[target_wl]
          added_cnt = 0
          for sym in selected_rows:
            if sym not in current_list:
              current_list.append(sym)
              added_cnt += 1
          save_watchlists(st.session_state.watchlists)
          st.success(
              f"✅ Successfully added {added_cnt} new stocks to"
              f" **{target_wl}**!"
          )
      with cw3:
        st.caption("➕ Create New Watchlist:")
        with st.form("create_wl_scan_form", clear_on_submit=True):
          fc1, fc2 = st.columns([1.7, 1.0])
          with fc1:
            new_scan_wl = st.text_input(
                "Create New Watchlist",
                placeholder="e.g., Telecom Breakout",
                label_visibility="collapsed",
            )
          with fc2:
            if st.form_submit_button("➕ Create", use_container_width=True):
              if (
                  new_scan_wl
                  and new_scan_wl not in st.session_state.watchlists
              ):
                st.session_state.watchlists[new_scan_wl] = []
                st.session_state.active_watchlist_name = new_scan_wl
                save_watchlists(st.session_state.watchlists)
                st.success(f"Created '{new_scan_wl}'!")
                st.rerun()
      with cw4:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("💡 Check rows above to enable actions.")

      st.markdown("---")
      if len(selected_rows) > 0:
        st.subheader(
            f"📋 Copy Selected Setups to TradingView ({len(selected_rows)}"
            " Stocks)"
        )
        st.code(", ".join(selected_rows), language="text")

      filtered_symbols = df_display["TV_Symbol"].tolist()
      st.subheader(
          f"📋 Copy Filtered Scan Results to TradingView"
          f" ({len(filtered_symbols)} Stocks)"
      )

      if filtered_symbols:
        batch_size = 30
        batches = [
            filtered_symbols[i : i + batch_size]
            for i in range(0, len(filtered_symbols), batch_size)
        ]

        if len(batches) > 1:
          st.markdown("#### ⚡ 30-Symbol TradingView Hot-Swap Batches")
          st.caption(
              "💡 **Free Tier Bypass Workflow:** In TradingView, press **`Ctrl+A`**"
              " → **`Backspace`** → **`Ctrl+V`** in your TV watchlist box to"
              " hot-swap 30 stocks at a time!"
          )

          batch_labels = []
          for idx, b_list in enumerate(batches):
            start_num = idx * batch_size + 1
            end_num = idx * batch_size + len(b_list)
            batch_labels.append(f"Batch {idx + 1} ({start_num}–{end_num})")

          selected_batch_label = st.selectbox(
              "Select 30-Symbol Batch to Copy:",
              options=batch_labels,
              key=f"scan_batch_dropdown_{rc}_{sc}",
          )
          selected_idx = batch_labels.index(selected_batch_label)
          st.code(", ".join(batches[selected_idx]), language="text")

        with st.expander(
            "📋 View / Copy All Tickers (Full Unbatched String)",
            expanded=False,
        ):
          tv_watchlist_string = ", ".join(filtered_symbols)
          st.code(tv_watchlist_string, language="text")

# ==========================================
# TAB 2: WATCHLIST STUDIO & TV FREE-TIER BRIDGE
# ==========================================
with tab_watchlists:
  st.subheader(
      "⭐ Multi-Watchlist Studio (Bypasses TV Free Tier 30-Symbol Cap)"
  )

  col_sel, col_new, col_del = st.columns([2.4, 1.8, 0.8])
  with col_sel:
    wl_names = list(st.session_state.watchlists.keys())
    active_wl = st.selectbox(
        "Select Active Watchlist:",
        options=wl_names,
        index=(
            wl_names.index(st.session_state.active_watchlist_name)
            if st.session_state.active_watchlist_name in wl_names
            else 0
        ),
        key="wl_active_selector",
    )
    st.session_state.active_watchlist_name = active_wl

    with st.form("inline_rename_form", clear_on_submit=True):
      r_col1, r_col2 = st.columns([2.6, 1.0])
      with r_col1:
        new_inline_name = st.text_input(
            "✏️ Rename Selected Watchlist:",
            value=active_wl,
            label_visibility="collapsed",
            placeholder="Rename watchlist...",
        )
      with r_col2:
        if st.form_submit_button("✏️ Rename", use_container_width=True):
          if (
              new_inline_name
              and new_inline_name != active_wl
              and new_inline_name not in st.session_state.watchlists
          ):
            old_name = active_wl
            st.session_state.watchlists[new_inline_name] = (
                st.session_state.watchlists.pop(old_name)
            )
            st.session_state.active_watchlist_name = new_inline_name
            save_watchlists(st.session_state.watchlists)
            st.success(f"Renamed to '{new_inline_name}'!")
            st.rerun()

  with col_new:
    with st.form("create_wl_form", clear_on_submit=True):
      new_wl_name = st.text_input(
          "Create New Watchlist:",
          placeholder="e.g., Sector: Capital Goods Build",
      )
      if st.form_submit_button(
          "➕ Create Watchlist", use_container_width=True
      ):
        if new_wl_name and new_wl_name not in st.session_state.watchlists:
          st.session_state.watchlists[new_wl_name] = []
          st.session_state.active_watchlist_name = new_wl_name
          save_watchlists(st.session_state.watchlists)
          st.success(f"Created Watchlist: {new_wl_name}")
          st.rerun()
  with col_del:
    st.markdown("<br>", unsafe_allow_html=True)
    if len(wl_names) > 1:
      if st.button(
          "🗑️ Delete", type="secondary", use_container_width=True
      ):
        del st.session_state.watchlists[active_wl]
        save_watchlists(st.session_state.watchlists)
        st.session_state.active_watchlist_name = list(
            st.session_state.watchlists.keys()
        )[0]
        st.rerun()

  current_symbols = st.session_state.watchlists[active_wl]

  with st.expander(
      "📥 Import / Paste Tickers & Backup Local Text (.TXT) Library",
      expanded=False,
  ):
    ci1, ci2 = st.columns([2, 1])
    with ci1:
      pasted_text = st.text_area(
          "Paste Tickers from TradingView (Comma, Space, or Newline"
          " separated):",
          placeholder="NSE:RELIANCE, BSE:TCS, ZOMATO, TRENT\nNSE:HAL",
      )
      if st.button(
          "➕ Import Tickers into Current Watchlist", type="primary"
      ):
        parsed_symbols = parse_pasted_tickers(pasted_text)
        current_list = st.session_state.watchlists[active_wl]
        added = 0
        for s in parsed_symbols:
          if s not in current_list:
            current_list.append(s)
            added += 1
        save_watchlists(st.session_state.watchlists)
        st.success(f"✅ Imported {added} symbols into **{active_wl}**!")
        st.rerun()
    with ci2:
      st.markdown("#### 💾 Backup & Restore Disk Library (.TXT)")
      txt_export_str = json.dumps(st.session_state.watchlists, indent=2)
      st.download_button(
          label="📥 Download Watchlists (.TXT)",
          data=txt_export_str,
          file_name="my_india_watchlists.txt",
          mime="text/plain",
          use_container_width=True,
      )
      uploaded_file = st.file_uploader(
          "Restore Watchlists (.TXT):",
          type=["txt", "json"],
          label_visibility="collapsed",
      )
      if uploaded_file is not None:
        try:
          loaded_wls = json.load(uploaded_file)
          if isinstance(loaded_wls, dict):
            st.session_state.watchlists = loaded_wls
            st.session_state.active_watchlist_name = list(loaded_wls.keys())[0]
            save_watchlists(loaded_wls)
            st.success("✅ Watchlists restored successfully!")
            st.rerun()
        except Exception:
          st.error(
              "Invalid file format. Ensure it is a valid backup file."
          )

  if not current_symbols:
    st.info(
        f"The watchlist **{active_wl}** is currently empty. Add setups from the"
        " Screener tab or paste symbols above!"
    )
  else:
    if len(current_symbols) > 1:
      st.markdown("---")
      st.markdown("#### ⚡ Priority Mover & Rank Jumper")
      rm_col1, rm_col2, rm_col3, rm_col4, rm_col5, rm_col6, rm_col7 = st.columns(
          [2.0, 0.8, 0.8, 0.8, 0.8, 1.1, 0.8]
      )
      with rm_col1:
        move_target_sym = st.selectbox(
            "Select Ticker to Move:",
            options=current_symbols,
            key=f"rapid_mover_sym_{active_wl}",
            label_visibility="collapsed",
        )
      with rm_col2:
        st.button(
            "🔝 Top",
            on_click=cb_move_top,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col3:
        st.button(
            "⬆️ Up",
            on_click=cb_move_up,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col4:
        st.button(
            "⬇️ Down",
            on_click=cb_move_down,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col5:
        st.button(
            "🔻 Bottom",
            on_click=cb_move_bottom,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col6:
        target_rank = st.number_input(
            "Rank #",
            min_value=1,
            max_value=len(current_symbols),
            value=1,
            step=1,
            key=f"rapid_mover_rank_{active_wl}",
            label_visibility="collapsed",
        )
      with rm_col7:
        st.button(
            "🎯 Jump",
            type="primary",
            on_click=cb_jump_rank,
            args=(active_wl, move_target_sym, target_rank),
            use_container_width=True,
        )

    with st.spinner(
        f"📡 Enriching {len(current_symbols)} Tickers with Live Price &"
        " ADR%..."
    ):
      enriched_df = fetch_watchlist_enrichMENT(current_symbols)

    ordered_df = pd.DataFrame({
        "TV_Symbol": current_symbols,
        "name": [s.split(":")[-1].strip().upper() for s in current_symbols],
    })

    if not enriched_df.empty:
      merged_df = ordered_df.merge(
          enriched_df, on="name", how="left", suffixes=("", "_tv")
      )
      if "TV_Symbol_tv" in merged_df.columns:
        merged_df["TV_Symbol"] = merged_df["TV_Symbol_tv"].fillna(
            merged_df["TV_Symbol"]
        )
    else:
      merged_df = ordered_df.copy()
      for col_name in [
          "Close",
          "Change %",
          "ADR_pct",
          "EPS Q YoY %",
          "Sales Q YoY %",
          "Perf % 1W",
          "Perf % 1M",
          "Perf % 3M",
          "Perf % 6M",
          "Market Cap (₹ Cr)",
          "IPO Date",
          "Sector",
          "Industry",
      ]:
        merged_df[col_name] = "N/A"

    merged_df["Close"] = merged_df.get("Close", pd.Series()).fillna("N/A")
    merged_df["Change %"] = merged_df.get("Change %", pd.Series()).fillna("N/A")
    merged_df["ADR %"] = merged_df.get("ADR_pct", pd.Series()).fillna("N/A")
    merged_df["EPS Q YoY %"] = merged_df.get(
        "EPS Q YoY %", pd.Series()
    ).fillna("N/A")
    merged_df["Sales Q YoY %"] = merged_df.get(
        "Sales Q YoY %", pd.Series()
    ).fillna("N/A")
    merged_df["Perf % 1W"] = merged_df.get("Perf % 1W", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 1M"] = merged_df.get("Perf % 1M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 3M"] = merged_df.get("Perf % 3M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 6M"] = merged_df.get("Perf % 6M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Market Cap (₹ Cr)"] = merged_df.get(
        "Market Cap (₹ Cr)", pd.Series()
    ).fillna("N/A")
    merged_df["IPO Date"] = merged_df.get("IPO Date", pd.Series()).fillna("N/A")
    merged_df["Sector"] = merged_df.get("Sector", pd.Series()).fillna(
        "Unclassified"
    )
    merged_df["Industry"] = merged_df.get("Industry", pd.Series()).fillna(
        "Unclassified"
    )

    merged_df["S.No._num"] = range(1, len(merged_df) + 1)
    merged_df["TV_Link"] = (
        "https://www.tradingview.com/chart/?symbol=" + merged_df["TV_Symbol"]
    )
    merged_df["Screener_Link"] = (
        "https://www.screener.in/company/"
        + merged_df["name"]
        + "/consolidated/"
    )

    wl_dot_map_wl = {}
    for wl_name, sym_list in st.session_state.watchlists.items():
      dot = (
          "🔵"
          if "breakout" in wl_name.lower()
          else (
              "🟢"
              if "focus" in wl_name.lower()
              else (
                  "🟡"
                  if "weekly" in wl_name.lower()
                  else (
                      "🟠"
                      if "bulk" in wl_name.lower()
                      else "🔴" if "sold" in wl_name.lower() else "🟣"
                  )
              )
          )
      )
      for s in sym_list:
        bare_s = s.split(":")[-1].strip().upper()
        wl_dot_map_wl[bare_s] = wl_dot_map_wl.get(bare_s, "") + dot

    merged_df["WL_Dots"] = (
        merged_df["name"].str.upper().map(wl_dot_map_wl).fillna("")
    )
    merged_df["S.No."] = merged_df.apply(
        lambda r: (
            f"{r['S.No._num']} {r['WL_Dots']}".strip()
            if r["WL_Dots"]
            else str(r["S.No._num"])
        ),
        axis=1,
    )

    nse_bands_map = get_nse_circuit_bands()
    merged_df["_is_circuit_badge"] = merged_df.apply(
        lambda r: is_circuit_stock_badge(r, nse_bands_map), axis=1
    )
    merged_df["name"] = merged_df["name"].where(
        ~merged_df["_is_circuit_badge"], merged_df["name"] + " 🚨"
    )

    rs_map = st.session_state.get("rs_rating_map", {})
    merged_df["RS Rating"] = (
        merged_df["name"]
        .str.replace(" 🚨", "")
        .str.upper()
        .map(rs_map)
        .fillna("N/A")
    )

    merged_df["Fundamental"] = (
        merged_df["name"]
        .str.replace(" 🚨", "")
        .str.upper()
        .map(
            {
                k: f"{v.get('verdict')} ({v.get('date', '')})"
                for k, v in st.session_state.fundamental_reports.items()
            }
        )
        .fillna("⚪ Not Analyzed")
    )

    wl_cols = [
        "S.No.",
        "TV_Symbol",
        "name",
        "RS Rating",
        "Fundamental",
        "Close",
        "Change %",
        "ADR %",
        "EPS Q YoY %",
        "Sales Q YoY %",
        "Perf % 1W",
        "Perf % 1M",
        "Perf % 3M",
        "Perf % 6M",
        "Market Cap (₹ Cr)",
        "IPO Date",
        "Sector",
        "Industry",
        "TV_Link",
        "Screener_Link",
    ]

    st.markdown(
        f"### ⭐ Watchlist: **{active_wl}** ({len(current_symbols)} Stocks)"
    )
    st.caption(
        "💡 **Watchlist Color Legend:** 🔵 Post Breakout Monitor | 🟢 Focus"
        " List | 🟡 Weekly Focus | 🟠 Scan Bulk | 🔴 Sold Stocks | 🟣 Custom"
        " | 🚨 **Circuit Band / Freeze**"
    )

    wsc = st.session_state.wl_sel_counter
    wl_table_event = st.dataframe(
        merged_df[wl_cols],
        use_container_width=True,
        hide_index=True,
        height=460,
        on_select="rerun",
        selection_mode="multi-row",
        column_config=get_left_aligned_column_config(wl_cols),
        key=f"wl_manage_table_{wsc}",
    )

    sel_symbols = parse_table_selection_multi(
        wl_table_event, merged_df, "TV_Symbol"
    )

    st.markdown("---")
    wf_col1, wf_col2, wf_col3 = st.columns([2.0, 1.3, 1.7])

    with wf_col1:
      if len(sel_symbols) == 1:
        active_sym_wl = sel_symbols[0]
        clean_wl_sym_name = active_sym_wl.split(":")[-1].strip().upper()
        if st.button(
            f"📖 Open Saved Report Modal ({clean_wl_sym_name})",
            type="primary",
            use_container_width=True,
            key=f"fund_btn_view_wl_{wsc}",
        ):
          show_fundamental_modal(active_sym_wl)
      else:
        st.button(
            "📖 Select a Single Stock Row to Open Report",
            type="secondary",
            disabled=True,
            use_container_width=True,
            key=f"fund_btn_view_wl_dis_{wsc}",
        )

    with wf_col2:
      force_reanalyze_wl = st.checkbox(
          "Force Re-Analyze Existing",
          value=False,
          key=f"force_wl_{wsc}",
          help="If checked, AI will re-fetch Screener PDFs even if a report already exists.",
      )

    with wf_col3:
      run_batch_wl = st.button(
          f"⚡ Analyze Selected ({len(sel_symbols)})",
          type="primary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
          key=f"fund_btn_run_wl_{wsc}",
      )

    if run_batch_wl and len(sel_symbols) > 0:
      with st.status(
          "🧠 Minervini Fundamental AI Analyst — Active Queue",
          expanded=True,
      ) as status_box_wl:
        p_bar = st.progress(0.0)
        for idx, sym in enumerate(sel_symbols):
          clean_sym = sym.split(":")[-1].strip().upper()
          if (
              clean_sym in st.session_state.fundamental_reports
              and not force_reanalyze_wl
          ):
            status_box_wl.write(
                f"⏩ **[{idx + 1}/{len(sel_symbols)}] {clean_sym}:** Report"
                " already exists in Gist. (Check 'Force Re-Analyze' to"
                " overwrite)"
            )
          else:
            status_box_wl.write(
                f"⚙️ **[{idx + 1}/{len(sel_symbols)}] {clean_sym}:**"
                " Downloading Screener.in PDFs & Running Gemini 2.5 Flash..."
            )
            run_gemini_fundamental_analysis(
                clean_sym,
                st.session_state.fundamental_reports,
                status_log=status_box_wl,
            )

          p_bar.progress((idx + 1) / len(sel_symbols))

        status_box_wl.update(
            label="✅ Batch AI Analysis Complete! Updating Table...",
            state="complete",
            expanded=True,
        )
        time.sleep(1.5)
        st.rerun()

    c_rem, c_clr, c_promo_sel, c_promo_btn = st.columns([1.5, 1.2, 2.0, 1.5])
    with c_rem:
      if st.button(
          f"🗑️ Remove Selected ({len(sel_symbols)})",
          type="secondary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
      ):
        for sym in sel_symbols:
          if sym in st.session_state.watchlists[active_wl]:
            st.session_state.watchlists[active_wl].remove(sym)
        save_watchlists(st.session_state.watchlists)
        st.rerun()
    with c_clr:
      if st.button(
          "🧹 Clear Selection",
          type="secondary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
          key="clear_wl_sel_btn",
      ):
        st.session_state.wl_sel_counter += 1
        st.rerun()
    with c_promo_sel:
      promo_target = st.selectbox(
          "Promote Selected To Target Watchlist:",
          options=(
              [name for name in wl_names if name != active_wl]
              if len(wl_names) > 1
              else wl_names
          ),
          key="promo_target_select",
          label_visibility="collapsed",
      )
    with c_promo_btn:
      if st.button(
          f"➡️ Promote Selected ({len(sel_symbols)})",
          type="primary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
      ):
        target_list = st.session_state.watchlists[promo_target]
        cnt = 0
        for sym in sel_symbols:
          if sym not in target_list:
            target_list.append(sym)
            cnt += 1
        save_watchlists(st.session_state.watchlists)
        st.success(f"✅ Promoted {cnt} stocks to **{promo_target}**!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ 30-Symbol TradingView Hot-Swap Batches")
    st.caption(
        "💡 **Free Tier Bypass Workflow:** In TradingView, press **`Ctrl+A`**"
        " → **`Backspace`** → **`Ctrl+V`** in your TV watchlist box to"
        " hot-swap 30 stocks at a time!"
    )

    batch_size = 30
    batches = [
        current_symbols[i : i + batch_size]
        for i in range(0, len(current_symbols), batch_size)
    ]

    if len(batches) > 1:
      batch_labels = []
      for idx, b_list in enumerate(batches):
        start_num = idx * batch_size + 1
        end_num = idx * batch_size + len(b_list)
        batch_labels.append(f"Batch {idx + 1} ({start_num}–{end_num})")

      selected_wl_batch_label = st.selectbox(
          "Select 30-Symbol Batch to Copy:",
          options=batch_labels,
          key=f"wl_batch_select_{active_wl}_{wsc}",
      )
      selected_wl_idx = batch_labels.index(selected_wl_batch_label)
      st.code(", ".join(batches[selected_wl_idx]), language="text")
    else:
      st.code(", ".join(current_symbols), language="text")

    with st.expander(
        "📋 View / Copy All Tickers (Full Unbatched String)",
        expanded=False,
    ):
      st.code(", ".join(current_symbols), language="text")

# ==========================================
# TAB 3: TRADEBOOK & PORTFOLIO RISK JOURNAL
# ==========================================
with tab_tradebook:
  st.subheader("📓 Tradebook & Institutional Risk Journal")
  st.caption(
      "Lot-based execution tracking, $1R$ risk-reward metrics, portfolio"
      " heat, Nifty 500 Shadow Benchmark Alpha, and Trading Performance Calendar."
  )

  tb_data = st.session_state.tradebook
  starting_cap = float(tb_data.get("config", {}).get("starting_capital", 500000.0))
  all_trades = tb_data.get("trades", [])

  df_mm_tb = load_market_monitor_data()

  open_trade_tickers = [
      t["ticker"] for t in all_trades if t.get("status") == "OPEN"
  ]
  live_price_map = {}
  if open_trade_tickers:
    enriched_tb = fetch_watchlist_enrichMENT(open_trade_tickers)
    if not enriched_tb.empty and "Close" in enriched_tb.columns:
      live_price_map = dict(
          zip(enriched_tb["name"].str.upper(), enriched_tb["Close"])
      )

  cash_balance = starting_cap
  realized_pnl_total = 0.0
  unrealized_pnl_total = 0.0
  open_invested_total = 0.0
  open_current_val_total = 0.0
  open_risk_total = 0.0

  bench_bought_total = 0.0
  bench_current_val_total = 0.0
  trades_beating_bench = 0
  evaluated_bench_trades = 0

  latest_nifty_close = (
      float(df_mm_tb.iloc[0]["Nifty 500 Close"])
      if not df_mm_tb.empty and "Nifty 500 Close" in df_mm_tb.columns
      else 23700.0
  )

  processed_trade_rows = []
  trade_signatures = {}
  sig_counter = 1

  # Assign SL Nos to unique combinations
  for tr in all_trades:
    sig = f"{tr.get('ticker')}_{tr.get('date_bought')}_{tr.get('buy_price')}"
    if sig not in trade_signatures:
      trade_signatures[sig] = sig_counter
      sig_counter += 1

  for idx, tr in enumerate(all_trades, 1):
    status = tr.get("status", "OPEN")
    ticker = tr.get("ticker", "N/A")
    clean_sym = ticker.split(":")[-1].strip().upper()

    sh_bought = int(tr.get("shares_bought", 0))
    sh_sold = int(tr.get("shares_sold", 0))
    sh_rem = max(0, sh_bought - sh_sold)

    b_price = float(tr.get("buy_price", 0.0))
    sl_price = float(tr.get("initial_sl", b_price * 0.92))
    date_b = tr.get("date_bought", "N/A")

    sig = f"{ticker}_{date_b}_{b_price}"
    sl_num_shared = trade_signatures[sig]

    unit_risk = max(0.01, b_price - sl_price)

    nifty_buy_close = float(
        tr.get(
            "nifty500_buy_close",
            fetch_nifty500_close_on_date(date_b, df_mm_tb),
        )
    )

    if status == "OPEN":
      curr_price = float(
          live_price_map.get(clean_sym, tr.get("current_price", b_price))
      )
      sold_price = None
      date_s = "N/A"

      capital_invested = sh_rem * b_price
      curr_val = sh_rem * curr_price
      booked_val = 0.0

      realized_pnl = 0.0
      unrealized_pnl = sh_rem * (curr_price - b_price)

      sh_risk = sh_rem * unit_risk
      open_risk_total += sh_risk

      open_invested_total += capital_invested
      open_current_val_total += curr_val
      unrealized_pnl_total += unrealized_pnl

      cash_balance -= capital_invested

      bench_val = (
          capital_invested * (latest_nifty_close / nifty_buy_close)
          if nifty_buy_close > 0
          else capital_invested
      )
      bench_bought_total += capital_invested
      bench_current_val_total += bench_val

      lot_return_pct = (
          ((curr_price - b_price) / b_price) * 100 if b_price > 0 else 0.0
      )
      bench_return_pct = (
          ((latest_nifty_close - nifty_buy_close) / nifty_buy_close) * 100
          if nifty_buy_close > 0
          else 0.0
      )
      if lot_return_pct > bench_return_pct:
        trades_beating_bench += 1
      evaluated_bench_trades += 1

      realized_r = 0.0
      status_label = "🟢 OPEN"

    else:  # CLOSED LOT
      sold_price = float(tr.get("sell_price", b_price))
      curr_price = sold_price
      date_s = tr.get("date_sold", "N/A")

      capital_invested = sh_sold * b_price
      booked_val = sh_sold * sold_price
      curr_val = 0.0

      realized_pnl = sh_sold * (sold_price - b_price)
      unrealized_pnl = 0.0

      realized_pnl_total += realized_pnl
      cash_balance += (booked_val - capital_invested)

      nifty_sell_close = float(
          tr.get(
              "nifty500_sell_close",
              fetch_nifty500_close_on_date(date_s, df_mm_tb),
          )
      )
      bench_val = (
          capital_invested * (nifty_sell_close / nifty_buy_close)
          if nifty_buy_close > 0
          else capital_invested
      )
      bench_bought_total += capital_invested
      bench_current_val_total += bench_val

      lot_return_pct = (
          ((sold_price - b_price) / b_price) * 100 if b_price > 0 else 0.0
      )
      bench_return_pct = (
          ((nifty_sell_close - nifty_buy_close) / nifty_buy_close) * 100
          if nifty_buy_close > 0
          else 0.0
      )
      if lot_return_pct > bench_return_pct:
        trades_beating_bench += 1
      evaluated_bench_trades += 1

      realized_r = (
          realized_pnl / (sh_sold * unit_risk) if (sh_sold * unit_risk) > 0 else 0.0
      )

      if realized_pnl > 0:
        status_label = "🔵 WIN"
      elif realized_pnl < 0:
        status_label = "🔴 LOSS"
      else:
        status_label = "⚪ SCRATCH"

    tot_return_inr = realized_pnl + unrealized_pnl
    abs_return_pct = (
        ((curr_price - b_price) / b_price) * 100 if b_price > 0 else 0.0
    )

    processed_trade_rows.append({
        "trade_id": tr.get("id"),
        "S.No._num": sl_num_shared,
        "Signature": sig,
        "Ticker": ticker,
        "Status": status_label,
        "Shares Bought": sh_bought,
        "Date Bought": date_b,
        "Buy Price (₹)": b_price,
        "Initial SL (₹)": sl_price,
        "Current / Sold Price (₹)": curr_price,
        "Gain / Loss (₹)": tot_return_inr,
        "Realized R": f"{realized_r:+.2f}R" if status == "CLOSED" else "0.00R",
        "Shares Sold": sh_sold,
        "Booked Value (₹)": booked_val,
        "Realised Gains (₹)": realized_pnl,
        "Shares Remaining": sh_rem,
        "Abs Return %": abs_return_pct,
        "Unrealised Value (₹)": unrealized_pnl,
        "Capital Invested (₹)": capital_invested,
        "Current Value (₹)": curr_val,
        "Date Sold": date_s,
    })

  total_portfolio_nav = cash_balance + open_current_val_total
  portfolio_heat_pct = (
      (open_risk_total / max(total_portfolio_nav, 1.0)) * 100
  )

  bench_total_nav = cash_balance + bench_current_val_total
  alpha_inr = total_portfolio_nav - bench_total_nav
  portfolio_net_return_pct = (
      ((total_portfolio_nav - starting_cap) / starting_cap) * 100
      if starting_cap > 0
      else 0.0
  )
  bench_net_return_pct = (
      ((bench_total_nav - starting_cap) / starting_cap) * 100
      if starting_cap > 0
      else 0.0
  )
  alpha_pct = portfolio_net_return_pct - bench_net_return_pct

  # --- TOP METRIC DASHBOARD BAR ---
  c1, c2, c3, c4, c5 = st.columns(5)
  with c1:
    st.metric(
        "Starting Capital",
        f"₹{starting_cap:,.2f}",
        f"Cash: ₹{cash_balance:,.2f}",
    )
  with c2:
    st.metric(
        "Portfolio NAV",
        f"₹{total_portfolio_nav:,.2f}",
        f"{portfolio_net_return_pct:+.2f}% Net",
    )
  with c3:
    st.metric(
        "Open Invested Value",
        f"₹{open_invested_total:,.2f}",
        f"Live: ₹{open_current_val_total:,.2f}",
    )
  with c4:
    st.metric(
        "Realized P&L",
        f"₹{realized_pnl_total:,.2f}",
        f"Unrealized: ₹{unrealized_pnl_total:,.2f}",
    )
  with c5:
    heat_color = (
        "🟢 SAFE"
        if portfolio_heat_pct <= 5.0
        else "🟡 MODERATE" if portfolio_heat_pct <= 7.0 else "🔴 HIGH"
    )
    st.metric("Portfolio Heat %", f"{portfolio_heat_pct:.2f}%", heat_color)

  st.markdown("---")
  st.caption("🏆 **Nifty 500 Shadow Benchmark Comparison (Dollar-Weighted):**")
  ac1, ac2, ac3, ac4 = st.columns(4)
  with ac1:
    st.metric("Portfolio Net Return", f"{portfolio_net_return_pct:+.2f}%")
  with ac2:
    st.metric("Nifty 500 Shadow Return", f"{bench_net_return_pct:+.2f}%")
  with ac3:
    st.metric("Alpha (Excess Return)", f"{alpha_pct:+.2f}%", f"₹{alpha_inr:,.2f}")
  with ac4:
    beat_pct = (
        (trades_beating_bench / max(evaluated_bench_trades, 1)) * 100
        if evaluated_bench_trades > 0
        else 0.0
    )
    st.metric("Beat Index Win Rate", f"{beat_pct:.1f}%")

  st.markdown("---")

  ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.2, 1.2, 1.2, 1.2, 2.0])
  with ctrl_col5:
    tb_filter = st.radio(
        "Display Filter:",
        options=["All Positions", "Open Positions Only", "Closed Trades Only"],
        horizontal=True,
    )

  df_tb_display = pd.DataFrame(processed_trade_rows)

  if not df_tb_display.empty:
    if tb_filter == "Open Positions Only":
      df_tb_display = df_tb_display[
          df_tb_display["Status"].str.contains("OPEN")
      ]
    elif tb_filter == "Closed Trades Only":
      df_tb_display = df_tb_display[
          df_tb_display["Status"].str.contains("WIN|LOSS|SCRATCH")
      ]

    if total_portfolio_nav > 0:
      df_tb_display["Allocation %"] = df_tb_display["Current Value (₹)"].apply(
          lambda v: (v / total_portfolio_nav) * 100 if v > 0 else 0.0
      )
    else:
      df_tb_display["Allocation %"] = 0.0

  tb_selected_rows = st.session_state.get("tb_manage_table", {}).get("selection", {}).get("rows", [])
  selected_trade_id = None
  if tb_selected_rows and len(tb_selected_rows) > 0 and not df_tb_display.empty:
    row_idx = tb_selected_rows[0]
    if row_idx < len(df_tb_display):
      selected_trade_id = df_tb_display.iloc[row_idx]["trade_id"]

  @st.dialog("➕ Log New Position Entry", width="medium")
  def show_buy_modal():
    active_wl = st.session_state.get(
        "active_watchlist_name",
        list(st.session_state.watchlists.keys())[0],
    )
    wl_tickers = st.session_state.watchlists.get(active_wl, [])
    st.caption(
        f"📍 Populating tickers strictly from active watchlist: **{active_wl}**"
    )

    with st.form("buy_trade_form", clear_on_submit=True):
      sel_ticker = st.selectbox(
          "Select Ticker from Active Watchlist:", options=wl_tickers
      )
      custom_ticker = st.text_input(
          "OR Type Custom Ticker (e.g. NSE:BEL):", placeholder="NSE:BEL"
      )
      final_ticker = (
          custom_ticker.strip().upper()
          if custom_ticker.strip()
          else sel_ticker
      )

      b_date = st.date_input("Date Bought:", value=date.today())
      b_shares = st.number_input(
          "Shares Bought:", min_value=1, value=100, step=1
      )
      b_price = st.number_input(
          "Buy Price (₹):", min_value=0.1, value=100.0, step=1.0
      )
      b_sl = st.number_input(
          "Initial Stop Loss Price (₹):",
          min_value=0.01,
          value=round(b_price * 0.92, 2),
          step=1.0,
      )

      outlay = b_shares * b_price
      risk_amount = b_shares * (b_price - b_sl)
      st.caption(
          f"💡 Total Outlay: **₹{outlay:,.2f}** | Initial Risk (1R):"
          f" **₹{risk_amount:,.2f}**"
      )

      if st.form_submit_button("💾 Save Position Entry", use_container_width=True):
        if final_ticker:
          date_s_str = b_date.strftime("%Y-%m-%d")
          nifty_close_buy = fetch_nifty500_close_on_date(date_s_str, df_mm_tb)

          new_trade = {
              "id": f"TRD_{int(time.time()*1000)}",
              "ticker": final_ticker,
              "status": "OPEN",
              "date_bought": date_s_str,
              "shares_bought": int(b_shares),
              "shares_sold": 0,
              "buy_price": float(b_price),
              "initial_sl": float(b_sl),
              "nifty500_buy_close": nifty_close_buy,
          }
          st.session_state.tradebook["trades"].append(new_trade)
          save_tradebook(st.session_state.tradebook)
          st.success(f"✅ Logged position for **{final_ticker}**!")
          st.rerun()

  @st.dialog("➖ Log Exit or Partial Sell", width="medium")
  def show_sell_modal(preselected_trade_id=None):
    open_lots = [
        t
        for t in st.session_state.tradebook["trades"]
        if t.get("status") == "OPEN"
    ]
    if not open_lots:
      st.info("No open trades currently in your Tradebook!")
      return

    lot_options = {
        (
            f"{t['ticker']} (Bought {t['date_bought']} |"
            f" {t['shares_bought'] - t['shares_sold']} shs @ ₹{t['buy_price']})"
        ): t
        for t in open_lots
    }
    
    default_index = 0
    if preselected_trade_id:
        for i, (lbl, t) in enumerate(lot_options.items()):
            if t.get("id") == preselected_trade_id:
                default_index = i
                break

    sel_label = st.selectbox(
        "Select Active Position Lot to Sell:", options=list(lot_options.keys()), index=default_index
    )
    sel_lot = lot_options[sel_label]

    max_sell = sel_lot["shares_bought"] - sel_lot["shares_sold"]

    with st.form("sell_trade_form", clear_on_submit=True):
      s_date = st.date_input("Date Sold:", value=date.today())
      s_shares = st.number_input(
          "Shares Sold:", min_value=1, max_value=max_sell, value=max_sell, step=1
      )
      s_price = st.number_input(
          "Sell Price (₹):", min_value=0.1, value=sel_lot["buy_price"], step=1.0
      )

      if st.form_submit_button("💾 Execute Exit / Partial Sell", use_container_width=True):
        date_s_str = s_date.strftime("%Y-%m-%d")
        nifty_close_sell = fetch_nifty500_close_on_date(date_s_str, df_mm_tb)

        if s_shares == max_sell:
          sel_lot["status"] = "CLOSED"
          sel_lot["shares_sold"] += s_shares
          sel_lot["sell_price"] = float(s_price)
          sel_lot["date_sold"] = date_s_str
          sel_lot["nifty500_sell_close"] = nifty_close_sell
        else:
          closed_split_lot = {
              "id": f"TRD_{int(time.time()*1000)}",
              "ticker": sel_lot["ticker"],
              "status": "CLOSED",
              "date_bought": sel_lot["date_bought"],
              "date_sold": date_s_str,
              "shares_bought": int(s_shares),
              "shares_sold": int(s_shares),
              "buy_price": sel_lot["buy_price"],
              "sell_price": float(s_price),
              "initial_sl": sel_lot["initial_sl"],
              "nifty500_buy_close": sel_lot["nifty500_buy_close"],
              "nifty500_sell_close": nifty_close_sell,
          }
          sel_lot["shares_bought"] -= s_shares
          st.session_state.tradebook["trades"].append(closed_split_lot)

        save_tradebook(st.session_state.tradebook)
        st.success(f"✅ Executed exit for **{sel_lot['ticker']}**!")
        st.rerun()

  @st.dialog("✏️ Edit or Delete Trade", width="medium")
  def show_edit_modal(trade_id):
    idx = next((i for i, t in enumerate(st.session_state.tradebook["trades"]) if t.get("id") == trade_id), None)
    if idx is None:
      st.error("Trade not found.")
      return

    sel_tr = st.session_state.tradebook["trades"][idx]
    stat = sel_tr.get("status", "OPEN")
    tick = sel_tr.get("ticker", "")
    sh_b = sel_tr.get("shares_bought", 0)
    sh_s = sel_tr.get("shares_sold", 0)
    bp = sel_tr.get("buy_price", 0.0)

    st.markdown(f"**Selected Trade:** `{tick}` | Bought {sh_b} shs @ ₹{bp}")
    st.markdown("---")

    with st.form("edit_trade_form"):
      e_status = st.selectbox(
          "Status", ["OPEN", "CLOSED"], index=0 if stat == "OPEN" else 1
      )
      e_tick = st.text_input("Ticker", tick)
      c1, c2 = st.columns(2)
      with c1:
        e_sh_b = st.number_input("Shares Bought", min_value=1, value=int(sh_b))
        e_bp = st.number_input("Buy Price", min_value=0.01, value=float(bp))
        try:
            e_db_val = pd.to_datetime(sel_tr.get("date_bought")).date()
        except:
            e_db_val = date.today()
        e_db = st.date_input("Date Bought", e_db_val)
        e_sl = st.number_input("Initial SL", min_value=0.00, value=float(sel_tr.get("initial_sl", 0.0)))
      with c2:
        e_sh_s = st.number_input("Shares Sold", min_value=0, value=int(sh_s))
        e_sp = st.number_input("Sell Price", min_value=0.0, value=float(sel_tr.get("sell_price", 0.0)))
        try:
            e_ds_val = pd.to_datetime(sel_tr.get("date_sold")).date() if sel_tr.get("date_sold") and sel_tr.get("date_sold") != "N/A" else date.today()
        except:
            e_ds_val = date.today()
        e_ds = st.date_input("Date Sold", e_ds_val)

      col_upd, col_del = st.columns(2)
      with col_upd:
        submit_upd = st.form_submit_button("💾 Update Trade", use_container_width=True)
      with col_del:
        submit_del = st.form_submit_button("🗑️ Delete Trade", use_container_width=True)

      if submit_upd:
        sel_tr["status"] = e_status
        sel_tr["ticker"] = e_tick
        sel_tr["shares_bought"] = e_sh_b
        sel_tr["buy_price"] = e_bp
        sel_tr["date_bought"] = e_db.strftime("%Y-%m-%d")
        sel_tr["initial_sl"] = e_sl
        sel_tr["shares_sold"] = e_sh_s
        sel_tr["sell_price"] = e_sp
        sel_tr["date_sold"] = e_ds.strftime("%Y-%m-%d") if e_status == "CLOSED" else "N/A"
        save_tradebook(st.session_state.tradebook)
        st.success("Trade updated successfully!")
        st.rerun()

      if submit_del:
        st.session_state.tradebook["trades"].pop(idx)
        save_tradebook(st.session_state.tradebook)
        st.success("Trade deleted successfully!")
        st.rerun()

  @st.dialog("⚙️ Configure Account Capital", width="small")
  def show_config_modal():
    with st.form("config_capital_form"):
      cap = st.number_input(
          "Starting Portfolio Capital (₹):",
          min_value=10000.0,
          value=starting_cap,
          step=25000.0,
      )
      if st.form_submit_button("💾 Save Config", use_container_width=True):
        st.session_state.tradebook["config"]["starting_capital"] = float(cap)
        save_tradebook(st.session_state.tradebook)
        st.success("Config updated!")
        st.rerun()

  with ctrl_col1:
    if st.button("➕ Log New Buy", type="primary", use_container_width=True):
      show_buy_modal()
  with ctrl_col2:
    if st.button("➖ Log Exit / Sell", type="secondary", use_container_width=True, disabled=(not selected_trade_id and open_count == 0)):
      show_sell_modal(selected_trade_id)
  with ctrl_col3:
    if st.button("✏️ Edit / Delete", type="secondary", use_container_width=True, disabled=not selected_trade_id):
      show_edit_modal(selected_trade_id)
  with ctrl_col4:
    if st.button("⚙️ Config Capital", type="secondary", use_container_width=True):
      show_config_modal()

  if df_tb_display.empty:
    st.info(
        "Your Tradebook is empty or no trades match the selected filter! Click **'➕ Log New Buy'** above to record your"
        " first position."
    )
  else:
    tb_table_columns = [
        "S.No._num",
        "Ticker",
        "Status",
        "Shares Bought",
        "Date Bought",
        "Buy Price (₹)",
        "Initial SL (₹)",
        "Current / Sold Price (₹)",
        "Gain / Loss (₹)",
        "Realized R",
        "Shares Sold",
        "Booked Value (₹)",
        "Realised Gains (₹)",
        "Shares Remaining",
        "Abs Return %",
        "Unrealised Value (₹)",
        "Capital Invested (₹)",
        "Current Value (₹)",
        "Allocation %",
    ]

    st.subheader(f"📋 Tradebook ({len(df_tb_display)} Rows)")
    st.dataframe(
        df_tb_display[tb_table_columns],
        use_container_width=True,
        hide_index=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row",
        column_config=get_left_aligned_column_config(tb_table_columns),
        key="tb_manage_table"
    )

    st.markdown("---")
    st.subheader("📊 Elite Risk Management & Performance Analytics")

    closed_lots = [
        t for t in processed_trade_rows
        if "WIN" in str(t.get("Status", "")) or "LOSS" in str(t.get("Status", "")) or "SCRATCH" in str(t.get("Status", ""))
    ]
    total_closed = len(closed_lots)
    
    unique_setups = len(trade_signatures)
    active_setups = len(set(t["Signature"] for t in processed_trade_rows if "OPEN" in t["Status"]))

    if total_closed > 0:
      wins = [t for t in closed_lots if t["Realised Gains (₹)"] > 0]
      losses = [t for t in closed_lots if t["Realised Gains (₹)"] <= 0]

      win_count = len(wins)
      loss_count = len(losses)
      win_rate = (win_count / total_closed) * 100

      avg_win_inr = (
          sum(t["Realised Gains (₹)"] for t in wins) / win_count
          if win_count > 0
          else 0.0
      )
      avg_loss_inr = (
          abs(sum(t["Realised Gains (₹)"] for t in losses)) / loss_count
          if loss_count > 0
          else 0.0
      )

      avg_win_pct = (
          sum(t["Abs Return %"] for t in wins) / win_count
          if win_count > 0
          else 0.0
      )
      avg_loss_pct = (
          abs(sum(t["Abs Return %"] for t in losses)) / loss_count
          if loss_count > 0
          else 0.0
      )

      rr_monetary = (
          avg_win_inr / avg_loss_inr if avg_loss_inr > 0 else avg_win_inr
      )
      rr_ratio = (
          avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else avg_win_pct
      )

      def calc_days(t):
        try:
          d1 = datetime.strptime(t["Date Bought"], "%Y-%m-%d")
          d2 = datetime.strptime(t["Date Sold"], "%Y-%m-%d")
          return max(1, (d2 - d1).days)
        except Exception:
          return 1

      avg_days_win = (
          sum(calc_days(t) for t in wins) / win_count if win_count > 0 else 0
      )
      avg_days_loss = (
          sum(calc_days(t) for t in losses) / loss_count if loss_count > 0 else 0
      )

      streak_count = 0
      last_outcome = None
      for t in reversed(closed_lots):
        is_win = t["Realised Gains (₹)"] > 0
        if last_outcome is None:
          last_outcome = is_win
          streak_count = 1
        elif last_outcome == is_win:
          streak_count += 1
        else:
          break

      streak_label = (
          f"🟢 {streak_count} Wins" if last_outcome else f"🔴 {streak_count} Losses"
      )
      if not last_outcome and streak_count >= 3:
        streak_label += " (⚠️ Cut Size 50%)"

    else:
      win_count, loss_count, win_rate = 0, 0, 0.0
      avg_win_inr, avg_loss_inr, avg_win_pct, avg_loss_pct = 0.0, 0.0, 0.0, 0.0
      rr_monetary, rr_ratio, avg_days_win, avg_days_loss = 0.0, 0.0, 0, 0
      streak_label = "⚪ No Closed Trades"

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
      st.metric(
          "Total Setups Logged",
          f"{unique_setups}",
          f"Live / Active: {active_setups}",
      )
    with k2:
      st.metric("Win Rate %", f"{win_rate:.1f}%", f"{win_count}W / {loss_count}L")
    with k3:
      st.metric(
          "Avg Win (₹ / %)",
          f"₹{avg_win_inr:,.0f}",
          f"+{avg_win_pct:.2f}%",
      )
    with k4:
      st.metric(
          "Avg Loss (₹ / %)",
          f"-₹{avg_loss_inr:,.0f}",
          f"-{avg_loss_pct:.2f}%",
      )
    with k5:
      st.metric(
          "Payoff Ratio (R:R)",
          f"{rr_ratio:.2f}x",
          f"Monetary: {rr_monetary:.2f}x",
      )

    k6, k7, k8 = st.columns(3)
    with k6:
      st.metric("Avg Days Held (Winners)", f"{avg_days_win:.1f} Days")
    with k7:
      st.metric("Avg Days Held (Losers)", f"{avg_days_loss:.1f} Days")
    with k8:
      st.metric("Progressive Exposure Streak", streak_label)

    # ==========================================
    # 📅 TRADING PERFORMANCE CALENDAR & WEEKLY LEDGER
    # ==========================================
    st.markdown("---")
    st.subheader("📅 Trading Performance Calendar & Weekly Ledger")
    st.caption("Tracks Daily and Weekly Realized Gain / Loss (₹) and Number of Closed Trades.")

    if total_closed == 0:
      st.info("No closed trades available to generate the Trading Calendar yet.")
    else:
      df_closed_cal = pd.DataFrame(closed_lots)
      df_closed_cal["Date_DT"] = pd.to_datetime(df_closed_cal["Date Sold"], errors="coerce")
      df_closed_cal = df_closed_cal.dropna(subset=["Date_DT"]).sort_values(by="Date_DT", ascending=False)

      daily_agg = (
          df_closed_cal.groupby(df_closed_cal["Date_DT"].dt.strftime("%Y-%m-%d"))
          .agg(
              Trades=("Ticker", "count"),
              Realised_Gains=("Realised Gains (₹)", "sum"),
              Wins=("Realised Gains (₹)", lambda s: (s > 0).sum()),
          )
          .reset_index()
      )
      daily_agg.columns = ["Date Sold", "Trades", "Realised Gains (₹)", "Wins"]
      
      # FIX: Use .clip(lower=1) instead of max() which causes ValueError on Series
      daily_agg["Win Rate %"] = ((daily_agg["Wins"] / daily_agg["Trades"].clip(lower=1)) * 100).round(1)
      daily_agg["Day"] = pd.to_datetime(daily_agg["Date Sold"]).dt.day_name().str[:3]
      daily_agg["Status"] = daily_agg["Realised Gains (₹)"].apply(
          lambda v: "🔵 +₹" + f"{v:,.0f}" if v > 0 else "🔴 -₹" + f"{abs(v):,.0f}"
      )

      daily_display_cols = ["Date Sold", "Day", "Trades", "Realised Gains (₹)", "Win Rate %", "Status"]

      df_closed_cal["ISO_Week"] = df_closed_cal["Date_DT"].dt.strftime("%Y-W%V")
      weekly_agg = (
          df_closed_cal.groupby("ISO_Week")
          .agg(
              Trades=("Ticker", "count"),
              Realised_Gains=("Realised Gains (₹)", "sum"),
              Wins=("Realised Gains (₹)", lambda s: (s > 0).sum()),
          )
          .reset_index()
      )
      weekly_agg.columns = ["ISO Week", "Trades", "Realised Gains (₹)", "Wins"]
      weekly_agg["Win Rate %"] = ((weekly_agg["Wins"] / weekly_agg["Trades"].clip(lower=1)) * 100).round(1)
      weekly_agg["Status"] = weekly_agg["Realised Gains (₹)"].apply(
          lambda v: "🔵 GREEN WEEK" if v > 0 else "🔴 RED WEEK"
      )
      weekly_agg = weekly_agg.sort_values(by="ISO Week", ascending=False)

      weekly_display_cols = ["ISO Week", "Trades", "Realised Gains (₹)", "Win Rate %", "Status"]

      # VISUAL GRID CALENDAR IMPLEMENTATION
      import calendar
      
      # Find the most recent month from our trades
      recent_dt = pd.to_datetime(daily_agg["Date Sold"].max())
      cal_year = recent_dt.year
      cal_month = recent_dt.month
      month_name = calendar.month_name[cal_month]
      
      st.markdown(f"#### {month_name} {cal_year}")
      
      # Build dictionary of days to P&L mapping
      day_map = {}
      for _, row in daily_agg.iterrows():
          d_obj = pd.to_datetime(row["Date Sold"])
          if d_obj.year == cal_year and d_obj.month == cal_month:
              day_map[d_obj.day] = {
                  "trades": row["Trades"],
                  "pnl": row["Realised Gains (₹)"]
              }
      
      # HTML/CSS Grid Generator
      cal_html = """
      <style>
      .cal-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-bottom: 20px; }
      .cal-header { font-weight: bold; text-align: center; padding: 10px; color: #E0E2EC; border-bottom: 2px solid #2B2F3E; }
      .cal-cell { border: 1px solid #2B2F3E; border-radius: 6px; padding: 10px; min-height: 90px; display: flex; flex-direction: column; justify-content: space-between; background-color: #1E222D; }
      .cal-cell-empty { border: none; background-color: transparent; }
      .cal-day { font-size: 13px; color: #888; text-align: right; margin-bottom: 5px; }
      .cal-val-win { color: #63BE7B; font-weight: bold; font-size: 16px; }
      .cal-val-loss { color: #F8696B; font-weight: bold; font-size: 16px; }
      .cal-val-neu { color: #E0E2EC; font-size: 16px; font-weight: bold;}
      .cal-trades { font-size: 12px; color: #888; margin-top: 5px; }
      .cal-week-tot { background-color: #243447; border-color: #3B4B61; text-align: center; }
      </style>
      <div class="cal-grid">
          <div class="cal-header">Sun</div><div class="cal-header">Mon</div><div class="cal-header">Tue</div>
          <div class="cal-header">Wed</div><div class="cal-header">Thu</div><div class="cal-header">Fri</div>
          <div class="cal-header">Sat</div><div class="cal-header">Week Total</div>
      """
      
      cal_matrix = calendar.monthcalendar(cal_year, cal_month)
      week_num = 1
      for week in cal_matrix:
          week_pnl = 0.0
          week_trades = 0
          for day in week:
              if day == 0:
                  cal_html += '<div class="cal-cell-empty"></div>'
              else:
                  data = day_map.get(day, {"trades": 0, "pnl": 0.0})
                  pnl = data["pnl"]
                  trades = data["trades"]
                  week_pnl += pnl
                  week_trades += trades
                  
                  val_class = "cal-val-neu"
                  if pnl > 0: val_class = "cal-val-win"
                  elif pnl < 0: val_class = "cal-val-loss"
                  
                  pnl_str = f"₹{pnl:,.0f}" if pnl == 0 else (f"+₹{pnl:,.0f}" if pnl > 0 else f"-₹{abs(pnl):,.0f}")
                  
                  cal_html += f"""
                  <div class="cal-cell">
                      <div class="cal-day">{day}</div>
                      <div class="{val_class}">{pnl_str}</div>
                      <div class="cal-trades">{trades} trades</div>
                  </div>
                  """
          # Week Total Column
          tot_class = "cal-val-neu"
          if week_pnl > 0: tot_class = "cal-val-win"
          elif week_pnl < 0: tot_class = "cal-val-loss"
          tot_pnl_str = f"₹{week_pnl:,.0f}" if week_pnl == 0 else (f"+₹{week_pnl:,.0f}" if week_pnl > 0 else f"-₹{abs(week_pnl):,.0f}")
          
          cal_html += f"""
          <div class="cal-cell cal-week-tot">
              <div class="cal-day">Week {week_num}</div>
              <div class="{tot_class}" style="text-align: center; margin-top: auto;">{tot_pnl_str}</div>
              <div class="cal-trades" style="text-align: center;">{week_trades} trades</div>
          </div>
          """
          week_num += 1
          
      cal_html += "</div>"
      st.markdown(cal_html, unsafe_allow_html=True)

      tab_day_tb, tab_week_tb = st.tabs(["📅 Daily Ledger Table", "🗓️ Weekly Matrix Table"])
      with tab_day_tb:
        st.dataframe(
            daily_agg[daily_display_cols],
            use_container_width=True,
            hide_index=True,
            height=280,
            column_config=get_left_aligned_column_config(daily_display_cols),
        )
      with tab_week_tb:
        st.dataframe(
            weekly_agg[weekly_display_cols],
            use_container_width=True,
            hide_index=True,
            height=280,
            column_config=get_left_aligned_column_config(weekly_display_cols),
        )

# ==========================================
# TAB 4: MARKET HEALTH & SECTOR ROTATION
# ==========================================
with tab_market_health:
  st.subheader("🏥 Market Health & Sector Rotation Studio")
  st.markdown(
      "Automated **Nifty 500 Breadth Monitor**, **27-Sector CAN SLIM Rotation"
      " Engine**, and **AI Situational Awareness Intelligence**."
  )

  tab_ai_intel, tab_mm, tab_sector_heat, tab_sector_rot = st.tabs([
      "🎯 Daily AI Situational Awareness & Action Plan",
      "📈 NSE Market Breadth Monitor",
      "🔥 Sector RS Heatmap",
      "📊 Historical Rotation Tracker",
  ])

  df_mm = load_market_monitor_data()
  df_heat, df_rot = load_sector_monitor_data()

  with tab_ai_intel:
    st.subheader("🧠 Daily Market & Sector Situational Awareness")
    st.caption(
        "Synthesizes Nifty 500 Breadth Thrusts, 27-Sector RS Velocity, and"
        " Active Screener Scan Clusters to produce an actionable institutional"
        " trading plan."
    )

    today_str = time.strftime("%Y-%m-%d")
    latest_briefing = st.session_state.market_briefings.get(today_str)

    b_col1, b_col2 = st.columns([1.8, 1.2])
    with b_col1:
      if latest_briefing:
        st.success(f"✅ Active Briefing Loaded for Date: **{today_str}**")
      else:
        st.info(
            f"No AI Briefing generated for **{today_str}** yet. Click the button"
            " on the right to synthesize today's data!"
        )
    with b_col2:
      run_briefing_btn = st.button(
          "🔄 Generate / Refresh Today's AI Briefing Now",
          type="primary",
          use_container_width=True,
      )

    if run_briefing_btn:
      with st.status(
          "🤖 Synthesizing Market Breadth, Sector RS Velocities & Scan"
          " Clusters...",
          expanded=True,
      ) as status_box:
        scan_summary = st.session_state.get("active_scan_summary", {})
        latest_briefing = run_gemini_market_awareness(
            df_mm, df_heat, df_rot, scan_summary, status_log=status_box
        )
        if latest_briefing:
          status_box.update(
              label="✅ Briefing Complete! Refreshing View...",
              state="complete",
          )
          time.sleep(1)
          st.rerun()

    if latest_briefing:
      st.markdown("---")
      st.markdown(latest_briefing.get("briefing_md", ""))
      st.markdown("---")

      pdf_bytes_briefing = create_pdf_bytes(
          f"Market_Awareness_{today_str}", latest_briefing.get("briefing_md", "")
      )
      st.download_button(
          label="📥 Download Daily Market Awareness Briefing (PDF)",
          data=pdf_bytes_briefing,
          file_name=f"NSE_Market_Situational_Awareness_{today_str}.pdf",
          mime="application/pdf",
          use_container_width=True,
      )

  with tab_mm:
    if not df_mm.empty:
      st.markdown(
          f"#### 📊 Nifty Total Market Breadth & VCP Indicators ({len(df_mm)} Days)"
      )
      latest = df_mm.iloc[0] if len(df_mm) > 0 else {}
      c1, c2, c3, c4 = st.columns(4)
      with c1:
        st.metric(
            "Latest Nifty 500 Close",
            f"{latest.get('Nifty 500 Close', 'N/A')}",
            f"{latest.get('Nifty 500 Chg %', 0)}%",
        )
      with c2:
        st.metric("5-Day Thrust Ratio", f"{latest.get('5 Day Ratio', 'N/A')}")
      with c3:
        st.metric("10-Day Thrust Ratio", f"{latest.get('10 Day Ratio', 'N/A')}")
      with c4:
        st.metric("A/D Ratio", f"{latest.get('A/D Ratio', 'N/A')}")
      styled_mm = style_market_monitor(df_mm)
      st.table(styled_mm)
    else:
      st.info("Market Monitor data not available yet.")

  with tab_sector_heat:
    if not df_heat.empty:
      st.markdown("#### 🔥 27-Sector CAN SLIM Relative Strength Heatmap (Ranked by 65D RS)")
      st.caption(
          "💡 **Velocity Legend:** Positive (+) values indicate upward rank"
          " acceleration; Negative (-) indicate loss of relative momentum."
      )
      styled_heat = style_sector_heatmap(df_heat)
      st.table(styled_heat)
    else:
      st.info("Sector Heatmap data not available yet.")

  with tab_sector_rot:
    if not df_rot.empty:
      st.markdown("#### 📊 65-Day Historical Relative Strength Ranks (All Sectors)")
      st.caption("💡 Rank 1 = Strongest Relative Strength vs. Nifty 500 Benchmark (`^CRSLDX`).")
      styled_rot = style_rotation_tracker(df_rot)
      st.table(styled_rot)
    else:
      st.info("Rotation Tracker data not available yet.")
