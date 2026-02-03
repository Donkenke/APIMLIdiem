import streamlit as st
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="Monitor Licitaciones v2", page_icon="⚡")

# Logic from your provided script
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}
EXCLUDE_KEYWORDS = ["odontología", "dental", "médico", "clínico", "salud", "funda", "resina", "escritorio"]
ALL_KEYWORDS = [kw for sublist in CATEGORIES.values() for kw in sublist]

# --- CSS: COMPACT TABLE DESIGN ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    .stApp { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    
    /* TABLE HEADER */
    .header-row {
        display: flex;
        background-color: #F1F5F9;
        border-bottom: 2px solid #E2E8F0;
        padding: 8px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* TABLE ROWS */
    .data-row {
        display: flex;
        align-items: center; /* Vertically center */
        background-color: #FFFFFF;
        border-bottom: 1px solid #F1F5F9;
        padding: 6px 10px; /* Reduced padding for compact height */
        transition: all 0.15s ease;
        cursor: pointer;
    }
    .data-row:hover {
        background-color: #F8FAFC;
        border-left: 3px solid #3B82F6;
        padding-left: 7px; /* Adjust for border */
    }
    
    /* CELLS */
    .cell-id { font-family: 'Consolas', monospace; font-size: 0.75rem; color: #3B82F6; font-weight: 600; width: 10%; }
    .cell-main { width: 40%; padding-right: 15px; }
    .cell-org { width: 25%; font-size: 0.8rem; color: #475569; }
    .cell-dates { width: 15%; text-align: right; font-size: 0.75rem; color: #64748B; }
    .cell-action { width: 10%; text-align: right; }

    /* TYPOGRAPHY */
    .txt-title { font-size: 0.9rem; font-weight: 600; color: #1E293B; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;}
    .txt-desc { font-size: 0.75rem; color: #94A3B8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; max-width: 95%; }
    .txt-tag { 
        display: inline-block; font-size: 0.65rem; padding: 1px 6px; 
        border-radius: 4px; background: #DBEAFE; color: #1E40AF; margin-bottom: 2px; font-weight: 500;
    }
    .txt-alert { color: #EF4444; font-weight: 600; }

    /* DETAIL BOX */
    .detail-box {
        background: white; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px;
        margin-top: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .detail-header { font-size: 1.1rem; font-weight: 700; color: #0F172A; margin-bottom: 15px; border-bottom: 1px solid #E2E8F0; padding-bottom: 10px;}
    .detail-section { margin-bottom: 15px; }
    .detail-label { font-size: 0.75rem; font-weight: 600; color: #64748B; text-transform: uppercase; margin-bottom: 4px; }
    .detail-value { font-size: 0.9rem; color: #334155; }
    
    /* STREAMLIT OVERRIDES */
    div[data-testid="stVerticalBlock"] > div { gap: 0rem; }
    .stButton button { padding: 2px 10px; font-size: 0.75rem; height: auto; min-height: 0px; }
</style>
""", unsafe_allow_html=True)

# --- SCRAPER LOGIC (ADAPTED FROM SNIPPET TO BS4) ---
# We use BS4 instead of Playwright because we only need the HTML text/tables, 
# and it is 10x faster and compatible with Streamlit Cloud.

@st.cache_data(ttl=3600, show_spinner=False)
def scrape_tender_details(code):
    """
    Scrapes the 'Global Data' (Sections 5, 6, 7, 8) from the public detail page.
    Replicates the logic of finding 'Requisitos', 'Criterios', 'Garantias'.
    """
    url = f"http://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={code}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        data = {
            "Requisitos": "No especificado",
            "Criterios": [],
            "Garantias": [],
            "MontoEstimado": "No visible",
            "Duracion": "No especificada"
        }

        # 1. Monto y Duración (ID matching)
        # span id="...lblMontoEstimado"
        monto_tag = soup.find("span", id=lambda x: x and x.endswith("lblMontoEstimado"))
        if monto_tag: data["MontoEstimado"] = monto_tag.get_text(strip=True)

        dur_tag = soup.find("span", id=lambda x: x and x.endswith("lblTiempoDuracionContrato"))
        if dur_tag: data["Duracion"] = dur_tag.get_text(strip=True)

        # 2. Requisitos (Text Extraction)
        # Strategy: Look for the header text, then find the container
        # In MP, this is usually in a div id="...pnlRequisitos" or similar, but text search is safer
        req_header = soup.find(string="Requisitos para contratar al proveedor adjudicado")
        if req_header:
            # The text is usually in a span/div nearby. 
            # We traverse up to the container and get text, or next sibling
            container = req_header.find_parent("tr") # Usually in a table row
            if container:
                data["Requisitos"] = container.get_text(" ", strip=True).replace("Requisitos para contratar al proveedor adjudicado", "").strip()

        # 3. Criterios de Evaluación (Table)
        # ID: grvCriterios
        crit_table = soup.find("table", id=lambda x: x and x.endswith("grvCriterios"))
        if crit_table:
            rows = crit_table.find_all("tr", class_="cssFwkItemStyle")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    data["Criterios"].append({
                        "Criterio": cols[0].get_text(strip=True),
                        "Ponderacion": cols[1].get_text(strip=True)
                    })

        # 4. Garantías (Table)
        # ID: grvGarantias
        gar_table = soup.find("table", id=lambda x: x and x.endswith("grvGarantias"))
        if gar_table:
            rows = gar_table.find_all("tr", class_="cssFwkItemStyle")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 5:
                    data["Garantias"].append({
                        "Tipo": cols[0].get_text(strip=True),
                        "Monto": cols[2].get_text(strip=True),
                        "Momento": cols[4].get_text(strip=True)
                    })
        
        return data

    except Exception as e:
        print(f"Error scraping {code}: {e}")
        return None

# --- FEED LOGIC ---
@st.cache_data(ttl=900, show_spinner=False)
def fetch_feed(ticket, days):
    results = []
    # Loop dates
    for i in range(days):
        date_str = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        try:
            r = requests.get(url, params={'fecha': date_str, 'ticket': ticket}, verify=False, timeout=5)
            if r.status_code == 200:
                items = r.json().get("Listado", [])
                for item in items:
                    # Filter: Must have keyword AND not be excluded
                    name = item.get('Nombre', '').lower()
                    if any(k in name for k in ALL_KEYWORDS) and not any(e in name for e in EXCLUDE_KEYWORDS):
                        # Add categories
                        cats = []
                        desc = (item.get('Descripcion', '') + " " + name).lower()
                        for c_name, c_kws in CATEGORIES.items():
                            if any(k in desc for k in c_kws):
                                cats.append(c_name)
                        item['Categorias'] = cats
                        results.append(item)
        except: pass
    return results

# --- APP LAYOUT ---
# Sidebar
with st.sidebar:
    st.title("⚙️ Configuración")
    ticket = st.secrets.get("MP_TICKET") or st.text_input("API Ticket", type="password")
    days = st.slider("Días a escanear", 1, 5, 2)
    
    st.divider()
    st.caption("Palabras clave activas:")
    st.code(", ".join(ALL_KEYWORDS[:10]) + "...", language=None)

# Main
st.title("Monitor de Licitaciones")

if "selected_tender" not in st.session_state:
    st.session_state.selected_tender = None

def select_tender(tender):
    st.session_state.selected_tender = tender

if not ticket:
    st.warning("Por favor ingresa un Ticket de Mercado Público.")
    st.stop()

# Fetch Data
with st.spinner("Buscando licitaciones..."):
    tenders = fetch_feed(ticket, days)

# --- SPLIT VIEW (List vs Detail) ---

if st.session_state.selected_tender:
    # --- DETAIL VIEW ---
    t = st.session_state.selected_tender
    
    if st.button("← Volver al listado"):
        st.session_state.selected_tender = None
        st.rerun()

    st.markdown(f"<div class='detail-header'>{t['CodigoExterno']} - {t['Nombre']}</div>", unsafe_allow_html=True)
    
    # Grid for basic info
    c1, c2, c3 = st.columns(3)
    c1.info(f"🏢 **Organismo:**\n\n{t.get('Comprador', {}).get('NombreOrganismo', '')}")
    c2.warning(f"📅 **Cierre:**\n\n{t.get('FechaCierre', 'Sin fecha')}")
    c3.success(f"🏷️ **Estado:**\n\n{t.get('Estado', '')}")

    st.markdown("---")
    
    # Scrape Extra Data Live
    with st.spinner(f"Extrayendo requisitos y garantías desde MercadoPúblico para {t['CodigoExterno']}..."):
        extra_data = scrape_tender_details(t['CodigoExterno'])
    
    if extra_data:
        # Layout Extra Data
        col_A, col_B = st.columns([1, 1])
        
        with col_A:
            st.markdown("#### 💰 Montos y Duración")
            st.markdown(f"**Estimado:** {extra_data['MontoEstimado']}")
            st.markdown(f"**Duración:** {extra_data['Duracion']}")
            
            st.markdown("#### 📝 Requisitos Contratación")
            st.markdown(f"<div style='background:#f9f9f9; padding:10px; border-radius:5px; font-size:0.85rem;'>{extra_data['Requisitos']}</div>", unsafe_allow_html=True)

        with col_B:
            st.markdown("#### ⚖️ Criterios de Evaluación")
            if extra_data['Criterios']:
                df_crit = pd.DataFrame(extra_data['Criterios'])
                st.dataframe(df_crit, hide_index=True, use_container_width=True)
            else:
                st.write("No se detectó tabla de criterios.")

            st.markdown("#### 🛡️ Garantías")
            if extra_data['Garantias']:
                df_gar = pd.DataFrame(extra_data['Garantias'])
                st.dataframe(df_gar, hide_index=True, use_container_width=True)
            else:
                st.write("No se detectó tabla de garantías.")
    else:
        st.error("No se pudo extraer la información detallada de la ficha web.")

else:
    # --- TABLE VIEW (Compact) ---
    st.markdown(f"**{len(tenders)} Licitaciones encontradas**")
    
    # Render Header
    st.markdown("""
    <div class='header-row'>
        <div style='width:10%'>ID</div>
        <div style='width:40%'>Descripción</div>
        <div style='width:25%'>Organismo</div>
        <div style='width:15%; text-align:right'>Fechas</div>
        <div style='width:10%; text-align:center'>Acción</div>
    </div>
    """, unsafe_allow_html=True)

    if not tenders:
        st.info("No hay resultados hoy.")

    for t in tenders:
        # Pre-process strings
        code = t.get('CodigoExterno')
        name = t.get('Nombre')
        desc = t.get('Descripcion', '')
        org = t.get('Comprador', {}).get('NombreOrganismo', 'Desc')
        unit = t.get('Comprador', {}).get('NombreUnidad', '')
        f_close = t.get('FechaCierre', '')[:10] if t.get('FechaCierre') else "N/A"
        
        # Categories HTML
        cats_html = "".join([f"<span class='txt-tag'>{c}</span> " for c in t.get('Categorias', [])])

        # Row Container
        with st.container():
            # Create a layout that matches the header
            # We use st.columns inside the container to place the button correctly
            # Note: We mix HTML and Streamlit widgets (Button) by using columns
            c1, c2, c3, c4, c5 = st.columns([1, 4, 2.5, 1.5, 1])
            
            with c1:
                st.markdown(f"<div class='cell-id'>{code}</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div>{cats_html}</div>", unsafe_allow_html=True)
                st.markdown(f"<span class='txt-title'>{name}</span>", unsafe_allow_html=True)
                st.markdown(f"<span class='txt-desc'>{desc}</span>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='cell-org'><b>{org}</b><br>{unit}</div>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<div class='cell-dates'>Cierre<br><span class='txt-alert'>{f_close}</span></div>", unsafe_allow_html=True)
            with c5:
                # The interaction trigger
                if st.button("🔍 Ver", key=code, use_container_width=True):
                    select_tender(t)
                    st.rerun()
            
            # Divider line
            st.markdown("<div style='border-bottom: 1px solid #F1F5F9; margin: 4px 0;'></div>", unsafe_allow_html=True)
