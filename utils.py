import requests
import urllib3
import streamlit as st
from datetime import datetime, timedelta

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}

EXCLUDE_KEYWORDS = [
    "odontología", "dental", "médico", "clínico", "salud", "examen de sangre",
    "psicotécnico", "funda", "resina", "mallas bioabsorbibles", "arqueológico",
    "artística", "evento", "limpieza de fosas", "escritorio"
]

ALL_KEYWORDS = [kw for cat_list in CATEGORIES.values() for kw in cat_list]

# --- HELPER FUNCTIONS ---
def safe_get(data, key, default=""):
    """Safely get value from dictionary"""
    if not data or not isinstance(data, dict):
        return default
    return data.get(key, default) or default

def format_date(date_str):
    """Format ISO date to DD/MM/YYYY"""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except:
        return date_str

def format_datetime(datetime_str):
    """Format ISO datetime to DD/MM/YYYY HH:MM"""
    if not datetime_str:
        return ""
    try:
        dt = datetime.strptime(datetime_str[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d/%m %H:%M")
    except:
        return datetime_str

def is_relevant(name, desc=""):
    """Check if tender is relevant based on keywords"""
    full_text = (name + " " + desc).lower()
    
    # Exclude medical/irrelevant
    if any(excl in full_text for excl in EXCLUDE_KEYWORDS):
        return False
    
    # Must have at least one keyword
    if any(kw in full_text for kw in ALL_KEYWORDS):
        return True
    
    return False

def categorize_tender(tender):
    """Categorize tender based on keywords"""
    text = (tender.get('Nombre', '') + " " + tender.get('Descripcion', '')).lower()
    detected_cats = []
    
    for cat_name, keywords in CATEGORIES.items():
        if any(kw in text for kw in keywords):
            detected_cats.append(cat_name)
    
    return detected_cats if detected_cats else ["General"]

# --- API FUNCTIONS ---
@st.cache_data(ttl=900, show_spinner=False)
def fetch_tenders(ticket, days=2):
    """Fetch tenders from MercadoPúblico API"""
    results = []
    
    for i in range(days):
        date_query = (datetime.now() - timedelta(days=i)).strftime("%d%m%Y")
        url = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
        
        try:
            response = requests.get(
                url,
                params={'fecha': date_query, 'ticket': ticket},
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                tenders = data.get('Listado', [])
                
                # Filter relevant tenders
                for tender in tenders:
                    nombre = tender.get('Nombre', '')
                    desc = tender.get('Descripcion', '')
                    
                    if is_relevant(nombre, desc):
                        # Ensure Comprador is a dict
                        if 'Comprador' not in tender or tender['Comprador'] is None:
                            tender['Comprador'] = {}
                        
                        # Ensure Fechas is a dict  
                        if 'Fechas' not in tender or tender['Fechas'] is None:
                            tender['Fechas'] = {}
                        
                        # Add categories
                        tender['CategoriasIDIEM'] = categorize_tender(tender)
                        
                        # Add public URL if not present
                        if 'URL_Publica' not in tender:
                            codigo = tender.get('CodigoExterno', '')
                            tender['URL_Publica'] = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={codigo}"
                        
                        results.append(tender)
            
        except Exception as e:
            st.warning(f"Error consultando {date_query}: {str(e)}")
    
    return results
