import streamlit as st
import pandas as pd
import plotly.express as px
import json
import re
from tradingview_screener import Query, col

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="India Equities Screener & Watchlist Studio",
    page_icon="📈",
    layout="wide"
)

# ==========================================
# 0. INITIALIZE SESSION STATE
# ==========================================
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

# Persistent Watchlist Storage in Session State
if "watchlists" not in st.session_state:
    st.session_state.watchlists = {
        "⭐ CAN SLIM Priority": ["NSE:JINDWORLD", "NSE:CDSL", "NSE:TITAGARH", "NSE:RECLTD"],
        "🚀 Breakout Watch": ["NSE:ZOMATO", "NSE:TRENT", "NSE:HAL"]
    }
if "active_watchlist_name" not in st.session_state:
    st.session_state.active_watchlist_name = "⭐ CAN SLIM Priority"

st.title("📈 India Equities Screener & Watchlist Studio")
st.markdown("Professional **CAN SLIM Screener**, **Hierarchical Sector → Industry Rotation**, and **Multi-Watchlist Studio with Live ADR% Enrichment**.")

# ==========================================
# 1. OFFICIAL 22 SECTORS & 59 INDUSTRIES
# ==========================================
INDIAN_SECTOR_HIERARCHY = {
    "Automobile and Auto Components": [
        "Automobiles", "Auto Components & Ancillaries", "Tyres & Rubber"
    ],
    "Capital Goods": [
        "Aerospace & Defense", "Electrical Equipment", "Engineering Services", 
        "Industrial Manufacturing", "Industrial Products"
    ],
    "Chemicals": [
        "Chemicals & Petrochemicals", "Fertilizers & Agrochemicals"
    ],
    "Construction": [
        "Civil Construction", "Infrastructure Developers"
    ],
    "Construction Materials": [
        "Cement & Cement Products", "Ceramics & Building Materials"
    ],
    "Consumer Durables": [
        "Consumer Electronics & Appliances", "Gems, Jewellery & Watches", "Household & Personal Products"
    ],
    "Consumer Services": [
        "Leisure Services", "Restaurants & QSR", "Retailing", "Travel & Tourism"
    ],
    "Diversified": [
        "Diversified Commercial Services", "Diversified Industrials"
    ],
    "Fast Moving Consumer Goods": [
        "Agricultural Food & Other Products", "Beverages", "Food Products", "Personal Care", "Tobacco Products"
    ],
    "Financial Services": [
        "Asset Management", "Banks", "Capital Markets", "Finance & NBFCs", 
        "Financial Technology (Fintech)", "Insurance"
    ],
    "Forest Materials": [
        "Paper, Forest & Jute Products"
    ],
    "Healthcare": [
        "Healthcare Research, Analytics & Technology", "Healthcare Services", 
        "Medical Equipment & Supplies", "Pharmaceuticals & Biotechnology"
    ],
    "Information Technology": [
        "IT - Hardware", "IT - Software & Consulting", "IT - Services"
    ],
    "Media, Entertainment & Publication": [
        "Broadcasting & Cable TV", "Entertainment & Content", "Print Media & Publishing"
    ],
    "Metals & Mining": [
        "Ferrous Metals (Steel & Iron)", "Non-Ferrous Metals", "Minerals & Mining"
    ],
    "Oil, Gas & Consumable Fuels": [
        "Consumable Fuels & Coal", "Oil & Gas Exploration & Production", "Petroleum Products & Refining"
    ],
    "Power": [
        "Power Generation", "Power Transmission & Distribution"
    ],
    "Realty": [
        "Real Estate Developers", "Real Estate Services"
    ],
    "Services": [
        "Commercial & Professional Services", "Logistics & Transportation Services", "Port & Shipping Services"
    ],
    "Telecommunication": [
        "Telecom - Equipment & Accessories", "Telecom - Services"
    ],
    "Textiles": [
        "Garments & Apparels", "Textiles & Weaving"
    ],
    "Utilities": [
        "Gas Transmission & Utilities", "Water & Other Utilities"
    ]
}

