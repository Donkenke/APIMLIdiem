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

# --- KEYWORD MAPPING ---
KEYWORD_MAPPING = {
  "Asesoría inspección": "Inspección Técnica y Supervisión",
  "AIF": "Inspección Técnica y Supervisión",
  "AIT": "Inspección Técnica y Supervisión",
  "ATIF": "Inspección Técnica y Supervisión",
  "ATOD": "Inspección Técnica y Supervisión",
  "AFOS": "Inspección Técnica y Supervisión",
  "ATO": "Inspección Técnica y Supervisión",
  "ITO": "Inspección Técnica y Supervisión",
  "Supervisión Construcción Pozos": "Inspección Técnica y Supervisión",
  "Estudio Ingeniería": "Ingeniería, Geotecnia y Laboratorio",
  "Estructural": "Ingeniería, Geotecnia y Laboratorio",
  "Ingeniería Conceptual": "Ingeniería, Geotecnia y Laboratorio",
  "Evaluación Estructural": "Ingeniería, Geotecnia y Laboratorio",
  "Mecánica Suelos": "Ingeniería, Geotecnia y Laboratorio",
  "Geológico": "Ingeniería, Geotecnia y Laboratorio",
  "Geotécnico": "Ingeniería, Geotecnia y Laboratorio",
  "Hidrogeológico": "Ingeniería, Geotecnia y Laboratorio",
  "Ensayos": "Ingeniería, Geotecnia y Laboratorio",
  "Topográfico": "Topografía y Levantamientos",
  "Topografía": "Topografía y Levantamientos",
  "Levantamiento": "Topografía y Levantamientos",
  "Levantamiento Catastro": "Topografía y Levantamientos",
  "Monitoreo y Levantamiento de Condiciones Existentes": "Topografía y Levantamientos",
  "Aerofotogrametría": "Topografía y Levantamientos",
  "Aerofotogramétrico": "Topografía y Levantamientos",
  "Levantamiento crítico": "Topografía y Levantamientos",
  "Huella Carbono": "Sustentabilidad y Medio Ambiente",
  "Cambio climático": "Sustentabilidad y Medio Ambiente",
  "PACC": "Sustentabilidad y Medio Ambiente",
  "PCC": "Sustentabilidad y Medio Ambiente",
  "Gases Efecto Invernadero": "Sustentabilidad y Medio Ambiente",
  "Actualización de la Estrategia Climática Nacional": "Sustentabilidad y Medio Ambiente",
  "Actualización del NDC": "Sustentabilidad y Medio Ambiente",
  "Metodología de cálculo de huella de carbono": "Sustentabilidad y Medio Ambiente",
  "Energética": "Sustentabilidad y Medio Ambiente",
  "Sustentabilidad": "Sustentabilidad y Medio Ambiente",
  "Sustentable": "Sustentabilidad y Medio Ambiente",
  "Ruido Acústico": "Sustentabilidad y Medio Ambiente",
  "Ruido Ambiental": "Sustentabilidad y Medio Ambiente",
  "Riles": "Sustentabilidad y Medio Ambiente",
  "Aguas Servidas": "Sustentabilidad y Medio Ambiente",
  "Reclamaciones": "Gestión de Contratos y Forense",
  "Revisión Contratos Obras": "Gestión de Contratos y Forense",
  "Revisión Contratos Operación": "Gestión de Contratos y Forense",
  "Revisión Ofertas": "Gestión de Contratos y Forense",
  "Revisión Bases": "Gestión de Contratos y Forense",
  "Auditoría Forense": "Gestión de Contratos y Forense",
  "Análisis Costo": "Gestión de Contratos y Forense",
  "Pérdida de productividad": "Gestión de Contratos y Forense",
  "Peritajes Forenses": "Gestión de Contratos y Forense",
  "Incendio Fuego": "Gestión de Contratos y Forense",
  "Riesgo": "Gestión de Contratos y Forense",
  "Estudio Vibraciones": "Gestión de Contratos y Forense",
  "Arquitectura": "Arquitectura y Edificación",
  "Elaboración Anteproyecto": "Arquitectura y Edificación",
  "Estudio de cabida": "Arquitectura y Edificación",
  "Estudio de Accesibilidad Universal": "Arquitectura y Edificación",
  "Patrimonio": "Arquitectura y Edificación",
  "Monumento Histórico": "Arquitectura y Edificación",
  "Diseño Cesfam": "Arquitectura y Edificación",
  "Rehabilitación Cesfam": "Arquitectura y Edificación",
  "Aeródromo": "Infraestructura y Estudios Básicos",
  "Aeropuerto": "Infraestructura y Estudios Básicos",
  "Aeroportuario": "Infraestructura y Estudios Básicos",
  "Túnel": "Infraestructura y Estudios Básicos",
  "Vialidad": "Infraestructura y Estudios Básicos",
  "Prefactibilidad": "Infraestructura y Estudios Básicos",
  "Plan Inversional": "Infraestructura y Estudios Básicos",
  "Estudio Demanda": "Infraestructura y Estudios Básicos",
  "Estudio Básico": "Infraestructura y Estudios Básicos",
  "Obras de Emergencia": "Infraestructura y Estudios Básicos",
  "Riego": "Infraestructura y Estudios Básicos",
  "Ministerio de Vivienda": "Mandantes Clave",
  "Minvu": "Mandantes Clave",
  "Servicio de Vivienda": "Mandantes Clave",
  "Serviu": "Mandantes Clave",
  "Ministerio de Educación": "Mandantes Clave",
  "Mineduc": "Mandantes Clave",
  "Dirección Educación Pública": "Mandantes Clave",
  "Servicios Locales Educacionales": "Mandantes Clave",
  "Ministerio de Salud": "Mandantes Clave",
  "Servicio de Salud": "Mandantes Clave",
  "Dirección de Arquitectura": "Mandantes Clave",
  "Superintendencia de Infraestructura": "Mandantes Clave",
  "Metropolitana": "Mandantes Clave",
  "Regional": "Mandantes Clave"
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
        # Clean UI columns
        data_to_save.pop('Ver', None)
        data_to_save.pop('Guardar', None)
        data_to_save.pop('MontoStr', None)
        
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

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_summaries_for_range(start_date, end_date, ticket):
    """Fetch summaries. Cached for 30 mins."""
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
    """Fetch details. Cached for 1 hour."""
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
    """Robust Date Parsing."""
    if not date_input:
        return None
    if isinstance(date_input, datetime):
        return date_input
    
    date_str = str(date_input).strip()
    
    if "." in date_str and "T" in date_str:
        date_str = date_str.split(".")[0]

    formats = [
        "%Y-%m-%dT%H:%M:%S", # ISO Standard
        "%Y-%m-%d",
        "%d-%m-%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    return None

def safe_float(val):
    try:
        if val is None or val == "":
            return 0.0
        return float(val)
    except Exception:
        return 0.0

def format_chilean_currency(val):
    try:
        if not val: return "$0"
        return "${:,.0f}".format(val).replace(",", ".")
    except:
        return "$0"

def clean_text(text):
    """Capitalizes text nicely (Title Case)."""
    if not text:
        return ""
    return str(text).strip().title()

def parse_tender_data(raw_tender):
    code = raw_tender.get('CodigoExterno', 'N/A')
    comprador = raw_tender.get('Comprador', {})
    fechas = raw_tender.get('Fechas', {})
    
    link_url = f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}"
    monto = safe_float(raw_tender.get('MontoEstimado'))
    
    return {
        "CodigoExterno": code,
        "Link": link_url,
        "Nombre": clean_text(raw_tender.get('Nombre', 'Sin Nombre')), # Capitalized
        "Organismo": clean_text(comprador.get('NombreOrganismo', 'N/A')), # Capitalized
        "Unidad": clean_text(comprador.get('NombreUnidad', 'N/A')), # Capitalized
        "FechaPublicacion": parse_date(fechas.get('FechaPublicacion')),
        "FechaCierre": parse_date(fechas.get('FechaCierre')),
        "Estado": raw_tender.get('Estado', ''),
        "MontoEstimado": monto,
        "MontoStr": format_chilean_currency(monto),
        "Descripcion": raw_tender.get('Descripcion', '')
    }

def get_category_info(text):
    text_lower = text.lower()
    for keyword, cat in KEYWORD_MAPPING.items():
        if keyword.lower() in text_lower:
            return cat, keyword 
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
         st.caption(f"Filtro: {len(KEYWORD_MAPPING)} palabras.")

    # --- TABS ---
    tab_search, tab_detail, tab_saved = st.tabs(["🔍 Resultados", "📄 Detalle", "💾 Marcadores"])

    # --- FETCH LOGIC ---
    if search_clicked or "search_results" not in st.session_state:
        if isinstance(date_range, tuple):
            start_d = date_range[0]
            end_d = date_range[1] if len(date_range) > 1 else date_range[0]
        else:
            start_d = end_d = today

        with st.spinner(f"Obteniendo lista de licitaciones..."):
            summaries = fetch_summaries_for_range(start_d, end_d, ticket)
        
        filtered_candidates = []
        audit_log = [] # List to store ALL fetched items for CSV
        
        # DEBUG COUNTERS
        debug_stats = {
            "total_fetched": len(summaries),
            "passed_keyword": 0,
            "passed_date": 0
        }
        
        # Phase 1: Filter Logic & Audit Log
        for s in summaries:
            full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
            cat, match_kw = get_category_info(full_text)
            c_date = parse_date(s.get('FechaCierre'))
            
            # Audit Record (Default: Rejected)
            log_entry = {
                "CodigoExterno": s.get('CodigoExterno'),
                "Nombre": s.get('Nombre'),
                "FechaCierre": s.get('FechaCierre'),
                "Estado Filtro": "Rechazado",
                "Motivo Rechazo": "Sin Match Palabras Clave",
                "Palabra Clave": ""
            }

            if cat:
                debug_stats["passed_keyword"] += 1
                log_entry["Palabra Clave"] = match_kw
                
                if is_date_valid(c_date):
                    debug_stats["passed_date"] += 1
                    # Accepted
                    s['_cat'] = cat
                    s['_kw'] = match_kw 
                    filtered_candidates.append(s)
                    
                    log_entry["Estado Filtro"] = "Aceptado"
                    log_entry["Motivo Rechazo"] = ""
                else:
                    log_entry["Motivo Rechazo"] = "Fecha Cierre Vencida"
            
            audit_log.append(log_entry)
        
        st.session_state['debug_stats'] = debug_stats
        st.session_state['audit_log'] = audit_log # Store for CSV download
        
        # Phase 2: Fetch Details
        final_data = []
        if filtered_candidates:
            info_ph = st.empty()
            info_ph.info(f"Analizando {len(filtered_candidates)} licitaciones potenciales...")
            
            prog = st.progress(0)
            total_cands = len(filtered_candidates)
            
            for idx, summary in enumerate(filtered_candidates):
                code = summary.get('CodigoExterno')
                detail = fetch_full_detail(code, ticket)
                
                if detail:
                    parsed = parse_tender_data(detail)
                    if is_date_valid(parsed['FechaCierre']):
                        parsed['Categoría'] = summary['_cat']
                        parsed['Palabra Clave'] = summary['_kw']
                        final_data.append(parsed)
                
                prog.progress((idx + 1) / total_cands)
                time.sleep(0.05)
                
            prog.empty()
            info_ph.empty()
        
        df = pd.DataFrame(final_data)
        st.session_state.search_results = df

    # --- TAB 1: RESULTS ---
    with tab_search:
        if "search_results" in st.session_state and not st.session_state.search_results.empty:
            df_results = st.session_state.search_results.copy()
            
            if "Ver" not in df_results.columns:
                df_results.insert(0, "Ver", False)
            if "Guardar" not in df_results.columns:
                df_results.insert(1, "Guardar", False)
            
            df_results["Web"] = df_results["Link"]
            
            # MODERNIZED COLUMN ORDER & WIDTHS
            # Nombre, Organismo, Unidad are now Capitalized by the parser
            cols_order = [
                "Web", "CodigoExterno", 
                "Nombre", "Organismo", "Unidad",
                "Categoría", "Palabra Clave", 
                "FechaPublicacion", "FechaCierre", "MontoStr",
                "Guardar", "Ver"
            ]

            st.info("💡 Resultados cargados. Las acciones están a la derecha.")

            edited_df = st.data_editor(
                df_results,
                column_order=cols_order,
                column_config={
                    "Web": st.column_config.LinkColumn(
                        "Web", display_text="🔗", width="small"
                    ),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="small"),
                    "Nombre": st.column_config.TextColumn("Nombre", width="large"),
                    "Organismo": st.column_config.TextColumn("Organismo", width="medium"),
                    "Unidad": st.column_config.TextColumn("Unidad", width="medium"),
                    "Categoría": st.column_config.TextColumn("Categoría", width="medium"),
                    "Palabra Clave": st.column_config.TextColumn("Match", width="small"),
                    "FechaPublicacion": st.column_config.DateColumn(
                        "Publicado", format="D MMM YYYY", width="medium"
                    ),
                    "FechaCierre": st.column_config.DateColumn(
                        "Cierre", format="D MMM YYYY", width="medium"
                    ),
                    "MontoStr": st.column_config.TextColumn(
                        "Monto", width="medium" # Simpler Header
                    ),
                    "Guardar": st.column_config.CheckboxColumn(
                        "Guardar", width="small", help="Guardar en DB"
                    ),
                    "Ver": st.column_config.CheckboxColumn(
                        "Ver", width="small", help="Ver Detalle"
                    )
                },
                disabled=["CodigoExterno", "Web", "Nombre", "Organismo", "Unidad", "Categoría", "Palabra Clave", "FechaPublicacion", "FechaCierre", "MontoStr"],
                hide_index=True,
                width="stretch",
                height=800
            )

            # --- HANDLE 'VER' SELECTION ---
            tenders_to_explore = edited_df[edited_df["Ver"] == True]
            if not tenders_to_explore.empty:
                st.session_state['selected_tender'] = tenders_to_explore.iloc[0].to_dict()
                if len(tenders_to_explore) > 1:
                    st.toast("⚠️ Visualizando primera selección.", icon="ℹ️")
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
                    st.warning("Marca la columna 'Guardar' para almacenar.")
        else:
            st.info("No hay resultados. Realiza una búsqueda.")

        # --- DEBUG / CSV SECTION ---
        if "debug_stats" in st.session_state and "audit_log" in st.session_state:
            stats = st.session_state["debug_stats"]
            audit_df = pd.DataFrame(st.session_state["audit_log"])
            
            with st.expander("🕵️ Depuración y Descarga de Datos (Audit Log)"):
                col_d1, col_d2, col_d3 = st.columns(3)
                col_d1.metric("Licitaciones API", stats["total_fetched"])
                col_d2.metric("Matches Keyword", stats["passed_keyword"])
                col_d3.metric("Visibles (Final)", len(st.session_state.search_results))
                
                st.write("### Descargar Registro Completo (CSV)")
                st.write("Descarga este archivo para revisar qué licitaciones fueron encontradas, cuáles fueron rechazadas y por qué.")
                
                csv = audit_df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="📥 Descargar Reporte de Filtros (CSV)",
                    data=csv,
                    file_name="licitaciones_debug_audit.csv",
                    mime="text/csv",
                )
                
                st.write("### Muestra de Datos de Auditoría")
                st.dataframe(audit_df.head(10), use_container_width=True)


    # --- TAB 2: DETAILS ---
    with tab_detail:
        if 'selected_tender' in st.session_state:
            row_data = st.session_state['selected_tender']
            
            st.header(row_data["Nombre"])
            st.caption(f"ID: {row_data['CodigoExterno']} | Estado: {row_data['Estado']}")
            
            st.markdown(f"**Categoría:** `{row_data.get('Categoría', 'N/A')}`")
            st.markdown(f"**Palabra Clave:** `{row_data.get('Palabra Clave', 'N/A')}`")

            st.divider()

            d_col1, d_col2, d_col3 = st.columns(3)
            with d_col1:
                st.metric("Organismo", row_data["Organismo"])
                st.metric("Unidad", row_data["Unidad"])
            with d_col2:
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
                width="stretch"
            )
            
            col_del, _ = st.columns([1, 3])
            with col_del:
                code_to_del = st.selectbox("Eliminar marcador:", df_saved['codigo_externo'])
                if st.button("🗑️ Borrar"):
                    delete_tender_from_db(code_to_del)
                    st.rerun()

if __name__ == "__main__":
    main()
