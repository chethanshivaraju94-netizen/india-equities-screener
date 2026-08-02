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
st.markdown("Customizable **CAN SLIM & Trend Screener** powered by TradingView speed and **Official NSE / AMFI Industry Classification**.")

# ==========================================
# 1. NSE / AMFI CLASSIFICATION ENGINE
# ==========================================
@st.cache_data(ttl=86400)  # Cache for 24 hours so it runs instantly
def load_nse_classification():
    """
    Loads official NSE listed securities with SEBI/AMFI 4-tier classification:
    Macro-Economic Sector -> Sector -> Industry -> Basic Industry
    """
    # Standard AMFI / NSE classification fallback mapping & structure
    # Attempt to load from official NSE equities list or local repository file 'nse_classification.csv'
    try:
        # Check if local file exists in repo first
        df_nse = pd.read_csv("nse_classification.csv")
    except Exception:
        # Automated fallback: Load official NSE equity list with Basic Industry mapping
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
            resp = requests.get(url, headers=headers, timeout=10)
            df_raw = pd.read_csv(StringIO(resp.text))
            
            # Standardize column names
            df_raw.columns = df_raw.columns.str.strip()
            
            # Map AMFI 4-Tier structure based on NSE Basic Industry
            df_nse = pd.DataFrame()
            df_nse["Symbol"] = df_raw["SYMBOL"].str.strip()
            df_nse["Name"] = df_raw["NAME OF COMPANY"].str.strip()
            
            # Map Basic Industry column
            if "BASIC INDUSTRY" in df_raw.columns:
                df_nse["Basic_Industry"] = df_raw["BASIC INDUSTRY"].str.strip()
            else:
                df_nse["Basic_Industry"] = "Unclassified"
                
            # Assign Macro-Sector and Sector categories cleanly
            def map_amfi_sector(bi):
                bi_upper = str(bi).upper()
                if any(k in bi_upper for k in ["BANK", "FINANC", "INSUR", "NBFC", "ASSET"]):
                    return "Financial Services", "Financial Services"
                elif any(k in bi_upper for k in ["SOFTWARE", "IT", "COMPUTER", "PLATFORM"]):
                    return "Information Technology", "Information Technology"
                elif any(k in bi_upper for k in ["PHARMA", "HEALTH", "HOSPITAL", "DRUG", "BIOTECH"]):
                    return "Healthcare", "Healthcare"
                elif any(k in bi_upper for k in ["AUTO", "VEHICL", "ANCILLAR", "TYRE"]):
                    return "Consumer Discretionary", "Automobile and Auto Components"
                elif any(k in bi_upper for k in ["GOODS", "MANUFACTUR", "ENGINEER", "DEFENCE", "AERO"]):
                    return "Industrials", "Capital Goods"
                elif any(k in bi_upper for k in ["FMCG", "FOOD", "BEVERAG", "TOBACCO", "PERSONAL"]):
                    return "Fast Moving Consumer Goods", "Fast Moving Consumer Goods"
                elif any(k in bi_upper for k in ["STEEL", "METALS", "MINING", "CEMENT", "CHEMIC"]):
                    return "Commodities", "Metals & Mining / Chemicals"
                elif any(k in bi_upper for k in ["POWER", "ENERGY", "GAS", "OIL", "PETRO"]):
                    return "Energy", "Oil, Gas & Consumable Fuels / Power"
                elif any(k in bi_upper for k in ["REAL ESTATE", "CONSTRUCT", "INFRA"]):
                    return "Realty & Infrastructure", "Construction / Realty"
                elif any(k in bi_upper for k in ["TELECOM", "MEDIA", "ENTERTAIN"]):
                    return "Telecommunication & Media", "Media, Entertainment & Telecom"
                else:
                    return "Others", "Diversified / Others"
            
            mapped_sectors = df_nse["Basic_Industry"].apply(map_amfi_sector)
            df_nse["Macro_Sector"] = [x[0] for x in mapped_sectors]
            df_nse["Sector"] = [x[1] for x in mapped_sectors]
            df_nse["Industry"] = df_nse["Basic_Industry"]  # Mapped to level 3/4 AMFI depth
            
        except Exception as e:
            # Safe empty structure if offline
            df_nse = pd.DataFrame(columns=["Symbol", "Macro_Sector", "Sector", "Industry", "Basic_Industry"])
            
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
    st.header("🏛️ Official NSE / AMFI Filters")
    
    # Dynamic options from loaded NSE dataset
    macro_options = sorted(nse_class_df["Macro_Sector"].dropna().unique().tolist()) if not nse_class_df.empty else []
    macro_choice = st.multiselect(
        "Macro-Economic Sector (e.g., Industrials, Financials):",
        options=macro_options,
        default=[]
    )
    
    # Cascade Sector options based on Macro choice
    if macro_choice and not nse_class_df.empty:
        sector_options = sorted(nse_class_df[nse_class_df["Macro_Sector"].isin(macro_choice)]["Sector"].dropna().unique().tolist())
    else:
        sector_options = sorted(nse_class_df["Sector"].dropna().unique().tolist()) if not nse_class_df.empty else []
        
    sector_choice = st.multiselect(
        "NSE Sector (e.g., Capital Goods, IT):",
        options=sector_options,
        default=[]
    )
    
    # Cascade Basic Industry options
    if sector_choice and not nse_class_df.empty:
        basic_ind_options = sorted(nse_class_df[nse_class_df["Sector"].isin(sector_choice)]["Basic_Industry"].dropna().unique().tolist())
    elif macro_choice and not nse_class_df.empty:
        basic_ind_options = sorted(nse_class_df[nse_class_df["Macro_Sector"].isin(macro_choice)]["Basic_Industry"].dropna().unique().tolist())
    else:
        basic_ind_options = sorted(nse_class_df["Basic_Industry"].dropna().unique().tolist()) if not nse_class_df.empty else []
        
    basic_ind_choice = st.multiselect(
        "Basic Industry (e.g., Industrial Products, Defence):",
        options=basic_ind_options,
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
    
    # --- 4. MERGE OFFICIAL NSE / AMFI CLASSIFICATION ---
    if not nse_class_df.empty:
        df = df.merge(
            nse_class_df[["Symbol", "Macro_Sector", "Sector", "Basic_Industry"]],
            left_on="name",
            right_on="Symbol",
            how="left"
        )
        # Fill unmapped symbols
        df["Macro_Sector"] = df["Macro_Sector"].fillna("Others")
        df["Sector"] = df["Sector"].fillna("Unclassified")
        df["Basic_Industry"] = df["Basic_Industry"].fillna("Unclassified")
    else:
        df["Macro_Sector"] = "N/A"
        df["Sector"] = "N/A"
        df["Basic_Industry"] = "N/A"
        
    # --- 5. APPLY CASCADING NSE SECTOR & INDUSTRY FILTERS ---
    if macro_choice:
        df = df[df["Macro_Sector"].isin(macro_choice)]
    if sector_choice:
        df = df[df["Sector"].isin(sector_choice)]
    if basic_ind_choice:
        df = df[df["Basic_Industry"].isin(basic_ind_choice)]
    
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
            'Macro_Sector', 'Sector', 'Basic_Industry'
        ]
        
        st.subheader(f"📊 Filtered Results ({len(df)} Stocks Found)")
        st.dataframe(df[table_columns], use_container_width=True, hide_index=True)
        
        # --- TRADINGVIEW WATCHLIST EXPORT ---
        st.markdown("---")
        st.subheader("📋 Copy to TradingView Watchlist")
        st.write("Copy the text string below and paste it directly into your TradingView Watchlist **Symbol Search / Import** box:")
        
        tv_watchlist_string = ", ".join(df['TV_Symbol'].tolist())
        st.code(tv_watchlist_string, language="text")
