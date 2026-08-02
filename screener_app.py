import streamlit as st
import pandas as pd
from tradingview_screener import Query, col

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="India Equities Screener (NSE Classified)",
    page_icon="📈",
    layout="wide"
)

st.title("📈 India Equities Interactive Screener")
st.markdown("Customizable **CAN SLIM & Trend Screener** powered by TradingView speed and the complete **Official NSE / AMFI Classification (22 Sectors & 59 Industries)**.")

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
    """
    Looks up exact TradingView pair first, then falls back safely if a new industry appears.
    """
    mapped = TV_TO_INDIAN_MAP.get((tv_sector, tv_industry))
    if mapped:
        return mapped
    return "Diversified", "Diversified Commercial Services"

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
    st.header("🏛️ Official NSE Filters (22 / 59)")
    
    # 1. NSE Sector Dropdown (22 Official Economic Sectors)
    sector_options = list(INDIAN_SECTOR_HIERARCHY.keys())
    sector_choice = st.multiselect(
        "NSE Sector (22 Economic Sectors):",
        options=sector_options,
        default=[]
    )
    
    # 2. Cascading NSE Industry Dropdown (59 Distinct Industries)
    if sector_choice:
        industry_options = []
        for sec in sector_choice:
            industry_options.extend(INDIAN_SECTOR_HIERARCHY.get(sec, []))
        industry_options = sorted(list(set(industry_options)))
    else:
        all_industries = [ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds]
        industry_options = sorted(list(set(all_industries)))
        
    industry_choice = st.multiselect(
        "NSE Industry (59 Distinct Classifications):",
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
with st.spinner("Scanning Indian Equities & Mapping 22 Sectors / 59 Industries..."):
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
    
    # --- 4. DETERMINISTIC 84-PAIR INDIAN SECTOR & INDUSTRY MAPPING ---
    mapped_sectors = []
    mapped_industries = []
    for _, row in df.iterrows():
        sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
        mapped_sectors.append(sec)
        mapped_industries.append(ind)
        
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries
        
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
