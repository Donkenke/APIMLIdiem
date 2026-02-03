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

# 1. NEW KEYWORD LIST (Extracted from your uploaded file)
SEARCH_KEYWORDS = [
    "Asesoría inspección", "AIF", "AIT", "ATIF", "ATOD", "AFOS", "ATO", "ITO",
    "Estudio Ingeniería", "Estructural", "Mecánica Suelos", "Geológico", "Geotécnico",
    "Topográfico", "Topografía", "Aeródromo", "Aeropuerto", "Aeroportuario",
    "Aerofotogrametría", "Aerofotogramétrico", "Levantamiento", "Energética",
    "Diseño Cesfam", "Rehabilitación Cesfam", "Túnel", "Patrimonio", "Monumento Histórico",
    "Obras de Emergencia", "Levantamiento crítico", "Hidrogeológico", "Prefactibilidad",
    "Plan Inversional", "Huella Carbono", "Cambio climático", "PACC", "PCC",
    "Sustentabilidad", "Sustentable", "Ruido Acústico", "Ruido Ambiental",
    "Gases Efecto Invernadero", "Incendio Fuego", "Riesgo", "Levantamiento Catastro",
    "Estudio Demanda", "Reclamaciones", "Revisión Contratos Obras",
    "Revisión Contratos Operación", "Auditoría Forense", "Revisión Ofertas",
    "Revisión Bases", "Análisis Costo", "Pérdida de productividad", "Peritajes Forenses",
    "Ingeniería Conceptual", "Estudio Vibraciones", "Evaluación Estructural",
    "Monitoreo y Levantamiento de Condiciones Existentes", "Riego", "Estudio Básico",
    "Riles", "Aguas Servidas", "Supervisión Construcción Pozos",
    "Actualización de la Estrategia Climática Nacional", "Actualización del NDC",
    "Metodología de cálculo de huella de carbono", "Estudio de cabida",
    "Estudio de Accesibilidad Universal", "Elaboración Anteproyecto", "Arquitectura",
    "Ministerio de Educación", "Mineduc", "Dirección Educación Pública",
    "Servicios Locales Educacionales", "Superintendencia de Infraestructura",
    "Dirección de Arquitectura", "Ministerio de Vivienda", "Servicio de Vivienda",
    "Metropolitana", "Regional", "Ministerio de Salud", "Minvu", "Serviu",
    "Servicio de Salud", "Vialidad", "Ensayos"
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
    """Safe retrieval of API Ticket from secrets."""
    try:
        return st.secrets.get("MP_TICKET")
    except Exception:
        return None

# 4. CACHING IMPLEMENTATION
# This ensures that if the user searches the same dates, we use the cache instead of the API.
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_summaries_for_range(start_date, end_date, ticket):
    """Fetches summaries for a range of dates. Cached for 1 hour."""
    all_summaries = []
    
    delta = end_date - start_date
    total_days = delta.days + 1
    
    # We use a placeholder for progress in the UI outside the cache function
    # But inside cache, we just do the logic
    
    for i in range(total_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%d%m%Y")
        
        url = f"{BASE_URL}/licitaciones.json?fecha={date_str}&ticket={ticket}"
        try:
            response = requests.get(url, verify=False, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get('Listado', [])
                all_summaries.extend(items)
        except Exception:
            pass # Skip errors to keep moving
        
    return all_summaries

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_full_detail(codigo_externo, ticket):
    """Fetches full details for a specific tender code. Cached."""
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

def parse_date_str(date_str):
    """Helper to parse API date strings."""
    if not date_str:
        return None
    try:
        # Standard format usually returned by MP: '2023-10-31T15:00:00'
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            # Fallback for simple date
            return datetime.strptime(date_str, "%Y-%m-%d")
        except:
            return None

def parse_tender_data(raw_tender):
    """Extracts relevant fields."""
    code = raw_tender.get('CodigoExterno', 'N/A')
    comprador = raw_tender.get('Comprador', {})
    fechas = raw_tender.get('Fechas', {})
    
    return {
        "CodigoExterno": code,
        "Nombre": raw_tender.get('Nombre', 'Sin Nombre'),
        "Descripcion": raw_tender.get('Descripcion', ''),
        "Organismo": comprador.get('NombreOrganismo', 'N/A'),
        "Unidad": comprador.get('NombreUnidad', 'N/A'),
        "FechaPublicacion": fechas.get('FechaPublicacion', ''),
        "FechaCierre": fechas.get('FechaCierre', ''),
        "Link": f"https://www.mercadopublico.cl/ListadoLicitaciones/Pantallas/DirectorioLicitacion.aspx?idLicitacion={code}",
        "Estado": raw_tender.get('Estado', ''),
        "MontoEstimado": raw_tender.get('MontoEstimado', 0)
    }

def is_relevant(text):
    """
    Checks if text contains ANY of the keywords from the uploaded file.
    Excludes are removed as requested.
    """
    text_lower = text.lower()
    
    # Check Includes (from strict list)
    return any(kw.lower() in text_lower for kw in SEARCH_KEYWORDS)

def is_date_valid(date_str):
    """
    3. DATE FILTERING
    Returns True if the closing date is in the future or valid.
    Returns False if the date has passed.
    """
    if not date_str:
        return True # Keep if date is missing to be safe
    
    dt_obj = parse_date_str(date_str)
    if dt_obj:
        if dt_obj < datetime.now():
            return False # Expired
    return True

# --- MAIN APP UI ---

def main():
    init_db()
    ticket = get_ticket()
    
    st.title("🏛️ Buscador Licitaciones (Optimizado)")
    
    if not ticket:
        st.warning("⚠️ Ticket no encontrado. Configure MP_TICKET en `.streamlit/secrets.toml`.")
        st.stop()

    # --- TOP CONTROLS ---
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Date Slicer (Range)
        today = datetime.now()
        ten_days_ago = today - timedelta(days=10)
        
        date_range = st.date_input(
            "Rango de Fechas (Fecha Publicación)",
            value=(ten_days_ago, today),
            max_value=today,
            format="DD/MM/YYYY"
        )
    
    with col2:
        st.write("") 
        st.write("") 
        # Update Button
        # Note: We use type="primary" to highlight it
        search_clicked = st.button("🔄 Buscar Datos", type="primary", use_container_width=True)

    with col3:
         st.write("")
         st.write("")
         st.caption(f"Filtro activo: {len(SEARCH_KEYWORDS)} palabras clave.")

    # --- TABS ---
    tab_search, tab_saved = st.tabs(["🔍 Resultados", "💾 Marcadores"])

    # --- LOGIC: FETCH DATA ---
    # Trigger if search is clicked OR if we have valid dates and no data yet
    should_run = search_clicked or "search_results" not in st.session_state

    if should_run:
        
        # Handle date range input
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = date_range
        elif isinstance(date_range, tuple) and len(date_range) == 1:
            start_d = end_d = date_range[0]
        else:
            start_d = end_d = today

        with st.spinner(f"Analizando licitaciones desde {start_d.strftime('%d/%m')} al {end_d.strftime('%d/%m')}..."):
            
            # 1. Fetch Summaries (Using Cached Function)
            summaries = fetch_summaries_for_range(start_d, end_d, ticket)
            
            # 2. Filter Locally (Keywords + Date Validity)
            filtered_summaries = []
            
            # Create a progress bar for the filtering phase
            prog_text = st.empty()
            prog_bar = st.progress(0)
            
            total_items = len(summaries)
            
            for idx, s in enumerate(summaries):
                # UI Update every 10 items to save resources
                if idx % 10 == 0:
                    prog_bar.progress((idx + 1) / total_items)
                    prog_text.caption(f"Filtrando {idx+1}/{total_items}...")

                full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
                closing_date_str = s.get('FechaCierre', '')
                
                # Apply Keyword Filter
                if is_relevant(full_text):
                    # Apply Date Filter (Must not be expired)
                    if is_date_valid(closing_date_str):
                        filtered_summaries.append(s)
            
            prog_text.empty()
            prog_bar.empty()
            
            # 3. Fetch Details
            final_data = []
            if filtered_summaries:
                info_ph = st.empty()
                info_ph.info(f"Encontrados {len(filtered_summaries)} candidatos. Descargando detalles...")
                
                prog_details = st.progress(0)
                for idx, summary in enumerate(filtered_summaries):
                    code = summary.get('CodigoExterno')
                    # Use Cached Detail Fetcher
                    detail = fetch_full_detail(code, ticket)
                    if detail:
                        final_data.append(parse_tender_data(detail))
                    
                    prog_details.progress((idx + 1) / len(filtered_summaries))
                
                prog_details.empty()
                info_ph.empty()
            
            # Save to Session State
            st.session_state.search_results = pd.DataFrame(final_data)

    # --- TAB 1: DISPLAY RESULTS ---
    with tab_search:
        if "search_results" in st.session_state:
            df_results = st.session_state.search_results
            
            if df_results.empty:
                st.info("No se encontraron licitaciones relevantes o vigentes en este periodo.")
            else:
                st.success(f"Mostrando {len(df_results)} licitaciones filtradas.")
                
                # Ensure 'Guardar' column exists for the editor
                if "Guardar" not in df_results.columns:
                    df_results.insert(0, "Guardar", False)

                # 5. EXPANDED TABLE HEIGHT
                edited_df = st.data_editor(
                    df_results,
                    column_config={
                        "Guardar": st.column_config.CheckboxColumn(
                            "Seleccionar",
                            help="Guardar en base de datos",
                            default=False,
                            width="small"
                        ),
                        "Link": st.column_config.LinkColumn(
                            "Ver Ficha",
                            display_text="🔗 Abrir"
                        ),
                        "MontoEstimado": st.column_config.NumberColumn(
                            "Monto",
                            format="$%d"
                        ),
                        "FechaCierre": st.column_config.DatetimeColumn(
                            "Cierre",
                            format="D MMM YYYY, HH:mm"
                        )
                    },
                    disabled=["CodigoExterno", "Nombre", "Organismo", "Unidad", "FechaCierre", "Link", "MontoEstimado", "Estado", "FechaPublicacion", "Descripcion"],
                    hide_index=True,
                    use_container_width=True,
                    height=800  # <--- Increased height here
                )

                # Save Button
                if st.button("💾 Guardar Seleccionadas"):
                    tenders_to_save = edited_df[edited_df["Guardar"] == True]
                    if not tenders_to_save.empty:
                        count = 0
                        for index, row in tenders_to_save.iterrows():
                            tender_dict = row.drop("Guardar").to_dict()
                            if save_tender_to_db(tender_dict):
                                count += 1
                        st.toast(f"✅ {count} licitaciones guardadas.", icon="💾")
                        time.sleep(1)
                    else:
                        st.warning("Selecciona al menos una fila.")
        else:
            st.info("Presiona 'Buscar Datos' para comenzar.")

    # --- TAB 2: SAVED ---
    with tab_saved:
        st.subheader("📚 Mis Licitaciones")
        df_saved = get_saved_tenders()
        
        if df_saved.empty:
            st.info("No hay marcadores guardados.")
        else:
            st.dataframe(
                df_saved,
                column_config={
                    "url": st.column_config.LinkColumn(
                        "Link",
                        display_text="🔗 Ir al Portal"
                    ),
                    "fecha_guardado": st.column_config.DatetimeColumn(
                        "Guardado el",
                        format="D MMM YYYY, HH:mm"
                    )
                },
                hide_index=True,
                use_container_width=True,
                height=600
            )
            
            st.divider()
            col_del, _ = st.columns([1, 3])
            with col_del:
                code_to_del = st.selectbox("Eliminar marcador:", df_saved['codigo_externo'])
                if st.button("🗑️ Borrar"):
                    delete_tender_from_db(code_to_del)
                    st.rerun()

if __name__ == "__main__":
    main()
