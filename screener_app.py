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
st.markdown("Filter Indian equities using **TradingView's backend API** and copy your watchlist directly.")

# --- SIDEBAR FORM (ONLY RUNS WHEN 'APPLY FILTERS' IS CLICKED) ---
with st.sidebar.form("filter_form"):
    st.header("1. Exchange & Universe")
    exchange_choice = st.multiselect(
        "Select Exchanges:",
        options=["NSE", "BSE"],
        default=["NSE"]
    )

    st.header("2. Fundamental Filters")
    # Market Cap in INR Crores (1 Crore = 10,000,000 INR)
    min_mcap_cr = st.number_input("Min Market Cap (₹ Crores):", min_value=0, value=500, step=100)
    min_pe = st.slider("Min P/E Ratio:", min_value=0.0, max_value=100.0, value=5.0, step=1.0)
    max_pe = st.slider("Max P/E Ratio:", min_value=5.0, max_value=200.0, value=60.0, step=5.0)

    st.header("3. Technical Filters (Daily)")
    min_rsi = st.slider("Min Daily RSI (14):", min_value=10, max_value=90, value=50, step=5)
    max_rsi = st.slider("Max Daily RSI (14):", min_value=20, max_value=100, value=80, step=5)
    above_sma50 = st.checkbox("Price Above 50-Day SMA", value=True)

    st.header("4. Display Settings")
    max_results = st.slider("Max Results to Fetch:", min_value=50, max_value=1000, value=250, step=50)
    
    # Dedicated Apply Button
    apply_filters = st.form_submit_button("🚀 Apply Filters", use_container_width=True, type="primary")

# --- BACKEND SCREENER LOGIC ---
def fetch_screener_data(exchanges, min_mcap, min_pe_val, max_pe_val, min_rsi_val, max_rsi_val, sma_filter, limit_rows):
    if not exchanges:
        return pd.DataFrame()
    
    # 1 Crore INR = 10^7 INR
    min_mcap_inr = min_mcap * 10_000_000
    
    # Use exact TradingView API internal field names!
    # P/E ratio is 'price_earnings_ttm' in the API database, NOT 'P/E'
    q = (Query()
         .set_markets('india')
         .select(
             'name', 
             'close', 
             'change', 
             'volume', 
             'market_cap_basic', 
             'price_earnings_ttm', 
             'RSI', 
             'SMA50',
             'exchange'
         )
         .where(
             col('market_cap_basic') >= min_mcap_inr,
             col('price_earnings_ttm').between(min_pe_val, max_pe_val),
             col('RSI').between(min_rsi_val, max_rsi_val)
         )
         .order_by('volume', ascending=False)
         .limit(limit_rows)
    )
        
    try:
        _, df = q.get_scanner_data()
        if df.empty:
            return df
            
        # Filter exchanges accurately
        df = df[df['exchange'].isin(exchanges)]
        
        # Apply SMA50 Trend Filter cleanly without breaking REST API syntax
        if sma_filter and 'SMA50' in df.columns and 'close' in df.columns:
            df = df[df['close'] > df['SMA50']]
            
        return df
    except Exception as e:
        st.error(f"Error fetching data from TradingView API: {e}")
        return pd.DataFrame()

# --- FETCH AND RENDER DATA ---
with st.spinner("Scanning Indian Equities via TradingView API..."):
    results_df = fetch_screener_data(
        exchange_choice,
        min_mcap_cr,
        min_pe,
        max_pe,
        min_rsi,
        max_rsi,
        above_sma50,
        max_results
    )

if results_df.empty:
    st.warning("No stocks matched your criteria. Click 'Apply Filters' after widening your ranges in the sidebar.")
else:
    display_df = results_df.copy()
    
    # Rename API field to readable UI label
    if 'price_earnings_ttm' in display_df.columns:
        display_df.rename(columns={'price_earnings_ttm': 'P/E'}, inplace=True)
    
    # --- SAFE TYPE CONVERSION TO PREVENT ROUNDING ERRORS ---
    numeric_cols = ['market_cap_basic', 'close', 'change', 'RSI', 'P/E', 'volume']
    for col_name in numeric_cols:
        if col_name in display_df.columns:
            display_df[col_name] = pd.to_numeric(display_df[col_name], errors='coerce')
    
    # Perform calculations and rounding safely
    display_df['Market Cap (₹ Cr)'] = (display_df['market_cap_basic'] / 10_000_000).round(2)
    display_df['Close'] = display_df['close'].round(2)
    display_df['Change %'] = display_df['change'].round(2)
    display_df['RSI (14)'] = display_df['RSI'].round(1)
    display_df['P/E'] = display_df['P/E'].round(2)
    
    # Build the TradingView Symbol column (e.g., NSE:RELIANCE)
    display_df['TV_Symbol'] = display_df['exchange'] + ":" + display_df['name']
    
    table_columns = [
        'TV_Symbol', 'name', 'Close', 'Change %', 
        'RSI (14)', 'P/E', 'Market Cap (₹ Cr)', 'volume'
    ]
    
    st.subheader(f"📊 Filtered Results ({len(display_df)} Stocks Found)")
    st.dataframe(display_df[table_columns], use_container_width=True, hide_index=True)
    
    # --- TRADINGVIEW WATCHLIST EXPORT ---
    st.markdown("---")
    st.subheader("📋 Copy to TradingView Watchlist")
    st.write("Copy the text string below and paste it directly into your TradingView Watchlist **Symbol Search / Import** box:")
    
    tv_watchlist_string = ", ".join(display_df['TV_Symbol'].tolist())
    st.code(tv_watchlist_string, language="text")
