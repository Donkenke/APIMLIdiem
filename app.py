import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import textwrap
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Monitor de Licitaciones",
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- ESTADO DE SESIÓN (Persistencia de Marcadores) ---
if 'saved_tenders' not in st.session_state:
    st.session_state.saved_tenders = []

# --- CONFIGURACIÓN DE CATEGORÍAS (Lógica IDIEM) ---
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}

# --- ESTILOS CSS (Clean UI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp { background-color: #F9FAFB; font-family: 'Inter', sans-serif; color: #111827; }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        background-color: #FFFFFF;
        border-radius: 6px;
        padding: 0 16px;
        color: #6B7280;
        font-weight: 500;
        border: 1px solid #E5E7EB;
    }
    .stTabs [aria-selected="true"] {
        background-color: #EFF6FF;
        color: #2563EB;
        border-color: #BFDBFE;
    }

    /* Cards */
    .tender-card {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: box-shadow 0.2s;
    }
    .tender-card:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border-color: #93C5FD;
    }

    /* Typography inside Card */
    .card-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .card-id { font-family: monospace; font-size: 0.8rem; color: #2563EB; background: #EFF6FF; padding: 2px 8px; border-radius: 4px; border: 1px solid #DBEAFE; }
    .card-title { font-size: 1.1rem; font-weight: 600; color: #111827; line-height: 1.4; margin-bottom: 8px; }
    
    /* Metadata Grid */
    .meta-grid { display: flex; flex-wrap: wrap; gap: 16px; font-size: 0.85rem; color: #4B5563; margin-top: 12px; border-top: 1px solid #F3F4F6; padding-top: 12px; }
    .meta-item { display: flex; align-items: center; gap: 6px; }
    .meta-icon { font-size: 1rem; }

    /* Tags */
    .cat-tag { 
        font-size: 0.75rem; 
        padding: 2px 8px; 
        border-radius: 12px; 
        background-color: #FEF3C7; 
        color: #92400E; 
        border: 1px solid #FDE68A;
        margin-right: 4px;
        display: inline-block;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def get_relative_time(date_str):
    if not date_str: return ""
    try:
        # Try full ISO format first
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except:
        try:
            # Try simple date
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return date_str
            
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1): return "Hace un instante"
    if diff < timedelta(hours=1): return f"Hace {int(diff.seconds/60)} min"
    if diff < timedelta(hours=24): return f"Hace {int(diff.seconds/3600)} h"
    if diff < timedelta(days=2): return "Ayer"
    if diff < timedelta(days=7): return f"Hace {diff.days} días"
    return dt.strftime("%d/%m/%Y")

def categorize_tender(text):
    text_lower = text.lower()
    detected = []
    for cat_name, keywords in CATEGORIES.items():
        if any(k in text_lower for k in keywords):
            detected.append(cat_name)
    return detected

def toggle_save_tender(tender_data):
    # Check if exists
    code = tender_data['CodigoExterno']
    exists = next((t for t in st.session_state.saved_tenders if t['CodigoExterno'] == code), None)
    
    if exists:
        st.session_state.saved_tenders.remove(exists)
        st.toast(f"Eliminado: {code}")
    else:
        st.session_state.saved_tenders.append(tender_data)
        st.toast(f"Guardado: {code}")

# --- API FETCHING ---

@st.cache_data(ttl=3600)
def fetch_product_category_name(uri, product_code):
    """Deep fetch: Navigates to the URI to get the real Category name."""
    if not uri or "mercadopublico.cl" not in uri: return None
    try:
        r = requests.get(uri, timeout=3)
        if r.status_code == 200:
            data = r.json()
            # Look for the product code match in the list
            for prod in data.get('Productos', []):
                if str(prod.get('CodigoProducto')) == str(product_code):
                    return prod.get('NombreProducto')
            # Fallback: Return the Category Name if product specific not found
            return data.get('NombreCategoria')
    except:
        return None
    return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_daily_feed(ticket, days_back=3):
    all_tenders = []
    pbar = st.progress(0, text="Consultando MercadoPúblico...")
    
    for i in range(days_back):
        date_query = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        
        try:
            r = requests.get(url, params={'fecha': date_query, 'ticket': ticket}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                tenders = data.get("Listado", [])
                
                # Enrich with a default creation date if missing (for UI sorting)
                fallback_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%dT09:00:00")
                for t in tenders:
                    if not t.get('FechaCreacion'):
                        t['FechaCreacion'] = fallback_date
                
                all_tenders.extend(tenders)
        except Exception:
            pass
        
        pbar.progress((i + 1) / days_back)
        
    pbar.empty()
    return all_tenders

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ocds_data(code):
    url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/record/{code}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# --- MAIN APP UI ---

with st.sidebar:
    st.header("Configuración")
    
    ticket_val = st.secrets.get("MP_TICKET", "")
    if not ticket_val:
        ticket_val = st.text_input("Ticket API", type="password")
        if not ticket_val:
            st.warning("Se requiere Ticket API")
            st.stop()
            
    days_slider = st.slider("Días a revisar", 1, 7, 2)
    search_query = st.text_input("Filtrar por texto")
    
    st.divider()
    st.metric("Guardados", len(st.session_state.saved_tenders))

st.title("Monitor de Licitaciones")
tab1, tab2 = st.tabs(["📡 Feed en Vivo", "🔖 Mis Marcadores"])

# --- TAB 1: FEED ---
with tab1:
    raw_list = fetch_daily_feed(ticket_val, days_slider)
    
    # Filter
    filtered_list = []
    terms = [x.strip().lower() for x in search_query.split(",")] if search_query else []
    
    for item in raw_list:
        # Robust Data Extraction
        buyer = item.get('Comprador') or {} # Handle None
        if not isinstance(buyer, dict): buyer = {} # Handle weird API responses
        
        org_name = buyer.get('NombreOrganismo', 'Organismo Desconocido')
        region_name = buyer.get('RegionUnidad', 'Región no especificada')
        
        # Text for searching
        full_text = (str(item.get('Nombre')) + str(item.get('Descripcion')) + org_name).lower()
        
        # Categorization
        cats = categorize_tender(full_text)
        item['calculated_cats'] = cats # Store for display
        item['clean_org'] = org_name
        item['clean_region'] = region_name
        
        if terms:
            if not any(term in full_text for term in terms):
                continue
        
        filtered_list.append(item)
        
    st.caption(f"Mostrando {len(filtered_list)} licitaciones.")

    if not filtered_list:
        st.info("No hay resultados.")
        
    for tender in filtered_list:
        code = tender.get('CodigoExterno')
        is_saved = any(t['CodigoExterno'] == code for t in st.session_state.saved_tenders)
        
        # Formats
        creation_human = get_relative_time(tender.get('FechaCreacion'))
        
        close_raw = tender.get('FechaCierre', '')
        try:
            close_human = datetime.strptime(close_raw, "%Y-%m-%dT%H:%M:%S").strftime("%d/%m/%Y %H:%M")
        except:
            close_human = "Sin fecha"
            
        # Cat HTML
        cat_html = " ".join([f"<span class='cat-tag'>{c}</span>" for c in tender.get('calculated_cats', [])])
        
        desc_short = textwrap.shorten(tender.get('Descripcion', ''), width=220, placeholder="...")

        # --- THE FIX: No indentation in the f-string HTML ---
        html_card = f"""
<div class="tender-card">
<div class="card-header-row">
<div><span class="card-id">{code}</span> <span style="font-size:0.8rem; color:#6B7280; margin-left:8px;">{creation_human}</span></div>
<div style="font-size:0.75rem; font-weight:700; color:#059669; background:#D1FAE5; padding:2px 8px; border-radius:12px;">{tender.get('Estado')}</div>
</div>
<div class="card-title">{tender.get('Nombre')}</div>
<div style="margin-bottom:8px;">{cat_html}</div>
<div style="font-size:0.9rem; color:#374151; margin-bottom:12px;">{desc_short}</div>
<div class="meta-grid">
<div class="meta-item"><span class="meta-icon">🏢</span> {tender['clean_org']}</div>
<div class="meta-item"><span class="meta-icon">📍</span> {tender['clean_region']}</div>
<div class="meta-item" style="color:#DC2626;"><span class="meta-icon">⏳</span> Cierre: {close_human}</div>
</div>
</div>
"""
        st.markdown(html_card, unsafe_allow_html=True)
        
        # Action Buttons
        col1, col2, col3 = st.columns([1.2, 2, 7])
        
        btn_label = "✅ Guardado" if is_saved else "🔖 Guardar"
        if col1.button(btn_label, key=f"btn_{code}"):
            toggle_save_tender(tender)
            st.rerun()
            
        col2.link_button("🌐 Ir a MP", f"http://www.mercadopublico.cl/fichaLicitacion.html?idLicitacion={code}")
        
        # Detail Expander with OCDS Logic
        with st.expander("🔎 Ver Items y Detalle Técnico"):
            with st.spinner("Consultando OCDS y Catálogo..."):
                ocds = fetch_ocds_data(code)
                if ocds:
                    try:
                        items = ocds['records'][0]['compiledRelease']['tender']['items']
                        clean_items = []
                        
                        for it in items:
                            base_desc = it.get('description', '')
                            classif = it.get('classification', {})
                            unspsc = classif.get('id', '')
                            uri = classif.get('uri', '')
                            
                            # Deep Fetch for Real Product Name
                            real_name = base_desc
                            if uri:
                                fetched_name = fetch_product_category_name(uri, unspsc)
                                if fetched_name:
                                    real_name = f"{fetched_name} ({base_desc})"
                                    
                            clean_items.append({
                                "Código UNSPSC": unspsc,
                                "Producto/Servicio": real_name,
                                "Cantidad": it.get('quantity', 0),
                                "Unidad": it.get('unit', {}).get('name', '')
                            })
                            
                        st.dataframe(pd.DataFrame(clean_items), use_container_width=True, hide_index=True)
                    except:
                        st.warning("Datos OCDS disponibles pero sin items estructurados.")
                else:
                    st.error("Licitación antigua o sin datos abiertos (OCDS) disponibles.")

# --- TAB 2: MARCADORES ---
with tab2:
    if not st.session_state.saved_tenders:
        st.info("No has guardado licitaciones aún.")
    else:
        st.success(f"Tienes {len(st.session_state.saved_tenders)} licitaciones guardadas.")
        
        df_saved = pd.DataFrame(st.session_state.saved_tenders)
        # Simple export button
        csv = df_saved.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Excel/CSV", data=csv, file_name="licitaciones_guardadas.csv", mime="text/csv")
        
        for t in st.session_state.saved_tenders:
            # Simple card for saved items
            code_saved = t['CodigoExterno']
            st.markdown(f"""
            <div style="padding:16px; background:white; border:1px solid #E5E7EB; border-radius:8px; margin-bottom:10px;">
                <div style="font-weight:bold; color:#111827;">{t.get('Nombre')}</div>
                <div style="font-size:0.8rem; color:#6B7280; font-family:monospace;">{code_saved}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🗑️ Eliminar", key=f"del_{code_saved}"):
                toggle_save_tender(t)
                st.rerun()


