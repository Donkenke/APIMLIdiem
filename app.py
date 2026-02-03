import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any
import time

# Page configuration
st.set_page_config(
    page_title="Mercado Público - Buscador de Licitaciones",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern, clean UI
st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 0rem 1rem;
    }
    
    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Tender card styling */
    .tender-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    
    .tender-card:hover {
        box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        border-color: #667eea;
        transform: translateY(-2px);
    }
    
    .tender-header {
        display: flex;
        justify-content: space-between;
        align-items: start;
        margin-bottom: 1rem;
    }
    
    .tender-code {
        background: #667eea;
        color: white;
        padding: 0.4rem 0.8rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.9rem;
        font-family: 'Courier New', monospace;
    }
    
    .tender-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1f2937;
        margin: 0.5rem 0;
        line-height: 1.4;
    }
    
    .tender-org {
        color: #6b7280;
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
    }
    
    .tender-meta {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
        padding: 1rem;
        background: #f9fafb;
        border-radius: 8px;
    }
    
    .meta-item {
        display: flex;
        flex-direction: column;
    }
    
    .meta-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        color: #6b7280;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-bottom: 0.25rem;
    }
    
    .meta-value {
        font-size: 0.95rem;
        color: #1f2937;
        font-weight: 500;
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    .status-publicada {
        background: #dcfce7;
        color: #166534;
    }
    
    .status-cerrada {
        background: #fee2e2;
        color: #991b1b;
    }
    
    .status-adjudicada {
        background: #dbeafe;
        color: #1e40af;
    }
    
    .category-tag {
        display: inline-block;
        background: #f3f4f6;
        color: #374151;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
        margin-top: 0.5rem;
    }
    
    .action-buttons {
        display: flex;
        gap: 0.5rem;
        margin-top: 1rem;
    }
    
    .btn-primary {
        background: #667eea;
        color: white;
        padding: 0.6rem 1.2rem;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 500;
        display: inline-block;
        transition: all 0.2s;
    }
    
    .btn-primary:hover {
        background: #5568d3;
        text-decoration: none;
    }
    
    .btn-secondary {
        background: #f3f4f6;
        color: #374151;
        padding: 0.6rem 1.2rem;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 500;
        display: inline-block;
        transition: all 0.2s;
    }
    
    .btn-secondary:hover {
        background: #e5e7eb;
        text-decoration: none;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background: #f9fafb;
    }
    
    /* Stats cards */
    .stats-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }
    
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #6b7280;
        margin-top: 0.5rem;
    }
    
    /* Loading animation */
    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(102, 126, 234, 0.3);
        border-radius: 50%;
        border-top-color: #667eea;
        animation: spin 1s ease-in-out infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
