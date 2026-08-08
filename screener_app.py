import glob
import io
import json
import os
import re
import smtplib
import time
import calendar
from datetime import datetime, date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from google import genai
import markdown
import plotly.express as px
import requests
import pandas as pd
import numpy as np
import streamlit as st
from tradingview_screener import Query, col

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="India Equities Screener & Watchlist Studio",
    page_icon="📈",
    layout="wide",
)

# ==========================================
# CUSTOM SLEEK CSS FOR ST.TABLE
# ==========================================
TABLE_CUSTOM_CSS = """
<style>
div[data-testid="stTable"] { overflow-x: auto !important; }
div[data-testid="stTable"] table { width: 100% !important; border-collapse: collapse !important; font-size: 13px !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; }
div[data-testid="stTable"] th { padding: 8px 12px !important; text-align: center !important; font-weight: 600 !important; white-space: nowrap !important; background-color: #1E222D !important; color: #E0E2EC !important; border-bottom: 2px solid #2B2F3E !important; min-width: 85px !important; }
div[data-testid="stTable"] td { padding: 7px 12px !important; text-align: center !important; white-space: nowrap !important; border-bottom: 1px solid #2B2F3E !important; min-width: 85px !important; }
div[data-testid="stTable"] th:nth-child(1), div[data-testid="stTable"] td:nth-child(1) { text-align: left !important; font-weight: 600 !important; white-space: nowrap !important; min-width: 115px !important; max-width: 150px !important; }
</style>
"""
st.markdown(TABLE_CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 0. AUTOMATIC GITHUB GIST PERSISTENCE
# ==========================================
WATCHLIST_FILE = "local_watchlists.json"
PRESETS_FILE = "local_filter_presets.json"
REPORTS_FILE = "local_fundamental_reports.json"
BRIEFINGS_FILE = "local_market_briefings.json"
TRADEBOOK_FILE = "local_tradebook.json"

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)
GIST_ID = st.secrets.get("GIST_ID", None)

def _gist_request(method, filename, data=None):
    if not GITHUB_TOKEN or not GIST_ID: return None
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/gists/{GIST_ID}"
    try:
        if method == "GET":
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200 and filename in res.json().get("files", {}):
                return json.loads(res.json()["files"][filename]["content"])
        elif method == "PATCH" and data is not None:
            requests.patch(url, headers=headers, json={"files": {filename: {"content": json.dumps(data, indent=2)}}}, timeout=5)
    except Exception:
        pass
    return None

def load_watchlists():
    res = _gist_request("GET", WATCHLIST_FILE)
    if res: return res
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {"Post Breakout Monitor": ["NSE:ZOMATO", "NSE:CDSL", "NSE:TITAGARH"], "Focus List": ["NSE:JINDWORLD", "NSE:TRENT", "NSE:HAL", "NSE:RECLTD"], "Weekly Focus": ["NSE:BHEL", "NSE:ABB", "NSE:SIEMENS", "NSE:CGPOWER"], "Scan Bulk": [], "Sold Stocks": []}

def save_watchlists(data):
    try:
        with open(WATCHLIST_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass
    _gist_request("PATCH", WATCHLIST_FILE, data)

def load_filter_presets():
    res = _gist_request("GET", PRESETS_FILE)
    if res: return res
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {"🏆 CAN SLIM & Growth Breakout": {"exchanges": ["NSE", "BSE"], "sectors": [], "industries": [], "indices": [], "min_mcap_cr": 1000, "vol_period_days": 60, "min_vol_cr": 5.0, "en_ipo": False, "ipo_filter": "All Stocks (No IPO Filter)", "en_eps_q": True, "min_eps_q": 15.0, "en_sales_q": True, "min_sales_q": 10.0, "allow_na_growth": True, "en_rs_rating": True, "min_rs_rating": 80, "en_adr": True, "min_adr": 2.5, "en_above_52l": True, "min_above_52l": 20, "en_below_52h": True, "max_below_52h": 25, "en_circuit": True, "circuit_val": ["2%", "5%", "10%"], "selected_perf_labels": ["1 Week", "1 Month", "3 Months", "6 Months"], "max_results": 4000, "ma_configs": [{"en": True, "type": "EMA", "len": 21}, {"en": True, "type": "SMA", "len": 50}, {"en": False, "type": "SMA", "len": 200}, {"en": False, "type": "EMA", "len": 10}, {"en": False, "type": "SMA", "len": 150}], "perf_configs": {c: {"en": False, "val": 0.0} for c in ["Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.YTD", "Perf.Y"]}}}

def save_filter_presets(data):
    try:
        with open(PRESETS_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass
    _gist_request("PATCH", PRESETS_FILE, data)

def load_fundamental_reports():
    res = _gist_request("GET", REPORTS_FILE)
    if res: return res
    if os.path.exists(REPORTS_FILE):
        try:
            with open(REPORTS_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {}

def save_fundamental_reports(data):
    try:
        with open(REPORTS_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass
    _gist_request("PATCH", REPORTS_FILE, data)

def load_market_briefings():
    res = _gist_request("GET", BRIEFINGS_FILE)
    if res: return res
    if os.path.exists(BRIEFINGS_FILE):
        try:
            with open(BRIEFINGS_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {}

def save_market_briefings(data):
    try:
        with open(BRIEFINGS_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass
    _gist_request("PATCH", BRIEFINGS_FILE, data)

def load_tradebook():
    res = _gist_request("GET", TRADEBOOK_FILE)
    if res: return res
    if os.path.exists(TRADEBOOK_FILE):
        try:
            with open(TRADEBOOK_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {"config": {"starting_capital": 500000.0}, "trades": []}

def save_tradebook(data):
    try:
        with open(TRADEBOOK_FILE, "w") as f: json.dump(data, f, indent=2)
    except Exception: pass
    _gist_request("PATCH", TRADEBOOK_FILE, data)

if "watchlists" not in st.session_state: st.session_state.watchlists = load_watchlists()
if "active_watchlist_name" not in st.session_state: st.session_state.active_watchlist_name = list(st.session_state.watchlists.keys())[0]
if "filter_presets" not in st.session_state: st.session_state.filter_presets = load_filter_presets()
if "fundamental_reports" not in st.session_state: st.session_state.fundamental_reports = load_fundamental_reports()
if "market_briefings" not in st.session_state: st.session_state.market_briefings = load_market_briefings()
if "tradebook" not in st.session_state: st.session_state.tradebook = load_tradebook()
if "active_scan_summary" not in st.session_state: st.session_state.active_scan_summary = {}
if "rs_rating_map" not in st.session_state: st.session_state.rs_rating_map = {}
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "scan_sel_counter" not in st.session_state: st.session_state.scan_sel_counter = 0
if "wl_sel_counter" not in st.session_state: st.session_state.wl_sel_counter = 0

def fetch_nifty500_close_on_date(date_str, df_mm=None):
    try:
        if df_mm is not None and not df_mm.empty and "Date" in df_mm.columns and "Nifty 500 Close" in df_mm.columns:
            match = df_mm[df_mm["Date"] == date_str]
            if not match.empty:
                val = pd.to_numeric(match.iloc[0]["Nifty 500 Close"], errors="coerce")
                if pd.notna(val) and val > 0: return float(val)
    except Exception: pass
    try:
        dt_obj = pd.to_datetime(date_str)
        p_start = int(dt_obj.timestamp())
        p_end = p_start + 86400 * 4
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/^CRSLDX?period1={p_start}&period2={p_end}&interval=1d"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            for q in data["chart"]["result"][0]["indicators"]["quote"][0]["close"]:
                if q is not None and q > 0: return float(q)
    except Exception: pass
    return 23700.0

def create_pdf_bytes(ticker, report_md):
    try: from fpdf import FPDF
    except ImportError: return report_md.encode("utf-8")
    def sanitize_for_pdf(text):
        if not text: return ""
        replacements = {"🟢": "[PASS] ", "🔴": "[FAIL] ", "🟡": "[WATCH] ", "⚠️": "[WARN] ", "🚀": "[CATALYST] ", "⚪": "[N/A] ", "🟣": "[REVIEW] ", "📊": "", "🏥": "", "📈": "", "🔥": "", "📋": "", "🧠": "", "⭐": "", "🎯": "[TARGET] ", "🚨": "[CIRCUIT] ", "₹": "Rs. ", "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "•": "*", "…": "..."}
        for k, v in replacements.items(): text = text.replace(k, v)
        return text.encode("latin-1", "replace").decode("latin-1")
    class PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, sanitize_for_pdf(f"MINERVINI FUNDAMENTAL AI REPORT - {ticker}"), ln=True, align="R")
            self.line(10, 16, 200, 16)
            self.ln(4)
        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, sanitize_for_pdf(f"Page {self.page_no()} | Generated by India Equities Screener Studio"), align="C")
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, sanitize_for_pdf(f"{ticker} Fundamental Analysis Report"), ln=True, align="L")
        pdf.ln(2)
        pdf.set_font("Helvetica", size=9)
        for line in report_md.split("\n"):
            line_str = sanitize_for_pdf(line.strip())
            if not line_str:
                pdf.ln(1.5)
                continue
            if line_str.startswith("#### ") or line_str.startswith("### "):
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(20, 50, 120)
                pdf.cell(0, 6, line_str.replace("#", "").strip(), ln=True)
                pdf.set_font("Helvetica", size=9)
                pdf.set_text_color(0, 0, 0)
            elif line_str.startswith("## ") or line_str.startswith("# "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(0, 7, line_str.replace("#", "").strip(), ln=True)
                pdf.set_font("Helvetica", size=9)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.multi_cell(0, 4.5, line_str)
                pdf.ln(0.5)
        return bytes(pdf.output())
    except Exception: return report_md.encode("utf-8")

def run_gemini_fundamental_analysis(ticker_input, reports_store=None, status_log=None):
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    screener_sid = st.secrets.get("SCREENER_SESSION_ID", "")
    email_addr = st.secrets.get("EMAIL_ADDRESS", "chethanshivaraju7@gmail.com")
    email_pass = st.secrets.get("EMAIL_APP_PASSWORD", "")
    if not gemini_key:
        if status_log: status_log.error("❌ Missing GEMINI_API_KEY in Streamlit Secrets!")
        return None
    
    client = genai.Client(api_key=gemini_key)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept': 'text/html', 'Referer': 'https://www.screener.in/'}
    cookies = {'sessionid': screener_sid}
    clean_ticker = ticker_input.split(":")[-1].strip().upper() if ":" in str(ticker_input) else str(ticker_input).strip().upper()
    download_dir = "documents"
    os.makedirs(download_dir, exist_ok=True)
    for f in glob.glob(f"{download_dir}/*"): os.remove(f)
    url = f"https://www.screener.in/company/{clean_ticker}/consolidated/"
    
    try:
        if status_log: status_log.write(f"📡 **{clean_ticker}:** Accessing Screener.in page...")
        response = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        if response.status_code != 200:
            if status_log: status_log.error(f"❌ **{clean_ticker}:** Could not access Screener.in page.")
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        documents_section = soup.find(id="documents")
        if not documents_section:
            if status_log: status_log.warning(f"⚠️ **{clean_ticker}:** No documents section found.")
            return None
        ars, transcripts, ppts = [], [], []
        for link in documents_section.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True).lower()
            if "financial year" in text or "annual report" in text: ars.append(("Annual Report", href))
            elif text == "transcript": transcripts.append(("Transcript", href))
            elif text == "ppt": ppts.append(("PPT", href))
        
        state = {"count": 0, "urls": set()}
        def try_download(text, href):
            if href in state["urls"]: return False
            full_url = href if href.startswith("http") else urljoin("https://www.screener.in", href)
            try:
                doc_response = requests.get(full_url, headers=headers, cookies=cookies, timeout=30, allow_redirects=True)
                if b"%PDF" in doc_response.content[:100]:
                    file_name = f"screener_doc_{state['count'] + 1}.pdf"
                    with open(os.path.join(download_dir, file_name), "wb") as f: f.write(doc_response.content)
                    state["count"] += 1
                    state["urls"].add(href)
                    time.sleep(1)
                    return True
            except Exception: pass
            return False
            
        ar_count, tr_count, ppt_count = 0, 0, 0
        for t, h in ars:
            if ar_count >= 1: break
            if try_download("Annual Report", h): ar_count += 1
        for t, h in transcripts:
            if tr_count >= 4: break
            if try_download("Transcript", h): tr_count += 1
        for t, h in ppts:
            if ppt_count >= 4: break
            if try_download("PPT", h): ppt_count += 1
            
        pdf_files = glob.glob(f"{download_dir}/*.pdf")
        if not pdf_files:
            if status_log: status_log.error(f"❌ **{clean_ticker}:** Could not download any PDFs.")
            return None
            
        uploaded_files = []
        for file_path in pdf_files: uploaded_files.append(client.files.upload(file=file_path))
        for f in uploaded_files:
            while True:
                if "ACTIVE" in str(client.files.get(name=f.name).state).upper(): break
                time.sleep(3)

        prompt = f"""
You are an uncompromising, strict Mark Minervini-style fundamental analyst. Analyze the provided Annual Report, Investor Presentations, and Earnings Call Transcripts for {clean_ticker}.

### STRICT VERDICT RULES
- **NO CATALYST = NO PASS:** Even if YoY earnings are >20%, you CANNOT award a 🟢 PASS if there is no explicit forward-looking catalyst. Maximum grade is 🟡 WATCHLIST.

### MANDATORY OUTPUT FORMAT (Do not skip ANY sections)

#### 1. HEADER & INSTANT VERDICT
- **MINERVINI FUNDAMENTAL VERDICT:** [Insert 🟢 PASS / 🟡 WATCHLIST / 🔴 FAIL]
- **🚀 PRIMARY CATALYST / BREAKOUT TRIGGER:** [1-2 BOLD sentences stating the exact forward-looking trigger. If NONE, state: "⚠️ NO CLEAR FORWARD CATALYST DETECTED"].
- **VERDICT LOGIC:** [1-2 sentence justification].

#### 2. SUPERPERFORMANCE SCORECARD
| Core Pillar | Status | Key Metric / Reason |
| :--- | :---: | :--- |
| **1. Growth Velocity (Code 33)** | [🟢/🟡/🔴/⚪] | [1-line summary] |
| **2. Forward Catalyst & Triggers** | [🟢/🟡/🔴/⚪] | [1-line summary] |
| **3. Earnings Quality & Red Flags**| [🟢/🟡/🔴/⚪] | [1-line summary] |

#### 3. BOTTOM LINE UP FRONT (BLUF)
- **Top Fundamental Strengths:**
  - [Bullet 1]
  - [Bullet 2]
- **Top Red Flags / Concerns:**
  - [Bullet 1]
  - [Bullet 2]

#### DETAILED ANALYSIS BREAKDOWN
##### SECTION 1: Growth Velocity
* **Latest Quarter YoY Growth:** [Detail]
* **Code 33 Acceleration:** [Detail]
* **Margin Dynamics:** [Detail]
* **Annual Track Record:** [Detail]

##### SECTION 2: Sector-Adaptive Catalyst & Forward Triggers
* **Primary Sector Catalyst:** [Detail]
* **Catalyst Magnitude & Timeline:** [Detail]
* **Market Leadership:** [Detail]

##### SECTION 3: Quality of Earnings & Red Flags
* **Inventory vs. Sales Growth:** [Detail]
* **Receivables vs. Sales Growth:** [Detail]
* **Cash Flow vs. Earnings:** [Detail]
* **Debt Load & Solvency:** [Detail]
"""
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt] + uploaded_files, config={"service_tier": "flex", "http_options": {"timeout": 900000}})
        except Exception as e:
            if "tokens allowed" in str(e) or "400" in str(e):
                response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt] + uploaded_files[:4], config={"service_tier": "flex", "http_options": {"timeout": 900000}})
            else: raise e

        analysis_text = response.text
        verdict = "🟣 Review Needed"
        for line in analysis_text.upper().split("\n"):
            if "MINERVINI FUNDAMENTAL VERDICT:" in line or "VERDICT:" in line:
                if "PASS" in line or "🟢" in line: verdict = "PASS 🟢"
                elif "WATCHLIST" in line or "🟡" in line: verdict = "WATCHLIST 🟡"
                elif "FAIL" in line or "🔴" in line: verdict = "FAIL 🔴"
                break

        today_str = time.strftime("%Y-%m-%d")
        report_entry = {"ticker": clean_ticker, "verdict": verdict, "date": today_str, "report_md": analysis_text}
        
        if reports_store is not None:
            reports_store[clean_ticker] = report_entry
            save_fundamental_reports(reports_store)
        else:
            st.session_state.fundamental_reports[clean_ticker] = report_entry
            save_fundamental_reports(st.session_state.fundamental_reports)

        if status_log: status_log.write(f"✅ **{clean_ticker}:** Analysis complete! Verdict -> **{verdict}**")

        if email_addr and email_pass:
            try:
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                html_text = markdown.markdown(analysis_text, extensions=["tables"])
                msg = MIMEMultipart("alternative")
                msg["From"] = email_addr
                msg["To"] = email_addr
                msg["Subject"] = f"{clean_ticker} - {verdict}"
                msg.attach(MIMEText(analysis_text, "plain"))
                msg.attach(MIMEText(html_text, "html"))
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(email_addr, email_pass)
                server.send_message(msg)
                server.quit()
            except Exception: pass

        return report_entry
    except Exception as e:
        if status_log: status_log.error(f"❌ **{clean_ticker}:** Analysis failed -> {e}")
        return None

@st.dialog("🧠 Minervini Fundamental AI Analyst", width="large")
def show_fundamental_modal(ticker_symbol):
    clean_sym = ticker_symbol.split(":")[-1].strip().upper() if ":" in str(ticker_symbol) else str(ticker_symbol).strip().upper()
    rep = st.session_state.fundamental_reports.get(clean_sym)
    if not rep:
        st.info(f"No stored report for **{clean_sym}**. Click 'Analyze Selected'!")
    else:
        st.subheader(f"📊 {clean_sym} — {rep.get('verdict', 'N/A')}")
        st.caption(f"📅 Generated On: **{rep.get('date', 'N/A')}**")
        st.markdown("---")
        st.markdown(rep.get("report_md", ""))
        st.markdown("---")
        col_pdf, col_re = st.columns([1, 1])
        with col_pdf:
            st.download_button(label=f"📥 Download {clean_sym} Report (PDF)", data=create_pdf_bytes(clean_sym, rep.get("report_md", "")), file_name=f"{clean_sym}_Minervini_Fundamental_Report.pdf", mime="application/pdf", use_container_width=True, type="primary")
        with col_re:
            if st.button("🔄 Re-Analyze & Overwrite (Quarterly Refresh)", type="secondary", use_container_width=True):
                with st.spinner(f"📡 Fetching latest Screener.in PDFs for {clean_sym}..."):
                    if run_gemini_fundamental_analysis(clean_sym, st.session_state.fundamental_reports):
                        st.success("✅ Report replaced with latest data!")
                        st.rerun()

def run_gemini_market_awareness(df_mm, df_heat, df_rot, scan_summary_dict=None, status_log=None):
    gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    if not gemini_key: return None
    client = genai.Client(api_key=gemini_key)
    mm_text = f"NSE Market Monitor (Last 10 Trading Days):\n{df_mm.head(10).to_string(index=False)}" if not df_mm.empty else "No Data"
    heat_text = f"27-Sector CAN SLIM RS Heatmap:\n{df_heat.to_string(index=False)}" if not df_heat.empty else "No Data"
    rot_text = f"65-Day Historical Sector RS Ranks:\n{df_rot.head(10).to_string(index=False)}" if not df_rot.empty else "No Data"
    scan_text = "No Data"
    if scan_summary_dict: scan_text = f"Active Screener Breakdown:\n- Top Sectors:\n{json.dumps(scan_summary_dict.get('sectors', {}), indent=2)}\n- Top Industries:\n{json.dumps(scan_summary_dict.get('industries', {}), indent=2)}"
    
    prompt = f"""
You are a Senior Institutional Market Strategist. Analyze the inputs to produce an actionable **Daily Market & Sector Situational Awareness Briefing**.
INPUTS:
{mm_text}
{heat_text}
{rot_text}
{scan_text}

Generate the exact following markdown structure:
# 🏥 DAILY MARKET & SECTOR SITUATIONAL AWARENESS BRIEFING
#### 1. EXECUTIVE SUMMARY & MARKET REGIME
- **CURRENT MARKET REGIME:** [🟢 CONFIRMED UPTREND / 🟡 POWERED UPTREND (CAUTION) / 🟠 RANGEBOUND / 🔴 MARKET UNDER PRESSURE]
- **SETUP SUITABILITY MATRIX:** (Momentum Breakouts, Pullbacks, Consolidation: Highly Conductive/Selective/Avoid)
- **OVERALL MARKET STATE SUMMARY:** [Analysis]
#### 2. MARKET BREADTH & HEALTH SYNTHESIS
[Analysis of MAs, Thrust, Expansion]
#### 3. SECTOR MOMENTUM & ROTATION RADAR
[🟢 LEADERSHIP SECTORS, 🚀 EMERGING SECTORS, ⚠️ FADING SECTORS, 🔴 AVOID SECTORS]
#### 4. ACTIVE SCREENER SCAN CLUSTER ANALYSIS
[Analysis of scan data]
#### 5. ACTIONABLE NEXT-DAY EXECUTION PLAN
- 🛡️ Allowed Risk Per Trade
- 💰 Maximum Portfolio Deployment
- 🎯 Primary Focus Sectors & Industries for Tomorrow
- 🚨 Key Invalidation Levels
"""
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=[prompt], config={"service_tier": "flex", "http_options": {"timeout": 900000}})
        entry = {"date": time.strftime("%Y-%m-%d"), "briefing_md": response.text}
        st.session_state.market_briefings[entry["date"]] = entry
        save_market_briefings(st.session_state.market_briefings)
        return entry
    except Exception as e:
        if status_log: status_log.error(f"❌ Failed to generate Market Briefing -> {e}")
        return None

