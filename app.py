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
        background-color: #F8F9FA;
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
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .tender-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
        border-color: #3B82F6;
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
    .status-publicada { background-color: #DCFCE7; color: #166534; }
    .status-cerrada { background-color: #FEE2E2; color: #991B1B; }
    .status-adjudicada { background-color: #DBEAFE; color: #1E40AF; }

    /* Título */
    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #111827;
        margin-bottom: 8px;
        line-height: 1.4;
    }

    /* Metadata Row */
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
        color: #6B7280;
        line-height: 1.5;
        border-top: 1px solid #F3F4F6;
        padding-top: 12px;
        margin-top: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES AUXILIARES ---

def format_relative_date(date_str):
    """Convierte fechas string a formato relativo humano."""
    if not date_str: return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return date_str

    now = datetime.now()
    diff = now - dt

    if diff < timedelta(minutes=1): return "Hace un momento"
    elif diff < timedelta(hours=1): return f"Hace {int(diff.seconds/60)} min"
    elif diff < timedelta(hours=24): return f"Hace {int(diff.seconds/3600)} horas"
    elif diff < timedelta(days=2): return "Ayer"
    elif diff < timedelta(days=7): return f"Hace {diff.days} días"
    else: return dt.strftime("%d %b %Y")

def safe_get(data_dict, keys, default="--"):
    """Navega seguro por diccionarios anidados."""
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
    """Obtiene licitaciones de la API real."""
    all_tenders = []
    progress_bar = st.progress(0, text="Conectando con MercadoPublico...")
    
    for i in range(days):
        date_query = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        
        try:
            resp = requests.get(url, params={'fecha': date_query, 'ticket': ticket}, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                tenders = data.get("Listado", [])
                
                # Inyectar fecha aproximada si falta
                for t in tenders:
                    if 'FechaCreacion' not in t:
                        t['FechaCreacion'] = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                
                all_tenders.extend(tenders)
        except Exception:
            pass 
            
        progress_bar.progress((i + 1) / days)
    
    progress_bar.empty()
    return all_tenders

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ocds_details(tender_code):
    """Consulta la API OCDS para detalles técnicos."""
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{tender_code}"
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# --- UI PRINCIPAL ---

with st.sidebar:
    st.header("🎛️ Filtros")
    
    # Manejo de API Key (Secrets o Input manual)
    ticket = st.secrets.get("MP_TICKET", None)
    if not ticket:
        ticket = st.text_input("Tu Ticket de MercadoPublico", type="password")
        if not ticket:
            st.warning("🔒 Ingresa tu ticket para ver datos reales.")
            st.stop()
            
    days_filter = st.slider("Antigüedad (Días)", 1, 5, 2)
    search_txt = st.text_input("Palabras clave", placeholder="Ej: Hormigón, Diseño...")
    region_sel = st.selectbox("Región", ["Todas", "Metropolitana", "Valparaíso", "Biobío", "Antofagasta", "Araucanía"])
    
    st.divider()
    st.caption("v2.2.0 • Producción")

# Obtención de Datos
raw_data = fetch_tenders_api(ticket, days_filter)

# Filtrado
filtered = []
keywords = [k.strip().lower() for k in search_txt.split(",")] if search_txt else []

for t in raw_data:
    nombre = str(t.get('Nombre', '')).lower()
    desc = str(t.get('Descripcion', '')).lower()
    region_t = safe_get(t, ['Comprador', 'RegionUnidad'], "").lower()
    
    if region_sel != "Todas" and region_sel.lower() not in region_t:
        continue
    if keywords and not any(k in nombre or k in desc for k in keywords):
        continue
    filtered.append(t)

# Métricas
st.title("Monitor de Licitaciones")
st.markdown("Vista en tiempo real de oportunidades de negocio.")
m1, m2, m3 = st.columns(3)
m1.metric("Oportunidades", len(filtered))
m2.metric("Total Escaneado", len(raw_data))
m3.metric("Estado API", "Conectado 🟢")
st.divider()

# Loop de Cards
if not filtered:
    st.info("🔍 No se encontraron licitaciones.")
else:
    for item in filtered:
        code = item.get('CodigoExterno', 'S/I')
        title = item.get('Nombre', 'Sin Título')
        status = item.get('Estado', 'Publicada').capitalize()
        
        status_class = "status-publicada"
        if "cerrada" in status.lower(): status_class = "status-cerrada"
        elif "adjudicada" in status.lower(): status_class = "status-adjudicada"

        org_name = safe_get(item, ['Comprador', 'NombreOrganismo'], "Organismo Desconocido")
        region = safe_get(item, ['Comprador', 'RegionUnidad'], "Región no esp.")
        
        date_close = format_relative_date(item.get('FechaCierre', ''))
        date_pub = format_relative_date(item.get('FechaCreacion', ''))

        raw_desc = item.get('Descripcion', '')
        # FIX: Ensure textwrap is imported and used correctly
        short_desc = textwrap.shorten(raw_desc, width=220, placeholder="...")
        
        # FIX: HTML string must NOT be indented to avoid Markdown code blocks
        card_html = f"""
<div class="tender-card">
<div class="card-header">
<span class="card-id">#{code}</span>
<span class="card-badge {status_class}">{status}</span>
</div>
<div class="card-title">{title}</div>
<div class="card-meta-grid">
<div class="meta-item" title="Organismo"><span class="meta-icon">🏢</span> {org_name}</div>
<div class="meta-item" title="Región"><span class="meta-icon">📍</span> {region}</div>
<div class="meta-item" title="Cierre"><span class="meta-icon">⏳</span> {date_close}</div>
<div class="meta-item" title="Publicado"><span class="meta-icon">📢</span> {date_pub}</div>
</div>
<div class="card-desc">{short_desc}</div>
</div>
"""
        st.markdown(card_html, unsafe_allow_html=True)
        
        # Actions
        c1, c2 = st.columns([0.2, 0.8])
        with c1:
            st.link_button("🌐 Web", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
        with c2:
            with st.expander("🛠️ Ver Detalle Técnico (Items)"):
                with st.spinner("Cargando datos..."):
                    ocds_data = fetch_ocds_details(code)
                    if ocds_data:
                        try:
                            # Safely extract items
                            records = ocds_data.get('records', [])
                            if records:
                                items_list = records[0].get('compiledRelease', {}).get('tender', {}).get('items', [])
                                clean_items = []
                                for it in items_list:
                                    clean_items.append({
                                        "Descripción": it.get('description', '--'),
                                        "Cantidad": it.get('quantity', 0),
                                        "Unidad": it.get('unit', {}).get('name', '--'),
                                        "UNSPSC": it.get('classification', {}).get('id', '--')
                                    })
                                st.dataframe(pd.DataFrame(clean_items), hide_index=True, use_container_width=True)
                            else:
                                st.warning("No hay items.")
                        except Exception as e:
                            st.error(f"Error parseando: {e}")
                    else:
                        st.error("Sin conexión OCDS.")