</style>
""", unsafe_allow_html=True)

# Configuration
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"],
    "Obras Sanitarias": ["agua potable", "alcantarillado", "sanitaria", "saneamiento", "aducción"],
    "Vialidad": ["pavimento", "carpeta asfáltica", "señalización", "demarcación", "camino"],
    "Construcción": ["edificación", "construcción", "obra civil", "montaje"]
}

EXCLUDE_KEYWORDS = [
    "odontología", "dental", "médico", "clínico", "salud", "examen de sangre",
    "psicotécnico", "funda", "resina", "mallas bioabsorbibles", "arqueológico",
    "artística", "evento", "limpieza de fosas", "escritorio", "alimentación"
]

def is_relevant(name: str, custom_keywords: List[str] = None) -> bool:
    """Check if tender is relevant based on keywords"""
    name_low = name.lower()
    
    # Use custom keywords if provided, otherwise use all categories
    if custom_keywords:
        keywords = custom_keywords
    else:
        keywords = [kw for sublist in CATEGORIES.values() for kw in sublist]
    
    has_keyword = any(k.lower() in name_low for k in keywords)
    is_not_excluded = not any(e in name_low for e in EXCLUDE_KEYWORDS)
    
    return has_keyword and is_not_excluded

def categorize_tender(tender: Dict[str, Any]) -> List[str]:
    """Categorize tender based on keywords"""
    text = (tender.get('Nombre', '') + " " + tender.get('Descripcion', '')).lower()
    detected_cats = []
    
    for cat_name, keywords in CATEGORIES.items():
        if any(k in text for k in keywords):
            detected_cats.append(cat_name)
    
    return detected_cats if detected_cats else ["General/No Categorizado"]

def fetch_tender_detail(code: str) -> Dict[str, Any]:
    """Fetch detailed tender information from OCDS API (no ticket required)"""
    try:
        url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/tender/{code}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching details for {code}: {e}")
    
    return {}

def format_currency(amount):
    """Format currency in Chilean Pesos"""
    if amount is None:
        return "No informado"
    try:
        return f"${amount:,.0f} CLP".replace(",", ".")
    except:
        return "No informado"

def format_date(date_str):
    """Format date string"""
    if not date_str:
        return "No informada"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%d/%m/%Y")
    except:
        return date_str

def get_status_class(estado: str) -> str:
    """Get CSS class for status badge"""
    estado_lower = estado.lower()
    if 'publicada' in estado_lower:
        return 'status-publicada'
    elif 'cerrada' in estado_lower:
        return 'status-cerrada'
    elif 'adjudicada' in estado_lower:
        return 'status-adjudicada'
    else:
        return 'status-publicada'

def render_tender_card(tender: Dict[str, Any], show_details: bool = False):
    """Render a tender card with enhanced details"""
    code = tender.get('CodigoExterno', 'N/A')
    nombre = tender.get('Nombre', 'Sin título')
    estado = tender.get('Estado', 'Desconocido')
    
    comprador = tender.get('Comprador', {})
    org_name = comprador.get('NombreOrganismo', 'No especificado')
    unit_name = comprador.get('NombreUnidad', '')
    
    fechas = tender.get('Fechas', {})
    fecha_publicacion = format_date(fechas.get('FechaPublicacion'))
    fecha_cierre = format_date(fechas.get('FechaCierre'))
    
    # Get categories
    categories = categorize_tender(tender)
    
    # URLs
    url_publica = f"https://www.mercadopublico.cl/ListadoLicitaciones/Pantallas/DirectorioLicitacion.aspx?idLicitacion={code}"
    url_docs = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}&parent=1"
    
    # Card HTML
    card_html = f"""
    <div class="tender-card">
        <div class="tender-header">
            <span class="tender-code">{code}</span>
            <span class="status-badge {get_status_class(estado)}">{estado}</span>
        </div>
        
        <div class="tender-title">{nombre}</div>
        <div class="tender-org">📍 {org_name}</div>
        {f'<div class="tender-org" style="margin-top: 0.25rem;">🏢 {unit_name}</div>' if unit_name else ''}
        
        <div class="tender-meta">
            <div class="meta-item">
                <span class="meta-label">Publicación</span>
                <span class="meta-value">📅 {fecha_publicacion}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Cierre</span>
                <span class="meta-value">⏰ {fecha_cierre}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Tipo</span>
                <span class="meta-value">{tender.get('Tipo', 'N/A')}</span>
            </div>
        </div>
        
        <div>
            {''.join([f'<span class="category-tag">🏷️ {cat}</span>' for cat in categories])}
        </div>
        
        <div class="action-buttons">
            <a href="{url_publica}" target="_blank" class="btn-primary">
                Ver Licitación 🔗
            </a>
            <a href="{url_docs}" target="_blank" class="btn-secondary">
                Ver Documentos 📄
            </a>
        </div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Show additional details if requested
    if show_details:
        with st.expander("🔍 Ver detalles adicionales"):
            detail_data = fetch_tender_detail(code)
            if detail_data:
                st.json(detail_data)

