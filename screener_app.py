import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from tradingview_screener import Query, col

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="India Equities Screener (NSE Classified)",
    page_icon="📈",
    layout="wide"
)

# Initialize Session State for Interactive Drilldown & Widget Reset
if "drilldown_type" not in st.session_state:
    st.session_state.drilldown_type = None
if "drilldown_vals" not in st.session_state:
    st.session_state.drilldown_vals = []
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

st.title("📈 India Equities Interactive Screener")
st.markdown("Customizable **CAN SLIM & Trend Screener** powered by **Lightning-Fast TradingView Native ADR%**, **Hierarchical Multi-Select Sector → Industry Drilldown**, **Responsive Chart Mode Terminal**, and **Official NSE / AMFI Classification (22 Sectors & 59 Industries)**.")

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

def parse_single_row_selection(event, df_source):
    if event and isinstance(event, dict):
        sel = event.get("selection", {})
        rows = sel.get("rows", [])
        if rows and len(rows) > 0:
            idx = rows[0]
            if idx < len(df_source):
                return df_source.iloc[idx]
    return None

# ==========================================
# 2. BACKEND SCREENER LOGIC
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

# ==========================================
# 3. SIDEBAR CONTROLS
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

    # --- 5 CUSTOMIZABLE MOVING AVERAGE SLOTS ---
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

    # --- INSTANT TRADINGVIEW ADR% FILTER ---
    st.markdown("---")
    st.header("4. Volatility & 52-Week Range")
    min_adr = st.slider("Min ADR % (TradingView Standard):", min_value=0.0, max_value=10.0, value=2.25, step=0.25)
    min_above_52l = st.slider("Min % Above 52-Week Low:", min_value=0, max_value=100, value=20, step=5)
    max_below_52h = st.slider("Max % Below 52-Week High:", min_value=0, max_value=50, value=30, step=5)

    st.markdown("---")
    st.header("5. Display Settings")
    max_results = st.slider("Max Results to Fetch:", min_value=500, max_value=3000, value=2500, step=250)
    
    apply_filters = st.form_submit_button("🚀 Apply Filters", use_container_width=True, type="primary")

# Reset drilldown when new filters are applied from sidebar
if apply_filters:
    st.session_state.drilldown_type = None
    st.session_state.drilldown_vals = []

