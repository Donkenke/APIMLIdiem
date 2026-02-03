import streamlit as st
import pandas as pd
import requests
import urllib3
import json
import sqlite3
import time
from datetime import datetime, timedelta

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Page setup
st.set_page_config(page_title="Monitor de Licitaciones", page_icon="📊", layout="wide")

# Constants
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
DB_FILE = "licitaciones.db"

# Default keywords from your script
DEFAULT_CATEGORIES = {
    "Laboratorio/Materiales": ["laboratorio", "ensayo", "hormigón", "probeta", "asfalto", "áridos", "cemento"],
    "Geotecnia/Suelos": ["geotecnia", "suelo", "calicata", "sondaje", "mecánica de suelo", "estratigrafía"],
    "Ingeniería/Estructuras": ["estructura", "cálculo", "diseño ingeniería", "sísmico", "patología", "puente", "viaducto"],
    "Inspección Técnica (ITO)": ["ito", "inspección técnica", "supervisión", "fiscalización de obra", "hito"]
}

DEFAULT_EXCLUDE = [
    "odontología", "dental", "médico", "clínico", "salud", "examen de sangre", 
    "psicotécnico", "funda", "resina", "mallas bioabsorbibles", "arqueológico",
    "artística", "evento", "limpieza de fosas", "escritorio"
]

