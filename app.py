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
    
    .stApp { background-color: #F8F9FA; font-family: 'Inter', sans-serif; }
    
    /* Fila de Tabla Custom */
    .tender-row {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 15px;
        transition: background 0.2s;
    }
    .tender-row:hover { background-color: #F9FAFB; border-color: #D1D5DB; }
    
    .col-id { min-width: 100px; font-family: monospace; font-size: 0.8rem; color: #6B7280; }
    .col-name { flex-grow: 1; font-weight: 600; color: #1F2937; font-size: 0.95rem; }
    .col-org { width: 200px; font-size: 0.8rem; color: #4B5563; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .col-date { width: 120px; font-size: 0.8rem; color: #DC2626; text-align: right; }
    
    /* Tags */
    .tag-cat { font-size: 0.7rem; background: #EFF6FF; color: #2563EB; padding: 2px 6px; border-radius: 4px; margin-right: 4px; }
    
    /* Botones invisibles en CSS, manejados por Streamlit */
    .stButton button { border: none; background: transparent; padding: 0; }
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

with st.sidebar:
    st.header("Configuración")
    ticket = st.secrets.get("MP_TICKET") or st.text_input("API Ticket", type="password")
    if not ticket: st.warning("Ingresa Ticket"); st.stop()
    
    days = st.slider("Días", 1, 5, 2)
    search = st.text_input("Filtrar texto")
    
    st.divider()
    
    # Exportar DB
    conn = sqlite3.connect(DB_FILE)
    df_db = pd.read_sql_query("SELECT * FROM tender_status WHERE guardado = 1", conn)
    conn.close()
    st.download_button("📥 Descargar Guardados (CSV)", df_db.to_csv(index=False), "guardados.csv")

st.title("Monitor de Licitaciones")

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

    # Header de columnas simulado
    st.markdown("""
    <div style="display:flex; padding:0 16px; margin-bottom:8px; font-weight:bold; color:#6B7280; font-size:0.8rem;">
        <div style="min-width:100px;">ID</div>
        <div style="flex-grow:1;">LICITACIÓN</div>
        <div style="width:200px;">ORGANISMO</div>
        <div style="width:80px; text-align:center;">VISTO</div>
        <div style="width:80px; text-align:center;">GUARDAR</div>
        <div style="width:50px;"></div>
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
            st.markdown(f"<span style='font-family:monospace; font-size:0.8rem; color:#2563EB'>{t_id}</span>", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"<div style='font-weight:600; font-size:0.95rem; line-height:1.2'>{tender.get('Nombre')}</div>", unsafe_allow_html=True)
            if cats_html: st.markdown(f"<div>{cats_html}</div>", unsafe_allow_html=True)
            
        with c3:
            st.markdown(f"<div style='font-size:0.8rem; color:#4B5563; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>{org}</div>", unsafe_allow_html=True)
            
        with c4:
            # Indicador Visual de Visto (No interactivo, solo informativo)
            st.markdown(f"<div style='text-align:center; cursor:default;' title='Visto'>{icon_visto}</div>", unsafe_allow_html=True)
            
        with c5:
            # Botón Guardar (Toggle)
            if st.button(icon_guardado, key=f"btn_save_{t_id}_{is_saved_view_only}", help="Guardar/Desguardar"):
                new_val = not state['guardado']
                update_status(t_id, 'guardado', new_val)
                st.rerun()

        with c6:
             st.link_button("🔗", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={t_id}", help="Ir a ficha")

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
