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

# --- KEYWORD MAPPING (Generated from your Excel file) ---
# Maps Keyword -> (Category, Sub-Specialty)
KEYWORD_MAPPING = {
  "Asesoría inspección": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "AIF": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "AIT": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "ATIF": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "ATOD": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "AFOS": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "ATO": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "ITO": ("1. Inspección Técnica y Supervisión (Core)", "Siglas y Roles"),
  "Supervisión Construcción Pozos": ("1. Inspección Técnica y Supervisión (Core)", "Supervisión Específica"),
  "Estudio Ingeniería": ("2. Ingeniería, Geotecnia y Laboratorio", "Ingeniería y Estructuras"),
  "Estructural": ("2. Ingeniería, Geotecnia y Laboratorio", "Ingeniería y Estructuras"),
  "Ingeniería Conceptual": ("2. Ingeniería, Geotecnia y Laboratorio", "Ingeniería y Estructuras"),
  "Evaluación Estructural": ("2. Ingeniería, Geotecnia y Laboratorio", "Ingeniería y Estructuras"),
  "Mecánica Suelos": ("2. Ingeniería, Geotecnia y Laboratorio", "Geotecnia y Suelos"),
  "Geológico": ("2. Ingeniería, Geotecnia y Laboratorio", "Geotecnia y Suelos"),
  "Geotécnico": ("2. Ingeniería, Geotecnia y Laboratorio", "Geotecnia y Suelos"),
  "Hidrogeológico": ("2. Ingeniería, Geotecnia y Laboratorio", "Geotecnia y Suelos"),
  "Ensayos": ("2. Ingeniería, Geotecnia y Laboratorio", "Laboratorio"),
  "Topográfico": ("3. Topografía y Levantamientos", "Mediciones y Catastro"),
  "Topografía": ("3. Topografía y Levantamientos", "Mediciones y Catastro"),
  "Levantamiento": ("3. Topografía y Levantamientos", "Mediciones y Catastro"),
  "Levantamiento Catastro": ("3. Topografía y Levantamientos", "Mediciones y Catastro"),
  "Monitoreo y Levantamiento de Condiciones Existentes": ("3. Topografía y Levantamientos", "Mediciones y Catastro"),
  "Aerofotogrametría": ("3. Topografía y Levantamientos", "Aéreo / Crítico"),
  "Aerofotogramétrico": ("3. Topografía y Levantamientos", "Aéreo / Crítico"),
  "Levantamiento crítico": ("3. Topografía y Levantamientos", "Aéreo / Crítico"),
  "Huella Carbono": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Cambio climático": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "PACC": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "PCC": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Gases Efecto Invernadero": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Actualización de la Estrategia Climática Nacional": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Actualización del NDC": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Metodología de cálculo de huella de carbono": ("4. Sustentabilidad y Medio Ambiente", "Cambio Climático y Huella"),
  "Energética": ("4. Sustentabilidad y Medio Ambiente", "Eficiencia y Ambiente"),
  "Sustentabilidad": ("4. Sustentabilidad y Medio Ambiente", "Eficiencia y Ambiente"),
  "Sustentable": ("4. Sustentabilidad y Medio Ambiente", "Eficiencia y Ambiente"),
  "Ruido Acústico": ("4. Sustentabilidad y Medio Ambiente", "Eficiencia y Ambiente"),
  "Ruido Ambiental": ("4. Sustentabilidad y Medio Ambiente", "Eficiencia y Ambiente"),
  "Riles": ("4. Sustentabilidad y Medio Ambiente", "Aguas y Residuos"),
  "Aguas Servidas": ("4. Sustentabilidad y Medio Ambiente", "Aguas y Residuos"),
  "Reclamaciones": ("5. Gestión de Contratos y Forense (Claims)", "Gestión Contractual"),
  "Revisión Contratos Obras": ("5. Gestión de Contratos y Forense (Claims)", "Gestión Contractual"),
  "Revisión Contratos Operación": ("5. Gestión de Contratos y Forense (Claims)", "Gestión Contractual"),
  "Revisión Ofertas": ("5. Gestión de Contratos y Forense (Claims)", "Gestión Contractual"),
  "Revisión Bases": ("5. Gestión de Contratos y Forense (Claims)", "Gestión Contractual"),
  "Auditoría Forense": ("5. Gestión de Contratos y Forense (Claims)", "Peritajes y Análisis"),
  "Análisis Costo": ("5. Gestión de Contratos y Forense (Claims)", "Peritajes y Análisis"),
  "Pérdida de productividad": ("5. Gestión de Contratos y Forense (Claims)", "Peritajes y Análisis"),
  "Peritajes Forenses": ("5. Gestión de Contratos y Forense (Claims)", "Peritajes y Análisis"),
  "Incendio Fuego": ("5. Gestión de Contratos y Forense (Claims)", "Riesgos y Vibraciones"),
  "Riesgo": ("5. Gestión de Contratos y Forense (Claims)", "Riesgos y Vibraciones"),
  "Estudio Vibraciones": ("5. Gestión de Contratos y Forense (Claims)", "Riesgos y Vibraciones"),
  "Arquitectura": ("6. Arquitectura y Edificación", "Diseño y Anteproyectos"),
  "Elaboración Anteproyecto": ("6. Arquitectura y Edificación", "Diseño y Anteproyectos"),
  "Estudio de cabida": ("6. Arquitectura y Edificación", "Diseño y Anteproyectos"),
  "Estudio de Accesibilidad Universal": ("6. Arquitectura y Edificación", "Diseño y Anteproyectos"),
  "Patrimonio": ("6. Arquitectura y Edificación", "Patrimonio"),
  "Monumento Histórico": ("6. Arquitectura y Edificación", "Patrimonio"),
  "Diseño Cesfam": ("6. Arquitectura y Edificación", "Salud (CESFAM)"),
  "Rehabilitación Cesfam": ("6. Arquitectura y Edificación", "Salud (CESFAM)"),
  "Aeródromo": ("7. Infraestructura y Estudios Básicos", "Transporte"),
  "Aeropuerto": ("7. Infraestructura y Estudios Básicos", "Transporte"),
  "Aeroportuario": ("7. Infraestructura y Estudios Básicos", "Transporte"),
  "Túnel": ("7. Infraestructura y Estudios Básicos", "Transporte"),
  "Vialidad": ("7. Infraestructura y Estudios Básicos", "Transporte"),
  "Prefactibilidad": ("7. Infraestructura y Estudios Básicos", "Estudios de Inversión"),
  "Plan Inversional": ("7. Infraestructura y Estudios Básicos", "Estudios de Inversión"),
  "Estudio Demanda": ("7. Infraestructura y Estudios Básicos", "Estudios de Inversión"),
  "Estudio Básico": ("7. Infraestructura y Estudios Básicos", "Estudios de Inversión"),
  "Obras de Emergencia": ("7. Infraestructura y Estudios Básicos", "Otros"),
  "Riego": ("7. Infraestructura y Estudios Básicos", "Otros"),
  "Ministerio de Vivienda": ("8. Mandantes Clave (Organismos Públicos)", "Vivienda (MINVU)"),
  "Minvu": ("8. Mandantes Clave (Organismos Públicos)", "Vivienda (MINVU)"),
  "Servicio de Vivienda": ("8. Mandantes Clave (Organismos Públicos)", "Vivienda (MINVU)"),
  "Serviu": ("8. Mandantes Clave (Organismos Públicos)", "Vivienda (MINVU)"),
  "Ministerio de Educación": ("8. Mandantes Clave (Organismos Públicos)", "Educación (MINEDUC)"),
  "Mineduc": ("8. Mandantes Clave (Organismos Públicos)", "Educación (MINEDUC)"),
  "Dirección Educación Pública": ("8. Mandantes Clave (Organismos Públicos)", "Educación (MINEDUC)"),
  "Servicios Locales Educacionales": ("8. Mandantes Clave (Organismos Públicos)", "Educación (MINEDUC)"),
  "Ministerio de Salud": ("8. Mandantes Clave (Organismos Públicos)", "Salud (MINSAL)"),
  "Servicio de Salud": ("8. Mandantes Clave (Organismos Públicos)", "Salud (MINSAL)"),
  "Dirección de Arquitectura": ("8. Mandantes Clave (Organismos Públicos)", "Obras Públicas (MOP)"),
  "Superintendencia de Infraestructura": ("8. Mandantes Clave (Organismos Públicos)", "Obras Públicas (MOP)"),
  "Metropolitana": ("8. Mandantes Clave (Organismos Públicos)", "Alcance Geográfico"),
  "Regional": ("8. Mandantes Clave (Organismos Públicos)", "Alcance Geográfico")
}

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
        data_to_save.pop('Ver', None)
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

