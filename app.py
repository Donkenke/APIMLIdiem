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

# KEYWORDS (from your file)
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

# --- DATABASE FUNCTIONS ---
def init_db():
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
    try:
        data_to_save = tender_dict.copy()
        # Clean up boolean columns used for UI before saving
        data_to_save.pop('Explorar', None)
        data_to_save.pop('Guardar', None)
        
        if isinstance(data_to_save.get('FechaCierre'), pd.Timestamp):
            data_to_save['FechaCierre'] = data_to_save['FechaCierre'].isoformat()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO marcadores (codigo_externo, nombre, organismo, fecha_cierre, url, raw_data)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data_to_save['CodigoExterno'],
            data_to_save['Nombre'],
            data_to_save['Organismo'],
            str(data_to_save['FechaCierre']),
            data_to_save['Link'],
            json.dumps(data_to_save, default=str)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving to DB: {e}")
        return False

def get_saved_tenders():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM marcadores ORDER BY fecha_guardado DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def delete_tender_from_db(codigo_externo):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM marcadores WHERE codigo_externo = ?", (codigo_externo,))
    conn.commit()
    conn.close()

# --- API & LOGIC FUNCTIONS ---

def get_ticket():
    try:
        return st.secrets.get("MP_TICKET")
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_summaries_for_range(start_date, end_date, ticket):
    all_summaries = []
    delta = end_date - start_date
    total_days = delta.days + 1
    
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
            pass
    return all_summaries

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_full_detail(codigo_externo, ticket):
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

