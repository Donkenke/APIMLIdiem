import streamlit as st
import pandas as pd
import requests
import urllib3
import json
import sqlite3
import time
import concurrent.futures
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="Monitor Licitaciones", page_icon="⚡", layout="wide")

# Constants
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
DB_FILE = "licitaciones_v6.db" 
ITEMS_PER_LOAD = 50 # How many items to add when clicking "Load More"
MAX_WORKERS = 5 

# --- KEYWORD CONFIGURATION (Same as before) ---
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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS marcadores (
        codigo_externo TEXT PRIMARY KEY,
        nombre TEXT,
        organismo TEXT,
        fecha_cierre TEXT,
        url TEXT,
        raw_data TEXT,
        fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ignorados (
        codigo_externo TEXT PRIMARY KEY,
        fecha_ignorado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cache_detalles (
        codigo_externo TEXT PRIMARY KEY,
        json_data TEXT,
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # New table to track what we have already seen to mark "New" items
    c.execute('''CREATE TABLE IF NOT EXISTS historial_vistas (
        codigo_externo TEXT PRIMARY KEY,
        fecha_primer_avistamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit(); conn.close()

# --- HELPERS ---
def get_ignored_set():
    try:
        conn = sqlite3.connect(DB_FILE)
        res = set(pd.read_sql("SELECT codigo_externo FROM ignorados", conn)['codigo_externo'])
        conn.close()
        return res
    except: return set()

def get_seen_set():
    try:
        conn = sqlite3.connect(DB_FILE)
        res = set(pd.read_sql("SELECT codigo_externo FROM historial_vistas", conn)['codigo_externo'])
        conn.close()
        return res
    except: return set()

def mark_as_seen(codigos):
    if not codigos: return
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.executemany("INSERT OR IGNORE INTO historial_vistas (codigo_externo) VALUES (?)", [(code,) for code in codigos])
        conn.commit(); conn.close()
    except: pass

def ignore_tender(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR REPLACE INTO ignorados (codigo_externo) VALUES (?)", (code,))
    conn.commit(); conn.close()

def save_tender(data):
    try:
        clean = data.copy()
        # Clean keys that are not needed in DB
        for k in ['Guardar','Ignorar','MontoStr','EstadoTiempo','EsNuevo']: 
            clean.pop(k, None)
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR REPLACE INTO marcadores (codigo_externo, nombre, organismo, fecha_cierre, url, raw_data) VALUES (?,?,?,?,?,?)",
                     (clean['CodigoExterno'], clean['Nombre'], clean['Organismo'], str(clean['FechaCierre']), clean['Link'], json.dumps(clean, default=str)))
        conn.commit(); conn.close()
        return True
    except: return False

def get_saved():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM marcadores ORDER BY fecha_guardado DESC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

# --- API & SEARCH ---
def get_api_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"})
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503], allowed_methods=["GET"])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def get_cached_details(codigos):
    if not codigos: return {}
    conn = sqlite3.connect(DB_FILE)
    placeholders = ','.join(['?']*len(codigos))
    try:
        df = pd.read_sql(f"SELECT codigo_externo, json_data FROM cache_detalles WHERE codigo_externo IN ({placeholders})", conn, params=codigos)
        conn.close()
        return dict(zip(df['codigo_externo'], df['json_data']))
    except: return {}

def save_cache(code, data):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR REPLACE INTO cache_detalles (codigo_externo, json_data) VALUES (?,?)", (code, json.dumps(data)))
        conn.commit(); conn.close()
    except: pass

@st.cache_data(ttl=300) 
def fetch_summaries_raw(start_date, end_date, ticket):
    results = []
    errors = []
    delta = (end_date - start_date).days + 1
    session = get_api_session()
    
    for i in range(delta):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%d%m%Y")
        url = f"{BASE_URL}/licitaciones.json?fecha={d_str}&ticket={ticket}"
        try:
            r = session.get(url, verify=False, timeout=15)
            if r.status_code == 200:
                js = r.json()
                items = js.get('Listado', [])
                for item in items: item['_fecha_origen'] = d_str 
                results.extend(items)
            else:
                errors.append(f"Fecha {d_str}: Error {r.status_code}")
        except Exception as e:
            errors.append(f"Fecha {d_str}: {str(e)}")
            
    return results, errors

def fetch_detail_worker(args):
    code, ticket = args
    try:
        session = get_api_session() 
        url = f"{BASE_URL}/licitaciones.json?codigo={code}&ticket={ticket}"
        r = session.get(url, verify=False, timeout=20)
        if r.status_code == 200:
            js = r.json()
            if js.get('Listado'):
                return code, js['Listado'][0]
    except: pass
    return code, None

def parse_date(d):
    if not d: return None
    if isinstance(d, datetime): return d
    s = str(d).strip().split('.')[0]
    for f in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"]:
        try: return datetime.strptime(s, f)
        except: continue
    return None

def get_cat(txt):
    if not txt: return None, None
    tl = txt.lower()
    for kw, cat in KEYWORD_MAPPING.items():
        if kw.lower() in tl: return cat, kw
    return None, None

def format_clp(v):
    try: return "${:,.0f}".format(float(v)).replace(",", ".")
    except: return "$0"

# --- MAIN ---
def main():
    init_db()
    
    # Visible rows state for "Load More" logic
    if 'visible_rows' not in st.session_state:
        st.session_state.visible_rows = ITEMS_PER_LOAD

    ticket = st.secrets.get("MP_TICKET")
    st.title("⚡ Monitor de Licitaciones Turbo")
    
    if not ticket: st.warning("Falta Ticket (MP_TICKET)"); st.stop()

    # --- NEW LAYOUT: Header & Filters ---
    # Col 1: Dates (No Border) | Col 2: Filters (Right Aligned, Compact)
    c_dates, c_spacer, c_filters = st.columns([1.5, 0.5, 3])
    
    with c_dates:
        today = datetime.now()
        dr = st.date_input("Rango de Consulta", (today - timedelta(days=15), today), max_value=today, format="DD/MM/YYYY")
    
    with c_filters:
        # Placeholder for filters that will populate after search
        # We define containers here so they appear in the layout, but fill them later
        c_f1, c_f2 = st.columns(2)

    # Search Button in a thin row below
    if st.button("🔄 Buscar Datos", type="primary"):
        st.cache_data.clear()
        if 'search_results' in st.session_state: del st.session_state['search_results']
        st.session_state.visible_rows = ITEMS_PER_LOAD # Reset pagination
        st.rerun()

    t_res, t_audit, t_sav = st.tabs(["🔍 Resultados", "🕵️ Auditoría", "💾 Guardados"])

    # --- LOGIC ---
    if 'search_results' not in st.session_state:
        if isinstance(dr, tuple): start, end = dr[0], dr[1] if len(dr)>1 else dr[0]
        else: start = end = dr
        
        with st.spinner("Descargando resúmenes..."):
            raw_items, fetch_errors = fetch_summaries_raw(start, end, ticket)
        
        if fetch_errors:
            with st.expander("Ver errores de descarga", expanded=False):
                st.write(fetch_errors)

        # Audit & Filter
        audit_logs = []
        candidates = []
        ignored = get_ignored_set()
        seen = get_seen_set()
        new_seen_ids = []
        
        for item in raw_items:
            code = item.get('CodigoExterno')
            if code in ignored:
                audit_logs.append({"ID": code, "Estado": "Ignorado"})
                continue

            full_txt = f"{item.get('Nombre','')} {item.get('Descripcion','')}"
            cat, kw = get_cat(full_txt)
            
            if cat:
                # Check New Status
                # Logic: If ID is NOT in 'seen' set, it is new for this user
                is_new = False
                if code not in seen:
                    is_new = True
                    new_seen_ids.append(code)
                
                item['_cat'], item['_kw'], item['_is_new'] = cat, kw, is_new
                candidates.append(item)
                audit_logs.append({"ID": code, "Estado": "Candidato"})
            else:
                audit_logs.append({"ID": code, "Estado": "No Keyword"})

        # Mark new items as seen in DB so they aren't "new" next time
        mark_as_seen(new_seen_ids)

        # Fetch Details
        cached = get_cached_details([c['CodigoExterno'] for c in candidates])
        to_fetch = [c['CodigoExterno'] for c in candidates if c['CodigoExterno'] not in cached]
        
        if to_fetch:
            status_text = st.empty()
            status_text.text(f"Descargando {len(to_fetch)} detalles...")
            tasks = [(code, ticket) for code in to_fetch]
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                future_to_code = {exe.submit(fetch_detail_worker, t): t[0] for t in tasks}
                for future in concurrent.futures.as_completed(future_to_code):
                    c_code, c_data = future.result()
                    if c_data:
                        save_cache(c_code, c_data)
                        cached[c_code] = json.dumps(c_data)
            status_text.empty()

        # Build Final DF
        final = []
        for cand in candidates:
            code = cand['CodigoExterno']
            det = json.loads(cached.get(code, "{}")) if code in cached else {}
            
            d_cierre = parse_date(det.get('Fechas', {}).get('FechaCierre'))
            if d_cierre and d_cierre < datetime.now(): continue # Skip expired

            final.append({
                "CodigoExterno": code,
                "Link": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
                "Nombre": det.get('Nombre','').title(),
                "Organismo": det.get('Comprador',{}).get('NombreOrganismo','').title(),
                "FechaPublicacion": parse_date(det.get('Fechas',{}).get('FechaPublicacion')),
                "FechaCierre": d_cierre,
                "MontoStr": format_clp(det.get('MontoEstimado',0)),
                "Descripcion": det.get('Descripcion',''),
                "Categoría": cand['_cat'],
                "Palabra Clave": cand['_kw'],
                "EsNuevo": cand['_is_new'] # Boolean for the checkbox column
            })
        
        st.session_state.search_results = pd.DataFrame(final)
        st.session_state.audit_data = pd.DataFrame(audit_logs)

    # --- RENDER TAB 1 ---
    with t_res:
        if 'search_results' in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            df = df.sort_values("FechaPublicacion", ascending=False)

            # --- POPULATE FILTERS (Right Side) ---
            with c_f1:
                cat_sel = st.multiselect("Categoría", options=sorted(df["Categoría"].unique()), label_visibility="collapsed", placeholder="Filtrar Categoría...")
            with c_f2:
                kw_sel = st.multiselect("Keywords", options=sorted(df["Palabra Clave"].unique()), label_visibility="collapsed", placeholder="Filtrar Keyword...")

            if cat_sel: df = df[df["Categoría"].isin(cat_sel)]
            if kw_sel: df = df[df["Palabra Clave"].isin(kw_sel)]

            # --- LOAD MORE LOGIC ---
            total_rows = len(df)
            visible = st.session_state.visible_rows
            df_visible = df.iloc[:visible]

            # Table
            # Note: We use LinkColumn for the web link and CheckboxColumn for "EsNuevo"
            event = st.dataframe(
                df_visible,
                column_order=["Link","CodigoExterno","Nombre","Organismo","FechaPublicacion","FechaCierre","Categoría","Palabra Clave","EsNuevo"],
                column_config={
                    "Link": st.column_config.LinkColumn("", display_text="🔗", width="small"),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="small"),
                    "Nombre": st.column_config.TextColumn("Nombre Licitación", width="large"),
                    "FechaPublicacion": st.column_config.DateColumn("Publicado", format="DD/MM/YY"),
                    "FechaCierre": st.column_config.DateColumn("Cierre", format="DD/MM/YY"),
                    "EsNuevo": st.column_config.CheckboxColumn("¿Nuevo?", default=False, width="small"), # Last Column Check
                },
                hide_index=True,
                height=600,
                selection_mode="single-row",
                on_select="rerun"
            )

            # Load More Button
            if visible < total_rows:
                st.write(f"Mostrando {visible} de {total_rows} licitaciones.")
                if st.button("⬇️ Cargar más resultados...", use_container_width=True):
                    st.session_state.visible_rows += ITEMS_PER_LOAD
                    st.rerun()

            # Selection Logic
            if event.selection and event.selection["rows"]:
                idx = event.selection["rows"][0]
                st.session_state['selected_tender'] = df_visible.iloc[idx].to_dict()
        else:
            st.info("Sin resultados pendientes.")

    # --- SIDEBAR DETAILS ---
    with st.sidebar:
        st.header("📋 Detalle")
        if 'selected_tender' in st.session_state:
            d = st.session_state['selected_tender']
            
            # Badge for New
            if d.get('EsNuevo'): st.success("✨ ¡Detectada hoy por primera vez!")
            
            st.subheader(d['Nombre'])
            st.caption(f"ID: {d['CodigoExterno']}")
            st.write(f"**Organismo:** {d['Organismo']}")
            st.write(f"**Cierre:** {d['FechaCierre']}")
            st.write(f"**Monto:** {d.get('MontoStr','-')}")
            
            st.markdown("---")
            st.caption("Descripción:")
            st.text_area("", d.get('Descripcion',''), height=150, disabled=True)
            
            st.link_button("🌍 Ver en Mercado Público", d['Link'], use_container_width=True)
            
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("💾 Guardar"):
                if save_tender(d): st.toast("Guardado")
            if c_s2.button("🚫 Ocultar"):
                ignore_tender(d['CodigoExterno'])
                st.toast("Ocultado")
        else:
            st.info("Selecciona una fila para ver detalles.")

    # --- AUDIT TAB ---
    with t_audit:
        if 'audit_data' in st.session_state:
            st.dataframe(st.session_state.audit_data, use_container_width=True)

    # --- SAVED TAB ---
    with t_sav:
        st.dataframe(get_saved(), use_container_width=True)

if __name__ == "__main__":
    main()
