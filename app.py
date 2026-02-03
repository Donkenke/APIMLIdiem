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

# Internal Filter Logic (Hidden from UI but active)
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
    """Safe retrieval of API Ticket from secrets."""
    try:
        return st.secrets.get("MP_TICKET")
    except Exception:
        return None

def fetch_summaries_for_range(start_date, end_date, ticket):
    """Fetches summaries for a range of dates."""
    all_summaries = []
    
    delta = end_date - start_date
    status_text = st.empty()
    bar = st.progress(0)
    
    total_days = delta.days + 1
    
    for i in range(total_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%d%m%Y")
        
        status_text.caption(f"Escaneando {date_str}...")
        
        url = f"{BASE_URL}/licitaciones.json?fecha={date_str}&ticket={ticket}"
        try:
            response = requests.get(url, verify=False, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get('Listado', [])
                all_summaries.extend(items)
        except Exception:
            pass # Skip errors to keep moving
            
        bar.progress((i + 1) / total_days)
        time.sleep(0.1) # Respect API limits
        
    status_text.empty()
    bar.empty()
    return all_summaries

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

def is_relevant(text, excludes):
    """
    Checks if text contains ANY of the default keywords 
    and NONE of the exclude keywords.
    """
    text_lower = text.lower()
    
    # 1. Check Excludes
    if any(ex in text_lower for ex in excludes):
        return False
        
    # 2. Check Includes (Hardcoded from global config)
    all_kws = [kw for sublist in DEFAULT_CATEGORIES.values() for kw in sublist]
    return any(kw in text_lower for kw in all_kws)

# --- MAIN APP UI ---

def main():
    init_db()
    ticket = get_ticket()
    
    st.title("🏛️ Buscador Licitaciones")
    
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
            "Rango de Fechas",
            value=(ten_days_ago, today),
            max_value=today,
            format="DD/MM/YYYY"
        )
    
    with col2:
        st.write("") 
        st.write("") 
        # Update Button
        force_refresh = st.button("🔄 Actualizar Datos", type="primary", use_container_width=True)

    with col3:
         st.write("")
         st.write("")
         st.caption("Filtros de palabras clave aplicados automáticamente.")

    # --- TABS ---
    tab_search, tab_saved = st.tabs(["🔍 Resultados", "💾 Marcadores"])

    # --- LOGIC: FETCH DATA ---
    # Run if: 1. No data in session, OR 2. Refresh clicked
    if "search_results" not in st.session_state or force_refresh:
        
        # Handle date range input
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = date_range
        elif isinstance(date_range, tuple) and len(date_range) == 1:
            start_d = end_d = date_range[0]
        else:
            start_d = end_d = today

        with st.spinner(f"Analizando licitaciones desde {start_d.strftime('%d/%m')} al {end_d.strftime('%d/%m')}..."):
            
            # 1. Fetch Summaries (Loop over days)
            summaries = fetch_summaries_for_range(start_d, end_d, ticket)
            
            # 2. Filter Locally
            filtered_summaries = []
            for s in summaries:
                full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
                if is_relevant(full_text, DEFAULT_EXCLUDE):
                    filtered_summaries.append(s)
            
            # 3. Fetch Details
            final_data = []
            if filtered_summaries:
                info_ph = st.empty()
                info_ph.info(f"Encontrados {len(filtered_summaries)} candidatos. Descargando detalles...")
                
                prog = st.progress(0)
                for idx, summary in enumerate(filtered_summaries):
                    code = summary.get('CodigoExterno')
                    detail = fetch_full_detail(code, ticket)
                    if detail:
                        final_data.append(parse_tender_data(detail))
                    prog.progress((idx + 1) / len(filtered_summaries))
                    time.sleep(0.1) # Gentle rate limiting
                
                prog.empty()
                info_ph.empty()
            
            # Save to Session State
            st.session_state.search_results = pd.DataFrame(final_data)

    # --- TAB 1: DISPLAY RESULTS ---
    with tab_search:
        df_results = st.session_state.search_results
        
        if df_results.empty:
            st.info("No se encontraron licitaciones relevantes en este periodo.")
        else:
            st.success(f"Mostrando {len(df_results)} licitaciones filtradas.")
            
            # Ensure 'Guardar' column exists for the editor
            if "Guardar" not in df_results.columns:
                df_results.insert(0, "Guardar", False)

            edited_df = st.data_editor(
                df_results,
                column_config={
                    "Guardar": st.column_config.CheckboxColumn(
                        "Seleccionar",
                        help="Guardar en base de datos",
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
                use_container_width=True
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
