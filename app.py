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
        for k in ['Ver', 'Guardar', 'MontoStr', 'EstadoTiempo']:
            data_to_save.pop(k, None)
        
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
    if not date_input: return None
    if isinstance(date_input, datetime): return date_input
    
    date_str = str(date_input).strip()
    if "." in date_str and "T" in date_str:
        date_str = date_str.split(".")[0]

    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"]:
        try: return datetime.strptime(date_str, fmt)
        except ValueError: continue
    return None

def safe_float(val):
    try: return float(val) if val else 0.0
    except: return 0.0

def format_chilean_currency(val):
    try: return "${:,.0f}".format(val).replace(",", ".") if val else "$0"
    except: return "$0"

def clean_text(text):
    if not text: return ""
    return str(text).strip().title()

def parse_tender_data(raw_tender):
    code = raw_tender.get('CodigoExterno', 'N/A')
    comprador = raw_tender.get('Comprador', {})
    fechas = raw_tender.get('Fechas', {})
    
    return {
        "CodigoExterno": code,
        "Link": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
        "Nombre": clean_text(raw_tender.get('Nombre', 'Sin Nombre')),
        "Organismo": clean_text(comprador.get('NombreOrganismo', 'N/A')),
        "Unidad": clean_text(comprador.get('NombreUnidad', 'N/A')),
        "FechaPublicacion": parse_date(fechas.get('FechaPublicacion')),
        "FechaCierre": parse_date(fechas.get('FechaCierre')),
        "Estado": raw_tender.get('Estado', ''),
        "MontoEstimado": safe_float(raw_tender.get('MontoEstimado')),
        "Descripcion": raw_tender.get('Descripcion', '')
    }

def get_category_info(text):
    text_lower = text.lower()
    for keyword, cat in KEYWORD_MAPPING.items():
        if keyword.lower() in text_lower:
            return cat, keyword 
    return None, None

def is_date_valid(date_obj):
    # CORREGIDO: Si la fecha es None, asumimos True (Vigente) para no descartar prematuramente
    # licitaciones cuyo resumen tiene fecha nula pero el detalle sí la tiene.
    if not date_obj: return True 
    return date_obj >= datetime.now()

# --- MAIN APP UI ---

