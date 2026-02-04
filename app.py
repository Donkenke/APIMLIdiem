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
DB_FILE = "licitaciones_v8.db" 
ITEMS_PER_LOAD = 50 
MAX_WORKERS = 5 

# --- KEYWORDS ---
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
        for k in ['Guardar','Ignorar','MontoStr','EstadoTiempo','EsNuevo','Web']: 
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

def restore_tender(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM ignorados WHERE codigo_externo = ?", (code,))
    conn.commit(); conn.close()

# --- API ---
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
    
    if 'visible_rows' not in st.session_state:
        st.session_state.visible_rows = ITEMS_PER_LOAD

    ticket = st.secrets.get("MP_TICKET")
    st.title("⚡ Monitor de Licitaciones Turbo")
    
    if not ticket: st.warning("Falta Ticket (MP_TICKET)"); st.stop()

    # --- HEADER: Date (Left) | Filters (Right) ---
    c_head1, c_spacer, c_head2 = st.columns([1.5, 1.5, 2.5])
    
    with c_head1:
        today = datetime.now()
        dr = st.date_input("Rango de Consulta", (today - timedelta(days=15), today), max_value=today, format="DD/MM/YYYY")
        if st.button("🔄 Buscar Datos", type="primary"):
            st.cache_data.clear()
            if 'search_results' in st.session_state: del st.session_state['search_results']
            st.session_state.visible_rows = ITEMS_PER_LOAD
            st.rerun()

    with c_head2:
        c_f1, c_f2 = st.columns(2)

    t_res, t_audit, t_sav = st.tabs(["🔍 Resultados", "🕵️ Auditoría", "💾 Guardados"])

    # --- LOGIC ---
    if 'search_results' not in st.session_state:
        if isinstance(dr, tuple): start, end = dr[0], dr[1] if len(dr)>1 else dr[0]
        else: start = end = dr
        
        with st.spinner("Descargando resúmenes..."):
            raw_items, fetch_errors = fetch_summaries_raw(start, end, ticket)
        
        if fetch_errors: st.warning(f"Errores conexión: {len(fetch_errors)}")

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
                is_new = False
                if code not in seen:
                    is_new = True
                    new_seen_ids.append(code)
                
                item['_cat'], item['_kw'], item['_is_new'] = cat, kw, is_new
                candidates.append(item)
                audit_logs.append({"ID": code, "Estado": "Candidato"})
            else:
                audit_logs.append({"ID": code, "Estado": "No Keyword"})

        mark_as_seen(new_seen_ids)

        # Fetch Details
        cached = get_cached_details([c['CodigoExterno'] for c in candidates])
        to_fetch = [c['CodigoExterno'] for c in candidates if c['CodigoExterno'] not in cached]
        
        if to_fetch:
            status = st.empty()
            status.text(f"Bajando {len(to_fetch)} detalles...")
            tasks = [(code, ticket) for code in to_fetch]
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
                future_to_code = {exe.submit(fetch_detail_worker, t): t[0] for t in tasks}
                for future in concurrent.futures.as_completed(future_to_code):
                    c_code, c_data = future.result()
                    if c_data:
                        save_cache(c_code, c_data)
                        cached[c_code] = json.dumps(c_data)
            status.empty()

        final = []
        for cand in candidates:
            code = cand['CodigoExterno']
            det = json.loads(cached.get(code, "{}")) if code in cached else {}
            
            d_cierre = parse_date(det.get('Fechas', {}).get('FechaCierre'))
            if d_cierre and d_cierre < datetime.now(): continue 

            final.append({
                "CodigoExterno": code,
                "Web": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
                "Link": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
                "Nombre": det.get('Nombre','').title(),
                "Organismo": det.get('Comprador',{}).get('NombreOrganismo','').title(),
                "FechaPublicacion": parse_date(det.get('Fechas',{}).get('FechaPublicacion')),
                "FechaCierre": d_cierre,
                "MontoStr": format_clp(det.get('MontoEstimado',0)),
                "Descripcion": det.get('Descripcion',''),
                "Categoría": cand['_cat'],
                "Palabra Clave": cand['_kw'],
                "EsNuevo": cand['_is_new'],
                "Guardar": False,
                "Ignorar": False
            })
        
        st.session_state.search_results = pd.DataFrame(final)
        st.session_state.audit_data = pd.DataFrame(audit_logs)

    # --- TAB RESULTADOS ---
    with t_res:
        if 'search_results' in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            df = df.sort_values("FechaPublicacion", ascending=False)

            # Filter Population
            with c_f1:
                cat_sel = st.multiselect("Categoría", options=sorted(df["Categoría"].unique()), label_visibility="collapsed", placeholder="Filtrar Categoría...")
            with c_f2:
                kw_sel = st.multiselect("Keywords", options=sorted(df["Palabra Clave"].unique()), label_visibility="collapsed", placeholder="Filtrar Keyword...")

            if cat_sel: df = df[df["Categoría"].isin(cat_sel)]
            if kw_sel: df = df[df["Palabra Clave"].isin(kw_sel)]

            total_rows = len(df)
            visible = st.session_state.visible_rows
            df_visible = df.iloc[:visible]

            # --- TABLE ---
            # ENABLED SELECTION (on_select="rerun") so index column appears and triggers sidebar
            edited_df = st.data_editor(
                df_visible,
                column_order=["Web","CodigoExterno","Nombre","Organismo","FechaPublicacion","FechaCierre","Categoría","Palabra Clave","EsNuevo","Guardar","Ignorar"],
                column_config={
                    "Web": st.column_config.LinkColumn("URL", display_text="🌐", width="small"),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="small", disabled=True),
                    "Nombre": st.column_config.TextColumn("Nombre Licitación", width="large", disabled=True),
                    "Organismo": st.column_config.TextColumn("Organismo", width="medium", disabled=True),
                    "FechaPublicacion": st.column_config.DateColumn("Publicado", format="DD/MM/YY", disabled=True),
                    "FechaCierre": st.column_config.DateColumn("Cierre", format="DD/MM/YY", disabled=True),
                    "EsNuevo": st.column_config.CheckboxColumn("¿Nuevo?", disabled=True, width="small"),
                    "Categoría": st.column_config.TextColumn("Categoría", width="small", disabled=True),
                    "Palabra Clave": st.column_config.TextColumn("Keyword", width="small", disabled=True),
                    "Guardar": st.column_config.CheckboxColumn("💾", width="small", default=False),
                    "Ignorar": st.column_config.CheckboxColumn("❌", width="small", default=False),
                },
                hide_index=True, # Hides numbers (0,1,2) but KEEPS the selection column due to on_select
                on_select="rerun", # CRITICAL: This enables the selection mechanism
                selection_mode="single-row",
                height=600,
                key="editor_main"
            )

            # --- SIDEBAR TRIGGER ---
            # Capture selection from the editor
            if edited_df and "selection" in st.session_state.editor_main:
                sel_rows = st.session_state.editor_main["selection"]["rows"]
                if sel_rows:
                    idx = sel_rows[0]
                    # Map back to data source
                    st.session_state['selected_tender'] = df_visible.iloc[idx].to_dict()

            # --- ACTION BUTTONS ---
            c_btn1, c_btn2, c_more = st.columns([1, 1, 3])
            
            with c_btn1:
                to_save = edited_df[edited_df["Guardar"]]
                if not to_save.empty:
                    if st.button(f"💾 Guardar ({len(to_save)})", type="primary"):
                        count = 0
                        for _, row in to_save.iterrows():
                            if save_tender(row.to_dict()): count += 1
                        st.toast(f"{count} guardados.", icon="✅")
                        time.sleep(1); st.rerun()

            with c_btn2:
                to_ignore = edited_df[edited_df["Ignorar"]]
                if not to_ignore.empty:
                    if st.button(f"❌ Eliminar ({len(to_ignore)})"):
                        for _, row in to_ignore.iterrows():
                            ignore_tender(row['CodigoExterno'])
                        st.toast(f"{len(to_ignore)} eliminados.", icon="🗑️")
                        st.cache_data.clear(); del st.session_state['search_results']
                        st.rerun()

            with c_more:
                if visible < total_rows:
                    if st.button("⬇️ Cargar más resultados...", use_container_width=True):
                        st.session_state.visible_rows += ITEMS_PER_LOAD
                        st.rerun()
        else:
            st.info("Sin resultados.")

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📋 Detalle")
        if 'selected_tender' in st.session_state:
            d = st.session_state['selected_tender']
            if d.get('EsNuevo'): st.success("✨ Nueva detección")
            
            st.subheader(d['Nombre'])
            st.write(f"**ID:** {d['CodigoExterno']}")
            st.write(f"**Org:** {d['Organismo']}")
            st.write(f"**Cierre:** {d['FechaCierre']}")
            st.write(f"**Monto:** {d.get('MontoStr','-')}")
            st.caption(d.get('Descripcion',''))
            st.link_button("Ir a Mercado Público 🌐", d['Link'], use_container_width=True)
            
            c_s1, c_s2 = st.columns(2)
            if c_s1.button("💾 Guardar", key="sb_save"):
                if save_tender(d): st.toast("Guardado")
            if c_s2.button("🚫 Ocultar", key="sb_ign"):
                ignore_tender(d['CodigoExterno'])
                st.toast("Ocultado")
        else:
            st.info("Selecciona una fila (casilla izquierda) para ver detalles.")
        
        st.divider()
        with st.expander("🛡️ Lista Negra"):
            ign = get_ignored_set()
            if ign:
                s = st.selectbox("Restaurar ID", list(ign))
                if st.button("Restaurar"):
                    restore_tender(s); st.rerun()
            else: st.write("Vacía")

    # --- SAVED ---
    with t_sav:
        st.dataframe(get_saved(), use_container_width=True, hide_index=True)
    
    with t_audit:
        if 'audit_data' in st.session_state: st.dataframe(st.session_state.audit_data, use_container_width=True)

if __name__ == "__main__":
    main()