def parse_date(date_input):
    if not date_input:
        return None
    if isinstance(date_input, datetime):
        return date_input
    try:
        return datetime.strptime(str(date_input), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(str(date_input), "%Y-%m-%d")
        except ValueError:
            return None

def parse_tender_data(raw_tender):
    code = raw_tender.get('CodigoExterno', 'N/A')
    comprador = raw_tender.get('Comprador', {})
    fechas = raw_tender.get('Fechas', {})
    
    return {
        "CodigoExterno": code,
        "Link": f"https://www.mercadopublico.cl/ListadoLicitaciones/Pantallas/DirectorioLicitacion.aspx?idLicitacion={code}",
        "Nombre": raw_tender.get('Nombre', 'Sin Nombre'),
        "Organismo": comprador.get('NombreOrganismo', 'N/A'),
        "Unidad": comprador.get('NombreUnidad', 'N/A'),
        "FechaPublicacion": parse_date(fechas.get('FechaPublicacion')),
        "FechaCierre": parse_date(fechas.get('FechaCierre')),
        "Estado": raw_tender.get('Estado', ''),
        "MontoEstimado": float(raw_tender.get('MontoEstimado', 0)),
        "Descripcion": raw_tender.get('Descripcion', '')
    }

def is_relevant(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in SEARCH_KEYWORDS)

def is_date_valid(date_obj):
    if not date_obj:
        return True
    return date_obj >= datetime.now()

# --- MAIN APP UI ---

def main():
    init_db()
    ticket = get_ticket()
    
    st.title("🏛️ Buscador Licitaciones")
    
    if not ticket:
        st.warning("⚠️ Ticket no encontrado.")
        st.stop()

    # --- CONTROLS ---
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        today = datetime.now()
        ten_days_ago = today - timedelta(days=10)
        date_range = st.date_input(
            "Rango de Fechas (Publicación)",
            value=(ten_days_ago, today),
            max_value=today,
            format="DD/MM/YYYY"
        )
    
    with col2:
        st.write("") 
        st.write("") 
        search_clicked = st.button("🔄 Buscar Datos", type="primary", use_container_width=True)

    with col3:
         st.write("")
         st.write("")
         st.caption(f"Filtro: {len(SEARCH_KEYWORDS)} palabras clave.")

    # --- TABS ---
    tab_search, tab_detail, tab_saved = st.tabs(["🔍 Resultados", "📄 Detalle", "💾 Marcadores"])

    # --- FETCH LOGIC ---
    if search_clicked or "search_results" not in st.session_state:
        if isinstance(date_range, tuple):
            start_d = date_range[0]
            end_d = date_range[1] if len(date_range) > 1 else date_range[0]
        else:
            start_d = end_d = today

        with st.spinner(f"Analizando..."):
            summaries = fetch_summaries_for_range(start_d, end_d, ticket)
            filtered_summaries = []
            
            for s in summaries:
                full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
                c_date = parse_date(s.get('FechaCierre'))
                
                if is_relevant(full_text) and is_date_valid(c_date):
                    filtered_summaries.append(s)
            
            final_data = []
            if filtered_summaries:
                prog = st.progress(0)
                for idx, summary in enumerate(filtered_summaries):
                    code = summary.get('CodigoExterno')
                    detail = fetch_full_detail(code, ticket)
                    if detail:
                        final_data.append(parse_tender_data(detail))
                    prog.progress((idx + 1) / len(filtered_summaries))
                prog.empty()
            
            df = pd.DataFrame(final_data)
            if not df.empty:
                df = df.sort_values(by="FechaPublicacion", ascending=False)
            st.session_state.search_results = df

    # --- TAB 1: RESULTS ---
    with tab_search:
        if "search_results" in st.session_state and not st.session_state.search_results.empty:
            df_results = st.session_state.search_results.copy()
            
            # Add Interactive Columns
            # We add "Explorar" for details and "Guardar" for database
            if "Explorar" not in df_results.columns:
                df_results.insert(0, "Explorar", False)
            if "Guardar" not in df_results.columns:
                df_results.insert(1, "Guardar", False)

            # Reorder columns: Explorar, Guardar, Codigo, Link, Nombre...
            cols_order = ["Explorar", "Guardar", "CodigoExterno", "Link", "Nombre", "Organismo", "FechaPublicacion", "FechaCierre", "MontoEstimado"]

            st.info("💡 Marca la casilla 'Explorar' para ver detalles, o 'Guardar' para almacenarla.")

            edited_df = st.data_editor(
                df_results,
                column_order=cols_order,
                column_config={
                    "Explorar": st.column_config.CheckboxColumn(
                        "👁️", width="small", help="Ver Detalle"
                    ),
                    "Guardar": st.column_config.CheckboxColumn(
                        "💾", width="small", help="Guardar en DB"
                    ),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="medium"),
                    "Link": st.column_config.LinkColumn(
                        "Web", display_text="🔗", width="small"
                    ),
                    "Nombre": st.column_config.TextColumn(
                        "Nombre Licitación", width="large"
                    ),
                    "FechaPublicacion": st.column_config.DateColumn(
                        "Publicado", format="D MMM YYYY"
                    ),
                    "FechaCierre": st.column_config.DateColumn(
                        "Cierre", format="D MMM YYYY"
                    ),
                    "MontoEstimado": st.column_config.NumberColumn(
                        "Monto ($)", format="$%d"
                    )
                },
                disabled=["CodigoExterno", "Link", "Nombre", "Organismo", "FechaPublicacion", "FechaCierre", "MontoEstimado"],
                hide_index=True,
                use_container_width=True,
                height=800  # Increased Height
            )

            # --- HANDLE EXPLORAR SELECTION ---
            # Check if any row has 'Explorar' set to True
            tenders_to_explore = edited_df[edited_df["Explorar"] == True]
            
            if not tenders_to_explore.empty:
                # We take the first one selected to avoid conflicts
                st.session_state['selected_tender'] = tenders_to_explore.iloc[0].to_dict()
                if len(tenders_to_explore) > 1:
                    st.toast("⚠️ Se muestran detalles solo de la primera selección.", icon="ℹ️")
            else:
                # Clear selection if unchecked
                if 'selected_tender' in st.session_state:
                     del st.session_state['selected_tender']

            # SAVE BUTTON
            if st.button("💾 Guardar Seleccionados"):
                tenders_to_save = edited_df[edited_df["Guardar"] == True]
                if not tenders_to_save.empty:
                    count = 0
                    for index, row in tenders_to_save.iterrows():
                        tender_dict = row.to_dict()
                        if save_tender_to_db(tender_dict):
                            count += 1
                    st.toast(f"✅ {count} licitaciones guardadas.", icon="💾")
                else:
                    st.warning("Marca la columna 💾 para guardar.")
        else:
            st.info("No hay resultados. Realiza una búsqueda.")

    # --- TAB 2: DETAILS ---
    with tab_detail:
        if 'selected_tender' in st.session_state:
            row_data = st.session_state['selected_tender']
            
            st.header(row_data["Nombre"])
            st.caption(f"ID: {row_data['CodigoExterno']} | Estado: {row_data['Estado']}")
            
            d_col1, d_col2, d_col3 = st.columns(3)
            with d_col1:
                st.metric("Organismo", row_data["Organismo"])
            with d_col2:
                # Handle both datetime objects and strings if they got converted
                pub = row_data["FechaPublicacion"]
                if isinstance(pub, str): pub = parse_date(pub)
                st.metric("Fecha Publicación", pub.strftime("%d %b %Y") if pub else "N/A")
            with d_col3:
                close = row_data["FechaCierre"]
                if isinstance(close, str): close = parse_date(close)
                st.metric("Fecha Cierre", close.strftime("%d %b %Y") if close else "N/A")

            st.divider()
            st.subheader("Descripción")
            st.write(row_data["Descripcion"])
            
            st.divider()
            st.markdown(f"[**🔗 Ver Ficha en MercadoPúblico**]({row_data['Link']})")
        else:
            st.info("👈 Marca la casilla '👁️' (Explorar) en la tabla de Resultados para ver el detalle aquí.")

    # --- TAB 3: SAVED ---
    with tab_saved:
        st.subheader("📚 Mis Marcadores")
        df_saved = get_saved_tenders()
        
        if df_saved.empty:
            st.info("No hay licitaciones guardadas.")
        else:
            st.dataframe(
                df_saved,
                column_config={
                    "url": st.column_config.LinkColumn("Link", display_text="🔗"),
                    "fecha_guardado": st.column_config.DatetimeColumn("Guardado", format="D MMM YYYY, HH:mm")
                },
                hide_index=True,
                use_container_width=True
            )
            
            col_del, _ = st.columns([1, 3])
            with col_del:
                code_to_del = st.selectbox("Eliminar marcador:", df_saved['codigo_externo'])
                if st.button("🗑️ Borrar"):
                    delete_tender_from_db(code_to_del)
                    st.rerun()

if __name__ == "__main__":
    main()