def fetch_excel_file(filename):
    if os.path.exists(filename): return filename
    headers_list = [{"User-Agent": "Mozilla/5.0"}]
    if GITHUB_TOKEN:
        headers_list.insert(0, {"User-Agent": "Mozilla/5.0", "Authorization": f"Bearer {GITHUB_TOKEN}"})
        headers_list.insert(0, {"User-Agent": "Mozilla/5.0", "Authorization": f"token {GITHUB_TOKEN}"})
    for repo in ["chethanshivaraju94-netizen/nse-market-monitor", "chethanshivaraju94-netizen/India-equities-screener"]:
        for branch in ["main", "master"]:
            for headers in headers_list:
                try:
                    res = requests.get(f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}", headers=headers, timeout=10)
                    if res.status_code == 200: return io.BytesIO(res.content)
                except Exception: pass
    return None

@st.cache_data(ttl=43200, show_spinner="📡 Synchronizing Circuit Bands...")
def get_nse_circuit_bands():
    symbol_to_band = {}
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        session.get("https://www.nseindia.com", timeout=5)
        res = session.get("https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O", timeout=6)
        if res.status_code == 200:
            for row in res.json().get("data", []):
                if row.get("symbol") and row.get("priceBand"): symbol_to_band[str(row["symbol"]).strip().upper()] = str(row["priceBand"]).strip()
    except Exception: pass
    if not symbol_to_band:
        try:
            res_cdn = requests.get("https://raw.githubusercontent.com/datasets/nse-stocks/master/data/stock_metadata.json", timeout=5)
            if res_cdn.status_code == 200:
                for item in res_cdn.json():
                    if item.get("symbol") and item.get("band"): symbol_to_band[str(item["symbol"]).strip().upper()] = str(item["band"]).strip()
        except Exception: pass
    return symbol_to_band

