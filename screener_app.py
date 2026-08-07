import glob
import io
import json
import os
import re
import smtplib
import threading
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from google import genai
import markdown
import plotly.express as px
import requests
import pandas as pd
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
# CUSTOM SLEEK CSS FOR ST.TABLE (NO WRAPPING & FIXED WIDTHS)
# ==========================================
TABLE_CUSTOM_CSS = """
<style>
div[data-testid="stTable"] {
    overflow-x: auto !important;
}
div[data-testid="stTable"] table {
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 13px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}
div[data-testid="stTable"] th {
    padding: 8px 12px !important;
    text-align: center !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    background-color: #1E222D !important;
    color: #E0E2EC !important;
    border-bottom: 2px solid #2B2F3E !important;
    min-width: 85px !important;
}
div[data-testid="stTable"] td {
    padding: 7px 12px !important;
    text-align: center !important;
    white-space: nowrap !important;
    border-bottom: 1px solid #2B2F3E !important;
    min-width: 85px !important;
}
div[data-testid="stTable"] th:nth-child(1),
div[data-testid="stTable"] td:nth-child(1) {
    text-align: left !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    min-width: 115px !important;
    max-width: 150px !important;
}
</style>
"""
st.markdown(TABLE_CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 0. AUTOMATIC GITHUB GIST PERSISTENCE
# ==========================================
WATCHLIST_FILE = "local_watchlists.json"
PRESETS_FILE = "local_filter_presets.json"
REPORTS_FILE = "local_fundamental_reports.json"

GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", None)
GIST_ID = st.secrets.get("GIST_ID", None)


def load_watchlists():
  if GITHUB_TOKEN and GIST_ID:
    try:
      headers = {
          "Authorization": f"token {GITHUB_TOKEN}",
          "Accept": "application/vnd.github.v3+json",
      }
      res = requests.get(
          f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=5
      )
      if res.status_code == 200:
        gist_data = res.json()
        if "local_watchlists.json" in gist_data["files"]:
          content = gist_data["files"]["local_watchlists.json"]["content"]
          return json.loads(content)
    except Exception as e:
      st.warning(f"GitHub Gist load failed, switching to local disk: {e}")

  if os.path.exists(WATCHLIST_FILE):
    try:
      with open(WATCHLIST_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass

  return {
      "Post Breakout Monitor": ["NSE:ZOMATO", "NSE:CDSL", "NSE:TITAGARH"],
      "Focus List": ["NSE:JINDWORLD", "NSE:TRENT", "NSE:HAL", "NSE:RECLTD"],
      "Weekly Focus": ["NSE:BHEL", "NSE:ABB", "NSE:SIEMENS", "NSE:CGPOWER"],
      "Scan Bulk": [],
      "Sold Stocks": [],
  }


def save_watchlists(watchlists_dict):
  try:
    with open(WATCHLIST_FILE, "w") as f:
      json.dump(watchlists_dict, f, indent=2)
  except Exception:
    pass

  if GITHUB_TOKEN and GIST_ID:
    try:
      headers = {
          "Authorization": f"token {GITHUB_TOKEN}",
          "Accept": "application/vnd.github.v3+json",
      }
      payload = {
          "files": {
              "local_watchlists.json": {
                  "content": json.dumps(watchlists_dict, indent=2)
              }
          }
      }
      requests.patch(
          f"https://api.github.com/gists/{GIST_ID}",
          headers=headers,
          json=payload,
          timeout=5,
      )
    except Exception:
      pass


def load_filter_presets():
  default_ma_configs = [
      {"en": True, "type": "EMA", "len": 21},
      {"en": True, "type": "SMA", "len": 50},
      {"en": False, "type": "SMA", "len": 200},
      {"en": False, "type": "EMA", "len": 10},
      {"en": False, "type": "SMA", "len": 150},
  ]
  default_presets = {
      "🏆 CAN SLIM & Growth Breakout": {
          "exchanges": ["NSE", "BSE"],
          "sectors": [],
          "industries": [],
          "indices": [],
          "min_mcap_cr": 1000,
          "vol_period_days": 60,
          "min_vol_cr": 5.0,
          "en_ipo": False,
          "ipo_filter": "All Stocks (No IPO Filter)",
          "en_eps_q": True,
          "min_eps_q": 15.0,
          "en_sales_q": True,
          "min_sales_q": 10.0,
          "allow_na_growth": True,
          "en_adr": True,
          "min_adr": 2.5,
          "en_above_52l": True,
          "min_above_52l": 20,
          "en_below_52h": True,
          "max_below_52h": 25,
          "en_circuit": True,
          "circuit_val": ["2%", "5%", "10%"],
          "selected_perf_labels": [
              "1 Week",
              "1 Month",
              "3 Months",
              "6 Months",
          ],
          "max_results": 4000,
          "ma_configs": default_ma_configs,
          "perf_configs": {
              c: {"en": False, "val": 0.0}
              for c in [
                  "Perf.W",
                  "Perf.1M",
                  "Perf.3M",
                  "Perf.6M",
                  "Perf.YTD",
                  "Perf.Y",
              ]
          },
      },
      "⚡ High ADR Momentum (>4%)": {
          "exchanges": ["NSE", "BSE"],
          "sectors": [],
          "industries": [],
          "indices": [],
          "min_mcap_cr": 500,
          "vol_period_days": 30,
          "min_vol_cr": 10.0,
          "en_ipo": False,
          "ipo_filter": "All Stocks (No IPO Filter)",
          "en_eps_q": False,
          "min_eps_q": 0.0,
          "en_sales_q": False,
          "min_sales_q": 0.0,
          "allow_na_growth": True,
          "en_adr": True,
          "min_adr": 4.0,
          "en_above_52l": True,
          "min_above_52l": 30,
          "en_below_52h": True,
          "max_below_52h": 15,
          "en_circuit": True,
          "circuit_val": ["2%", "5%", "10%"],
          "selected_perf_labels": ["1 Week", "1 Month", "3 Months"],
          "max_results": 4000,
          "ma_configs": default_ma_configs,
          "perf_configs": {
              c: {"en": False, "val": 0.0}
              for c in [
                  "Perf.W",
                  "Perf.1M",
                  "Perf.3M",
                  "Perf.6M",
                  "Perf.YTD",
                  "Perf.Y",
              ]
          },
      },
      "🛡️ Nifty 500 Core Compounders": {
          "exchanges": ["NSE"],
          "sectors": [],
          "industries": [],
          "indices": ["NIFTY 500"],
          "min_mcap_cr": 5000,
          "vol_period_days": 60,
          "min_vol_cr": 15.0,
          "en_ipo": True,
          "ipo_filter": "Seasoned: Listed > 1 Year Ago",
          "en_eps_q": True,
          "min_eps_q": 10.0,
          "en_sales_q": True,
          "min_sales_q": 10.0,
          "allow_na_growth": False,
          "en_adr": True,
          "min_adr": 1.5,
          "en_above_52l": True,
          "min_above_52l": 15,
          "en_below_52h": True,
          "max_below_52h": 35,
          "en_circuit": False,
          "circuit_val": ["2%", "5%", "10%"],
          "selected_perf_labels": [
              "1 Month",
              "3 Months",
              "6 Months",
              "1 Year",
          ],
          "max_results": 4000,
          "ma_configs": [
              {"en": True, "type": "EMA", "len": 21},
              {"en": True, "type": "SMA", "len": 50},
              {"en": True, "type": "SMA", "len": 200},
              {"en": False, "type": "EMA", "len": 10},
              {"en": False, "type": "SMA", "len": 150},
          ],
          "perf_configs": {
              c: {"en": False, "val": 0.0}
              for c in [
                  "Perf.W",
                  "Perf.1M",
                  "Perf.3M",
                  "Perf.6M",
                  "Perf.YTD",
                  "Perf.Y",
              ]
          },
      },
  }

  if GITHUB_TOKEN and GIST_ID:
    try:
      headers = {
          "Authorization": f"token {GITHUB_TOKEN}",
          "Accept": "application/vnd.github.v3+json",
      }
      res = requests.get(
          f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=5
      )
      if res.status_code == 200:
        gist_data = res.json()
        if PRESETS_FILE in gist_data["files"]:
          content = gist_data["files"][PRESETS_FILE]["content"]
          return json.loads(content)
    except Exception:
      pass

  if os.path.exists(PRESETS_FILE):
    try:
      with open(PRESETS_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass

  return default_presets


def save_filter_presets(presets_dict):
  try:
    with open(PRESETS_FILE, "w") as f:
      json.dump(presets_dict, f, indent=2)
  except Exception:
    pass

  if GITHUB_TOKEN and GIST_ID:
    try:
      headers = {
          "Authorization": f"token {GITHUB_TOKEN}",
          "Accept": "application/vnd.github.v3+json",
      }
      payload = {
          "files": {PRESETS_FILE: {"content": json.dumps(presets_dict, indent=2)}}
      }
      requests.patch(
          f"https://api.github.com/gists/{GIST_ID}",
          headers=headers,
          json=payload,
          timeout=5,
      )
    except Exception:
      pass


# ==========================================
# GIST PERSISTENCE FOR FUNDAMENTAL REPORTS
# ==========================================
def load_fundamental_reports():
  if GITHUB_TOKEN and GIST_ID:
    try:
      headers = {
          "Authorization": f"token {GITHUB_TOKEN}",
          "Accept": "application/vnd.github.v3+json",
      }
      res = requests.get(
          f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=5
      )
      if res.status_code == 200:
        gist_data = res.json()
        if REPORTS_FILE in gist_data["files"]:
          content = gist_data["files"][REPORTS_FILE]["content"]
          return json.loads(content)
    except Exception:
      pass

  if os.path.exists(REPORTS_FILE):
    try:
      with open(REPORTS_FILE, "r") as f:
        return json.load(f)
    except Exception:
      pass

  return {}


def save_fundamental_reports(reports_dict, auth_config=None):
  try:
    with open(REPORTS_FILE, "w") as f:
      json.dump(reports_dict, f, indent=2)
  except Exception:
    pass

  token = (
      auth_config.get("github_token")
      if auth_config
      else st.secrets.get("GITHUB_TOKEN", None)
  )
  gist_id = (
      auth_config.get("gist_id")
      if auth_config
      else st.secrets.get("GIST_ID", None)
  )

  if token and gist_id:
    try:
      headers = {
          "Authorization": f"token {token}",
          "Accept": "application/vnd.github.v3+json",
      }
      payload = {
          "files": {REPORTS_FILE: {"content": json.dumps(reports_dict, indent=2)}}
      }
      requests.patch(
          f"https://api.github.com/gists/{gist_id}",
          headers=headers,
          json=payload,
          timeout=5,
      )
    except Exception:
      pass


if "watchlists" not in st.session_state:
  st.session_state.watchlists = load_watchlists()
if "active_watchlist_name" not in st.session_state:
  st.session_state.active_watchlist_name = list(
      st.session_state.watchlists.keys()
  )[0]
if "filter_presets" not in st.session_state:
  st.session_state.filter_presets = load_filter_presets()
if "fundamental_reports" not in st.session_state:
  st.session_state.fundamental_reports = load_fundamental_reports()
if "reset_counter" not in st.session_state:
  st.session_state.reset_counter = 0
if "scan_sel_counter" not in st.session_state:
  st.session_state.scan_sel_counter = 0
if "wl_sel_counter" not in st.session_state:
  st.session_state.wl_sel_counter = 0

# ==========================================
# UNSTOPPABLE BACKGROUND AI WORKER TRACKER
# ==========================================
GLOBAL_AI_WORKER_STATE = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current_ticker": "",
    "message": "",
    "last_updated": 0,
}


def background_ai_worker(
    symbols_list, force_reanalyze, auth_config, reports_dict
):
  GLOBAL_AI_WORKER_STATE["is_running"] = True
  GLOBAL_AI_WORKER_STATE["total"] = len(symbols_list)
  GLOBAL_AI_WORKER_STATE["completed"] = 0

  for idx, sym in enumerate(symbols_list):
    clean_sym = sym.split(":")[-1].strip().upper()
    GLOBAL_AI_WORKER_STATE["current_ticker"] = clean_sym
    GLOBAL_AI_WORKER_STATE["message"] = (
        f"Analyzing ({idx + 1}/{len(symbols_list)}): {clean_sym} — Downloading"
        " PDFs & Running Gemini..."
    )

    if clean_sym in reports_dict and not force_reanalyze:
      GLOBAL_AI_WORKER_STATE["completed"] += 1
      continue

    try:
      new_rep = run_gemini_fundamental_analysis(clean_sym, auth_config)
      if new_rep:
        reports_dict[clean_sym] = new_rep
        save_fundamental_reports(reports_dict, auth_config)
    except Exception as e:
      print(f"Background AI Worker Error ({clean_sym}): {e}")

    GLOBAL_AI_WORKER_STATE["completed"] += 1
    GLOBAL_AI_WORKER_STATE["last_updated"] = time.time()

  GLOBAL_AI_WORKER_STATE["is_running"] = False
  GLOBAL_AI_WORKER_STATE["message"] = (
      f"✅ Completed AI Fundamental Analysis for {len(symbols_list)} stocks!"
  )
  GLOBAL_AI_WORKER_STATE["last_updated"] = time.time()


# ==========================================
# GEMINI FUNDAMENTAL AI ANALYST ENGINE
# ==========================================
def run_gemini_fundamental_analysis(ticker_input, auth_config):
  gemini_key = auth_config.get("gemini_key", "")
  screener_sid = auth_config.get("screener_sid", "")
  email_addr = auth_config.get("email_addr", "")
  email_pass = auth_config.get("email_pass", "")

  if not gemini_key:
    return None

  client = genai.Client(api_key=gemini_key)
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
      ),
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
      ),
      "Referer": "https://www.screener.in/",
  }
  cookies = {"sessionid": screener_sid}

  clean_ticker = (
      ticker_input.split(":")[-1].strip().upper()
      if ":" in str(ticker_input)
      else str(ticker_input).strip().upper()
  )
  download_dir = f"documents_{clean_ticker}"
  os.makedirs(download_dir, exist_ok=True)
  for f in glob.glob(f"{download_dir}/*"):
    os.remove(f)

  url = f"https://www.screener.in/company/{clean_ticker}/consolidated/"

  try:
    res = requests.get(url, headers=headers, cookies=cookies, timeout=20)
    if res.status_code != 200:
      return None

    soup = BeautifulSoup(res.content, "html.parser")
    documents_section = soup.find(id="documents")
    if not documents_section:
      return None

    ars, transcripts, ppts = [], [], []
    for link in documents_section.find_all("a", href=True):
      href = link["href"]
      text = link.get_text(strip=True).lower()
      if "financial year" in text or "annual report" in text:
        ars.append(("Annual Report", href))
      elif text == "transcript":
        transcripts.append(("Transcript", href))
      elif text == "ppt":
        ppts.append(("PPT", href))

    state = {"count": 0, "urls": set()}

    def try_download(text, href):
      if href in state["urls"]:
        return False
      full_url = (
          href
          if href.startswith("http")
          else urljoin("https://www.screener.in", href)
      )
      try:
        doc_res = requests.get(
            full_url, headers=headers, cookies=cookies, timeout=30
        )
        if b"%PDF" in doc_res.content[:100]:
          file_name = f"screener_doc_{state['count'] + 1}.pdf"
          file_path = os.path.join(download_dir, file_name)
          with open(file_path, "wb") as f:
            f.write(doc_res.content)
          state["count"] += 1
          state["urls"].add(href)
          time.sleep(0.5)
          return True
      except Exception:
        pass
      return False

    for t, h in ars[:1]:
      try_download("Annual Report", h)
    for t, h in transcripts[:4]:
      try_download("Transcript", h)
    for t, h in ppts[:4]:
      try_download("PPT", h)

    pdf_files = glob.glob(f"{download_dir}/*.pdf")
    if not pdf_files:
      return None

    uploaded_files = [client.files.upload(file=fp) for fp in pdf_files]
    for f in uploaded_files:
      while True:
        info = client.files.get(name=f.name)
        if "ACTIVE" in str(info.state).upper():
          break
        time.sleep(2)

    prompt = """
You are an uncompromising, strict Mark Minervini-style fundamental analyst. Your sole objective is to analyze the provided Annual Report, Investor Presentations, and Earnings Call Transcripts to determine if the company meets Minervini's "Superperformance" criteria.

### DATA & GROUND TRUTH RULES
1. Rely ONLY on the uploaded documents and consider ONLY consolidated financial figures.
2. Do not speculate, calculate unstated assumptions, or fill gaps from external knowledge.
3. If any metric or fact is missing from the document, write explicitly: "Not available in uploaded documents."

### STRICT CATALYST & VERDICT RULES (CRITICAL)
- **NO CATALYST = NO PASS:** Even if YoY earnings and sales growth are >20%, you CANNOT award a 🟢 PASS if there is no explicit, forward-looking fundamental catalyst identified in the transcripts or presentations. If growth is strong but no catalyst/trigger is found, the maximum grade is 🟡 WATCHLIST.
- **SECTOR-ADAPTIVE CATALYST SEARCH:** Automatically adjust the catalyst criteria based on the company's business model:
  - *Manufacturing / Auto / Infra:* CapEx completion, plant commissioning, order book growth, raw material margin relief.
  - *Financials / Banks / NBFCs:* Credit/loan growth acceleration, Net Interest Margin (NIM) expansion, sharp drops in NPAs, strong AUM growth.
  - *Tech / IT / SaaS:* Large deal wins (TCV), client additions, utilization/margin recovery, geographic expansion.
  - *Consumer / FMCG / Retail:* Volume growth acceleration (not just price-led), Same-Store Sales Growth (SSSG), store count expansion.
  - *Pharma / Healthcare:* US FDA approvals, new launches, hospital bed capacity additions, ARPOB growth.
  - *Platforms / Exchanges:* Market share expansion, active user growth, transaction volume surges.
- **FORWARD-LOOKING vs. BACKWARD-LOOKING:** Prioritize forward-looking triggers (management guidance, upcoming launches, margin expansions, pipeline) found in recent Earnings Calls over historical reports.
- **Base Verdict ONLY on Available Data:** Do not penalize missing data points, but strictly enforce the presence of a tangible growth catalyst.

---

### OUTPUT FORMAT & VISUAL HIERARCHY

#### 1. HEADER & INSTANT VERDICT
Provide the company name and an instant decision verdict:
- **MINERVINI FUNDAMENTAL VERDICT:** [Insert 🟢 PASS / 🟡 WATCHLIST / 🔴 FAIL]
- **🚀 PRIMARY CATALYST / BREAKOUT TRIGGER:** [State in 1-2 BOLD sentences the exact forward-looking trigger driving this stock].
- **VERDICT LOGIC:** [Provide a 1-2 sentence justification for the overall verdict].

#### 2. SUPERPERFORMANCE SCORECARD
Present this quick-scan summary table (Use "N/A - Not in Document" if missing):

| Core Pillar | Status | Key Metric / Reason |
| :--- | :---: | :--- |
| **1. Growth Velocity (Code 33)** | [🟢 / 🟡 / 🔴 / ⚪ N/A] | [1-line summary of EPS, Sales, and Net Margin acceleration] |
| **2. Forward Catalyst & Triggers** | [🟢 / 🟡 / 🔴 / ⚪ N/A] | [1-line summary of sector-specific catalyst from Concalls/PPTs] |
| **3. Earnings Quality & Red Flags**| [🟢 / 🟡 / 🔴 / ⚪ N/A] | [1-line summary of receivables, inventory, or cash flow] |

#### 3. BOTTOM LINE UP FRONT (BLUF)
- **Top Fundamental Strengths (from available data):**
  - [Bullet 1]
  - [Bullet 2]
  - [Bullet 3]
- **Top Red Flags / Concerns (from available data):**
  - [Bullet 1]
  - [Bullet 2]
  - [Bullet 3]

---

### DETAILED ANALYSIS BREAKDOWN
Use visual status icons at the start of each bullet: 🟢 Clear Pass | 🔴 Fail/Red Flag | 🟡 Mixed/Override | ⚠️ Warning/Watch | ⚪ Not available in document.
"""

    try:
      response = client.models.generate_content(
          model="gemini-2.5-flash",
          contents=[prompt] + uploaded_files,
          config={"service_tier": "flex"},
      )
    except Exception as e:
      if "tokens allowed" in str(e) or "400" in str(e):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt] + uploaded_files[:4],
            config={"service_tier": "flex"},
        )
      else:
        raise e

    analysis_text = response.text

    verdict_line = ""
    for line in analysis_text.upper().split("\n"):
      if "MINERVINI FUNDAMENTAL VERDICT:" in line or "VERDICT:" in line:
        verdict_line = line
        break

    if "PASS" in verdict_line or "🟢" in verdict_line:
      verdict = "🟢 PASS"
    elif "WATCHLIST" in verdict_line or "🟡" in verdict_line:
      verdict = "🟡 WATCHLIST"
    elif "FAIL" in verdict_line or "🔴" in verdict_line:
      verdict = "🔴 FAIL"
    else:
      verdict = "🟣 Review Needed"

    today_str = time.strftime("%Y-%m-%d")
    report_entry = {
        "ticker": clean_ticker,
        "verdict": verdict,
        "date": today_str,
        "report_md": analysis_text,
    }

    # Optional Email Sender
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
      except Exception:
        pass

    return report_entry

  except Exception:
    return None


