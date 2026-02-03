import streamlit as st
import requests
import sqlite3
import json
import urllib3
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURATION & SETUP ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="Monitor Licitaciones", page_icon="📋")

DB_FILE = "tenders_db_v3.db"

# --- LOGIC FROM REFERENCE SCRIPT ---
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}

EXCLUDE_KEYWORDS = [
    "odontología", "dental", "médico", "clínico", "salud", "examen de sangre", 
    "psicotécnico", "funda", "resina", "mallas bioabsorbibles", "arqueológico",
    "artística", "evento", "limpieza de fosas", "escritorio"
]

ALL_KEYWORDS = [kw for sublist in CATEGORIES.values() for kw in sublist]

# --- COMPACT CSS FOR TABLE DESIGN ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');
    
    .stApp { 
        background-color: #FAFBFC; 
        font-family: 'IBM Plex Sans', sans-serif; 
        color: #1A1F36; 
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Compact Table Container */
    .table-container {
        background: white;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        overflow: hidden;
        margin-bottom: 16px;
    }
    
    /* Compact Header */
    .table-header {
        display: grid;
        grid-template-columns: 110px 2fr 1.5fr 1fr 220px 140px;
        gap: 12px;
        align-items: center;
        background: #F8F9FA;
        border-bottom: 2px solid #DEE2E6;
        padding: 10px 16px;
        font-weight: 600;
        font-size: 0.7rem;
        color: #495057;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    /* Compact Row */
    .table-row {
        display: grid;
        grid-template-columns: 110px 2fr 1.5fr 1fr 220px 140px;
        gap: 12px;
        align-items: center;
        background-color: #FFFFFF;
        border-bottom: 1px solid #F1F3F5;
        padding: 10px 16px;
        transition: background-color 0.1s;
    }
    
    .table-row:hover { 
        background-color: #F8F9FA;
    }

    /* Cell Styles - Compact */
    .cell-id { 
        font-family: 'JetBrains Mono', monospace; 
        font-size: 0.75rem; 
        color: #4263EB; 
        font-weight: 600;
        background: #EDF2FF;
        padding: 4px 8px;
        border-radius: 4px;
        text-align: center;
        width: fit-content;
    }
    
    .cell-title { 
        font-size: 0.85rem; 
        font-weight: 600; 
        color: #212529; 
        line-height: 1.3;
        margin-bottom: 3px;
    }
    
    .cell-org { 
        font-size: 0.8rem; 
        font-weight: 500; 
        color: #343A40; 
        line-height: 1.3;
    }
    
    .cell-unit { 
        font-size: 0.75rem; 
        color: #6C757D; 
        line-height: 1.3;
    }
    
    .cell-date { 
        font-size: 0.75rem; 
        color: #495057; 
        line-height: 1.5;
    }
    
    .cell-deadline { 
        font-size: 0.75rem; 
        color: #DC3545; 
        font-weight: 600;
    }

    .tag-cat {
        display: inline-block;
        font-size: 0.65rem;
        padding: 2px 7px;
        border-radius: 3px;
        background: #D0EBFF;
        color: #1864AB;
        font-weight: 500;
        margin-right: 4px;
        margin-bottom: 3px;
    }

    /* Compact Buttons */
    .stButton button { 
        padding: 5px 10px !important; 
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
        height: 28px !important;
    }
    
    div[data-testid="column"] { 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .stats-badge {
        display: inline-block;
        background: linear-gradient(135deg, #4263EB 0%, #3B5BDB 100%);
        color: white;
        padding: 6px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id TEXT PRIMARY KEY,
            saved BOOLEAN DEFAULT 0,
            json_data TEXT,
            added_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def toggle_save(tender_data):
    code = tender_data['CodigoExterno']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT saved FROM tenders WHERE id = ?", (code,))
    row = c.fetchone()
    
    if row and row[0]:
        c.execute("DELETE FROM tenders WHERE id = ?", (code,))
        st.toast(f"❌ Eliminado: {code}")
    else:
        json_str = json.dumps(tender_data, ensure_ascii=False)
        date_now = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT OR REPLACE INTO tenders (id, saved, json_data, added_date) VALUES (?, 1, ?, ?)", 
                  (code, json_str, date_now))
        st.toast(f"💾 Guardado: {code}")
        
    conn.commit()
    conn.close()

def get_saved_tenders():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT json_data FROM tenders WHERE saved = 1 ORDER BY added_date DESC", conn)
    conn.close()
    tenders = []
    for _, row in df.iterrows():
        tenders.append(json.loads(row['json_data']))
    return tenders

def get_saved_ids():
    conn = sqlite3.connect(DB_FILE)
    ids = [row[0] for row in conn.execute("SELECT id FROM tenders WHERE saved = 1")]
    conn.close()
    return set(ids)

# --- BUSINESS LOGIC ---
def is_relevant(name, desc=""):
    full_text = (name + " " + desc).lower()
    if any(ex in full_text for ex in EXCLUDE_KEYWORDS):
        return False
    if any(k in full_text for k in ALL_KEYWORDS):
        return True
    return False

def categorize_tender(tender):
    text = (tender.get('Nombre', '') + " " + tender.get('Descripcion', '')).lower()
    detected_cats = []
    for cat_name, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            detected_cats.append(cat_name)
    return detected_cats

# --- API FETCHING ---
@st.cache_data(ttl=900, show_spinner=False)
def fetch_feed(ticket, days=2):
    results = []
    pbar = st.progress(0, text="Escaneando MercadoPúblico...")
    
    for i in range(days):
        date_query = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        try:
            r = requests.get(url, params={'fecha': date_query, 'ticket': ticket}, verify=False, timeout=8)
            if r.status_code == 200:
                data = r.json()
                tenders = data.get("Listado", [])
                
                for t in tenders:
                    if is_relevant(t.get('Nombre', ''), t.get('Descripcion', '')):
                        if not t.get('FechaCreacion'):
                             t['FechaCreacion'] = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT00:00:00")
                        
                        t['CategoriasIDIEM'] = categorize_tender(t)
                        results.append(t)
                        
        except Exception as e:
            print(f"Error {date_query}: {e}")
            
        pbar.progress((i+1)/days)
    
    pbar.empty()
    return results

# --- HELPER FUNCTIONS FOR DATA EXTRACTION ---
def safe_get_nested(data, *keys, default=""):
    """Safely get nested dictionary values"""
    try:
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
            else:
                return default
        return value if value is not None else default
    except:
        return default

def parse_date(date_str, format_out="%d/%m/%Y"):
    """Parse ISO date string to formatted date"""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime(format_out)
    except:
        return date_str

def parse_datetime(datetime_str, format_out="%d/%m/%Y %H:%M"):
    """Parse ISO datetime string to formatted datetime"""
    if not datetime_str:
        return ""
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime(format_out)
    except:
        return datetime_str

# --- UI COMPONENTS ---
def render_header():
    st.markdown("""
    <div class="table-container">
        <div class="table-header">
            <div>ID</div>
            <div>LICITACIÓN</div>
            <div>ORGANISMO</div>
            <div>UNIDAD</div>
            <div>FECHAS</div>
            <div>ACCIONES</div>
        </div>
    """, unsafe_allow_html=True)

def render_row(tender, saved_ids, index):
    code = tender.get('CodigoExterno', 'N/A')
    is_saved = code in saved_ids
    
    # Extract Comprador data properly
    comprador = tender.get('Comprador', {})
    if not isinstance(comprador, dict):
        comprador = {}
    
    org_name = comprador.get('NombreOrganismo', 'Organismo no indicado')
    unit_name = comprador.get('NombreUnidad', 'Sin unidad')
    region = comprador.get('RegionUnidad', '')
    
    # Extract Fechas properly
    fechas = tender.get('Fechas', {})
    if not isinstance(fechas, dict):
        fechas = {}
    
    f_inicio = parse_datetime(fechas.get('FechaInicio', ''))
    f_cierre = parse_datetime(fechas.get('FechaCierre', ''))
    f_pub = parse_datetime(fechas.get('FechaPublicacion', ''))
    
    # Get URL
    url_publica = tender.get('URL_Publica', f"https://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
    
    # Categories
    cats = tender.get('CategoriasIDIEM', [])
    tags_html = "".join([f"<span class='tag-cat'>{c}</span>" for c in cats])

    # Render Row
    st.markdown(f"""
    <div class="table-row">
        <div>
            <div class="cell-id">{code}</div>
        </div>
        <div>
            {f'<div style="margin-bottom: 4px;">{tags_html}</div>' if tags_html else ''}
            <div class="cell-title">{tender.get('Nombre', 'Sin título')}</div>
        </div>
        <div>
            <div class="cell-org">{org_name}</div>
            {f'<div class="cell-unit" style="margin-top: 2px;">{region}</div>' if region else ''}
        </div>
        <div>
            <div class="cell-unit">{unit_name}</div>
        </div>
        <div>
            {f'<div class="cell-date">Inicio: {f_inicio}</div>' if f_inicio else ''}
            {f'<div class="cell-deadline">Cierre: {f_cierre}</div>' if f_cierre else '<div class="cell-date">Sin fecha cierre</div>'}
            {f'<div class="cell-date" style="font-size: 0.7rem; margin-top: 2px;">Pub: {f_pub}</div>' if f_pub else ''}
        </div>
        <div style="display: flex; gap: 6px;">
    """, unsafe_allow_html=True)
    
    # Action Buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        btn_text = "⭐" if is_saved else "☆"
        if st.button(btn_text, key=f"save_{code}_{index}", use_container_width=True, 
                    type="primary" if is_saved else "secondary"):
            toggle_save(tender)
            st.rerun()
    
    with col2:
        st.link_button("🔗", url_publica, use_container_width=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_footer():
    st.markdown("</div>", unsafe_allow_html=True)

# --- MAIN APP ---
init_db()

# Sidebar
with st.sidebar:
    st.markdown("# 📋 Monitor Licitaciones")
    st.markdown("---")
    
    ticket = st.secrets.get("MP_TICKET") or st.text_input("🔑 Ticket API", type="password")
    
    if not ticket:
        st.warning("🔒 Se requiere ticket de API")
        st.stop()
        
    days = st.slider("📅 Días de búsqueda", 1, 7, 2)
    
    st.markdown("---")
    st.info(f"**{len(ALL_KEYWORDS)}** palabras clave activas")
    
    with st.expander("🏷️ Ver categorías"):
        for cat, keywords in CATEGORIES.items():
            st.markdown(f"**{cat}**")
            st.caption(", ".join(keywords[:3]) + "...")

# Main content
st.markdown("# Panel de Control")
st.markdown("---")

tab_feed, tab_saved = st.tabs(["📡 Feed en Vivo", "⭐ Guardados"])

with tab_feed:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### Licitaciones Filtradas")
    
    with col2:
        if st.button("🔄 Actualizar", use_container_width=True):
            fetch_feed.clear()
            st.rerun()
        
    feed_data = fetch_feed(ticket, days)
    saved_ids_set = get_saved_ids()
    
    st.markdown(f"<span class='stats-badge'>{len(feed_data)} resultados</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not feed_data:
        st.info("📭 No se encontraron licitaciones con los criterios configurados.")
    else:
        render_header()
        for idx, t in enumerate(feed_data):
            render_row(t, saved_ids_set, idx)
        render_footer()

with tab_saved:
    saved_data = get_saved_tenders()
    saved_ids_set = get_saved_ids()
    
    st.markdown("### Biblioteca Personal")
    st.markdown(f"<span class='stats-badge'>{len(saved_data)} guardadas</span>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if not saved_data:
        st.info("⭐ Guarda licitaciones desde el feed para acceder a ellas rápidamente.")
    else:
        render_header()
        for idx, t in enumerate(saved_data):
            render_row(t, saved_ids_set, f"saved_{idx}")
        render_footer()
