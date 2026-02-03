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

# --- ENHANCED CSS FOR CLEAN TABLE DESIGN ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');
    
    /* Global Styles */
    .stApp { 
        background-color: #FAFBFC; 
        font-family: 'Work Sans', -apple-system, BlinkMacSystemFont, sans-serif; 
        color: #1A1F36; 
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Table Container */
    .table-container {
        background: white;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        overflow: hidden;
        margin-bottom: 24px;
    }
    
    /* TABLE HEADER */
    .table-header {
        display: grid;
        grid-template-columns: 100px 1fr 280px 160px 180px;
        gap: 16px;
        align-items: center;
        background: linear-gradient(to bottom, #F7F8FA 0%, #F3F4F6 100%);
        border-bottom: 1px solid #E1E4E8;
        padding: 14px 20px;
        font-weight: 600;
        font-size: 0.75rem;
        color: #6B7B93;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* TABLE ROW */
    .table-row {
        display: grid;
        grid-template-columns: 100px 1fr 280px 160px 180px;
        gap: 16px;
        align-items: center;
        background-color: #FFFFFF;
        border-bottom: 1px solid #F0F2F5;
        padding: 16px 20px;
        transition: all 0.15s ease;
    }
    
    .table-row:hover { 
        background-color: #F8FAFC;
        box-shadow: inset 0 0 0 1px #E3E8EF;
    }
    
    .table-row:last-child {
        border-bottom: none;
    }

    /* Cell Styles */
    .cell-id { 
        font-family: 'JetBrains Mono', monospace; 
        font-size: 0.8rem; 
        color: #5B6BF5; 
        font-weight: 600;
        background: linear-gradient(135deg, #F0F3FF 0%, #E8EDFF 100%);
        padding: 6px 10px;
        border-radius: 6px;
        text-align: center;
        width: fit-content;
    }
    
    .cell-title { 
        font-size: 0.925rem; 
        font-weight: 600; 
        color: #1A1F36; 
        line-height: 1.4;
        margin-bottom: 4px;
    }
    
    .cell-desc { 
        font-size: 0.8rem; 
        color: #6B7B93; 
        line-height: 1.45;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .cell-org { 
        font-size: 0.875rem; 
        font-weight: 600; 
        color: #2D3748; 
        margin-bottom: 2px;
    }
    
    .cell-unit { 
        font-size: 0.8rem; 
        color: #6B7B93; 
        margin-top: 2px;
    }
    
    .cell-date { 
        font-size: 0.8rem; 
        color: #525F7F; 
        line-height: 1.6;
    }
    
    .cell-deadline { 
        font-size: 0.8rem; 
        color: #E63946; 
        font-weight: 600;
        margin-top: 2px;
    }

    /* TAGS */
    .tag-container {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 8px;
    }
    
    .tag-cat {
        display: inline-block;
        font-size: 0.7rem;
        padding: 4px 10px;
        border-radius: 4px;
        background: linear-gradient(135deg, #E8F0FE 0%, #D6E4FF 100%);
        color: #1967D2;
        font-weight: 500;
        border: 1px solid #C2D9FF;
    }

    /* Checkbox Styling */
    .checkbox-cell {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .custom-checkbox {
        width: 18px;
        height: 18px;
        border: 2px solid #D1D5DB;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .custom-checkbox:hover {
        border-color: #5B6BF5;
    }
    
    .custom-checkbox.checked {
        background-color: #5B6BF5;
        border-color: #5B6BF5;
    }

    /* Override Streamlit Button Styles */
    .stButton button { 
        padding: 8px 14px !important; 
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        transition: all 0.2s !important;
        border: 1px solid #E1E4E8 !important;
    }
    
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    }
    
    /* Column alignment */
    div[data-testid="column"] { 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Stats Badge */
    .stats-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.875rem;
        font-weight: 600;
        margin-left: 12px;
    }
    
    /* Empty State */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #6B7B93;
    }
    
    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 16px;
        opacity: 0.3;
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

# --- UI COMPONENTS ---
def render_header():
    st.markdown("""
    <div class="table-container">
        <div class="table-header">
            <div>ID</div>
            <div>LICITACIÓN</div>
            <div>ORGANISMO</div>
            <div>FECHAS</div>
            <div style="text-align: center;">ACCIONES</div>
        </div>
    """, unsafe_allow_html=True)

def render_row(tender, saved_ids, index):
    code = tender.get('CodigoExterno')
    is_saved = code in saved_ids
    
    buyer = tender.get('Comprador', {})
    if not isinstance(buyer, dict): 
        buyer = {}
    
    org_name = buyer.get('NombreOrganismo', 'Organismo no indicado')
    unit_name = buyer.get('NombreUnidad', '')
    region = buyer.get('RegionUnidad', '')
    
    # Parse dates
    try:
        f_pub = datetime.strptime(tender.get('FechaCreacion', '')[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except: 
        f_pub = "--"
    
    try:
        f_close_raw = tender.get('FechaCierre', '')
        if f_close_raw:
            f_close = datetime.strptime(f_close_raw, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y")
        else:
            f_close = "Sin fecha"
    except: 
        f_close = "Sin fecha"

    # Categories
    cats = tender.get('CategoriasIDIEM', [])
    tags_html = "".join([f"<span class='tag-cat'>{c}</span>" for c in cats])

    # Description
    description = tender.get('Descripcion', '')[:200]
    
    # Row HTML
    st.markdown(f"""
    <div class="table-row">
        <div>
            <div class="cell-id">{code}</div>
        </div>
        <div>
            <div class="tag-container">{tags_html}</div>
            <div class="cell-title">{tender.get('Nombre', 'Sin título')}</div>
            <div class="cell-desc">{description}</div>
        </div>
        <div>
            <div class="cell-org">{org_name}</div>
            {f'<div class="cell-unit">{unit_name}</div>' if unit_name else ''}
            {f'<div class="cell-unit" style="font-style:italic; color: #9CA3AF;">{region}</div>' if region else ''}
        </div>
        <div>
            <div class="cell-date">Publicación: {f_pub}</div>
            <div class="cell-deadline">Cierre: {f_close}</div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
    """, unsafe_allow_html=True)
    
    # Action Buttons using Streamlit columns for proper alignment
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        btn_text = "⭐" if is_saved else "☆"
        if st.button(btn_text, key=f"save_{code}_{index}", use_container_width=True, 
                    type="primary" if is_saved else "secondary"):
            toggle_save(tender)
            st.rerun()
    
    with col_btn2:
        st.link_button("🔗", f"https://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}", 
                      use_container_width=True)
    
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
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <h3>No se encontraron licitaciones</h3>
            <p>No hay licitaciones que coincidan con los criterios de búsqueda.</p>
        </div>
        """, unsafe_allow_html=True)
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
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">⭐</div>
            <h3>Biblioteca vacía</h3>
            <p>Guarda licitaciones desde el feed para acceder a ellas rápidamente.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        render_header()
        for idx, t in enumerate(saved_data):
            render_row(t, saved_ids_set, f"saved_{idx}")
        render_footer()