# 100% Deterministic Lookup Table for all 84 TradingView India Sector/Industry pairs
TV_TO_INDIAN_MAP = {
    ('Commercial Services', 'Financial Publishing/Services'): ('Financial Services', 'Capital Markets'),
    ('Commercial Services', 'Miscellaneous Commercial Services'): ('Services', 'Commercial & Professional Services'),
    ('Commercial Services', 'Personnel Services'): ('Services', 'Commercial & Professional Services'),
    ('Consumer Durables', 'Automotive Aftermarket'): ('Automobile and Auto Components', 'Auto Components & Ancillaries'),
    ('Consumer Durables', 'Electronics/Appliances'): ('Consumer Durables', 'Consumer Electronics & Appliances'),
    ('Consumer Durables', 'Home Furnishings'): ('Consumer Durables', 'Household & Personal Products'),
    ('Consumer Durables', 'Homebuilding'): ('Realty', 'Real Estate Developers'),
    ('Consumer Durables', 'Motor Vehicles'): ('Automobile and Auto Components', 'Automobiles'),
    ('Consumer Durables', 'Other Consumer Specialties'): ('Consumer Durables', 'Gems, Jewellery & Watches'),
    ('Consumer Non-Durables', 'Apparel/Footwear'): ('Textiles', 'Garments & Apparels'),
    ('Consumer Non-Durables', 'Beverages: Alcoholic'): ('Fast Moving Consumer Goods', 'Beverages'),
    ('Consumer Non-Durables', 'Food: Major Diversified'): ('Fast Moving Consumer Goods', 'Food Products'),
    ('Consumer Non-Durables', 'Food: Specialty/Candy'): ('Fast Moving Consumer Goods', 'Food Products'),
    ('Consumer Non-Durables', 'Household/Personal Care'): ('Fast Moving Consumer Goods', 'Personal Care'),
    ('Consumer Services', 'Broadcasting'): ('Media, Entertainment & Publication', 'Broadcasting & Cable TV'),
    ('Consumer Services', 'Hotels/Resorts/Cruise lines'): ('Consumer Services', 'Travel & Tourism'),
    ('Consumer Services', 'Movies/Entertainment'): ('Media, Entertainment & Publication', 'Entertainment & Content'),
    ('Consumer Services', 'Publishing: Books/Magazines'): ('Media, Entertainment & Publication', 'Print Media & Publishing'),
    ('Consumer Services', 'Restaurants'): ('Consumer Services', 'Restaurants & QSR'),
    ('Distribution Services', 'Electronics Distributors'): ('Capital Goods', 'Industrial Products'),
    ('Distribution Services', 'Medical Distributors'): ('Healthcare', 'Medical Equipment & Supplies'),
    ('Distribution Services', 'Wholesale Distributors'): ('Services', 'Commercial & Professional Services'),
    ('Electronic Technology', 'Aerospace & Defense'): ('Capital Goods', 'Aerospace & Defense'),
    ('Electronic Technology', 'Computer Communications'): ('Telecommunication', 'Telecom - Equipment & Accessories'),
    ('Electronic Technology', 'Computer Peripherals'): ('Information Technology', 'IT - Hardware'),
    ('Electronic Technology', 'Electronic Components'): ('Capital Goods', 'Electrical Equipment'),
    ('Electronic Technology', 'Electronic Equipment/Instruments'): ('Capital Goods', 'Electrical Equipment'),
    ('Electronic Technology', 'Electronic Production Equipment'): ('Capital Goods', 'Industrial Manufacturing'),
    ('Electronic Technology', 'Telecommunications Equipment'): ('Telecommunication', 'Telecom - Equipment & Accessories'),
    ('Energy Minerals', 'Oil & Gas Production'): ('Oil, Gas & Consumable Fuels', 'Oil & Gas Exploration & Production'),
    ('Energy Minerals', 'Oil Refining/Marketing'): ('Oil, Gas & Consumable Fuels', 'Petroleum Products & Refining'),
    ('Finance', 'Finance/Rental/Leasing'): ('Financial Services', 'Finance & NBFCs'),
    ('Finance', 'Financial Conglomerates'): ('Financial Services', 'Finance & NBFCs'),
    ('Finance', 'Investment Banks/Brokers'): ('Financial Services', 'Capital Markets'),
    ('Finance', 'Investment Managers'): ('Financial Services', 'Asset Management'),
    ('Finance', 'Life/Health Insurance'): ('Financial Services', 'Insurance'),
    ('Finance', 'Major Banks'): ('Financial Services', 'Banks'),
    ('Finance', 'Multi-Line Insurance'): ('Financial Services', 'Insurance'),
    ('Finance', 'Real Estate Development'): ('Realty', 'Real Estate Developers'),
    ('Finance', 'Regional Banks'): ('Financial Services', 'Banks'),
    ('Health Services', 'Hospital/Nursing Management'): ('Healthcare', 'Healthcare Services'),
    ('Health Services', 'Medical/Nursing Services'): ('Healthcare', 'Healthcare Services'),
    ('Health Technology', 'Biotechnology'): ('Healthcare', 'Pharmaceuticals & Biotechnology'),
    ('Health Technology', 'Medical Specialties'): ('Healthcare', 'Medical Equipment & Supplies'),
    ('Health Technology', 'Pharmaceuticals: Generic'): ('Healthcare', 'Pharmaceuticals & Biotechnology'),
    ('Health Technology', 'Pharmaceuticals: Major'): ('Healthcare', 'Pharmaceuticals & Biotechnology'),
    ('Health Technology', 'Pharmaceuticals: Other'): ('Healthcare', 'Pharmaceuticals & Biotechnology'),
    ('Industrial Services', 'Contract Drilling'): ('Oil, Gas & Consumable Fuels', 'Oil & Gas Exploration & Production'),
    ('Industrial Services', 'Engineering & Construction'): ('Construction', 'Civil Construction'),
    ('Industrial Services', 'Oilfield Services/Equipment'): ('Oil, Gas & Consumable Fuels', 'Oil & Gas Exploration & Production'),
    ('Non-Energy Minerals', 'Construction Materials'): ('Construction Materials', 'Ceramics & Building Materials'),
    ('Non-Energy Minerals', 'Forest Products'): ('Forest Materials', 'Paper, Forest & Jute Products'),
    ('Non-Energy Minerals', 'Other Metals/Minerals'): ('Metals & Mining', 'Minerals & Mining'),
    ('Non-Energy Minerals', 'Steel'): ('Metals & Mining', 'Ferrous Metals (Steel & Iron)'),
    ('Process Industries', 'Agricultural Commodities/Milling'): ('Fast Moving Consumer Goods', 'Agricultural Food & Other Products'),
    ('Process Industries', 'Chemicals: Agricultural'): ('Chemicals', 'Fertilizers & Agrochemicals'),
    ('Process Industries', 'Chemicals: Major Diversified'): ('Chemicals', 'Chemicals & Petrochemicals'),
    ('Process Industries', 'Chemicals: Specialty'): ('Chemicals', 'Chemicals & Petrochemicals'),
    ('Process Industries', 'Containers/Packaging'): ('Capital Goods', 'Industrial Products'),
    ('Process Industries', 'Industrial Specialties'): ('Capital Goods', 'Industrial Manufacturing'),
    ('Process Industries', 'Pulp & Paper'): ('Forest Materials', 'Paper, Forest & Jute Products'),
    ('Process Industries', 'Textiles'): ('Textiles', 'Textiles & Weaving'),
    ('Producer Manufacturing', 'Auto Parts: OEM'): ('Automobile and Auto Components', 'Auto Components & Ancillaries'),
    ('Producer Manufacturing', 'Building Products'): ('Construction Materials', 'Cement & Cement Products'),
    ('Producer Manufacturing', 'Electrical Products'): ('Capital Goods', 'Electrical Equipment'),
    ('Producer Manufacturing', 'Industrial Machinery'): ('Capital Goods', 'Industrial Manufacturing'),
    ('Producer Manufacturing', 'Metal Fabrication'): ('Capital Goods', 'Industrial Manufacturing'),
    ('Producer Manufacturing', 'Miscellaneous Manufacturing'): ('Capital Goods', 'Industrial Products'),
    ('Producer Manufacturing', 'Office Equipment/Supplies'): ('Consumer Durables', 'Household & Personal Products'),
    ('Producer Manufacturing', 'Trucks/Construction/Farm Machinery'): ('Automobile and Auto Components', 'Automobiles'),
    ('Retail Trade', 'Apparel/Footwear Retail'): ('Consumer Services', 'Retailing'),
    ('Retail Trade', 'Electronics/Appliance Stores'): ('Consumer Services', 'Retailing'),
    ('Retail Trade', 'Internet Retail'): ('Consumer Services', 'Retailing'),
    ('Retail Trade', 'Specialty Stores'): ('Consumer Services', 'Retailing'),
    ('Technology Services', 'Information Technology Services'): ('Information Technology', 'IT - Services'),
    ('Technology Services', 'Internet Software/Services'): ('Information Technology', 'IT - Software & Consulting'),
    ('Technology Services', 'Packaged Software'): ('Information Technology', 'IT - Software & Consulting'),
    ('Transportation', 'Air Freight/Couriers'): ('Services', 'Logistics & Transportation Services'),
    ('Transportation', 'Airlines'): ('Consumer Services', 'Travel & Tourism'),
    ('Transportation', 'Marine Shipping'): ('Services', 'Port & Shipping Services'),
    ('Transportation', 'Other Transportation'): ('Services', 'Logistics & Transportation Services'),
    ('Transportation', 'Railroads'): ('Services', 'Logistics & Transportation Services'),
    ('Utilities', 'Electric Utilities'): ('Power', 'Power Generation'),
    ('Utilities', 'Gas Distributors'): ('Utilities', 'Gas Transmission & Utilities')
}

