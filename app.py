import streamlit as st
import requests
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import textwrap
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Monitor de Licitaciones", page_icon="🏢")

# --- DATABASE SETUP (PERSISTENCIA REAL) ---
DB_FILE = "tenders_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tabla para tracking de estados por licitación
    c.execute('''
        CREATE TABLE IF NOT EXISTS tender_status (
            id TEXT PRIMARY KEY,
            visto BOOLEAN DEFAULT 0,
            guardado BOOLEAN DEFAULT 0,
            first_seen_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_status_dict(tender_ids):
    """Obtiene el estado de múltiples IDs de una sola vez."""
    conn = sqlite3.connect(DB_FILE)
    placeholders = ',' .join('?' for _ in tender_ids)
    query = f"SELECT id, visto, guardado FROM tender_status WHERE id IN ({placeholders})"
    df = pd.read_sql_query(query, conn, params=tuple(tender_ids))
    conn.close()
    
    # Convertir a diccionario para búsqueda rápida
    status_map = {}
    if not df.empty:
        for _, row in df.iterrows():
            status_map[str(row['id'])] = {'visto': bool(row['visto']), 'guardado': bool(row['guardado'])}
    return status_map

def update_status(tender_id, field, value):
    """Actualiza Visto o Guardado en la BD."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Upsert logic (Insertar si no existe, actualizar si existe)
    c.execute("SELECT id FROM tender_status WHERE id = ?", (tender_id,))
    exists = c.fetchone()
    
    if not exists:
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        c.execute("INSERT INTO tender_status (id, visto, guardado, first_seen_date) VALUES (?, 0, 0, ?)", (tender_id, today))
    
    query = f"UPDATE tender_status SET {field} = ? WHERE id = ?"
    c.execute(query, (1 if value else 0, tender_id))
    conn.commit()
    conn.close()

# Inicializar DB al arranque
init_db()

# --- ESTILOS CSS (Row Layout) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    .stApp { 
        background-color: #F8F9FA; 
        font-family: 'Inter', sans-serif; 
    }
    
    /* Header Styles */
    header { 
        background-color: white; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
        padding: 1rem 0;
        border-bottom: 1px solid #E5E7EB;
    }
    
    /* Sidebar Styling */
    .css-1d391kg {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }
    
    /* Professional Container Styling */
    .main-container {
        max-width: 100%;
        padding: 0 1rem;
    }
    
    /* Fila de Tabla Custom */
    .tender-row {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 15px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .tender-row:hover { 
        background-color: #F9FAFB; 
        border-color: #D1D5DB; 
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    
    .col-id { 
        min-width: 120px; 
        font-family: monospace; 
        font-size: 0.85rem; 
        color: #4B5563; 
        font-weight: 500;
    }
    .col-name { 
        flex-grow: 1; 
        font-weight: 600; 
        color: #1F2937; 
        font-size: 1rem; 
        line-height: 1.4;
    }
    .col-org { 
        width: 220px; 
        font-size: 0.85rem; 
        color: #4B5563; 
        white-space: nowrap; 
        overflow: hidden; 
        text-overflow: ellipsis; 
    }
    .col-date { 
        width: 140px; 
        font-size: 0.85rem; 
        color: #DC2626; 
        text-align: right; 
        font-weight: 500;
    }
    
    /* Professional Tag Styling */
    .tag-cat { 
        font-size: 0.75rem; 
        background: linear-gradient(135deg, #dbeafe, #bfdbfe); 
        color: #1d4ed8; 
        padding: 3px 8px; 
        border-radius: 20px; 
        margin-right: 6px; 
        display: inline-block;
        border: 1px solid #93c5fd;
    }
    
    /* Professional Button Styling */
    .stButton>button {
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        background-color: white !important;
        color: #4B5563 !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    
    .stButton>button:hover {
        background-color: #F3F4F6 !important;
        border-color: #9CA3AF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
    }
    
    .stButton>button:active {
        transform: translateY(0) !important;
    }
    
    /* Special styling for starred buttons */
    .star-button {
        font-size: 1.2rem !important;
        padding: 4px !important;
        min-width: 36px !important;
    }
    
    /* Link button styling */
    .stLinkButton>button {
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        background-color: white !important;
        color: #4B5563 !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        text-decoration: none !important;
    }
    
    /* Expander styling */
    .streamlit-expander {
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        margin: 10px 0 !important;
    }
    
    .streamlit-expanderHeader {
        background-color: #F9FAFB !important;
        border-radius: 7px 7px 0 0 !important;
        padding: 10px 15px !important;
        font-weight: 500 !important;
    }
    
    /* Professional table styling */
    .dataframe {
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 24px !important;
        font-weight: 600 !important;
        color: #4B5563 !important;
        border-bottom: 3px solid transparent !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #1F2937 !important;
        border-bottom: 3px solid #D1D5DB !important;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #2563EB !important;
        border-bottom: 3px solid #2563EB !important;
    }
    
    /* Status indicator styling */
    .status-indicator {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background-color: #F3F4F6;
        font-size: 0.8rem;
    }
    
    .status-seen {
        background-color: #dbeafe;
        color: #1d4ed8;
    }
    
    .status-saved {
        background-color: #fef3c7;
        color: #d97706;
    }
    
    /* Header alignment fix */
    .header-row {
        display: flex;
        padding: 0 20px;
        margin-bottom: 16px;
        font-weight: 600;
        color: #374151;
        font-size: 0.9rem;
        border-bottom: 2px solid #E5E7EB;
        padding-bottom: 12px;
    }
    
    .header-id { min-width: 120px; }
    .header-name { flex-grow: 1; }
    .header-org { width: 220px; }
    .header-status { width: 80px; text-align: center; }
    .header-actions { width: 100px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE CATEGORÍAS ---
CATEGORIES = {
    "Laboratorio": ["laboratorio", "ensayo", "hormigón", "suelo", "asfalto"],
    "Ingeniería": ["ingeniería", "cálculo", "diseño", "estructural", "consultoría"],
    "ITO": ["ito", "inspección", "fiscalización", "supervisión"]
}

# --- FUNCIONES API ---

@st.cache_data(ttl=3600)
def fetch_ocds_rich_data(code):
    """Trae datos OCDS para el detalle técnico"""
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{code}"
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=3600)
def fetch_product_category_name(uri, product_code):
    """Obtiene nombre real del producto desde la URI"""
    if not uri or "mercadopublico" not in uri: return None
    try:
        r = requests.get(uri, timeout=3)
        if r.status_code == 200:
            data = r.json()
            for prod in data.get('Productos', []):
                if str(prod.get('CodigoProducto')) == str(product_code):
                    return prod.get('NombreProducto')
            return data.get('NombreCategoria')
    except:
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_api_feed(ticket, days=3):
    tenders = []
    pbar = st.progress(0, text="Cargando datos...")
    for i in range(days):
        date_q = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        try:
            r = requests.get(url, params={'fecha': date_q, 'ticket': ticket}, timeout=6)
            if r.status_code == 200:
                data = r.json().get("Listado", [])
                # Agregar fecha fake si falta para ordenar
                creation_fallback = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                for t in data:
                    if not t.get('FechaCreacion'): t['FechaCreacion'] = creation_fallback
                tenders.extend(data)
        except: pass
        pbar.progress((i+1)/days)
    pbar.empty()
    return tenders

def categorize(text):
    text = text.lower()
    return [cat for cat, kws in CATEGORIES.items() if any(kw in text for kw in kws)]

# --- INTERFAZ PRINCIPAL ---

# Professional sidebar styling
with st.sidebar:
    st.markdown("<div style='padding: 1rem 0;'><h2 style='margin-bottom: 1.5rem;'>⚙️ Configuración</h2></div>", unsafe_allow_html=True)
    ticket = st.secrets.get("MP_TICKET") or st.text_input("🔐 API Ticket", type="password")
    if not ticket: 
        st.warning("⚠️ Ingresa Ticket")
        st.stop()
    
    days = st.slider("📅 Días", 1, 5, 2)
    search = st.text_input("🔍 Filtrar texto")
    
    st.divider()
    
    # Exportar DB
    conn = sqlite3.connect(DB_FILE)
    df_db = pd.read_sql_query("SELECT * FROM tender_status WHERE guardado = 1", conn)
    conn.close()
    st.download_button("📥 Descargar Guardados (CSV)", df_db.to_csv(index=False), "guardados.csv")

st.markdown("<div class='main-container'>", unsafe_allow_html=True)
st.title("🏢 Monitor de Licitaciones")

# Tabs
tab_all, tab_saved = st.tabs(["Listado General", "Solo Guardados"])

def render_list(is_saved_view_only=False):
    # 1. Obtener Datos API
    if is_saved_view_only:
        # Modo "Solo Guardados": Usamos la DB como fuente principal
        conn = sqlite3.connect(DB_FILE)
        saved_ids = pd.read_sql_query("SELECT id FROM tender_status WHERE guardado = 1", conn)['id'].tolist()
        conn.close()
        
        # Como la API pública no permite buscar por ID masivo fácilmente sin loop,
        # aquí hacemos un fetch general (cacheado) y filtramos.
        # *Nota: En producción real, deberías guardar el JSON completo en la DB para no depender de la API histórica.*
        raw_feed = fetch_api_feed(ticket, 7) # Buscamos 7 días atrás para intentar encontrar los guardados
        filtered_feed = [t for t in raw_feed if t['CodigoExterno'] in saved_ids]
    else:
        # Modo General
        filtered_feed = fetch_api_feed(ticket, days)

    # 2. Obtener Estados de DB (Batch)
    current_ids = [t['CodigoExterno'] for t in filtered_feed]
    status_map = get_status_dict(current_ids)
    
    # 3. Filtrar Texto (Frontend)
    if search:
        terms = [s.strip().lower() for s in search.split(",")]
        filtered_feed = [t for t in filtered_feed if any(term in (str(t.get('Nombre'))+str(t.get('Descripcion'))).lower() for term in terms)]

    # 4. Render Grid Headers
    if not filtered_feed:
        st.info("No hay datos para mostrar.")
        return

    # Header de columnas con alineación profesional
    st.markdown("""
    <div class="header-row">
        <div class="header-id">ID</div>
        <div class="header-name">LICITACIÓN</div>
        <div class="header-org">ORGANISMO</div>
        <div class="header-status">VISTO</div>
        <div class="header-status">GUARDAR</div>
        <div class="header-actions">ACCIONES</div>
    </div>
    """, unsafe_allow_html=True)

    for tender in filtered_feed:
        t_id = tender['CodigoExterno']
        
        # Recuperar estado de DB o default
        state = status_map.get(t_id, {'visto': False, 'guardado': False})
        
        # Marcar como Visto AUTOMÁTICAMENTE al renderizar (Si no estaba visto)
        if not state['visto'] and not is_saved_view_only:
            update_status(t_id, 'visto', True)
            state['visto'] = True # Actualizar local para visualización actual

        # Preparar datos visuales
        org = tender.get('Comprador', {}).get('NombreOrganismo', 'N/A')
        cats = categorize(str(tender.get('Nombre')) + str(tender.get('Descripcion')))
        cats_html = "".join([f"<span class='tag-cat'>{c}</span>" for c in cats])
        
        # Iconos Estado
        icon_visto = "👁️" if state['visto'] else "⚪"
        icon_guardado = "⭐" if state['guardado'] else "☆"
        btn_type = "primary" if state['guardado'] else "secondary"

        # --- ROW LAYOUT ---
        # Usamos columnas de Streamlit para alinear perfectamente los botones interactivos
        c1, c2, c3, c4, c5, c6 = st.columns([1.5, 4, 2, 1, 1, 0.5])
        
        with c1:
            st.markdown(f"<div class='col-id'>{t_id}</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"<div class='col-name'>{tender.get('Nombre')}</div>", unsafe_allow_html=True)
            if cats_html: st.markdown(f"<div>{cats_html}</div>", unsafe_allow_html=True)
            
        with c3:
            st.markdown(f"<div class='col-org'>{org}</div>", unsafe_allow_html=True)
            
        with c4:
            # Indicador Visual de Visto (No interactivo, solo informativo)
            st.markdown(f"<div class='status-indicator status-seen' title='Visto'>{icon_visto}</div>", unsafe_allow_html=True)
            
        with c5:
            # Botón Guardar (Toggle) con clase especial
            if st.button(icon_guardado, key=f"btn_save_{t_id}_{is_saved_view_only}", help="Guardar/Desguardar", type="secondary"):
                new_val = not state['guardado']
                update_status(t_id, 'guardado', new_val)
                st.rerun()

        with c6:
            st.link_button("🔗", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={t_id}", help="Ir a ficha", type="secondary")

        # Expander para detalles técnicos (OCDS)
        with st.expander("    Ver detalle técnico", expanded=False):
            with st.spinner("Cargando items..."):
                ocds = fetch_ocds_rich_data(t_id)
                if ocds:
                    try:
                        items = ocds['records'][0]['compiledRelease']['tender']['items']
                        data_items = []
                        for it in items:
                            base_desc = it.get('description', '')
                            # Deep Fetch logic
                            uri = it.get('classification', {}).get('uri')
                            code_prod = it.get('classification', {}).get('id')
                            if uri:
                                real_name = fetch_product_category_name(uri, code_prod)
                                if real_name: base_desc = f"({real_name}) {base_desc}"
                            
                            data_items.append({
                                "Código": code_prod,
                                "Descripción": base_desc,
                                "Cant": it.get('quantity')
                            })
                        st.dataframe(pd.DataFrame(data_items), hide_index=True, use_container_width=True)
                    except:
                        st.warning("Sin items desglosados.")

# Renderizar Vistas
with tab_all:
    render_list(is_saved_view_only=False)

with tab_saved:
    render_list(is_saved_view_only=True)

st.markdown("</div>", unsafe_allow_html=True)
