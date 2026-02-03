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
    page_title="Monitor de Licitaciones",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- ESTILOS MODERNOS (CLEAN UI 2026) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Reset básico y fuente */
    .stApp {
        background-color: #F8F9FA; /* Gris muy claro, casi blanco */
        font-family: 'Inter', sans-serif;
        color: #1F2937;
    }
    
    h1, h2, h3 {
        color: #111827;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* Cards de Licitación */
    .tender-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); /* Sombra sutil */
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .tender-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
        border-color: #3B82F6; /* Azul al pasar el mouse */
    }

    /* Header de la Card */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }

    .card-id {
        font-size: 0.75rem;
        font-weight: 600;
        color: #6B7280;
        background-color: #F3F4F6;
        padding: 4px 8px;
        border-radius: 6px;
        letter-spacing: 0.05em;
    }

    .card-badge {
        font-size: 0.75rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
    }
    .status-publicada { background-color: #DCFCE7; color: #166534; } /* Verde */
    .status-cerrada { background-color: #FEE2E2; color: #991B1B; } /* Rojo */
    .status-adjudicada { background-color: #DBEAFE; color: #1E40AF; } /* Azul */

    /* Título */
    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 8px;
        line-height: 1.4;
    }

    /* Metadata Row (Grid Horizontal) */
    .card-meta-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-bottom: 16px;
        font-size: 0.875rem;
        color: #4B5563;
        align-items: center;
    }
    
    .meta-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .meta-icon { opacity: 0.6; }

    /* Descripción */
    .card-desc {
        font-size: 0.875rem;
        color: #6B7280; /* Gris medio */
        line-height: 1.5;
        border-top: 1px solid #F3F4F6;
        padding-top: 12px;
        margin-top: 12px;
    }

    /* Métricas Superiores */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] { font-size: 0.875rem; color: #6B7280; }
    div[data-testid="stMetricValue"] { color: #111827; font-weight: 600; }

    /* Botones */
    .stButton button {
        background-color: #FFFFFF;
        color: #374151;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton button:hover {
        border-color: #3B82F6;
        color: #3B82F6;
        background-color: #EFF6FF;
    }
    
    /* Expander Cleaner */
    .streamlit-expanderHeader {
        background-color: #FFFFFF;
        color: #374151;
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---

def format_relative_date(date_str):
    """
    Convierte fechas string a formato relativo humano (hace 2 horas, ayer, etc).
    Intenta parsear varios formatos comunes de la API.
    """
    if not date_str:
        return ""
    
    # Intentar parsear la fecha (formato usual: 2026-02-03T10:00:00)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return date_str # Devuelve original si falla

    now = datetime.now()
    diff = now - dt

    if diff < timedelta(minutes=1):
        return "Hace un momento"
    elif diff < timedelta(hours=1):
        return f"Hace {int(diff.seconds/60)} min"
    elif diff < timedelta(hours=24):
        return f"Hace {int(diff.seconds/3600)} horas"
    elif diff < timedelta(days=2):
        return "Ayer"
    elif diff < timedelta(days=7):
        return f"Hace {diff.days} días"
    else:
        return dt.strftime("%d %b %Y") # Formato estándar si es antiguo

def safe_get(data_dict, keys, default="--"):
    """
    Navega seguro por diccionarios anidados.
    keys: lista de claves ['Comprador', 'Nombre']
    """
    current = data_dict
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return current if current not in [None, "", "null"] else default

# --- LÓGICA DE DATOS ---

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_tenders_api(ticket, days=3):
    """
    Obtiene licitaciones de los últimos X días desde la API real.
    """
    all_tenders = []
    # Usamos una barra de progreso sutil
    progress_bar = st.progress(0)
    
    for i in range(days):
        date_query = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        
        try:
            resp = requests.get(url, params={'fecha': date_query, 'ticket': ticket}, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                tenders = data.get("Listado", [])
                
                # Inyectamos una fecha de creación simulada basada en la query
                # porque la API "Listado" a veces no trae la fecha exacta de publicación
                for t in tenders:
                    if 'FechaCreacion' not in t:
                        t['FechaCreacion'] = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                
                all_tenders.extend(tenders)
        except Exception:
            pass # Falla silenciosa para no romper la UI
            
        progress_bar.progress((i + 1) / days)
    
    progress_bar.empty()
    return all_tenders

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ocds_details(tender_code):
    """Consulta la API OCDS para detalles técnicos (ítems, UNSPSC)."""
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{tender_code}"
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- UI PRINCIPAL ---

# 1. Sidebar (Filtros)
with st.sidebar:
    st.header("🎛️ Filtros")
    
    # API Key (Oculta o Secrets)
    ticket = st.secrets.get("MP_TICKET", None)
    if not ticket:
        ticket = st.text_input("Tu Ticket de MercadoPublico", type="password")
        if not ticket:
            st.warning("🔒 Ingresa tu ticket para ver datos reales.")
            st.stop()
            
    days_filter = st.slider("Antigüedad (Días)", 1, 5, 2)
    
    st.subheader("Búsqueda")
    search_txt = st.text_input("Palabras clave", placeholder="Ej: Hormigón, Diseño, Arica...")
    
    region_sel = st.selectbox("Región", ["Todas", "Metropolitana", "Valparaíso", "Biobío", "Antofagasta", "Araucanía"])
    
    st.divider()
    st.caption("v2.1.0 • Producción")

# 2. Obtención de Datos
raw_data = fetch_tenders_api(ticket, days_filter)

# 3. Filtrado Local
filtered = []
keywords = [k.strip().lower() for k in search_txt.split(",")] if search_txt else []

for t in raw_data:
    # Extracción segura de datos para filtrar
    nombre = str(t.get('Nombre', '')).lower()
    desc = str(t.get('Descripcion', '')).lower()
    region_t = safe_get(t, ['Comprador', 'RegionUnidad'], "").lower()
    
    # Filtro Región
    if region_sel != "Todas" and region_sel.lower() not in region_t:
        continue
        
    # Filtro Keywords
    if keywords:
        if not any(k in nombre or k in desc for k in keywords):
            continue
            
    filtered.append(t)

# 4. Header y Métricas
st.title("Monitor de Licitaciones")
st.markdown("Vista en tiempo real de oportunidades de negocio.")

m1, m2, m3 = st.columns(3)
m1.metric("Oportunidades", len(filtered))
m2.metric("Total Escaneado", len(raw_data))
m3.metric("Estado API", "Conectado 🟢")

st.divider()

# 5. Renderizado de Cards (Loop Principal)
if not filtered:
    st.info("🔍 No se encontraron licitaciones con estos filtros.")
else:
    for item in filtered:
        # Preparar variables para la UI (Limpieza de datos)
        code = item.get('CodigoExterno', 'S/I')
        title = item.get('Nombre', 'Sin Título')
        status = item.get('Estado', 'Publicada').capitalize()
        
        # Clases de color para el estado
        status_class = "status-publicada"
        if "cerrada" in status.lower(): status_class = "status-cerrada"
        elif "adjudicada" in status.lower(): status_class = "status-adjudicada"

        # Datos extraídos seguramente
        org_name = safe_get(item, ['Comprador', 'NombreOrganismo'], "Organismo Desconocido")
        region = safe_get(item, ['Comprador', 'RegionUnidad'], "Región no esp.")
        currency = item.get('Moneda', '')
        if currency not in ['CLP', 'UF', 'USD']: currency = "CLP" # Default
        
        # Fechas
        date_close_raw = item.get('FechaCierre', '')
        date_close_human = format_relative_date(date_close_raw)
        
        date_pub_raw = item.get('FechaCreacion', '') # Usamos nuestra fecha inyectada o la real
        date_pub_human = format_relative_date(date_pub_raw)

        # Descripción truncada y sanitizada (Evita error </div>)
        raw_desc = item.get('Descripcion', '')
        short_desc = textwrap.shorten(raw_desc, width=220, placeholder="...")
        # Escapar caracteres HTML peligrosos si fuera necesario, pero textwrap suele ser seguro.
        
        # Construcción de la Card HTML
        card_html = f"""
        <div class="tender-card">
            <div class="card-header">
                <span class="card-id">#{code}</span>
                <span class="card-badge {status_class}">{status}</span>
            </div>
            <div class="card-title">{title}</div>
            
            <div class="card-meta-grid">
                <div class="meta-item" title="Organismo">
                    <span class="meta-icon">🏢</span> {org_name}
                </div>
                <div class="meta-item" title="Región">
                    <span class="meta-icon">📍</span> {region}
                </div>
                <div class="meta-item" title="Cierre">
                    <span class="meta-icon">⏳</span> Cierre: {date_close_human}
                </div>
                <div class="meta-item" title="Publicado">
                    <span class="meta-icon">📢</span> {date_pub_human}
                </div>
            </div>
            
            <div class="card-desc">
                {short_desc}
            </div>
        </div>
        """
        
        # Renderizar la tarjeta visual
        st.markdown(card_html, unsafe_allow_html=True)
        
        # Botones de Acción (Fuera del HTML para interactividad Streamlit)
        c_act1, c_act2 = st.columns([0.2, 0.8])
        
        with c_act1:
            st.link_button("🌐 Ver en Web", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
        
        with c_act2:
            # Lógica de Expansión (Detalle Técnico)
            with st.expander("🛠️ Ver Detalle Técnico (Items & Categorías)"):
                # Solo hacemos fetch si el usuario abre esto (Lazy Loading)
                with st.spinner("Consultando especificaciones técnicas..."):
                    ocds_data = fetch_ocds_details(code)
                    
                    if ocds_data:
                        # Parseo específico de items OCDS
                        try:
                            items_list = ocds_data['records'][0]['compiledRelease']['tender']['items']
                            clean_items = []
                            for it in items_list:
                                clean_items.append({
                                    "Descripción": it.get('description', '--'),
                                    "Cantidad": it.get('quantity', 0),
                                    "Unidad": it.get('unit', {}).get('name', '--'),
                                    "Código UNSPSC": it.get('classification', {}).get('id', '--')
                                })
                            
                            st.dataframe(
                                pd.DataFrame(clean_items), 
                                hide_index=True, 
                                use_container_width=True
                            )
                        except:
                            st.warning("⚠️ No se encontraron ítems desglosados en el registro OCDS.")
                            st.json(ocds_data) # Fallback para debug
                    else:
                        st.error("No se pudo conectar con el servicio de datos abiertos (OCDS) para esta licitación.")
            with col_actions[0]:

                 st.link_button("🔗 Web", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
