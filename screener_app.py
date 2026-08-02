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
st.markdown("Customizable **CAN SLIM & Trend Screener** powered by TradingView speed and the complete **Official NSE / AMFI Classification (22 Sectors & 59 Industries)**.")

# ==========================================
# 1. COMPLETE 22 SECTORS & 59 INDUSTRIES
# ==========================================
INDIAN_SECTOR_HIERARCHY = {
    "Automobile and Auto Components": [
        "Automobiles", "Auto Components & Ancillaries", "Tyres & Rubber"
    ],
    "Capital Goods": [
        "Aerospace & Defense", "Electrical Equipment", "Engineering Services", 
        "Industrial Manufacturing & Products"
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
        "Consumer Electronics & Appliances", "Gems, Jewellery & Watches"
    ],
    "Consumer Services": [
        "Leisure Services", "Restaurants & QSR", "Retailing", "Travel & Tourism"
    ],
    "Diversified": [
        "Diversified Commercial Services", "Diversified Industrials"
    ],
    "Fast Moving Consumer Goods": [
        "Agricultural Food & Beverages", "Food Products", "Personal Care", "Tobacco Products"
    ],
    "Financial Services": [
        "Asset Management", "Banks", "Capital Markets", "Finance & NBFCs", 
        "Financial Technology (Fintech)", "Insurance"
    ],
    "Forest Materials": [
        "Paper, Forest & Jute Products"
    ],
    "Healthcare": [
        "Healthcare Services", "Medical Equipment & Supplies", "Pharmaceuticals & Biotechnology"
    ],
    "Information Technology": [
        "IT - Hardware", "IT - Software & Consulting"
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

def map_to_indian_classification(tv_industry, tv_sector):
    """
    Deterministic mapper: Assigns every stock to one of the 
    official 22 AMFI/NSE Sectors and 59 Industries.
    """
    ind_upper = str(tv_industry).upper() + " " + str(tv_sector).upper()
    
    # 1. Financial Services
    if any(k in ind_upper for k in ["BANK"]):
        return "Financial Services", "Banks"
    elif any(k in ind_upper for k in ["FINANC", "NBFC", "LOAN", "LEASING"]):
        return "Financial Services", "Finance & NBFCs"
    elif any(k in ind_upper for k in ["INSUR", "LIFE"]):
        return "Financial Services", "Insurance"
    elif any(k in ind_upper for k in ["ASSET", "BROKING", "INVEST", "CAPITAL"]):
        return "Financial Services", "Capital Markets"
    elif any(k in ind_upper for k in ["FINTECH", "PAYMENT"]):
        return "Financial Services", "Financial Technology (Fintech)"
    
    # 2. Information Technology
    elif any(k in ind_upper for k in ["SOFTWARE", "IT", "COMPUTER", "CYBER", "PLATFORM"]):
        return "Information Technology", "IT - Software & Consulting"
    elif any(k in ind_upper for k in ["HARDWARE", "SERVER", "SEMICONDUCTOR"]):
        return "Information Technology", "IT - Hardware"
    
    # 3. Healthcare
    elif any(k in ind_upper for k in ["PHARMA", "DRUG", "BIOTECH"]):
        return "Healthcare", "Pharmaceuticals & Biotechnology"
    elif any(k in ind_upper for k in ["HOSPITAL", "HEALTH", "NURSING", "CLINIC"]):
        return "Healthcare", "Healthcare Services"
    elif any(k in ind_upper for k in ["MEDICAL", "SURGICAL", "DIAGNOSTIC"]):
        return "Healthcare", "Medical Equipment & Supplies"
    
    # 4. Automobile and Auto Components
    elif any(k in ind_upper for k in ["AUTO PARTS", "ANCILLAR"]):
        return "Automobile and Auto Components", "Auto Components & Ancillaries"
    elif any(k in ind_upper for k in ["TYRE", "RUBBER"]):
        return "Automobile and Auto Components", "Tyres & Rubber"
    elif any(k in ind_upper for k in ["MOTOR", "VEHICL", "AUTOMOBIL", "TRACTOR"]):
        return "Automobile and Auto Components", "Automobiles"
    
    # 5. Capital Goods
    elif any(k in ind_upper for k in ["DEFENCE", "AERO"]):
        return "Capital Goods", "Aerospace & Defense"
    elif any(k in ind_upper for k in ["ELECTRICAL", "CABLE", "TRANSFORMER"]):
        return "Capital Goods", "Electrical Equipment"
    elif any(k in ind_upper for k in ["ENGINEER", "MACHIN", "MANUFACTUR", "INDUSTRIAL"]):
        return "Capital Goods", "Industrial Manufacturing & Products"
    
    # 6. Chemicals
    elif any(k in ind_upper for k in ["FERTIL", "PESTICID", "AGROCHEM"]):
        return "Chemicals", "Fertilizers & Agrochemicals"
    elif any(k in ind_upper for k in ["CHEMIC", "POLYMER"]):
        return "Chemicals", "Chemicals & Petrochemicals"
    
    # 7. Fast Moving Consumer Goods
    elif any(k in ind_upper for k in ["TOBACCO", "CIGARETTE"]):
        return "Fast Moving Consumer Goods", "Tobacco Products"
    elif any(k in ind_upper for k in ["PERSONAL", "HOUSEHOLD", "CARE", "COSMETIC"]):
        return "Fast Moving Consumer Goods", "Personal Care"
    elif any(k in ind_upper for k in ["BEVERAG", "BREW", "DISTILL"]):
        return "Fast Moving Consumer Goods", "Agricultural Food & Beverages"
    elif any(k in ind_upper for k in ["FMCG", "FOOD", "DAIRY", "AGRI"]):
        return "Fast Moving Consumer Goods", "Food Products"
    
    # 8. Metals & Mining
    elif any(k in ind_upper for k in ["STEEL", "IRON"]):
        return "Metals & Mining", "Ferrous Metals (Steel & Iron)"
    elif any(k in ind_upper for k in ["ALUMIN", "COPPER", "ZINC", "NON-FERROUS"]):
        return "Metals & Mining", "Non-Ferrous Metals"
    elif any(k in ind_upper for k in ["MINING", "MINERAL", "ORE"]):
        return "Metals & Mining", "Minerals & Mining"
    
    # 9. Oil, Gas & Consumable Fuels
    elif any(k in ind_upper for k in ["COAL", "FUEL", "LUBRICANT"]):
        return "Oil, Gas & Consumable Fuels", "Consumable Fuels & Coal"
    elif any(k in ind_upper for k in ["REFIN"]):
        return "Oil, Gas & Consumable Fuels", "Petroleum Products & Refining"
    elif any(k in ind_upper for k in ["OIL", "GAS", "PETRO"]):
        return "Oil, Gas & Consumable Fuels", "Oil & Gas Exploration & Production"
    
    # 10. Power
    elif any(k in ind_upper for k in ["TRANSMISSION", "GRID"]):
        return "Power", "Power Transmission & Distribution"
    elif any(k in ind_upper for k in ["POWER", "ENERGY", "SOLAR", "RENEW"]):
        return "Power", "Power Generation"
    
    # 11. Construction Materials
    elif any(k in ind_upper for k in ["CEMENT", "CONCRETE"]):
        return "Construction Materials", "Cement & Cement Products"
    elif any(k in ind_upper for k in ["CERAMIC", "TILE", "GRANITE"]):
        return "Construction Materials", "Ceramics & Building Materials"
    
    # 12. Construction
    elif any(k in ind_upper for k in ["INFRASTRUCTURE", "HIGHWAY", "BRIDGE"]):
        return "Construction", "Infrastructure Developers"
    elif any(k in ind_upper for k in ["CONSTRUCT", "CIVIL", "EPC"]):
        return "Construction", "Civil Construction"
    
    # 13. Realty
    elif any(k in ind_upper for k in ["REAL ESTATE", "REALTY", "DEVELOPER"]):
        return "Realty", "Real Estate Developers"
    elif any(k in ind_upper for k in ["PROPERTY SERVICES"]):
        return "Realty", "Real Estate Services"
    
    # 14. Telecommunication
    elif any(k in ind_upper for k in ["TELECOM EQUIPMENT"]):
        return "Telecommunication", "Telecom - Equipment & Accessories"
    elif any(k in ind_upper for k in ["TELECOM", "WIRELESS", "CELLULAR"]):
        return "Telecommunication", "Telecom - Services"
    
    # 15. Media, Entertainment & Publication
    elif any(k in ind_upper for k in ["BROADCAST", "CABLE", "TV"]):
        return "Media, Entertainment & Publication", "Broadcasting & Cable TV"
    elif any(k in ind_upper for k in ["PUBLISH", "PRINT", "NEWSPAPER"]):
        return "Media, Entertainment & Publication", "Print Media & Publishing"
    elif any(k in ind_upper for k in ["MEDIA", "ENTERTAIN", "FILM", "MULTIPLEX"]):
        return "Media, Entertainment & Publication", "Entertainment & Content"
    
    # 16. Consumer Services
    elif any(k in ind_upper for k in ["HOTEL", "RESORT", "TRAVEL", "TOURISM", "AIRLINE"]):
        return "Consumer Services", "Travel & Tourism"
    elif any(k in ind_upper for k in ["RESTAURANT", "QSR", "FOOD SERVICE"]):
        return "Consumer Services", "Restaurants & QSR"
    elif any(k in ind_upper for k in ["RETAIL", "STORE", "MALL", "SUPERMARKET"]):
        return "Consumer Services", "Retailing"
    elif any(k in ind_upper for k in ["LEISURE", "GAMING", "CLUB"]):
        return "Consumer Services", "Leisure Services"
    
    # 17. Consumer Durables
    elif any(k in ind_upper for k in ["JEWELLERY", "WATCH", "GEM"]):
        return "Consumer Durables", "Gems, Jewellery & Watches"
    elif any(k in ind_upper for k in ["ELECTRONIC", "APPLIANCE", "TV"]):
        return "Consumer Durables", "Consumer Electronics & Appliances"
    elif any(k in ind_upper for k in ["DURABLE"]):
        return "Consumer Durables", "Household & Personal Products"
    
    # 18. Textiles
    elif any(k in ind_upper for k in ["GARMENT", "APPAREL", "CLOTHING"]):
        return "Textiles", "Garments & Apparels"
    elif any(k in ind_upper for k in ["TEXTILE", "SPINNING", "WEAVING"]):
        return "Textiles", "Textiles & Weaving"
    
    # 19. Forest Materials
    elif any(k in ind_upper for k in ["PAPER", "FOREST", "JUTE", "TIMBER", "WOOD"]):
        return "Forest Materials", "Paper, Forest & Jute Products"
    
    # 20. Utilities
    elif any(k in ind_upper for k in ["GAS DISTRIBUTION", "PIPELINE"]):
        return "Utilities", "Gas Transmission & Utilities"
    elif any(k in ind_upper for k in ["WATER", "WASTE", "UTILITY"]):
        return "Utilities", "Water & Other Utilities"
    
    # 21. Services
    elif any(k in ind_upper for k in ["LOGISTIC", "TRANSPORT", "COURIER", "FREIGHT"]):
        return "Services", "Logistics & Transportation Services"
    elif any(k in ind_upper for k in ["PORT", "SHIPPING", "DOCK"]):
        return "Services", "Port & Shipping Services"
    elif any(k in ind_upper for k in ["SERVICE", "CONSULTING"]):
        return "Services", "Commercial & Professional Services"
    
    # 22. Diversified
    else:
        return "Diversified", "Diversified Industrials"

# Optional: Load local CSV if available ('nse_classification.csv')
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
    
    # --- 4. SAFE 22-SECTOR / 59-INDUSTRY MAPPING ---
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
        df["Sector"] = df["NSE_Sector"].combine_first(df["Sector"]).fillna("Diversified")
        df["Industry"] = df["NSE_Industry"].combine_first(df["Industry"]).fillna("Diversified Industrials")
        
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