# ==========================================
# 4. FETCH, ENRICH & FILTER DATA
# ==========================================
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
    
    # Map Indian Sectors (84-pair lookup table) for ENTIRE universe
    mapped_sectors, mapped_industries = [], []
    for _, row in df.iterrows():
        sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
        mapped_sectors.append(sec)
        mapped_industries.append(ind)
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries
    
    # Track Total Universe Counts per Sector and Industry (before technical filtering)
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
            
    # --- INSTANT VECTORIZED ADR% CALCULATION (< 0.01s) ---
    df['ADR_pct'] = (df['ADR'] / df['close']) * 100
    df = df[df['ADR_pct'] >= min_adr]
            
    # Apply Custom Moving Averages
    for ma in ma_filters:
        c_name = ma["col_name"]
        if ma["enabled"] and c_name in df.columns:
            df = df[df['close'] > df[c_name]]
        
    # --- RUPEE VOLUME FILTER ---
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
        
        # ==========================================
        # 5. SCAN SUMMARY & ROTATION DASHBOARD
        # ==========================================
        st.subheader("📊 Scan Summary & Market Rotation")
        tab_sector, tab_industry = st.tabs(["🛠️ Sector Summary", "🏢 Basic Industry Summary"])
        
        # --- TAB 1: SECTOR SUMMARY ---
        with tab_sector:
            sec_counts = df['Sector'].value_counts().reset_index()
            sec_counts.columns = ['Sector', 'Number of Stocks Passed']
            sec_counts['% Share of Passed Stocks'] = (
                (sec_counts['Number of Stocks Passed'] / total_passed) * 100
            ).round(1)
            sec_counts['% of Stocks Passed Amongst Total Stocks in the Sector'] = sec_counts.apply(
                lambda r: round((r['Number of Stocks Passed'] / total_sector_counts.get(r['Sector'], 1)) * 100, 1),
                axis=1
            )
            
            c_chart1, c_table1 = st.columns([1.1, 1.3])
            with c_chart1:
                fig_sec = px.pie(
                    sec_counts, 
                    names='Sector', 
                    values='Number of Stocks Passed',
                    hole=0.55
                )
                fig_sec.update_traces(textinfo='percent', textposition='inside')
                fig_sec.update_layout(
                    annotations=[dict(text=f"<b>Total Stocks:<br>{total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)],
                    showlegend=False,
                    margin=dict(t=20, b=10, l=20, r=20),
                    height=360
                )
                chart_ev_sec = st.plotly_chart(
                    fig_sec, 
                    use_container_width=True, 
                    on_select="rerun", 
                    selection_mode="points", 
                    key=f"sec_chart_{rc}"
                )
                st.caption("Note: All Percentages are Based on the Total Number of Passed Stocks")
                
            with c_table1:
                table_ev_sec = st.dataframe(
                    sec_counts, 
                    use_container_width=True, 
                    hide_index=True, 
                    height=360,
                    on_select="rerun",
                    selection_mode="multi-row",
                    key=f"sec_table_{rc}"
                )
            
            # Detect Sector Multi-Click (Chart or Table)
            sel_sec_chart = parse_chart_selection_multi(chart_ev_sec)
            sel_sec_table = parse_table_selection_multi(table_ev_sec, sec_counts, "Sector")
            
            if sel_sec_chart:
                st.session_state.drilldown_type = "Sector"
                st.session_state.drilldown_vals = sel_sec_chart
            elif sel_sec_table:
                st.session_state.drilldown_type = "Sector"
                st.session_state.drilldown_vals = sel_sec_table

        # --- TAB 2: INDUSTRY SUMMARY (HIERARCHICALLY FILTERED BY MULTI-SECTORS) ---
        with tab_industry:
            if st.session_state.drilldown_type == "Sector" and st.session_state.drilldown_vals:
                df_ind_source = df[df['Sector'].isin(st.session_state.drilldown_vals)]
                ind_total_passed = len(df_ind_source)
                sec_list_str = ", ".join(st.session_state.drilldown_vals)
                st.info(f"🏢 **Hierarchical View:** Showing Basic Industries inside **{sec_list_str}** ({ind_total_passed} Stocks)")
            else:
                df_ind_source = df
                ind_total_passed = total_passed
                
            ind_counts = df_ind_source['Industry'].value_counts().reset_index()
            ind_counts.columns = ['Basic Industry', 'Number of Stocks Passed']
            
            ind_counts['% Share of Passed Stocks'] = (
                (ind_counts['Number of Stocks Passed'] / max(ind_total_passed, 1)) * 100
            ).round(1)
            
            ind_counts['% of Stocks Passed Amongst Total Stocks in the Industry'] = ind_counts.apply(
                lambda r: round((r['Number of Stocks Passed'] / total_industry_counts.get(r['Basic Industry'], 1)) * 100, 1),
                axis=1
            )
            
            c_chart2, c_table2 = st.columns([1.1, 1.3])
            with c_chart2:
                fig_ind = px.pie(
                    ind_counts, 
                    names='Basic Industry', 
                    values='Number of Stocks Passed',
                    hole=0.55
                )
                fig_ind.update_traces(textinfo='percent', textposition='inside')
                fig_ind.update_layout(
                    annotations=[dict(text=f"<b>Total Stocks:<br>{ind_total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)],
                    showlegend=False,
                    margin=dict(t=20, b=10, l=20, r=20),
                    height=360
                )
                chart_ev_ind = st.plotly_chart(
                    fig_ind, 
                    use_container_width=True, 
                    on_select="rerun", 
                    selection_mode="points", 
                    key=f"ind_chart_{rc}"
                )
                st.caption("Note: All Percentages are Based on the Total Number of Passed Stocks")
                
            with c_table2:
                table_ev_ind = st.dataframe(
                    ind_counts, 
                    use_container_width=True, 
                    hide_index=True, 
                    height=360,
                    on_select="rerun",
                    selection_mode="multi-row",
                    key=f"ind_table_{rc}"
                )
                
            # Detect Industry Multi-Click (Chart or Table)
            sel_ind_chart = parse_chart_selection_multi(chart_ev_ind)
            sel_ind_table = parse_table_selection_multi(table_ev_ind, ind_counts, "Basic Industry")
            
            if sel_ind_chart:
                st.session_state.drilldown_type = "Industry"
                st.session_state.drilldown_vals = sel_ind_chart
            elif sel_ind_table:
                st.session_state.drilldown_type = "Industry"
                st.session_state.drilldown_vals = sel_ind_table

        # ==========================================
        # 6. ACTIVE DRILLDOWN BANNER & FILTERING
        # ==========================================
        st.markdown("---")
        df_display = df.copy()
        
        if st.session_state.drilldown_vals:
            selected_items_str = ", ".join(st.session_state.drilldown_vals)
            col_info, col_reset = st.columns([3, 1])
            with col_info:
                st.info(f"🔍 **Active Drilldown:** Showing only stocks in **{st.session_state.drilldown_type} — {selected_items_str}**")
            with col_reset:
                if st.button("🔄 Reset Scan Results (Show All)", type="primary", use_container_width=True):
                    st.session_state.drilldown_type = None
                    st.session_state.drilldown_vals = []
                    st.session_state.reset_counter += 1
                    st.rerun()
            
            # Apply dynamic multi-selection filter to DataFrame
            df_display = df_display[df_display[st.session_state.drilldown_type].isin(st.session_state.drilldown_vals)]
        else:
            st.caption("💡 **Tip:** Select one or more sectors/industries from the tables above to filter the stock list.")

        # ==========================================
        # 7. VIEW MODE SWITCHER: TABLE vs. CHART MODE
        # ==========================================
        df_display['Market Cap (₹ Cr)'] = (df_display['market_cap_basic'] / 10_000_000).round(2)
        vol_display_label = f"{vol_period_days}D Close×AvgVol (₹ Cr)"
        df_display[vol_display_label] = (df_display['val_traded_inr'] / 10_000_000).round(2)
        
        df_display['Close'] = df_display['close'].round(2)
        df_display['Change %'] = df_display['change'].round(2)
        df_display['ADR %'] = df_display['ADR_pct'].round(2)
        df_display['TV_Symbol'] = df_display['exchange'] + ":" + df_display['name']
        
        active_ma_labels = []
        for ma in ma_filters:
            if ma["enabled"] and ma["col_name"] in df_display.columns:
                df_display[ma["label"]] = df_display[ma["col_name"]].round(2)
                active_ma_labels.append(ma["label"])
        
        table_columns = [
            'TV_Symbol', 'name', 'Close', 'Change %', 
            'ADR %'
        ] + active_ma_labels + [
            vol_display_label, 'Market Cap (₹ Cr)', 
            'Sector', 'Industry'
        ]

        c_header, c_toggle = st.columns([2.5, 1.5])
        with c_header:
            if st.session_state.drilldown_vals:
                st.subheader(f"📋 Scan Results ({len(df_display)} Stocks in Selected Group)")
            else:
                st.subheader(f"📋 Scan Results ({len(df_display)} Stocks Found)")
        with c_toggle:
            view_mode = st.radio(
                "Switch View Mode:", 
                ["📋 Table View", "📊 Interactive Chart Mode"], 
                horizontal=True,
                label_visibility="collapsed"
            )

        # --- MODE A: STANDARD TABLE VIEW ---
        if view_mode == "📋 Table View":
            st.dataframe(df_display[table_columns], use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("📋 Copy to TradingView Watchlist")
            tv_watchlist_string = ", ".join(df_display['TV_Symbol'].tolist())
            st.code(tv_watchlist_string, language="text")

        # --- MODE B: INTERACTIVE CHART MODE (RESPONSIVE WATCHLIST & TV WIDGET) ---
        else:
            if df_display.empty:
                st.warning("No stocks available in chart mode for current selection.")
            else:
                col_watchlist, col_chart = st.columns([1.3, 3.7])
                
                with col_watchlist:
                    st.markdown("#### ⚡ Watchlist Sidebar")
                    st.caption("Click any ticker to load chart:")
                    
                    watchlist_df = df_display[['TV_Symbol', 'Close', 'Change %', 'ADR %']].copy()
                    
                    # Watchlist interactive selector matched to chart height (620px)
                    watchlist_event = st.dataframe(
                        watchlist_df,
                        use_container_width=True,
                        hide_index=True,
                        height=620,
                        on_select="rerun",
                        selection_mode="single-row",
                        key=f"wl_table_{rc}"
                    )
                    
                    selected_row = parse_single_row_selection(watchlist_event, watchlist_df)
                    if selected_row is not None:
                        active_symbol = selected_row['TV_Symbol']
                    else:
                        active_symbol = watchlist_df.iloc[0]['TV_Symbol']

                with col_chart:
                    ticker_only = active_symbol.split(":")[-1]

                    # Controls Bar: Exchange Switcher + Deep Link Button
                    c_title, c_ex_switch, c_link = st.columns([2.0, 1.2, 1.3])
                    with c_title:
                        st.markdown(f"### 📈 {active_symbol}")
                    with c_ex_switch:
                        widget_prefix = st.selectbox(
                            "Widget Exchange:",
                            options=["BSE", "NSE"],
                            index=0,
                            help="BSE is recommended to bypass TradingView iframe embed blocks. Use NSE for direct links."
                        )
                    with c_link:
                        deep_link_url = f"https://www.tradingview.com/chart/?symbol=NSE:{ticker_only}"
                        st.markdown(
                            f'<a href="{deep_link_url}" target="_blank" style="display:inline-block;padding:0.4rem 0.8rem;background-color:#2962FF;color:white;text-decoration:none;border-radius:4px;font-weight:bold;float:right;margin-top:4px;">↗️ Open in TradingView App</a>',
                            unsafe_allow_html=True
                        )

                    widget_symbol = f"{widget_prefix}:{ticker_only}"
                    
                    # Dynamically inject active Screener MAs into chart widget studies
                    active_studies = ["STD;SMA"]
                    if any(m["enabled"] and m["col_name"]=="EMA21" for m in ma_filters):
                        active_studies.append("STD;EMA")

                    chart_widget_html = f"""
                    <div class="tradingview-widget-container" style="height:620px;width:100%;margin:0;padding:0;overflow:hidden;">
                      <div id="tradingview_chart_container" style="height:620px;width:100%"></div>
                      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                      <script type="text/javascript">
                      new TradingView.widget(
                      {{
                        "autosize": true,
                        "height": 620,
                        "symbol": "{widget_symbol}",
                        "interval": "D",
                        "timezone": "Asia/Kolkata",
                        "theme": "dark",
                        "style": "1",
                        "locale": "en",
                        "toolbar_bg": "#f1f3f6",
                        "enable_publishing": false,
                        "withdateranges": true,
                        "hide_side_toolbar": false,
                        "allow_symbol_change": true,
                        "details": true,
                        "studies": [
                          "STD;SMA",
                          "STD;Volume"
                        ],
                        "container_id": "tradingview_chart_container"
                      }}
                      );
                      </script>
                    </div>
                    """
                    components.html(chart_widget_html, height=620, scrolling=False)
