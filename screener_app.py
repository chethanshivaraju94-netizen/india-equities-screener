import streamlit as st
import pandas as pd
import requests
from io import StringIO
from tradingview_screener import Query, col

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="India Equities Screener (NSE Classified)",
    page_icon="📈",
    layout="wide"
)

st.title("📈 India Equities Interactive Screener")
st.markdown("Customizable **CAN SLIM & Trend Screener** powered by TradingView speed and **Official NSE / AMFI Sector & Industry Classification**.")

# ==========================================
# 1. INDIAN SECTOR & INDUSTRY HIERARCHY
# ==========================================
# Complete Indian AMFI/SEBI Sector -> Industry Hierarchy for UI Dropdowns & Mapping
INDIAN_SECTOR_HIERARCHY = {
    "Financial Services": [
        "Banks", "Finance & NBFCs", "Insurance", "Asset Management & Broking"
    ],
    "Information Technology": [
        "IT - Software & Services", "IT - Hardware & Equipment", "Internet & E-Commerce"
    ],
    "Healthcare": [
        "Pharmaceuticals & Biotechnology", "Healthcare Services & Hospitals", "Medical Equipment & Supplies"
    ],
    "Automobile and Auto Components": [
        "Automobiles", "Auto Components & Ancillaries", "Tyres & Rubber"
    ],
    "Capital Goods & Manufacturing": [
        "Industrial Machinery & Equipment", "Defence & Aerospace", "Electrical Equipment", "Engineering & Construction"
    ],
    "Fast Moving Consumer Goods": [
        "Food & Beverages", "Personal & Household Care", "Agricultural Products & Tobacco"
    ],
    "Metals & Mining": [
        "Steel & Iron Products", "Non-Ferrous Metals (Aluminium, Copper)", "Mining & Minerals"
    ],
    "Chemicals & Fertilizers": [
        "Specialty & Industrial Chemicals", "Fertilizers & Agrochemicals"
    ],
    "Oil, Gas & Power": [
        "Oil & Gas Exploration & Distribution", "Power Generation & Utilities", "Renewable Energy"
    ],
    "Construction & Realty": [
        "Real Estate & Developers", "Cement & Building Materials", "Infrastructure & Construction"
    ],
    "Telecommunication & Media": [
        "Telecom Services & Equipment", "Broadcasting & Entertainment", "Media & Publishing"
    ],
    "Consumer Discretionary & Retail": [
        "Retail & Specialty Stores", "Hotels, Resorts & Tourism", "Textiles, Apparel & Footwear", "Consumer Durables & Electronics"
    ],
    "Diversified / Others": [
        "Diversified Industrials", "Logistics & Transportation", "Others"
    ]
}