def main():
    # Header
    st.markdown("""
    <div class="header-container">
        <div class="header-title">🏛️ Buscador de Licitaciones</div>
        <div class="header-subtitle">Sistema de búsqueda inteligente para licitaciones públicas de Chile</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar filters
    with st.sidebar:
        st.header("⚙️ Filtros de Búsqueda")
        
        # Date range
        st.subheader("📅 Rango de Fechas")
        days_back = st.slider("Días hacia atrás", 1, 90, 30)
        
        # Category filter
        st.subheader("🏷️ Categorías")
        selected_categories = st.multiselect(
            "Seleccionar categorías",
            options=list(CATEGORIES.keys()) + ["Todas"],
            default=["Todas"]
        )
        
        # Custom keywords
        st.subheader("🔑 Palabras Clave Personalizadas")
        custom_keywords_input = st.text_area(
            "Una por línea (opcional)",
            placeholder="hormigón\nensayo\npavimento"
        )
        
        # Estado filter
        st.subheader("📊 Estado")
        estados_filter = st.multiselect(
            "Filtrar por estado",
            options=["Todas", "Publicada", "Cerrada", "Adjudicada"],
            default=["Todas"]
        )
        
        # Search button
        search_button = st.button("🔍 Buscar Licitaciones", type="primary", use_container_width=True)
    
    # Main content
    if search_button:
        with st.spinner("🔄 Buscando licitaciones..."):
            # Parse custom keywords
            custom_keywords = []
            if custom_keywords_input.strip():
                custom_keywords = [kw.strip().lower() for kw in custom_keywords_input.split('\n') if kw.strip()]
            
            # Get keywords based on selected categories
            if "Todas" not in selected_categories and selected_categories:
                category_keywords = []
                for cat in selected_categories:
                    if cat in CATEGORIES:
                        category_keywords.extend(CATEGORIES[cat])
                search_keywords = category_keywords + custom_keywords
            else:
                search_keywords = custom_keywords if custom_keywords else None
            
            # Fetch tenders from API
            all_tenders = []
            today = datetime.now()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(days_back):
                current_date = today - timedelta(days=i)
                date_str = current_date.strftime("%d%m%Y")
                
                status_text.text(f"Buscando en fecha: {current_date.strftime('%d/%m/%Y')}")
                
                try:
                    # Note: Using public endpoint without ticket (limited functionality)
                    # For production, you'd need to get a ticket from Mercado Público
                    url = f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json?fecha={date_str}"
                    
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('Listado', [])
                        
                        # Filter relevant items
                        for item in items:
                            if is_relevant(item.get('Nombre', ''), search_keywords):
                                # Apply status filter
                                estado = item.get('Estado', '')
                                if "Todas" in estados_filter or estado in estados_filter:
                                    all_tenders.append(item)
                    
                    time.sleep(0.3)  # Rate limiting
                    
                except Exception as e:
                    st.warning(f"Error en fecha {date_str}: {str(e)}")
                
                progress_bar.progress((i + 1) / days_back)
            
            progress_bar.empty()
            status_text.empty()
            
            # Display results
            if all_tenders:
                # Stats
                st.markdown(f"""
                <div class="stats-container">
                    <div class="stat-card">
                        <div class="stat-value">{len(all_tenders)}</div>
                        <div class="stat-label">Licitaciones Encontradas</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{days_back}</div>
                        <div class="stat-label">Días Analizados</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{len([t for t in all_tenders if t.get('Estado') == 'Publicada'])}</div>
                        <div class="stat-label">Activas</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Sort options
                col1, col2 = st.columns([3, 1])
                with col2:
                    sort_by = st.selectbox(
                        "Ordenar por",
                        ["Fecha Publicación (Más reciente)", "Fecha Publicación (Más antigua)", "Código"]
                    )
                
                # Sort tenders
                if "Más reciente" in sort_by:
                    all_tenders.sort(key=lambda x: x.get('Fechas', {}).get('FechaPublicacion', ''), reverse=True)
                elif "Más antigua" in sort_by:
                    all_tenders.sort(key=lambda x: x.get('Fechas', {}).get('FechaPublicacion', ''))
                else:
                    all_tenders.sort(key=lambda x: x.get('CodigoExterno', ''))
                
                # Display tenders
                st.subheader(f"📋 Resultados ({len(all_tenders)} licitaciones)")
                
                for tender in all_tenders:
                    render_tender_card(tender)
                
            else:
                st.warning("⚠️ No se encontraron licitaciones con los criterios especificados.")
                st.info("💡 Intenta ampliar el rango de fechas o ajustar las palabras clave.")
    
    else:
        # Welcome message
        st.info("""
        👋 **Bienvenido al Buscador de Licitaciones**
        
        Este sistema te permite buscar licitaciones públicas de Chile de manera inteligente:
        
        - 🔍 **Búsqueda por palabras clave**: Filtra licitaciones relevantes para tu área
        - 🏷️ **Categorización automática**: Organiza resultados por categorías
        - 📊 **Visualización clara**: Información importante al alcance de un vistazo
        - 🔗 **Acceso directo**: Enlaces a Mercado Público para más detalles
        
        **Para comenzar**, configura los filtros en el panel lateral y haz clic en "Buscar Licitaciones".
        
        ---
        
        ⚠️ **Nota**: Esta aplicación usa la API pública de Mercado Público. Para acceso completo,
        necesitas registrar un ticket en [https://www.mercadopublico.cl](https://www.mercadopublico.cl)
        """)

if __name__ == "__main__":
    main()

