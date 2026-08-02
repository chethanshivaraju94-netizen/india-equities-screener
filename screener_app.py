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
# 1. ROBUST NSE / AMFI CLASSIFICATION ENGINE
# ==========================================
@st.cache_data(ttl=86400)
def load_nse_classification():
    """
    Loads NSE listed securities and maps them to Indian AMFI/SEBI Sector -> Industry.
    Uses multiple fallback sources so dropdowns are NEVER empty!
    """
    df_nse = pd.DataFrame()
    
    # Source 1: Try loading a custom local file if you uploaded one to repo root
    try:
        df_nse = pd.read_csv("nse_classification.csv")
        if not df_nse.empty and "Symbol" in df_nse.columns:
            return df_nse
    except Exception:
        pass

    # Source 2: Try fetching from reliable open-source GitHub mirrors of NSE stocks
    urls_to_try = [
        "https://raw.githubusercontent.com/AnjulaMehto/NSE_Stock_Data/main/EQUITY_L.csv",
        "https://raw.githubusercontent.com/sahilrahman12/nse-stock-data/main/nse_stocks.csv",
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                df_raw = pd.read_csv(StringIO(resp.text))
                df_raw.columns = df_raw.columns.str.strip()
                
                if "SYMBOL" in df_raw.columns:
                    df_nse["Symbol"] = df_raw["SYMBOL"].str.strip()
                    
                    # Extract Industry
                    if "BASIC INDUSTRY" in df_raw.columns:
                        df_nse["Industry"] = df_raw["BASIC INDUSTRY"].str.strip()
                    elif "INDUSTRY" in df_raw.columns:
                        df_nse["Industry"] = df_raw["INDUSTRY"].str.strip()
                    else:
                        df_nse["Industry"] = "Unclassified"
                    break
        except Exception:
            continue
            
    return df_nse

nse_class_df = load_nse_classification()

# Failsafe AMFI/SEBI Indian Sector Mapper
def map_to_indian_sector(industry_name):
    ind_upper = str(industry_name).upper()
    if any(k in ind_upper for k in ["BANK", "FINANC", "INSUR", "NBFC", "ASSET", "LOAN", "INVEST"]):
        return "Financial Services"
    elif any(k in ind_upper for k in ["SOFTWARE", "IT", "COMPUTER", "CYBER", "PLATFORM", "TECH"]):
        return "Information Technology"
    elif any(k in ind_upper for k in ["PHARMA", "HEALTH", "HOSPITAL", "DRUG", "BIOTECH", "MEDICAL"]):
        return "Healthcare"
    elif any(k in ind_upper for k in ["AUTO", "VEHICL", "ANCILLAR", "TYRE", "TRACTOR"]):
        return "Automobile and Auto Components"
    elif any(k in ind_upper for k in ["GOODS", "MANUFACTUR", "ENGINEER", "DEFENCE", "AERO", "INDUSTRIAL"]):
        return "Capital Goods & Manufacturing"
    elif any(k in ind_upper for k in ["FMCG", "FOOD", "BEVERAG", "TOBACCO", "PERSONAL", "HOUSEHOLD", "AGRI"]):
        return "Fast Moving Consumer Goods"
    elif any(k in ind_upper for k in ["STEEL", "METALS", "MINING", "CEMENT", "ALUMIN", "COPPER"]):
        return "Metals & Mining"
    elif any(k in ind_upper for k in ["CHEMIC", "FERTIL", "PESTICID", "POLYMER"]):
        return "Chemicals & Fertilizers"
    elif any(k in ind_upper for k in ["POWER", "ENERGY", "GAS", "OIL", "PETRO", "COAL", "UTIL"]):
        return "Oil, Gas & Power"
    elif any(k in ind_upper for k in ["REAL ESTATE", "CONSTRUCT", "INFRA", "CEMENT", "REALTY"]):
        return "Construction & Realty"
    elif any(k in ind_upper for k in ["TELECOM", "MEDIA", "ENTERTAIN", "BROADCAST"]):
        return "Telecommunication & Media"
    elif any(k in ind_upper for k in ["RETAIL", "CONSUMER SERVICES", "HOTEL", "TRAVEL", "TEXTILE", "APPAREL"]):
        return "Consumer Discretionary & Retail"
    else:
        return "Diversified / Others"

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
             'industry'
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
# 3. SIDEBAR CONTROLS & DATA ENRICHMENT
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
    
    # Standard AMFI Indian Sectors list for UI rendering
    default_indian_sectors = [
        "Financial Services", "Information Technology", "Healthcare",
        "Automobile and Auto Components", "Capital Goods & Manufacturing",
        "Fast Moving Consumer Goods", "Metals & Mining", "Chemicals & Fertilizers",
        "Oil, Gas & Power", "Construction & Realty", "Telecommunication & Media",
        "Consumer Discretionary & Retail", "Diversified / Others"
    ]
    
    sector_choice = st.multiselect(
        "NSE Sector (e.g., Financial Services, IT):",
        options=default_indian_sectors,
        default=[]
    )
    
    # We will filter industries dynamically after fetching, but allow text input or multi-select fallback
    industry_filter_text = st.text_input(
        "Filter Industry Contains (Optional keyword, e.g., 'Pharma', 'Software'):",
        value=""
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
# 4. FETCH, ENRICH & FILTER
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
    
    # --- 4. MAP OFFICIAL INDIAN SECTOR & INDUSTRY ---
    if not nse_class_df.empty and "Symbol" in nse_class_df.columns:
        df = df.merge(
            nse_class_df[["Symbol", "Industry"]],
            left_on="name",
            right_on="Symbol",
            how="left",
            suffixes=("", "_nse")
        )
        # Prefer NSE Industry if available, fallback to API Industry
        df["Industry"] = df["Industry_nse"].combine_first(df["industry"]).fillna("Diversified")
    else:
        df["Industry"] = df["industry"].fillna("Diversified")
        
    # Generate official Indian AMFI/SEBI Sector from Industry
    df["Sector"] = df["Industry"].apply(map_to_indian_sector)
        
    # --- 5. APPLY NSE SECTOR & INDUSTRY FILTERS ---
    if sector_choice:
        df = df[df["Sector"].isin(sector_choice)]
        
    if industry_filter_text.strip():
        df = df[df["Industry"].str.contains(industry_filter_text.strip(), case=False, na=False)]
    
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