def map_to_indian_classification(tv_industry, tv_sector):
    mapped = TV_TO_INDIAN_MAP.get((tv_sector, tv_industry))
    if mapped:
        return mapped
    return "Diversified", "Diversified Commercial Services"

# Safe multi-selection parsers for Streamlit Plotly / Table events
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

# String cleaning helper for pasting from TradingView
def parse_pasted_tickers(raw_text):
    if not raw_text:
        return []
    tokens = re.split(r'[,\\n\\t]+', raw_text)
    cleaned = []
    for t in tokens:
        t = t.strip().upper()
        if not t:
            continue
        if ":" not in t:
            t = f"NSE:{t}"
        if t not in cleaned:
            cleaned.append(t)
    return cleaned

# ==========================================
# 2. BACKEND API QUERIES
# ==========================================
def fetch_screener_data(exchanges, min_mcap, vol_period_days, ma_columns_to_fetch, limit_rows):
    if not exchanges:
        return pd.DataFrame()
    min_mcap_inr = min_mcap * 10_000_000
    tv_vol_col = f"average_volume_{vol_period_days}d_calc"
    select_cols = [
        'name', 'close', 'change', 'volume', 'market_cap_basic',
        tv_vol_col, 'ADR', 'price_52_week_high',
        'price_52_week_low', 'exchange', 'type', 'industry', 'sector'
    ]
    for c in ma_columns_to_fetch:
        if c not in select_cols:
            select_cols.append(c)
    q = (Query()
         .set_markets('india')
         .select(*select_cols)
         .where(col('market_cap_basic') >= min_mcap_inr)
         .order_by('volume', ascending=False)
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
    bare_names = [s.split(":")[-1] for s in symbol_list]
    q = (Query()
         .set_markets('india')
         .select('name', 'close', 'change', 'ADR', 'market_cap_basic', 'exchange', 'industry', 'sector')
         .where(col('name').isin(bare_names))
         .limit(len(bare_names) + 10)
    )
    try:
        _, df = q.get_scanner_data()
        if not df.empty:
            df['ADR_pct'] = ((df['ADR'] / df['close']) * 100).round(2)
            df['Close'] = df['close'].round(2)
            df['Change %'] = df['change'].round(2)
            df['Market Cap (₹ Cr)'] = (df['market_cap_basic'] / 10_000_000).round(2)
            df['TV_Symbol'] = df['exchange'] + ":" + df['name']
            mapped_sectors, mapped_industries = [], []
            for _, row in df.iterrows():
                sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
                mapped_sectors.append(sec)
                mapped_industries.append(ind)
            df["Sector"] = mapped_sectors
            df["Industry"] = mapped_industries
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 3. SIDEBAR CONTROLS & ACTIVE WATCHLIST
# ==========================================
with st.sidebar.form("filter_form"):
    st.header("1. Exchange & Universe")
    exchange_choice = st.multiselect(
        "Select Exchanges:",
        options=["NSE", "BSE"],
        default=["NSE", "BSE"]
    )
    
    st.markdown("---")
    st.header("🏛️ Official NSE Filters (22 / 59)")
    sector_options = list(INDIAN_SECTOR_HIERARCHY.keys())
    sector_choice = st.multiselect("NSE Sector (22 Economic Sectors):", options=sector_options, default=[])
    
    if sector_choice:
        industry_options = []
        for sec in sector_choice:
            industry_options.extend(INDIAN_SECTOR_HIERARCHY.get(sec, []))
        industry_options = sorted(list(set(industry_options)))
    else:
        all_industries = [ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds]
        industry_options = sorted(list(set(all_industries)))
        
    industry_choice = st.multiselect("NSE Industry (59 Distinct Classifications):", options=industry_options, default=[])

    st.markdown("---")
    st.header("2. Fundamental & Liquidity")
    min_mcap_cr = st.number_input("Min Market Cap (₹ Crores):", min_value=0, value=1000, step=100)
    
    vol_period_days = st.selectbox(
        "Average Volume Period:",
        options=[10, 30, 60, 90],
        index=2,
        format_func=lambda x: f"{x} Days",
        help="Select average volume period (10D, 30D, 60D, or 90D)."
    )
    min_vol_cr = st.number_input(f"Min {vol_period_days}D Avg Rupee Volume (₹ Cr):", min_value=0.0, value=5.0, step=0.5)

    st.markdown("---")
    st.header("3. Trend & Moving Averages (5 MAs)")
    default_ma_configs = [
        {"en": True,  "type": "EMA", "len": 21},
        {"en": True,  "type": "SMA", "len": 50},
        {"en": True,  "type": "SMA", "len": 200},
        {"en": False, "type": "EMA", "len": 10},
        {"en": False, "type": "SMA", "len": 150}
    ]
    ma_filters = []
    for i, cfg in enumerate(default_ma_configs, 1):
        c1, c2, c3 = st.columns([1.8, 1.6, 1.6])
        with c1:
            en = st.checkbox(f"MA {i} >", value=cfg["en"], key=f"ma_{i}_en")
        with c2:
            m_type = st.selectbox("Type", ["EMA", "SMA"], index=0 if cfg["type"]=="EMA" else 1, key=f"ma_{i}_type", label_visibility="collapsed")
        with c3:
            m_len = st.number_input("Len", min_value=1, max_value=500, value=cfg["len"], step=1, key=f"ma_{i}_len", label_visibility="collapsed")
        col_name = f"{m_type}{m_len}"
        ma_filters.append({
            "enabled": en, "type": m_type, "length": m_len, "col_name": col_name, "label": f"{m_type} {m_len}"
        })

    st.markdown("---")
    st.header("4. Volatility & 52-Week Range")
    min_adr = st.slider("Min ADR % (TradingView Standard):", min_value=0.0, max_value=10.0, value=2.25, step=0.25)
    min_above_52l = st.slider("Min % Above 52-Week Low:", min_value=0, max_value=100, value=20, step=5)
    max_below_52h = st.slider("Max % Below 52-Week High:", min_value=0, max_value=50, value=30, step=5)

    st.markdown("---")
    st.header("5. Display Settings")
    max_results = st.slider("Max Results to Fetch:", min_value=500, max_value=3000, value=2500, step=250)
    
    apply_filters = st.form_submit_button("🚀 Apply Filters", use_container_width=True, type="primary")

if apply_filters:
    st.session_state.reset_counter += 1

# Active Watchlist Switcher in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("⭐ Target Active Watchlist")
wl_names = list(st.session_state.watchlists.keys())
active_wl = st.sidebar.selectbox(
    "1-Click Add Target:",
    options=wl_names,
    index=wl_names.index(st.session_state.active_watchlist_name) if st.session_state.active_watchlist_name in wl_names else 0,
    key="wl_sidebar_target_selector"
)
st.session_state.active_watchlist_name = active_wl

# ==========================================
# 4. TOP-LEVEL WORKSPACE TABS
# ==========================================
tab_screener, tab_watchlists = st.tabs([
    "🔎 CAN SLIM Screener & Rotation",
    "⭐ Watchlist Studio & TradingView Bridge"
])

# ==========================================
# TAB 1: CAN SLIM SCREENER & ROTATION
# ==========================================
with tab_screener:
    ma_cols_to_fetch = list(set([m["col_name"] for m in ma_filters]))
    tv_vol_col = f"average_volume_{vol_period_days}d_calc"

    with st.spinner("⚡ Scanning Indian Equities & Applying Filters..."):
        results_df = fetch_screener_data(exchange_choice, min_mcap_cr, vol_period_days, ma_cols_to_fetch, max_results)

    if results_df.empty:
        st.warning("No stocks matched your criteria. Click 'Apply Filters' after adjusting your parameters.")
    else:
        df = results_df.copy()
        df = df[df['exchange'].isin(exchange_choice)]
        if 'type' in df.columns:
            df = df[df['type'] == 'stock']
        df = df.drop_duplicates(subset=['name'], keep='first')
        
        mapped_sectors, mapped_industries = [], []
        for _, row in df.iterrows():
            sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
            mapped_sectors.append(sec)
            mapped_industries.append(ind)
        df["Sector"] = mapped_sectors
        df["Industry"] = mapped_industries
        
        total_sector_counts = df['Sector'].value_counts()
        total_industry_counts = df['Industry'].value_counts()
            
        if sector_choice:
            df = df[df["Sector"].isin(sector_choice)]
        if industry_choice:
            df = df[df["Industry"].isin(industry_choice)]
        
        numeric_cols = ['market_cap_basic', 'close', 'change', 'volume', tv_vol_col, 'ADR', 'price_52_week_high', 'price_52_week_low'] + ma_cols_to_fetch
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
                
        df['ADR_pct'] = (df['ADR'] / df['close']) * 100
        df = df[df['ADR_pct'] >= min_adr]
                
        for ma in ma_filters:
            c_name = ma["col_name"]
            if ma["enabled"] and c_name in df.columns:
                df = df[df['close'] > df[c_name]]
            
        if tv_vol_col in df.columns:
            df['val_traded_inr'] = df['close'] * df[tv_vol_col]
            df = df[df['val_traded_inr'] >= (min_vol_cr * 10_000_000)]
            
        if 'price_52_week_low' in df.columns:
            pct_above_low = ((df['close'] - df['price_52_week_low']) / df['price_52_week_low']) * 100
            df = df[pct_above_low >= min_above_52l]
            
        if 'price_52_week_high' in df.columns:
            pct_below_high = ((df['price_52_week_high'] - df['close']) / df['price_52_week_high']) * 100
            df = df[pct_below_high <= max_below_52h]

        if df.empty:
            st.warning("No stocks passed all criteria. Try broadening your NSE Sector/Industry selections.")
        else:
            total_passed = len(df)
            rc = st.session_state.reset_counter
            
            # ------------------------------------------
            # SECTOR & INDUSTRY ROTATION TABLES
            # ------------------------------------------
            st.subheader("📊 Scan Summary & Market Rotation")
            tab_sector_sum, tab_industry_sum = st.tabs(["🛠️ Sector Summary", "🏢 Basic Industry Summary"])
            
            with tab_sector_sum:
                sec_counts = df['Sector'].value_counts().reset_index()
                sec_counts.columns = ['Sector', 'Number of Stocks Passed']
                sec_counts['% Share of Passed Stocks'] = ((sec_counts['Number of Stocks Passed'] / total_passed) * 100).round(1)
                sec_counts['% of Stocks Passed Amongst Total Stocks in the Sector'] = sec_counts.apply(
                    lambda r: round((r['Number of Stocks Passed'] / total_sector_counts.get(r['Sector'], 1)) * 100, 1), axis=1
                )
                c_chart1, c_table1 = st.columns([1.1, 1.3])
                with c_chart1:
                    fig_sec = px.pie(sec_counts, names='Sector', values='Number of Stocks Passed', hole=0.55)
                    fig_sec.update_traces(textinfo='percent', textposition='inside')
                    fig_sec.update_layout(annotations=[dict(text=f"<b>Total Stocks:<br>{total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)], showlegend=False, margin=dict(t=20, b=10, l=20, r=20), height=360)
                    chart_ev_sec = st.plotly_chart(fig_sec, use_container_width=True, on_select="rerun", selection_mode="points", key=f"sec_chart_{rc}")
                    st.caption("Note: All Percentages are Based on the Total Number of Passed Stocks")
                with c_table1:
                    table_ev_sec = st.dataframe(sec_counts, use_container_width=True, hide_index=True, height=360, on_select="rerun", selection_mode="multi-row", key=f"sec_table_{rc}")
                sel_sec_chart = parse_chart_selection_multi(chart_ev_sec)
                sel_sec_table = parse_table_selection_multi(table_ev_sec, sec_counts, "Sector")
                active_sectors = sel_sec_table if sel_sec_table else sel_sec_chart

            with tab_industry_sum:
                if active_sectors:
                    df_ind_source = df[df['Sector'].isin(active_sectors)]
                    ind_total_passed = len(df_ind_source)
                    st.info(f"🏢 **Hierarchical View:** Showing Basic Industries inside **{', '.join(active_sectors)}** ({ind_total_passed} Stocks)")
                else:
                    df_ind_source = df
                    ind_total_passed = total_passed
                ind_counts = df_ind_source['Industry'].value_counts().reset_index()
                ind_counts.columns = ['Basic Industry', 'Number of Stocks Passed']
                ind_counts['% Share of Passed Stocks'] = ((ind_counts['Number of Stocks Passed'] / max(ind_total_passed, 1)) * 100).round(1)
                ind_counts['% of Stocks Passed Amongst Total Stocks in the Industry'] = ind_counts.apply(
                    lambda r: round((r['Number of Stocks Passed'] / total_industry_counts.get(r['Basic Industry'], 1)) * 100, 1), axis=1
                )
                sec_hash = "_".join(sorted(active_sectors)) if active_sectors else "all"
                c_chart2, c_table2 = st.columns([1.1, 1.3])
                with c_chart2:
                    fig_ind = px.pie(ind_counts, names='Basic Industry', values='Number of Stocks Passed', hole=0.55)
                    fig_ind.update_traces(textinfo='percent', textposition='inside')
                    fig_ind.update_layout(annotations=[dict(text=f"<b>Total Stocks:<br>{ind_total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)], showlegend=False, margin=dict(t=20, b=10, l=20, r=20), height=360)
                    chart_ev_ind = st.plotly_chart(fig_ind, use_container_width=True, on_select="rerun", selection_mode="points", key=f"ind_chart_{rc}_{sec_hash}")
                    st.caption("Note: All Percentages are Based on the Total Number of Passed Stocks")
                with c_table2:
                    table_ev_ind = st.dataframe(ind_counts, use_container_width=True, hide_index=True, height=360, on_select="rerun", selection_mode="multi-row", key=f"ind_table_{rc}_{sec_hash}")
                sel_ind_chart = parse_chart_selection_multi(chart_ev_ind)
                sel_ind_table = parse_table_selection_multi(table_ev_ind, ind_counts, "Basic Industry")
                active_industries = sel_ind_table if sel_ind_table else sel_ind_chart

            # ------------------------------------------
            # ACTIVE DRILLDOWN & DISPLAY PREPARATION
            # ------------------------------------------
            st.markdown("---")
            df_display = df.copy()
            if active_sectors:
                df_display = df_display[df_display['Sector'].isin(active_sectors)]
            if active_industries:
                df_display = df_display[df_display['Industry'].isin(active_industries)]
                
            if active_sectors or active_industries:
                filter_labels = []
                if active_sectors: filter_labels.append(f"**Sector:** {', '.join(active_sectors)}")
                if active_industries: filter_labels.append(f"**Industry:** {', '.join(active_industries)}")
                col_info, col_reset = st.columns([3, 1])
                with col_info:
                    st.info(f"🔍 **Active Drilldown:** {' | '.join(filter_labels)} ({len(df_display)} Stocks)")
                with col_reset:
                    if st.button("🔄 Reset Scan Results (Show All)", type="primary", use_container_width=True):
                        st.session_state.reset_counter += 1
                        st.rerun()

            # --- SERIAL NUMBER ADDED ---
            df_display['S.No.'] = range(1, len(df_display) + 1)
            
            df_display['Market Cap (₹ Cr)'] = (df_display['market_cap_basic'] / 10_000_000).round(2)
            vol_display_label = f"{vol_period_days}D Close×AvgVol (₹ Cr)"
            df_display[vol_display_label] = (df_display['val_traded_inr'] / 10_000_000).round(2)
            df_display['Close'] = df_display['close'].round(2)
            df_display['Change %'] = df_display['change'].round(2)
            df_display['ADR %'] = df_display['ADR_pct'].round(2)
            df_display['TV_Symbol'] = df_display['exchange'] + ":" + df_display['name']
            
            # Clickable TradingView Deep-Link for every row
            df_display['TV_Link'] = "https://www.tradingview.com/chart/?symbol=NSE:" + df_display['name']
            
            active_ma_labels = []
            for ma in ma_filters:
                if ma["enabled"] and ma["col_name"] in df_display.columns:
                    df_display[ma["label"]] = df_display[ma["col_name"]].round(2)
                    active_ma_labels.append(ma["label"])
            
            table_columns = [
                'S.No.', 'TV_Symbol', 'name', 'Close', 'Change %', 
                'ADR %'
            ] + active_ma_labels + [
                vol_display_label, 'Market Cap (₹ Cr)', 
                'Sector', 'Industry', 'TV_Link'
            ]

            # ------------------------------------------
            # SCAN RESULTS TABLE
            # ------------------------------------------
            st.subheader(f"📋 Scan Results ({len(df_display)} Stocks Found)")
            
            table_ev_scan = st.dataframe(
                df_display[table_columns], 
                use_container_width=True, 
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                column_config={
                    "TV_Link": st.column_config.LinkColumn("TradingView", display_text="↗️ Chart")
                },
                key=f"scan_table_{rc}"
            )
            
            selected_rows = parse_table_selection_multi(table_ev_scan, df_display, "TV_Symbol")
            
            # 1-CLICK ADD SELECTED TO WATCHLIST
            st.markdown("---")
            cw1, cw2, cw3 = st.columns([1.8, 1.5, 1.2])
            with cw1:
                target_wl = st.selectbox("Select Target Watchlist to Add Setups:", options=list(st.session_state.watchlists.keys()), index=list(st.session_state.watchlists.keys()).index(st.session_state.active_watchlist_name), key="wl_table_target_select")
            with cw2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"➕ Add Selected Setups ({len(selected_rows)}) to Watchlist", type="primary", use_container_width=True, disabled=len(selected_rows)==0):
                    current_list = st.session_state.watchlists[target_wl]
                    added_cnt = 0
                    for sym in selected_rows:
                        if sym not in current_list:
                            current_list.append(sym)
                            added_cnt += 1
                    st.success(f"✅ Successfully added {added_cnt} new stocks to **{target_wl}**!")
            with cw3:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption("💡 Check rows above to enable bulk quick-add.")

            # --- SELECTIVE vs ALL TRADINGVIEW EXPORT ---
            st.markdown("---")
            if len(selected_rows) > 0:
                st.subheader(f"📋 Copy Selected Setups to TradingView ({len(selected_rows)} Stocks)")
                st.code(", ".join(selected_rows), language="text")
            
            st.subheader(f"📋 Copy All Results to TradingView ({len(df_display)} Stocks)")
            tv_watchlist_string = ", ".join(df_display['TV_Symbol'].tolist())
            st.code(tv_watchlist_string, language="text")

# ==========================================
# TAB 2: WATCHLIST STUDIO & TRADINGVIEW BRIDGE
# ==========================================
with tab_watchlists:
    st.subheader("⭐ Multi-Watchlist Studio & TradingView Bridge")
    
    col_sel, col_new, col_del = st.columns([2.0, 1.8, 1.0])
    with col_sel:
        wl_names = list(st.session_state.watchlists.keys())
        active_wl = st.selectbox(
            "Select Active Watchlist:",
            options=wl_names,
            index=wl_names.index(st.session_state.active_watchlist_name) if st.session_state.active_watchlist_name in wl_names else 0,
            key="wl_active_selector"
        )
        st.session_state.active_watchlist_name = active_wl
    with col_new:
        with st.form("create_wl_form", clear_on_submit=True):
            new_wl_name = st.text_input("Create New Watchlist:", placeholder="e.g., Q3 Breakout Watch")
            if st.form_submit_button("➕ Create Watchlist", use_container_width=True):
                if new_wl_name and new_wl_name not in st.session_state.watchlists:
                    st.session_state.watchlists[new_wl_name] = []
                    st.session_state.active_watchlist_name = new_wl_name
                    st.success(f"Created Watchlist: {new_wl_name}")
                    st.rerun()
    with col_del:
        st.markdown("<br>", unsafe_allow_html=True)
        if len(wl_names) > 1:
            if st.button("🗑️ Delete Watchlist", type="secondary", use_container_width=True):
                del st.session_state.watchlists[active_wl]
                st.session_state.active_watchlist_name = list(st.session_state.watchlists.keys())[0]
                st.rerun()

    with st.expander("📥 Import / Paste Tickers from TradingView & Backup JSON Library", expanded=False):
        ci1, ci2 = st.columns([2, 1])
        with ci1:
            pasted_text = st.text_area("Paste Tickers from TradingView (Comma, Space, or Newline separated):", placeholder="NSE:RELIANCE, BSE:TCS, ZOMATO, TRENT\nNSE:HAL")
            if st.button("➕ Import Tickers into Current Watchlist", type="primary"):
                parsed_symbols = parse_pasted_tickers(pasted_text)
                current_list = st.session_state.watchlists[active_wl]
                added = 0
                for s in parsed_symbols:
                    if s not in current_list:
                        current_list.append(s)
                        added += 1
                st.success(f"✅ Imported {added} symbols into **{active_wl}**!")
                st.rerun()
        with ci2:
            st.markdown("#### 💾 Backup & Restore Library")
            json_str = json.dumps(st.session_state.watchlists, indent=2)
            st.download_button(
                label="📥 Download All Watchlists (JSON)",
                data=json_str,
                file_name="my_india_watchlists.json",
                mime="application/json",
                use_container_width=True
            )
            uploaded_file = st.file_uploader("Restore Watchlists (JSON):", type=["json"], label_visibility="collapsed")
            if uploaded_file is not None:
                try:
                    loaded_wls = json.load(uploaded_file)
                    if isinstance(loaded_wls, dict):
                        st.session_state.watchlists = loaded_wls
                        st.session_state.active_watchlist_name = list(loaded_wls.keys())[0]
                        st.success("✅ Watchlists restored successfully!")
                        st.rerun()
                except Exception as e:
                    st.error("Invalid JSON format.")

    current_symbols = st.session_state.watchlists[active_wl]
    if not current_symbols:
        st.info(f"The watchlist **{active_wl}** is currently empty. Add setups from the Screener tab or paste symbols above!")
    else:
        with st.spinner(f"📡 Enriching {len(current_symbols)} Tickers with Live Price & ADR%..."):
            enriched_df = fetch_watchlist_enrichMENT(current_symbols)

        ordered_df = pd.DataFrame({"TV_Symbol": current_symbols})
        if not enriched_df.empty:
            merged_df = ordered_df.merge(enriched_df, on="TV_Symbol", how="left")
        else:
            merged_df = ordered_df.copy()
            for col_name in ['name', 'Close', 'Change %', 'ADR_pct', 'Market Cap (₹ Cr)', 'Sector', 'Industry']:
                merged_df[col_name] = "N/A"

        # --- SERIAL NUMBER ADDED TO WATCHLIST ---
        merged_df['S.No.'] = range(1, len(merged_df) + 1)
        merged_df['ADR %'] = merged_df.get('ADR_pct', "N/A")
        
        # Clickable TradingView Deep-Link for Watchlist symbols
        merged_df['TV_Link'] = "https://www.tradingview.com/chart/?symbol=" + merged_df['TV_Symbol']
        wl_cols = ['S.No.', 'TV_Symbol', 'Close', 'Change %', 'ADR %', 'Market Cap (₹ Cr)', 'Sector', 'Industry', 'TV_Link']

        st.markdown(f"### ⭐ Watchlist: **{active_wl}** ({len(current_symbols)} Stocks)")

        wl_table_event = st.dataframe(
            merged_df[wl_cols],
            use_container_width=True,
            hide_index=True,
            height=460,
            on_select="rerun",
            selection_mode="multi-row",
            column_config={
                "TV_Link": st.column_config.LinkColumn("TradingView", display_text="↗️ Chart")
            },
            key="wl_manage_table"
        )

        sel_to_remove = parse_table_selection_multi(wl_table_event, merged_df, "TV_Symbol")
        if sel_to_remove:
            if st.button(f"🗑️ Remove Selected ({len(sel_to_remove)}) from '{active_wl}'", type="secondary"):
                for sym in sel_to_remove:
                    if sym in st.session_state.watchlists[active_wl]:
                        st.session_state.watchlists[active_wl].remove(sym)
                st.rerun()

        st.markdown("---")
        st.subheader("📋 Copy Watchlist to TradingView Clipboard")
        tv_export_string = ", ".join(current_symbols)
        st.code(tv_export_string, language="text")
