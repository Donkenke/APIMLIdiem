import streamlit as st
import requests
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta
import textwrap

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Monitor de Licitaciones", page_icon="🏢")

# --- DATABASE SETUP (PERSISTENCIA TOTAL) ---
DB_FILE = "tenders_v2.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Ahora guardamos el JSON completo para no depender de la API en la pestaña de guardados
    c.execute('''
        CREATE TABLE IF NOT EXISTS tender_records (
            id TEXT PRIMARY KEY,
            visto BOOLEAN DEFAULT 0,
            guardado BOOLEAN DEFAULT 0,
            json_data TEXT,
            updated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db_status_map(ids_list):
    """Obtiene estado Visto/Guardado para una lista de IDs."""
    if not ids_list: return {}
    conn = sqlite3.connect(DB_FILE)
    placeholders = ',' .join('?' for _ in ids_list)
    query = f"SELECT id, visto, guardado FROM tender_records WHERE id IN ({placeholders})"
    try:
        df = pd.read_sql_query(query, conn, params=tuple(ids_list))
        status_map = {}
        if not df.empty:
            for _, row in df.iterrows():
                status_map[str(row['id'])] = {'visto': bool(row['visto']), 'guardado': bool(row['guardado'])}
        return status_map
    except:
        return {}
    finally:
        conn.close()

def save_tender_interaction(tender_obj, action_type, value):
    """
    Guarda o Actualiza una licitación en la BD.
    action_type: 'visto' o 'guardado'
    value: True/False
    """
    t_id = tender_obj['CodigoExterno']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Verificar si existe
    c.execute("SELECT id, visto, guardado FROM tender_records WHERE id = ?", (t_id,))
    row = c.fetchone()
    
    current_visto = row[1] if row else 0
    current_guardado = row[2] if row else 0
    
    # 2. Determinar nuevos valores
    new_visto = value if action_type == 'visto' else current_visto
    new_guardado = value if action_type == 'guardado' else current_guardado
    
    # 3. Serializar JSON para persistencia offline
    json_str = json.dumps(tender_obj, ensure_ascii=False)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 4. Upsert (Insert or Replace)
    c.execute('''
        INSERT OR REPLACE INTO tender_records (id, visto, guardado, json_data, updated_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (t_id, new_visto, new_guardado, json_str, timestamp))
    
    conn.commit()
    conn.close()

def get_saved_tenders_from_db():
    """Recupera TODA la data de los guardados directamente de la BD (Sin API)."""
    conn = sqlite3.connect(DB_FILE)
    try:
        # Solo traemos los que tienen guardado = 1
        df = pd.read_sql_query("SELECT json_data FROM tender_records WHERE guardado = 1 ORDER BY updated_at DESC", conn)
        tenders = []
        for _, row in df.iterrows():
            if row['json_data']:
                tenders.append(json.loads(row['json_data']))
        return tenders
    except Exception as e:
        return []
    finally:
        conn.close()

# Inicializar DB
init_db()

# --- ESTILOS CSS (Row Layout Moderno) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    .stApp { background-color: #F3F4F6; font-family: 'Inter', sans-serif; color: #1F2937; }
    
    /* Fila de Tabla Estilizada */
    .tender-row {
        background-color: white;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: transform 0.1s;
    }
    
    /* Headers de la tabla */
    .table-header {
        display: flex;
        padding: 0 18px;
        margin-bottom: 8px;
        font-size: 0.75rem;
        font-weight: 700;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Tags de Categoría */
    .cat-badge {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 600;
        color: #2563EB;
        background-color: #EFF6FF;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 5px;
        border: 1px solid #DBEAFE;
    }
    
    /* Columnas Custom */
    div[data-testid="column"] { align-items: center; display: flex; }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE CATEGORÍAS ---
CATEGORIES = {
    "Laboratorio": ["laboratorio", "ensayo", "hormigón", "suelo", "asfalto"],
    "Ingeniería": ["ingeniería", "cálculo", "diseño", "estructural", "consultoría"],
    "ITO": ["ito", "inspección", "fiscalización", "supervisión"],
    "Salud": ["salud", "hospital", "clínico", "médico"]
}

# --- FUNCIONES API & UTILIDADES ---
@st.cache_data(ttl=3600)
def fetch_ocds_rich_data(code):
    try:
        r = requests.get(f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{code}", timeout=3)
        return r.json() if r.status_code == 200 else None
    except: return None

@st.cache_data(ttl=3600)
def fetch_product_category_name(uri, product_code):
    if not uri or "mercadopublico" not in uri: return None
    try:
        r = requests.get(uri, timeout=3)
        if r.status_code == 200:
            for prod in r.json().get('Productos', []):
                if str(prod.get('CodigoProducto')) == str(product_code):
                    return prod.get('NombreProducto')
            return r.json().get('NombreCategoria')
    except: return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_live_feed(ticket, days):
    tenders = []
    pbar = st.progress(0, text="Sincronizando Feed...")
    for i in range(days):
        date_q = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        try:
            r = requests.get("https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json", 
                             params={'fecha': date_q, 'ticket': ticket}, timeout=6)
            if r.status_code == 200:
                data = r.json().get("Listado", [])
                # Fix fechas
                fallback = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                for t in data:
                    if not t.get('FechaCreacion'): t['FechaCreacion'] = fallback
                tenders.extend(data)
        except: pass
        pbar.progress((i+1)/days)
    pbar.empty()
    return tenders

def categorize(text):
    text = text.lower()
    return [cat for cat, kws in CATEGORIES.items() if any(kw in text for kw in kws)]

# --- UI PRINCIPAL ---

with st.sidebar:
    st.title("🎛️ Monitor")
    ticket = st.secrets.get("MP_TICKET") or st.text_input("API Ticket", type="password")
    if not ticket: st.warning("🔒 Ticket requerido"); st.stop()
    
    days_slider = st.slider("Ventana de tiempo", 1, 5, 2)
    search_txt = st.text_input("Filtrar resultados")
    st.divider()
    
    # Exportar DB
    if st.button("Descargar Base de Datos"):
        with open(DB_FILE, "rb") as f:
            st.download_button("📥 Bajar .db", f, file_name="tenders_full.db")

st.title("Licitaciones 2026")

# TABS
tab_feed, tab_saved = st.tabs(["📡 Feed en Vivo", "⭐ Guardados (Persistente)"])

def render_table_row(tender, is_saved_view):
    """Renderiza una fila única con lógica de columnas alineadas"""
    t_id = tender['CodigoExterno']
    
    # Recuperar estado actualizado de DB
    status_map = get_db_status_map([t_id])
    status = status_map.get(t_id, {'visto': False, 'guardado': False})
    
    # Auto-Check "Visto" en Feed
    if not is_saved_view and not status['visto']:
        save_tender_interaction(tender, 'visto', True)
        status['visto'] = True

    # Preparar datos visuales
    org_name = tender.get('Comprador', {}).get('NombreOrganismo', 'N/A')
    cats = categorize(str(tender.get('Nombre')) + str(tender.get('Descripcion')))
    cats_html = "".join([f"<span class='cat-badge'>{c}</span>" for c in cats])
    
    # Iconos
    icon_eye = "👁️" if status['visto'] else "⚪"
    icon_star = "⭐" if status['guardado'] else "☆"
    
    # --- LAYOUT DE FILA ---
    # Contenedor visual blanco
    with st.container():
        # CSS Grid Layout simulado con columnas
        c1, c2, c3, c4, c5, c6 = st.columns([1.2, 4, 2, 0.8, 0.8, 0.5])
        
        with c1:
            st.markdown(f"<span style='font-family:monospace; color:#4B5563; font-size:0.8rem;'>{t_id}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='font-weight:600; font-size:0.95rem; color:#111827; line-height:1.2; margin-bottom:4px;'>{tender.get('Nombre')}</div>", unsafe_allow_html=True)
            if cats_html: st.markdown(cats_html, unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div style='font-size:0.8rem; color:#6B7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{org_name}</div>", unsafe_allow_html=True)
        with c4:
             st.markdown(f"<div style='text-align:center; opacity:0.7;' title='Visto'>{icon_eye}</div>", unsafe_allow_html=True)
        with c5:
            # Botón Interactivo Guardar
            if st.button(icon_star, key=f"s_{t_id}_{is_saved_view}", help="Guardar"):
                new_val = not status['guardado']
                save_tender_interaction(tender, 'guardado', new_val)
                st.rerun() # Recarga inmediata para reflejar cambio
        with c6:
            st.link_button("🔗", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={t_id}")
            
        # Expander Técnico
        with st.expander("    Ver detalle técnico", expanded=False):
            with st.spinner("Cargando items..."):
                ocds = fetch_ocds_rich_data(t_id)
                if ocds:
                    try:
                        items = ocds['records'][0]['compiledRelease']['tender']['items']
                        data_items = []
                        for it in items:
                            base_desc = it.get('description', '')
                            uri = it.get('classification', {}).get('uri')
                            code_prod = it.get('classification', {}).get('id')
                            if uri:
                                real = fetch_product_category_name(uri, code_prod)
                                if real: base_desc = f"({real}) {base_desc}"
                            data_items.append({"Código": code_prod, "Descripción": base_desc, "Cant": it.get('quantity')})
                        st.dataframe(pd.DataFrame(data_items), hide_index=True, use_container_width=True)
                    except: st.warning("Sin desglose.")
        
        st.markdown("<hr style='margin: 0 0 10px 0; border:0; border-top:1px solid #F3F4F6;'>", unsafe_allow_html=True)


# --- TAB 1: FEED LOGIC ---
with tab_feed:
    tenders_feed = fetch_live_feed(ticket, days_slider)
    
    # Filter Text
    if search_txt:
        terms = [x.strip().lower() for x in search_txt.split(",")]
        tenders_feed = [t for t in tenders_feed if any(term in (str(t.get('Nombre'))+str(t.get('Descripcion'))).lower() for term in terms)]

    st.markdown("""
    <div class="table-header">
        <div style="width:12%;">ID</div>
        <div style="width:40%;">Licitación</div>
        <div style="width:20%;">Organismo</div>
        <div style="width:8%; text-align:center;">Visto</div>
        <div style="width:8%; text-align:center;">Guardar</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not tenders_feed: st.info("No hay datos recientes.")
    for t in tenders_feed:
        render_table_row(t, is_saved_view=False)

# --- TAB 2: SAVED LOGIC ---
with tab_saved:
    # AQUÍ ESTÁ EL CAMBIO CLAVE: Leemos de la BD, no de la API
    saved_tenders = get_saved_tenders_from_db()
    
    st.markdown("""
    <div class="table-header">
        <div style="width:12%;">ID</div>
        <div style="width:40%;">Licitación (Guardada Localmente)</div>
        <div style="width:20%;">Organismo</div>
        <div style="width:8%; text-align:center;">Visto</div>
        <div style="width:8%; text-align:center;">Eliminar</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not saved_tenders:
        st.info("No hay licitaciones guardadas.")
    
    for t in saved_tenders:
        render_table_row(t, is_saved_view=True)
