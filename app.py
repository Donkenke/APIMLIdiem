import streamlit as st
import pandas as pd
import json
import os
import re
import sqlite3
from datetime import datetime, date

# --- CONFIGURATION ---
st.set_page_config(page_title="Monitor Licitaciones IDIEM", layout="wide", page_icon="🏗️")

UTM_VALUE = 69611 
JSON_FILE = "FINAL_PRODUCTION_DATA.json"
DB_FILE = "licitaciones_state.db"

# Custom CSS
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        div.stButton > button:first-child { border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

if 'selected_code' not in st.session_state:
    st.session_state.selected_code = None

# ==========================================
# 🧠 CATEGORIZATION LOGIC
# ==========================================
def get_category(text):
    if not text: return "General"
    text = text.upper()
    if re.search(r'\b(AIF|AIT|ATIF|ATOD|AFOS|ATO|ITO)\b', text): return "Inspección Técnica"
    if re.search(r'\b(PACC|PCC)\b', text): return "Sustentabilidad"
    if any(x in text for x in ["ASESORÍA INSPECCIÓN", "SUPERVISIÓN CONSTRUCCIÓN"]): return "Inspección Técnica"
    if any(x in text for x in ["ESTRUCTURAL", "MECÁNICA SUELOS", "GEOLÓGICO", "GEOTÉCNICO", "ENSAYOS", "LABORATORIO"]): return "Ingeniería y Lab"
    if any(x in text for x in ["TOPOGRÁFICO", "TOPOGRAFÍA", "LEVANTAMIENTO", "AEROFOTOGRAMETRÍA"]): return "Topografía"
    if any(x in text for x in ["ARQUITECTURA", "DISEÑO ARQUITECTÓNICO"]): return "Arquitectura"
    if any(x in text for x in ["EFICIENCIA ENERGÉTICA", "CERTIFICACIÓN", "SUSTENTABLE"]): return "Sustentabilidad"
    if any(x in text for x in ["MODELACIÓN", "BIM", "COORDINACIÓN DIGITAL"]): return "BIM / Modelación"
    return "Otras Civiles"

# ==========================================
# 🗄️ SQLITE DATABASE
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS hidden (code TEXT PRIMARY KEY, timestamp DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS saved (code TEXT PRIMARY KEY, timestamp DATETIME, note TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS history (code TEXT PRIMARY KEY, first_seen DATETIME)')
    conn.commit()
    return conn

conn = init_db()

def get_db_lists():
    c = conn.cursor()
    hidden = {row[0] for row in c.execute('SELECT code FROM hidden').fetchall()}
    saved = {row[0] for row in c.execute('SELECT code FROM saved').fetchall()}
    history = {row[0] for row in c.execute('SELECT code FROM history').fetchall()}
    return hidden, saved, history

def db_toggle_save(code, action):
    c = conn.cursor()
    if action:
        c.execute('INSERT OR REPLACE INTO saved (code, timestamp) VALUES (?, ?)', (code, datetime.now()))
        c.execute('DELETE FROM hidden WHERE code = ?', (code,))
        st.toast(f"✅ Guardado: {code}")
    else:
        c.execute('DELETE FROM saved WHERE code = ?', (code,))
        st.toast(f"❌ Removido: {code}")
    conn.commit()

def db_hide_permanent(code):
    c = conn.cursor()
    c.execute('DELETE FROM saved WHERE code = ?', (code,))
    c.execute('INSERT OR REPLACE INTO hidden (code, timestamp) VALUES (?, ?)', (code, datetime.now()))
    conn.commit()
    st.toast(f"🗑️ Ocultado: {code}")

def db_mark_seen(codes):
    if not codes: return
    c = conn.cursor()
    now = datetime.now()
    data = [(c, now) for c in codes]
    c.executemany('INSERT OR IGNORE INTO history (code, first_seen) VALUES (?, ?)', data)
    conn.commit()

# ==========================================
# 🛠️ DATA PROCESSING
# ==========================================
def clean_money_string(text):
    if not text: return 0
    try:
        clean = re.sub(r'[^\d]', '', str(text))
        if clean: return float(clean)
    except: pass
    return 0

def estimate_monto(text):
    if not text: return 0
    matches = re.findall(r'(\d[\d\.]*)', text)
    if matches:
        try:
            return float(matches[0].replace(".", "")) * UTM_VALUE
        except: pass
    return 0

def format_clp(val):
    if not val or val == 0: return "$ 0"
    return f"${val:,.0f}".replace(",", ".")

@st.cache_data
def load_data():
    if not os.path.exists(JSON_FILE):
        return pd.DataFrame(), {}
    
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rows = []
    full_map = {}
    
    for item in data:
        code = item.get("CodigoExterno")
        name = item.get("Nombre", "")
        
        # 1. Categoría
        cat = item.get("Match_Category")
        if not cat or cat == "Sin Categoría":
            cat = get_category(name)
        
        # 2. Monto
        monto = 0
        if item.get("MontoEstimado") and float(item.get("MontoEstimado") or 0) > 0:
            monto = float(item.get("MontoEstimado"))
        else:
            ext = item.get("ExtendedMetadata", {}).get("Section_1_Características", {})
            monto = clean_money_string(ext.get("Presupuesto"))
            if monto == 0:
                monto = estimate_monto(ext.get("Tipo de Licitación", ""))

        # 3. Fechas (Robust Extraction)
        fechas = item.get("Fechas")
        if not fechas: fechas = {} # Handle None if "Fechas": null
        
        # Fecha Publicacion
        raw_pub = fechas.get("FechaPublicacion")
        f_pub = str(raw_pub)[:10] if raw_pub else ""
        
        # Fecha Cierre (This was causing the crash)
        raw_cierre = fechas.get("FechaCierre")
        f_cierre_str = str(raw_cierre)[:10] if raw_cierre else ""
        
        # Parse for Filtering
        f_cierre_obj = None
        if f_cierre_str:
            try:
                f_cierre_obj = datetime.strptime(f_cierre_str, "%Y-%m-%d").date()
            except: 
                pass

        rows.append({
            "Codigo": code,
            "Nombre": name,
            "Organismo": item.get("Comprador", {}).get("NombreOrganismo", ""),
            "Categoria": cat,
            "Monto_Num": monto,
            "Monto": format_clp(monto),
            "Fecha Pub": f_pub,
            "Fecha Cierre": f_cierre_str,
            "FechaCierreObj": f_cierre_obj,
            "URL": item.get("URL_Publica")
        })
        full_map[code] = item
        
    return pd.DataFrame(rows), full_map

# Load Data
df_raw, full_map = load_data()
hidden_ids, saved_ids, history_ids = get_db_lists()

# ==========================================
# 🔍 FILTERS (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("🎛️ Filtros")
    
    if not df_raw.empty:
        # Date Filter (Based on Fecha Cierre)
        valid_dates = df_raw["FechaCierreObj"].dropna()
        if not valid_dates.empty:
            min_d, max_d = valid_dates.min(), valid_dates.max()
            date_range = st.date_input("📅 Fecha de Cierre", [min_d, max_d])
        else:
            date_range = []
            st.warning("No hay fechas de cierre válidas para filtrar.")
        
        # Category Filter
        all_cats = sorted(df_raw["Categoria"].astype(str).unique().tolist())
        sel_cats = st.multiselect("🏷️ Categoría", all_cats)
        
        # Organismo Filter
        all_orgs = sorted(df_raw["Organismo"].astype(str).unique().tolist())
        sel_orgs = st.multiselect("🏢 Organismo", all_orgs)
    else:
        date_range = []
        sel_cats = []
        sel_orgs = []

    st.divider()
    if st.button("🔄 Refrescar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 🧠 APPLY FILTERS
# ==========================================
if not df_raw.empty:
    # 1. Exclude Hidden
    df_visible = df_raw[~df_raw["Codigo"].isin(hidden_ids)].copy()

    # 2. Date Filter
    if len(date_range) == 2:
        df_visible = df_visible[
            (df_visible["FechaCierreObj"] >= date_range[0]) & 
            (df_visible["FechaCierreObj"] <= date_range[1])
        ]
        
    # 3. Dropdown Filters
    if sel_cats:
        df_visible = df_visible[df_visible["Categoria"].isin(sel_cats)]
    if sel_orgs:
        df_visible = df_visible[df_visible["Organismo"].isin(sel_orgs)]

    # 4. State Columns
    new_mask = ~df_visible["Codigo"].isin(history_ids)
    
    df_visible["Estado"] = "Visto"
    df_visible.loc[new_mask, "Estado"] = "🆕 Nuevo"
    
    df_visible["Guardar"] = df_visible["Codigo"].isin(saved_ids)
    df_visible["Ocultar"] = False
    
    # Mark New as Seen
    new_codes = df_visible.loc[new_mask, "Codigo"].tolist()
    if new_codes:
        db_mark_seen(new_codes)

    # Saved View
    df_saved_view = df_raw[df_raw["Codigo"].isin(saved_ids)].copy()
    df_saved_view["Guardar"] = True
    df_saved_view["Ocultar"] = False
    df_saved_view["Estado"] = "Guardado"

else:
    df_visible = pd.DataFrame()
    df_saved_view = pd.DataFrame()

# ==========================================
# 🖥️ MAIN UI
# ==========================================
st.title("Monitor Licitaciones IDIEM")

# Detail Selector
all_options = df_visible["Codigo"].tolist() if not df_visible.empty else []
if not df_saved_view.empty: all_options.extend(df_saved_view["Codigo"].tolist())
all_options = sorted(list(set(all_options)))

with st.expander("🔎 Ver Detalle (Buscar por ID)", expanded=False):
    sel_code = st.selectbox("ID Licitación:", [""] + all_options, format_func=lambda x: f"{x} - {full_map.get(x, {}).get('Nombre','')[:60]}..." if x else "Seleccionar...")
    if sel_code and sel_code != st.session_state.selected_code:
        st.session_state.selected_code = sel_code

tab_main, tab_saved, tab_detail = st.tabs(["📥 Disponibles", "⭐ Guardadas", "📄 Ficha Técnica"])

def handle_editor_changes(edited_df, original_df):
    # Save Click
    changes_save = edited_df["Guardar"] != original_df["Guardar"]
    if changes_save.any():
        row = edited_df[changes_save].iloc[0]
        db_toggle_save(row["Codigo"], row["Guardar"])
        return True
    # Hide Click
    changes_hide = edited_df["Ocultar"] == True 
    if changes_hide.any():
        row = edited_df[changes_hide].iloc[0]
        db_hide_permanent(row["Codigo"])
        return True
    return False

# --- COLUMNS CONFIGURATION ---
common_config = {
    "URL": st.column_config.LinkColumn("Link", display_text="🔗", width="small"),
    "Guardar": st.column_config.CheckboxColumn("Guardar", width="small"),
    "Ocultar": st.column_config.CheckboxColumn("Ocultar", width="small"),
    "Codigo": st.column_config.TextColumn("ID", width="medium"),
    "Nombre": st.column_config.TextColumn("Nombre Licitación", width="large"),
    "Organismo": st.column_config.TextColumn("Organismo", width="medium"),
    "Monto": st.column_config.TextColumn("Monto ($)", width="medium"), 
    "Fecha Pub": st.column_config.TextColumn("Publicación", width="small"),
    "Fecha Cierre": st.column_config.TextColumn("Cierre", width="small"),
    "Categoria": st.column_config.TextColumn("Categoría", width="medium"),
    "Estado": st.column_config.TextColumn("Visto?", width="small", disabled=True)
}

ordered_cols = ["URL", "Guardar", "Ocultar", "Codigo", "Nombre", "Organismo", "Monto", "Fecha Pub", "Fecha Cierre", "Categoria", "Estado"]

# --- TAB 1: DISPONIBLES ---
with tab_main:
    st.caption(f"Mostrando {len(df_visible)} registros.")
    if not df_visible.empty:
        # Sort
        df_disp = df_visible.sort_values(by=["Estado", "FechaCierreObj"], ascending=[True, True]) 
        
        ukey = f"main_{len(df_disp)}_{st.session_state.get('last_update',0)}"
        
        edited_main = st.data_editor(
            df_disp,
            column_config=common_config,
            column_order=ordered_cols,
            hide_index=True,
            use_container_width=True,
            height=600,
            key=ukey
        )
        
        if handle_editor_changes(edited_main, df_disp):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()

# --- TAB 2: GUARDADAS ---
with tab_saved:
    if not df_saved_view.empty:
        ukey_saved = f"saved_{len(df_saved_view)}_{st.session_state.get('last_update',0)}"
        edited_saved = st.data_editor(
            df_saved_view,
            column_config=common_config,
            column_order=ordered_cols,
            hide_index=True,
            use_container_width=True,
            key=ukey_saved
        )
        if handle_editor_changes(edited_saved, df_saved_view):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()
    else:
        st.info("Sin elementos guardados.")

# --- TAB 3: DETALLE ---
with tab_detail:
    if st.session_state.selected_code and st.session_state.selected_code in full_map:
        code = st.session_state.selected_code
        data = full_map[code]
        
        st.subheader(data.get("Nombre"))
        st.caption(f"ID: {code} | Estado: {data.get('Estado')}")
        
        c_btn, c_rest = st.columns([1, 4])
        with c_btn:
            is_s = code in saved_ids
            if st.button("❌ Quitar" if is_s else "⭐ Guardar", key="btn_dtl"):
                db_toggle_save(code, not is_s)
                st.rerun()

        st.divider()
        c1, c2 = st.columns(2)
        sec1 = data.get("ExtendedMetadata", {}).get("Section_1_Características", {})
        
        fechas_det = data.get("Fechas") or {}

        with c1:
             st.markdown(f"**Organismo:** {data.get('Comprador', {}).get('NombreOrganismo', '-')}")
             st.markdown(f"**Tipo:** {sec1.get('Tipo de Licitación', '-')}")
             st.markdown(f"**Cierre:** :red[{fechas_det.get('FechaCierre', 'No informado')}]")
        with c2:
             st.markdown(f"[🔗 Link MercadoPúblico]({data.get('URL_Publica')})")
             
             m_est = data.get("MontoEstimado")
             if m_est and float(m_est) > 0:
                 st.markdown(f"**Monto:** :blue[{format_clp(float(m_est))}]")
             else:
                 st.markdown(f"**Presupuesto:** {sec1.get('Presupuesto', 'No informado')}")

        st.info(data.get("Descripcion", "Sin descripción"))
        
        items = data.get('Items', {}).get('Listado', [])
        if not items and 'DetalleArticulos' in data: items = data['DetalleArticulos']
        if items:
            st.markdown("###### Items")
            st.dataframe(pd.json_normalize(items), use_container_width=True)
    else:
        st.markdown("<br><h3 style='text-align:center; color:#ccc'>👈 Usa el buscador arriba para ver detalle</h3>", unsafe_allow_html=True)
