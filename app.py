import streamlit as st
import sqlite3
import json
from datetime import datetime
from utils import (
    fetch_tenders,
    categorize_tender,
    format_date,
    format_datetime,
    safe_get
)

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Monitor Licitaciones IDIEM", page_icon="📋")

DB_FILE = "tenders.db"

# --- STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');
    
    .stApp { 
        background-color: #F8F9FA; 
        font-family: 'Inter', sans-serif; 
    }
    
    /* Hide Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Table styling */
    .tender-table {
        background: white;
        border-radius: 8px;
        overflow: hidden;
        margin: 16px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .table-header {
        display: grid;
        grid-template-columns: 120px 2fr 1.5fr 1fr 200px 100px;
        gap: 12px;
        background: #F1F3F5;
        padding: 12px 16px;
        font-weight: 600;
        font-size: 0.75rem;
        color: #495057;
        text-transform: uppercase;
        border-bottom: 2px solid #DEE2E6;
    }
    
    .table-row {
        display: grid;
        grid-template-columns: 120px 2fr 1.5fr 1fr 200px 100px;
        gap: 12px;
        padding: 12px 16px;
        border-bottom: 1px solid #F1F3F5;
        align-items: center;
        transition: background 0.1s;
    }
    
    .table-row:hover {
        background: #F8F9FA;
    }
    
    .tender-id {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #4263EB;
        font-weight: 600;
        background: #E7F5FF;
        padding: 4px 8px;
        border-radius: 4px;
        text-align: center;
    }
    
    .tender-title {
        font-size: 0.9rem;
        font-weight: 600;
        color: #212529;
        margin-bottom: 4px;
        line-height: 1.3;
    }
    
    .tender-cat {
        display: inline-block;
        font-size: 0.7rem;
        padding: 2px 8px;
        margin: 2px 4px 2px 0;
        border-radius: 3px;
        background: #D0EBFF;
        color: #1864AB;
        font-weight: 500;
    }
    
    .org-name {
        font-size: 0.85rem;
        font-weight: 500;
        color: #343A40;
    }
    
    .org-unit {
        font-size: 0.75rem;
        color: #6C757D;
        margin-top: 2px;
    }
    
    .date-label {
        font-size: 0.75rem;
        color: #495057;
    }
    
    .date-value {
        font-size: 0.75rem;
        color: #DC3545;
        font-weight: 600;
    }
    
    .stButton button {
        padding: 6px 12px !important;
        font-size: 0.8rem !important;
        border-radius: 4px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE ---
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            tender_id TEXT PRIMARY KEY,
            tender_data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_bookmark(tender_id, tender_data):
    """Save a tender to bookmarks"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR REPLACE INTO bookmarks (tender_id, tender_data, created_at) VALUES (?, ?, ?)",
            (tender_id, json.dumps(tender_data, ensure_ascii=False), datetime.now().isoformat())
        )
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False
    finally:
        conn.close()

def remove_bookmark(tender_id):
    """Remove a tender from bookmarks"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM bookmarks WHERE tender_id = ?", (tender_id,))
    conn.commit()
    conn.close()

def get_bookmarks():
    """Get all bookmarked tenders"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT tender_data FROM bookmarks ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

def is_bookmarked(tender_id):
    """Check if tender is bookmarked"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM bookmarks WHERE tender_id = ?", (tender_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

# --- UI COMPONENTS ---
def render_table_header():
    """Render table header"""
    st.markdown("""
    <div class="tender-table">
        <div class="table-header">
            <div>ID</div>
            <div>LICITACIÓN</div>
            <div>ORGANISMO</div>
            <div>UNIDAD</div>
            <div>FECHAS</div>
            <div>ACCIONES</div>
        </div>
    """, unsafe_allow_html=True)

def render_tender_row(tender, index):
    """Render a single tender row"""
    tender_id = tender.get('CodigoExterno', 'N/A')
    nombre = tender.get('Nombre', 'Sin título')
    
    # Extract nested data safely - handle both dict and None cases
    comprador = tender.get('Comprador')
    if not isinstance(comprador, dict):
        comprador = {}
    
    fechas = tender.get('Fechas')
    if not isinstance(fechas, dict):
        fechas = {}
    
    # Extract comprador fields with fallbacks
    org_name = comprador.get('NombreOrganismo', None)
    if not org_name:
        org_name = 'Organismo no indicado'
    
    unit_name = comprador.get('NombreUnidad', None)
    if not unit_name:
        unit_name = 'Unidad no indicada'
    
    region = comprador.get('RegionUnidad', '')
    
    # Extract dates with fallbacks
    fecha_inicio = fechas.get('FechaInicio', None)
    fecha_cierre = fechas.get('FechaCierre', None)
    
    # Format dates
    fecha_inicio_fmt = format_datetime(fecha_inicio) if fecha_inicio else ''
    fecha_cierre_fmt = format_datetime(fecha_cierre) if fecha_cierre else ''
    
    # Categories
    categories = tender.get('CategoriasIDIEM', [])
    cat_html = ''.join([f'<span class="tender-cat">{cat}</span>' for cat in categories])
    
    # URL
    url = tender.get('URL_Publica', f'https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={tender_id}')
    
    # Check if bookmarked
    bookmarked = is_bookmarked(tender_id)
    
    # Render row
    st.markdown(f"""
    <div class="table-row">
        <div>
            <div class="tender-id">{tender_id}</div>
        </div>
        <div>
            {cat_html}
            <div class="tender-title">{nombre}</div>
        </div>
        <div>
            <div class="org-name">{org_name}</div>
            {f'<div class="org-unit">{region}</div>' if region else ''}
        </div>
        <div>
            <div class="org-unit">{unit_name}</div>
        </div>
        <div>
            {f'<div class="date-label">Inicio: {fecha_inicio_fmt}</div>' if fecha_inicio_fmt else ''}
            {f'<div class="date-value">Cierre: {fecha_cierre_fmt}</div>' if fecha_cierre_fmt else '<div class="date-label">Sin fecha cierre</div>'}
        </div>
        <div style="display: flex; gap: 6px; align-items: center;">
    """, unsafe_allow_html=True)
    
    # Bookmark button
    col1, col2 = st.columns([1, 1])
    with col1:
        btn_label = "⭐" if bookmarked else "☆"
        btn_type = "primary" if bookmarked else "secondary"
        if st.button(btn_label, key=f"bookmark_{tender_id}_{index}", type=btn_type):
            if bookmarked:
                remove_bookmark(tender_id)
                st.toast(f"Eliminado: {tender_id}", icon="❌")
            else:
                add_bookmark(tender_id, tender)
                st.toast(f"Guardado: {tender_id}", icon="💾")
            st.rerun()
    
    with col2:
        st.link_button("🔗", url, use_container_width=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_table_footer():
    """Close table div"""
    st.markdown("</div>", unsafe_allow_html=True)

# --- MAIN APP ---
def main():
    # Initialize database
    init_db()
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 📋 Monitor Licitaciones")
        st.markdown("### IDIEM - UC")
        st.markdown("---")
        
        # Get API ticket
        ticket = st.secrets.get("MP_TICKET", None)
        if not ticket:
            ticket = st.text_input("🔑 Ticket API", type="password")
        
        if not ticket:
            st.error("Se requiere un ticket de API")
            st.stop()
        
        # Days to scan
        days = st.slider("📅 Días a escanear", 1, 7, 2)
        
        # Debug mode
        debug_mode = st.checkbox("🐛 Modo Debug", value=False)
        
        st.markdown("---")
        st.markdown("#### Filtros Activos")
        st.info("Laboratorio, Geotecnia, Ingeniería, ITO")
    
    # Main content
    st.title("Panel de Control")
    st.markdown("---")
    
    # Tabs
    tab1, tab2 = st.tabs(["📡 Feed en Vivo", "⭐ Mis Marcadores"])
    
    with tab1:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Licitaciones Filtradas")
        with col2:
            if st.button("🔄 Actualizar", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        # Fetch tenders
        with st.spinner("Consultando MercadoPúblico..."):
            tenders = fetch_tenders(ticket, days)
        
        if not tenders:
            st.warning("No se encontraron licitaciones con los criterios configurados.")
        else:
            st.success(f"✅ {len(tenders)} licitaciones encontradas")
            
            # Debug mode - show first tender structure
            if debug_mode and tenders:
                with st.expander("🔍 Ver estructura del primer tender"):
                    st.json(tenders[0])
            
            # Render table
            render_table_header()
            for idx, tender in enumerate(tenders):
                render_tender_row(tender, idx)
            render_table_footer()
    
    with tab2:
        st.markdown("### Mis Licitaciones Guardadas")
        
        bookmarks = get_bookmarks()
        
        if not bookmarks:
            st.info("⭐ No tienes licitaciones guardadas. Usa el botón ☆ para marcar favoritos.")
        else:
            st.success(f"📌 {len(bookmarks)} licitaciones guardadas")
            
            # Render table
            render_table_header()
            for idx, tender in enumerate(bookmarks):
                render_tender_row(tender, f"saved_{idx}")
            render_table_footer()

if __name__ == "__main__":
    main()