@st.dialog("🧠 Minervini Fundamental AI Analyst", width="large")
def show_fundamental_modal(ticker_symbol):
  clean_sym = (
      ticker_symbol.split(":")[-1].strip().upper()
      if ":" in str(ticker_symbol)
      else str(ticker_symbol).strip().upper()
  )
  rep = st.session_state.fundamental_reports.get(clean_sym)

  if not rep:
    st.info(
        f"No stored report for **{clean_sym}**. Check its row in the table"
        " below and click 'Analyze Selected'!"
    )
  else:
    st.subheader(f"📊 {clean_sym} — {rep.get('verdict', 'N/A')}")
    st.caption(
        f"📅 Generated On: **{rep.get('date', 'N/A')}** | 💡 Zero tokens"
        " spent on load"
    )
    st.markdown("---")
    st.markdown(rep.get("report_md", ""))
    st.markdown("---")
    if st.button(
        "🔄 Re-Analyze & Overwrite (Quarterly Refresh)",
        type="secondary",
        use_container_width=True,
    ):
      auth_config = {
          "gemini_key": st.secrets.get("GEMINI_API_KEY", ""),
          "screener_sid": st.secrets.get("SCREENER_SESSION_ID", ""),
          "email_addr": st.secrets.get("EMAIL_ADDRESS", ""),
          "email_pass": st.secrets.get("EMAIL_APP_PASSWORD", ""),
          "github_token": st.secrets.get("GITHUB_TOKEN", None),
          "gist_id": st.secrets.get("GIST_ID", None),
      }
      with st.spinner(
          f"📡 Fetching latest Screener.in PDFs & replacing {clean_sym}"
          " report..."
      ):
        updated_rep = run_gemini_fundamental_analysis(clean_sym, auth_config)
        if updated_rep:
          st.session_state.fundamental_reports[clean_sym] = updated_rep
          save_fundamental_reports(
              st.session_state.fundamental_reports, auth_config
          )
          st.success("✅ Old report replaced with latest quarterly data!")
          st.rerun()


def get_fundamental_badge(sym_name):
  clean_sym = (
      sym_name.split(":")[-1].strip().upper()
      if ":" in str(sym_name)
      else str(sym_name).strip().upper()
  )
  rep = st.session_state.fundamental_reports.get(clean_sym)
  if not rep:
    return "⚪ Not Analyzed"
  return f"{rep.get('verdict')} ({rep.get('date', '')})"


