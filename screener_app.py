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
# 1. NSE / AMFI CLASSIFICATION ENGINE
# ==========================================
@st.cache_data(ttl=86400)  # Cache for 24 hours so it runs instantly
def load_nse_classification():
    """
    Loads official NSE listed securities with AMFI/SEBI classification:
    Sector -> Industry
    """
    try:
        # Check if local custom file exists in repo first ('nse_classification.csv' with Symbol, Sector, Industry)
        df_nse = pd.read_csv("nse_classification.csv")
    except Exception:
        # Automated fallback: Load official NSE equity list
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
            resp = requests.get(url, headers=headers, timeout=10)
            df_raw = pd.read_csv(StringIO(resp.text))
            
            # Standardize column names
            df_raw.columns = df_raw.columns.str.strip()
            
            df_nse = pd.DataFrame()
            df_nse["Symbol"] = df_raw["SYMBOL"].str.strip()
            
            # Use raw NSE industry column as 'Industry'
            if "BASIC INDUSTRY" in df_raw.columns:
                df_nse["Industry"] = df_raw["BASIC INDUSTRY"].str.strip()
            elif "INDUSTRY" in df_raw.columns:
                df_nse["Industry"] = df_raw["INDUSTRY"].str.strip()
            else:
                df_nse["Industry"] = "Unclassified"
                
            # Assign official NSE Sector categories cleanly from Industry
            def map_nse_sector(ind):
                ind_upper = str(ind).upper()
                if any(k in ind_upper for k in ["BANK", "FINANC", "INSUR", "NBFC", "ASSET"]):
                    return "Financial Services"
                elif any(k in ind_upper for k in ["SOFTWARE", "IT", "COMPUTER", "PLATFORM"]):
                    return "Information Technology"
                elif any(k in ind_upper for k in ["PHARMA", "HEALTH", "HOSPITAL", "DRUG", "BIOTECH"]):
                    return "Healthcare"
                elif any(k in ind_upper for k in ["AUTO", "VEHICL", "ANCILLAR", "TYRE"]):
                    return "Automotive & Auto Components"
                elif any(k in ind_upper for k in ["GOODS", "MANUFACTUR", "ENGINEER", "DEFENCE", "AERO"]):
                    return "Capital Goods & Manufacturing"
                elif any(k in ind_upper for k in ["FMCG", "FOOD", "BEVERAG", "TOBACCO", "PERSONAL"]):
                    return "Fast Moving Consumer Goods"
                elif any(k in ind_upper for k in ["STEEL", "METALS", "MINING", "CEMENT", "CHEMIC"]):
                    return "Metals, Mining & Chemicals"
                elif any(k in ind_upper for k in ["POWER", "ENERGY", "GAS", "OIL", "PETRO"]):
                    return "Oil, Gas & Energy"
                elif any(k in ind_upper for k in ["REAL ESTATE", "CONSTRUCT", "INFRA"]):
                    return "Construction & Realty"
                elif any(k in ind_upper for k in ["TELECOM", "MEDIA", "ENTERTAIN"]):
                    return "Media, Entertainment & Telecom"
                elif any(k in ind_upper for k in ["RETAIL", "CONSUMER SERVICES", "HOTEL", "TRAVEL"]):
                    return "Consumer Services & Retail"
                else:
                    return "Diversified / Others"
            
            df_nse["Sector"] = df_nse["Industry"].apply(map_nse_sector)
            
        except Exception:
            # Safe empty structure if offline
            df_nse = pd.DataFrame(columns=["Symbol", "Sector", "Industry"])
            
    return df_nse

nse_class_df = load_nse_classification()

# ==========================================
# 2. SIDEBAR FILTER CONTROLS
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
    
    # 1. NSE Sector Options
    sector_options = sorted(nse_class_df["Sector"].dropna().unique().tolist()) if not nse_class_df.empty else []
    sector_choice = st.multiselect(
        "NSE Sector (e.g., Capital Goods, IT):",
        options=sector_options,
        default=[]
    )
    
    # 2. Cascading Industry Options (Narrows automatically when Sector is selected)
    if sector_choice and not nse_class_df.empty:
        industry_options = sorted(nse_class_df[nse_class_df["Sector"].isin(sector_choice)]["Industry"].dropna().unique().tolist())
    else:
        industry_options = sorted(nse_class_df["Industry"].dropna().unique().tolist()) if not nse_class_df.empty else []
        
    industry_choice = st.multiselect(
        "NSE Industry (e.g., Pharmaceuticals, Industrial Products):",
        options=industry_options,
        default=[]
    )

    st.markdown("---")
    st.header("2. Fundamental & Liquidity")
    # 10 B INR = 1000 Crores INR
    min_mcap_cr = st.number_input(
        "Min Market Cap (₹ Crores) [1000 Cr = 10B INR]:", 
        min_value=0, value=1000, step=100
    )
    # 50 M INR = 5 Crores INR
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
    
    # Dedicated Apply Button
    apply_filters = st.form_submit_button("🚀 Apply Filters", use_container_width=True, type="primary")

# ==========================================
# 3. BACKEND SCREENER LOGIC
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
             'type'
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
# 4. FETCH, MERGE & FILTER DATA
# ==========================================
with st.spinner("Scanning Indian Equities & Mapping Official NSE Classifications..."):
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
    
    # 2. Filter for COMMON STOCKS ONLY (removes REITs, InvITs, ETFs)
    if 'type' in df.columns:
        df = df[df['type'] == 'stock']
    
    # 3. SMART DEDUPLICATION (Removes duplicate BSE rows for stocks already listed on NSE)
    df = df.drop_duplicates(subset=['name'], keep='first')
    
    # --- 4. MERGE OFFICIAL NSE SECTOR & INDUSTRY ---
    if not nse_class_df.empty:
        df = df.merge(
            nse_class_df[["Symbol", "Sector", "Industry"]],
            left_on="name",
            right_on="Symbol",
            how="left"
        )
        # Fill unmapped symbols
        df["Sector"] = df["Sector"].fillna("Unclassified")
        df["Industry"] = df["Industry"].fillna("Unclassified")
    else:
        df["Sector"] = "N/A"
        df["Industry"] = "N/A"
        
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
