import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import textwrap
import time
import json

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="MercadoPublico Intel",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- ESTADO DE LA SESIÓN (PERSISTENCIA) ---
if 'saved_tenders' not in st.session_state:
    st.session_state.saved_tenders = []

# --- CONFIGURACIÓN DE CATEGORÍAS (Lógica IDIEM) ---
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}

# --- ESTILOS CSS MODERNOS (CLEAN UI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp { background-color: #F9FAFB; font-family: 'Inter', sans-serif; color: #111827; }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #F3F4F6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        color: #6B7280;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #2563EB;
        border-top: 2px solid #2563EB;
    }

    /* Cards */
    .tender-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: all 0.2s;
    }
    .tender-card:hover {
        border-color: #93C5FD;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* Tipografía Card */
    .card-top-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
    .card-id { font-family: monospace; font-size: 0.8rem; color: #6B7280; background: #F3F4F6; padding: 2px 6px; border-radius: 4px; }
    .card-title { font-size: 1.05rem; font-weight: 600; color: #111827; margin-bottom: 4px; line-height: 1.4; }
    
    /* Metadata grid */
    .meta-grid { display: flex; flex-wrap: wrap; gap: 15px; font-size: 0.85rem; color: #4B5563; margin-top: 8px; margin-bottom: 12px; }
    .meta-item { display: flex; align-items: center; gap: 5px; }
    .meta-icon { color: #9CA3AF; }

    /* Tags Categorías */
    .cat-tag { 
        font-size: 0.75rem; 
        padding: 2px 8px; 
        border-radius: 12px; 
        background-color: #EFF6FF; 
        color: #1D4ED8; 
        border: 1px solid #DBEAFE;
        margin-right: 4px;
        display: inline-block;
    }

    /* Botones y Badges */
    div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #111827; }
    
    .status-badge {
        font-size: 0.7rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 99px;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE SOPORTE ---

def get_relative_time(date_str):
    """Calcula 'Hace 10 minutos' basado en FechaCreacion"""
    if not date_str: return ""
    try:
        # Intentar formato ISO completo
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except:
        try:
            # Fallback a fecha simple
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return "" # No mostrar si no se puede parsear
            
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1): return "Hace un instante"
    if diff < timedelta(hours=1): return f"Hace {int(diff.seconds/60)} min"
    if diff < timedelta(hours=24): return f"Hace {int(diff.seconds/3600)} h"
    if diff < timedelta(days=7): return f"Hace {diff.days} días"
    return dt.strftime("%d/%m/%Y")

def categorize_tender(tender_obj):
    """Asigna etiquetas basado en palabras clave (Lógica IDIEM)"""
    text = (str(tender_obj.get('Nombre', '')) + " " + str(tender_obj.get('Descripcion', ''))).lower()
    detected = []
    for cat_name, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            detected.append(cat_name)
    return detected

def toggle_save(tender):
    """Manejador para guardar/borrar de la sesión"""
    # Check if already saved by ID
    existing = next((x for x in st.session_state.saved_tenders if x['CodigoExterno'] == tender['CodigoExterno']), None)
    if existing:
        st.session_state.saved_tenders.remove(existing)
        st.toast(f"Eliminado: {tender['CodigoExterno']}")
    else:
        st.session_state.saved_tenders.append(tender)
        st.toast(f"Guardado: {tender['CodigoExterno']}")

# --- LÓGICA DE DATOS (API & OCDS) ---

@st.cache_data(ttl=3600)
def fetch_product_name_from_uri(uri, product_code):
    """
    Cadena de llamadas: URI -> JSON -> Match CodigoProducto -> Nombre Real
    Ej: Obtiene '4.8 Obras Sanitarias. 2da'
    """
    if not uri or not product_code: return None
    try:
        r = requests.get(uri, timeout=3)
        if r.status_code == 200:
            data = r.json()
            products = data.get('Productos', [])
            # Buscar el match exacto del ID
            for p in products:
                # La API devuelve enteros a veces, aseguramos string
                if str(p.get('CodigoProducto')) == str(product_code):
                    return p.get('NombreProducto')
    except:
        return None
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_main_feed(ticket, days=3):
    all_tenders = []
    pbar = st.progress(0, text="Sincronizando MercadoPúblico...")
    
    for i in range(days):
        date_q = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        try:
            r = requests.get(url, params={'fecha': date_q, 'ticket': ticket}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                tenders = data.get("Listado", [])
                
                # Enriquecer con fecha de creación aproximada para la UI si falta
                creation_fallback = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                
                for t in tenders:
                    if 'FechaCreacion' not in t: t['FechaCreacion'] = creation_fallback
                    
                all_tenders.extend(tenders)
        except Exception:
            pass
        pbar.progress((i+1)/days)
    
    pbar.empty()
    return all_tenders

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ocds_rich_data(code):
    """Obtiene OCDS y pre-procesa items para nombres reales"""
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{code}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- UI PRINCIPAL ---

with st.sidebar:
    st.header("Parámetros")
    ticket = st.secrets.get("MP_TICKET", None)
    if not ticket:
        ticket = st.text_input("Ticket API", type="password")
        if not ticket: st.warning("Ticket Requerido"); st.stop()
    
    days_n = st.slider("Días atrás", 1, 7, 2)
    search = st.text_input("Buscar texto...")
    
    st.divider()
    st.markdown(f"**Guardados:** {len(st.session_state.saved_tenders)}")

st.title("Monitor de Licitaciones")

# TABS PRINCIPALES
tab_explore, tab_saved = st.tabs(["🌎 Explorar", "🔖 Marcadores"])

# --- TAB 1: EXPLORAR ---
with tab_explore:
    raw_feed = fetch_main_feed(ticket, days_n)
    
    # Filtrado
    filtered = []
    terms = [t.strip().lower() for t in search.split(",")] if search else []
    
    for t in raw_feed:
        # Categorización automática
        cats = categorize_tender(t)
        t['custom_cats'] = cats # Guardamos en el objeto
        
        # Filtro Texto
        full_text = (str(t.get('Nombre')) + str(t.get('Descripcion')) + str(t.get('Comprador'))).lower()
        if terms and not any(term in full_text for term in terms):
            continue
            
        filtered.append(t)
        
    st.caption(f"Mostrando {len(filtered)} resultados recientes.")
    
    if not filtered:
        st.info("No hay resultados.")
    
    for tender in filtered:
        # Pre-cálculos UI
        code = tender.get('CodigoExterno')
        is_saved = any(x['CodigoExterno'] == code for x in st.session_state.saved_tenders)
        
        # Fechas
        created_str = tender.get('FechaCreacion', '')
        relative_time = get_relative_time(created_str)
        
        close_str = tender.get('FechaCierre', '')
        try:
            close_fmt = datetime.strptime(close_str, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")
        except:
            close_fmt = close_str if close_str else "Sin fecha"

        # Organismo (Fix Desconocido)
        comp = tender.get('Comprador', {})
        org = comp.get('NombreOrganismo', 'Organismo Desconocido')
        unit = comp.get('NombreUnidad', '')
        region = comp.get('RegionUnidad', 'Región no esp.')
        full_org = f"{org} — {unit}" if unit else org

        # HTML Render
        cat_html = "".join([f"<span class='cat-tag'>{c}</span>" for c in tender.get('custom_cats', [])])
        status_color = "#DCFCE7" if tender.get('Estado') == 'Publicada' else "#F3F4F6"
        status_text_color = "#166534" if tender.get('Estado') == 'Publicada' else "#374151"
        
        desc = textwrap.shorten(tender.get('Descripcion', ''), width=200, placeholder="...")

        st.markdown(f"""
        <div class="tender-card">
            <div class="card-top-row">
                <div>
                    <span class="card-id">{code}</span>
                    <span class="status-badge" style="background:{status_color}; color:{status_text_color}">{tender.get('Estado')}</span>
                </div>
                <div style="font-size:0.8rem; color:#6B7280;">
                    Creado: <b>{relative_time}</b>
                </div>
            </div>
            <div class="card-title">{tender.get('Nombre')}</div>
            <div>{cat_html}</div>
            
            <div class="meta-grid">
                <div class="meta-item"><span class="meta-icon">🏢</span> {full_org}</div>
                <div class="meta-item"><span class="meta-icon">📍</span> {region}</div>
                <div class="meta-item" style="color:#DC2626;"><span class="meta-icon">⏳</span> Cierre: {close_fmt}</div>
            </div>
            <div style="font-size:0.9rem; color:#4B5563; margin-top:10px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

        # Botonera
        c1, c2, c3 = st.columns([1, 2, 8])
        
        # Botón Guardar (Logic Toggle)
        save_label = "✅ Guardado" if is_saved else "🔖 Guardar"
        if c1.button(save_label, key=f"save_{code}"):
            toggle_save(tender)
            st.rerun()

        # Link Externo
        c2.link_button("🌐 Ver Ficha", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
        
        # Detalle Técnico (Deep Link OCDS)
        with st.expander("🛠️ Análisis Técnico (OCDS)"):
            with st.spinner("Conectando con API OCDS..."):
                ocds = fetch_ocds_rich_data(code)
                if ocds:
                    try:
                        # Extraer Items
                        items = ocds['records'][0]['compiledRelease']['tender']['items']
                        
                        clean_items = []
                        for it in items:
                            # 1. Datos básicos
                            base_desc = it.get('description', '')
                            qty = it.get('quantity', 0)
                            unspsc_id = it.get('classification', {}).get('id', '')
                            uri = it.get('classification', {}).get('uri', '')
                            
                            # 2. EL SALTO EXTRA (Deep Fetch)
                            # Si tenemos URI, vamos a buscar el nombre real del producto
                            real_name = base_desc # Default
                            
                            if uri and "mercadopublico.cl" in uri:
                                fetched_name = fetch_product_name_from_uri(uri, unspsc_id)
                                if fetched_name:
                                    real_name = f"{fetched_name} ({base_desc})"
                            
                            clean_items.append({
                                "UNSPSC": unspsc_id,
                                "Producto (Normalizado)": real_name,
                                "Cantidad": qty,
                                "Unidad": it.get('unit', {}).get('name', 'Unidad')
                            })
                        
                        st.dataframe(pd.DataFrame(clean_items), use_container_width=True, hide_index=True)
                        
                    except Exception as e:
                        st.warning("No se encontraron items estructurados.")
                else:
                    st.error("No hay datos OCDS disponibles.")


# --- TAB 2: GUARDADOS ---
with tab_saved:
    if not st.session_state.saved_tenders:
        st.info("No tienes licitaciones guardadas. Ve a la pestaña 'Explorar' y marca algunas.")
    else:
        # Convertir a DataFrame para permitir exportación si se desea
        st.success(f"Tienes {len(st.session_state.saved_tenders)} marcadores.")
        
        for t in st.session_state.saved_tenders:
            code = t['CodigoExterno']
            
            # Reutilizamos el diseño simple para la lista guardada
            st.markdown(f"""
            <div style="padding:15px; border:1px solid #E5E7EB; border-radius:8px; margin-bottom:10px; background:white;">
                <div style="font-weight:bold; font-size:1.1rem;">{t.get('Nombre')}</div>
                <div style="font-size:0.85rem; color:#6B7280; font-family:monospace;">{code}</div>
            </div>
            """, unsafe_allow_html=True)
            
            col_a, col_b = st.columns([1, 5])
            if col_a.button("🗑️ Borrar", key=f"del_{code}"):
                toggle_save(t)
                st.rerun()
            col_b.link_button("Ir a MP", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")