# ==========================================
# 0B. AUTHENTICATED EXCEL LOADER (3-TIER AUTH & RETRY)
# ==========================================
def fetch_excel_file(filename):
  if os.path.exists(filename):
    return filename

  headers_list = []
  if GITHUB_TOKEN:
    headers_list.append({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    })
    headers_list.append({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Authorization": f"token {GITHUB_TOKEN}",
    })
  headers_list.append({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

  repos = [
      "chethanshivaraju94-netizen/nse-market-monitor",
      "chethanshivaraju94-netizen/India-equities-screener",
  ]
  branches = ["main", "master"]

  for repo in repos:
    for branch in branches:
      url = f"https://raw.githubusercontent.com/{repo}/{branch}/{filename}"
      for headers in headers_list:
        try:
          res = requests.get(url, headers=headers, timeout=10)
          if res.status_code == 200:
            return io.BytesIO(res.content)
        except Exception:
          pass

  return None


@st.cache_data(ttl=43200, show_spinner="📡 Synchronizing Daily Circuit Price Bands...")
def get_nse_circuit_bands():
  symbol_to_band = {}
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    session = requests.Session()
    session.headers.update(headers)
    session.get("https://www.nseindia.com", timeout=5)
    url = (
        "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
    )
    res = session.get(url, timeout=6)
    if res.status_code == 200:
      data = res.json()
      for row in data.get("data", []):
        sym = str(row.get("symbol", "")).strip().upper()
        band_val = str(row.get("priceBand", "")).strip()
        if sym and band_val:
          symbol_to_band[sym] = band_val
  except Exception:
    pass

  if not symbol_to_band:
    try:
      cdn_url = (
          "https://raw.githubusercontent.com/datasets/nse-stocks/master/data/stock_metadata.json"
      )
      res_cdn = requests.get(cdn_url, timeout=5)
      if res_cdn.status_code == 200:
        for item in res_cdn.json():
          sym = str(item.get("symbol", "")).strip().upper()
          band_val = str(item.get("band", "")).strip()
          if sym and band_val:
            symbol_to_band[sym] = band_val
    except Exception:
      pass

  return symbol_to_band


@st.cache_data(
    ttl=3600, show_spinner="📡 Fetching latest Market Health & Sector tables..."
)
def load_market_monitor_data():
  file_source = fetch_excel_file("NSE_Market_Monitor.xlsx")
  if file_source is None:
    return pd.DataFrame()

  try:
    df = pd.read_excel(file_source, sheet_name=0)
    if "Date" in df.columns:
      df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime(
          "%Y-%m-%d"
      )
    return df
  except Exception as e:
    st.error(f"Could not parse Market Monitor file: {e}")
    return pd.DataFrame()


@st.cache_data(
    ttl=3600,
    show_spinner="📡 Fetching Sector Rotation & Heatmap tables...",
)
def load_sector_monitor_data():
  file_source = fetch_excel_file("NSE_Sector_Monitor.xlsx")
  if file_source is None:
    return pd.DataFrame(), pd.DataFrame()

  try:
    xls = pd.ExcelFile(file_source)
    df_heat = (
        pd.read_excel(xls, sheet_name="Heatmap")
        if "Heatmap" in xls.sheet_names
        else pd.DataFrame()
    )
    df_rot = (
        pd.read_excel(xls, sheet_name="Rotation Tracker")
        if "Rotation Tracker" in xls.sheet_names
        else pd.DataFrame()
    )
    if "Date" in df_rot.columns:
      df_rot["Date"] = pd.to_datetime(
          df_rot["Date"], errors="coerce"
      ).dt.strftime("%Y-%m-%d")
    return df_heat, df_rot
  except Exception as e:
    st.error(f"Could not parse Sector Monitor file: {e}")
    return pd.DataFrame(), pd.DataFrame()


# ==========================================
# 0C. EXCEL COLOR SCALE GRADIENT ENGINE FOR TAB 3
# ==========================================
def color_scale_3pt(
    val,
    v_min,
    v_mid,
    v_max,
    c_min=(248, 105, 107),
    c_mid=(255, 255, 255),
    c_max=(99, 190, 123),
):
  if pd.isna(val) or val == "" or str(val).strip() == "":
    return ""
  try:
    v = float(val)
  except Exception:
    return ""

  if v <= v_min:
    r, g, b = c_min
  elif v >= v_max:
    r, g, b = c_max
  elif v < v_mid:
    ratio = (v - v_min) / max((v_mid - v_min), 1e-6)
    r = int(c_min[0] + (c_mid[0] - c_min[0]) * ratio)
    g = int(c_min[1] + (c_mid[1] - c_min[1]) * ratio)
    b = int(c_min[2] + (c_mid[2] - c_min[2]) * ratio)
  else:
    ratio = (v - v_mid) / max((v_max - v_mid), 1e-6)
    r = int(c_mid[0] + (c_max[0] - c_mid[0]) * ratio)
    g = int(c_mid[1] + (c_max[1] - c_mid[1]) * ratio)
    b = int(c_mid[2] + (c_max[2] - c_mid[2]) * ratio)
  return f"background-color: #{r:02X}{g:02X}{b:02X}; color: #000000;"


def color_scale_2pt(
    val, v_min, v_max, c_min=(255, 255, 255), c_max=(99, 190, 123)
):
  if pd.isna(val) or val == "" or str(val).strip() == "":
    return ""
  try:
    v = float(val)
  except Exception:
    return ""

  if v <= v_min:
    r, g, b = c_min
  elif v >= v_max:
    r, g, b = c_max
  else:
    ratio = (v - v_min) / max((v_max - v_min), 1e-6)
    r = int(c_min[0] + (c_max[0] - c_min[0]) * ratio)
    g = int(c_min[1] + (c_max[1] - c_min[1]) * ratio)
    b = int(c_min[2] + (c_max[2] - c_min[2]) * ratio)
  return f"background-color: #{r:02X}{g:02X}{b:02X}; color: #000000;"


def color_binary_badge(val):
  v_str = str(val).strip().lower()
  if v_str in ["yes", "up"]:
    return "background-color: #63BE7B; color: #000000; font-weight: bold;"
  elif v_str in ["no", "down"]:
    return "background-color: #F8696B; color: #000000; font-weight: bold;"
  return ""


def safe_map(styler, func, subset=None):
  if hasattr(styler, "map"):
    return styler.map(func, subset=subset)
  else:
    return styler.applymap(func, subset=subset)


def style_market_monitor(df):
  styler = df.style
  format_dict = {}
  int_cols = [
      "Up 4% Today",
      "Down 4% Today",
      "Advances",
      "Declines",
      "52W Highs",
      "52W Lows",
  ]
  float_cols = [
      "5 Day Ratio",
      "10 Day Ratio",
      "A/D Ratio",
      "Volume Breadth",
      "> 200 SMA (%)",
      "> 50 SMA (%)",
      "> 20 EMA (%)",
      "> 10 EMA (%)",
      "Nifty 500 Close",
      "Nifty 500 Chg %",
  ]
  for col in int_cols:
    if col in df.columns:
      format_dict[col] = "{:.0f}"
  for col in float_cols:
    if col in df.columns:
      format_dict[col] = "{:.2f}"
  styler = styler.format(format_dict, na_rep="N/A")

  for c in ["Up 4% Today", "Advances", "52W Highs"]:
    if c in df.columns:
      max_v = 750 if c == "Advances" else 200
      styler = safe_map(
          styler,
          lambda v, mv=max_v: color_scale_2pt(
              v, 0, mv, (255, 255, 255), (99, 190, 123)
          ),
          subset=[c],
      )
  for c in ["Down 4% Today", "Declines", "52W Lows"]:
    if c in df.columns:
      max_v = 750 if c == "Declines" else 200
      styler = safe_map(
          styler,
          lambda v, mv=max_v: color_scale_2pt(
              v, 0, mv, (255, 255, 255), (248, 105, 107)
          ),
          subset=[c],
      )
  for c in ["5 Day Ratio", "10 Day Ratio", "A/D Ratio", "Volume Breadth"]:
    if c in df.columns:
      styler = safe_map(
          styler,
          lambda v: color_scale_3pt(v, 0.5, 1.0, 2.0),
          subset=[c],
      )
  for c in ["> 200 SMA (%)", "> 50 SMA (%)", "> 20 EMA (%)", "> 10 EMA (%)"]:
    if c in df.columns:
      styler = safe_map(
          styler,
          lambda v: color_scale_3pt(v, 0.0, 50.0, 100.0),
          subset=[c],
      )
  if "Nifty 500 Chg %" in df.columns:
    styler = safe_map(
        styler,
        lambda v: color_scale_3pt(v, -2.0, 0.0, 2.0),
        subset=["Nifty 500 Chg %"],
    )
  try:
    styler = styler.hide(axis="index")
  except Exception:
    pass
  return styler


def style_sector_heatmap(df):
  styler = df.style
  format_dict = {}
  int_cols = ["65D RS Rank"]
  vel_cols = [
      "5D Rank Velocity",
      "10D Rank Velocity",
      "21D Rank Velocity",
      "65D Rank Velocity",
  ]
  float_cols = [
      "Close",
      "% Chg",
      "5D RS %",
      "21D RS %",
      "65D RS %",
      "% Off RS High",
  ]
  for col in int_cols:
    if col in df.columns:
      format_dict[col] = "{:.0f}"
  for col in vel_cols:
    if col in df.columns:
      format_dict[col] = "{:+.0f}"
  for col in float_cols:
    if col in df.columns:
      format_dict[col] = "{:.2f}"
  styler = styler.format(format_dict, na_rep="N/A")

  for c in vel_cols:
    if c in df.columns:
      styler = safe_map(
          styler,
          lambda v: color_scale_3pt(v, -10, 0, 10),
          subset=[c],
      )
  rs_cols = ["5D RS %", "21D RS %", "65D RS %"]
  for c in rs_cols:
    if c in df.columns:
      styler = safe_map(
          styler,
          lambda v: color_scale_3pt(v, -10, 0, 10),
          subset=[c],
      )
  if "% Off RS High" in df.columns:
    styler = safe_map(
        styler,
        lambda v: color_scale_3pt(v, -15.0, -5.0, 0.0),
        subset=["% Off RS High"],
    )
  bin_cols = [
      "RS Trend (>50 SMA)",
      "> 10 EMA",
      "> 20 EMA",
      "> 50 SMA",
      "> 200 SMA",
  ]
  for c in bin_cols:
    if c in df.columns:
      styler = safe_map(styler, color_binary_badge, subset=[c])
  try:
    styler = styler.hide(axis="index")
  except Exception:
    pass
  return styler


def style_rotation_tracker(df):
  styler = df.style
  sec_cols = [c for c in df.columns if c != "Date"]
  format_dict = {c: "{:.0f}" for c in sec_cols}
  styler = styler.format(format_dict, na_rep="N/A")

  num_sec = max(len(sec_cols), 1)
  mid_rank = max((num_sec // 2) + 1, 1)
  for c in sec_cols:
    styler = safe_map(
        styler,
        lambda v, ms=num_sec, mr=mid_rank: color_scale_3pt(
            v,
            1,
            mr,
            ms,
            c_min=(99, 190, 123),
            c_mid=(255, 255, 255),
            c_max=(248, 105, 107),
        ),
        subset=[c],
    )
  try:
    styler = styler.hide(axis="index")
  except Exception:
    pass
  return styler


# ==========================================
# 100% LEFT-ALIGNED & ZERO-TRUNCATION TABLE CONFIG
# ==========================================
def get_left_aligned_column_config(col_list):
  cfg = {}
  for col in col_list:
    if col == "TV_Link":
      cfg[col] = st.column_config.LinkColumn(
          "TradingView", display_text="↗️ Chart", alignment="left", width=85
      )
    elif col == "Screener_Link":
      cfg[col] = st.column_config.LinkColumn(
          "Screener.in", display_text="↗️ Screener", alignment="left", width=95
      )
    elif col in ["S.No.", "S.No._num"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=75)
    elif col == "TV_Symbol":
      cfg[col] = st.column_config.Column(col, alignment="left", width=135)
    elif col == "name":
      cfg[col] = st.column_config.Column(col, alignment="left", width=140)
    elif col in ["Date", "Sector"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=130)
    elif col == "Fundamental":
      cfg[col] = st.column_config.Column(col, alignment="left", width=155)
    elif "Rank Velocity" in col:
      cfg[col] = st.column_config.NumberColumn(
          col, alignment="left", format="%+d", width=125
      )
    elif col in ["Sector", "Basic Industry"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=220)
    elif col == "Industry":
      cfg[col] = st.column_config.Column(col, alignment="left", width=250)
    elif col in ["Close", "Change %", "ADR %"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=85)
    elif col in ["EPS Q YoY %", "Sales Q YoY %", "IPO Date"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=110)
    elif "Perf %" in col or "EMA" in col or "SMA" in col:
      cfg[col] = st.column_config.Column(col, alignment="left", width=85)
    elif col == "Market Cap (₹ Cr)":
      cfg[col] = st.column_config.Column(col, alignment="left", width=130)
    elif "Close×AvgVol" in col:
      cfg[col] = st.column_config.Column(col, alignment="left", width=150)
    elif col == "Stocks Passed":
      cfg[col] = st.column_config.Column(col, alignment="left", width=115)
    elif col == "% Share":
      cfg[col] = st.column_config.Column(col, alignment="left", width=90)
    elif col in ["% of Sector Total", "% of Industry Total"]:
      cfg[col] = st.column_config.Column(col, alignment="left", width=145)
    else:
      cfg[col] = st.column_config.Column(col, alignment="left", width=110)
  return cfg


# ==========================================
# REORDER CALLBACK FUNCTIONS
# ==========================================
def cb_move_top(wl_name, sym):
  lst = st.session_state.watchlists.get(wl_name, [])
  if sym in lst:
    lst.remove(sym)
    lst.insert(0, sym)
    save_watchlists(st.session_state.watchlists)


def cb_move_up(wl_name, sym):
  lst = st.session_state.watchlists.get(wl_name, [])
  if sym in lst:
    idx = lst.index(sym)
    if idx > 0:
      lst.pop(idx)
      lst.insert(idx - 1, sym)
      save_watchlists(st.session_state.watchlists)


def cb_move_down(wl_name, sym):
  lst = st.session_state.watchlists.get(wl_name, [])
  if sym in lst:
    idx = lst.index(sym)
    if idx < len(lst) - 1:
      lst.pop(idx)
      lst.insert(idx + 1, sym)
      save_watchlists(st.session_state.watchlists)


def cb_move_bottom(wl_name, sym):
  lst = st.session_state.watchlists.get(wl_name, [])
  if sym in lst:
    lst.remove(sym)
    lst.append(sym)
    save_watchlists(st.session_state.watchlists)


def cb_jump_rank(wl_name, sym, target_rank):
  lst = st.session_state.watchlists.get(wl_name, [])
  if sym in lst:
    lst.remove(sym)
    new_idx = max(0, min(len(lst), target_rank - 1))
    lst.insert(new_idx, sym)
    save_watchlists(st.session_state.watchlists)


st.title("📈 India Equities Screener & Watchlist Studio")
st.markdown(
    "Professional **CAN SLIM Screener**, **Hierarchical Sector Rotation**, and"
    " **Multi-Watchlist Studio with Free-Tier TradingView 30-Stock"
    " Hot-Swapping**."
)

# ==========================================
# 1. OFFICIAL 22 SECTORS & 59 INDUSTRIES
# ==========================================
INDIAN_SECTOR_HIERARCHY = {
    "Automobile and Auto Components": [
        "Automobiles",
        "Auto Components & Ancillaries",
        "Tyres & Rubber",
    ],
    "Capital Goods": [
        "Aerospace & Defense",
        "Electrical Equipment",
        "Engineering Services",
        "Industrial Manufacturing",
        "Industrial Products",
    ],
    "Chemicals": ["Chemicals & Petrochemicals", "Fertilizers & Agrochemicals"],
    "Construction": ["Civil Construction", "Infrastructure Developers"],
    "Construction Materials": [
        "Cement & Cement Products",
        "Ceramics & Building Materials",
    ],
    "Consumer Durables": [
        "Consumer Electronics & Appliances",
        "Gems, Jewellery & Watches",
        "Household & Personal Products",
    ],
    "Consumer Services": [
        "Leisure Services",
        "Restaurants & QSR",
        "Retailing",
        "Travel & Tourism",
    ],
    "Diversified": [
        "Diversified Commercial Services",
        "Diversified Industrials",
    ],
    "Fast Moving Consumer Goods": [
        "Agricultural Food & Other Products",
        "Beverages",
        "Food Products",
        "Personal Care",
        "Tobacco Products",
    ],
    "Financial Services": [
        "Asset Management",
        "Banks",
        "Capital Markets",
        "Finance & NBFCs",
        "Financial Technology (Fintech)",
        "Insurance",
    ],
    "Forest Materials": ["Paper, Forest & Jute Products"],
    "Healthcare": [
        "Healthcare Research, Analytics & Technology",
        "Healthcare Services",
        "Medical Equipment & Supplies",
        "Pharmaceuticals & Biotechnology",
    ],
    "Information Technology": [
        "IT - Hardware",
        "IT - Software & Consulting",
        "IT - Services",
    ],
    "Media, Entertainment & Publication": [
        "Broadcasting & Cable TV",
        "Entertainment & Content",
        "Print Media & Publishing",
    ],
    "Metals & Mining": [
        "Ferrous Metals (Steel & Iron)",
        "Non-Ferrous Metals",
        "Minerals & Mining",
    ],
    "Oil, Gas & Consumable Fuels": [
        "Consumable Fuels & Coal",
        "Oil & Gas Exploration & Production",
        "Petroleum Products & Refining",
    ],
    "Power": ["Power Generation", "Power Transmission & Distribution"],
    "Realty": ["Real Estate Developers", "Real Estate Services"],
    "Services": [
        "Commercial & Professional Services",
        "Logistics & Transportation Services",
        "Port & Shipping Services",
    ],
    "Telecommunication": [
        "Telecom - Equipment & Accessories",
        "Telecom - Services",
    ],
    "Textiles": ["Garments & Apparels", "Textiles & Weaving"],
    "Utilities": ["Gas Transmission & Utilities", "Water & Other Utilities"],
}

TV_TO_INDIAN_MAP = {
    ("Commercial Services", "Financial Publishing/Services"): (
        "Financial Services",
        "Capital Markets",
    ),
    ("Commercial Services", "Miscellaneous Commercial Services"): (
        "Services",
        "Commercial & Professional Services",
    ),
    ("Commercial Services", "Personnel Services"): (
        "Services",
        "Commercial & Professional Services",
    ),
    ("Consumer Durables", "Automotive Aftermarket"): (
        "Automobile and Auto Components",
        "Auto Components & Ancillaries",
    ),
    ("Consumer Durables", "Electronics/Appliances"): (
        "Consumer Durables",
        "Consumer Electronics & Appliances",
    ),
    ("Consumer Durables", "Home Furnishings"): (
        "Consumer Durables",
        "Household & Personal Products",
    ),
    ("Consumer Durables", "Homebuilding"): ("Realty", "Real Estate Developers"),
    ("Consumer Durables", "Motor Vehicles"): (
        "Automobile and Auto Components",
        "Automobiles",
    ),
    ("Consumer Durables", "Other Consumer Specialties"): (
        "Consumer Durables",
        "Gems, Jewellery & Watches",
    ),
    ("Consumer Non-Durables", "Apparel/Footwear"): (
        "Textiles",
        "Garments & Apparels",
    ),
    ("Consumer Non-Durables", "Beverages: Alcoholic"): (
        "Fast Moving Consumer Goods",
        "Beverages",
    ),
    ("Consumer Non-Durables", "Food: Major Diversified"): (
        "Fast Moving Consumer Goods",
        "Food Products",
    ),
    ("Consumer Non-Durables", "Food: Specialty/Candy"): (
        "Fast Moving Consumer Goods",
        "Food Products",
    ),
    ("Consumer Non-Durables", "Household/Personal Care"): (
        "Fast Moving Consumer Goods",
        "Personal Care",
    ),
    ("Consumer Services", "Broadcasting"): (
        "Media, Entertainment & Publication",
        "Broadcasting & Cable TV",
    ),
    ("Consumer Services", "Hotels/Resorts/Cruise lines"): (
        "Consumer Services",
        "Travel & Tourism",
    ),
    ("Consumer Services", "Movies/Entertainment"): (
        "Media, Entertainment & Publication",
        "Entertainment & Content",
    ),
    ("Consumer Services", "Publishing: Books/Magazines"): (
        "Media, Entertainment & Publication",
        "Print Media & Publishing",
    ),
    ("Consumer Services", "Restaurants"): (
        "Consumer Services",
        "Restaurants & QSR",
    ),
    ("Distribution Services", "Electronics Distributors"): (
        "Capital Goods",
        "Industrial Products",
    ),
    ("Distribution Services", "Medical Distributors"): (
        "Healthcare",
        "Medical Equipment & Supplies",
    ),
    ("Distribution Services", "Wholesale Distributors"): (
        "Services",
        "Commercial & Professional Services",
    ),
    ("Electronic Technology", "Aerospace & Defense"): (
        "Capital Goods",
        "Aerospace & Defense",
    ),
    ("Electronic Technology", "Computer Communications"): (
        "Telecommunication",
        "Telecom - Equipment & Accessories",
    ),
    ("Electronic Technology", "Computer Peripherals"): (
        "Information Technology",
        "IT - Hardware",
    ),
    ("Electronic Technology", "Electronic Components"): (
        "Capital Goods",
        "Electrical Equipment",
    ),
    ("Electronic Technology", "Electronic Equipment/Instruments"): (
        "Capital Goods",
        "Electrical Equipment",
    ),
    ("Electronic Technology", "Electronic Production Equipment"): (
        "Capital Goods",
        "Industrial Manufacturing",
    ),
    ("Electronic Technology", "Telecommunications Equipment"): (
        "Telecommunication",
        "Telecom - Equipment & Accessories",
    ),
    ("Energy Minerals", "Oil & Gas Production"): (
        "Oil, Gas & Consumable Fuels",
        "Oil & Gas Exploration & Production",
    ),
    ("Energy Minerals", "Oil Refining/Marketing"): (
        "Oil, Gas & Consumable Fuels",
        "Petroleum Products & Refining",
    ),
    ("Finance", "Finance/Rental/Leasing"): ("Financial Services", "Finance & NBFCs"),
    ("Finance", "Financial Conglomerates"): (
        "Financial Services",
        "Finance & NBFCs",
    ),
    ("Finance", "Investment Banks/Brokers"): (
        "Financial Services",
        "Capital Markets",
    ),
    ("Finance", "Investment Managers"): (
        "Financial Services",
        "Asset Management",
    ),
    ("Finance", "Life/Health Insurance"): ("Financial Services", "Insurance"),
    ("Finance", "Major Banks"): ("Financial Services", "Banks"),
    ("Finance", "Multi-Line Insurance"): ("Financial Services", "Insurance"),
    ("Finance", "Real Estate Development"): ("Realty", "Real Estate Developers"),
    ("Finance", "Regional Banks"): ("Financial Services", "Banks"),
    ("Health Services", "Hospital/Nursing Management"): (
        "Healthcare",
        "Healthcare Services",
    ),
    ("Health Services", "Medical/Nursing Services"): (
        "Healthcare",
        "Healthcare Services",
    ),
    ("Health Technology", "Biotechnology"): (
        "Healthcare",
        "Pharmaceuticals & Biotechnology",
    ),
    ("Health Technology", "Medical Specialties"): (
        "Healthcare",
        "Medical Equipment & Supplies",
    ),
    ("Health Technology", "Pharmaceuticals: Generic"): (
        "Healthcare",
        "Pharmaceuticals & Biotechnology",
    ),
    ("Health Technology", "Pharmaceuticals: Major"): (
        "Healthcare",
        "Pharmaceuticals & Biotechnology",
    ),
    ("Health Technology", "Pharmaceuticals: Other"): (
        "Healthcare",
        "Pharmaceuticals & Biotechnology",
    ),
    ("Industrial Services", "Contract Drilling"): (
        "Oil, Gas & Consumable Fuels",
        "Oil & Gas Exploration & Production",
    ),
    ("Industrial Services", "Engineering & Construction"): (
        "Construction",
        "Civil Construction",
    ),
    ("Industrial Services", "Oilfield Services/Equipment"): (
        "Oil, Gas & Consumable Fuels",
        "Oil & Gas Exploration & Production",
    ),
    ("Non-Energy Minerals", "Construction Materials"): (
        "Construction Materials",
        "Ceramics & Building Materials",
    ),
    ("Non-Energy Minerals", "Forest Products"): (
        "Forest Materials",
        "Paper, Forest & Jute Products",
    ),
    ("Non-Energy Minerals", "Other Metals/Minerals"): (
        "Metals & Mining",
        "Minerals & Mining",
    ),
    ("Non-Energy Minerals", "Steel"): (
        "Metals & Mining",
        "Ferrous Metals (Steel & Iron)",
    ),
    ("Process Industries", "Agricultural Commodities/Milling"): (
        "Fast Moving Consumer Goods",
        "Agricultural Food & Other Products",
    ),
    ("Process Industries", "Chemicals: Agricultural"): (
        "Chemicals",
        "Fertilizers & Agrochemicals",
    ),
    ("Process Industries", "Chemicals: Major Diversified"): (
        "Chemicals",
        "Chemicals & Petrochemicals",
    ),
    ("Process Industries", "Chemicals: Specialty"): (
        "Chemicals",
        "Chemicals & Petrochemicals",
    ),
    ("Process Industries", "Containers/Packaging"): (
        "Capital Goods",
        "Industrial Products",
    ),
    ("Process Industries", "Industrial Specialties"): (
        "Capital Goods",
        "Industrial Manufacturing",
    ),
    ("Process Industries", "Pulp & Paper"): (
        "Forest Materials",
        "Paper, Forest & Jute Products",
    ),
    ("Process Industries", "Textiles"): ("Textiles", "Textiles & Weaving"),
    ("Producer Manufacturing", "Auto Parts: OEM"): (
        "Automobile and Auto Components",
        "Auto Components & Ancillaries",
    ),
    ("Producer Manufacturing", "Building Products"): (
        "Construction Materials",
        "Cement & Cement Products",
    ),
    ("Producer Manufacturing", "Electrical Products"): (
        "Capital Goods",
        "Electrical Equipment",
    ),
    ("Producer Manufacturing", "Industrial Machinery"): (
        "Capital Goods",
        "Industrial Manufacturing",
    ),
    ("Producer Manufacturing", "Metal Fabrication"): (
        "Capital Goods",
        "Industrial Manufacturing",
    ),
    ("Producer Manufacturing", "Miscellaneous Manufacturing"): (
        "Capital Goods",
        "Industrial Products",
    ),
    ("Producer Manufacturing", "Office Equipment/Supplies"): (
        "Consumer Durables",
        "Household & Personal Products",
    ),
    ("Producer Manufacturing", "Trucks/Construction/Farm Machinery"): (
        "Automobile and Auto Components",
        "Automobiles",
    ),
    ("Retail Trade", "Apparel/Footwear Retail"): (
        "Consumer Services",
        "Retailing",
    ),
    ("Retail Trade", "Electronics/Appliance Stores"): (
        "Consumer Services",
        "Retailing",
    ),
    ("Retail Trade", "Internet Retail"): ("Consumer Services", "Retailing"),
    ("Retail Trade", "Specialty Stores"): ("Consumer Services", "Retailing"),
    ("Technology Services", "Information Technology Services"): (
        "Information Technology",
        "IT - Services",
    ),
    ("Technology Services", "Internet Software/Services"): (
        "Information Technology",
        "IT - Software & Consulting",
    ),
    ("Technology Services", "Packaged Software"): (
        "Information Technology",
        "IT - Software & Consulting",
    ),
    ("Transportation", "Air Freight/Couriers"): (
        "Services",
        "Logistics & Transportation Services",
    ),
    ("Transportation", "Airlines"): ("Consumer Services", "Travel & Tourism"),
    ("Transportation", "Marine Shipping"): (
        "Services",
        "Port & Shipping Services",
    ),
    ("Transportation", "Other Transportation"): (
        "Services",
        "Logistics & Transportation Services",
    ),
    ("Transportation", "Railroads"): (
        "Services",
        "Logistics & Transportation Services",
    ),
    ("Utilities", "Electric Utilities"): ("Power", "Power Generation"),
    ("Utilities", "Gas Distributors"): ("Utilities", "Gas Transmission & Utilities"),
}


def map_to_indian_classification(tv_industry, tv_sector):
  mapped = TV_TO_INDIAN_MAP.get((tv_sector, tv_industry))
  if mapped:
    return mapped
  return "Diversified", "Diversified Commercial Services"


def parse_chart_selection_multi(event):
  if event and isinstance(event, dict):
    sel = event.get("selection", {})
    points = sel.get("points", [])
    if points:
      return [p.get("label") for p in points if p.get("label")]
  return []


def parse_table_selection_multi(event, df_source, col_name):
  if event and isinstance(event, dict):
    sel = event.get("selection", {})
    rows = sel.get("rows", [])
    if rows:
      selected_vals = []
      for idx in rows:
        if idx < len(df_source):
          selected_vals.append(df_source.iloc[idx][col_name])
      return selected_vals
  return []


def parse_pasted_tickers(raw_text):
  if not raw_text:
    return []
  tokens = re.split(r"[,\\n\\r\\t;]+", raw_text)
  cleaned = []
  for t in tokens:
    t = t.strip().upper()
    t = re.sub(r"[^A-Z0-9:]", "", t)
    if not t:
      continue
    if ":" not in t:
      t = f"NSE:{t}"
    if t not in cleaned:
      cleaned.append(t)
  return cleaned


# ==========================================
# MULTI-ALIAS COALESCING HELPER
# ==========================================
def coalesce_columns(df, col_list):
  res = pd.Series(index=df.index, dtype="float64")
  for c in col_list:
    if c in df.columns:
      s = pd.to_numeric(df[c], errors="coerce")
      res = res.fillna(s)
  return res


# ==========================================
# ROBUST MULTI-ALIAS IPO DATE HELPER
# ==========================================
def clean_tv_date_col(val_series):
  num_s = pd.to_numeric(val_series, errors="coerce")
  num_valid = num_s.where(num_s > 0)
  dt_unix_s = pd.to_datetime(
      num_valid.where(num_valid <= 1e11), unit="s", errors="coerce"
  )
  dt_unix_ms = pd.to_datetime(
      num_valid.where(num_valid > 1e11), unit="ms", errors="coerce"
  )
  dt_unix = dt_unix_s.fillna(dt_unix_ms)
  dt_iso = pd.to_datetime(val_series, errors="coerce")
  dt_combined = dt_unix.fillna(dt_iso)
  return dt_combined.where(dt_combined >= pd.Timestamp("1980-01-01"), pd.NaT)


def add_clean_ipo_date_col(df):
  ipo_cols = [
      c
      for c in [
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
      ]
      if c in df.columns
  ]
  if ipo_cols:
    clean_dt_df = pd.DataFrame(index=df.index)
    for c in ipo_cols:
      clean_dt_df[c] = clean_tv_date_col(df[c])
    df["IPO_Date_DT"] = clean_dt_df.max(axis=1)
  else:
    df["IPO_Date_DT"] = pd.NaT
  df["IPO Date"] = df["IPO_Date_DT"].dt.strftime("%Y-%m-%d").fillna("N/A")
  return df


# ==========================================
# 2. BACKEND API QUERIES
# ==========================================
EPS_Q_ALIASES = [
    "earnings_per_share_diluted_yoy_growth_fq",
    "earnings_per_share_fq_yoy_growth",
    "earnings_per_share_diluted_yoy_growth_quarterly",
    "basic_eps_yoy_growth_fq",
]

SALES_Q_ALIASES = [
    "revenue_yoy_growth_fq",
    "total_revenue_yoy_growth_fq",
    "revenue_yoy_growth_quarterly",
    "sales_yoy_growth_fq",
]


def fetch_screener_data(
    exchanges, min_mcap, vol_period_days, ma_columns_to_fetch, limit_rows
):
  if not exchanges:
    return pd.DataFrame()
  min_mcap_inr = min_mcap * 10_000_000
  tv_vol_col = f"average_volume_{vol_period_days}d_calc"
  select_cols = (
      [
          "name",
          "close",
          "change",
          "high",
          "low",
          "open",
          "volume",
          "market_cap_basic",
          tv_vol_col,
          "ADR",
          "price_52_week_high",
          "price_52_week_low",
          "exchange",
          "type",
          "industry",
          "sector",
          "index",
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
          "Perf.W",
          "Perf.1M",
          "Perf.3M",
          "Perf.6M",
          "Perf.YTD",
          "Perf.Y",
      ]
      + EPS_Q_ALIASES
      + SALES_Q_ALIASES
  )

  for c in ma_columns_to_fetch:
    if c not in select_cols:
      select_cols.append(c)
  q = (
      Query()
      .set_markets("india")
      .select(*select_cols)
      .where(col("market_cap_basic") >= min_mcap_inr)
      .order_by("volume", ascending=False)
      .limit(limit_rows)
  )
  try:
    _, df = q.get_scanner_data()
    return df
  except Exception as e:
    st.error(f"Error fetching data from TradingView API: {e}")
    return pd.DataFrame()


def fetch_watchlist_enrichMENT(symbol_list):
  if not symbol_list:
    return pd.DataFrame()
  bare_names = [s.split(":")[-1].strip().upper() for s in symbol_list]
  select_cols = (
      [
          "name",
          "close",
          "change",
          "ADR",
          "market_cap_basic",
          "exchange",
          "industry",
          "sector",
          "index",
          "ipo_offer_date",
          "offer_date",
          "recent_ipo_date",
          "ipo_date",
          "listing_date",
          "Perf.W",
          "Perf.1M",
          "Perf.3M",
          "Perf.6M",
          "Perf.YTD",
          "Perf.Y",
      ]
      + EPS_Q_ALIASES
      + SALES_Q_ALIASES
  )

  q = (
      Query()
      .set_markets("india")
      .select(*select_cols)
      .where(col("name").isin(bare_names))
      .limit(max(len(bare_names) * 5, 1500))
  )
  try:
    _, df = q.get_scanner_data()
    if not df.empty:
      df["ADR_pct"] = ((df["ADR"] / df["close"]) * 100).round(2)
      df["Close"] = df["close"].round(2)
      df["Change %"] = df["change"].round(2)
      df["Market Cap (₹ Cr)"] = (df["market_cap_basic"] / 10_000_000).round(2)
      df["EPS Q YoY %"] = coalesce_columns(df, EPS_Q_ALIASES).round(2)
      df["Sales Q YoY %"] = coalesce_columns(df, SALES_Q_ALIASES).round(2)
      df = add_clean_ipo_date_col(df)

      if "Perf.W" in df.columns:
        df["Perf % 1W"] = pd.to_numeric(df["Perf.W"], errors="coerce").round(2)
      if "Perf.1M" in df.columns:
        df["Perf % 1M"] = pd.to_numeric(df["Perf.1M"], errors="coerce").round(2)
      if "Perf.3M" in df.columns:
        df["Perf % 3M"] = pd.to_numeric(df["Perf.3M"], errors="coerce").round(2)
      if "Perf.6M" in df.columns:
        df["Perf % 6M"] = pd.to_numeric(df["Perf.6M"], errors="coerce").round(2)
      if "Perf.YTD" in df.columns:
        df["Perf % YTD"] = pd.to_numeric(
            df["Perf.YTD"], errors="coerce"
        ).round(2)
      if "Perf.Y" in df.columns:
        df["Perf % 1Y"] = pd.to_numeric(df["Perf.Y"], errors="coerce").round(2)

      df = df.drop_duplicates(subset=["name"], keep="first")

      mapped_sectors, mapped_industries = [], []
      for _, row in df.iterrows():
        sec, ind = map_to_indian_classification(
            row.get("industry", ""), row.get("sector", "")
        )
        mapped_sectors.append(sec)
        mapped_industries.append(ind)
      df["Sector"] = mapped_sectors
      df["Industry"] = mapped_industries
    return df
  except Exception:
    return pd.DataFrame()


# ==========================================
# 3. SIDEBAR CONTROLS & STRATEGY PRESETS
# ==========================================
st.sidebar.markdown("### 💾 Saved Filter Presets")
preset_names = list(st.session_state.filter_presets.keys())
selected_preset_name = st.sidebar.selectbox(
    "Load or Update Strategy Preset:",
    options=preset_names,
    index=0 if preset_names else None,
    key="sb_preset_selector",
)

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
      st.session_state["f_ipo"] = p.get(
          "ipo_filter", "All Stocks (No IPO Filter)"
      )
      st.session_state["f_en_eps_q"] = p.get("en_eps_q", False)
      st.session_state["f_min_eps_q"] = p.get("min_eps_q", 10.0)
      st.session_state["f_en_sales_q"] = p.get("en_sales_q", False)
      st.session_state["f_min_sales_q"] = p.get("min_sales_q", 10.0)
      st.session_state["f_allow_na_growth"] = p.get("allow_na_growth", True)
      st.session_state["f_en_adr"] = p.get("en_adr", True)
      st.session_state["f_min_adr"] = p.get("min_adr", 2.25)
      st.session_state["f_en_52l"] = p.get("en_above_52l", True)
      st.session_state["f_min_52l"] = p.get("min_above_52l", 20)
      st.session_state["f_en_52h"] = p.get("en_below_52h", True)
      st.session_state["f_max_52h"] = p.get("max_below_52h", 30)
      st.session_state["f_en_circuit"] = p.get("en_circuit", True)

      c_val = p.get("circuit_val", ["2%", "5%", "10%"])
      if isinstance(c_val, str):
        c_val = ["2%", "5%", "10%"]
      st.session_state["f_circuit_val"] = c_val

      st.session_state["f_perf_labels"] = p.get(
          "selected_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
      )
      st.session_state["f_max_res"] = p.get("max_results", 4000)

      ma_cfgs = p.get("ma_configs", [])
      for i, cfg in enumerate(ma_cfgs, 1):
        st.session_state[f"ma_{i}_en"] = cfg.get("en", False)
        st.session_state[f"ma_{i}_type"] = cfg.get("type", "SMA")
        st.session_state[f"ma_{i}_len"] = cfg.get("len", 50)

      perf_cfgs = p.get("perf_configs", {})
      for c_key, p_val in perf_cfgs.items():
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
          "ipo_filter": st.session_state.get(
              "f_ipo", "All Stocks (No IPO Filter)"
          ),
          "en_eps_q": st.session_state.get("f_en_eps_q", False),
          "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
          "en_sales_q": st.session_state.get("f_en_sales_q", False),
          "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
          "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
          "en_adr": st.session_state.get("f_en_adr", True),
          "min_adr": st.session_state.get("f_min_adr", 2.25),
          "en_above_52l": st.session_state.get("f_en_52l", True),
          "min_above_52l": st.session_state.get("f_min_52l", 20),
          "en_below_52h": st.session_state.get("f_en_52h", True),
          "max_below_52h": st.session_state.get("f_max_52h", 30),
          "en_circuit": st.session_state.get("f_en_circuit", True),
          "circuit_val": st.session_state.get(
              "f_circuit_val", ["2%", "5%", "10%"]
          ),
          "selected_perf_labels": st.session_state.get(
              "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
          ),
          "max_results": st.session_state.get("f_max_res", 4000),
          "ma_configs": [
              {
                  "en": st.session_state.get(f"ma_{i}_en", False),
                  "type": st.session_state.get(f"ma_{i}_type", "SMA"),
                  "len": st.session_state.get(f"ma_{i}_len", 50),
              }
              for i in range(1, 6)
          ],
          "perf_configs": {
              col: {
                  "en": st.session_state.get(f"en_perf_{col}", False),
                  "val": st.session_state.get(f"val_perf_{col}", 0.0),
              }
              for col in [
                  "Perf.W",
                  "Perf.1M",
                  "Perf.3M",
                  "Perf.6M",
                  "Perf.YTD",
                  "Perf.Y",
              ]
          },
      }
      save_filter_presets(st.session_state.filter_presets)
      st.success(f"Updated '{selected_preset_name}'!")
      st.rerun()

with col_del:
  if st.sidebar.button("🗑️ Del", use_container_width=True):
    if (
        len(preset_names) > 1
        and selected_preset_name in st.session_state.filter_presets
    ):
      del st.session_state.filter_presets[selected_preset_name]
      save_filter_presets(st.session_state.filter_presets)
      st.rerun()

with st.sidebar.expander("➕ Save Current Filters as New Preset"):
  with st.form("save_preset_form", clear_on_submit=True):
    new_preset_name = st.text_input(
        "Preset Name:", placeholder="e.g., Breakout Momentum"
    )
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
            "ipo_filter": st.session_state.get(
                "f_ipo", "All Stocks (No IPO Filter)"
            ),
            "en_eps_q": st.session_state.get("f_en_eps_q", False),
            "min_eps_q": st.session_state.get("f_min_eps_q", 10.0),
            "en_sales_q": st.session_state.get("f_en_sales_q", False),
            "min_sales_q": st.session_state.get("f_min_sales_q", 10.0),
            "allow_na_growth": st.session_state.get("f_allow_na_growth", True),
            "en_adr": st.session_state.get("f_en_adr", True),
            "min_adr": st.session_state.get("f_min_adr", 2.25),
            "en_above_52l": st.session_state.get("f_en_52l", True),
            "min_above_52l": st.session_state.get("f_min_52l", 20),
            "en_below_52h": st.session_state.get("f_en_52h", True),
            "max_below_52h": st.session_state.get("f_max_52h", 30),
            "en_circuit": st.session_state.get("f_en_circuit", True),
            "circuit_val": st.session_state.get(
                "f_circuit_val", ["2%", "5%", "10%"]
            ),
            "selected_perf_labels": st.session_state.get(
                "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
            ),
            "max_results": st.session_state.get("f_max_res", 4000),
            "ma_configs": [
                {
                    "en": st.session_state.get(f"ma_{i}_en", False),
                    "type": st.session_state.get(f"ma_{i}_type", "SMA"),
                    "len": st.session_state.get(f"ma_{i}_len", 50),
                }
                for i in range(1, 6)
            ],
            "perf_configs": {
                col: {
                    "en": st.session_state.get(f"en_perf_{col}", False),
                    "val": st.session_state.get(f"val_perf_{col}", 0.0),
                }
                for col in [
                    "Perf.W",
                    "Perf.1M",
                    "Perf.3M",
                    "Perf.6M",
                    "Perf.YTD",
                    "Perf.Y",
                ]
            },
        }
        save_filter_presets(st.session_state.filter_presets)
        st.success(f"Saved preset '{new_preset_name}'!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚡ **Auto-Update Enabled:** Adjusting any filter below updates results"
    " instantly."
)

# ----------------------------------------------------
# 1. EXCHANGE & UNIVERSE
# ----------------------------------------------------
st.sidebar.header("1. Exchange & Universe")
exchange_choice = st.sidebar.multiselect(
    "Select Exchanges:",
    options=["NSE", "BSE"],
    default=st.session_state.get("f_exchanges", ["NSE", "BSE"]),
    key="f_exchanges",
)

st.sidebar.markdown("---")
st.sidebar.header("🏛️ Official NSE Filters & Indices")
sector_options = list(INDIAN_SECTOR_HIERARCHY.keys())
sector_choice = st.sidebar.multiselect(
    "NSE Sector (22 Economic Sectors):",
    options=sector_options,
    default=st.session_state.get("f_sectors", []),
    key="f_sectors",
)

if sector_choice:
  industry_options = []
  for sec in sector_choice:
    industry_options.extend(INDIAN_SECTOR_HIERARCHY.get(sec, []))
  industry_options = sorted(list(set(industry_options)))
else:
  all_industries = [
      ind for inds in INDIAN_SECTOR_HIERARCHY.values() for ind in inds
  ]
  industry_options = sorted(list(set(all_industries)))

industry_choice = st.sidebar.multiselect(
    "NSE Industry (59 Distinct Classifications):",
    options=industry_options,
    default=st.session_state.get("f_industries", []),
    key="f_industries",
)

exhaustive_indices = [
    "NIFTY 50",
    "NIFTY NEXT 50",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY 500",
    "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50",
    "NIFTY SMALLCAP 100",
    "NIFTY SMALLCAP 250",
    "NIFTY MICROCAP 250",
    "NIFTY TOTAL MARKET",
    "NIFTY LARGEMIDCAP 250",
    "NIFTY BANK",
    "NIFTY AUTO",
    "NIFTY FINANCIAL SERVICES",
    "NIFTY FMCG",
    "NIFTY IT",
    "NIFTY MEDIA",
    "NIFTY METAL",
    "NIFTY PHARMA",
    "NIFTY PSU BANK",
    "NIFTY PRIVATE BANK",
    "NIFTY REALTY",
    "NIFTY HEALTHCARE",
    "NIFTY CONSUMER DURABLES",
    "NIFTY OIL & GAS",
    "NIFTY COMMODITIES",
    "NIFTY INDIA CONSUMPTION",
    "NIFTY CPSE",
    "NIFTY INFRASTRUCTURE",
    "NIFTY MNC",
    "NIFTY PSE",
    "NIFTY SERVICES SECTOR",
    "NIFTY ENERGY",
    "NIFTY HOUSING",
    "NIFTY INDIA DEFENCE",
    "NIFTY INDIA DIGITAL",
    "NIFTY INDIA MANUFACTURING",
    "NIFTY MOBILITY",
    "BSE SENSEX",
    "BSE 100",
    "BSE 200",
    "BSE 500",
]
index_choice = st.sidebar.multiselect(
    "Index Membership (45+ Available):",
    options=exhaustive_indices,
    default=st.session_state.get("f_indices", []),
    key="f_indices",
)

st.sidebar.markdown("---")
st.sidebar.header("2. Fundamental, Liquidity & IPO Date")
min_mcap_cr = st.sidebar.number_input(
    "Min Market Cap (₹ Crores):",
    min_value=0,
    value=st.session_state.get("f_min_mcap", 1000),
    step=100,
    key="f_min_mcap",
)
vol_period_days = st.sidebar.selectbox(
    "Average Volume Period:",
    options=[10, 30, 60, 90],
    index=[10, 30, 60, 90].index(st.session_state.get("f_vol_period", 60)),
    format_func=lambda x: f"{x} Days",
    key="f_vol_period",
)
min_vol_cr = st.sidebar.number_input(
    f"Min {vol_period_days}D Avg Rupee Volume (₹ Cr):",
    min_value=0.0,
    value=st.session_state.get("f_min_vol", 5.0),
    step=0.5,
    key="f_min_vol",
)

en_ipo = st.sidebar.checkbox(
    "Filter by IPO Listing Age",
    value=st.session_state.get("f_en_ipo", False),
    key="f_en_ipo",
)
ipo_filter_options = [
    "All Stocks (No IPO Filter)",
    "Recent IPO: Past 1 Month",
    "Recent IPO: Past 3 Months",
    "Recent IPO: Past 6 Months",
    "Recent IPO: Past 1 Year",
    "Recent IPO: Past 2 Years",
    "Seasoned: Listed > 1 Year Ago",
    "Seasoned: Listed > 3 Years Ago",
    "Seasoned: Listed > 5 Years Ago",
]
ipo_filter_choice = st.sidebar.selectbox(
    "IPO Date / Listing Age Filter:",
    options=ipo_filter_options,
    index=ipo_filter_options.index(
        st.session_state.get("f_ipo", "All Stocks (No IPO Filter)")
    ),
    key="f_ipo",
    disabled=not en_ipo,
)

# ----------------------------------------------------
# 2B. QUARTERLY YOY FUNDAMENTAL GROWTH
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("2B. Quarterly YoY Fundamental Growth")

en_eps_q = st.sidebar.checkbox(
    "Filter by Min Quarterly YoY EPS Growth %",
    value=st.session_state.get("f_en_eps_q", False),
    key="f_en_eps_q",
)
min_eps_q = st.sidebar.slider(
    "Min Quarterly YoY EPS Growth %:",
    min_value=-50.0,
    max_value=200.0,
    value=float(st.session_state.get("f_min_eps_q", 10.0)),
    step=5.0,
    key="f_min_eps_q",
    disabled=not en_eps_q,
)

en_sales_q = st.sidebar.checkbox(
    "Filter by Min Quarterly YoY Sales Growth %",
    value=st.session_state.get("f_en_sales_q", False),
    key="f_en_sales_q",
)
min_sales_q = st.sidebar.slider(
    "Min Quarterly YoY Sales Growth %:",
    min_value=-50.0,
    max_value=200.0,
    value=float(st.session_state.get("f_min_sales_q", 10.0)),
    step=5.0,
    key="f_min_sales_q",
    disabled=not en_sales_q,
)

allow_na_growth = st.sidebar.checkbox(
    "Pass stocks with missing (N/A) TradingView growth data",
    value=st.session_state.get("f_allow_na_growth", True),
    key="f_allow_na_growth",
    help=(
        "TradingView sometimes lags on quarterly data for Indian small-caps."
        " Checking this ensures great technical setups aren't dropped."
    ),
)

st.sidebar.markdown("---")
st.sidebar.header("3. Trend & Moving Averages (5 MAs)")
default_ma_configs = [
    {"en": True, "type": "EMA", "len": 21},
    {"en": True, "type": "SMA", "len": 50},
    {"en": False, "type": "SMA", "len": 200},
    {"en": False, "type": "EMA", "len": 10},
    {"en": False, "type": "SMA", "len": 150},
]
ma_filters = []
for i, cfg in enumerate(default_ma_configs, 1):
  c1, c2, c3 = st.sidebar.columns([1.8, 1.6, 1.6])
  with c1:
    en = st.checkbox(
        f"MA {i} >",
        value=st.session_state.get(f"ma_{i}_en", cfg["en"]),
        key=f"ma_{i}_en",
    )
  with c2:
    m_type = st.selectbox(
        "Type",
        ["EMA", "SMA"],
        index=0 if st.session_state.get(f"ma_{i}_type", cfg["type"]) == "EMA" else 1,
        key=f"ma_{i}_type",
        label_visibility="collapsed",
    )
  with c3:
    m_len = st.number_input(
        "Len",
        min_value=1,
        max_value=500,
        value=st.session_state.get(f"ma_{i}_len", cfg["len"]),
        step=1,
        key=f"ma_{i}_len",
        label_visibility="collapsed",
    )
  col_name = f"{m_type}{m_len}"
  ma_filters.append({
      "enabled": en,
      "type": m_type,
      "length": m_len,
      "col_name": col_name,
      "label": f"{m_type} {m_len}",
  })

# ----------------------------------------------------
# 4. VOLATILITY & 52-WEEK RANGE
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("4. Volatility & 52-Week Range")

en_adr = st.sidebar.checkbox(
    "Filter by Min ADR %",
    value=st.session_state.get("f_en_adr", True),
    key="f_en_adr",
)
min_adr = st.sidebar.slider(
    "Min ADR % (TradingView Standard):",
    min_value=0.0,
    max_value=10.0,
    value=st.session_state.get("f_min_adr", 2.25),
    step=0.25,
    key="f_min_adr",
    disabled=not en_adr,
)

en_52l = st.sidebar.checkbox(
    "Filter by Min % Above 52-Week Low",
    value=st.session_state.get("f_en_52l", True),
    key="f_en_52l",
)
min_above_52l = st.sidebar.slider(
    "Min % Above 52-Week Low:",
    min_value=0,
    max_value=100,
    value=st.session_state.get("f_min_52l", 20),
    step=5,
    key="f_min_52l",
    disabled=not en_52l,
)

en_52h = st.sidebar.checkbox(
    "Filter by Max % Below 52-Week High",
    value=st.session_state.get("f_en_52h", True),
    key="f_en_52h",
)
max_below_52h = st.sidebar.slider(
    "Max % Below 52-Week High:",
    min_value=0,
    max_value=50,
    value=st.session_state.get("f_max_52h", 30),
    step=5,
    key="f_max_52h",
    disabled=not en_52h,
)

# ----------------------------------------------------
# 4B. CIRCUIT LIMIT & FREEZE PROTECTION (MULTI-SELECT)
# ----------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("4B. Circuit Limit Protection")

c_cb, c_sb = st.sidebar.columns([1.1, 1.4])
with c_cb:
  en_circuit = st.checkbox(
      "Exclude Circuit:",
      value=st.session_state.get("f_en_circuit", True),
      key="f_en_circuit",
  )
with c_sb:
  circuit_options = ["2%", "5%", "10%"]
  default_circuits = st.session_state.get("f_circuit_val", ["2%", "5%", "10%"])
  if isinstance(default_circuits, str):
    default_circuits = ["2%", "5%", "10%"]

  circuit_choice = st.multiselect(
      "Circuit Bands to Exclude:",
      options=circuit_options,
      default=default_circuits,
      key="f_circuit_val",
      disabled=not en_circuit,
      label_visibility="collapsed",
      placeholder="Select bands...",
  )

st.sidebar.markdown("---")
st.sidebar.header("5. Performance % (Relative Strength)")
perf_options = {
    "1 Week": ("Perf.W", "Perf % 1W"),
    "1 Month": ("Perf.1M", "Perf % 1M"),
    "3 Months": ("Perf.3M", "Perf % 3M"),
    "6 Months": ("Perf.6M", "Perf % 6M"),
    "YTD": ("Perf.YTD", "Perf % YTD"),
    "1 Year": ("Perf.Y", "Perf % 1Y"),
}
selected_perf_labels = st.sidebar.multiselect(
    "Display Perf % Columns in Table:",
    options=list(perf_options.keys()),
    default=st.session_state.get(
        "f_perf_labels", ["1 Week", "1 Month", "3 Months", "6 Months"]
    ),
    key="f_perf_labels",
)

st.sidebar.caption("Optional Minimum Performance % Thresholds:")
perf_filters = []
p_cols = st.sidebar.columns(2)
for idx, (label, (tv_col, disp_label)) in enumerate(perf_options.items()):
  with p_cols[idx % 2]:
    en_p = st.checkbox(
        f"Min {label} >",
        value=st.session_state.get(f"en_perf_{tv_col}", False),
        key=f"en_perf_{tv_col}",
    )
    min_val = st.number_input(
        f"Min % ({label})",
        min_value=-100.0,
        max_value=10000.0,
        value=st.session_state.get(f"val_perf_{tv_col}", 0.0),
        step=5.0,
        key=f"val_perf_{tv_col}",
        label_visibility="collapsed",
    )
    perf_filters.append({
        "enabled": en_p,
        "label": label,
        "col_name": tv_col,
        "display_label": disp_label,
        "min_val": min_val,
    })

st.sidebar.markdown("---")
st.sidebar.header("6. Display Settings")
max_results = st.sidebar.slider(
    "Max Results to Fetch (4000+ Covers Entire Liquid Universe):",
    min_value=1000,
    max_value=5000,
    value=st.session_state.get("f_max_res", 4000),
    step=250,
    key="f_max_res",
)

# ==========================================
# 4. TOP-LEVEL WORKSPACE TABS (3 TABS NOW)
# ==========================================
tab_screener, tab_watchlists, tab_market_health = st.tabs([
    "🔎 CAN SLIM Screener & Rotation",
    "⭐ Multi-Watchlist Studio & TV Free-Tier Bridge",
    "🏥 Market Health & Sector Rotation",
])

# ==========================================
# TAB 1: CAN SLIM SCREENER & ROTATION
# ==========================================
with tab_screener:
  ma_cols_to_fetch = list(set([m["col_name"] for m in ma_filters]))
  tv_vol_col = f"average_volume_{vol_period_days}d_calc"

  with st.spinner("⚡ Scanning Indian Equities & Applying Active Filters..."):
    results_df = fetch_screener_data(
        exchange_choice,
        min_mcap_cr,
        vol_period_days,
        ma_cols_to_fetch,
        max_results,
    )
    nse_bands_map = get_nse_circuit_bands() or {}

  if results_df.empty:
    st.warning(
        "No stocks matched your criteria. Adjust your sidebar filters or switch"
        " to another Preset."
    )
  else:
    df = results_df.copy()
    df = df[df["exchange"].isin(exchange_choice)]
    if "type" in df.columns:
      df = df[df["type"] == "stock"]
    df = df.drop_duplicates(subset=["name"], keep="first")

    mapped_sectors, mapped_industries = [], []
    for _, row in df.iterrows():
      sec, ind = map_to_indian_classification(
          row.get("industry", ""), row.get("sector", "")
      )
      mapped_sectors.append(sec)
      mapped_industries.append(ind)
    df["Sector"] = mapped_sectors
    df["Industry"] = mapped_industries

    total_sector_counts = df["Sector"].value_counts()
    total_industry_counts = df["Industry"].value_counts()

    if sector_choice:
      df = df[df["Sector"].isin(sector_choice)]
    if industry_choice:
      df = df[df["Industry"].isin(industry_choice)]

    if "index" in df.columns:
      df["Index"] = df["index"].fillna("N/A")
    else:
      df["Index"] = "N/A"

    if index_choice:

      def matches_index(val):
        if pd.isna(val) or val == "N/A" or not val:
          return False
        val_str = str(val).upper()
        for idx_name in index_choice:
          if idx_name.upper() in val_str:
            return True
        return False

      df = df[df["Index"].apply(matches_index)]

    # ----------------------------------------------------
    # QUARTERLY YOY GROWTH COALESCING & FILTERING
    # ----------------------------------------------------
    df["EPS Q YoY %"] = coalesce_columns(df, EPS_Q_ALIASES).round(2)
    df["Sales Q YoY %"] = coalesce_columns(df, SALES_Q_ALIASES).round(2)

    if en_eps_q:
      if allow_na_growth:
        df = df[(df["EPS Q YoY %"] >= min_eps_q) | (df["EPS Q YoY %"].isna())]
      else:
        df = df[df["EPS Q YoY %"] >= min_eps_q]

    if en_sales_q:
      if allow_na_growth:
        df = df[
            (df["Sales Q YoY %"] >= min_sales_q) | (df["Sales Q YoY %"].isna())
        ]
      else:
        df = df[df["Sales Q YoY %"] >= min_sales_q]

    # ----------------------------------------------------
    # ROBUST MULTI-ALIAS IPO DATE PARSING
    # ----------------------------------------------------
    df = add_clean_ipo_date_col(df)

    if en_ipo and ipo_filter_choice != "All Stocks (No IPO Filter)":
      now_dt = pd.Timestamp.now()
      if ipo_filter_choice == "Recent IPO: Past 1 Month":
        cutoff = now_dt - pd.DateOffset(months=1)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 3 Months":
        cutoff = now_dt - pd.DateOffset(months=3)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 6 Months":
        cutoff = now_dt - pd.DateOffset(months=6)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 1 Year":
        cutoff = now_dt - pd.DateOffset(years=1)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Recent IPO: Past 2 Years":
        cutoff = now_dt - pd.DateOffset(years=2)
        df = df[df["IPO_Date_DT"] >= cutoff]
      elif ipo_filter_choice == "Seasoned: Listed > 1 Year Ago":
        cutoff = now_dt - pd.DateOffset(years=1)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]
      elif ipo_filter_choice == "Seasoned: Listed > 3 Years Ago":
        cutoff = now_dt - pd.DateOffset(years=3)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]
      elif ipo_filter_choice == "Seasoned: Listed > 5 Years Ago":
        cutoff = now_dt - pd.DateOffset(years=5)
        df = df[(df["IPO_Date_DT"] < cutoff) | (df["IPO Date"] == "N/A")]

    numeric_cols = [
        "market_cap_basic",
        "close",
        "change",
        "high",
        "low",
        "open",
        "volume",
        tv_vol_col,
        "ADR",
        "price_52_week_high",
        "price_52_week_low",
    ] + ma_cols_to_fetch
    for c in numeric_cols:
      if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["ADR_pct"] = (df["ADR"] / df["close"]) * 100
    if en_adr:
      df = df[df["ADR_pct"] >= min_adr]

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
      pct_above_low = (
          (df["close"] - df["price_52_week_low"]) / df["price_52_week_low"]
      ) * 100
      if en_52l:
        df = df[pct_above_low >= min_above_52l]

    if "price_52_week_high" in df.columns:
      pct_below_high = (
          (df["price_52_week_high"] - df["close"]) / df["price_52_week_high"]
      ) * 100
      if en_52h:
        df = df[pct_below_high <= max_below_52h]

    for pf in perf_filters:
      if pf["enabled"] and pf["col_name"] in df.columns:
        df[pf["col_name"]] = pd.to_numeric(df[pf["col_name"]], errors="coerce")
        df = df[df[pf["col_name"]] >= pf["min_val"]]

    # ----------------------------------------------------
    # HYBRID CIRCUIT LIMIT EXCLUSION (MULTI-SELECT SUPPORT)
    # ----------------------------------------------------
    if en_circuit and circuit_choice:
      df["high"] = pd.to_numeric(df["high"], errors="coerce")
      df["low"] = pd.to_numeric(df["low"], errors="coerce")
      df["open"] = pd.to_numeric(df["open"], errors="coerce")
      df["change_abs"] = df["change"].abs()

      is_full_day_freeze = df["high"] == df["low"]
      is_at_high_lock = (df["close"] == df["high"]) & (df["high"] > df["open"])
      is_at_low_lock = (df["close"] == df["low"]) & (df["low"] < df["open"])
      is_locked_extreme = is_at_high_lock | is_at_low_lock

      selected_band_nums = [b.replace("%", "") for b in circuit_choice]

      def is_circuit_hit(row):
        sym = str(row["name"]).strip().upper()
        band_val = nse_bands_map.get(sym, "")
        c_abs = row["change_abs"]
        is_locked = row["high"] == row["low"] or (
            (row["close"] == row["high"] or row["close"] == row["low"])
            and row["high"] != row["open"]
        )

        if band_val in selected_band_nums:
          return True

        if is_locked:
          if "2" in selected_band_nums and 1.97 <= c_abs <= 2.00:
            return True
          if "5" in selected_band_nums and 4.97 <= c_abs <= 5.00:
            return True
          if "10" in selected_band_nums and 9.97 <= c_abs <= 10.00:
            return True

        return False

      df["_is_circuit_excluded"] = df.apply(is_circuit_hit, axis=1)
      df = df[~df["_is_circuit_excluded"] & ~is_full_day_freeze]
      df = df.drop(columns=["_is_circuit_excluded"])

    if df.empty:
      st.warning(
          "No stocks passed all criteria. Try broadening your NSE"
          " Sector/Industry selections."
      )
    else:
      total_passed = len(df)
      rc = st.session_state.reset_counter

      st.subheader("📊 Scan Summary & Market Rotation")
      tab_sector_sum, tab_industry_sum = st.tabs(
          ["🛠️ Sector Summary", "🏢 Basic Industry Summary"]
      )

      with tab_sector_sum:
        sec_counts = df["Sector"].value_counts().reset_index()
        sec_counts.columns = ["Sector", "Stocks Passed"]
        sec_counts["% Share"] = (
            (sec_counts["Stocks Passed"] / total_passed) * 100
        ).round(1)
        sec_counts["% of Sector Total"] = sec_counts.apply(
            lambda r: round(
                (
                    r["Stocks Passed"]
                    / total_sector_counts.get(r["Sector"], 1)
                )
                * 100,
                1,
            ),
            axis=1,
        )
        c_chart1, c_table1 = st.columns([1.1, 1.3])
        with c_chart1:
          fig_sec = px.pie(
              sec_counts, names="Sector", values="Stocks Passed", hole=0.55
          )
          fig_sec.update_traces(textinfo="percent", textposition="inside")
          fig_sec.update_layout(
              annotations=[
                  dict(
                      text=f"<b>Total Stocks:<br>{total_passed}</b>",
                      x=0.5,
                      y=0.5,
                      font_size=16,
                      showarrow=False,
                  )
              ],
              showlegend=False,
              margin=dict(t=20, b=10, l=20, r=20),
              height=360,
          )
          chart_ev_sec = st.plotly_chart(
              fig_sec,
              use_container_width=True,
              on_select="rerun",
              selection_mode="points",
              key=f"sec_chart_{rc}",
          )
        with c_table1:
          table_ev_sec = st.dataframe(
              sec_counts,
              use_container_width=True,
              hide_index=True,
              height=360,
              on_select="rerun",
              selection_mode="multi-row",
              column_config=get_left_aligned_column_config(sec_counts.columns),
              key=f"sec_table_{rc}",
          )
        sel_sec_chart = parse_chart_selection_multi(chart_ev_sec)
        sel_sec_table = parse_table_selection_multi(
            table_ev_sec, sec_counts, "Sector"
        )
        active_sectors = sel_sec_table if sel_sec_table else sel_sec_chart

      with tab_industry_sum:
        if active_sectors:
          df_ind_source = df[df["Sector"].isin(active_sectors)]
          ind_total_passed = len(df_ind_source)
          st.info(
              "🏢 **Hierarchical View:** Showing Basic Industries inside"
              f" **{', '.join(active_sectors)}** ({ind_total_passed} Stocks)"
          )
        else:
          df_ind_source = df
          ind_total_passed = total_passed
        ind_counts = df_ind_source["Industry"].value_counts().reset_index()
        ind_counts.columns = ["Basic Industry", "Stocks Passed"]
        ind_counts["% Share"] = (
            (ind_counts["Stocks Passed"] / max(ind_total_passed, 1)) * 100
        ).round(1)
        ind_counts["% of Industry Total"] = ind_counts.apply(
            lambda r: round(
                (
                    r["Stocks Passed"]
                    / total_industry_counts.get(r["Basic Industry"], 1)
                )
                * 100,
                1,
            ),
            axis=1,
        )
        sec_hash = "_".join(sorted(active_sectors)) if active_sectors else "all"
        c_chart2, c_table2 = st.columns([1.1, 1.3])
        with c_chart2:
          fig_ind = px.pie(
              ind_counts,
              names="Basic Industry",
              values="Stocks Passed",
              hole=0.55,
          )
          fig_ind.update_traces(textinfo="percent", textposition="inside")
          fig_ind.update_layout(
              annotations=[
                  dict(
                      text=f"<b>Total Stocks:<br>{ind_total_passed}</b>",
                      x=0.5,
                      y=0.5,
                      font_size=16,
                      showarrow=False,
                  )
              ],
              showlegend=False,
              margin=dict(t=20, b=10, l=20, r=20),
              height=360,
          )
          chart_ev_ind = st.plotly_chart(
              fig_ind,
              use_container_width=True,
              on_select="rerun",
              selection_mode="points",
              key=f"ind_chart_{rc}_{sec_hash}",
          )
        with c_table2:
          table_ev_ind = st.dataframe(
              ind_counts,
              use_container_width=True,
              hide_index=True,
              height=360,
              on_select="rerun",
              selection_mode="multi-row",
              column_config=get_left_aligned_column_config(ind_counts.columns),
              key=f"ind_table_{rc}_{sec_hash}",
          )
        sel_ind_chart = parse_chart_selection_multi(chart_ev_ind)
        sel_ind_table = parse_table_selection_multi(
            table_ev_ind, ind_counts, "Basic Industry"
        )
        active_industries = (
            sel_ind_table if sel_ind_table else sel_ind_chart
        )

      st.markdown("---")
      df_display = df.copy()
      if active_sectors:
        df_display = df_display[df_display["Sector"].isin(active_sectors)]
      if active_industries:
        df_display = df_display[df_display["Industry"].isin(active_industries)]

      if active_sectors or active_industries:
        filter_labels = []
        if active_sectors:
          filter_labels.append(f"**Sector:** {', '.join(active_sectors)}")
        if active_industries:
          filter_labels.append(f"**Industry:** {', '.join(active_industries)}")
        col_info, col_reset = st.columns([3, 1])
        with col_info:
          st.info(
              f"🔍 **Active Drilldown:** {' | '.join(filter_labels)} ({len(df_display)} Stocks)"
          )
        with col_reset:
          if st.button(
              "🔄 Reset Scan Results (Show All)",
              type="primary",
              use_container_width=True,
          ):
            st.session_state.reset_counter += 1
            st.rerun()

      df_display["S.No._num"] = range(1, len(df_display) + 1)
      df_display["Market Cap (₹ Cr)"] = (
          df_display["market_cap_basic"] / 10_000_000
      ).round(2)
      vol_display_label = f"{vol_period_days}D Close×AvgVol (₹ Cr)"
      df_display[vol_display_label] = (
          df_display["val_traded_inr"] / 10_000_000
      ).round(2)
      df_display["Close"] = df_display["close"].round(2)
      df_display["Change %"] = df_display["change"].round(2)
      df_display["ADR %"] = df_display["ADR_pct"].round(2)
      df_display["TV_Symbol"] = df_display["exchange"] + ":" + df_display["name"]
      df_display["TV_Link"] = (
          "https://www.tradingview.com/chart/?symbol=NSE:" + df_display["name"]
      )
      df_display["Screener_Link"] = (
          "https://www.screener.in/company/"
          + df_display["name"]
          + "/consolidated/"
      )

      wl_dot_map = {}
      for wl_name, sym_list in st.session_state.watchlists.items():
        dot = (
            "🔵"
            if "breakout" in wl_name.lower()
            else (
                "🟢"
                if "focus" in wl_name.lower()
                else (
                    "🟡"
                    if "weekly" in wl_name.lower()
                    else (
                        "🟠"
                        if "bulk" in wl_name.lower()
                        else "🔴" if "sold" in wl_name.lower() else "🟣"
                    )
                )
            )
        )
        for s in sym_list:
          bare_s = s.split(":")[-1].strip().upper()
          wl_dot_map[bare_s] = wl_dot_map.get(bare_s, "") + dot

      df_display["WL_Dots"] = (
          df_display["name"].str.upper().map(wl_dot_map).fillna("")
      )
      df_display["S.No."] = df_display.apply(
          lambda r: (
              f"{r['S.No._num']} {r['WL_Dots']}".strip()
              if r["WL_Dots"]
              else str(r["S.No._num"])
          ),
          axis=1,
      )

      df_display["_in_band"] = (
          df_display["name"].str.upper().map(nse_bands_map)
      )
      cond1 = df_display["_in_band"].isin(["2", "5", "10"])
      cond2 = (
          (df_display["high"] == df_display["low"])
          & (df_display["high"] > 0)
          & (df_display["change"].abs() > 1.5)
      )
      df_display["_is_circuit_badge"] = cond1 | cond2
      df_display["name"] = df_display["name"].where(
          ~df_display["_is_circuit_badge"], df_display["name"] + " 🚨"
      )

      fund_badge_map = {
          k: f"{v.get('verdict')} ({v.get('date', '')})"
          for k, v in st.session_state.fundamental_reports.items()
      }
      df_display["Fundamental"] = (
          df_display["name"].str.replace(" 🚨", "").str.upper().map(
              fund_badge_map
          ).fillna("⚪ Not Analyzed")
      )

      canonical_perf_order = [
          "Perf % 1W",
          "Perf % 1M",
          "Perf % 3M",
          "Perf % 6M",
          "Perf % YTD",
          "Perf % 1Y",
      ]
      for label, (tv_col, disp_label) in perf_options.items():
        if tv_col in df_display.columns:
          df_display[disp_label] = pd.to_numeric(
              df_display[tv_col], errors="coerce"
          ).round(2)

      active_perf_labels = [
          p
          for p in canonical_perf_order
          if p in [perf_options[lbl][1] for lbl in selected_perf_labels]
          and p in df_display.columns
      ]

      active_ma_labels = []
      for ma in ma_filters:
        if ma["enabled"] and ma["col_name"] in df_display.columns:
          df_display[ma["label"]] = df_display[ma["col_name"]].round(2)
          active_ma_labels.append(ma["label"])

      table_columns = (
          [
              "S.No.",
              "TV_Symbol",
              "name",
              "Fundamental",
              "Close",
              "Change %",
              "ADR %",
              "EPS Q YoY %",
              "Sales Q YoY %",
          ]
          + active_perf_labels
          + active_ma_labels
          + [
              vol_display_label,
              "Market Cap (₹ Cr)",
              "IPO Date",
              "Sector",
              "Industry",
              "TV_Link",
              "Screener_Link",
          ]
      )

      st.subheader(f"📋 Scan Results ({len(df_display)} Stocks Found)")
      st.caption(
          "💡 **Watchlist Color Legend:** 🔵 Post Breakout Monitor | 🟢 Focus"
          " List | 🟡 Weekly Focus | 🟠 Scan Bulk | 🔴 Sold Stocks | 🟣 Custom"
          " | 🚨 **Circuit Band / Freeze**"
      )

      sc = st.session_state.scan_sel_counter
      table_ev_scan = st.dataframe(
          df_display[table_columns],
          use_container_width=True,
          hide_index=True,
          on_select="rerun",
          selection_mode="multi-row",
          column_config=get_left_aligned_column_config(table_columns),
          key=f"scan_table_{rc}_{sc}",
      )

      selected_rows = parse_table_selection_multi(
          table_ev_scan, df_display, "TV_Symbol"
      )

      # ----------------------------------------------------
      # 🧠 CHECKBOX-DRIVEN FUNDAMENTAL ANALYST (SCAN TAB)
      # ----------------------------------------------------
      st.markdown("---")
      f_col1, f_col2, f_col3 = st.columns([2.0, 1.3, 1.7])

      with f_col1:
        if len(selected_rows) == 1:
          active_sym = selected_rows[0]
          clean_sym_name = active_sym.split(":")[-1].strip().upper()
          if st.button(
              f"📖 Open Saved Report Modal ({clean_sym_name})",
              type="primary",
              use_container_width=True,
              key=f"fund_btn_view_scan_{rc}_{sc}",
          ):
            show_fundamental_modal(active_sym)
        else:
          st.button(
              "📖 Select a Single Stock Row to Open Report",
              type="secondary",
              disabled=True,
              use_container_width=True,
              key=f"fund_btn_view_scan_dis_{rc}_{sc}",
          )

      with f_col2:
        force_reanalyze_scan = st.checkbox(
            "Force Re-Analyze Existing",
            value=False,
            key=f"force_scan_{rc}_{sc}",
            help="If checked, AI will re-fetch Screener PDFs even if a report already exists.",
        )

      with f_col3:
        run_batch_scan = st.button(
            f"⚡ Analyze Selected ({len(selected_rows)})",
            type="primary",
            use_container_width=True,
            disabled=len(selected_rows) == 0,
            key=f"fund_btn_run_scan_{rc}_{sc}",
        )

      if run_batch_scan and len(selected_rows) > 0:
        if not GLOBAL_AI_WORKER_STATE["is_running"]:
          auth_cfg = {
              "gemini_key": st.secrets.get("GEMINI_API_KEY", ""),
              "screener_sid": st.secrets.get("SCREENER_SESSION_ID", ""),
              "email_addr": st.secrets.get("EMAIL_ADDRESS", ""),
              "email_pass": st.secrets.get("EMAIL_APP_PASSWORD", ""),
              "github_token": st.secrets.get("GITHUB_TOKEN", None),
              "gist_id": st.secrets.get("GIST_ID", None),
          }
          t = threading.Thread(
              target=background_ai_worker,
              args=(
                  selected_rows,
                  force_reanalyze_scan,
                  auth_cfg,
                  st.session_state.fundamental_reports,
              ),
              daemon=True,
          )
          t.start()
          time.sleep(0.4)
          st.rerun()

      if GLOBAL_AI_WORKER_STATE["is_running"]:
        st.info(
            "⚙️ **Background AI Worker Active:**"
            f" {GLOBAL_AI_WORKER_STATE['message']} *(You can freely"
            " check/uncheck boxes or switch watchlists — analysis will not"
            " abort!)*"
        )
        st.progress(
            GLOBAL_AI_WORKER_STATE["completed"]
            / max(1, GLOBAL_AI_WORKER_STATE["total"])
        )
        if st.button("🔄 Refresh Progress & Table", key=f"ref_worker_{rc}_{sc}"):
          st.rerun()
      elif (
          GLOBAL_AI_WORKER_STATE["message"]
          and time.time() - GLOBAL_AI_WORKER_STATE["last_updated"] < 60
      ):
        st.success(GLOBAL_AI_WORKER_STATE["message"])

      st.markdown("---")
      cw1, cw2, cw3, cw4 = st.columns([1.8, 1.5, 2.0, 0.9])
      with cw1:
        wl_keys = list(st.session_state.watchlists.keys())
        target_wl = st.selectbox(
            "Select Target Watchlist to Add Setups:",
            options=wl_keys,
            index=(
                wl_keys.index(st.session_state.active_watchlist_name)
                if st.session_state.active_watchlist_name in wl_keys
                else 0
            ),
            key="wl_table_target_select",
        )
      with cw2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(
            f"➕ Add Selected ({len(selected_rows)}) to Watchlist",
            type="primary",
            use_container_width=True,
            disabled=len(selected_rows) == 0,
        ):
          current_list = st.session_state.watchlists[target_wl]
          added_cnt = 0
          for sym in selected_rows:
            if sym not in current_list:
              current_list.append(sym)
              added_cnt += 1
          save_watchlists(st.session_state.watchlists)
          st.success(
              f"✅ Successfully added {added_cnt} new stocks to"
              f" **{target_wl}**!"
          )
      with cw3:
        st.caption("➕ Create New Watchlist:")
        with st.form("create_wl_scan_form", clear_on_submit=True):
          fc1, fc2 = st.columns([1.7, 1.0])
          with fc1:
            new_scan_wl = st.text_input(
                "Create New Watchlist",
                placeholder="e.g., Telecom Breakout",
                label_visibility="collapsed",
            )
          with fc2:
            if st.form_submit_button("➕ Create", use_container_width=True):
              if (
                  new_scan_wl
                  and new_scan_wl not in st.session_state.watchlists
              ):
                st.session_state.watchlists[new_scan_wl] = []
                st.session_state.active_watchlist_name = new_scan_wl
                save_watchlists(st.session_state.watchlists)
                st.success(f"Created '{new_scan_wl}'!")
                st.rerun()
      with cw4:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("💡 Check rows above to enable actions.")

      st.markdown("---")
      if len(selected_rows) > 0:
        st.subheader(
            f"📋 Copy Selected Setups to TradingView ({len(selected_rows)}"
            " Stocks)"
        )
        st.code(", ".join(selected_rows), language="text")

      filtered_symbols = df_display["TV_Symbol"].tolist()
      st.subheader(
          f"📋 Copy Filtered Scan Results to TradingView"
          f" ({len(filtered_symbols)} Stocks)"
      )

      if filtered_symbols:
        batch_size = 30
        batches = [
            filtered_symbols[i : i + batch_size]
            for i in range(0, len(filtered_symbols), batch_size)
        ]

        if len(batches) > 1:
          st.markdown("#### ⚡ 30-Symbol TradingView Hot-Swap Batches")
          st.caption(
              "💡 **Free Tier Bypass Workflow:** In TradingView, press **`Ctrl+A`**"
              " → **`Backspace`** → **`Ctrl+V`** in your TV watchlist box to"
              " hot-swap 30 stocks at a time!"
          )

          batch_labels = []
          for idx, b_list in enumerate(batches):
            start_num = idx * batch_size + 1
            end_num = idx * batch_size + len(b_list)
            batch_labels.append(f"Batch {idx + 1} ({start_num}–{end_num})")

          selected_batch_label = st.selectbox(
              "Select 30-Symbol Batch to Copy:",
              options=batch_labels,
              key=f"scan_batch_dropdown_{rc}_{sc}",
          )
          selected_idx = batch_labels.index(selected_batch_label)
          st.code(", ".join(batches[selected_idx]), language="text")

        with st.expander(
            "📋 View / Copy All Tickers (Full Unbatched String)",
            expanded=False,
        ):
          tv_watchlist_string = ", ".join(filtered_symbols)
          st.code(tv_watchlist_string, language="text")

