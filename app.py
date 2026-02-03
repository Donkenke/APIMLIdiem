import streamlit as st
import requests
import urllib3
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & SETUP ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="Monitor Licitaciones", page_icon="⚡")

# Safe import for scraping features (prevents crash)
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# --- 2. CSS: THE "REAL TABLE" LOOK ---
# This forces the tight, spreadsheet-like density you asked for.
st.markdown("""
<style>
    /* RESET CONTAINER MARGINS */
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    
    /* TABLE STYLES */
    .mp-table-header {
        display: flex;
        background-color: #F8FAFC;
        border-bottom: 2px solid #E2E8F0;
        border-top: 1px solid #E2E8F0;
        padding: 8px 12px;
        font-family: 'Source Sans Pro', sans-serif;
        font-size: 12px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .mp-table-row {
        display: flex;
        background-color: #FFFFFF;
        border-bottom: 1px solid #F1F5F9;
        padding: 8px 12px;
        align-items: flex-start; /* Top align content */
        transition: background 0.1s;
        cursor: pointer;
        line-height: 1.3;
    }
    
    .mp-table-row:hover {
        background-color: #F8FAFC;
        border-left: 3px solid #2563EB;
        padding-left: 9px; /* Compensate for border */
    }

    /* COLUMNS WIDTHS */
    .col-id   { width: 12%; min-width: 90px; }
    .col-desc { width: 43%; padding-right: 15px; }
    .col-org  { width: 25%; padding-right: 10px; }
    .col-date { width: 12%; text-align: right; }
    .col-btn  { width: 8%;  text-align: right; display: flex; justify-content: flex-end; align-items: center;}

    /* TYPOGRAPHY SPECIFICS */
    .txt-id { 
        font-family: 'Courier New', monospace; 
        font-weight: 700; 
        color: #2563EB; 
        font-size: 13px; 
    }
    
    .txt-tag {
        display: inline-block;
        background: #EFF6FF;
        color: #1E40AF;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
        margin-bottom: 4px;
        text-transform: uppercase;
    }

    .txt-title {
        display: block;
        font-size: 14px;
        font-weight: 600;
        color: #1E293B;
        margin-bottom: 2px;
    }

    .txt-summary {
        display: block;
        font-size: 12px;
        color: #64748B;
        display: -webkit-box;
        -webkit-line-clamp: 2; /* Limit to 2 lines */
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .txt-org-name {
        display: block;
        font-size: 12px;
        font-weight: 700;
        color: #334155;
    }
    
    .txt-org-unit {
        display: block;
        font-size: 11px;
        color: #94A3B8;
        margin-top: 1px;
    }

    .txt-date-label { font-size: 10px; color: #94A3B8; text-transform: uppercase; }
    .txt-date-val   { font-size: 12px; font-weight: 600; color: #DC2626; }
    
    /* HIDE STREAMLIT DEFAULT BUTTON STYLES */
    .stButton button {
        background-color: white;
        color: #2563EB;
        border: 1px solid #BFDBFE;
        padding: 2px 10px;
        font-size: 11px;
        border-radius: 4px;
        height: auto;
    }
    .stButton button:hover {
        border-color: #2563EB;
        color: #1E40AF;
        background-color: #EFF6FF;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOGIC ---

CATEGORIES = {
    "Laboratorio": ["laboratorio", "ensayo", "hormigón", "asfalto", "suelo"],
    "Ingeniería": ["ingeniería", "diseño", "cálculo", "consultoría", "asesoría"],
    "ITO": ["ito", "inspección", "supervisión", "fiscalización"]
}

@st.cache_data(ttl=600)
def get_feed_data():
    """
    Fetches real data or returns structure matching your JSON.
    """
    # ... (Keep your existing API call logic here) ...
    # For DEMO, I will manually reconstruct the structure from your JSON snippets
    # so you can see it working immediately without API keys.
    
    # EXAMPLE DATA based on your 'idiem_tenders_7days.json' snippet
    mock_data = [
        {
            "CodigoExterno": "2369-5-LR26",
            "Nombre": "PP 114 Conserv. infraestructura menor ciclovías",
            "Estado": "Publicada",
            "FechaCierre": "2026-03-05T15:00:00",
            "Descripcion": "La Municipalidad de Arica requiere ejecutar proyecto denominado Conservación infraestructura menor para el transporte público región de Arica.",
            "Comprador": {
                "NombreOrganismo": "I MUNICIPALIDAD DE ARICA",
                "NombreUnidad": "SECRETARIA COMUNAL DE PLANIFICACIÓN"
            }
        },
        {
            "CodigoExterno": "1704-25-LP26",
            "Nombre": "SERVICIO DE SOPORTE Y MANTENCIÓN DE INFRAESTRUCTURA",
            "Estado": "Publicada",
            "FechaCierre": "2026-02-28T12:00:00",
            "Descripcion": "Servicio de soporte y mantención de infraestructura de hiperconvergencia para el hospital.",
            "Comprador": {
                "NombreOrganismo": "SERVICIO DE SALUD VINA DEL MAR QUILLOTA",
                "NombreUnidad": "Hospital San Martín de Quillota"
            }
        }
    ]
    return mock_data

def process_tenders(raw_list):
    """
    Processing logic to safely extract fields and assign categories.
    """
    processed = []
    for item in raw_list:
        # --- 1. SAFE EXTRACTION (The Fix for your crash) ---
        # We use .get() with defaults everywhere.
        buyer = item.get("Comprador", {}) or {} # Handle if Comprador is None
        
        # --- 2. CATEGORY LOGIC ---
        name = item.get("Nombre", "").upper()
        desc = item.get("Descripcion", "").upper()
        full_text = name + " " + desc
        
        found_cats = []
        for cat, keywords in CATEGORIES.items():
            if any(k.upper() in full_text for k in keywords):
                found_cats.append(cat)
        
        # Clean Date
        raw_date = item.get("FechaCierre", "")
        clean_date = raw_date.split("T")[0] if raw_date else "N/A"

        processed.append({
            "id": item.get("CodigoExterno", "---"),
            "title": item.get("Nombre", "Sin Título"),
            "summary": item.get("Descripcion", ""),
            "org_name": buyer.get("NombreOrganismo", "Organismo Desconocido"),
            "org_unit": buyer.get("NombreUnidad", ""),
            "date_close": clean_date,
            "tags": found_cats[:2], # Limit to 2 tags
            "raw": item
        })
    return processed

# --- 4. RENDER UI ---

if "selected_code" not in st.session_state:
    st.session_state.selected_code = None

def select_item(code):
    st.session_state.selected_code = code

# Load Data
data = get_feed_data()
rows = process_tenders(data)

# HEADER
st.title("Monitor Licitaciones")
st.markdown(f"**{len(rows)} Resultados encontrados**")

if st.session_state.selected_code:
    # --- DETAIL VIEW ---
    st.button("← Volver", on_click=select_item, args=(None,))
    st.info(f"Detalle para {st.session_state.selected_code} (Aquí iría tu lógica de Playwright/BS4)")
    # ... Your scraping logic goes here ...

else:
    # --- TABLE VIEW (THE FIX) ---
    
    # 1. Render Header Row
    st.markdown("""
    <div class="mp-table-header">
        <div class="col-id">ID Licitación</div>
        <div class="col-desc">Descripción del Requerimiento</div>
        <div class="col-org">Organismo / Unidad</div>
        <div class="col-date">Cierre</div>
        <div class="col-btn">Acción</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Render Data Rows
    for row in rows:
        # Generate HTML for the row
        # We perform the logic *inside* Python, but render pure HTML
        
        # Safe Tag rendering
        tags_html = "".join([f'<span class="txt-tag">{t}</span> ' for t in row['tags']])
        
        # Safe ID for button key
        btn_key = f"btn_{row['id']}"

        # THE CONTAINER STRATEGY
        # We use st.container to group the HTML row and the invisible Streamlit button
        with st.container():
            # We create 2 columns: 
            # Col A (92%): The HTML Row (Visuals)
            # Col B (8%):  The Streamlit Button (Interaction)
            # This is a hack to get "Custom HTML" + "Python Click Event"
            
            c1, c2 = st.columns([0.92, 0.08])
            
            with c1:
                st.markdown(f"""
                <div class="mp-table-row">
                    <div class="col-id">
                        <span class="txt-id">{row['id']}</span>
                    </div>
                    <div class="col-desc">
                        {tags_html}
                        <span class="txt-title">{row['title']}</span>
                        <span class="txt-summary">{row['summary']}</span>
                    </div>
                    <div class="col-org">
                        <span class="txt-org-name">{row['org_name']}</span>
                        <span class="txt-org-unit">{row['org_unit']}</span>
                    </div>
                    <div class="col-date">
                        <div class="txt-date-label">Cierre</div>
                        <div class="txt-date-val">{row['date_close']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with c2:
                # Invisible alignment spacer
                st.markdown('<div style="height: 18px"></div>', unsafe_allow_html=True) 
                if st.button("Ver", key=btn_key):
                    select_item(row['id'])
                    st.rerun()
            
            # Reduce gap between rows
            st.markdown('<style>div[data-testid="stVerticalBlock"] > div { margin-bottom: -15px; }</style>', unsafe_allow_html=True)
