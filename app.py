import streamlit as st
import pandas as pd
import requests
import urllib3
import json
import sqlite3
import time
import math
import concurrent.futures
import numpy as np
import random
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="Monitor IDIEM Pro", page_icon="🏗️", layout="wide")

# Constants
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
DB_FILE = "licitaciones_v9_ui_fix.db" 
ITEMS_PER_PAGE = 50 
# Ola 1: Velocidad normal
MAX_WORKERS_WAVE_1 = 4 
# Ola 2: Velocidad reducida para asegurar éxito
MAX_WORKERS_WAVE_2 = 2

# --- KEYWORD MAPPING (IDIEM) ---
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

# --- SCORING RULES (Pure Python) ---
SCORING_RULES = {
    "geotecn": 10, "mecanica de suelos": 10, "calicata": 10, "sondaje": 10,
    "laboratorio": 10, "ensayo": 10, "hormigon": 10, "asfalto": 10, "acero": 8,
    "forense": 10, "peritaje": 10, "ato": 10,
    "ito ": 6, "ito.": 10, "inspeccion tecnica": 10, "supervision": 10, 
    "topograf": 6, "levantamiento": 6, "mensura": 5, "fotogrametr": 6,
    "huella de carbono": 7, "sustentab": 6, "eficiencia energetica": 6,
    "estructural": 10, "calculo": 5, "sismico": 6,
    "ingenieria": 10, "estudio": 10, "consultoria": 10, "diseño": 10, 
    "proyecto": 5, "obra civil": 10, "edificacion": 10, "infraestructura": 10,
    "arriendo": -5, "compra de": -2, "suministro": -2, "catering": -10, 
    "aseo": -10, "vigilancia": -10, "dental":-5
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
    conn.commit()
    conn.close()

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
    conn.commit()
    conn.close()

def save_tender(data):
    try:
        clean = data.copy()
        for k in ['Web','Guardar','Ignorar','MontoStr','EstadoTiempo', 'Similitud']: 
            clean.pop(k, None)
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR REPLACE INTO marcadores (codigo_externo, nombre, organismo, fecha_cierre, url, raw_data) VALUES (?,?,?,?,?,?)",
                     (clean['CodigoExterno'], clean['Nombre'], clean['Organismo'], str(clean['FechaCierre']), clean['Link'], json.dumps(clean, default=str)))
        conn.commit()
        conn.close()
        return True
    except: return False

