import streamlit as st
import pandas as pd
import requests
import urllib3
import json
import sqlite3
import time
import math
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Page setup
st.set_page_config(page_title="Monitor de Licitaciones Pro", page_icon="🏗️", layout="wide")

# Constants
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
DB_FILE = "licitaciones_v3.db" # Changed DB to force refresh structure
ITEMS_PER_PAGE = 50 

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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Marcadores
    c.execute('''CREATE TABLE IF NOT EXISTS marcadores (
        codigo_externo TEXT PRIMARY KEY,
        nombre TEXT,
        organismo TEXT,
        fecha_cierre TEXT,
        url TEXT,
        raw_data TEXT,
        fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Ignorados
    c.execute('''CREATE TABLE IF NOT EXISTS ignorados (
        codigo_externo TEXT PRIMARY KEY,
        fecha_ignorado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Cache Detalles
    c.execute('''CREATE TABLE IF NOT EXISTS cache_detalles (
        codigo_externo TEXT PRIMARY KEY,
        json_data TEXT,
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit(); conn.close()

# --- DB HELPERS ---
def get_ignored_set():
    try:
        conn = sqlite3.connect(DB_FILE)
        res = set(pd.read_sql("SELECT codigo_externo FROM ignorados", conn)['codigo_externo'])
        conn.close()
        return res
    except: return set()

def ignore_tender(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR REPLACE INTO ignorados (codigo_externo) VALUES (?)", (code,))
    conn.commit(); conn.close()

def restore_tender(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM ignorados WHERE codigo_externo = ?", (code,))
    conn.commit(); conn.close()

def save_tender(data):
    try:
        clean = data.copy()
        for k in ['Ver','Guardar','Ignorar','MontoStr','EstadoTiempo']: clean.pop(k, None)
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

def delete_saved(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM marcadores WHERE codigo_externo = ?", (code,))
    conn.commit(); conn.close()

# --- CACHE & API ---
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

def get_api_session():
    """Creates a robust session with Retries and User-Agent."""
    session = requests.Session()
    
    # 1. User Agent Spoofing (Looks like a Browser)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    })
    
    # 2. Retry Strategy (Handles 500, 502, 503 errors automatically)
    retry_strategy = Retry(
        total=3,  # Retry 3 times
        backoff_factor=1,  # Wait 1s, then 2s, etc.
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

@st.cache_data(ttl=300) 
def fetch_summaries_raw(start_date, end_date, ticket):
    results = []
    errors = []
    delta = (end_date - start_date).days + 1
    
    session = get_api_session() # Use robust session
    
    for i in range(delta):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%d%m%Y")
        url = f"{BASE_URL}/licitaciones.json?fecha={d_str}&ticket={ticket}"
        try:
            # Increased timeout slightly
            r = session.get(url, verify=False, timeout=15)
            if r.status_code == 200:
                js = r.json()
                items = js.get('Listado', [])
                for item in items: item['_fecha_origen'] = d_str 
                results.extend(items)
            else:
                errors.append(f"Error {r.status_code} en {d_str}")
        except Exception as e:
            errors.append(f"Fallo conexión en {d_str}: {str(e)}")
            
        # Small sleep between dates to avoid aggressive throttling
        time.sleep(0.3)
            
    return results, errors

def fetch_detail_live(code, ticket):
    try:
        session = get_api_session()
        url = f"{BASE_URL}/licitaciones.json?codigo={code}&ticket={ticket}"
        r = session.get(url, verify=False, timeout=15)
        if r.status_code == 200:
            js = r.json()
            if js.get('Listado'): return js['Listado'][0]
    except: pass
    return None

# --- UTILS ---
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
    if 'page_number' not in st.session_state: st.session_state.page_number = 1
    
    ticket = st.secrets.get("MP_TICKET")
    st.title("🏗️ Monitor de Licitaciones (Pro Audit)")
    
    if not ticket: st.warning("Falta Ticket"); st.stop()

    # Filters
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        today = datetime.now()
        # Default range: 15 days to ensure coverage
        dr = st.date_input("Rango", (today - timedelta(days=15), today), max_value=today, format="DD/MM/YYYY")
        show_closed = st.checkbox("Incluir Cerradas (Historial)", value=False)
    with c2:
        st.write(""); st.write("")
        # Clear cache button integration
        if st.button("🔄 Buscar (Forzar Recarga)", type="primary"):
            st.cache_data.clear()
            if 'search_results' in st.session_state: del st.session_state['search_results']
            st.rerun()
    with c3:
        st.metric("Keywords", len(KEYWORD_MAPPING))

    t_res, t_audit, t_sav = st.tabs(["🔍 Resultados", "🕵️ Auditoría (Todo)", "💾 Guardados"])

    # LOGIC
    if 'search_results' not in st.session_state:
        if isinstance(dr, tuple): start, end = dr[0], dr[1] if len(dr)>1 else dr[0]
        else: start = end = dr
        
        ignored_set = get_ignored_set()
        
        with st.spinner("Descargando resúmenes diarios..."):
            raw_items, fetch_errors = fetch_summaries_raw(start, end, ticket)
            
        if fetch_errors:
            st.error(f"Errores de conexión: {len(fetch_errors)}")
            with st.expander("Ver Errores"): st.write(fetch_errors)

        # AUDIT PIPELINE
        audit_logs = []
        candidates = []
        codes_needed = []

        # 1. First Pass (Summary Level)
        for item in raw_items:
            code = item.get('CodigoExterno')
            name = item.get('Nombre', '')
            desc = item.get('Descripcion', '')
            pub_date = item.get('FechaPublicacion', '')
            
            # Audit Object
            log = {
                "ID": code,
                "Nombre": name,
                "Publicado": pub_date,
                "Estado_Audit": "Desconocido",
                "Motivo": "",
                "Keyword_Found": ""
            }
            
            # Blacklist Check
            if code in ignored_set:
                log["Estado_Audit"] = "Oculto"
                log["Motivo"] = "Lista Negra"
                audit_logs.append(log)
                continue

            # Keyword Check
            full_txt = f"{name} {desc}"
            cat, kw = get_cat(full_txt)
            
            if not cat:
                log["Estado_Audit"] = "Descartado"
                log["Motivo"] = "Sin Keyword"
                audit_logs.append(log)
                continue
            
            log["Keyword_Found"] = kw
            
            # Date Check (Summary Level - Permissive)
            d_sum = parse_date(item.get('FechaCierre'))
            
            # We keep it if it's valid OR if it's None (API incomplete) OR if show_closed is True
            if show_closed or (d_sum is None) or (d_sum >= datetime.now()):
                item['_cat'] = cat
                item['_kw'] = kw
                candidates.append(item)
                codes_needed.append(code)
                log["Estado_Audit"] = "Candidato"
                log["Motivo"] = "Pasa Filtro Inicial"
            else:
                log["Estado_Audit"] = "Descartado"
                log["Motivo"] = f"Fecha Vencida (Resumen: {d_sum})"
            
            audit_logs.append(log)

        # 2. Second Pass (Detail Fetching)
        final_list = []
        
        if candidates:
            pbar = st.progress(0)
            status_txt = st.empty()
            
            # Bulk Cache Load
            cached_map = get_cached_details(codes_needed)
            
            for idx, cand in enumerate(candidates):
                code = cand['CodigoExterno']
                detail = None
                
                # Try Cache
                if code in cached_map:
                    try: detail = json.loads(cached_map[code])
                    except: pass
                
                # Try API
                if not detail:
                    detail = fetch_detail_live(code, ticket)
                    if detail: save_cache(code, detail)
                    time.sleep(0.1) # Throttled for safety
                
                # Update Audit based on Detail
                if detail:
                    d_cierre = parse_date(detail.get('Fechas', {}).get('FechaCierre'))
                    
                    # Final Date Decision
                    is_valid = False
                    if show_closed: is_valid = True
                    elif d_cierre and d_cierre >= datetime.now(): is_valid = True
                    
                    if is_valid:
                        # Build Final Row
                        row = {
                            "CodigoExterno": code,
                            "Link": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
                            "Nombre": str(detail.get('Nombre','')).title(),
                            "Organismo": str(detail.get('Comprador',{}).get('NombreOrganismo','')).title(),
                            "Unidad": str(detail.get('Comprador',{}).get('NombreUnidad','')).title(),
                            "FechaPublicacion": parse_date(detail.get('Fechas',{}).get('FechaPublicacion')),
                            "FechaCierre": d_cierre,
                            "MontoStr": format_clp(detail.get('MontoEstimado',0)),
                            "Descripcion": detail.get('Descripcion',''),
                            "Categoría": cand['_cat'],
                            "Palabra Clave": cand['_kw'],
                            "EstadoTiempo": "🟢 Vigente" if (d_cierre and d_cierre >= datetime.now()) else "🔴 Cerrada"
                        }
                        if not d_cierre: row["EstadoTiempo"] = "⚠️ Sin Fecha"
                        final_list.append(row)
                        
                        # Update Log
                        for l in audit_logs:
                            if l['ID'] == code: 
                                l['Estado_Audit'] = "VISIBLE"
                                l['Motivo'] = "Detalle OK"
                    else:
                        # Rejected by Detail Date
                        for l in audit_logs:
                            if l['ID'] == code: 
                                l['Estado_Audit'] = "Descartado"
                                l['Motivo'] = f"Vencida en Detalle ({d_cierre})"
                else:
                    # Detail fetch failed, keep audit as candidate but warn
                     for l in audit_logs:
                            if l['ID'] == code: 
                                l['Estado_Audit'] = "Error API"
                                l['Motivo'] = "No se pudo descargar detalle"

                pbar.progress((idx+1)/len(candidates))
                status_txt.caption(f"Verificando detalles {idx+1}/{len(candidates)}")
            
            pbar.empty(); status_txt.empty()

        # Save to Session
        st.session_state.search_results = pd.DataFrame(final_list)
        st.session_state.audit_data = pd.DataFrame(audit_logs)
        st.session_state.page_number = 1

    # --- TAB: AUDIT ---
    with t_audit:
        if 'audit_data' in st.session_state:
            df_a = st.session_state.audit_data
            st.markdown(f"### 🕵️ Auditoría Total: {len(df_a)} registros analizados")
            
            # Filters for Audit Table
            f_status = st.multiselect("Filtrar Estado:", df_a['Estado_Audit'].unique(), default=df_a['Estado_Audit'].unique())
            df_show = df_a[df_a['Estado_Audit'].isin(f_status)]
            
            st.dataframe(df_show, use_container_width=True)
            st.download_button("📥 Descargar CSV Auditoría", df_a.to_csv(index=False).encode('utf-8'), "audit_completo.csv", "text/csv")
        else:
            st.info("Realiza una búsqueda para ver la auditoría.")

    # --- TAB: RESULTS ---
    with t_res:
        if 'search_results' in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            if "FechaPublicacion" in df.columns:
                df = df.sort_values("FechaPublicacion", ascending=False)

            # Columns setup
            for c in ["Ver","Guardar","Ignorar"]: 
                if c not in df.columns: df[c] = False
            df["Web"] = df["Link"]
            
            # Pagination
            total_rows = len(df)
            total_pages = math.ceil(total_rows / ITEMS_PER_PAGE)
            
            cp1, cp2, cp3 = st.columns([1,4,1])
            with cp1: 
                if st.button("⬅️") and st.session_state.page_number > 1: st.session_state.page_number -= 1
            with cp3:
                if st.button("➡️") and st.session_state.page_number < total_pages: st.session_state.page_number += 1
            with cp2:
                st.markdown(f"<div style='text-align:center'>Pág {st.session_state.page_number} de {total_pages} ({total_rows} total)</div>", unsafe_allow_html=True)
                
            idx_start = (st.session_state.page_number - 1) * ITEMS_PER_PAGE
            idx_end = idx_start + ITEMS_PER_PAGE
            df_page = df.iloc[idx_start:idx_end]
            
            # Data Editor
            edited = st.data_editor(
                df_page,
                column_order=["Web","CodigoExterno","Nombre","EstadoTiempo","FechaPublicacion","FechaCierre","Categoría","Palabra Clave","Ignorar","Guardar","Ver"],
                column_config={
                    "Web": st.column_config.LinkColumn("🔗", width="small", display_text="🔗"),
                    "Ignorar": st.column_config.CheckboxColumn("❌", width="small"),
                    "Guardar": st.column_config.CheckboxColumn("💾", width="small"),
                    "Ver": st.column_config.CheckboxColumn("👁️", width="small"),
                    "FechaPublicacion": st.column_config.DateColumn("Publicado", format="DD/MM/YYYY"),
                    "FechaCierre": st.column_config.DateColumn("Cierre", format="DD/MM/YYYY"),
                },
                hide_index=True,
                height=700,
                key=f"editor_{st.session_state.page_number}"
            )
            
            # Actions
            sel = edited[edited["Ver"]==True]
            if not sel.empty: st.session_state['selected_tender'] = sel.iloc[0].to_dict()
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("💾 Guardar Seleccionados"):
                    cnt = sum(save_tender(r.to_dict()) for _, r in edited[edited["Guardar"]].iterrows())
                    if cnt: st.toast(f"Guardados: {cnt}", icon="💾")
            with c_a2:
                if st.button("❌ Ocultar (Lista Negra)"):
                    rows = edited[edited["Ignorar"]]
                    for _, r in rows.iterrows(): ignore_tender(r['CodigoExterno'])
                    if not rows.empty: 
                        st.toast("Ocultados. Recarga para actualizar.", icon="🗑️")
                        time.sleep(1); st.rerun()

    # --- TAB: DETAILS ---
    with st.sidebar:
        if 'selected_tender' in st.session_state:
            d = st.session_state['selected_tender']
            st.header("📄 Detalle Rápido")
            st.info(d['Nombre'])
            st.write(f"**ID:** {d['CodigoExterno']}")
            st.write(f"**Cierre:** {d['FechaCierre']}")
            st.write(d.get('Descripcion',''))
            st.markdown(f"[Ver Web]({d['Link']})")
        
        st.divider()
        st.header("🛡️ Gestión Lista Negra")
        ign = get_ignored_set()
        if ign:
            st.write(f"{len(ign)} ocultos.")
            to_restore = st.selectbox("Restaurar ID", list(ign))
            if st.button("Restaurar"):
                restore_tender(to_restore)
                st.rerun()

    # --- TAB: SAVED ---
    with t_sav:
        saved = get_saved()
        if not saved.empty:
            st.dataframe(saved)
            if st.button("Borrar Marcador Seleccionado"):
                # Logic simplified for button
                pass 
        else: st.info("No hay guardados")

if __name__ == "__main__":
    main()
