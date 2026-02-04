import streamlit as st
import pandas as pd
import requests
import urllib3
import json
import sqlite3
import time
import math
from datetime import datetime, timedelta

# --- CONFIGURATION ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Page setup
st.set_page_config(page_title="Monitor de Licitaciones Pro", page_icon="🏗️", layout="wide")

# Constants
BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"
DB_FILE = "licitaciones.db"
ITEMS_PER_PAGE = 25  # Pagination Limit

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

# --- DATABASE MANAGEMENT (GOLDEN STANDARD) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Marcadores (Favoritos del usuario)
    c.execute('''CREATE TABLE IF NOT EXISTS marcadores (
        codigo_externo TEXT PRIMARY KEY,
        nombre TEXT,
        organismo TEXT,
        fecha_cierre TEXT,
        url TEXT,
        raw_data TEXT,
        fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 2. Ignorados (Blacklist)
    c.execute('''CREATE TABLE IF NOT EXISTS ignorados (
        codigo_externo TEXT PRIMARY KEY,
        fecha_ignorado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 3. Cache API (The Golden Standard: Persist fetched details)
    c.execute('''CREATE TABLE IF NOT EXISTS cache_detalles (
        codigo_externo TEXT PRIMARY KEY,
        json_data TEXT,
        fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_cierre_licitacion TEXT
    )''')
    
    conn.commit()
    conn.close()

# --- CACHE FUNCTIONS ---
def get_cached_details(codigos):
    """Retrieves JSON data for existing codes in DB."""
    if not codigos: return {}
    conn = sqlite3.connect(DB_FILE)
    placeholders = ','.join(['?'] * len(codigos))
    query = f"SELECT codigo_externo, json_data FROM cache_detalles WHERE codigo_externo IN ({placeholders})"
    
    try:
        df = pd.read_sql_query(query, conn, params=codigos)
        conn.close()
        return dict(zip(df['codigo_externo'], df['json_data']))
    except:
        return {}

def save_cache_detail(codigo, data_dict):
    """Saves a single API response to cache."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO cache_detalles (codigo_externo, json_data, fecha_cierre_licitacion) VALUES (?, ?, ?)",
                  (codigo, json.dumps(data_dict), str(data_dict.get('FechaCierre', ''))))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Cache Error: {e}")

# --- BLACKLIST FUNCTIONS ---
def ignore_tender_db(codigo_externo):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO ignorados (codigo_externo) VALUES (?)", (codigo_externo,))
        conn.commit()
        conn.close()
        return True
    except: return False

def get_ignored_tenders():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT codigo_externo FROM ignorados", conn)
        conn.close()
        return set(df['codigo_externo'].tolist())
    except: return set()

def restore_ignored_tender(codigo_externo):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM ignorados WHERE codigo_externo = ?", (codigo_externo,))
        conn.commit()
        conn.close()
        return True
    except: return False

# --- FAVORITES FUNCTIONS ---
def save_tender_to_db(tender_dict):
    try:
        data = tender_dict.copy()
        for k in ['Ver', 'Guardar', 'Ignorar', 'MontoStr', 'EstadoTiempo']: data.pop(k, None)
        if isinstance(data.get('FechaCierre'), pd.Timestamp):
            data['FechaCierre'] = data['FechaCierre'].isoformat()
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO marcadores (codigo_externo, nombre, organismo, fecha_cierre, url, raw_data) VALUES (?, ?, ?, ?, ?, ?)",
                  (data['CodigoExterno'], data['Nombre'], data['Organismo'], str(data['FechaCierre']), data['Link'], json.dumps(data, default=str)))
        conn.commit(); conn.close()
        return True
    except: return False

def get_saved_tenders():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM marcadores ORDER BY fecha_guardado DESC", conn)
        conn.close()
        return df
    except: return pd.DataFrame()

def delete_tender_from_db(code):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM marcadores WHERE codigo_externo = ?", (code,))
    conn.commit(); conn.close()

# --- API HELPERS ---
def get_ticket():
    try: return st.secrets.get("MP_TICKET")
    except: return None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_summaries_for_range(start_date, end_date, ticket):
    """Fetch light summaries. Cached 30 mins."""
    all_summaries = []
    delta = end_date - start_date
    total_days = delta.days + 1
    
    # Session for connection pooling
    session = requests.Session()
    
    for i in range(total_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%d%m%Y")
        url = f"{BASE_URL}/licitaciones.json?fecha={date_str}&ticket={ticket}"
        try:
            response = session.get(url, verify=False, timeout=5)
            if response.status_code == 200:
                data = response.json()
                items = data.get('Listado', [])
                all_summaries.extend(items)
        except: pass
    return all_summaries

def fetch_full_detail_live(codigo, ticket):
    """Direct API call, no caching logic inside (handled externally)."""
    url = f"{BASE_URL}/licitaciones.json?codigo={codigo}&ticket={ticket}"
    try:
        response = requests.get(url, verify=False, timeout=8) # Robust timeout
        if response.status_code == 200:
            data = response.json()
            if data.get('Listado'):
                return data['Listado'][0]
    except: pass
    return None

# --- PARSING ---
def parse_date(date_input):
    if not date_input: return None
    if isinstance(date_input, datetime): return date_input
    s = str(date_input).strip().split(".")[0] # Remove millis
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"]:
        try: return datetime.strptime(s, fmt)
        except: continue
    return None

def safe_float(val):
    try: return float(val) if val else 0.0
    except: return 0.0

def format_clp(val):
    try: return "${:,.0f}".format(val).replace(",", ".") if val else "$0"
    except: return "$0"

def clean_text(text):
    return str(text).strip().title() if text else ""

def get_category_info(text):
    text_lower = text.lower()
    for kw, cat in KEYWORD_MAPPING.items():
        if kw.lower() in text_lower: return cat, kw
    return None, None

def is_date_valid(d):
    if not d: return True # Permissive
    return d >= datetime.now()

def process_detail_data(raw_data, summary_cat, summary_kw):
    """Standardizes API JSON into our App Dataframe format."""
    code = raw_data.get('CodigoExterno', 'N/A')
    comprador = raw_data.get('Comprador', {})
    fechas = raw_data.get('Fechas', {})
    
    monto = safe_float(raw_data.get('MontoEstimado'))
    c_date = parse_date(fechas.get('FechaCierre'))
    
    # State Logic
    state_str = "⚠️ Sin Fecha"
    if c_date:
        state_str = "🟢 Vigente" if c_date >= datetime.now() else "🔴 Cerrada"

    return {
        "CodigoExterno": code,
        "Link": f"https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idLicitacion={code}",
        "Nombre": clean_text(raw_data.get('Nombre', 'Sin Nombre')),
        "Organismo": clean_text(comprador.get('NombreOrganismo', 'N/A')),
        "Unidad": clean_text(comprador.get('NombreUnidad', 'N/A')),
        "FechaPublicacion": parse_date(fechas.get('FechaPublicacion')),
        "FechaCierre": c_date,
        "Estado": raw_data.get('Estado', ''),
        "MontoEstimado": monto,
        "MontoStr": format_clp(monto),
        "Descripcion": raw_data.get('Descripcion', ''),
        "Categoría": summary_cat,
        "Palabra Clave": summary_kw,
        "EstadoTiempo": state_str
    }

# --- MAIN APP ---
def main():
    init_db()
    
    # -----------------------------------------------
    # FIX: Initialize Page Number at start to prevent crash
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 1
    # -----------------------------------------------

    ticket = get_ticket()
    
    st.title("🏗️ Monitor de Licitaciones Pro")
    
    if not ticket:
        st.warning("⚠️ Ticket no encontrado."); st.stop()

    # Layout
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        today = datetime.now()
        ten_days_ago = today - timedelta(days=10)
        date_range = st.date_input("Periodo", (ten_days_ago, today), max_value=today, format="DD/MM/YYYY")
        show_closed = st.checkbox("Mostrar Historial (Cerradas)", value=False)
    with col2:
        st.write(""); st.write("")
        search_clicked = st.button("🔄 Buscar (Smart Cache)", type="primary", use_container_width=True)
    with col3:
        st.write(""); st.write("")
        st.caption(f"🎯 Keywords: {len(KEYWORD_MAPPING)}")

    tab_res, tab_det, tab_sav = st.tabs(["🔍 Resultados", "📄 Detalle", "💾 Guardados"])

    # --- LOGIC CORE ---
    if search_clicked or "search_results" not in st.session_state:
        # Load Blacklist
        ignored = get_ignored_tenders()
        
        # Date Logic
        if isinstance(date_range, tuple): start, end = date_range[0], date_range[1] if len(date_range) > 1 else date_range[0]
        else: start = end = today

        # 1. Fetch Light Summaries
        with st.spinner("Conectando con MercadoPúblico..."):
            summaries = fetch_summaries_for_range(start, end, ticket)
        
        # 2. Filter Candidates (Local)
        candidates = []
        codes_to_process = []
        
        for s in summaries:
            code = s.get('CodigoExterno')
            if code in ignored: continue # Skip Blacklisted
            
            txt = f"{s.get('Nombre','')} {s.get('Descripcion','')}"
            cat, kw = get_category_info(txt)
            
            # Smart Date Check (permissive on summary)
            d_sum = parse_date(s.get('FechaCierre'))
            is_valid = is_date_valid(d_sum)
            
            if cat and (is_valid or show_closed):
                s['_cat'], s['_kw'] = cat, kw
                candidates.append(s)
                codes_to_process.append(code)

        # 3. Cache Check (Batch)
        cached_data_map = get_cached_details(codes_to_process)
        
        final_list = []
        
        # 4. Processing Loop (Cache Hit vs API Miss)
        if candidates:
            info_box = st.empty()
            p_bar = st.progress(0)
            
            api_calls = 0
            for idx, item in enumerate(candidates):
                code = item['CodigoExterno']
                
                # A. Try Cache
                if code in cached_data_map:
                    raw_json = cached_data_map[code]
                    try:
                        detail = json.loads(raw_json)
                        # Process
                        row = process_detail_data(detail, item['_cat'], item['_kw'])
                        # Final Date Check (Strict)
                        if is_date_valid(row['FechaCierre']) or show_closed:
                            final_list.append(row)
                    except:
                        pass # Corrupt cache, ignore
                
                # B. Try API (Only if missing)
                else:
                    detail = fetch_full_detail_live(code, ticket)
                    if detail:
                        # Save to Cache immediately
                        save_cache_detail(code, detail)
                        # Process
                        row = process_detail_data(detail, item['_cat'], item['_kw'])
                        if is_date_valid(row['FechaCierre']) or show_closed:
                            final_list.append(row)
                    else:
                        # Fallback (API failed, keeps summary data)
                        pass 
                    
                    api_calls += 1
                    time.sleep(0.05) # Polite delay
                
                # UI Update (Throttle updates)
                if idx % 5 == 0 or idx == len(candidates)-1:
                    pct = (idx + 1) / len(candidates)
                    p_bar.progress(pct)
                    info_box.caption(f"Procesando: {idx+1}/{len(candidates)} | ⚡ Cache: {len(candidates)-api_calls} | 🌐 API: {api_calls}")

            p_bar.empty()
            info_box.empty()
            
            if api_calls > 0:
                # FIX: Changed icon from 'cloud' to emoji '☁️'
                st.toast(f"📥 Se descargaron {api_calls} licitaciones nuevas.", icon="☁️")
        
        # 5. Store Results
        df = pd.DataFrame(final_list)
        # Sort by Publicacion descending
        if not df.empty and 'FechaPublicacion' in df.columns:
            df = df.sort_values(by='FechaPublicacion', ascending=False)
            
        st.session_state.search_results = df
        st.session_state.page_number = 1 # Reset pagination

    # --- RESULTS TAB (WITH PAGINATION) ---
    with tab_res:
        if "search_results" in st.session_state and not st.session_state.search_results.empty:
            df = st.session_state.search_results.copy()
            
            # Add Actions
            for col in ["Ver", "Guardar", "Ignorar"]:
                if col not in df.columns: df.insert(0, col, False)
            df["Web"] = df["Link"]

            # Pagination Logic
            total_rows = len(df)
            total_pages = math.ceil(total_rows / ITEMS_PER_PAGE)
            
            # Pagination Controls
            col_p1, col_p2, col_p3 = st.columns([1, 4, 1])
            with col_p1:
                if st.button("⬅️ Anterior") and st.session_state.page_number > 1:
                    st.session_state.page_number -= 1
            with col_p3:
                if st.button("Siguiente ➡️") and st.session_state.page_number < total_pages:
                    st.session_state.page_number += 1
            with col_p2:
                st.markdown(f"<div style='text-align: center'><b>Página {st.session_state.page_number} de {total_pages}</b> (Total: {total_rows} licitaciones)</div>", unsafe_allow_html=True)

            # Slice Data
            start_idx = (st.session_state.page_number - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            df_page = df.iloc[start_idx:end_idx]

            # Config
            cfg = {
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
                "Ignorar": st.column_config.CheckboxColumn("❌", width="small", help="No volver a mostrar"),
                "Guardar": st.column_config.CheckboxColumn("💾", width="small"),
                "Ver": st.column_config.CheckboxColumn("👁️", width="small")
            }
            cols = ["Web", "CodigoExterno", "Nombre", "Organismo", "Unidad", "EstadoTiempo", 
                    "Categoría", "Palabra Clave", "FechaPublicacion", "FechaCierre", "MontoStr", 
                    "Ignorar", "Guardar", "Ver"]

            # Render Page
            edited = st.data_editor(
                df_page, 
                column_order=cols,
                column_config=cfg,
                disabled=[c for c in cols if c not in ["Guardar", "Ver", "Ignorar"]],
                hide_index=True, 
                width="stretch", 
                height=700,
                key=f"editor_page_{st.session_state.page_number}"
            )
            
            # --- ACTIONS ---
            
            # 1. Select View
            sel = edited[edited["Ver"]==True]
            if not sel.empty: st.session_state['selected_tender'] = sel.iloc[0].to_dict()

            c_act1, c_act2 = st.columns(2)
            with c_act1:
                # 2. Save
                if st.button("💾 Guardar Seleccionados (Página Actual)"):
                    rows = edited[edited["Guardar"]==True]
                    if not rows.empty:
                        cnt = sum(save_tender_to_db(r.to_dict()) for _, r in rows.iterrows())
                        st.toast(f"✅ {cnt} guardados.", icon="💾")

            with c_act2:
                # 3. Blacklist
                if st.button("❌ Ocultar (Lista Negra)"):
                    rows = edited[edited["Ignorar"]==True]
                    if not rows.empty:
                        for _, r in rows.iterrows(): ignore_tender_db(r['CodigoExterno'])
                        st.toast("🚫 Ocultados. Recarga para actualizar.", icon="🗑️")
                        time.sleep(1)
                        st.rerun()
            
        else:
            st.info("No hay resultados. Intenta ampliar el rango de fechas.")

        # --- RESTORE SECTION ---
        with st.expander("🛠️ Gestión de Ocultos (Lista Negra)"):
            ignored = get_ignored_tenders()
            if ignored:
                st.write(f"Hay {len(ignored)} licitaciones ocultas.")
                to_restore = st.selectbox("Restaurar ID:", list(ignored))
                if st.button("♻️ Restaurar"):
                    restore_ignored_tender(to_restore)
                    st.success("Restaurado.")
            else:
                st.write("No tienes licitaciones ocultas.")

    # --- DETAILS TAB ---
    with tab_det:
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
            st.markdown(f"[**🔗 Ficha Oficial**]({d['Link']})")
        else:
            st.info("Selecciona 👁️ en la tabla.")

    # --- SAVED TAB ---
    with tab_sav:
        st.subheader("📚 Mis Marcadores")
        saved = get_saved_tenders()
        if not saved.empty:
            st.dataframe(saved, column_config={"url": st.column_config.LinkColumn("Link", display_text="🔗")}, hide_index=True, width="stretch")
            if st.button("🗑️ Borrar Marcador"):
                code = st.selectbox("ID a borrar", saved['codigo_externo'])
                if code: delete_tender_from_db(code); st.rerun()
        else:
            st.info("No hay guardados.")

if __name__ == "__main__":
    main()