# --- DATABASE FUNCTIONS (Persistence) ---
def init_db():
    """Initializes a local SQLite database for bookmarks."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS marcadores (
            codigo_externo TEXT PRIMARY KEY,
            nombre TEXT,
            organismo TEXT,
            fecha_cierre TEXT,
            url TEXT,
            raw_data TEXT,
            fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_tender_to_db(tender_dict):
    """Saves a single tender to the database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO marcadores (codigo_externo, nombre, organismo, fecha_cierre, url, raw_data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            tender_dict['CodigoExterno'],
            tender_dict['Nombre'],
            tender_dict['Organismo'],
            tender_dict['FechaCierre'],
            tender_dict['Link'],
            json.dumps(tender_dict)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving to DB: {e}")
        return False

def get_saved_tenders():
    """Retrieves saved tenders."""
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM marcadores ORDER BY fecha_guardado DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def delete_tender_from_db(codigo_externo):
    """Removes a tender from bookmarks."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM marcadores WHERE codigo_externo = ?", (codigo_externo,))
    conn.commit()
    conn.close()

# --- API & LOGIC FUNCTIONS ---

def get_ticket():
    """Safe retrieval of API Ticket from secrets or sidebar."""
    try:
        return st.secrets["MP_TICKET"]
    except Exception:
        return st.sidebar.text_input("Ingrese Ticket MercadoPúblico", type="password")

def fetch_summaries(date_str, ticket):
    """Fetches the list of tenders for a specific day."""
    url = f"{BASE_URL}/licitaciones.json?fecha={date_str}&ticket={ticket}"
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('Listado', [])
        else:
            st.warning(f"Error API ({response.status_code}): {response.text}")
            return []
    except Exception as e:
        st.error(f"Connection error: {e}")
        return []

def fetch_full_detail(codigo_externo, ticket):
    """Fetches full details for a specific tender code."""
    url = f"{BASE_URL}/licitaciones.json?codigo={codigo_externo}&ticket={ticket}"
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('Listado'):
                return data['Listado'][0]
    except Exception:
        pass
    return None

def parse_tender_data(raw_tender):
    """Extracts relevant fields based on the user's JSON structure."""
    # Ensure we handle cases where raw_tender might be the summary or the full detail
    # The structure provided in prompt: root -> Listado -> [0] -> object
    
    # Defaults
    code = raw_tender.get('CodigoExterno', 'N/A')
    
    # Comprador parsing
    comprador = raw_tender.get('Comprador', {})
    organismo = comprador.get('NombreOrganismo', 'N/A')
    unidad = comprador.get('NombreUnidad', 'N/A')
    
    # Fechas parsing
    fechas = raw_tender.get('Fechas', {})
    pub_date = fechas.get('FechaPublicacion', '')
    close_date = fechas.get('FechaCierre', '')
    
    # URL Construction
    url_publica = f"https://www.mercadopublico.cl/ListadoLicitaciones/Pantallas/DirectorioLicitacion.aspx?idLicitacion={code}"
    
    return {
        "CodigoExterno": code,
        "Nombre": raw_tender.get('Nombre', 'Sin Nombre'),
        "Descripcion": raw_tender.get('Descripcion', ''),
        "Organismo": organismo,
        "Unidad": unidad,
        "FechaPublicacion": pub_date,
        "FechaCierre": close_date,
        "Link": url_publica,
        "Estado": raw_tender.get('Estado', '')
    }

def is_relevant(text, keywords, excludes):
    text_lower = text.lower()
    if any(ex in text_lower for ex in excludes):
        return False
    # If no keywords provided, return True (show all), otherwise check match
    if not keywords:
        return True
    return any(kw in text_lower for kw in keywords)

# --- MAIN APP UI ---

def main():
    init_db()
    ticket = get_ticket()
    
    st.title("🏛️ Buscador Licitaciones")
    
    if not ticket:
        st.warning("⚠️ Por favor configure su Ticket en `.streamlit/secrets.toml` o ingréselo en la barra lateral.")
        st.stop()

    # Tabs for main functionality
    tab_search, tab_saved = st.tabs(["🔍 Buscar Licitaciones", "💾 Marcadores Guardados"])

    # --- TAB 1: SEARCH ---
    with tab_search:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search_date = st.date_input("Fecha a consultar", datetime.now())
        with col2:
            # Flatten keywords for the selector
            all_kws = [kw for sublist in DEFAULT_CATEGORIES.values() for kw in sublist]
            selected_keywords = st.multiselect("Filtrar por palabras clave (dejalo vacío para ver todo)", all_kws, default=all_kws[:3])
        with col3:
            st.write("") # Spacer
            st.write("") 
            run_search = st.button("Buscar en MercadoPúblico", type="primary")

        if run_search:
            date_str = search_date.strftime("%d%m%Y")
            with st.spinner(f"Consultando API para el {date_str}..."):
                # 1. Get Summaries
                summaries = fetch_summaries(date_str, ticket)
                
                # 2. Local Filtering (Fast)
                filtered_summaries = []
                for s in summaries:
                    # Construct text for search
                    full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
                    if is_relevant(full_text, selected_keywords, DEFAULT_EXCLUDE):
                        filtered_summaries.append(s)
                
                if not filtered_summaries:
                    st.info("No se encontraron licitaciones con los filtros actuales.")
                else:
                    st.success(f"Se encontraron {len(filtered_summaries)} licitaciones relevantes. Obteniendo detalles...")
                    
                    # 3. Fetch Full Details & Build Table
                    # Progress bar for fetching details (API rate limit friendly)
                    progress_bar = st.progress(0)
                    table_data = []
                    
                    for i, summary in enumerate(filtered_summaries):
                        code = summary.get('CodigoExterno')
                        # In a real heavy app, you might skip this step and just show summary data first
                        # But user requested detailed extraction based on the JSON provided.
                        full_detail = fetch_full_detail(code, ticket)
                        
                        if full_detail:
                            parsed = parse_tender_data(full_detail)
                            table_data.append(parsed)
                        
                        # Update progress
                        progress_bar.progress((i + 1) / len(filtered_summaries))
                        time.sleep(0.1) # Gentle rate limiting
                    
                    progress_bar.empty()
                    
                    # Create DataFrame
                    if table_data:
                        df_results = pd.DataFrame(table_data)
                        
                        # Add a selection column for saving
                        df_results.insert(0, "Guardar", False)
                        
                        # Display using Data Editor to allow selection
                        st.subheader("Resultados")
                        
                        edited_df = st.data_editor(
                            df_results,
                            column_config={
                                "Guardar": st.column_config.CheckboxColumn(
                                    "Seleccionar",
                                    help="Selecciona para guardar en base de datos",
                                    default=False,
                                ),
                                "Link": st.column_config.LinkColumn(
                                    "Ver Ficha",
                                    help="Ir a MercadoPúblico",
                                    display_text="🔗 Abrir"
                                ),
                                "MontoEstimado": st.column_config.NumberColumn(
                                    "Monto",
                                    format="$%d"
                                )
                            },
                            disabled=["CodigoExterno", "Nombre", "Organismo", "Unidad", "FechaCierre", "Link"],
                            hide_index=True,
                            use_container_width=True
                        )
                        
                        # Button to process selected rows
                        if st.button("💾 Guardar Seleccionadas en BD"):
                            tenders_to_save = edited_df[edited_df["Guardar"] == True]
                            if not tenders_to_save.empty:
                                count = 0
                                for index, row in tenders_to_save.iterrows():
                                    # Convert row back to dict (excluding 'Guardar' col)
                                    tender_dict = row.drop("Guardar").to_dict()
                                    if save_tender_to_db(tender_dict):
                                        count += 1
                                st.success(f"✅ Se guardaron {count} licitaciones correctamente.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("No seleccionaste ninguna licitación.")

    # --- TAB 2: SAVED ---
    with tab_saved:
        st.subheader("📚 Licitaciones Guardadas")
        df_saved = get_saved_tenders()
        
        if df_saved.empty:
            st.info("No hay licitaciones guardadas aún.")
        else:
            # Display saved data
            st.dataframe(
                df_saved,
                column_config={
                    "url": st.column_config.LinkColumn(
                        "Enlace Oficial",
                        display_text="🔗 Ir al Portal"
                    ),
                    "fecha_guardado": st.column_config.DatetimeColumn(
                        "Guardado el",
                        format="D MMM YYYY, HH:mm"
                    )
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Delete functionality
            st.write("---")
            st.write("**Administrar Marcadores**")
            col_del, _ = st.columns([1, 3])
            with col_del:
                code_to_del = st.selectbox("Seleccionar código para borrar", df_saved['codigo_externo'])
                if st.button("🗑️ Borrar Marcador"):
                    delete_tender_from_db(code_to_del)
                    st.success(f"Marcador {code_to_del} eliminado.")
                    time.sleep(1)
                    st.rerun()

if __name__ == "__main__":
    main()
