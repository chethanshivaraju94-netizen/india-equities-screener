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

# --- SIDEBAR FILTERS ---
st.sidebar.header("1. Exchange & Universe")
exchange_choice = st.sidebar.multiselect(
    "Select Exchanges:",
    options=["NSE", "BSE"],
    default=["NSE"]
)

st.sidebar.header("2. Fundamental Filters")
# Market Cap in INR Crores (1 Crore = 10,000,000 INR)
min_mcap_cr = st.sidebar.number_input("Min Market Cap (₹ Crores):", min_value=0, value=500, step=100)
min_pe = st.sidebar.slider("Min P/E Ratio:", min_value=0.0, max_value=100.0, value=5.0, step=1.0)
max_pe = st.sidebar.slider("Max P/E Ratio:", min_value=5.0, max_value=200.0, value=60.0, step=5.0)

st.sidebar.header("3. Technical Filters (Daily)")
min_rsi = st.sidebar.slider("Min Daily RSI (14):", min_value=10, max_value=90, value=50, step=5)
max_rsi = st.sidebar.slider("Max Daily RSI (14):", min_value=20, max_value=100, value=80, step=5)
above_sma50 = st.sidebar.checkbox("Price Above 50-Day SMA", value=True)

st.sidebar.header("4. Display Settings")
max_results = st.sidebar.slider("Max Results to Fetch:", min_value=50, max_value=1000, value=250, step=50)

# --- BACKEND SCREENER LOGIC ---
@st.cache_data(ttl=300)
def fetch_screener_data(exchanges, min_mcap, min_pe_val, max_pe_val, min_rsi_val, max_rsi_val, sma_filter, limit_rows):
    if not exchanges:
        return pd.DataFrame()
    
    # 1 Crore INR = 10^7 INR
    min_mcap_inr = min_mcap * 10_000_000
    
    q = (Query()
         .select(
             'name', 
             'close', 
             'change', 
             'volume', 
             'market_cap_basic', 
             'P/E', 
             'RSI', 
             'SMA50',
             'exchange'
         )
         .where(
             col('exchange').isin(exchanges),
             col('market_cap_basic') >= min_mcap_inr,
             col('P/E').between(min_pe_val, max_pe_val),
             col('RSI').between(min_rsi_val, max_rsi_val)
         )
         .order_by('volume', ascending=False)
         .limit(limit_rows)
    )
    
    if sma_filter:
        q = q.where(col('close') > col('SMA50'))
        
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
        min_pe,
        max_pe,
        min_rsi,
        max_rsi,
        above_sma50,
        max_results
    )

if results_df.empty:
    st.warning("No stocks matched your criteria. Try widening your filters in the sidebar.")
else:
    display_df = results_df.copy()
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
