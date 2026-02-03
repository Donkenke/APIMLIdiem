import streamlit as st
import requests
import urllib3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & SETUP ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="Monitor Licitaciones", page_icon="⚡")

# Safe import for scraping features (prevents crash if bs4 is missing)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- 2. CSS: COMPACT TABLE DESIGN ---
st.markdown("""
<style>
    /* RESET */
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    
    /* TABLE HEADER */
    .mp-table-header {
        display: flex;
        background-color: #F8FAFC;
        border-bottom: 2px solid #E2E8F0;
        border-top: 1px solid #E2E8F0;
        padding: 8px 12px;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* TABLE ROW */
    .mp-table-row {
        display: flex;
        background-color: #FFFFFF;
        border-bottom: 1px solid #F1F5F9;
        padding: 6px 12px;
        align-items: flex-start;
        transition: background 0.1s;
        line-height: 1.3;
    }
    .mp-table-row:hover {
        background-color: #F8FAFC;
        border-left: 3px solid #2563EB;
        padding-left: 9px;
    }

    /* COLUMNS */
    .col-id   { width: 10%; min-width: 80px; }
    .col-desc { width: 45%; padding-right: 15px; }
    .col-org  { width: 25%; padding-right: 10px; }
    .col-date { width: 12%; text-align: right; }
    .col-btn  { width: 8%;  text-align: right; }

    /* TYPOGRAPHY */
    .txt-id { font-family: 'Consolas', monospace; font-weight: 700; color: #2563EB; font-size: 12px; }
    .txt-tag { display: inline-block; background: #EFF6FF; color: #1E40AF; font-size: 9px; font-weight: 600; padding: 1px 5px; border-radius: 4px; margin-bottom: 3px; border: 1px solid #DBEAFE; margin-right: 3px; }
    .txt-title { display: block; font-size: 13px; font-weight: 600; color: #1E293B; margin-bottom: 2px; }
    .txt-summary { display: block; font-size: 11px; color: #64748B; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .txt-org-name { display: block; font-size: 11px; font-weight: 700; color: #334155; }
    .txt-org-unit { display: block; font-size: 10px; color: #94A3B8; margin-top: 1px; }
    .txt-date-label { font-size: 9px; color: #94A3B8; text-transform: uppercase; }
    .txt-date-val   { font-size: 11px; font-weight: 600; color: #DC2626; }
    
    /* BUTTON OVERRIDES */
    .stButton button {
        background-color: white; color: #2563EB; border: 1px solid #BFDBFE;
        padding: 0px 10px; font-size: 11px; border-radius: 4px; height: 28px; line-height: 28px;
    }
    .stButton button:hover { border-color: #2563EB; color: #1E40AF; background-color: #EFF6FF; }
    div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC & FILTERS ---

CATEGORIES = {
    "Laboratorio": ["laboratorio", "ensayo", "hormigón", "asfalto", "suelo", "probeta", "áridos"],
    "Ingeniería": ["ingeniería", "diseño", "cálculo", "consultoría", "asesoría", "estructura", "sísmico"],
    "ITO": ["ito", "inspección", "supervisión", "fiscalización"]
}

EXCLUDE_KEYWORDS = ["odontología", "dental", "médico", "clínico", "salud", "funda", "resina"]

def categorize_text(text):
    text = text.lower()
    found = []
    for cat, kws in CATEGORIES.items():
        if any(k in text for k in kws):
            found.append(cat)
    return found

# --- 4. REAL API FETCHING ---

@st.cache_data(ttl=900, show_spinner=False)
def fetch_live_feed(ticket, days):
    """
    Fetches REAL data from MercadoPublico API.
    """
    results = []
    for i in range(days):
        date_q = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        
        try:
            r = requests.get(url, params={'fecha': date_q, 'ticket': ticket}, verify=False, timeout=5)
            if r.status_code == 200:
                data = r.json()
                items = data.get("Listado", [])
                
                for item in items:
                    name = item.get("Nombre", "").upper()
                    desc = item.get("Descripcion", "").upper()
                    full_text = name + " " + desc
                    
                    # 1. Filter: Exclude bad keywords
                    if any(ex.upper() in full_text for ex in EXCLUDE_KEYWORDS):
                        continue
                        
                    # 2. Filter: Must have at least one relevant keyword? (Optional)
                    # For now, we accept everything unless excluded, or you can uncomment below:
                    # if not any(k.upper() in full_text for sublist in CATEGORIES.values() for k in sublist): continue

                    # 3. Safe Extraction (Fixing the Crash)
                    buyer = item.get("Comprador")
                    if not isinstance(buyer, dict): 
                        buyer = {} # Force dict if None/String
                        
                    # Calculate Tags
                    item["_tags"] = categorize_text(full_text)
                    item["_org"] = buyer.get("NombreOrganismo", "Organismo Desconocido")
                    item["_unit"] = buyer.get("NombreUnidad", "")
                    
                    results.append(item)
        except Exception:
            pass
            
    return results

@st.cache_data(ttl=3600)
def scrape_details_bs4(code):
    """
    Real scraping using BeautifulSoup (Safe Mode)
    """
    if not HAS_BS4:
        return {"Error": "Librería BeautifulSoup no instalada."}
        
    url = f"http://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={code}"
    data = {"Requisitos": "", "Criterios": [], "Monto": "--"}
    
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try to find requirements (Heuristic: Look for long text in spans)
        # This is a basic implementation to prevent crashes
        lbl_monto = soup.find("span", id=lambda x: x and "lblMontoEstimado" in x)
        if lbl_monto: data["Monto"] = lbl_monto.get_text(strip=True)
        
        return data
    except:
        return {}

# --- 5. RENDER UI ---

if "selected_tender" not in st.session_state:
    st.session_state.selected_tender = None

def select_tender(t):
    st.session_state.selected_tender = t

# Sidebar
with st.sidebar:
    st.title("⚙️ Configuración")
    ticket = st.secrets.get("MP_TICKET") or st.text_input("API Ticket", type="password")
    days = st.slider("Días", 1, 5, 2)

# Main
st.title("Monitor Licitaciones")

if not ticket:
    st.warning("🔒 Ingresa tu Ticket API para conectar.")
    st.stop()

# Load Data
with st.spinner("Conectando a MercadoPúblico..."):
    tenders = fetch_live_feed(ticket, days)

if st.session_state.selected_tender:
    # --- DETAIL VIEW ---
    t = st.session_state.selected_tender
    st.button("← Volver al Listado", on_click=select_tender, args=(None,))
    
    st.markdown(f"### {t['CodigoExterno']} - {t['Nombre']}")
    st.info(t['Descripcion'])
    
    # Scrape on demand
    if HAS_BS4:
        with st.spinner("Analizando ficha web..."):
            details = scrape_details_bs4(t['CodigoExterno'])
            if details.get("Monto"):
                st.metric("Monto Estimado", details["Monto"])
    else:
        st.warning("Scraper desactivado (falta dependencia).")

else:
    # --- TABLE VIEW ---
    st.markdown(f"**{len(tenders)} Licitaciones encontradas**")
    
    # Header
    st.markdown("""
    <div class="mp-table-header">
        <div class="col-id">ID</div>
        <div class="col-desc">Descripción</div>
        <div class="col-org">Organismo</div>
        <div class="col-date">Cierre</div>
        <div class="col-btn">Acción</div>
    </div>
    """, unsafe_allow_html=True)

    if not tenders:
        st.info("No se encontraron resultados.")

    for row in tenders:
        # Prepare Data
        code = row.get("CodigoExterno")
        title = row.get("Nombre")
        summary = row.get("Descripcion")
        org_name = row.get("_org")
        org_unit = row.get("_unit")
        tags = row.get("_tags", [])
        
        # Date Clean
        f_close = row.get("FechaCierre", "")
        if f_close: f_close = f_close.split("T")[0]
        else: f_close = "--"

        # HTML Components
        tags_html = "".join([f'<span class="txt-tag">{tag}</span>' for tag in tags])

        # Render Container
        with st.container():
            c1, c2 = st.columns([0.92, 0.08])
            
            with c1:
                st.markdown(f"""
                <div class="mp-table-row">
                    <div class="col-id"><span class="txt-id">{code}</span></div>
                    <div class="col-desc">
                        {tags_html}
                        <span class="txt-title">{title}</span>
                        <span class="txt-summary">{summary}</span>
                    </div>
                    <div class="col-org">
                        <span class="txt-org-name">{org_name}</span>
                        <span class="txt-org-unit">{org_unit}</span>
                    </div>
                    <div class="col-date">
                        <div class="txt-date-label">Cierre</div>
                        <div class="txt-date-val">{f_close}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with c2:
                # Spacer for button alignment
                st.markdown('<div style="height: 12px"></div>', unsafe_allow_html=True)
                if st.button("Ver", key=f"b_{code}"):
                    select_tender(row)
                    st.rerun()
            
            # Remove gap
            st.markdown('<style>div[data-testid="stVerticalBlock"] > div { margin-bottom: -15px; }</style>', unsafe_allow_html=True)
