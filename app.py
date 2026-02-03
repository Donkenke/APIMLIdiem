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

# --- CSS FOR TABLE LAYOUT ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    .stApp { background-color: #F9FAFB; font-family: 'Inter', sans-serif; color: #1F2937; }
    
    /* TABLE HEADER */
    .table-header {
        display: flex;
        align-items: center;
        background-color: #F3F4F6;
        border-bottom: 2px solid #E5E7EB;
        padding: 12px 10px;
        font-weight: 600;
        font-size: 0.8rem;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 5px;
    }
    
    /* TABLE ROW */
    .table-row {
        display: flex;
        align-items: center;
        background-color: #FFFFFF;
        border-bottom: 1px solid #F3F4F6;
        padding: 12px 10px;
        transition: background-color 0.1s;
    }
    .table-row:hover { background-color: #EFF6FF; }
    
    /* COLUMN WIDTHS (Must match Streamlit Columns) */
    /* 1: ID (10%)
       2: Nombre + Tags (40%)
       3: Organismo (25%)
       4: Fechas (15%)
       5: Acciones (10%)
    */

    .cell-id { font-family: monospace; font-size: 0.8rem; color: #2563EB; font-weight: 600; }
    .cell-title { font-size: 0.95rem; font-weight: 600; color: #111827; line-height: 1.3; }
    .cell-desc { font-size: 0.8rem; color: #6B7280; margin-top: 4px; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 90%; }
    .cell-org { font-size: 0.85rem; font-weight: 600; color: #374151; }
    .cell-unit { font-size: 0.8rem; color: #6B7280; display: block; }
    .cell-date { font-size: 0.8rem; color: #4B5563; text-align: right; }
    .cell-deadline { font-size: 0.8rem; color: #DC2626; font-weight: 600; text-align: right; display: block; }

    /* TAGS */
    .tag-cat {
        display: inline-block;
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 99px;
        background-color: #DBEAFE;
        color: #1E40AF;
        margin-right: 5px;
        margin-bottom: 4px;
        font-weight: 500;
    }

    /* Override Streamlit Button padding */
    .stButton button { padding: 4px 10px; font-size: 0.8rem; }
    
    div[data-testid="column"] { align-items: center; }
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Simplified Table: ID, Saved (bool), JSON (Data)
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
    
    # Check current state
    c.execute("SELECT saved FROM tenders WHERE id = ?", (code,))
    row = c.fetchone()
    
    if row and row[0]:
        # If saved, delete it (Unsave)
        c.execute("DELETE FROM tenders WHERE id = ?", (code,))
        st.toast(f"❌ Eliminado: {code}")
    else:
        # If not saved, insert it
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

# --- BUSINESS LOGIC (From Snippet) ---
def is_relevant(name, desc=""):
    full_text = (name + " " + desc).lower()
    # 1. Exclude forbidden words
    if any(ex in full_text for ex in EXCLUDE_KEYWORDS):
        return False
    # 2. Must have at least one keyword (Optional, remove if you want to see everything non-excluded)
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
                
                # Filter locally to avoid spam in UI
                for t in tenders:
                    if is_relevant(t.get('Nombre', ''), t.get('Descripcion', '')):
                        # Add missing logic for dates if API list is sparse
                        if not t.get('FechaCreacion'):
                             t['FechaCreacion'] = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT00:00:00")
                        
                        # Calculate Categories immediately
                        t['CategoriasIDIEM'] = categorize_tender(t)
                        results.append(t)
                        
        except Exception as e:
            print(f"Error {date_query}: {e}")
            
        pbar.progress((i+1)/days)
    
    pbar.empty()
    return results

# --- UI COMPONENTS ---
def render_header():
    # Matches columns: [1, 4, 3, 1.5, 1]
    st.markdown("""
    <div class="table-header">
        <div style="width: 9%;">ID</div>
        <div style="width: 35%;">LICITACIÓN</div>
        <div style="width: 28%;">ORGANISMO / UNIDAD</div>
        <div style="width: 15%; text-align: right;">FECHAS</div>
        <div style="width: 13%; text-align: center;">ACCIONES</div>
    </div>
    """, unsafe_allow_html=True)

def render_row(tender, saved_ids):
    # Data Preparation
    code = tender.get('CodigoExterno')
    is_saved = code in saved_ids
    
    # 1. Parse Comprador (Org + Unit)
    buyer = tender.get('Comprador', {})
    # Handle case where buyer might be null or string (API quirk)
    if not isinstance(buyer, dict): buyer = {}
    
    org_name = buyer.get('NombreOrganismo', 'Organismo no indicado')
    unit_name = buyer.get('NombreUnidad', '')
    
    # 2. Dates
    try:
        f_pub = datetime.strptime(tender.get('FechaCreacion', '')[:10], "%Y-%m-%d").strftime("%d/%m")
    except: f_pub = "--"
    
    try:
        f_close_raw = tender.get('FechaCierre', '')
        if f_close_raw:
            f_close = datetime.strptime(f_close_raw, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m %H:%M")
        else:
            f_close = "Sin Fecha"
    except: f_close = tender.get('FechaCierre')

    # 3. Categories HTML
    cats = tender.get('CategoriasIDIEM', [])
    tags_html = "".join([f"<span class='tag-cat'>{c}</span>" for c in cats])

    # 4. Streamlit Layout (Grid)
    # Uses container to create the row background effect
    with st.container():
        # Columns must align with Header % widths visually
        c1, c2, c3, c4, c5 = st.columns([1, 4, 3, 1.5, 1.2])
        
        with c1:
            st.markdown(f"<div class='cell-id'>{code}</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"<div>{tags_html}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='cell-title'>{tender.get('Nombre')}</div>", unsafe_allow_html=True)
            st.markdown(f"<span class='cell-desc'>{tender.get('Descripcion', '')}</span>", unsafe_allow_html=True)
            
        with c3:
            st.markdown(f"<div class='cell-org'>🏢 {org_name}</div>", unsafe_allow_html=True)
            if unit_name:
                st.markdown(f"<div class='cell-unit'>📍 {unit_name}</div>", unsafe_allow_html=True)
            region = buyer.get('RegionUnidad', '')
            if region:
                st.markdown(f"<div class='cell-unit' style='font-style:italic;'>{region}</div>", unsafe_allow_html=True)
                
        with c4:
            st.markdown(f"<div class='cell-date'>Pub: {f_pub}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='cell-deadline'>Cierre: {f_close}</div>", unsafe_allow_html=True)
            
        with c5:
            # Action Buttons
            btn_text = "⭐ Guardado" if is_saved else "☆ Guardar"
            btn_type = "primary" if is_saved else "secondary"
            
            if st.button(btn_text, key=f"btn_{code}", use_container_width=True, type=btn_type):
                toggle_save(tender)
                st.rerun()
                
            st.link_button("🔗 Ver Ficha", f"https://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}", use_container_width=True)
            
        st.markdown("<hr style='margin: 0; border-top: 1px solid #E5E7EB;'>", unsafe_allow_html=True)

# --- MAIN APP ---
init_db()

with st.sidebar:
    st.header("Monitor Licitaciones")
    ticket = st.secrets.get("MP_TICKET") or st.text_input("Ingresa Ticket API", type="password")
    
    if not ticket:
        st.warning("🔒 Se requiere ticket")
        st.stop()
        
    days = st.slider("Días de búsqueda", 1, 5, 2)
    st.info(f"Filtrando por {len(ALL_KEYWORDS)} palabras clave técnicas.")

st.title("Panel de Control")

tab_feed, tab_saved = st.tabs(["📡 Feed (Filtrado)", "⭐ Guardados"])

with tab_feed:
    if st.button("🔄 Actualizar Feed"):
        fetch_feed.clear()
        st.rerun()
        
    feed_data = fetch_feed(ticket, days)
    saved_ids_set = get_saved_ids()
    
    st.markdown(f"**Resultados:** {len(feed_data)} licitaciones relevantes encontradas.")
    
    render_header()
    if not feed_data:
        st.warning("No se encontraron licitaciones con las palabras clave configuradas.")
    else:
        for t in feed_data:
            render_row(t, saved_ids_set)

with tab_saved:
    saved_data = get_saved_tenders()
    saved_ids_set = get_saved_ids() # Refresh set
    
    st.markdown(f"**Biblioteca:** {len(saved_data)} licitaciones guardadas.")
    
    render_header()
    if not saved_data:
        st.info("No tienes licitaciones guardadas aún.")
    else:
        for t in saved_data:
            render_row(t, saved_ids_set)