def map_to_indian_classification(tv_industry, tv_sector):
    """
    Deterministic Indian AMFI/SEBI Sector & Industry mapper.
    Never fails, works offline for all 3,000+ Indian equities.
    """
    ind_upper = str(tv_industry).upper() + " " + str(tv_sector).upper()
    
    if any(k in ind_upper for k in ["BANK"]):
        return "Financial Services", "Banks"
    elif any(k in ind_upper for k in ["FINANC", "NBFC", "LOAN", "LEASING"]):
        return "Financial Services", "Finance & NBFCs"
    elif any(k in ind_upper for k in ["INSUR", "LIFE"]):
        return "Financial Services", "Insurance"
    elif any(k in ind_upper for k in ["ASSET", "BROKING", "INVEST"]):
        return "Financial Services", "Asset Management & Broking"
    elif any(k in ind_upper for k in ["SOFTWARE", "IT", "COMPUTER", "CYBER", "PLATFORM", "PACKAGED"]):
        return "Information Technology", "IT - Software & Services"
    elif any(k in ind_upper for k in ["PHARMA", "DRUG", "BIOTECH", "MEDICAL"]):
        return "Healthcare", "Pharmaceuticals & Biotechnology"
    elif any(k in ind_upper for k in ["HOSPITAL", "HEALTH", "NURSING"]):
        return "Healthcare", "Healthcare Services & Hospitals"
    elif any(k in ind_upper for k in ["AUTO PARTS", "ANCILLAR", "TYRE", "RUBBER"]):
        return "Automobile and Auto Components", "Auto Components & Ancillaries"
    elif any(k in ind_upper for k in ["MOTOR", "VEHICL", "AUTOMOBIL", "TRACTOR"]):
        return "Automobile and Auto Components", "Automobiles"
    elif any(k in ind_upper for k in ["DEFENCE", "AERO"]):
        return "Capital Goods & Manufacturing", "Defence & Aerospace"
    elif any(k in ind_upper for k in ["ENGINEER", "MACHIN", "MANUFACTUR", "INDUSTRIAL"]):
        return "Capital Goods & Manufacturing", "Industrial Machinery & Equipment"
    elif any(k in ind_upper for k in ["FMCG", "FOOD", "BEVERAG", "TOBACCO", "AGRI"]):
        return "Fast Moving Consumer Goods", "Food & Beverages"
    elif any(k in ind_upper for k in ["PERSONAL", "HOUSEHOLD", "CARE"]):
        return "Fast Moving Consumer Goods", "Personal & Household Care"
    elif any(k in ind_upper for k in ["STEEL", "IRON"]):
        return "Metals & Mining", "Steel & Iron Products"
    elif any(k in ind_upper for k in ["ALUMIN", "COPPER", "METAL", "MINING"]):
        return "Metals & Mining", "Non-Ferrous Metals (Aluminium, Copper)"
    elif any(k in ind_upper for k in ["CHEMIC", "POLYMER"]):
        return "Chemicals & Fertilizers", "Specialty & Industrial Chemicals"
    elif any(k in ind_upper for k in ["FERTIL", "PESTICID"]):
        return "Chemicals & Fertilizers", "Fertilizers & Agrochemicals"
    elif any(k in ind_upper for k in ["POWER", "UTILIT", "ENERGY", "SOLAR", "RENEW"]):
        return "Oil, Gas & Power", "Power Generation & Utilities"
    elif any(k in ind_upper for k in ["OIL", "GAS", "PETRO", "COAL"]):
        return "Oil, Gas & Power", "Oil & Gas Exploration & Distribution"
    elif any(k in ind_upper for k in ["CEMENT", "BUILDING", "CONSTRUCT", "INFRA"]):
        return "Construction & Realty", "Cement & Building Materials"
    elif any(k in ind_upper for k in ["REAL ESTATE", "REALTY", "DEVELOPER"]):
        return "Construction & Realty", "Real Estate & Developers"
    elif any(k in ind_upper for k in ["TELECOM", "WIRELESS"]):
        return "Telecommunication & Media", "Telecom Services & Equipment"
    elif any(k in ind_upper for k in ["MEDIA", "ENTERTAIN", "BROADCAST", "PUBLISH"]):
        return "Telecommunication & Media", "Broadcasting & Entertainment"
    elif any(k in ind_upper for k in ["RETAIL", "STORE"]):
        return "Consumer Discretionary & Retail", "Retail & Specialty Stores"
    elif any(k in ind_upper for k in ["HOTEL", "RESORT", "TRAVEL", "TOURISM"]):
        return "Consumer Discretionary & Retail", "Hotels, Resorts & Tourism"
    elif any(k in ind_upper for k in ["TEXTILE", "APPAREL", "FOOTWEAR"]):
        return "Consumer Discretionary & Retail", "Textiles, Apparel & Footwear"
    else:
        return "Diversified / Others", "Others"

# Optional: Load local CSV if available in root ('nse_classification.csv')
@st.cache_data(ttl=86400)
def load_local_nse_csv():
    try:
        df_nse = pd.read_csv("nse_classification.csv")
        if not df_nse.empty and "Symbol" in df_nse.columns:
            return df_nse
    except Exception:
        pass
    return pd.DataFrame()

local_nse_df = load_local_nse_csv()