# ==========================================
# TAB 2: WATCHLIST STUDIO & TV FREE-TIER BRIDGE
# ==========================================
with tab_watchlists:
  st.subheader(
      "⭐ Multi-Watchlist Studio (Bypasses TV Free Tier 30-Symbol Cap)"
  )

  col_sel, col_new, col_del = st.columns([2.4, 1.8, 0.8])
  with col_sel:
    wl_names = list(st.session_state.watchlists.keys())
    active_wl = st.selectbox(
        "Select Active Watchlist:",
        options=wl_names,
        index=(
            wl_names.index(st.session_state.active_watchlist_name)
            if st.session_state.active_watchlist_name in wl_names
            else 0
        ),
        key="wl_active_selector",
    )
    st.session_state.active_watchlist_name = active_wl

    with st.form("inline_rename_form", clear_on_submit=True):
      r_col1, r_col2 = st.columns([2.6, 1.0])
      with r_col1:
        new_inline_name = st.text_input(
            "✏️ Rename Selected Watchlist:",
            value=active_wl,
            label_visibility="collapsed",
            placeholder="Rename watchlist...",
        )
      with r_col2:
        if st.form_submit_button("✏️ Rename", use_container_width=True):
          if (
              new_inline_name
              and new_inline_name != active_wl
              and new_inline_name not in st.session_state.watchlists
          ):
            old_name = active_wl
            st.session_state.watchlists[new_inline_name] = (
                st.session_state.watchlists.pop(old_name)
            )
            st.session_state.active_watchlist_name = new_inline_name
            save_watchlists(st.session_state.watchlists)
            st.success(f"Renamed to '{new_inline_name}'!")
            st.rerun()

  with col_new:
    with st.form("create_wl_form", clear_on_submit=True):
      new_wl_name = st.text_input(
          "Create New Watchlist:",
          placeholder="e.g., Sector: Capital Goods Build",
      )
      if st.form_submit_button(
          "➕ Create Watchlist", use_container_width=True
      ):
        if new_wl_name and new_wl_name not in st.session_state.watchlists:
          st.session_state.watchlists[new_wl_name] = []
          st.session_state.active_watchlist_name = new_wl_name
          save_watchlists(st.session_state.watchlists)
          st.success(f"Created Watchlist: {new_wl_name}")
          st.rerun()
  with col_del:
    st.markdown("<br>", unsafe_allow_html=True)
    if len(wl_names) > 1:
      if st.button(
          "🗑️ Delete", type="secondary", use_container_width=True
      ):
        del st.session_state.watchlists[active_wl]
        save_watchlists(st.session_state.watchlists)
        st.session_state.active_watchlist_name = list(
            st.session_state.watchlists.keys()
        )[0]
        st.rerun()

  current_symbols = st.session_state.watchlists[active_wl]

  with st.expander(
      "📥 Import / Paste Tickers & Backup Local Text (.TXT) Library",
      expanded=False,
  ):
    ci1, ci2 = st.columns([2, 1])
    with ci1:
      pasted_text = st.text_area(
          "Paste Tickers from TradingView (Comma, Space, or Newline"
          " separated):",
          placeholder="NSE:RELIANCE, BSE:TCS, ZOMATO, TRENT\nNSE:HAL",
      )
      if st.button(
          "➕ Import Tickers into Current Watchlist", type="primary"
      ):
        parsed_symbols = parse_pasted_tickers(pasted_text)
        current_list = st.session_state.watchlists[active_wl]
        added = 0
        for s in parsed_symbols:
          if s not in current_list:
            current_list.append(s)
            added += 1
        save_watchlists(st.session_state.watchlists)
        st.success(f"✅ Imported {added} symbols into **{active_wl}**!")
        st.rerun()
    with ci2:
      st.markdown("#### 💾 Backup & Restore Disk Library (.TXT)")
      txt_export_str = json.dumps(st.session_state.watchlists, indent=2)
      st.download_button(
          label="📥 Download Watchlists (.TXT)",
          data=txt_export_str,
          file_name="my_india_watchlists.txt",
          mime="text/plain",
          use_container_width=True,
      )
      uploaded_file = st.file_uploader(
          "Restore Watchlists (.TXT):",
          type=["txt", "json"],
          label_visibility="collapsed",
      )
      if uploaded_file is not None:
        try:
          loaded_wls = json.load(uploaded_file)
          if isinstance(loaded_wls, dict):
            st.session_state.watchlists = loaded_wls
            st.session_state.active_watchlist_name = list(loaded_wls.keys())[0]
            save_watchlists(loaded_wls)
            st.success("✅ Watchlists restored successfully!")
            st.rerun()
        except Exception:
          st.error(
              "Invalid file format. Ensure it is a valid backup file."
          )

  if not current_symbols:
    st.info(
        f"The watchlist **{active_wl}** is currently empty. Add setups from the"
        " Screener tab or paste symbols above!"
    )
  else:
    if len(current_symbols) > 1:
      st.markdown("---")
      st.markdown("#### ⚡ Priority Mover & Rank Jumper")
      rm_col1, rm_col2, rm_col3, rm_col4, rm_col5, rm_col6, rm_col7 = st.columns(
          [2.0, 0.8, 0.8, 0.8, 0.8, 1.1, 0.8]
      )
      with rm_col1:
        move_target_sym = st.selectbox(
            "Select Ticker to Move:",
            options=current_symbols,
            key=f"rapid_mover_sym_{active_wl}",
            label_visibility="collapsed",
        )
      with rm_col2:
        st.button(
            "🔝 Top",
            on_click=cb_move_top,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col3:
        st.button(
            "⬆️ Up",
            on_click=cb_move_up,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col4:
        st.button(
            "⬇️ Down",
            on_click=cb_move_down,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col5:
        st.button(
            "🔻 Bottom",
            on_click=cb_move_bottom,
            args=(active_wl, move_target_sym),
            use_container_width=True,
        )
      with rm_col6:
        target_rank = st.number_input(
            "Rank #",
            min_value=1,
            max_value=len(current_symbols),
            value=1,
            step=1,
            key=f"rapid_mover_rank_{active_wl}",
            label_visibility="collapsed",
        )
      with rm_col7:
        st.button(
            "🎯 Jump",
            type="primary",
            on_click=cb_jump_rank,
            args=(active_wl, move_target_sym, target_rank),
            use_container_width=True,
        )

    with st.spinner(
        f"📡 Enriching {len(current_symbols)} Tickers with Live Price &"
        " ADR%..."
    ):
      enriched_df = fetch_watchlist_enrichMENT(current_symbols)

    ordered_df = pd.DataFrame({
        "TV_Symbol": current_symbols,
        "name": [s.split(":")[-1].strip().upper() for s in current_symbols],
    })

    if not enriched_df.empty:
      merged_df = ordered_df.merge(
          enriched_df, on="name", how="left", suffixes=("", "_tv")
      )
      if "TV_Symbol_tv" in merged_df.columns:
        merged_df["TV_Symbol"] = merged_df["TV_Symbol_tv"].fillna(
            merged_df["TV_Symbol"]
        )
    else:
      merged_df = ordered_df.copy()
      for col_name in [
          "Close",
          "Change %",
          "ADR_pct",
          "EPS Q YoY %",
          "Sales Q YoY %",
          "Perf % 1W",
          "Perf % 1M",
          "Perf % 3M",
          "Perf % 6M",
          "Market Cap (₹ Cr)",
          "IPO Date",
          "Sector",
          "Industry",
      ]:
        merged_df[col_name] = "N/A"

    merged_df["Close"] = merged_df.get("Close", pd.Series()).fillna("N/A")
    merged_df["Change %"] = merged_df.get("Change %", pd.Series()).fillna("N/A")
    merged_df["ADR %"] = merged_df.get("ADR_pct", pd.Series()).fillna("N/A")
    merged_df["EPS Q YoY %"] = merged_df.get(
        "EPS Q YoY %", pd.Series()
    ).fillna("N/A")
    merged_df["Sales Q YoY %"] = merged_df.get(
        "Sales Q YoY %", pd.Series()
    ).fillna("N/A")
    merged_df["Perf % 1W"] = merged_df.get("Perf % 1W", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 1M"] = merged_df.get("Perf % 1M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 3M"] = merged_df.get("Perf % 3M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Perf % 6M"] = merged_df.get("Perf % 6M", pd.Series()).fillna(
        "N/A"
    )
    merged_df["Market Cap (₹ Cr)"] = merged_df.get(
        "Market Cap (₹ Cr)", pd.Series()
    ).fillna("N/A")
    merged_df["IPO Date"] = merged_df.get("IPO Date", pd.Series()).fillna("N/A")
    merged_df["Sector"] = merged_df.get("Sector", pd.Series()).fillna(
        "Unclassified"
    )
    merged_df["Industry"] = merged_df.get("Industry", pd.Series()).fillna(
        "Unclassified"
    )

    merged_df["S.No._num"] = range(1, len(merged_df) + 1)
    merged_df["TV_Link"] = (
        "https://www.tradingview.com/chart/?symbol=" + merged_df["TV_Symbol"]
    )
    merged_df["Screener_Link"] = (
        "https://www.screener.in/company/"
        + merged_df["name"]
        + "/consolidated/"
    )

    wl_dot_map_wl = {}
    for wl_name, sym_list in st.session_state.watchlists.items():
      dot = (
          "🔵"
          if "breakout" in wl_name.lower()
          else (
              "🟢"
              if "focus" in wl_name.lower()
              else (
                  "🟡"
                  if "weekly" in wl_name.lower()
                  else (
                      "🟠"
                      if "bulk" in wl_name.lower()
                      else "🔴" if "sold" in wl_name.lower() else "🟣"
                  )
              )
          )
      )
      for s in sym_list:
        bare_s = s.split(":")[-1].strip().upper()
        wl_dot_map_wl[bare_s] = wl_dot_map_wl.get(bare_s, "") + dot

    merged_df["WL_Dots"] = (
        merged_df["name"].str.upper().map(wl_dot_map_wl).fillna("")
    )
    merged_df["S.No."] = merged_df.apply(
        lambda r: (
            f"{r['S.No._num']} {r['WL_Dots']}".strip()
            if r["WL_Dots"]
            else str(r["S.No._num"])
        ),
        axis=1,
    )

    nse_bands_map = get_nse_circuit_bands()
    merged_df["_is_circuit_badge"] = merged_df.apply(
        lambda r: is_circuit_stock_badge(r, nse_bands_map), axis=1
    )
    merged_df["name"] = merged_df["name"].where(
        ~merged_df["_is_circuit_badge"], merged_df["name"] + " 🚨"
    )

    # ----------------------------------------------------
    # ATTACH PERSISTENT FUNDAMENTAL REPORT BADGE COLUMN
    # ----------------------------------------------------
    merged_df["Fundamental"] = (
        merged_df["name"]
        .str.replace(" 🚨", "")
        .str.upper()
        .map(
            {
                k: f"{v.get('verdict')} ({v.get('date', '')})"
                for k, v in st.session_state.fundamental_reports.items()
            }
        )
        .fillna("⚪ Not Analyzed")
    )

    wl_cols = [
        "S.No.",
        "TV_Symbol",
        "name",
        "Fundamental",
        "Close",
        "Change %",
        "ADR %",
        "EPS Q YoY %",
        "Sales Q YoY %",
        "Perf % 1W",
        "Perf % 1M",
        "Perf % 3M",
        "Perf % 6M",
        "Market Cap (₹ Cr)",
        "IPO Date",
        "Sector",
        "Industry",
        "TV_Link",
        "Screener_Link",
    ]

    st.markdown(
        f"### ⭐ Watchlist: **{active_wl}** ({len(current_symbols)} Stocks)"
    )
    st.caption(
        "💡 **Watchlist Color Legend:** 🔵 Post Breakout Monitor | 🟢 Focus"
        " List | 🟡 Weekly Focus | 🟠 Scan Bulk | 🔴 Sold Stocks | 🟣 Custom"
        " | 🚨 **Circuit Band / Freeze**"
    )

    wsc = st.session_state.wl_sel_counter
    wl_table_event = st.dataframe(
        merged_df[wl_cols],
        use_container_width=True,
        hide_index=True,
        height=460,
        on_select="rerun",
        selection_mode="multi-row",
        column_config=get_left_aligned_column_config(wl_cols),
        key=f"wl_manage_table_{wsc}",
    )

    sel_symbols = parse_table_selection_multi(
        wl_table_event, merged_df, "TV_Symbol"
    )

    # ----------------------------------------------------
    # 🧠 CHECKBOX-DRIVEN FUNDAMENTAL ANALYST (WATCHLIST TAB)
    # ----------------------------------------------------
    st.markdown("---")
    wf_col1, wf_col2, wf_col3 = st.columns([2.0, 1.3, 1.7])

    with wf_col1:
      if len(sel_symbols) == 1:
        active_sym_wl = sel_symbols[0]
        clean_wl_sym_name = active_sym_wl.split(":")[-1].strip().upper()
        if st.button(
            f"📖 Open Saved Report Modal ({clean_wl_sym_name})",
            type="primary",
            use_container_width=True,
            key=f"fund_btn_view_wl_{wsc}",
        ):
          show_fundamental_modal(active_sym_wl)
      else:
        st.button(
            "📖 Select a Single Stock Row to Open Report",
            type="secondary",
            disabled=True,
            use_container_width=True,
            key=f"fund_btn_view_wl_dis_{wsc}",
        )

    with wf_col2:
      force_reanalyze_wl = st.checkbox(
          "Force Re-Analyze Existing",
          value=False,
          key=f"force_wl_{wsc}",
          help="If checked, AI will re-fetch Screener PDFs even if a report already exists.",
      )

    with wf_col3:
      run_batch_wl = st.button(
          f"⚡ Analyze Selected ({len(sel_symbols)})",
          type="primary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
          key=f"fund_btn_run_wl_{wsc}",
      )

    if run_batch_wl and len(sel_symbols) > 0:
      if not GLOBAL_AI_WORKER_STATE["is_running"]:
        auth_cfg_wl = {
            "gemini_key": st.secrets.get("GEMINI_API_KEY", ""),
            "screener_sid": st.secrets.get("SCREENER_SESSION_ID", ""),
            "email_addr": st.secrets.get("EMAIL_ADDRESS", ""),
            "email_pass": st.secrets.get("EMAIL_APP_PASSWORD", ""),
            "github_token": st.secrets.get("GITHUB_TOKEN", None),
            "gist_id": st.secrets.get("GIST_ID", None),
        }
        t = threading.Thread(
            target=background_ai_worker,
            args=(
                sel_symbols,
                force_reanalyze_wl,
                auth_cfg_wl,
                st.session_state.fundamental_reports,
            ),
            daemon=True,
        )
        t.start()
        time.sleep(0.4)
        st.rerun()

    if GLOBAL_AI_WORKER_STATE["is_running"]:
      st.info(
          "⚙️ **Background AI Worker Active:**"
          f" {GLOBAL_AI_WORKER_STATE['message']} *(You can freely check/uncheck"
          " boxes or switch watchlists — analysis will not abort!)*"
      )
      st.progress(
          GLOBAL_AI_WORKER_STATE["completed"]
          / max(1, GLOBAL_AI_WORKER_STATE["total"])
      )
      if st.button("🔄 Refresh Progress & Table", key=f"ref_worker_wl_{wsc}"):
        st.rerun()
    elif (
        GLOBAL_AI_WORKER_STATE["message"]
        and time.time() - GLOBAL_AI_WORKER_STATE["last_updated"] < 60
    ):
      st.success(GLOBAL_AI_WORKER_STATE["message"])

    c_rem, c_clr, c_promo_sel, c_promo_btn = st.columns([1.5, 1.2, 2.0, 1.5])
    with c_rem:
      if st.button(
          f"🗑️ Remove Selected ({len(sel_symbols)})",
          type="secondary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
      ):
        for sym in sel_symbols:
          if sym in st.session_state.watchlists[active_wl]:
            st.session_state.watchlists[active_wl].remove(sym)
        save_watchlists(st.session_state.watchlists)
        st.rerun()
    with c_clr:
      if st.button(
          "🧹 Clear Selection",
          type="secondary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
          key="clear_wl_sel_btn",
      ):
        st.session_state.wl_sel_counter += 1
        st.rerun()
    with c_promo_sel:
      promo_target = st.selectbox(
          "Promote Selected To Target Watchlist:",
          options=(
              [name for name in wl_names if name != active_wl]
              if len(wl_names) > 1
              else wl_names
          ),
          key="promo_target_select",
          label_visibility="collapsed",
      )
    with c_promo_btn:
      if st.button(
          f"➡️ Promote Selected ({len(sel_symbols)})",
          type="primary",
          use_container_width=True,
          disabled=len(sel_symbols) == 0,
      ):
        target_list = st.session_state.watchlists[promo_target]
        cnt = 0
        for sym in sel_symbols:
          if sym not in target_list:
            target_list.append(sym)
            cnt += 1
        save_watchlists(st.session_state.watchlists)
        st.success(f"✅ Promoted {cnt} stocks to **{promo_target}**!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### ⚡ 30-Symbol TradingView Hot-Swap Batches")
    st.caption(
        "💡 **Free Tier Bypass Workflow:** In TradingView, press **`Ctrl+A`**"
        " → **`Backspace`** → **`Ctrl+V`** in your TV watchlist box to"
        " hot-swap 30 stocks at a time!"
    )

    batch_size = 30
    batches = [
        current_symbols[i : i + batch_size]
        for i in range(0, len(current_symbols), batch_size)
    ]

    if len(batches) > 1:
      batch_labels = []
      for idx, b_list in enumerate(batches):
        start_num = idx * batch_size + 1
        end_num = idx * batch_size + len(b_list)
        batch_labels.append(f"Batch {idx + 1} ({start_num}–{end_num})")

      selected_wl_batch_label = st.selectbox(
          "Select 30-Symbol Batch to Copy:",
          options=batch_labels,
          key=f"wl_batch_select_{active_wl}_{wsc}",
      )
      selected_wl_idx = batch_labels.index(selected_wl_batch_label)
      st.code(", ".join(batches[selected_wl_idx]), language="text")
    else:
      st.code(", ".join(current_symbols), language="text")

    with st.expander(
        "📋 View / Copy All Tickers (Full Unbatched String)",
        expanded=False,
    ):
      st.code(", ".join(current_symbols), language="text")

# ==========================================
# TAB 3: MARKET HEALTH & SECTOR ROTATION
# ==========================================
with tab_market_health:
  st.subheader("🏥 Market Health & Sector Rotation Studio")
  st.markdown(
      "Automated **Nifty 500 Breadth Monitor** and **27-Sector CAN SLIM"
      " Rotation Engine**. Automatically synchronized with your daily"
      " scheduled cronjob."
  )

  tab_mm, tab_sector_heat, tab_sector_rot = st.tabs([
      "📈 NSE Market Breadth Monitor",
      "🔥 Sector RS Heatmap",
      "📊 Historical Rotation Tracker",
  ])

  # ------------------------------------------
  # TAB 3A: NSE MARKET MONITOR
  # ------------------------------------------
  with tab_mm:
    df_mm = load_market_monitor_data()
    if not df_mm.empty:
      st.markdown(
          f"#### 📊 Nifty Total Market Breadth & VCP Indicators ({len(df_mm)} Days)"
      )

      latest = df_mm.iloc[0] if len(df_mm) > 0 else {}
      c1, c2, c3, c4 = st.columns(4)
      with c1:
        st.metric(
            "Latest Nifty 500 Close",
            f"{latest.get('Nifty 500 Close', 'N/A')}",
            f"{latest.get('Nifty 500 Chg %', 0)}%",
        )
      with c2:
        st.metric(
            "5-Day Thrust Ratio", f"{latest.get('5 Day Ratio', 'N/A')}"
        )
      with c3:
        st.metric(
            "10-Day Thrust Ratio", f"{latest.get('10 Day Ratio', 'N/A')}"
        )
      with c4:
        st.metric("A/D Ratio", f"{latest.get('A/D Ratio', 'N/A')}")

      styled_mm = style_market_monitor(df_mm)
      st.table(styled_mm)
    else:
      st.info(
          "Market Monitor data not available yet. If your repo is Private,"
          " ensure `GITHUB_TOKEN = 'ghp_...'` is added in your Streamlit Cloud"
          " App Settings -> Secrets."
      )
      if st.button(
          "🔄 Retry Fetching Market Monitor Now",
          key="retry_mm_btn",
          type="primary",
      ):
        load_market_monitor_data.clear()
        st.rerun()

  # ------------------------------------------
  # TAB 3B: SECTOR RS HEATMAP
  # ------------------------------------------
  with tab_sector_heat:
    df_heat, _ = load_sector_monitor_data()
    if not df_heat.empty:
      st.markdown(
          "#### 🔥 27-Sector CAN SLIM Relative Strength Heatmap (Ranked by 65D RS)"
      )
      st.caption(
          "💡 **Velocity Legend:** Positive (+) values indicate upward rank"
          " acceleration; Negative (-) indicate loss of relative momentum."
      )

      styled_heat = style_sector_heatmap(df_heat)
      st.table(styled_heat)
    else:
      st.info(
          "Sector Heatmap data not available yet. If your repo is Private,"
          " ensure `GITHUB_TOKEN = 'ghp_...'` is added in your Streamlit Cloud"
          " App Settings -> Secrets."
      )
      if st.button(
          "🔄 Retry Fetching Sector Data Now",
          key="retry_sec_btn",
          type="primary",
      ):
        load_sector_monitor_data.clear()
        st.rerun()

  # ------------------------------------------
  # TAB 3C: HISTORICAL ROTATION TRACKER
  # ------------------------------------------
  with tab_sector_rot:
    _, df_rot = load_sector_monitor_data()
    if not df_rot.empty:
      st.markdown(
          "#### 📊 65-Day Historical Relative Strength Ranks (All Sectors)"
      )
      st.caption(
          "💡 Rank 1 = Strongest Relative Strength vs. Nifty 500 Benchmark"
          " (`^CRSLDX`)."
      )

      styled_rot = style_rotation_tracker(df_rot)
      st.table(styled_rot)
    else:
      st.info(
          "Rotation Tracker data not available yet. If your repo is Private,"
          " ensure `GITHUB_TOKEN = 'ghp_...'` is added in your Streamlit Cloud"
          " App Settings -> Secrets."
      )
      if st.button(
          "🔄 Retry Fetching Rotation Data Now",
          key="retry_rot_btn",
          type="primary",
      ):
        load_sector_monitor_data.clear()
        st.rerun()

  st.markdown("---")
  with st.expander(
      "⚡ Optional: Force Real-Time Scan Now (Bypass Daily Schedule)"
  ):
    st.caption(
        "Your scheduled cronjob automatically pushes updated Excel files to"
        " GitHub every weekday. Click below only if you want to force an"
        " immediate intraday refresh of Streamlit's data cache."
    )
    if st.button(
        "🔄 Clear Streamlit Data Cache & Reload", type="secondary"
    ):
      st.cache_data.clear()
      st.success("✅ Data cache cleared! Reloading latest tables...")
      st.rerun()
