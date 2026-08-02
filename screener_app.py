import streamlit as st
import pandas as pd
from tradingview_screener import Query, col

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="India Equities Screener",
    page_icon="📈",
    layout="wide"
)

st.title("📈 India Equities Interactive Screener")
st.markdown("Customizable **CAN SLIM & Trend Screener** matching your exact TradingView filter layout.")

# --- SIDEBAR FORM (ONLY RUNS WHEN 'APPLY FILTERS' IS CLICKED) ---
with st.sidebar.form("filter_form"):
    st.header("1. Exchange & Universe")
    exchange_choice = st.multiselect(
        "Select Exchanges:",
        options=["NSE", "BSE"],
        default=["NSE", "BSE"]
    )
    
    sector_choice = st.multiselect(
        "Filter by Sector (Optional - Leave empty for All):",
        options=[
            "Finance", "Technology", "Health Technology", "Electronic Technology",
            "Consumer Non-Durables", "Consumer Durables", "Process Industries",
            "Producer Manufacturing", "Energy Minerals", "Non-Energy Minerals",
            "Commercial Services", "Retail Trade", "Transportation", "Utilities"
        ],
        default=[]
    )

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

# --- BACKEND SCREENER LOGIC ---
def fetch_screener_data(exchanges, min_mcap, min_adr_val, limit_rows):
    if not exchanges:
        return pd.DataFrame()
    
    # Convert ₹ Crores to raw INR (1 Crore = 10,000,000 INR)
    min_mcap_inr = min_mcap * 10_000_000
    
    # Fetch data + include 'type' to filter out REITs/InvITs/ETFs
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
             'sector',
             'industry',
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

# --- FETCH AND RENDER DATA ---
with st.spinner("Scanning Indian Equities via TradingView API..."):
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
    # Since df is sorted by volume descending, keep='first' keeps the high-volume NSE symbol!
    df = df.drop_duplicates(subset=['name'], keep='first')
    
    # 4. Filter Sector (if user selected specific sectors)
    if sector_choice:
        df = df[df['sector'].isin(sector_choice)]
    
    # --- SAFE NUMERIC CONVERSION ---
    numeric_cols = [
        'market_cap_basic', 'close', 'change', 'volume', 
        'EMA21', 'SMA50', 'SMA200', 'average_volume_60d_calc', 
        'ADR', 'price_52_week_high', 'price_52_week_low'
    ]
    for col_name in numeric_cols:
        if col_name in df.columns:
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
            
    # --- APPLY SCREENSHOT FILTERS ROBUSTLY IN PANDAS ---
    
    # A. Trend & Moving Average Filters
    if above_ema21 and 'EMA21' in df.columns:
        df = df[df['close'] > df['EMA21']]
    if above_sma50 and 'SMA50' in df.columns:
        df = df[df['close'] > df['SMA50']]
    if above_sma200 and 'SMA200' in df.columns:
        df = df[df['close'] > df['SMA200']]
        
    # B. 60-Day Average Rupee Volume Filter (Price x avg vol 60D >= 50M INR / ₹5 Cr)
    if 'average_volume_60d_calc' in df.columns:
        df['val_traded_60d_inr'] = df['close'] * df['average_volume_60d_calc']
        df = df[df['val_traded_60d_inr'] >= (min_vol60d_cr * 10_000_000)]
        
    # C. Price Above 52-Week Low by X% or more (>= 20%)
    if 'price_52_week_low' in df.columns:
        pct_above_low = ((df['close'] - df['price_52_week_low']) / df['price_52_week_low']) * 100
        df = df[pct_above_low >= min_above_52l]
        
    # D. Price Below 52-Week High by 0% to Y% (<= 30%)
    if 'price_52_week_high' in df.columns:
        pct_below_high = ((df['price_52_week_high'] - df['close']) / df['price_52_week_high']) * 100
        df = df[pct_below_high <= max_below_52h]

    # --- DISPLAY FORMATTING ---
    if df.empty:
        st.warning("No stocks passed all technical and fundamental criteria.")
    else:
        # Format calculated display columns
        df['Market Cap (₹ Cr)'] = (df['market_cap_basic'] / 10_000_000).round(2)
        df['60D Vol (₹ Cr)'] = (df['val_traded_60d_inr'] / 10_000_000).round(2)
        df['Close'] = df['close'].round(2)
        df['Change %'] = df['change'].round(2)
        df['ADR %'] = df['ADR'].round(2)
        df['TV_Symbol'] = df['exchange'] + ":" + df['name']
        
        table_columns = [
            'TV_Symbol', 'name', 'Close', 'Change %', 
            'ADR %', '60D Vol (₹ Cr)', 'Market Cap (₹ Cr)', 
            'sector', 'industry'
        ]
        
        st.subheader(f"📊 Filtered Results ({len(df)} Stocks Found)")
        st.dataframe(df[table_columns], use_container_width=True, hide_index=True)
        
        # --- TRADINGVIEW WATCHLIST EXPORT ---
        st.markdown("---")
        st.subheader("📋 Copy to TradingView Watchlist")
        st.write("Copy the text string below and paste it directly into your TradingView Watchlist **Symbol Search / Import** box:")
        
        tv_watchlist_string = ", ".join(df['TV_Symbol'].tolist())
        st.code(tv_watchlist_string, language="text")
