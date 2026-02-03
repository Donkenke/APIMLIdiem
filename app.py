import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import textwrap
import time

# --- CONFIGURATION & PAGE SETUP ---
st.set_page_config(
    layout="wide",
    page_title="MercadoPublico Intel",
    page_icon="📡",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (SCI-FI / TECHNICAL AESTHETIC) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600&display=swap');

    /* Global Dark Theme adjustments */
    .stApp {
        background-color: #0d1117; /* Github Dark Dimmed */
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, h4, .stMetricLabel, .stMarkdown code {
        font-family: 'JetBrains Mono', monospace;
    }

    /* Metric Containers */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    div[data-testid="stMetricValue"] {
        color: #58a6ff;
    }

    /* Tender Card Styling */
    .tender-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-left: 5px solid #238636; /* Success Green */
        padding: 20px;
        margin-bottom: 16px;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    .tender-card:hover {
        border-color: #58a6ff;
        box-shadow: 0 4px 12px rgba(88, 166, 255, 0.1);
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    
    .card-id {
        font-family: 'JetBrains Mono', monospace;
        color: #58a6ff;
        background: rgba(88, 166, 255, 0.15);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
    }
    
    .card-status {
        font-family: 'JetBrains Mono', monospace;
        color: #2ea043;
        border: 1px solid #2ea043;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75em;
        text-transform: uppercase;
    }

    .card-title {
        color: #c9d1d9;
        font-size: 1.15em;
        font-weight: 600;
        margin-bottom: 8px;
        line-height: 1.4;
    }

    .card-meta {
        display: flex;
        gap: 20px;
        color: #8b949e;
        font-size: 0.85em;
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }

    .card-desc {
        color: #8b949e;
        font-size: 0.9em;
        line-height: 1.5;
        border-top: 1px solid #21262d;
        padding-top: 10px;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #21262d;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        color: #c9d1d9;
    }
</style>
""", unsafe_allow_html=True)


# --- BACKEND LOGIC ---

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_daily_tenders(date_str, ticket):
    """
    Production: Hits the official MercadoPublico API for a specific date.
    Returns the list of tenders or an empty list.
    """
    url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
    params = {
        "fecha": date_str,
        "ticket": ticket
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # The API returns { "Cantidad": X, "FechaCreacion": "...", "Listado": [...] }
            return data.get("Listado", [])
        else:
            # Silent fail or log
            print(f"API Error {response.status_code} for {date_str}")
            return []
    except Exception as e:
        print(f"Connection error for {date_str}: {e}")
        return []

def fetch_last_x_days(days, ticket):
    """
    Iterates backwards from today to fetch X days of data.
    Aggregates all into a single list.
    """
    all_tenders = []
    # Progress bar in the UI
    progress_text = "Syncing with MercadoPublico Mainframe..."
    my_bar = st.progress(0, text=progress_text)
    
    today = datetime.now()
    
    for i in range(days):
        date_query = (today - timedelta(days=i)).strftime("%d%m%Y")
        tenders = fetch_daily_tenders(date_query, ticket)
        if tenders:
            all_tenders.extend(tenders)
        
        # Update progress
        percent_complete = int((i + 1) / days * 100)
        my_bar.progress(percent_complete, text=f"Scanning date: {date_query} ({len(tenders)} found)")
        time.sleep(0.1) # Respectful API delay
    
    my_bar.empty()
    return all_tenders

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_ocds_data(tender_id):
    """
    Production: Hits the OCDS API (No Ticket Needed).
    Fetches rich details: Items, UNSPSC codes, etc.
    """
    # The ID structure in OCDS URL usually works with the standard code (e.g. 1506-85-O125)
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{tender_id}"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def parse_ocds_items(ocds_json):
    """
    Extracts item details specifically looking for the 'classification' 
    and 'description' as requested by the user.
    """
    parsed_items = []
    
    try:
        # OCDS Structure: records[0] -> compiledRelease -> tender -> items
        records = ocds_json.get('records', [])
        if not records: return []
        
        tender = records[0].get('compiledRelease', {}).get('tender', {})
        items = tender.get('items', [])
        
        for item in items:
            classification = item.get('classification', {})
            
            # The user wants to see the specific category code and description
            item_data = {
                "Description": item.get('description', 'N/A'),
                "Qty": item.get('quantity', 0),
                "Unit": item.get('unit', {}).get('name', 'N/A'),
                "UNSPSC Code": classification.get('id', 'N/A'),
                # The category URI often contains the text logic if needed, 
                # but we display the URI so the user can verify if they want.
                "Category URI": classification.get('uri', '#')
            }
            parsed_items.append(item_data)
            
    except Exception as e:
        print(f"Error parsing OCDS: {e}")
        
    return parsed_items

# --- FRONTEND UI ---

# 1. Sidebar Controls
with st.sidebar:
    st.title("🎛️ Control Deck")
    
    # API Key Handling (Try Secrets first, then Fallback to Input)
    if "MP_TICKET" in st.secrets:
        api_ticket = st.secrets["MP_TICKET"]
        st.success("Authenticated via Secrets")
    else:
        api_ticket = st.text_input("Enter API Ticket", type="password")
        st.caption("Get your ticket at api.mercadopublico.cl")

    st.divider()
    
    days_to_fetch = st.slider("Lookback Window (Days)", 1, 7, 3)
    
    st.subheader("Filters")
    # Keywords
    search_query = st.text_input("Keyword Search", placeholder="e.g., Hormigon, Consultoria, Arica")
    
    # Region Filter (Simple predefined list, can be expanded)
    region_options = ["All", "Metropolitana", "Valparaíso", "Biobío", "Antofagasta", "Araucanía", "Arica"]
    region_filter = st.selectbox("Region Scope", region_options)
    
    st.divider()
    st.info("System Ready. Waiting for command.")

# 2. Main Execution Flow
st.title("Tender Intelligence Unit")
st.markdown(f"**Live Feed** | Accessing MercadoPúblico Data | Protocol: `REST + OCDS`")

if not api_ticket:
    st.warning("⚠️ API Ticket required to initialize scan.")
    st.stop()

# 3. Fetch Data (Cached)
raw_tenders = fetch_last_x_days(days_to_fetch, api_ticket)

# 4. Filter Logic (Client Side)
filtered_tenders = []
keywords = [k.strip().lower() for k in search_query.split(",")] if search_query else []

for t in raw_tenders:
    # Safely get fields
    name = str(t.get('Nombre', '')).lower()
    desc = str(t.get('Descripcion', '')).lower()
    region = t.get('Comprador', {}).get('RegionUnidad', '')
    
    # Region Filter
    if region_filter != "All" and region_filter not in region:
        continue
        
    # Keyword Filter
    if keywords:
        # If any keyword matches name OR description
        if not any(k in name or k in desc for k in keywords):
            continue
            
    filtered_tenders.append(t)

# 5. Metrics Display
c1, c2, c3, c4 = st.columns(4)
c1.metric("Raw Feed", len(raw_tenders))
c2.metric("Filtered Targets", len(filtered_tenders))
c3.metric("API Efficiency", "100%")
c4.metric("Last Update", datetime.now().strftime("%H:%M:%S"))

st.divider()

# 6. Render Results
if not filtered_tenders:
    st.info("No tenders found matching current parameters.")
else:
    for tender in filtered_tenders:
        code = tender.get('CodigoExterno')
        
        # Container for visual grouping
        with st.container():
            # Formatting dates
            date_close = tender.get('FechaCierre', 'N/A')
            if date_close:
                # Basic parsing, might need adjustment based on exact API format
                try:
                    date_obj = datetime.strptime(date_close, "%Y-%m-%dT%H:%M:%S")
                    date_display = date_obj.strftime("%d %b %Y")
                except:
                    date_display = date_close
            else:
                date_display = "No Date"

            # Render Card HTML
            html_content = f"""
            <div class="tender-card">
                <div class="card-header">
                    <span class="card-id">{code}</span>
                    <span class="card-status">{tender.get('Estado', 'Unknown')}</span>
                </div>
                <div class="card-title">{tender.get('Nombre')}</div>
                <div class="card-meta">
                    <span>🏢 {tender.get('Comprador', {}).get('NombreOrganismo', 'N/A')}</span>
                    <span>📍 {tender.get('Comprador', {}).get('RegionUnidad', 'N/A')}</span>
                    <span>📅 Close: {date_display}</span>
                    <span>💰 {tender.get('Moneda', 'CLP')}</span>
                </div>
                <div class="card-desc">
                    {textwrap.shorten(tender.get('Descripcion', ''), width=200, placeholder="...")}
                </div>
            </div>
            """
            st.markdown(html_content, unsafe_allow_html=True)
            
            # Action Bar
            col_actions = st.columns([1, 2, 8])
            
            with col_actions[1]:
                # Deep Dive Button logic
                # We use an expander. When opened, it triggers the OCDS fetch.
                with st.expander("🔎 INSPECT DATA"):
                    with st.spinner(f"Establish link to OCDS Node: {code}..."):
                        ocds_data = fetch_ocds_data(code)
                        
                        if ocds_data:
                            items = parse_ocds_items(ocds_data)
                            
                            st.markdown("##### 📦 Technical Specifications (Items)")
                            if items:
                                df = pd.DataFrame(items)
                                st.dataframe(
                                    df, 
                                    use_container_width=True,
                                    column_config={
                                        "Category URI": st.column_config.LinkColumn("UNSPSC Definition")
                                    }
                                )
                            else:
                                st.warning("No itemized data available in OCDS record.")
                                
                            # Optional: Show Raw JSON for "Hacker" feel
                            if st.checkbox("Show Raw JSON Payload", key=f"raw_{code}"):
                                st.json(ocds_data)
                        else:
                            st.error("OCDS Link Failed. Tender might be closed or archived.")

            with col_actions[0]:
                 st.link_button("🔗 Web", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")