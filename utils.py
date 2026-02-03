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
def format_datetime(datetime_str):
    """Format ISO datetime to DD/MM HH:MM"""
    if not datetime_str:
        return ""
    try:
        # Handle datetime with milliseconds like "2026-02-03T11:59:50.16"
        if '.' in datetime_str:
            dt_part = datetime_str.split('.')[0]
        else:
            dt_part = datetime_str[:19]
        
        dt = datetime.strptime(dt_part, "%Y-%m-%dT%H:%M:%S")
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
    
    return detected_cats if detected_cats else []

# --- API FUNCTIONS ---
@st.cache_data(ttl=900, show_spinner=False)
def fetch_tenders(ticket, days=2):
    """
    Fetch tenders from MercadoPúblico API
    
    API Response Structure (based on actual response):
    {
        "Cantidad": 1,
        "FechaCreacion": "2026-02-03T18:34:22.7824192Z",
        "Version": "v1",
        "Listado": [
            {
                "CodigoExterno": "1002588-7-LP26",
                "Nombre": "...",
                "Descripcion": "...",
                "Comprador": {
                    "NombreOrganismo": "...",
                    "NombreUnidad": "...",
                    "RegionUnidad": "..."
                },
                "Fechas": {
                    "FechaPublicacion": "2026-02-03T11:59:50.16",
                    "FechaCierre": "2026-02-23T15:00:00"
                }
            }
        ]
    }
    """
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
                
                # Get the Listado array from the response
                tenders = data.get('Listado', [])
                
                # Filter relevant tenders
                for tender in tenders:
                    nombre = tender.get('Nombre', '')
                    desc = tender.get('Descripcion', '')
                    
                    if is_relevant(nombre, desc):
                        # Add categories
                        tender['CategoriasIDIEM'] = categorize_tender(tender)
                        results.append(tender)
            
            elif response.status_code == 401:
                st.error("❌ Error de autenticación: Verifica tu ticket de API")
                break
            
        except requests.exceptions.Timeout:
            st.warning(f"⏱️ Timeout consultando {date_query}")
        except Exception as e:
            st.warning(f"⚠️ Error {date_query}: {str(e)}")
    
    return results