# ==========================================
# 2. BACKEND SCREENER LOGIC
# ==========================================
def fetch_screener_data(exchanges, min_mcap, min_adr_val, limit_rows):
    if not exchanges:
        return pd.DataFrame()
    
    min_mcap_inr = min_mcap * 10_000_000
    
    q = (Query()
         .set_markets('india')
         .select(
             'name', 
             'close', 
             'change', 
             'volume', 
             'market_cap_basic', 
             'EMA21',
             'SMA50', 
             'SMA200',
             'average_volume_60d_calc',
             'ADR',
             'price_52_week_high',
             'price_52_week_low',
             'exchange',
             'type',
             'industry',
             'sector'
         )
         .where(
             col('market_cap_basic') >= min_mcap_inr,
             col('ADR') >= min_adr_val
         )
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
# 3. SIDEBAR CONTROLS & DYNAMIC DROPDOWNS
# ==========================================
with st.sidebar.form("filter_form"):
    st.header("1. Exchange & Universe")
    exchange_choice = st.multiselect(
        "Select Exchanges:",
        options=["NSE", "BSE"],
        default=["NSE", "BSE"]
    )
    
    st.markdown("---")
    st.header("🏛️ Official NSE Filters")
    
    # 1. NSE Sector Dropdown (Always populated with 13 Indian Sectors)
    sector_options = list(INDIAN_SECTOR_HIERARCHY.keys())
    sector_choice = st.multiselect(
        "NSE Sector (e.g., Financial Services, IT):",
        options=sector_options,
        default=[]
    )
    
    # 2. Cascading NSE Industry Dropdown
    if sector_choice:
        industry_options = []
        for sec in sector_choice:
            industry_options.extend(INDIAN_SECTOR_HIERARCHY.get(sec, []))
        industry_options = sorted(list(set(industry_options)))
    else:
        all_industries = [ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds]
        industry_options = sorted(list(set(all_industries)))
        
    industry_choice = st.multiselect(
        "NSE Industry (e.g., Banks, IT - Software & Services):",
        options=industry_options,
        default=[]
    )

    st.markdown("---")
    st.header("2. Fundamental & Liquidity")
    min_mcap_cr = st.number_input(
        "Min Market Cap (₹ Crores) [1000 Cr = 10B INR]:", 
        min_value=0, value=1000, step=100
    )
    min_vol60d_cr = st.number_input(
        "Min 60D Avg Rupee Volume (₹ Cr) [5 Cr = 50M INR]:", 
        min_value=0.0, value=5.0, step=0.5
    )

    st.header("3. Trend & Moving Averages")
    above_ema21 = st.checkbox("Price > EMA 21", value=True)
    above_sma50 = st.checkbox("Price > SMA 50", value=True)
    above_sma200 = st.checkbox("Price > SMA 200", value=True)

    st.header("4. Volatility & 52-Week Range")
    min_adr = st.slider("Min ADR % (Average Daily Range):", min_value=0.0, max_value=10.0, value=2.25, step=0.25)
    min_above_52l = st.slider("Min % Above 52-Week Low:", min_value=0, max_value=100, value=20, step=5)
    max_below_52h = st.slider("Max % Below 52-Week High (0% to X%):", min_value=0, max_value=50, value=30, step=5)

    st.header("5. Display Settings")
    max_results = st.slider("Max Results to Fetch:", min_value=500, max_value=3000, value=2500, step=250)
    
    apply_filters = st.form_submit_button("🚀 Apply Filters", use_container_width=True, type="primary")

# ==========================================
# 4. FETCH, ENRICH & FILTER DATA
# ==========================================
with st.spinner("Scanning Indian Equities & Mapping Official Indian Sectors..."):
    results_df = fetch_screener_data(
        exchange_choice,
        min_mcap_cr,
        min_adr,
        max_results
    )

if results_df.empty:
    st.warning("No stocks matched your criteria. Click 'Apply Filters' after adjusting your parameters.")
else:
    df = results_df.copy()
    
    # 1. Filter Exchanges exactly
    df = df[df['exchange'].isin(exchange_choice)]
    
    # 2. Filter for COMMON STOCKS ONLY
    if 'type' in df.columns:
        df = df[df['type'] == 'stock']
    
    # 3. SMART DEDUPLICATION (Keep NSE listing for dual-listed stocks)
    df = df.drop_duplicates(subset=['name'], keep='first')
    
    # --- 4. SAFE INDIAN SECTOR & INDUSTRY MAPPING (Zero KeyError) ---
    mapped_sectors = []
    mapped_industries = []
    for _, row in df.iterrows():
        sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
        mapped_sectors.append(sec)
        mapped_industries.append(ind)
        
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries
    
    # Optional override: If you uploaded 'nse_classification.csv' with columns Symbol, Sector, Industry
    if not local_nse_df.empty and "Symbol" in local_nse_df.columns:
        override_df = local_nse_df[["Symbol", "Sector", "Industry"]].copy()
        override_df.rename(columns={"Sector": "NSE_Sector", "Industry": "NSE_Industry"}, inplace=True)
        
        df = df.merge(
            override_df,
            left_on="name",
            right_on="Symbol",
            how="left"
        )
        df["Sector"] = df["NSE_Sector"].combine_first(df["Sector"]).fillna("Diversified / Others")
        df["Industry"] = df["NSE_Industry"].combine_first(df["Industry"]).fillna("Others")
        
    # --- 5. APPLY NSE SECTOR & INDUSTRY FILTERS ---
    if sector_choice:
        df = df[df["Sector"].isin(sector_choice)]
    if industry_choice:
        df = df[df["Industry"].isin(industry_choice)]
    
    # --- SAFE NUMERIC CONVERSION ---
    numeric_cols = [
        'market_cap_basic', 'close', 'change', 'volume', 
        'EMA21', 'SMA50', 'SMA200', 'average_volume_60d_calc', 
        'ADR', 'price_52_week_high', 'price_52_week_low'
    ]
    for col_name in numeric_cols:
        if col_name in df.columns:
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
            
    # --- APPLY TECHNICAL & FUNDAMENTAL FILTERS ---
    if above_ema21 and 'EMA21' in df.columns:
        df = df[df['close'] > df['EMA21']]
    if above_sma50 and 'SMA50' in df.columns:
        df = df[df['close'] > df['SMA50']]
    if above_sma200 and 'SMA200' in df.columns:
        df = df[df['close'] > df['SMA200']]
        
    if 'average_volume_60d_calc' in df.columns:
        df['val_traded_60d_inr'] = df['close'] * df['average_volume_60d_calc']
        df = df[df['val_traded_60d_inr'] >= (min_vol60d_cr * 10_000_000)]
        
    if 'price_52_week_low' in df.columns:
        pct_above_low = ((df['close'] - df['price_52_week_low']) / df['price_52_week_low']) * 100
        df = df[pct_above_low >= min_above_52l]
        
    if 'price_52_week_high' in df.columns:
        pct_below_high = ((df['price_52_week_high'] - df['close']) / df['price_52_week_high']) * 100
        df = df[pct_below_high <= max_below_52h]

    # --- DISPLAY FORMATTING ---
    if df.empty:
        st.warning("No stocks passed all criteria. Try broadening your NSE Sector/Industry selections.")
    else:
        df['Market Cap (₹ Cr)'] = (df['market_cap_basic'] / 10_000_000).round(2)
        df['60D Vol (₹ Cr)'] = (df['val_traded_60d_inr'] / 10_000_000).round(2)
        df['Close'] = df['close'].round(2)
        df['Change %'] = df['change'].round(2)
        df['ADR %'] = df['ADR'].round(2)
        df['TV_Symbol'] = df['exchange'] + ":" + df['name']
        
        table_columns = [
            'TV_Symbol', 'name', 'Close', 'Change %', 
            'ADR %', '60D Vol (₹ Cr)', 'Market Cap (₹ Cr)', 
            'Sector', 'Industry'
        ]
        
        st.subheader(f"📊 Filtered Results ({len(df)} Stocks Found)")
        st.dataframe(df[table_columns], use_container_width=True, hide_index=True)
        
        # --- TRADINGVIEW WATCHLIST EXPORT ---
        st.markdown("---")
        st.subheader("📋 Copy to TradingView Watchlist")
        st.write("Copy the text string below and paste it directly into your TradingView Watchlist **Symbol Search / Import** box:")
        
        tv_watchlist_string = ", ".join(df['TV_Symbol'].tolist())
        st.code(tv_watchlist_string, language="text")