def main():
    init_db()
    ticket = get_ticket()
    
    st.title("🏛️ Buscador Licitaciones")
    
    if not ticket:
        st.warning("⚠️ Ticket no encontrado.")
        st.stop()

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        today = datetime.now()
        ten_days_ago = today - timedelta(days=10)
        date_range = st.date_input("Rango de Fechas", value=(ten_days_ago, today), max_value=today, format="DD/MM/YYYY")
        show_closed = st.checkbox("Mostrar historial (incluir cerradas)", value=False)
    
    with col2:
        st.write(""); st.write("")
        search_clicked = st.button("🔄 Buscar Datos", type="primary", use_container_width=True)

    with col3:
         st.write(""); st.write("")
         st.caption(f"Filtro: {len(KEYWORD_MAPPING)} palabras.")

    tab_search, tab_detail, tab_saved = st.tabs(["🔍 Resultados", "📄 Detalle", "💾 Marcadores"])

    if search_clicked or "search_results" not in st.session_state:
        if isinstance(date_range, tuple): start_d, end_d = date_range[0], date_range[1] if len(date_range) > 1 else date_range[0]
        else: start_d = end_d = today

        with st.spinner(f"Obteniendo lista de licitaciones..."):
            summaries = fetch_summaries_for_range(start_d, end_d, ticket)
        
        filtered_candidates = []
        audit_log = [] 
        debug_stats = {"total_fetched": len(summaries), "passed_keyword": 0, "passed_date": 0}
        
        # --- PHASE 1: FILTERING ---
        for s in summaries:
            full_text = f"{s.get('Nombre', '')} {s.get('Descripcion', '')}"
            cat, match_kw = get_category_info(full_text)
            c_date = parse_date(s.get('FechaCierre')) # Puede ser None aquí
            
            # Lógica corregida: 
            # Si c_date es None (API falla en resumen), is_date_valid devuelve True para no matar el proceso.
            # La validación final real se hace en Phase 2 con el detalle.
            is_vigente_preliminar = is_date_valid(c_date)
            
            log_entry = {
                "CodigoExterno": s.get('CodigoExterno'), "Nombre": s.get('Nombre'), 
                "FechaCierre": s.get('FechaCierre'), "Estado Filtro": "Rechazado", "Motivo": "Sin Match", "Palabra": ""
            }

            if cat:
                debug_stats["passed_keyword"] += 1
                log_entry["Palabra"] = match_kw
                
                if is_vigente_preliminar or show_closed:
                    if is_vigente_preliminar: debug_stats["passed_date"] += 1
                    s['_cat'], s['_kw'] = cat, match_kw
                    filtered_candidates.append(s)
                    log_entry["Estado Filtro"] = "Aceptado (Preliminar)"
                    log_entry["Motivo"] = ""
                else:
                    log_entry["Motivo"] = "Fecha Vencida (Resumen)"
            
            audit_log.append(log_entry)
        
        st.session_state['debug_stats'] = debug_stats
        st.session_state['audit_log'] = audit_log 
        
        # --- PHASE 2: DETAILS ---
        final_data = []
        if filtered_candidates:
            info_ph = st.empty()
            info_ph.info(f"Procesando {len(filtered_candidates)} licitaciones detectadas...")
            prog = st.progress(0)
            
            for idx, summary in enumerate(filtered_candidates):
                detail = fetch_full_detail(summary.get('CodigoExterno'), ticket)
                if detail:
                    parsed = parse_tender_data(detail)
                    
                    # Validación Final de Fecha con datos reales
                    c_date_real = parsed['FechaCierre']
                    real_vigente = True
                    if c_date_real:
                        real_vigente = c_date_real >= datetime.now()
                    
                    if real_vigente or show_closed:
                        parsed['Categoría'] = summary['_cat']
                        parsed['Palabra Clave'] = summary['_kw']
                        parsed['MontoStr'] = format_chilean_currency(parsed['MontoEstimado'])
                        
                        # Estado visual
                        if not c_date_real:
                            parsed['EstadoTiempo'] = "⚠️ Sin Fecha"
                        elif real_vigente:
                            parsed['EstadoTiempo'] = "🟢 Vigente"
                        else:
                            parsed['EstadoTiempo'] = "🔴 Cerrada"
                            
                        final_data.append(parsed)
                
                prog.progress((idx + 1) / len(filtered_candidates))
                time.sleep(0.05)
            
            prog.empty()
            info_ph.empty()
        
        st.session_state.search_results = pd.DataFrame(final_data)

    with tab_search:
        if "search_results" in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            if "Ver" not in df.columns: df.insert(0, "Ver", False)
            if "Guardar" not in df.columns: df.insert(1, "Guardar", False)
            df["Web"] = df["Link"]
            
            cols = ["Web", "CodigoExterno", "Nombre", "Organismo", "Unidad", "EstadoTiempo", 
                    "Categoría", "Palabra Clave", "FechaPublicacion", "FechaCierre", "MontoStr", "Guardar", "Ver"]
            
            st.info(f"💡 Mostrando {len(df)} resultados.")
            
            edited = st.data_editor(
                df, column_order=cols,
                column_config={
                    "Web": st.column_config.LinkColumn("Web", display_text="🔗", width="small"),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="small"),
                    "Nombre": st.column_config.TextColumn("Nombre", width="large"),
                    "Organismo": st.column_config.TextColumn("Organismo", width="medium"),
                    "Unidad": st.column_config.TextColumn("Unidad", width="medium"),
                    "EstadoTiempo": st.column_config.TextColumn("Estado", width="small"),
                    "Categoría": st.column_config.TextColumn("Categoría", width="medium"),
                    "Palabra Clave": st.column_config.TextColumn("Match", width="small"),
                    "FechaPublicacion": st.column_config.DateColumn("Publicado", format="D MMM YYYY", width="medium"),
                    "FechaCierre": st.column_config.DateColumn("Cierre", format="D MMM YYYY", width="medium"),
                    "MontoStr": st.column_config.TextColumn("Monto", width="medium"),
                    "Guardar": st.column_config.CheckboxColumn("Guardar", width="small"),
                    "Ver": st.column_config.CheckboxColumn("Ver", width="small")
                },
                disabled=[c for c in cols if c not in ["Guardar", "Ver"]],
                hide_index=True, width="stretch", height=800
            )
            
            sel = edited[edited["Ver"]==True]
            if not sel.empty: st.session_state['selected_tender'] = sel.iloc[0].to_dict()
            
            if st.button("💾 Guardar Seleccionados"):
                save_cnt = sum([save_tender_to_db(row.to_dict()) for _, row in edited[edited["Guardar"]==True].iterrows()])
                if save_cnt: st.toast(f"✅ {save_cnt} guardadas.", icon="💾")
        else:
            st.info("No hay resultados. Intenta ampliar la fecha o activar el historial.")

        if "audit_log" in st.session_state:
            with st.expander("🕵️ Depuración y Auditoría"):
                st.download_button("📥 Descargar CSV", pd.DataFrame(st.session_state["audit_log"]).to_csv(index=False).encode('utf-8'), "audit.csv", "text/csv")
                st.dataframe(pd.DataFrame(st.session_state["audit_log"]).head(5))

    with tab_detail:
        if 'selected_tender' in st.session_state:
            d = st.session_state['selected_tender']
            st.header(d["Nombre"])
            st.caption(f"ID: {d['CodigoExterno']}")
            st.markdown(f"**Categoría:** `{d.get('Categoría')}` | **Match:** `{d.get('Palabra Clave')}`")
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("Organismo", d["Organismo"]); c1.metric("Unidad", d["Unidad"])
            
            pub = d["FechaPublicacion"]
            if isinstance(pub, str): pub = parse_date(pub)
            c2.metric("Publicado", pub.strftime("%d %b %Y") if pub else "N/A")
            
            close = d["FechaCierre"]
            if isinstance(close, str): close = parse_date(close)
            c3.metric("Cierre", close.strftime("%d %b %Y") if close else "N/A")
            
            st.divider()
            st.write(d["Descripcion"])
            st.markdown(f"[**🔗 Ver en MercadoPúblico**]({d['Link']})")

    with tab_saved:
        st.subheader("📚 Mis Marcadores")
        saved = get_saved_tenders()
        if not saved.empty:
            st.dataframe(saved, column_config={"url": st.column_config.LinkColumn("Link", display_text="🔗")}, hide_index=True, width="stretch")
            if st.button("🗑️ Borrar Marcador"):
                code = st.selectbox("ID a borrar", saved['codigo_externo'])
                if code: delete_tender_from_db(code); st.rerun()
        else:
            st.info("Sin guardados.")

if __name__ == "__main__":
    main()