def get_saved():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql("SELECT * FROM marcadores ORDER BY fecha_guardado DESC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

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
        conn.commit()
        conn.close()
    except: pass

def get_api_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    })
    retry_strategy = Retry(
        total=3, 
        backoff_factor=1, 
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
    session = get_api_session()
    
    for i in range(delta):
        d = start_date + timedelta(days=i)
        d_str = d.strftime("%d%m%Y")
        url = f"{BASE_URL}/licitaciones.json?fecha={d_str}&ticket={ticket}"
        try:
            r = session.get(url, verify=False, timeout=30)
            if r.status_code == 200:
                js = r.json()
                items = js.get('Listado', [])
                for item in items: item['_fecha_origen'] = d_str 
                results.extend(items)
            else:
                errors.append(f"Error {r.status_code} en {d_str}")
        except Exception as e:
            errors.append(f"Fallo conexión en {d_str}: {str(e)}")
        time.sleep(0.5) 
            
    return results, errors

def fetch_detail_worker(args):
    code, ticket = args
    time.sleep(random.uniform(0.1, 0.4)) 
    try:
        session = get_api_session() 
        url = f"{BASE_URL}/licitaciones.json?codigo={code}&ticket={ticket}"
        r = session.get(url, verify=False, timeout=30)
        if r.status_code == 200:
            js = r.json()
            if js.get('Listado'):
                return code, js['Listado'][0]
    except: pass
    return code, None

# --- HEURISTIC SCORING ---
def calculate_relevance_heuristic(tenders_list):
    scores = []
    MAX_SCORE_THRESHOLD = 25.0 
    for t in tenders_list:
        text = f"{t.get('Nombre', '')} {t.get('Descripcion', '')}".lower()
        current_score = 0.0
        for root_word, points in SCORING_RULES.items():
            if root_word in text:
                current_score += points
        final_score = max(0.0, current_score)
        percentage = min(final_score / MAX_SCORE_THRESHOLD, 1.0)
        scores.append(percentage)
    return scores

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
    st.title("🏗️ Monitor IDIEM Pro")
    
    if not ticket: 
        st.warning("Falta Ticket (MP_TICKET en secrets)")
        st.stop()

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        today = datetime.now()
        dr = st.date_input("Rango", (today - timedelta(days=15), today), max_value=today, format="DD/MM/YYYY")
        show_closed = st.checkbox("Incluir Cerradas", value=False)
    with c2:
        st.write("")
        st.write("")
        if st.button("🔄 Buscar Datos", type="primary"):
            st.cache_data.clear()
            if 'search_results' in st.session_state: del st.session_state['search_results']
            st.rerun()
    with c3:
        st.metric("Keywords", len(KEYWORD_MAPPING))

    t_res, t_audit, t_sav = st.tabs(["🔍 Resultados", "🕵️ Auditoría", "💾 Guardados"])

    if 'search_results' not in st.session_state:
        if isinstance(dr, tuple): start, end = dr[0], dr[1] if len(dr)>1 else dr[0]
        else: start = end = dr
        ignored_set = get_ignored_set()
        
        with st.spinner("1. Obteniendo listado maestro..."):
            raw_items, fetch_errors = fetch_summaries_raw(start, end, ticket)
            
        if fetch_errors:
            st.warning(f"Advertencia: {len(fetch_errors)} días tuvieron problemas.")

        audit_logs = []
        candidates = []
        codes_needed_for_api = []
        cached_map = {}

        # 1. Filter
        for item in raw_items:
            code = item.get('CodigoExterno')
            name = item.get('Nombre', '')
            desc = item.get('Descripcion', '')
            pub_date = item.get('FechaPublicacion', '')
            log = {"ID": code, "Nombre": name, "Publicado": pub_date, "Estado_Audit": "?", "Motivo": ""}
            
            if code in ignored_set:
                log["Estado_Audit"], log["Motivo"] = "Oculto", "Lista Negra"
                audit_logs.append(log)
                continue

            full_txt = f"{name} {desc}"
            cat, kw = get_cat(full_txt)
            
            if not cat:
                log["Estado_Audit"], log["Motivo"] = "Descartado", "Sin Keyword"
                audit_logs.append(log)
                continue
            
            d_sum = parse_date(item.get('FechaCierre'))
            if show_closed or (d_sum is None) or (d_sum >= datetime.now()):
                item['_cat'], item['_kw'] = cat, kw
                candidates.append(item)
                log["Estado_Audit"] = "Candidato"
            else:
                log["Estado_Audit"], log["Motivo"] = "Descartado", f"Vencida ({d_sum})"
            audit_logs.append(log)

        # 2. Cache Check
        all_candidate_codes = [c['CodigoExterno'] for c in candidates]
        cached_map = get_cached_details(all_candidate_codes)
        
        for c in all_candidate_codes:
            if c not in cached_map:
                codes_needed_for_api.append(c)

        # 3. Parallel Fetching with RECOVERY WAVE
        if codes_needed_for_api:
            st.info(f"Descargando {len(codes_needed_for_api)} detalles...")
            
            # --- WAVE 1 ---
            failed_in_wave_1 = []
            results_fetched = 0
            pbar = st.progress(0)
            
            tasks = [(code, ticket) for code in codes_needed_for_api]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_WAVE_1) as executor:
                future_to_code = {executor.submit(fetch_detail_worker, task): task[0] for task in tasks}
                for future in concurrent.futures.as_completed(future_to_code):
                    code_done, detail_data = future.result()
                    results_fetched += 1
                    
                    if detail_data:
                        save_cache(code_done, detail_data)
                        cached_map[code_done] = json.dumps(detail_data)
                    else:
                        failed_in_wave_1.append(code_done)
                    
                    pbar.progress(results_fetched / len(codes_needed_for_api))
            
            # --- WAVE 2 ---
            if failed_in_wave_1:
                st.toast(f"Ola 1: {len(failed_in_wave_1)} pendientes. Reintentando...", icon="🚑")
                time.sleep(2) 
                tasks_retry = [(code, ticket) for code in failed_in_wave_1]
                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS_WAVE_2) as executor:
                    future_to_code = {executor.submit(fetch_detail_worker, task): task[0] for task in tasks_retry}
                    for future in concurrent.futures.as_completed(future_to_code):
                        code_done, detail_data = future.result()
                        if detail_data:
                            save_cache(code_done, detail_data)
                            cached_map[code_done] = json.dumps(detail_data)
                            st.toast(f"Recuperada: {code_done}", icon="✅")
            pbar.empty()
        
        # 4. Final Processing
        final_list = []
        for cand in candidates:
            code = cand['CodigoExterno']
            detail = None
            if code in cached_map:
                try: detail = json.loads(cached_map[code])
                except: pass
            
            if detail:
                d_cierre = parse_date(detail.get('Fechas', {}).get('FechaCierre'))
                is_valid = False
                if show_closed: is_valid = True
                elif d_cierre and d_cierre >= datetime.now(): is_valid = True
                
                if is_valid:
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
                    
                    for l in audit_logs:
                        if l['ID'] == code: l['Estado_Audit'], l['Motivo'] = "VISIBLE", "OK"
                else:
                     for l in audit_logs:
                        if l['ID'] == code: l['Estado_Audit'], l['Motivo'] = "Descartado", "Vencida (Detalle)"
            else:
                 for l in audit_logs:
                     if l['ID'] == code: l['Estado_Audit'], l['Motivo'] = "Error API", "Fallo tras 2 intentos"

        if final_list:
            scores = calculate_relevance_heuristic(final_list)
            for i, row in enumerate(final_list):
                row['Similitud'] = scores[i] 

        st.session_state.search_results = pd.DataFrame(final_list)
        st.session_state.audit_data = pd.DataFrame(audit_logs)
        st.session_state.page_number = 1

    # RENDERING
    with t_res:
        if 'search_results' in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            
            # --- GLOBAL SORT CONTROL (Fixes Pagination Sort Issue) ---
            c_sort1, c_sort2 = st.columns([3, 1])
            with c_sort1:
                st.caption(f"Mostrando {len(df)} licitaciones")
            with c_sort2:
                sort_opt = st.selectbox("Ordenar por:", ["Relevancia (Alta)", "Fecha Publicación (Reciente)", "Fecha Cierre (Pronta)"], label_visibility="collapsed")

            if sort_opt == "Relevancia (Alta)":
                if "Similitud" not in df.columns: df["Similitud"] = 0.0
                df = df.sort_values("Similitud", ascending=False)
            elif sort_opt == "Fecha Publicación (Reciente)":
                df = df.sort_values("FechaPublicacion", ascending=False)
            elif sort_opt == "Fecha Cierre (Pronta)":
                df = df.sort_values("FechaCierre", ascending=True)

            # Columns Init
            df["Web"] = df["Link"]
            df["Guardar"] = False
            df["Ignorar"] = False
            
            # Pagination Logic
            total_rows = len(df)
            total_pages = math.ceil(total_rows / ITEMS_PER_PAGE)
            
            # --- COMPACT NAVIGATION (2026 Standard) ---
            # Centered with tight layout
            col_nav1, col_nav2, col_nav3, col_nav4, col_nav5 = st.columns([4, 1, 3, 1, 4])
            
            with col_nav2:
                if st.button("◀", key="prev", use_container_width=True) and st.session_state.page_number > 1: 
                    st.session_state.page_number -= 1
            
            with col_nav3:
                st.markdown(f"<div style='text-align:center; padding-top:5px; font-weight:bold;'>{st.session_state.page_number} / {total_pages}</div>", unsafe_allow_html=True)
            
            with col_nav4:
                if st.button("▶", key="next", use_container_width=True) and st.session_state.page_number < total_pages: 
                    st.session_state.page_number += 1
            
            # Slicing for Display
            idx_start = (st.session_state.page_number - 1) * ITEMS_PER_PAGE
            df_page = df.iloc[idx_start : idx_start + ITEMS_PER_PAGE]
            
            # --- FINAL TABLE CONFIG ---
            edited = st.data_editor(
                df_page,
                column_order=[
                    "Web", "CodigoExterno", "Nombre", 
                    "Organismo", "Unidad", # Added back
                    "EstadoTiempo", "FechaPublicacion", "FechaCierre", 
                    "Categoría", "Ignorar", "Guardar", 
                    "Similitud" # Last column
                ],
                column_config={
                    "Web": st.column_config.LinkColumn("🔗", width="small", display_text="🔗"),
                    "CodigoExterno": st.column_config.TextColumn("ID", width="medium"),
                    "Nombre": st.column_config.TextColumn("Nombre Licitación", width="large"),
                    "Organismo": st.column_config.TextColumn("Organismo", width="medium"),
                    "Unidad": st.column_config.TextColumn("Unidad Compra", width="medium"),
                    "Ignorar": st.column_config.CheckboxColumn("🗑️", width="small", default=False),
                    "Guardar": st.column_config.CheckboxColumn("💾", width="small", default=False),
                    "Similitud": st.column_config.ProgressColumn(
                        "Relevancia", 
                        format=" ", # Hide text, just show bar
                        min_value=0, max_value=1,
                        width="medium"
                    ),
                    "FechaPublicacion": st.column_config.DateColumn("Publicado", format="DD/MM/YY"),
                    "FechaCierre": st.column_config.DateColumn("Cierre", format="DD/MM/YY"),
                },
                hide_index=True,
                height=750,
                key=f"editor_{st.session_state.page_number}"
            )
            
            # Actions
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("💾 Guardar Seleccionados", use_container_width=True):
                    to_save = edited[edited["Guardar"] == True]
                    cnt = sum(save_tender(r.to_dict()) for _, r in to_save.iterrows())
                    if cnt: st.toast(f"Guardados: {cnt}", icon="💾")
            with c_a2:
                if st.button("🚫 Ocultar (Lista Negra)", use_container_width=True):
                    to_ignore = edited[edited["Ignorar"] == True]
                    for _, r in to_ignore.iterrows(): ignore_tender(r['CodigoExterno'])
                    if not to_ignore.empty: 
                        st.toast(f"Ocultados: {len(to_ignore)}", icon="🗑️")
                        time.sleep(1); st.rerun()
        else:
            st.info("Sin resultados disponibles.")

    with t_audit:
        if 'audit_data' in st.session_state:
            st.dataframe(st.session_state.audit_data, use_container_width=True)

    with t_sav:
        saved = get_saved()
        if not saved.empty: st.dataframe(saved)
        else: st.info("No hay guardados")

    with st.sidebar:
        st.success("✅ Sistema IDIEM Pro Activo")
        st.info("La navegación ahora es centralizada y el ordenamiento aplica a todo el conjunto de datos.")
        st.divider()
        ign = get_ignored_set()
        if ign:
            if st.button(f"Restaurar {len(ign)} Ocultos"):
                conn = sqlite3.connect(DB_FILE)
                conn.execute("DELETE FROM ignorados")
                conn.commit()
                conn.close()
                st.rerun()

if __name__ == "__main__":
    main()