@st.cache_data(ttl=3600, show_spinner="📡 Fetching Market Monitor...")
def load_market_monitor_data():
    file_source = fetch_excel_file("NSE_Market_Monitor.xlsx")
    if file_source is None: return pd.DataFrame()
    try:
        df = pd.read_excel(file_source, sheet_name=0)
        if "Date" in df.columns: df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        return df
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner="📡 Fetching Sector Monitor...")
def load_sector_monitor_data():
    file_source = fetch_excel_file("NSE_Sector_Monitor.xlsx")
    if file_source is None: return pd.DataFrame(), pd.DataFrame()
    try:
        xls = pd.ExcelFile(file_source)
        df_heat = pd.read_excel(xls, sheet_name="Heatmap") if "Heatmap" in xls.sheet_names else pd.DataFrame()
        df_rot = pd.read_excel(xls, sheet_name="Rotation Tracker") if "Rotation Tracker" in xls.sheet_names else pd.DataFrame()
        if "Date" in df_rot.columns: df_rot["Date"] = pd.to_datetime(df_rot["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        return df_heat, df_rot
    except Exception: return pd.DataFrame(), pd.DataFrame()

def color_scale_3pt(val, v_min, v_mid, v_max, c_min=(248,105,107), c_mid=(255,255,255), c_max=(99,190,123)):
    try: v = float(val)
    except Exception: return ""
    if v <= v_min: r,g,b = c_min
    elif v >= v_max: r,g,b = c_max
    elif v < v_mid:
        ratio = (v - v_min) / max((v_mid - v_min), 1e-6)
        r, g, b = [int(c_min[i] + (c_mid[i] - c_min[i]) * ratio) for i in range(3)]
    else:
        ratio = (v - v_mid) / max((v_max - v_mid), 1e-6)
        r, g, b = [int(c_mid[i] + (c_max[i] - c_mid[i]) * ratio) for i in range(3)]
    return f"background-color: #{r:02X}{g:02X}{b:02X}; color: #000000;"

def color_scale_2pt(val, v_min, v_max, c_min=(255,255,255), c_max=(99,190,123)):
    try: v = float(val)
    except Exception: return ""
    if v <= v_min: r,g,b = c_min
    elif v >= v_max: r,g,b = c_max
    else:
        ratio = (v - v_min) / max((v_max - v_min), 1e-6)
        r, g, b = [int(c_min[i] + (c_max[i] - c_min[i]) * ratio) for i in range(3)]
    return f"background-color: #{r:02X}{g:02X}{b:02X}; color: #000000;"

def color_binary_badge(val):
    v_str = str(val).strip().lower()
    if v_str in ["yes", "up"]: return "background-color: #63BE7B; color: #000000; font-weight: bold;"
    elif v_str in ["no", "down"]: return "background-color: #F8696B; color: #000000; font-weight: bold;"
    return ""

def safe_map(styler, func, subset=None):
    return styler.map(func, subset=subset) if hasattr(styler, "map") else styler.applymap(func, subset=subset)

def style_market_monitor(df):
    styler = df.style.format({c: "{:.0f}" for c in ["Up 4% Today", "Down 4% Today", "Advances", "Declines", "52W Highs", "52W Lows"] if c in df.columns}, na_rep="N/A")
    styler = styler.format({c: "{:.2f}" for c in ["5 Day Ratio", "10 Day Ratio", "A/D Ratio", "Volume Breadth", "> 200 SMA (%)", "> 50 SMA (%)", "> 20 EMA (%)", "> 10 EMA (%)", "Nifty 500 Close", "Nifty 500 Chg %"] if c in df.columns}, na_rep="N/A")
    for c in ["Up 4% Today", "Advances", "52W Highs"]:
        if c in df.columns: styler = safe_map(styler, lambda v, mv=(750 if c=="Advances" else 200): color_scale_2pt(v, 0, mv, (255,255,255), (99,190,123)), subset=[c])
    for c in ["Down 4% Today", "Declines", "52W Lows"]:
        if c in df.columns: styler = safe_map(styler, lambda v, mv=(750 if c=="Declines" else 200): color_scale_2pt(v, 0, mv, (255,255,255), (248,105,107)), subset=[c])
    for c in ["5 Day Ratio", "10 Day Ratio", "A/D Ratio", "Volume Breadth"]:
        if c in df.columns: styler = safe_map(styler, lambda v: color_scale_3pt(v, 0.5, 1.0, 2.0), subset=[c])
    for c in ["> 200 SMA (%)", "> 50 SMA (%)", "> 20 EMA (%)", "> 10 EMA (%)"]:
        if c in df.columns: styler = safe_map(styler, lambda v: color_scale_3pt(v, 0.0, 50.0, 100.0), subset=[c])
    if "Nifty 500 Chg %" in df.columns: styler = safe_map(styler, lambda v: color_scale_3pt(v, -2.0, 0.0, 2.0), subset=["Nifty 500 Chg %"])
    try: return styler.hide(axis="index")
    except: return styler

def style_sector_heatmap(df):
    styler = df.style.format({c: "{:.0f}" for c in ["65D RS Rank"] if c in df.columns}, na_rep="N/A")
    styler = styler.format({c: "{:+.0f}" for c in ["5D Rank Velocity", "10D Rank Velocity", "21D Rank Velocity", "65D Rank Velocity"] if c in df.columns}, na_rep="N/A")
    styler = styler.format({c: "{:.2f}" for c in ["Close", "% Chg", "5D RS %", "21D RS %", "65D RS %", "% Off RS High"] if c in df.columns}, na_rep="N/A")
    for c in ["5D Rank Velocity", "10D Rank Velocity", "21D Rank Velocity", "65D Rank Velocity", "5D RS %", "21D RS %", "65D RS %"]:
        if c in df.columns: styler = safe_map(styler, lambda v: color_scale_3pt(v, -10, 0, 10), subset=[c])
    if "% Off RS High" in df.columns: styler = safe_map(styler, lambda v: color_scale_3pt(v, -15.0, -5.0, 0.0), subset=["% Off RS High"])
    for c in ["RS Trend (>50 SMA)", "> 10 EMA", "> 20 EMA", "> 50 SMA", "> 200 SMA"]:
        if c in df.columns: styler = safe_map(styler, color_binary_badge, subset=[c])
    try: return styler.hide(axis="index")
    except: return styler

def style_rotation_tracker(df):
    sec_cols = [c for c in df.columns if c != "Date"]
    styler = df.style.format({c: "{:.0f}" for c in sec_cols}, na_rep="N/A")
    num_sec = max(len(sec_cols), 1)
    mid_rank = max((num_sec // 2) + 1, 1)
    for c in sec_cols: styler = safe_map(styler, lambda v, ms=num_sec, mr=mid_rank: color_scale_3pt(v, 1, mr, ms, (99,190,123), (255,255,255), (248,105,107)), subset=[c])
    try: return styler.hide(axis="index")
    except: return styler

def get_left_aligned_column_config(col_list):
    cfg = {}
    for col in col_list:
        if col in ["TV_Link", "Screener_Link"]: cfg[col] = st.column_config.LinkColumn(col, alignment="left", width=95)
        elif col in ["S.No.", "S.No._num"]: cfg[col] = st.column_config.Column(col, alignment="left", width=75)
        elif "Rank Velocity" in col: cfg[col] = st.column_config.NumberColumn(col, alignment="left", format="%+d", width=125)
        elif col == "RS Rating": cfg[col] = st.column_config.NumberColumn("RS Rating", alignment="left", format="%d", width=95)
        elif col in ["Sector", "Basic Industry"]: cfg[col] = st.column_config.Column(col, alignment="left", width=220)
        else: cfg[col] = st.column_config.Column(col, alignment="left", width=110)
    return cfg

INDIAN_SECTOR_HIERARCHY = {
    "Automobile and Auto Components": ["Automobiles", "Auto Components & Ancillaries", "Tyres & Rubber"],
    "Capital Goods": ["Aerospace & Defense", "Electrical Equipment", "Engineering Services", "Industrial Manufacturing", "Industrial Products"],
    "Chemicals": ["Chemicals & Petrochemicals", "Fertilizers & Agrochemicals"],
    "Construction": ["Civil Construction", "Infrastructure Developers"],
    "Construction Materials": ["Cement & Cement Products", "Ceramics & Building Materials"],
    "Consumer Durables": ["Consumer Electronics & Appliances", "Gems, Jewellery & Watches", "Household & Personal Products"],
    "Consumer Services": ["Leisure Services", "Restaurants & QSR", "Retailing", "Travel & Tourism"],
    "Diversified": ["Diversified Commercial Services", "Diversified Industrials"],
    "Fast Moving Consumer Goods": ["Agricultural Food & Other Products", "Beverages", "Food Products", "Personal Care", "Tobacco Products"],
    "Financial Services": ["Asset Management", "Banks", "Capital Markets", "Finance & NBFCs", "Financial Technology (Fintech)", "Insurance"],
    "Forest Materials": ["Paper, Forest & Jute Products"],
    "Healthcare": ["Healthcare Research, Analytics & Technology", "Healthcare Services", "Medical Equipment & Supplies", "Pharmaceuticals & Biotechnology"],
    "Information Technology": ["IT - Hardware", "IT - Software & Consulting", "IT - Services"],
    "Media, Entertainment & Publication": ["Broadcasting & Cable TV", "Entertainment & Content", "Print Media & Publishing"],
    "Metals & Mining": ["Ferrous Metals (Steel & Iron)", "Non-Ferrous Metals", "Minerals & Mining"],
    "Oil, Gas & Consumable Fuels": ["Consumable Fuels & Coal", "Oil & Gas Exploration & Production", "Petroleum Products & Refining"],
    "Power": ["Power Generation", "Power Transmission & Distribution"],
    "Realty": ["Real Estate Developers", "Real Estate Services"],
    "Services": ["Commercial & Professional Services", "Logistics & Transportation Services", "Port & Shipping Services"],
    "Telecommunication": ["Telecom - Equipment & Accessories", "Telecom - Services"],
    "Textiles": ["Garments & Apparels", "Textiles & Weaving"],
    "Utilities": ["Gas Transmission & Utilities", "Water & Other Utilities"],
}

TV_TO_INDIAN_MAP = {
    ("Commercial Services", "Financial Publishing/Services"): ("Financial Services", "Capital Markets"),
    ("Commercial Services", "Miscellaneous Commercial Services"): ("Services", "Commercial & Professional Services"),
    ("Commercial Services", "Personnel Services"): ("Services", "Commercial & Professional Services"),
    ("Consumer Durables", "Automotive Aftermarket"): ("Automobile and Auto Components", "Auto Components & Ancillaries"),
    ("Consumer Durables", "Electronics/Appliances"): ("Consumer Durables", "Consumer Electronics & Appliances"),
    ("Consumer Durables", "Home Furnishings"): ("Consumer Durables", "Household & Personal Products"),
    ("Consumer Durables", "Homebuilding"): ("Realty", "Real Estate Developers"),
    ("Consumer Durables", "Motor Vehicles"): ("Automobile and Auto Components", "Automobiles"),
    ("Consumer Durables", "Other Consumer Specialties"): ("Consumer Durables", "Gems, Jewellery & Watches"),
    ("Consumer Non-Durables", "Apparel/Footwear"): ("Textiles", "Garments & Apparels"),
    ("Consumer Non-Durables", "Beverages: Alcoholic"): ("Fast Moving Consumer Goods", "Beverages"),
    ("Consumer Non-Durables", "Food: Major Diversified"): ("Fast Moving Consumer Goods", "Food Products"),
    ("Consumer Non-Durables", "Food: Specialty/Candy"): ("Fast Moving Consumer Goods", "Food Products"),
    ("Consumer Non-Durables", "Household/Personal Care"): ("Fast Moving Consumer Goods", "Personal Care"),
    ("Consumer Services", "Broadcasting"): ("Media, Entertainment & Publication", "Broadcasting & Cable TV"),
    ("Consumer Services", "Hotels/Resorts/Cruise lines"): ("Consumer Services", "Travel & Tourism"),
    ("Consumer Services", "Movies/Entertainment"): ("Media, Entertainment & Publication", "Entertainment & Content"),
    ("Consumer Services", "Publishing: Books/Magazines"): ("Media, Entertainment & Publication", "Print Media & Publishing"),
    ("Consumer Services", "Restaurants"): ("Consumer Services", "Restaurants & QSR"),
    ("Distribution Services", "Electronics Distributors"): ("Capital Goods", "Industrial Products"),
    ("Distribution Services", "Medical Distributors"): ("Healthcare", "Medical Equipment & Supplies"),
    ("Distribution Services", "Wholesale Distributors"): ("Services", "Commercial & Professional Services"),
    ("Electronic Technology", "Aerospace & Defense"): ("Capital Goods", "Aerospace & Defense"),
    ("Electronic Technology", "Computer Communications"): ("Telecommunication", "Telecom - Equipment & Accessories"),
    ("Electronic Technology", "Computer Peripherals"): ("Information Technology", "IT - Hardware"),
    ("Electronic Technology", "Electronic Components"): ("Capital Goods", "Electrical Equipment"),
    ("Electronic Technology", "Electronic Equipment/Instruments"): ("Capital Goods", "Electrical Equipment"),
    ("Electronic Technology", "Electronic Production Equipment"): ("Capital Goods", "Industrial Manufacturing"),
    ("Electronic Technology", "Telecommunications Equipment"): ("Telecommunication", "Telecom - Equipment & Accessories"),
    ("Energy Minerals", "Oil & Gas Production"): ("Oil, Gas & Consumable Fuels", "Oil & Gas Exploration & Production"),
    ("Energy Minerals", "Oil Refining/Marketing"): ("Oil, Gas & Consumable Fuels", "Petroleum Products & Refining"),
    ("Finance", "Finance/Rental/Leasing"): ("Financial Services", "Finance & NBFCs"),
    ("Finance", "Financial Conglomerates"): ("Financial Services", "Finance & NBFCs"),
    ("Finance", "Investment Banks/Brokers"): ("Financial Services", "Capital Markets"),
    ("Finance", "Investment Managers"): ("Financial Services", "Asset Management"),
    ("Finance", "Life/Health Insurance"): ("Financial Services", "Insurance"),
    ("Finance", "Major Banks"): ("Financial Services", "Banks"),
    ("Finance", "Multi-Line Insurance"): ("Financial Services", "Insurance"),
    ("Finance", "Real Estate Development"): ("Realty", "Real Estate Developers"),
    ("Finance", "Regional Banks"): ("Financial Services", "Banks"),
    ("Health Services", "Hospital/Nursing Management"): ("Healthcare", "Healthcare Services"),
    ("Health Services", "Medical/Nursing Services"): ("Healthcare", "Healthcare Services"),
    ("Health Technology", "Biotechnology"): ("Healthcare", "Pharmaceuticals & Biotechnology"),
    ("Health Technology", "Medical Specialties"): ("Healthcare", "Medical Equipment & Supplies"),
    ("Health Technology", "Pharmaceuticals: Generic"): ("Healthcare", "Pharmaceuticals & Biotechnology"),
    ("Health Technology", "Pharmaceuticals: Major"): ("Healthcare", "Pharmaceuticals & Biotechnology"),
    ("Health Technology", "Pharmaceuticals: Other"): ("Healthcare", "Pharmaceuticals & Biotechnology"),
    ("Industrial Services", "Contract Drilling"): ("Oil, Gas & Consumable Fuels", "Oil & Gas Exploration & Production"),
    ("Industrial Services", "Engineering & Construction"): ("Construction", "Civil Construction"),
    ("Industrial Services", "Oilfield Services/Equipment"): ("Oil, Gas & Consumable Fuels", "Oil & Gas Exploration & Production"),
    ("Non-Energy Minerals", "Construction Materials"): ("Construction Materials", "Ceramics & Building Materials"),
    ("Non-Energy Minerals", "Forest Products"): ("Forest Materials", "Paper, Forest & Jute Products"),
    ("Non-Energy Minerals", "Other Metals/Minerals"): ("Metals & Mining", "Minerals & Mining"),
    ("Non-Energy Minerals", "Steel"): ("Metals & Mining", "Ferrous Metals (Steel & Iron)"),
    ("Process Industries", "Agricultural Commodities/Milling"): ("Fast Moving Consumer Goods", "Agricultural Food & Other Products"),
    ("Process Industries", "Chemicals: Agricultural"): ("Chemicals", "Fertilizers & Agrochemicals"),
    ("Process Industries", "Chemicals: Major Diversified"): ("Chemicals", "Chemicals & Petrochemicals"),
    ("Process Industries", "Chemicals: Specialty"): ("Chemicals", "Chemicals & Petrochemicals"),
    ("Process Industries", "Containers/Packaging"): ("Capital Goods", "Industrial Products"),
    ("Process Industries", "Industrial Specialties"): ("Capital Goods", "Industrial Manufacturing"),
    ("Process Industries", "Pulp & Paper"): ("Forest Materials", "Paper, Forest & Jute Products"),
    ("Process Industries", "Textiles"): ("Textiles", "Textiles & Weaving"),
    ("Producer Manufacturing", "Auto Parts: OEM"): ("Automobile and Auto Components", "Auto Components & Ancillaries"),
    ("Producer Manufacturing", "Building Products"): ("Construction Materials", "Cement & Cement Products"),
    ("Producer Manufacturing", "Electrical Products"): ("Capital Goods", "Electrical Equipment"),
    ("Producer Manufacturing", "Industrial Machinery"): ("Capital Goods", "Industrial Manufacturing"),
    ("Producer Manufacturing", "Metal Fabrication"): ("Capital Goods", "Industrial Manufacturing"),
    ("Producer Manufacturing", "Miscellaneous Manufacturing"): ("Capital Goods", "Industrial Products"),
    ("Producer Manufacturing", "Office Equipment/Supplies"): ("Consumer Durables", "Household & Personal Products"),
    ("Producer Manufacturing", "Trucks/Construction/Farm Machinery"): ("Automobile and Auto Components", "Automobiles"),
    ("Retail Trade", "Apparel/Footwear Retail"): ("Consumer Services", "Retailing"),
    ("Retail Trade", "Electronics/Appliance Stores"): ("Consumer Services", "Retailing"),
    ("Retail Trade", "Internet Retail"): ("Consumer Services", "Retailing"),
    ("Retail Trade", "Specialty Stores"): ("Consumer Services", "Retailing"),
    ("Technology Services", "Information Technology Services"): ("Information Technology", "IT - Services"),
    ("Technology Services", "Internet Software/Services"): ("Information Technology", "IT - Software & Consulting"),
    ("Technology Services", "Packaged Software"): ("Information Technology", "IT - Software & Consulting"),
    ("Transportation", "Air Freight/Couriers"): ("Services", "Logistics & Transportation Services"),
    ("Transportation", "Airlines"): ("Consumer Services", "Travel & Tourism"),
    ("Transportation", "Marine Shipping"): ("Services", "Port & Shipping Services"),
    ("Transportation", "Other Transportation"): ("Services", "Logistics & Transportation Services"),
    ("Transportation", "Railroads"): ("Services", "Logistics & Transportation Services"),
    ("Utilities", "Electric Utilities"): ("Power", "Power Generation"),
    ("Utilities", "Gas Distributors"): ("Utilities", "Gas Transmission & Utilities"),
}

st.sidebar.markdown("### 💾 Saved Filter Presets")
preset_names = list(st.session_state.filter_presets.keys())
selected_preset_name = st.sidebar.selectbox("Load or Update Strategy Preset:", options=preset_names, index=0 if preset_names else None, key="sb_preset_selector")

col_load, col_update, col_del = st.sidebar.columns([1.2, 1.2, 0.9])
with col_load:
  if st.sidebar.button("⚡ Load", use_container_width=True, type="primary"):
    if selected_preset_name in st.session_state.filter_presets:
      p = st.session_state.filter_presets[selected_preset_name]
      st.session_state["f_exchanges"] = p.get("exchanges", ["NSE", "BSE"])
      st.session_state["f_sectors"] = p.get("sectors", [])
      st.session_state["f_industries"] = p.get("industries", [])
      st.session_state["f_indices"] = p.get("indices", [])
      st.session_state["f_min_mcap"] = p.get("min_mcap_cr", 1000)
      st.session_state["f_vol_period"] = p.get("vol_period_days", 60)
      st.session_state["f_min_vol"] = p.get("min_vol_cr", 5.0)
      st.session_state["f_en_ipo"] = p.get("en_ipo", False)
      st.session_state["f_ipo"] = p.get("ipo_filter", "All Stocks (No IPO Filter)")
      st.session_state["f_en_eps_q"] = p.get("en_eps_q", False)
      st.session_state["f_min_eps_q"] = p.get("min_eps_q", 10.0)
      st.session_state["f_en_sales_q"] = p.get("en_sales_q", False)
      st.session_state["f_min_sales_q"] = p.get("min_sales_q", 10.0)
      st.session_state["f_allow_na_growth"] = p.get("allow_na_growth", True)
      st.session_state["f_en_rs_rating"] = p.get("en_rs_rating", True)
      st.session_state["f_min_rs_rating"] = p.get("min_rs_rating", 80)
      st.session_state["f_en_adr"] = p.get("en_adr", True)
      st.session_state["f_min_adr"] = p.get("min_adr", 2.25)
      st.session_state["f_en_52l"] = p.get("en_above_52l", True)
      st.session_state["f_min_52l"] = p.get("min_above_52l", 20)
      st.session_state["f_en_52h"] = p.get("en_below_52h", True)
      st.session_state["f_max_52h"] = p.get("max_below_52h", 30)
      st.session_state["f_en_circuit"] = p.get("en_circuit", True)
      st.session_state["f_circuit_val"] = p.get("circuit_val", ["2%", "5%", "10%"])
      st.session_state["f_perf_labels"] = p.get("selected_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"])
      st.session_state["f_max_res"] = p.get("max_results", 4000)
      for i, cfg in enumerate(p.get("ma_configs", []), 1):
        st.session_state[f"ma_{i}_en"] = cfg.get("en", False)
        st.session_state[f"ma_{i}_type"] = cfg.get("type", "SMA")
        st.session_state[f"ma_{i}_len"] = cfg.get("len", 50)
      for c_key, p_val in p.get("perf_configs", {}).items():
        st.session_state[f"en_perf_{c_key}"] = p_val.get("en", False)
        st.session_state[f"val_perf_{c_key}"] = p_val.get("val", 0.0)
      st.success(f"Loaded '{selected_preset_name}'!")
      st.rerun()

with col_update:
  if st.sidebar.button("🔄 Update", use_container_width=True):
    if selected_preset_name in st.session_state.filter_presets:
      st.session_state.filter_presets[selected_preset_name] = {
          "exchanges": st.session_state.get("f_exchanges", ["NSE", "BSE"]),
          "sectors": st.session_state.get("f_sectors", []),
          "industries": st.session_state.get("f_industries", []),
          "indices": st.session_state.get("f_indices", []),
          "min_mcap_cr": st.session_state.get("f_min_mcap", 1000),
          "vol_period_days": st.session_state.get("f_vol_period", 60),
          "min_vol_cr": st.session_state.get("f_min_vol", 5.0),
          "en_ipo": st.session_state.get("f_en_ipo", False),
          "ipo_filter": st.session_state.get("f_ipo", "All Stocks (No IPO Filter)"),
          "en_eps_q": st.session_state.get("f_en_eps_q", False),
          "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
          "en_sales_q": st.session_state.get("f_en_sales_q", False),
          "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
          "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
          "en_rs_rating": st.session_state.get("f_en_rs_rating", True),
          "min_rs_rating": st.session_state.get("f_min_rs_rating", 80),
          "en_adr": st.session_state.get("f_en_adr", True),
          "min_adr": st.session_state.get("f_min_adr", 2.25),
          "en_above_52l": st.session_state.get("f_en_52l", True),
          "min_above_52l": st.session_state.get("f_min_52l", 20),
          "en_below_52h": st.session_state.get("f_en_52h", True),
          "max_below_52h": st.session_state.get("f_max_52h", 30),
          "en_circuit": st.session_state.get("f_en_circuit", True),
          "circuit_val": st.session_state.get("f_circuit_val", ["2%", "5%", "10%"]),
          "selected_perf_labels": st.session_state.get("f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]),
          "max_results": st.session_state.get("f_max_res", 4000),
          "ma_configs": [{"en": st.session_state.get(f"ma_{i}_en", False), "type": st.session_state.get(f"ma_{i}_type", "SMA"), "len": st.session_state.get(f"ma_{i}_len", 50)} for i in range(1, 6)],
          "perf_configs": {c: {"en": st.session_state.get(f"en_perf_{c}", False), "val": st.session_state.get(f"val_perf_{c}", 0.0)} for c in ["Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.YTD", "Perf.Y"]},
      }
      save_filter_presets(st.session_state.filter_presets)
      st.success(f"Updated '{selected_preset_name}'!")
      st.rerun()

with col_del:
  if st.sidebar.button("🗑️ Del", use_container_width=True):
    if len(preset_names) > 1 and selected_preset_name in st.session_state.filter_presets:
      del st.session_state.filter_presets[selected_preset_name]
      save_filter_presets(st.session_state.filter_presets)
      st.rerun()

with st.sidebar.expander("➕ Save Current Filters as New Preset"):
  with st.form("save_preset_form", clear_on_submit=True):
    new_preset_name = st.text_input("Preset Name:", placeholder="e.g., Breakout Momentum")
    if st.form_submit_button("💾 Save Preset", use_container_width=True):
      if new_preset_name:
        st.session_state.filter_presets[new_preset_name] = {
            "exchanges": st.session_state.get("f_exchanges", ["NSE", "BSE"]),
            "sectors": st.session_state.get("f_sectors", []),
            "industries": st.session_state.get("f_industries", []),
            "indices": st.session_state.get("f_indices", []),
            "min_mcap_cr": st.session_state.get("f_min_mcap", 1000),
            "vol_period_days": st.session_state.get("f_vol_period", 60),
            "min_vol_cr": st.session_state.get("f_min_vol", 5.0),
            "en_ipo": st.session_state.get("f_en_ipo", False),
            "ipo_filter": st.session_state.get("f_ipo", "All Stocks (No IPO Filter)"),
            "en_eps_q": st.session_state.get("f_en_eps_q", False),
            "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
            "en_sales_q": st.session_state.get("f_en_sales_q", False),
            "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
            "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
            "en_rs_rating": st.session_state.get("f_en_rs_rating", True),
            "min_rs_rating": st.session_state.get("f_min_rs_rating", 80),
            "en_adr": st.session_state.get("f_en_adr", True),
            "min_adr": st.session_state.get("f_min_adr", 2.25),
            "en_above_52l": st.session_state.get("f_en_52l", True),
            "min_above_52l": st.session_state.get("f_min_52l", 20),
            "en_below_52h": st.session_state.get("f_en_52h", True),
            "max_below_52h": st.session_state.get("f_max_52h", 30),
            "en_circuit": st.session_state.get("f_en_circuit", True),
            "circuit_val": st.session_state.get("f_circuit_val", ["2%", "5%", "10%"]),
            "selected_perf_labels": st.session_state.get("f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]),
            "max_results": st.session_state.get("f_max_res", 4000),
            "ma_configs": [{"en": st.session_state.get(f"ma_{i}_en", False), "type": st.session_state.get(f"ma_{i}_type", "SMA"), "len": st.session_state.get(f"ma_{i}_len", 50)} for i in range(1, 6)],
            "perf_configs": {col: {"en": st.session_state.get(f"en_perf_{col}", False), "val": st.session_state.get(f"val_perf_{col}", 0.0)} for col in ["Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.YTD", "Perf.Y"]},
        }
        save_filter_presets(st.session_state.filter_presets)
        st.success(f"Saved preset '{new_preset_name}'!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("1. Exchange & Universe")
exchange_choice = st.sidebar.multiselect("Select Exchanges:", options=["NSE", "BSE"], default=st.session_state.get("f_exchanges", ["NSE", "BSE"]), key="f_exchanges")
st.sidebar.markdown("---")
st.sidebar.header("🏛️ Official NSE Filters & Indices")
sector_choice = st.sidebar.multiselect("NSE Sector:", options=list(INDIAN_SECTOR_HIERARCHY.keys()), default=st.session_state.get("f_sectors", []), key="f_sectors")
industry_options = sorted(list(set(ind for sec in sector_choice for ind in INDIAN_SECTOR_HIERARCHY.get(sec, []))) if sector_choice else list(set(ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds)))
industry_choice = st.sidebar.multiselect("NSE Industry:", options=industry_options, default=st.session_state.get("f_industries", []), key="f_industries")
exhaustive_indices = ["NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 200", "NIFTY 500", "NIFTY MIDCAP 50", "NIFTY MIDCAP 100", "NIFTY MIDCAP 150", "NIFTY SMALLCAP 50", "NIFTY SMALLCAP 100", "NIFTY SMALLCAP 250", "NIFTY MICROCAP 250", "NIFTY TOTAL MARKET", "NIFTY LARGEMIDCAP 250", "NIFTY BANK", "NIFTY AUTO", "NIFTY FINANCIAL SERVICES", "NIFTY FMCG", "NIFTY IT", "NIFTY MEDIA", "NIFTY METAL", "NIFTY PHARMA", "NIFTY PSU BANK", "NIFTY PRIVATE BANK", "NIFTY REALTY", "NIFTY HEALTHCARE", "NIFTY CONSUMER DURABLES", "NIFTY OIL & GAS", "NIFTY COMMODITIES", "NIFTY INDIA CONSUMPTION", "NIFTY CPSE", "NIFTY INFRASTRUCTURE", "NIFTY MNC", "NIFTY PSE", "NIFTY SERVICES SECTOR", "NIFTY ENERGY", "NIFTY HOUSING", "NIFTY INDIA DEFENCE", "NIFTY INDIA DIGITAL", "NIFTY INDIA MANUFACTURING", "NIFTY MOBILITY", "BSE SENSEX", "BSE 100", "BSE 200", "BSE 500"]
index_choice = st.sidebar.multiselect("Index Membership:", options=exhaustive_indices, default=st.session_state.get("f_indices", []), key="f_indices")
st.sidebar.markdown("---")
st.sidebar.header("2. Fundamental, Liquidity & IPO Date")
min_mcap_cr = st.sidebar.number_input("Min Market Cap (₹ Crores):", min_value=0, value=st.session_state.get("f_min_mcap", 1000), step=100, key="f_min_mcap")
vol_period_days = st.sidebar.selectbox("Average Volume Period:", options=[10, 30, 60, 90], index=[10, 30, 60, 90].index(st.session_state.get("f_vol_period", 60)), format_func=lambda x: f"{x} Days", key="f_vol_period")
min_vol_cr = st.sidebar.number_input(f"Min {vol_period_days}D Avg Rupee Volume (₹ Cr):", min_value=0.0, value=st.session_state.get("f_min_vol", 5.0), step=0.5, key="f_min_vol")
en_ipo = st.sidebar.checkbox("Filter by IPO Listing Age", value=st.session_state.get("f_en_ipo", False), key="f_en_ipo")
ipo_filter_options = ["All Stocks (No IPO Filter)", "Recent IPO: Past 1 Month", "Recent IPO: Past 3 Months", "Recent IPO: Past 6 Months", "Recent IPO: Past 1 Year", "Recent IPO: Past 2 Years", "Seasoned: Listed > 1 Year Ago", "Seasoned: Listed > 3 Years Ago", "Seasoned: Listed > 5 Years Ago"]
ipo_filter_choice = st.sidebar.selectbox("IPO Date / Age Filter:", options=ipo_filter_options, index=ipo_filter_options.index(st.session_state.get("f_ipo", "All Stocks (No IPO Filter)")), key="f_ipo", disabled=not en_ipo)
st.sidebar.markdown("---")
st.sidebar.header("2B. Quarterly YoY Fundamental Growth")
en_eps_q = st.sidebar.checkbox("Filter by Min Quarterly YoY EPS Growth %", value=st.session_state.get("f_en_eps_q", False), key="f_en_eps_q")
min_eps_q = st.sidebar.slider("Min Quarterly YoY EPS Growth %:", min_value=-50.0, max_value=200.0, value=float(st.session_state.get("f_min_eps_q", 10.0)), step=5.0, key="f_min_eps_q", disabled=not en_eps_q)
en_sales_q = st.sidebar.checkbox("Filter by Min Quarterly YoY Sales Growth %", value=st.session_state.get("f_en_sales_q", False), key="f_en_sales_q")
min_sales_q = st.sidebar.slider("Min Quarterly YoY Sales Growth %:", min_value=-50.0, max_value=200.0, value=float(st.session_state.get("f_min_sales_q", 10.0)), step=5.0, key="f_min_sales_q", disabled=not en_sales_q)
allow_na_growth = st.sidebar.checkbox("Pass stocks with missing (N/A) TradingView growth data", value=st.session_state.get("f_allow_na_growth", True), key="f_allow_na_growth")
st.sidebar.markdown("---")
st.sidebar.header("3. Trend & Moving Averages (5 MAs)")
default_ma_configs = [{"en": True, "type": "EMA", "len": 21}, {"en": True, "type": "SMA", "len": 50}, {"en": False, "type": "SMA", "len": 200}, {"en": False, "type": "EMA", "len": 10}, {"en": False, "type": "SMA", "len": 150}]
ma_filters = []
for i, cfg in enumerate(default_ma_configs, 1):
  c1, c2, c3 = st.sidebar.columns([1.8, 1.6, 1.6])
  with c1: en = st.checkbox(f"MA {i} >", value=st.session_state.get(f"ma_{i}_en", cfg["en"]), key=f"ma_{i}_en")
  with c2: m_type = st.selectbox("Type", ["EMA", "SMA"], index=0 if st.session_state.get(f"ma_{i}_type", cfg["type"]) == "EMA" else 1, key=f"ma_{i}_type", label_visibility="collapsed")
  with c3: m_len = st.number_input("Len", min_value=1, max_value=500, value=st.session_state.get(f"ma_{i}_len", cfg["len"]), step=1, key=f"ma_{i}_len", label_visibility="collapsed")
  ma_filters.append({"enabled": en, "type": m_type, "length": m_len, "col_name": f"{m_type}{m_len}", "label": f"{m_type} {m_len}"})
st.sidebar.markdown("---")
st.sidebar.header("4. Volatility & 52-Week Range")
en_adr = st.sidebar.checkbox("Filter by Min ADR %", value=st.session_state.get("f_en_adr", True), key="f_en_adr")
min_adr = st.sidebar.slider("Min ADR %:", min_value=0.0, max_value=10.0, value=st.session_state.get("f_min_adr", 2.25), step=0.25, key="f_min_adr", disabled=not en_adr)
en_52l = st.sidebar.checkbox("Filter by Min % Above 52-Week Low", value=st.session_state.get("f_en_52l", True), key="f_en_52l")
min_above_52l = st.sidebar.slider("Min % Above 52-Week Low:", min_value=0, max_value=100, value=st.session_state.get("f_min_52l", 20), step=5, key="f_min_52l", disabled=not en_52l)
en_52h = st.sidebar.checkbox("Filter by Max % Below 52-Week High", value=st.session_state.get("f_en_52h", True), key="f_en_52h")
max_below_52h = st.sidebar.slider("Max % Below 52-Week High:", min_value=0, max_value=50, value=st.session_state.get("f_max_52h", 30), step=5, key="f_max_52h", disabled=not en_52h)
st.sidebar.markdown("---")
st.sidebar.header("4B. Circuit Limit Protection")
c_cb, c_sb = st.sidebar.columns([1.1, 1.4])
with c_cb: en_circuit = st.checkbox("Exclude Circuit:", value=st.session_state.get("f_en_circuit", True), key="f_en_circuit")
with c_sb: circuit_choice = st.multiselect("Bands:", options=["2%", "5%", "10%"], default=st.session_state.get("f_circuit_val", ["2%", "5%", "10%"]), key="f_circuit_val", disabled=not en_circuit, label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.header("5. Performance % & IBD RS Rating")
en_rs_rating = st.sidebar.checkbox("Filter by Min IBD RS Rating (1-99)", value=st.session_state.get("f_en_rs_rating", True), key="f_en_rs_rating")
min_rs_rating = st.sidebar.slider("Min IBD RS Rating:", min_value=1, max_value=99, value=st.session_state.get("f_min_rs_rating", 80), step=1, key="f_min_rs_rating", disabled=not en_rs_rating)
perf_options = {"1 Week": ("Perf.W", "Perf % 1W"), "1 Month": ("Perf.1M", "Perf % 1M"), "3 Months": ("Perf.3M", "Perf % 3M"), "6 Months": ("Perf.6M", "Perf % 6M"), "YTD": ("Perf.YTD", "Perf % YTD"), "1 Year": ("Perf.Y", "Perf % 1Y")}
selected_perf_labels = st.sidebar.multiselect("Display Perf % Columns:", options=list(perf_options.keys()), default=st.session_state.get("f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]), key="f_perf_labels")
perf_filters = []
p_cols = st.sidebar.columns(2)
for idx, (label, (tv_col, disp_label)) in enumerate(perf_options.items()):
  with p_cols[idx % 2]:
    en_p = st.checkbox(f"Min {label} >", value=st.session_state.get(f"en_perf_{tv_col}", False), key=f"en_perf_{tv_col}")
    min_val = st.number_input(f"Min % ({label})", min_value=-100.0, max_value=10000.0, value=st.session_state.get(f"val_perf_{tv_col}", 0.0), step=5.0, key=f"val_perf_{tv_col}", label_visibility="collapsed")
    perf_filters.append({"enabled": en_p, "label": label, "col_name": tv_col, "display_label": disp_label, "min_val": min_val})
st.sidebar.markdown("---")
st.sidebar.header("6. Display Settings")
max_results = st.sidebar.slider("Max Results to Fetch:", min_value=1000, max_value=5000, value=st.session_state.get("f_max_res", 4000), step=250, key="f_max_res")

# ==========================================
# WORKSPACE TABS
# ==========================================
tab_screener, tab_watchlists, tab_tradebook, tab_market_health = st.tabs([
    "🔎 CAN SLIM Screener & Rotation",
    "⭐ Multi-Watchlist Studio",
    "📓 Tradebook & Portfolio Journal",
    "🏥 Market Health & Sector Rotation",
])

with tab_screener:
  ma_cols_to_fetch = list(set([m["col_name"] for m in ma_filters]))
  tv_vol_col = f"average_volume_{vol_period_days}d_calc"
  with st.spinner("⚡ Scanning Indian Equities & Applying Active Filters..."):
    results_df = fetch_screener_data(exchange_choice, min_mcap_cr, vol_period_days, ma_cols_to_fetch, max_results)
    nse_bands_map = get_nse_circuit_bands()
    if not results_df.empty:
      p_3m = pd.to_numeric(results_df.get("Perf.3M"), errors="coerce").fillna(0)
      p_6m = pd.to_numeric(results_df.get("Perf.6M"), errors="coerce").fillna(0)
      p_1y = pd.to_numeric(results_df.get("Perf.Y"), errors="coerce").fillna(0)
      results_df["_ibd_raw_score"] = (2 * p_3m) + p_6m + p_1y
      rs_pct = results_df["_ibd_raw_score"].rank(pct=True, na_option="keep")
      results_df["RS Rating"] = ((rs_pct * 98 + 1).round().fillna(1).astype(int))
      st.session_state.rs_rating_map = dict(zip(results_df["name"].str.upper(), results_df["RS Rating"]))

  if results_df.empty: st.warning("No stocks matched your criteria.")
  else:
    df = results_df.copy()
    df = df[df["exchange"].isin(exchange_choice)]
    if "type" in df.columns: df = df[df["type"] == "stock"]
    df = df.drop_duplicates(subset=["name"], keep="first")

    mapped_sectors, mapped_industries = [], []
    for _, row in df.iterrows():
      sec, ind = map_to_indian_classification(row.get("industry", ""), row.get("sector", ""))
      mapped_sectors.append(sec)
      mapped_industries.append(ind)
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries

    total_sector_counts = df["Sector"].value_counts()
    total_industry_counts = df["Industry"].value_counts()

    if sector_choice: df = df[df["Sector"].isin(sector_choice)]
    if industry_choice: df = df[df["Industry"].isin(industry_choice)]
    if "index" in df.columns: df["Index"] = df["index"].fillna("N/A")
    else: df["Index"] = "N/A"
    if index_choice:
      def matches_index(val):
        if pd.isna(val) or val == "N/A" or not val: return False
        val_str = str(val).upper()
        for idx_name in index_choice:
          if idx_name.upper() in val_str: return True
        return False
      df = df[df["Index"].apply(matches_index)]

    df["EPS Q YoY %"] = coalesce_columns(df, EPS_Q_ALIASES).round(2)
    df["Sales Q YoY %"] = coalesce_columns(df, SALES_Q_ALIASES).round(2)

    if en_eps_q: df = df[(df["EPS Q YoY %"] >= min_eps_q) | (df["EPS Q YoY %"].isna())] if allow_na_growth else df[df["EPS Q YoY %"] >= min_eps_q]
    if en_sales_q: df = df[(df["Sales Q YoY %"] >= min_sales_q) | (df["Sales Q YoY %"].isna())] if allow_na_growth else df[df["Sales Q YoY %"] >= min_sales_q]
    if en_rs_rating and "RS Rating" in df.columns: df = df[df["RS Rating"] >= min_rs_rating]

    df = add_clean_ipo_date_col(df)
    if en_ipo and ipo_filter_choice != "All Stocks (No IPO Filter)":
      now_dt = pd.Timestamp.now()
      if "Recent IPO" in ipo_filter_choice:
        months = 1 if "1 Month" in ipo_filter_choice else 3 if "3 Months" in ipo_filter_choice else 6 if "6 Months" in ipo_filter_choice else 12 if "1 Year" in ipo_filter_choice else 24
        df = df[df["IPO_Date_DT"] >= (now_dt - pd.DateOffset(months=months))]
      else:
        years = 1 if "1 Year" in ipo_filter_choice else 3 if "3 Years" in ipo_filter_choice else 5
        df = df[(df["IPO_Date_DT"] < (now_dt - pd.DateOffset(years=years))) | (df["IPO Date"] == "N/A")]

    for c in ["market_cap_basic", "close", "change", "high", "low", "open", "volume", tv_vol_col, "ADR", "price_52_week_high", "price_52_week_low"] + ma_cols_to_fetch:
      if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")

    df["ADR_pct"] = (df["ADR"] / df["close"]) * 100
    if en_adr: df = df[df["ADR_pct"] >= min_adr]
    for ma in ma_filters:
      c_name = ma["col_name"]
      if ma["enabled"] and c_name in df.columns:
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df[c_name] = pd.to_numeric(df[c_name], errors="coerce")
        df = df[df["close"] > df[c_name]]

    if tv_vol_col in df.columns:
      df["val_traded_inr"] = df["close"] * df[tv_vol_col]
      df = df[df["val_traded_inr"] >= (min_vol_cr * 10_000_000)]

    if "price_52_week_low" in df.columns:
      if en_52l: df = df[(((df["close"] - df["price_52_week_low"]) / df["price_52_week_low"]) * 100) >= min_above_52l]
    if "price_52_week_high" in df.columns:
      if en_52h: df = df[(((df["price_52_week_high"] - df["close"]) / df["price_52_week_high"]) * 100) <= max_below_52h]

    for pf in perf_filters:
      if pf["enabled"] and pf["col_name"] in df.columns:
        df[pf["col_name"]] = pd.to_numeric(df[pf["col_name"]], errors="coerce")
        df = df[df[pf["col_name"]] >= pf["min_val"]]

    if en_circuit and circuit_choice:
      df["change_abs"] = df["change"].abs()
      is_full_day_freeze = df["high"] == df["low"]
      bands = [b.replace("%", "") for b in circuit_choice]
      def is_circuit_hit(row):
        sym = str(row["name"]).strip().upper()
        band_val = nse_bands_map.get(sym, "")
        if band_val in bands: return True
        c_abs = row["change_abs"]
        is_locked = row["high"] == row["low"] or ((row["close"] == row["high"] or row["close"] == row["low"]) and row["high"] != row["open"])
        if is_locked:
          if "2" in bands and 1.97 <= c_abs <= 2.00: return True
          if "5" in bands and 4.97 <= c_abs <= 5.00: return True
          if "10" in bands and 9.97 <= c_abs <= 10.00: return True
        return False
      df["_is_circuit_excluded"] = df.apply(is_circuit_hit, axis=1)
      df = df[~df["_is_circuit_excluded"] & ~is_full_day_freeze].drop(columns=["_is_circuit_excluded"])

    if df.empty: st.warning("No stocks passed all criteria.")
    else:
      total_passed = len(df)
      rc = st.session_state.reset_counter

      st.subheader("📊 Scan Summary & Market Rotation")
      tab_sector_sum, tab_industry_sum = st.tabs(["🛠️ Sector Summary", "🏢 Basic Industry Summary"])
      with tab_sector_sum:
        sec_counts = df["Sector"].value_counts().reset_index()
        sec_counts.columns = ["Sector", "Stocks Passed"]
        sec_counts["% Share"] = ((sec_counts["Stocks Passed"] / total_passed) * 100).round(1)
        sec_counts["% of Sector Total"] = sec_counts.apply(lambda r: round((r["Stocks Passed"] / total_sector_counts.get(r["Sector"], 1)) * 100, 1), axis=1)
        c_chart1, c_table1 = st.columns([1.1, 1.3])
        with c_chart1:
          fig_sec = px.pie(sec_counts, names="Sector", values="Stocks Passed", hole=0.55)
          fig_sec.update_traces(textinfo="percent", textposition="inside")
          fig_sec.update_layout(annotations=[dict(text=f"<b>Total Stocks:<br>{total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)], showlegend=False, margin=dict(t=20, b=10, l=20, r=20), height=360)
          chart_ev_sec = st.plotly_chart(fig_sec, use_container_width=True, on_select="rerun", selection_mode="points", key=f"sec_chart_{rc}")
        with c_table1:
          table_ev_sec = st.dataframe(sec_counts, use_container_width=True, hide_index=True, height=360, on_select="rerun", selection_mode="multi-row", column_config=get_left_aligned_column_config(sec_counts.columns), key=f"sec_table_{rc}")
        sel_sec_chart = parse_chart_selection_multi(chart_ev_sec)
        sel_sec_table = parse_table_selection_multi(table_ev_sec, sec_counts, "Sector")
        active_sectors = sel_sec_table if sel_sec_table else sel_sec_chart

      with tab_industry_sum:
        df_ind_source = df[df["Sector"].isin(active_sectors)] if active_sectors else df
        ind_total_passed = len(df_ind_source)
        ind_counts = df_ind_source["Industry"].value_counts().reset_index()
        ind_counts.columns = ["Basic Industry", "Stocks Passed"]
        ind_counts["% Share"] = ((ind_counts["Stocks Passed"] / max(ind_total_passed, 1)) * 100).round(1)
        ind_counts["% of Industry Total"] = ind_counts.apply(lambda r: round((r["Stocks Passed"] / total_industry_counts.get(r["Basic Industry"], 1)) * 100, 1), axis=1)
        sec_hash = "_".join(sorted(active_sectors)) if active_sectors else "all"
        c_chart2, c_table2 = st.columns([1.1, 1.3])
        with c_chart2:
          fig_ind = px.pie(ind_counts, names="Basic Industry", values="Stocks Passed", hole=0.55)
          fig_ind.update_traces(textinfo="percent", textposition="inside")
          fig_ind.update_layout(annotations=[dict(text=f"<b>Total Stocks:<br>{ind_total_passed}</b>", x=0.5, y=0.5, font_size=16, showarrow=False)], showlegend=False, margin=dict(t=20, b=10, l=20, r=20), height=360)
          chart_ev_ind = st.plotly_chart(fig_ind, use_container_width=True, on_select="rerun", selection_mode="points", key=f"ind_chart_{rc}_{sec_hash}")
        with c_table2:
          table_ev_ind = st.dataframe(ind_counts, use_container_width=True, hide_index=True, height=360, on_select="rerun", selection_mode="multi-row", column_config=get_left_aligned_column_config(ind_counts.columns), key=f"ind_table_{rc}_{sec_hash}")
        sel_ind_chart = parse_chart_selection_multi(chart_ev_ind)
        sel_ind_table = parse_table_selection_multi(table_ev_ind, ind_counts, "Basic Industry")
        active_industries = sel_ind_table if sel_ind_table else sel_ind_chart

      st.session_state.active_scan_summary = {"total_passed": total_passed, "sectors": sec_counts.head(10).to_dict(orient="records"), "industries": ind_counts.head(10).to_dict(orient="records")}

      st.markdown("---")
      df_display = df.copy()
      if active_sectors: df_display = df_display[df_display["Sector"].isin(active_sectors)]
      if active_industries: df_display = df_display[df_display["Industry"].isin(active_industries)]
      if active_sectors or active_industries:
        filter_labels = []
        if active_sectors: filter_labels.append(f"**Sector:** {', '.join(active_sectors)}")
        if active_industries: filter_labels.append(f"**Industry:** {', '.join(active_industries)}")
        col_info, col_reset = st.columns([3, 1])
        with col_info: st.info(f"🔍 **Active Drilldown:** {' | '.join(filter_labels)} ({len(df_display)} Stocks)")
        with col_reset:
          if st.button("🔄 Reset Scan Results (Show All)", type="primary", use_container_width=True):
            st.session_state.reset_counter += 1
            st.rerun()

      df_display["S.No._num"] = range(1, len(df_display) + 1)
      df_display["Market Cap (₹ Cr)"] = (df_display["market_cap_basic"] / 10_000_000).round(2)
      vol_display_label = f"{vol_period_days}D Close×AvgVol (₹ Cr)"
      df_display[vol_display_label] = (df_display["val_traded_inr"] / 10_000_000).round(2)
      df_display["Close"] = df_display["close"].round(2)
      df_display["Change %"] = df_display["change"].round(2)
      df_display["ADR %"] = df_display["ADR_pct"].round(2)
      df_display["TV_Symbol"] = df_display["exchange"] + ":" + df_display["name"]
      df_display["TV_Link"] = "https://www.tradingview.com/chart/?symbol=NSE:" + df_display["name"]
      df_display["Screener_Link"] = "https://www.screener.in/company/" + df_display["name"] + "/consolidated/"

      wl_dot_map = {}
      for wl_name, sym_list in st.session_state.watchlists.items():
        dot = "🔵" if "breakout" in wl_name.lower() else "🟢" if "focus" in wl_name.lower() else "🟡" if "weekly" in wl_name.lower() else "🟠" if "bulk" in wl_name.lower() else "🔴" if "sold" in wl_name.lower() else "🟣"
        for s in sym_list:
          bare_s = s.split(":")[-1].strip().upper()
          wl_dot_map[bare_s] = wl_dot_map.get(bare_s, "") + dot
      df_display["WL_Dots"] = df_display["name"].str.upper().map(wl_dot_map).fillna("")
      df_display["S.No."] = df_display.apply(lambda r: f"{r['S.No._num']} {r['WL_Dots']}".strip() if r["WL_Dots"] else str(r["S.No._num"]), axis=1)

      df_display["_in_band"] = df_display["name"].str.upper().map(nse_bands_map)
      cond1 = df_display["_in_band"].isin(["2", "5", "10"])
      cond2 = ((df_display["high"] == df_display["low"]) & (df_display["high"] > 0) & (df_display["change"].abs() > 1.5))
      df_display["_is_circuit_badge"] = cond1 | cond2
      df_display["name"] = df_display["name"].where(~df_display["_is_circuit_badge"], df_display["name"] + " 🚨")

      rs_map = st.session_state.get("rs_rating_map", {})
      df_display["RS Rating"] = df_display["name"].str.replace(" 🚨", "").str.upper().map(rs_map).fillna("N/A")
      fund_badge_map = {k: f"{v.get('verdict')} ({v.get('date', '')})" for k, v in st.session_state.fundamental_reports.items()}
      df_display["Fundamental"] = df_display["name"].str.replace(" 🚨", "").str.upper().map(fund_badge_map).fillna("⚪ Not Analyzed")

      for label, (tv_col, disp_label) in perf_options.items():
        if tv_col in df_display.columns: df_display[disp_label] = pd.to_numeric(df_display[tv_col], errors="coerce").round(2)
      active_perf_labels = [p for p in ["Perf % 1W", "Perf % 1M", "Perf % 3M", "Perf % 6M", "Perf % YTD", "Perf % 1Y"] if p in [perf_options[lbl][1] for lbl in selected_perf_labels] and p in df_display.columns]

      active_ma_labels = []
      for ma in ma_filters:
        if ma["enabled"] and ma["col_name"] in df_display.columns:
          df_display[ma["label"]] = df_display[ma["col_name"]].round(2)
          active_ma_labels.append(ma["label"])

      table_columns = ["S.No.", "TV_Symbol", "name", "RS Rating", "Fundamental", "Close", "Change %", "ADR %", "EPS Q YoY %", "Sales Q YoY %"] + active_perf_labels + active_ma_labels + [vol_display_label, "Market Cap (₹ Cr)", "IPO Date", "Sector", "Industry", "TV_Link", "Screener_Link"]

      st.subheader(f"📋 Scan Results ({len(df_display)} Stocks Found)")
      st.caption("💡 **RS Rating:** IBD-Style 1-99 Percentile Score calculated across 4,000+ listed Indian equities before filters.")
      sc = st.session_state.scan_sel_counter
      table_ev_scan = st.dataframe(df_display[table_columns], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="multi-row", column_config=get_left_aligned_column_config(table_columns), key=f"scan_table_{rc}_{sc}")
      selected_rows = parse_table_selection_multi(table_ev_scan, df_display, "TV_Symbol")

      st.markdown("---")
      f_col1, f_col2, f_col3 = st.columns([2.0, 1.3, 1.7])
      with f_col1:
        if len(selected_rows) == 1:
          if st.button(f"📖 Open Saved Report Modal ({selected_rows[0].split(':')[-1].strip().upper()})", type="primary", use_container_width=True, key=f"fund_btn_view_scan_{rc}_{sc}"): show_fundamental_modal(selected_rows[0])
        else:
          st.button("📖 Select a Single Stock Row to Open Report", type="secondary", disabled=True, use_container_width=True, key=f"fund_btn_view_scan_dis_{rc}_{sc}")
      with f_col2: force_reanalyze_scan = st.checkbox("Force Re-Analyze Existing", value=False, key=f"force_scan_{rc}_{sc}")
      with f_col3: run_batch_scan = st.button(f"⚡ Analyze Selected ({len(selected_rows)})", type="primary", use_container_width=True, disabled=len(selected_rows) == 0, key=f"fund_btn_run_scan_{rc}_{sc}")

      if run_batch_scan and len(selected_rows) > 0:
        with st.status("🧠 Minervini Fundamental AI Analyst — Active Queue", expanded=True) as status_box:
          p_bar = st.progress(0.0)
          for idx, sym in enumerate(selected_rows):
            clean_sym = sym.split(":")[-1].strip().upper()
            if clean_sym in st.session_state.fundamental_reports and not force_reanalyze_scan: status_box.write(f"⏩ **[{idx+1}/{len(selected_rows)}] {clean_sym}:** Report exists.")
            else:
              status_box.write(f"⚙️ **[{idx+1}/{len(selected_rows)}] {clean_sym}:** Running AI Analyst...")
              run_gemini_fundamental_analysis(clean_sym, st.session_state.fundamental_reports, status_box)
            p_bar.progress((idx + 1) / len(selected_rows))
          status_box.update(label="✅ Batch AI Analysis Complete!", state="complete", expanded=True)
          time.sleep(1.5)
          st.rerun()

      st.markdown("---")
      cw1, cw2, cw3, cw4 = st.columns([1.8, 1.5, 2.0, 0.9])
      with cw1:
        wl_keys = list(st.session_state.watchlists.keys())
        target_wl = st.selectbox("Select Target Watchlist to Add Setups:", options=wl_keys, index=wl_keys.index(st.session_state.active_watchlist_name) if st.session_state.active_watchlist_name in wl_keys else 0, key="wl_table_target_select")
      with cw2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"➕ Add Selected ({len(selected_rows)}) to Watchlist", type="primary", use_container_width=True, disabled=len(selected_rows) == 0):
          added_cnt = 0
          for sym in selected_rows:
            if sym not in st.session_state.watchlists[target_wl]:
              st.session_state.watchlists[target_wl].append(sym)
              added_cnt += 1
          save_watchlists(st.session_state.watchlists)
          st.success(f"✅ Successfully added {added_cnt} new stocks to **{target_wl}**!")
      with cw3:
        st.caption("➕ Create New Watchlist:")
        with st.form("create_wl_scan_form", clear_on_submit=True):
          fc1, fc2 = st.columns([1.7, 1.0])
          with fc1: new_scan_wl = st.text_input("Create New Watchlist", placeholder="e.g., Telecom Breakout", label_visibility="collapsed")
          with fc2:
            if st.form_submit_button("➕ Create", use_container_width=True) and new_scan_wl and new_scan_wl not in st.session_state.watchlists:
              st.session_state.watchlists[new_scan_wl] = []
              st.session_state.active_watchlist_name = new_scan_wl
              save_watchlists(st.session_state.watchlists)
              st.success(f"Created '{new_scan_wl}'!")
              st.rerun()

      filtered_symbols = df_display["TV_Symbol"].tolist()
      st.markdown("---")
      if filtered_symbols:
        st.subheader(f"📋 Copy Filtered Scan Results to TradingView ({len(filtered_symbols)} Stocks)")
        batch_size = 30
        batches = [filtered_symbols[i : i + batch_size] for i in range(0, len(filtered_symbols), batch_size)]
        if len(batches) > 1:
          batch_labels = [f"Batch {idx+1} ({idx*batch_size+1}–{idx*batch_size+len(b)})" for idx, b in enumerate(batches)]
          selected_batch_label = st.selectbox("Select 30-Symbol Batch to Copy:", options=batch_labels, key=f"scan_batch_dropdown_{rc}_{sc}")
          st.code(", ".join(batches[batch_labels.index(selected_batch_label)]), language="text")
        with st.expander("📋 View / Copy All Tickers", expanded=False): st.code(", ".join(filtered_symbols), language="text")

with tab_watchlists:
  st.subheader("⭐ Multi-Watchlist Studio (Bypasses TV Free Tier 30-Symbol Cap)")
  col_sel, col_new, col_del = st.columns([2.4, 1.8, 0.8])
  with col_sel:
    wl_names = list(st.session_state.watchlists.keys())
    active_wl = st.selectbox("Select Active Watchlist:", options=wl_names, index=wl_names.index(st.session_state.active_watchlist_name) if st.session_state.active_watchlist_name in wl_names else 0, key="wl_active_selector")
    st.session_state.active_watchlist_name = active_wl
    with st.form("inline_rename_form", clear_on_submit=True):
      r_col1, r_col2 = st.columns([2.6, 1.0])
      with r_col1: new_inline_name = st.text_input("✏️ Rename Selected Watchlist:", value=active_wl, label_visibility="collapsed")
      with r_col2:
        if st.form_submit_button("✏️ Rename", use_container_width=True) and new_inline_name and new_inline_name != active_wl and new_inline_name not in st.session_state.watchlists:
          st.session_state.watchlists[new_inline_name] = st.session_state.watchlists.pop(active_wl)
          st.session_state.active_watchlist_name = new_inline_name
          save_watchlists(st.session_state.watchlists)
          st.rerun()
  with col_new:
    with st.form("create_wl_form", clear_on_submit=True):
      new_wl_name = st.text_input("Create New Watchlist:", placeholder="e.g., Sector: Capital Goods Build")
      if st.form_submit_button("➕ Create Watchlist", use_container_width=True) and new_wl_name and new_wl_name not in st.session_state.watchlists:
        st.session_state.watchlists[new_wl_name] = []
        st.session_state.active_watchlist_name = new_wl_name
        save_watchlists(st.session_state.watchlists)
        st.rerun()
  with col_del:
    st.markdown("<br>", unsafe_allow_html=True)
    if len(wl_names) > 1 and st.button("🗑️ Delete", type="secondary", use_container_width=True):
      del st.session_state.watchlists[active_wl]
      save_watchlists(st.session_state.watchlists)
      st.session_state.active_watchlist_name = list(st.session_state.watchlists.keys())[0]
      st.rerun()

  current_symbols = st.session_state.watchlists[active_wl]

  with st.expander("📥 Import / Paste Tickers & Backup Local Text (.TXT) Library", expanded=False):
    ci1, ci2 = st.columns([2, 1])
    with ci1:
      pasted_text = st.text_area("Paste Tickers from TradingView:", placeholder="NSE:RELIANCE, BSE:TCS")
      if st.button("➕ Import Tickers into Current Watchlist", type="primary"):
        for s in parse_pasted_tickers(pasted_text):
          if s not in st.session_state.watchlists[active_wl]: st.session_state.watchlists[active_wl].append(s)
        save_watchlists(st.session_state.watchlists)
        st.rerun()
    with ci2:
      st.download_button(label="📥 Download Watchlists (.TXT)", data=json.dumps(st.session_state.watchlists, indent=2), file_name="my_india_watchlists.txt", mime="text/plain", use_container_width=True)
      uploaded_file = st.file_uploader("Restore Watchlists (.TXT):", type=["txt", "json"], label_visibility="collapsed")
      if uploaded_file is not None:
        try:
          st.session_state.watchlists = json.load(uploaded_file)
          st.session_state.active_watchlist_name = list(st.session_state.watchlists.keys())[0]
          save_watchlists(st.session_state.watchlists)
          st.rerun()
        except Exception: st.error("Invalid file format.")

  if not current_symbols: st.info(f"The watchlist **{active_wl}** is empty.")
  else:
    rm_col1, rm_col2, rm_col3, rm_col4, rm_col5, rm_col6, rm_col7 = st.columns([2.0, 0.8, 0.8, 0.8, 0.8, 1.1, 0.8])
    with rm_col1: move_target_sym = st.selectbox("Select Ticker to Move:", options=current_symbols, key=f"rapid_mover_sym_{active_wl}", label_visibility="collapsed")
    with rm_col2: st.button("🔝 Top", on_click=cb_move_top, args=(active_wl, move_target_sym), use_container_width=True)
    with rm_col3: st.button("⬆️ Up", on_click=cb_move_up, args=(active_wl, move_target_sym), use_container_width=True)
    with rm_col4: st.button("⬇️ Down", on_click=cb_move_down, args=(active_wl, move_target_sym), use_container_width=True)
    with rm_col5: st.button("🔻 Bottom", on_click=cb_move_bottom, args=(active_wl, move_target_sym), use_container_width=True)
    with rm_col6: target_rank = st.number_input("Rank #", min_value=1, max_value=len(current_symbols), value=1, step=1, key=f"rapid_mover_rank_{active_wl}", label_visibility="collapsed")
    with rm_col7: st.button("🎯 Jump", type="primary", on_click=cb_jump_rank, args=(active_wl, move_target_sym, target_rank), use_container_width=True)

    with st.spinner(f"📡 Enriching {len(current_symbols)} Tickers..."):
      enriched_df = fetch_watchlist_enrichMENT(current_symbols)

    ordered_df = pd.DataFrame({"TV_Symbol": current_symbols, "name": [s.split(":")[-1].strip().upper() for s in current_symbols]})
    merged_df = ordered_df.merge(enriched_df, on="name", how="left", suffixes=("", "_tv")) if not enriched_df.empty else ordered_df.copy()
    if "TV_Symbol_tv" in merged_df.columns: merged_df["TV_Symbol"] = merged_df["TV_Symbol_tv"].fillna(merged_df["TV_Symbol"])
    for col_name in ["Close", "Change %", "ADR_pct", "EPS Q YoY %", "Sales Q YoY %", "Perf % 1W", "Perf % 1M", "Perf % 3M", "Perf % 6M", "Market Cap (₹ Cr)", "IPO Date", "Sector", "Industry"]:
      merged_df[col_name] = merged_df.get(col_name, pd.Series()).fillna("N/A")

    merged_df["S.No._num"] = range(1, len(merged_df) + 1)
    merged_df["TV_Link"] = "https://www.tradingview.com/chart/?symbol=" + merged_df["TV_Symbol"]
    merged_df["Screener_Link"] = "https://www.screener.in/company/" + merged_df["name"] + "/consolidated/"

    wl_dot_map_wl = {}
    for wl_name, sym_list in st.session_state.watchlists.items():
      dot = "🔵" if "breakout" in wl_name.lower() else "🟢" if "focus" in wl_name.lower() else "🟡" if "weekly" in wl_name.lower() else "🟠" if "bulk" in wl_name.lower() else "🔴" if "sold" in wl_name.lower() else "🟣"
      for s in sym_list: wl_dot_map_wl[s.split(":")[-1].strip().upper()] = wl_dot_map_wl.get(s.split(":")[-1].strip().upper(), "") + dot
    merged_df["WL_Dots"] = merged_df["name"].str.upper().map(wl_dot_map_wl).fillna("")
    merged_df["S.No."] = merged_df.apply(lambda r: f"{r['S.No._num']} {r['WL_Dots']}".strip() if r["WL_Dots"] else str(r["S.No._num"]), axis=1)

    nse_bands_map = get_nse_circuit_bands()
    merged_df["_is_circuit_badge"] = merged_df.apply(lambda r: is_circuit_stock_badge(r, nse_bands_map), axis=1)
    merged_df["name"] = merged_df["name"].where(~merged_df["_is_circuit_badge"], merged_df["name"] + " 🚨")
    merged_df["RS Rating"] = merged_df["name"].str.replace(" 🚨", "").str.upper().map(st.session_state.get("rs_rating_map", {})).fillna("N/A")
    merged_df["Fundamental"] = merged_df["name"].str.replace(" 🚨", "").str.upper().map({k: f"{v.get('verdict')} ({v.get('date', '')})" for k, v in st.session_state.fundamental_reports.items()}).fillna("⚪ Not Analyzed")

    wl_cols = ["S.No.", "TV_Symbol", "name", "RS Rating", "Fundamental", "Close", "Change %", "ADR %", "EPS Q YoY %", "Sales Q YoY %", "Perf % 1W", "Perf % 1M", "Perf % 3M", "Perf % 6M", "Market Cap (₹ Cr)", "IPO Date", "Sector", "Industry", "TV_Link", "Screener_Link"]
    st.markdown(f"### ⭐ Watchlist: **{active_wl}** ({len(current_symbols)} Stocks)")
    wsc = st.session_state.wl_sel_counter
    wl_table_event = st.dataframe(merged_df[wl_cols], use_container_width=True, hide_index=True, height=460, on_select="rerun", selection_mode="multi-row", column_config=get_left_aligned_column_config(wl_cols), key=f"wl_manage_table_{wsc}")
    sel_symbols = parse_table_selection_multi(wl_table_event, merged_df, "TV_Symbol")

    st.markdown("---")
    wf_col1, wf_col2, wf_col3 = st.columns([2.0, 1.3, 1.7])
    with wf_col1:
      if len(sel_symbols) == 1:
        if st.button(f"📖 Open Saved Report Modal ({sel_symbols[0].split(':')[-1].strip().upper()})", type="primary", use_container_width=True, key=f"fund_btn_view_wl_{wsc}"): show_fundamental_modal(sel_symbols[0])
      else: st.button("📖 Select a Single Stock Row to Open Report", type="secondary", disabled=True, use_container_width=True, key=f"fund_btn_view_wl_dis_{wsc}")
    with wf_col2: force_reanalyze_wl = st.checkbox("Force Re-Analyze Existing", value=False, key=f"force_wl_{wsc}")
    with wf_col3: run_batch_wl = st.button(f"⚡ Analyze Selected ({len(sel_symbols)})", type="primary", use_container_width=True, disabled=len(sel_symbols) == 0, key=f"fund_btn_run_wl_{wsc}")
    
    if run_batch_wl and len(sel_symbols) > 0:
      with st.status("🧠 Minervini Fundamental AI Analyst — Active Queue", expanded=True) as status_box_wl:
        for idx, sym in enumerate(sel_symbols):
          clean_sym = sym.split(":")[-1].strip().upper()
          if clean_sym in st.session_state.fundamental_reports and not force_reanalyze_wl: status_box_wl.write(f"⏩ **[{idx+1}/{len(sel_symbols)}] {clean_sym}:** Report exists.")
          else:
            status_box_wl.write(f"⚙️ **[{idx+1}/{len(sel_symbols)}] {clean_sym}:** Running AI Analyst...")
            run_gemini_fundamental_analysis(clean_sym, st.session_state.fundamental_reports, status_box_wl)
        status_box_wl.update(label="✅ Batch AI Analysis Complete!", state="complete", expanded=True)
        time.sleep(1.5)
        st.rerun()

    c_rem, c_clr, c_promo_sel, c_promo_btn = st.columns([1.5, 1.2, 2.0, 1.5])
    with c_rem:
      if st.button(f"🗑️ Remove Selected ({len(sel_symbols)})", type="secondary", use_container_width=True, disabled=len(sel_symbols) == 0):
        for sym in sel_symbols:
          if sym in st.session_state.watchlists[active_wl]: st.session_state.watchlists[active_wl].remove(sym)
        save_watchlists(st.session_state.watchlists)
        st.rerun()
    with c_clr:
      if st.button("🧹 Clear Selection", type="secondary", use_container_width=True, disabled=len(sel_symbols) == 0, key="clear_wl_sel_btn"):
        st.session_state.wl_sel_counter += 1
        st.rerun()
    with c_promo_sel: promo_target = st.selectbox("Promote Selected To Target Watchlist:", options=[name for name in wl_names if name != active_wl] if len(wl_names) > 1 else wl_names, key="promo_target_select", label_visibility="collapsed")
    with c_promo_btn:
      if st.button(f"➡️ Promote Selected ({len(sel_symbols)})", type="primary", use_container_width=True, disabled=len(sel_symbols) == 0):
        for sym in sel_symbols:
          if sym not in st.session_state.watchlists[promo_target]: st.session_state.watchlists[promo_target].append(sym)
        save_watchlists(st.session_state.watchlists)
        st.rerun()

    if len(current_symbols) > 30:
      st.markdown("---")
      st.subheader("#### ⚡ 30-Symbol TradingView Hot-Swap Batches")
      batches = [current_symbols[i : i + 30] for i in range(0, len(current_symbols), 30)]
      batch_labels = [f"Batch {idx+1} ({idx*30+1}–{idx*30+len(b)})" for idx, b in enumerate(batches)]
      selected_wl_batch_label = st.selectbox("Select 30-Symbol Batch to Copy:", options=batch_labels, key=f"wl_batch_select_{active_wl}_{wsc}")
      st.code(", ".join(batches[batch_labels.index(selected_wl_batch_label)]), language="text")
      with st.expander("📋 View / Copy All Tickers", expanded=False): st.code(", ".join(current_symbols), language="text")
    else:
      st.markdown("---")
      st.code(", ".join(current_symbols), language="text")

# ==========================================
# TAB 3: TRADEBOOK & PORTFOLIO RISK JOURNAL
# ==========================================
with tab_tradebook:
  st.subheader("📓 Tradebook & Institutional Risk Journal")
  tb_data = st.session_state.tradebook
  starting_cap = float(tb_data.get("config", {}).get("starting_capital", 500000.0))
  all_trades = tb_data.get("trades", [])

  df_mm_tb = load_market_monitor_data()

  open_trade_tickers = [t["ticker"] for t in all_trades if t.get("status") == "OPEN"]
  live_price_map = {}
  if open_trade_tickers:
    enriched_tb = fetch_watchlist_enrichMENT(open_trade_tickers)
    if not enriched_tb.empty and "Close" in enriched_tb.columns:
      live_price_map = dict(zip(enriched_tb["name"].str.upper(), enriched_tb["Close"]))

  cash_balance = starting_cap
  realized_pnl_total = unrealized_pnl_total = open_invested_total = open_current_val_total = open_risk_total = 0.0
  bench_bought_total = bench_current_val_total = 0.0
  trades_beating_bench = evaluated_bench_trades = 0

  latest_nifty_close = float(df_mm_tb.iloc[0]["Nifty 500 Close"]) if not df_mm_tb.empty and "Nifty 500 Close" in df_mm_tb.columns else 23700.0

  processed_trade_rows = []
  trade_signatures = {}
  sig_counter = 1
  for tr in all_trades:
    sig = f"{tr.get('ticker')}_{tr.get('date_bought')}_{tr.get('buy_price')}"
    if sig not in trade_signatures:
      trade_signatures[sig] = sig_counter
      sig_counter += 1

  for idx, tr in enumerate(all_trades, 1):
    status = tr.get("status", "OPEN")
    ticker = tr.get("ticker", "N/A")
    clean_sym = ticker.split(":")[-1].strip().upper()
    sh_bought = int(tr.get("shares_bought", 0))
    sh_sold = int(tr.get("shares_sold", 0))
    sh_rem = max(0, sh_bought - sh_sold)
    b_price = float(tr.get("buy_price", 0.0))
    sl_price = float(tr.get("initial_sl", b_price * 0.92))
    date_b = tr.get("date_bought", "N/A")
    sig = f"{ticker}_{date_b}_{b_price}"
    sl_num_shared = trade_signatures[sig]
    unit_risk = max(0.01, b_price - sl_price)
    nifty_buy_close = float(tr.get("nifty500_buy_close", fetch_nifty500_close_on_date(date_b, df_mm_tb)))

    if status == "OPEN":
      curr_price = float(live_price_map.get(clean_sym, tr.get("current_price", b_price)))
      sold_price, date_s = None, "N/A"
      capital_invested = sh_rem * b_price
      curr_val = sh_rem * curr_price
      booked_val, realized_pnl = 0.0, 0.0
      unrealized_pnl = sh_rem * (curr_price - b_price)
      open_risk_total += sh_rem * unit_risk
      open_invested_total += capital_invested
      open_current_val_total += curr_val
      unrealized_pnl_total += unrealized_pnl
      cash_balance -= capital_invested

      bench_val = capital_invested * (latest_nifty_close / nifty_buy_close) if nifty_buy_close > 0 else capital_invested
      bench_bought_total += capital_invested
      bench_current_val_total += bench_val

      lot_return_pct = (((curr_price - b_price) / b_price) * 100 if b_price > 0 else 0.0)
      bench_return_pct = (((latest_nifty_close - nifty_buy_close) / nifty_buy_close) * 100 if nifty_buy_close > 0 else 0.0)
      if lot_return_pct > bench_return_pct: trades_beating_bench += 1
      evaluated_bench_trades += 1
      realized_r, status_label = 0.0, "🟢 OPEN"

    else:
      sold_price = float(tr.get("sell_price", b_price))
      curr_price = sold_price
      date_s = tr.get("date_sold", "N/A")
      capital_invested = sh_sold * b_price
      booked_val = sh_sold * sold_price
      curr_val, unrealized_pnl = 0.0, 0.0
      realized_pnl = sh_sold * (sold_price - b_price)
      realized_pnl_total += realized_pnl
      cash_balance += (booked_val - capital_invested)

      nifty_sell_close = float(tr.get("nifty500_sell_close", fetch_nifty500_close_on_date(date_s, df_mm_tb)))
      bench_val = capital_invested * (nifty_sell_close / nifty_buy_close) if nifty_buy_close > 0 else capital_invested
      bench_bought_total += capital_invested
      bench_current_val_total += bench_val

      lot_return_pct = (((sold_price - b_price) / b_price) * 100 if b_price > 0 else 0.0)
      bench_return_pct = (((nifty_sell_close - nifty_buy_close) / nifty_buy_close) * 100 if nifty_buy_close > 0 else 0.0)
      if lot_return_pct > bench_return_pct: trades_beating_bench += 1
      evaluated_bench_trades += 1
      realized_r = (realized_pnl / (sh_sold * unit_risk) if (sh_sold * unit_risk) > 0 else 0.0)
      status_label = "🔵 WIN" if realized_pnl > 0 else "🔴 LOSS" if realized_pnl < 0 else "⚪ SCRATCH"

    tot_return_inr = realized_pnl + unrealized_pnl
    abs_return_pct = (((curr_price - b_price) / b_price) * 100 if b_price > 0 else 0.0)

    processed_trade_rows.append({
        "trade_id": tr.get("id"), "S.No._num": sl_num_shared, "Signature": sig, "Ticker": ticker, "Status": status_label,
        "Shares Bought": sh_bought, "Date Bought": date_b, "Buy Price (₹)": b_price, "Initial SL (₹)": sl_price,
        "Current / Sold Price (₹)": curr_price, "Gain / Loss (₹)": tot_return_inr,
        "Realized R": f"{realized_r:+.2f}R" if status == "CLOSED" else "0.00R", "Shares Sold": sh_sold,
        "Booked Value (₹)": booked_val, "Realised Gains (₹)": realized_pnl, "Shares Remaining": sh_rem,
        "Abs Return %": abs_return_pct, "Unrealised Value (₹)": unrealized_pnl, "Capital Invested (₹)": capital_invested,
        "Current Value (₹)": curr_val, "Date Sold": date_s,
    })

  total_portfolio_nav = cash_balance + open_current_val_total
  portfolio_heat_pct = ((open_risk_total / max(total_portfolio_nav, 1.0)) * 100)
  bench_total_nav = cash_balance + bench_current_val_total
  alpha_inr = total_portfolio_nav - bench_total_nav
  portfolio_net_return_pct = (((total_portfolio_nav - starting_cap) / starting_cap) * 100 if starting_cap > 0 else 0.0)
  bench_net_return_pct = (((bench_total_nav - starting_cap) / starting_cap) * 100 if starting_cap > 0 else 0.0)
  alpha_pct = portfolio_net_return_pct - bench_net_return_pct

  c1, c2, c3, c4, c5 = st.columns(5)
  c1.metric("Starting Capital", f"₹{starting_cap:,.2f}", f"Cash: ₹{cash_balance:,.2f}")
  c2.metric("Portfolio NAV", f"₹{total_portfolio_nav:,.2f}", f"{portfolio_net_return_pct:+.2f}% Net")
  c3.metric("Open Invested Value", f"₹{open_invested_total:,.2f}", f"Live: ₹{open_current_val_total:,.2f}")
  c4.metric("Realized P&L", f"₹{realized_pnl_total:,.2f}", f"Unrealized: ₹{unrealized_pnl_total:,.2f}")
  c5.metric("Portfolio Heat %", f"{portfolio_heat_pct:.2f}%", "🟢 SAFE" if portfolio_heat_pct <= 5.0 else "🟡 MODERATE" if portfolio_heat_pct <= 7.0 else "🔴 HIGH")

  st.markdown("---")
  ac1, ac2, ac3, ac4 = st.columns(4)
  ac1.metric("Portfolio Net Return", f"{portfolio_net_return_pct:+.2f}%")
  ac2.metric("Nifty 500 Shadow Return", f"{bench_net_return_pct:+.2f}%")
  ac3.metric("Alpha (Excess Return)", f"{alpha_pct:+.2f}%", f"₹{alpha_inr:,.2f}")
  beat_pct = ((trades_beating_bench / max(evaluated_bench_trades, 1)) * 100 if evaluated_bench_trades > 0 else 0.0)
  ac4.metric("Beat Index Win Rate", f"{beat_pct:.1f}%")
  st.markdown("---")

  df_tb_display = pd.DataFrame(processed_trade_rows)
  tb_selected_rows = st.session_state.get("tb_manage_table", {}).get("selection", {}).get("rows", [])
  selected_trade_id = None
  
  ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.2, 1.2, 1.2, 1.2, 2.0])
  with ctrl_col5: tb_filter = st.radio("Display Filter:", options=["All Positions", "Open Positions Only", "Closed Trades Only"], horizontal=True)
  
  if not df_tb_display.empty:
    if tb_filter == "Open Positions Only": df_tb_display = df_tb_display[df_tb_display["Status"] == "🟢 OPEN"]
    elif tb_filter == "Closed Trades Only": df_tb_display = df_tb_display[df_tb_display["Status"].isin(["🔵 WIN", "🔴 LOSS", "⚪ SCRATCH"])]
    df_tb_display["Allocation %"] = df_tb_display["Current Value (₹)"].apply(lambda v: (v / total_portfolio_nav) * 100 if total_portfolio_nav > 0 and v > 0 else 0.0)
    if tb_selected_rows and len(tb_selected_rows) > 0 and tb_selected_rows[0] < len(df_tb_display): selected_trade_id = df_tb_display.iloc[tb_selected_rows[0]]["trade_id"]

  @st.dialog("➕ Log New Position Entry", width="medium")
  def show_buy_modal():
    active_wl = st.session_state.get("active_watchlist_name", list(st.session_state.watchlists.keys())[0])
    with st.form("buy_trade_form", clear_on_submit=True):
      sel_ticker = st.selectbox("Select Ticker from Active Watchlist:", options=st.session_state.watchlists.get(active_wl, []))
      custom_ticker = st.text_input("OR Type Custom Ticker:", placeholder="NSE:BEL")
      b_date = st.date_input("Date Bought:", value=date.today())
      b_shares = st.number_input("Shares Bought:", min_value=1, value=100)
      b_price = st.number_input("Buy Price (₹):", min_value=0.1, value=100.0)
      b_sl = st.number_input("Initial Stop Loss Price (₹):", min_value=0.01, value=round(b_price * 0.92, 2))
      if st.form_submit_button("💾 Save Position Entry", use_container_width=True):
        final_ticker = custom_ticker.strip().upper() if custom_ticker.strip() else sel_ticker
        if final_ticker:
          date_s_str = b_date.strftime("%Y-%m-%d")
          st.session_state.tradebook["trades"].append({"id": f"TRD_{int(time.time()*1000)}", "ticker": final_ticker, "status": "OPEN", "date_bought": date_s_str, "shares_bought": int(b_shares), "shares_sold": 0, "buy_price": float(b_price), "initial_sl": float(b_sl), "nifty500_buy_close": fetch_nifty500_close_on_date(date_s_str, df_mm_tb)})
          save_tradebook(st.session_state.tradebook)
          st.rerun()

  @st.dialog("➖ Log Exit or Partial Sell", width="medium")
  def show_sell_modal(preselected_trade_id=None):
    open_lots = [t for t in st.session_state.tradebook["trades"] if t.get("status") == "OPEN"]
    if not open_lots: return st.info("No open trades currently in your Tradebook!")
    lot_options = {(f"{t['ticker']} (Bought {t['date_bought']} | {t['shares_bought'] - t['shares_sold']} shs @ ₹{t['buy_price']})"): t for t in open_lots}
    default_index = 0
    if preselected_trade_id:
        for i, (lbl, t) in enumerate(lot_options.items()):
            if t.get("id") == preselected_trade_id: default_index = i; break
    sel_label = st.selectbox("Select Active Position Lot to Sell:", options=list(lot_options.keys()), index=default_index)
    sel_lot = lot_options[sel_label]
    max_sell = sel_lot["shares_bought"] - sel_lot["shares_sold"]
    with st.form("sell_trade_form", clear_on_submit=True):
      s_date = st.date_input("Date Sold:", value=date.today())
      s_shares = st.number_input("Shares Sold:", min_value=1, max_value=max_sell, value=max_sell)
      s_price = st.number_input("Sell Price (₹):", min_value=0.1, value=sel_lot["buy_price"])
      if st.form_submit_button("💾 Execute Exit / Partial Sell", use_container_width=True):
        date_s_str = s_date.strftime("%Y-%m-%d")
        if s_shares == max_sell:
          sel_lot["status"], sel_lot["shares_sold"], sel_lot["sell_price"], sel_lot["date_sold"], sel_lot["nifty500_sell_close"] = "CLOSED", sel_lot["shares_sold"] + s_shares, float(s_price), date_s_str, fetch_nifty500_close_on_date(date_s_str, df_mm_tb)
        else:
          st.session_state.tradebook["trades"].append({"id": f"TRD_{int(time.time()*1000)}", "ticker": sel_lot["ticker"], "status": "CLOSED", "date_bought": sel_lot["date_bought"], "date_sold": date_s_str, "shares_bought": int(s_shares), "shares_sold": int(s_shares), "buy_price": sel_lot["buy_price"], "sell_price": float(s_price), "initial_sl": sel_lot["initial_sl"], "nifty500_buy_close": sel_lot["nifty500_buy_close"], "nifty500_sell_close": fetch_nifty500_close_on_date(date_s_str, df_mm_tb)})
          sel_lot["shares_bought"] -= s_shares
        save_tradebook(st.session_state.tradebook)
        st.rerun()

  @st.dialog("✏️ Edit or Delete Trade", width="medium")
  def show_edit_modal(trade_id):
    idx = next((i for i, t in enumerate(st.session_state.tradebook["trades"]) if t.get("id") == trade_id), None)
    if idx is None: return st.error("Trade not found.")
    sel_tr = st.session_state.tradebook["trades"][idx]
    with st.form("edit_trade_form"):
      e_status = st.selectbox("Status", ["OPEN", "CLOSED"], index=0 if sel_tr.get("status") == "OPEN" else 1)
      e_tick = st.text_input("Ticker", sel_tr.get("ticker", ""))
      c1, c2 = st.columns(2)
      with c1:
        e_sh_b = st.number_input("Shares Bought", min_value=1, value=int(sel_tr.get("shares_bought", 0)))
        e_bp = st.number_input("Buy Price", min_value=0.01, value=float(sel_tr.get("buy_price", 0.0)))
        try: e_db_val = pd.to_datetime(sel_tr.get("date_bought")).date()
        except: e_db_val = date.today()
        e_db = st.date_input("Date Bought", e_db_val)
        e_sl = st.number_input("Initial SL", min_value=0.00, value=float(sel_tr.get("initial_sl", 0.0)))
      with c2:
        e_sh_s = st.number_input("Shares Sold", min_value=0, value=int(sel_tr.get("shares_sold", 0)))
        e_sp = st.number_input("Sell Price", min_value=0.0, value=float(sel_tr.get("sell_price", 0.0)))
        try: e_ds_val = pd.to_datetime(sel_tr.get("date_sold")).date() if sel_tr.get("date_sold") and sel_tr.get("date_sold") != "N/A" else date.today()
        except: e_ds_val = date.today()
        e_ds = st.date_input("Date Sold", e_ds_val)
      col_upd, col_del = st.columns(2)
      with col_upd: submit_upd = st.form_submit_button("💾 Update Trade", use_container_width=True)
      with col_del: submit_del = st.form_submit_button("🗑️ Delete Trade", use_container_width=True)
      if submit_upd:
        sel_tr.update({"status": e_status, "ticker": e_tick, "shares_bought": e_sh_b, "buy_price": e_bp, "date_bought": e_db.strftime("%Y-%m-%d"), "initial_sl": e_sl, "shares_sold": e_sh_s, "sell_price": e_sp, "date_sold": e_ds.strftime("%Y-%m-%d") if e_status == "CLOSED" else "N/A"})
        save_tradebook(st.session_state.tradebook)
        st.rerun()
      if submit_del:
        st.session_state.tradebook["trades"].pop(idx)
        save_tradebook(st.session_state.tradebook)
        st.rerun()

  @st.dialog("⚙️ Configure Account Capital", width="small")
  def show_config_modal():
    with st.form("config_capital_form"):
      cap = st.number_input("Starting Portfolio Capital (₹):", min_value=10000.0, value=starting_cap, step=25000.0)
      if st.form_submit_button("💾 Save Config", use_container_width=True):
        st.session_state.tradebook["config"]["starting_capital"] = float(cap)
        save_tradebook(st.session_state.tradebook)
        st.rerun()

  with ctrl_col1:
    if st.button("➕ Log New Buy", type="primary", use_container_width=True): show_buy_modal()
  with ctrl_col2:
    if st.button("➖ Log Exit / Sell", type="secondary", use_container_width=True, disabled=(not selected_trade_id and len([t for t in all_trades if t.get("status") == "OPEN"]) == 0)): show_sell_modal(selected_trade_id)
  with ctrl_col3:
    if st.button("✏️ Edit / Delete", type="secondary", use_container_width=True, disabled=not selected_trade_id): show_edit_modal(selected_trade_id)
  with ctrl_col4:
    if st.button("⚙️ Config Capital", type="secondary", use_container_width=True): show_config_modal()

  if df_tb_display.empty: st.info("Your Tradebook is empty or no trades match the selected filter!")
  else:
    tb_table_columns = ["S.No._num", "Ticker", "Status", "Shares Bought", "Date Bought", "Buy Price (₹)", "Initial SL (₹)", "Current / Sold Price (₹)", "Gain / Loss (₹)", "Realized R", "Shares Sold", "Booked Value (₹)", "Realised Gains (₹)", "Shares Remaining", "Abs Return %", "Unrealised Value (₹)", "Capital Invested (₹)", "Current Value (₹)", "Allocation %"]
    st.dataframe(df_tb_display[tb_table_columns], use_container_width=True, hide_index=True, height=400, on_select="rerun", selection_mode="single-row", column_config=get_left_aligned_column_config(tb_table_columns), key="tb_manage_table")

    st.markdown("---")
    st.subheader("📊 Elite Risk Management & Performance Analytics")
    closed_lots = [t for t in processed_trade_rows if "WIN" in str(t.get("Status", "")) or "LOSS" in str(t.get("Status", "")) or "SCRATCH" in str(t.get("Status", ""))]
    total_closed = len(closed_lots)
    unique_setups = len(trade_signatures)
    active_setups = len(set(t["Signature"] for t in processed_trade_rows if "OPEN" in t["Status"]))

    if total_closed > 0:
      wins = [t for t in closed_lots if t["Realised Gains (₹)"] > 0]
      losses = [t for t in closed_lots if t["Realised Gains (₹)"] <= 0]
      win_count, loss_count = len(wins), len(losses)
      win_rate = (win_count / total_closed) * 100
      avg_win_inr = sum(t["Realised Gains (₹)"] for t in wins) / win_count if win_count > 0 else 0.0
      avg_loss_inr = abs(sum(t["Realised Gains (₹)"] for t in losses)) / loss_count if loss_count > 0 else 0.0
      avg_win_pct = sum(t["Abs Return %"] for t in wins) / win_count if win_count > 0 else 0.0
      avg_loss_pct = abs(sum(t["Abs Return %"] for t in losses)) / loss_count if loss_count > 0 else 0.0
      rr_monetary = avg_win_inr / avg_loss_inr if avg_loss_inr > 0 else avg_win_inr
      rr_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else avg_win_pct
      def calc_days(t):
        try: return max(1, (datetime.strptime(t["Date Sold"], "%Y-%m-%d") - datetime.strptime(t["Date Bought"], "%Y-%m-%d")).days)
        except Exception: return 1
      avg_days_win = sum(calc_days(t) for t in wins) / win_count if win_count > 0 else 0
      avg_days_loss = sum(calc_days(t) for t in losses) / loss_count if loss_count > 0 else 0
      streak_count = 0
      last_outcome = None
      for t in reversed(closed_lots):
        is_win = t["Realised Gains (₹)"] > 0
        if last_outcome is None: last_outcome, streak_count = is_win, 1
        elif last_outcome == is_win: streak_count += 1
        else: break
      streak_label = f"🟢 {streak_count} Wins" if last_outcome else f"🔴 {streak_count} Losses"
      if not last_outcome and streak_count >= 3: streak_label += " (⚠️ Cut Size 50%)"
    else:
      win_count, loss_count, win_rate, avg_win_inr, avg_loss_inr, avg_win_pct, avg_loss_pct, rr_monetary, rr_ratio, avg_days_win, avg_days_loss = 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0
      streak_label = "⚪ No Closed Trades"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Setups Logged", f"{unique_setups}", f"Live / Active: {active_setups}")
    k2.metric("Win Rate %", f"{win_rate:.1f}%", f"{win_count}W / {loss_count}L")
    k3.metric("Avg Win (₹ / %)", f"₹{avg_win_inr:,.0f}", f"+{avg_win_pct:.2f}%")
    k4.metric("Avg Loss (₹ / %)", f"-₹{avg_loss_inr:,.0f}", f"-{avg_loss_pct:.2f}%")
    k5.metric("Payoff Ratio (R:R)", f"{rr_ratio:.2f}x", f"Monetary: {rr_monetary:.2f}x")
    k6, k7, k8 = st.columns(3)
    k6.metric("Avg Days Held (Winners)", f"{avg_days_win:.1f} Days")
    k7.metric("Avg Days Held (Losers)", f"{avg_days_loss:.1f} Days")
    k8.metric("Progressive Exposure Streak", streak_label)

    st.markdown("---")
    st.subheader("📅 Trading Performance Calendar & Weekly Ledger")
    if total_closed == 0: st.info("No closed trades available to generate the Trading Calendar yet.")
    else:
      df_closed_cal = pd.DataFrame(closed_lots)
      df_closed_cal["Date_DT"] = pd.to_datetime(df_closed_cal["Date Sold"], errors="coerce")
      df_closed_cal = df_closed_cal.dropna(subset=["Date_DT"]).sort_values(by="Date_DT", ascending=False)
      daily_agg = df_closed_cal.groupby(df_closed_cal["Date_DT"].dt.strftime("%Y-%m-%d")).agg(Trades=("Ticker", "count"), Realised_Gains=("Realised Gains (₹)", "sum"), Wins=("Realised Gains (₹)", lambda s: (s > 0).sum())).reset_index()
      daily_agg.columns = ["Date Sold", "Trades", "Realised Gains (₹)", "Wins"]
      
      daily_agg["Win Rate %"] = ((daily_agg["Wins"] / daily_agg["Trades"].clip(lower=1)) * 100).round(1)
      daily_agg["Day"] = pd.to_datetime(daily_agg["Date Sold"]).dt.day_name().str[:3]
      daily_agg["Status"] = daily_agg["Realised Gains (₹)"].apply(lambda v: "🔵 +₹" + f"{v:,.0f}" if v > 0 else "🔴 -₹" + f"{abs(v):,.0f}")

      daily_display_cols = ["Date Sold", "Day", "Trades", "Realised Gains (₹)", "Win Rate %", "Status"]

      df_closed_cal["ISO_Week"] = df_closed_cal["Date_DT"].dt.strftime("%Y-W%V")
      weekly_agg = df_closed_cal.groupby("ISO_Week").agg(Trades=("Ticker", "count"), Realised_Gains=("Realised Gains (₹)", "sum"), Wins=("Realised Gains (₹)", lambda s: (s > 0).sum())).reset_index()
      weekly_agg.columns = ["ISO Week", "Trades", "Realised Gains (₹)", "Wins"]
      weekly_agg["Win Rate %"] = ((weekly_agg["Wins"] / weekly_agg["Trades"].clip(lower=1)) * 100).round(1)
      weekly_agg["Status"] = weekly_agg["Realised Gains (₹)"].apply(lambda v: "🔵 GREEN WEEK" if v > 0 else "🔴 RED WEEK")
      weekly_agg = weekly_agg.sort_values(by="ISO Week", ascending=False)
      
      recent_dt = pd.to_datetime(daily_agg["Date Sold"].max())
      cal_year, cal_month = recent_dt.year, recent_dt.month
      st.markdown(f"#### {calendar.month_name[cal_month]} {cal_year}")
      day_map = {pd.to_datetime(row["Date Sold"]).day: {"trades": row["Trades"], "pnl": row["Realised Gains (₹)"]} for _, row in daily_agg.iterrows() if pd.to_datetime(row["Date Sold"]).year == cal_year and pd.to_datetime(row["Date Sold"]).month == cal_month}
      
      cal_html = """<style>.cal-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 10px; margin-bottom: 20px; } .cal-header { font-weight: bold; text-align: center; padding: 10px; color: #E0E2EC; border-bottom: 2px solid #2B2F3E; } .cal-cell { border: 1px solid #2B2F3E; border-radius: 6px; padding: 10px; min-height: 90px; display: flex; flex-direction: column; justify-content: space-between; background-color: #1E222D; } .cal-cell-empty { border: none; background-color: transparent; } .cal-day { font-size: 13px; color: #888; text-align: right; margin-bottom: 5px; } .cal-val-win { color: #63BE7B; font-weight: bold; font-size: 16px; } .cal-val-loss { color: #F8696B; font-weight: bold; font-size: 16px; } .cal-val-neu { color: #E0E2EC; font-size: 16px; font-weight: bold;} .cal-trades { font-size: 12px; color: #888; margin-top: 5px; } .cal-week-tot { background-color: #243447; border-color: #3B4B61; text-align: center; }</style><div class="cal-grid"><div class="cal-header">Sun</div><div class="cal-header">Mon</div><div class="cal-header">Tue</div><div class="cal-header">Wed</div><div class="cal-header">Thu</div><div class="cal-header">Fri</div><div class="cal-header">Sat</div><div class="cal-header">Week Total</div>"""
      week_num = 1
      for week in calendar.monthcalendar(cal_year, cal_month):
          week_pnl, week_trades = 0.0, 0
          for day in week:
              if day == 0: cal_html += '<div class="cal-cell-empty"></div>'
              else:
                  data = day_map.get(day, {"trades": 0, "pnl": 0.0})
                  week_pnl += data["pnl"]; week_trades += data["trades"]
                  val_class = "cal-val-win" if data["pnl"] > 0 else "cal-val-loss" if data["pnl"] < 0 else "cal-val-neu"
                  pnl_str = f"₹{data['pnl']:,.0f}" if data['pnl'] == 0 else (f"+₹{data['pnl']:,.0f}" if data['pnl'] > 0 else f"-₹{abs(data['pnl']):,.0f}")
                  cal_html += f'<div class="cal-cell"><div class="cal-day">{day}</div><div class="{val_class}">{pnl_str}</div><div class="cal-trades">{data["trades"]} trades</div></div>'
          tot_class = "cal-val-win" if week_pnl > 0 else "cal-val-loss" if week_pnl < 0 else "cal-val-neu"
          tot_pnl_str = f"₹{week_pnl:,.0f}" if week_pnl == 0 else (f"+₹{week_pnl:,.0f}" if week_pnl > 0 else f"-₹{abs(week_pnl):,.0f}")
          cal_html += f'<div class="cal-cell cal-week-tot"><div class="cal-day">Week {week_num}</div><div class="{tot_class}" style="text-align: center; margin-top: auto;">{tot_pnl_str}</div><div class="cal-trades" style="text-align: center;">{week_trades} trades</div></div>'
          week_num += 1
      st.markdown(cal_html + "</div>", unsafe_allow_html=True)

      tab_day_tb, tab_week_tb = st.tabs(["📅 Daily Ledger Table", "🗓️ Weekly Matrix Table"])
      with tab_day_tb: st.dataframe(daily_agg[["Date Sold", "Day", "Trades", "Realised Gains (₹)", "Win Rate %", "Status"]], use_container_width=True, hide_index=True, height=280)
      with tab_week_tb: st.dataframe(weekly_agg[["ISO Week", "Trades", "Realised Gains (₹)", "Win Rate %", "Status"]], use_container_width=True, hide_index=True, height=280)

# ==========================================
# TAB 4: MARKET HEALTH & SECTOR ROTATION
# ==========================================
with tab_market_health:
  st.subheader("🏥 Market Health & Sector Rotation Studio")
  tab_ai_intel, tab_mm, tab_sector_heat, tab_sector_rot = st.tabs(["🎯 Daily AI Situational Awareness", "📈 NSE Market Breadth Monitor", "🔥 Sector RS Heatmap", "📊 Historical Rotation Tracker"])
  df_mm, (df_heat, df_rot) = load_market_monitor_data(), load_sector_monitor_data()

  with tab_ai_intel:
    st.subheader("🧠 Daily Market & Sector Situational Awareness")
    today_str = time.strftime("%Y-%m-%d")
    latest_briefing = st.session_state.market_briefings.get(today_str)
    b_col1, b_col2 = st.columns([1.8, 1.2])
    with b_col1:
      if latest_briefing: st.success(f"✅ Active Briefing Loaded for Date: **{today_str}**")
      else: st.info(f"No AI Briefing generated for **{today_str}** yet.")
    with b_col2:
      if st.button("🔄 Generate / Refresh Today's AI Briefing Now", type="primary", use_container_width=True):
        with st.status("🤖 Synthesizing Market Data...", expanded=True) as status_box:
          latest_briefing = run_gemini_market_awareness(df_mm, df_heat, df_rot, st.session_state.get("active_scan_summary", {}), status_log=status_box)
          if latest_briefing: status_box.update(label="✅ Briefing Complete!", state="complete"); time.sleep(1); st.rerun()
    if latest_briefing:
      st.markdown("---")
      st.markdown(latest_briefing.get("briefing_md", ""))
      st.markdown("---")
      st.download_button("📥 Download Daily Market Awareness Briefing (PDF)", data=create_pdf_bytes(f"Market_Awareness_{today_str}", latest_briefing.get("briefing_md", "")), file_name=f"NSE_Market_Awareness_{today_str}.pdf", mime="application/pdf", use_container_width=True)

  with tab_mm:
    if not df_mm.empty:
      st.markdown(f"#### 📊 Nifty Total Market Breadth & VCP Indicators ({len(df_mm)} Days)")
      latest = df_mm.iloc[0] if len(df_mm) > 0 else {}
      c1, c2, c3, c4 = st.columns(4)
      c1.metric("Latest Nifty 500 Close", f"{latest.get('Nifty 500 Close', 'N/A')}", f"{latest.get('Nifty 500 Chg %', 0)}%")
      c2.metric("5-Day Thrust Ratio", f"{latest.get('5 Day Ratio', 'N/A')}")
      c3.metric("10-Day Thrust Ratio", f"{latest.get('10 Day Ratio', 'N/A')}")
      c4.metric("A/D Ratio", f"{latest.get('A/D Ratio', 'N/A')}")
      st.table(style_market_monitor(df_mm))
    else: st.info("Market Monitor data not available yet.")

  with tab_sector_heat:
    if not df_heat.empty:
      st.markdown("#### 🔥 27-Sector CAN SLIM Relative Strength Heatmap")
      st.table(style_sector_heatmap(df_heat))
    else: st.info("Sector Heatmap data not available yet.")

  with tab_sector_rot:
    if not df_rot.empty:
      st.markdown("#### 📊 65-Day Historical Relative Strength Ranks")
      st.table(style_rotation_tracker(df_rot))
    else: st.info("Rotation Tracker data not available yet.")