def get_category_info(text):
    """
    Scans text for keywords in the mapping. 
    Returns (Category, Sub-Specialty) of the FIRST match found, or ('Otros', 'Sin Clasificar').
    """
    text_lower = text.lower()
    for keyword, (cat, sub) in KEYWORD_MAPPING.items():
        if keyword.lower() in text_lower:
            return cat, sub
    return None, None

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
         st.caption(f"Filtro activo: {len(KEYWORD_MAPPING)} palabras clave.")

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
            
            # Phase 1: Filter & Categorize
            for s in summaries:
                full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
                c_date = parse_date(s.get('FechaCierre'))
                
                cat, sub = get_category_info(full_text)
                
                if cat and is_date_valid(c_date):
                    # Inject category info into the summary dict temporarily to pass it along
                    s['_cat'] = cat
                    s['_sub'] = sub
                    filtered_summaries.append(s)
            
            # Phase 2: Details
            final_data = []
            if filtered_summaries:
                prog = st.progress(0)
                for idx, summary in enumerate(filtered_summaries):
                    code = summary.get('CodigoExterno')
                    detail = fetch_full_detail(code, ticket)
                    if detail:
                        parsed = parse_tender_data(detail)
                        # Add the categories we found earlier
                        parsed['Categoría Estratégica'] = summary['_cat']
                        parsed['Sub-Especialidad'] = summary['_sub']
                        final_data.append(parsed)
                    prog.progress((idx + 1) / len(filtered_summaries))
                prog.empty()
            
            df = pd.DataFrame(final_data)
            # Default Sort: Publicacion Descending
            if not df.empty:
                df = df.sort_values(by="FechaPublicacion", ascending=False)
            st.session_state.search_results = df

    # --- TAB 1: RESULTS ---
    with tab_search:
        if "search_results" in st.session_state and not st.session_state.search_results.empty:
            df_results = st.session_state.search_results.copy()
            
            # Add Interactive Columns
            # "Web" will be the LinkColumn
            # "Ver" will be the Selection Checkbox
            # "Guardar" will be the Save Checkbox
            
            if "Ver" not in df_results.columns:
                df_results.insert(0, "Ver", False)
            if "Guardar" not in df_results.columns:
                df_results.insert(1, "Guardar", False)
            
            # We rename 'Link' column to 'Web' for the display
            df_results["Web"] = df_results["Link"]
            
            # Column Order
            cols_order = [
                "Web", "Ver", "Guardar", "CodigoExterno", 
                "Categoría Estratégica", "Sub-Especialidad",
                "Nombre", "FechaPublicacion", "FechaCierre", "MontoEstimado"
            ]

            st.info("💡 Usa la columna 'Ver' para revisar el detalle y 'Guardar' para almacenar.")

            edited_df = st.data_editor(
                df_results,
                column_order=cols_order,
                column_config={
                    "Web": st.column_config.LinkColumn(
                        "Web", display_text="🔗", width="small", help="Ir a MercadoPúblico"
                    ),
                    "Ver": st.column_config.CheckboxColumn(
                        "Ver", width="small", help="Ver Detalle Interno"
                    ),
                    "Guardar": st.column_config.CheckboxColumn(
                        "💾", width="small", help="Guardar en DB"
                    ),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="small"),
                    "Categoría Estratégica": st.column_config.TextColumn("Categoría", width="medium"),
                    "Sub-Especialidad": st.column_config.TextColumn("Especialidad", width="medium"),
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
                        "Monto", format="$%d"
                    )
                },
                disabled=["CodigoExterno", "Web", "Nombre", "Categoría Estratégica", "Sub-Especialidad", "FechaPublicacion", "FechaCierre", "MontoEstimado"],
                hide_index=True,
                use_container_width=True,
                height=800
            )

            # --- HANDLE 'VER' SELECTION ---
            # Check if any row has 'Ver' set to True
            tenders_to_explore = edited_df[edited_df["Ver"] == True]
            
            if not tenders_to_explore.empty:
                st.session_state['selected_tender'] = tenders_to_explore.iloc[0].to_dict()
                if len(tenders_to_explore) > 1:
                    st.toast("⚠️ Se muestran detalles solo de la primera selección.", icon="ℹ️")
            else:
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
            
            # Tags for Category
            st.markdown(f"**Categoría:** `{row_data.get('Categoría Estratégica', 'N/A')}`")
            st.markdown(f"**Especialidad:** `{row_data.get('Sub-Especialidad', 'N/A')}`")

            st.divider()

            d_col1, d_col2, d_col3 = st.columns(3)
            with d_col1:
                st.metric("Organismo", row_data["Organismo"])
            with d_col2:
                # Handle both datetime objects and strings
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
            st.markdown(f"[**🔗 Ver Ficha Oficial en MercadoPúblico**]({row_data['Link']})")
        else:
            st.info("👈 Marca la casilla 'Ver' en la tabla de Resultados para ver el detalle aquí.")

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
