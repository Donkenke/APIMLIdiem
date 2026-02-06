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
# 🧠 CATEGORIZATION LOGIC (From Scraper)
# ==========================================
def get_category(text):
    """Assigns category based on keywords defined in scraper.py"""
    if not text: return "General"
    text = text.upper()
    
    # 1. Strict Acronyms
    if re.search(r'\b(AIF|AIT|ATIF|ATOD|AFOS|ATO|ITO)\b', text): return "Inspección Técnica"
    if re.search(r'\b(PACC|PCC)\b', text): return "Sustentabilidad"
    
    # 2. Key Phrases
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
        
        # 1. Determine Category (Use Scraper logic if missing)
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

        # 3. Fecha
        fecha_str = item.get("Fechas", {}).get("FechaPublicacion", "")[:10]
        fecha_obj = None
        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except: pass

        rows.append({
            "Codigo": code,
            "Nombre": name,
            "Organismo": item.get("Comprador", {}).get("NombreOrganismo", ""),
            "Categoria": cat,
            "Monto": monto,
            "Fecha": fecha_obj, 
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
        # Date Filter
        min_d = df_raw["Fecha"].min()
        max_d = df_raw["Fecha"].max()
        if pd.isna(min_d): min_d = date.today()
        if pd.isna(max_d): max_d = date.today()
        date_range = st.date_input("📅 Fecha Publicación", [min_d, max_d])
        
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
# 🧠 APPLY FILTERS & LOGIC
# ==========================================
if not df_raw.empty:
    # A. Filter Hidden
    df_visible = df_raw[~df_raw["Codigo"].isin(hidden_ids)].copy()

    # B. Apply Filters
    if len(date_range) == 2:
        df_visible = df_visible[
            (df_visible["Fecha"] >= date_range[0]) & 
            (df_visible["Fecha"] <= date_range[1])
        ]
    if sel_cats:
        df_visible = df_visible[df_visible["Categoria"].isin(sel_cats)]
    if sel_orgs:
        df_visible = df_visible[df_visible["Organismo"].isin(sel_orgs)]

    # C. UI Columns
    new_mask = ~df_visible["Codigo"].isin(history_ids)
    df_visible["Nuevo"] = False
    df_visible.loc[new_mask, "Nuevo"] = True
    
    df_visible["⭐"] = df_visible["Codigo"].isin(saved_ids)
    df_visible["🗑️"] = False # Default unchecked
    
    # Mark New as Seen
    new_codes = df_visible.loc[new_mask, "Codigo"].tolist()
    if new_codes:
        db_mark_seen(new_codes)
        
    # Saved View
    df_saved_view = df_raw[df_raw["Codigo"].isin(saved_ids)].copy()
    df_saved_view["⭐"] = True
    df_saved_view["🗑️"] = False
    df_saved_view["Nuevo"] = False

else:
    df_visible = pd.DataFrame()
    df_saved_view = pd.DataFrame()

# ==========================================
# 🖥️ MAIN UI
# ==========================================
st.title("Monitor Licitaciones IDIEM")

# --- DETAIL SELECTOR (Replaces Row Click) ---
# Since data_editor doesn't support selection, we use this dropdown
all_options = df_visible["Codigo"].tolist() if not df_visible.empty else []
if df_saved_view is not None and not df_saved_view.empty:
    all_options.extend(df_saved_view["Codigo"].tolist())
all_options = sorted(list(set(all_options)))

# Selector in Expander to save space
with st.expander("🔎 Ver Detalle de Licitación (Seleccionar ID)", expanded=False):
    sel_code = st.selectbox("Buscar por ID:", [""] + all_options, format_func=lambda x: f"{x} - {full_map.get(x, {}).get('Nombre','')[:60]}..." if x else "Seleccionar...")
    if sel_code and sel_code != st.session_state.selected_code:
        st.session_state.selected_code = sel_code
        # No rerun needed here, tabs will handle it

tab_main, tab_saved, tab_detail = st.tabs(["📥 Disponibles", "⭐ Guardadas", "📄 Ficha Técnica"])

def handle_editor_changes(edited_df, original_df):
    """Detects checkbox clicks."""
    # Save Click
    changes_save = edited_df["⭐"] != original_df["⭐"]
    if changes_save.any():
        row = edited_df[changes_save].iloc[0]
        db_toggle_save(row["Codigo"], row["⭐"])
        return True

    # Trash Click
    changes_hide = edited_df["🗑️"] == True 
    if changes_hide.any():
        row = edited_df[changes_hide].iloc[0]
        db_hide_permanent(row["Codigo"])
        return True
    return False

# --- TAB 1 ---
with tab_main:
    st.caption(f"Registros encontrados: {len(df_visible)}")
    
    if not df_visible.empty:
        # Sort: Newest first
        df_display = df_visible.sort_values(by=["Nuevo", "Fecha"], ascending=[False, False])
        
        column_cfg = {
            "⭐": st.column_config.CheckboxColumn("Guardar", width="small"),
            "🗑️": st.column_config.CheckboxColumn("Ocultar", width="small"),
            "Nuevo": st.column_config.CheckboxColumn("🆕", width="small", disabled=True),
            "Codigo": st.column_config.TextColumn("ID", width="medium"),
            "Nombre": st.column_config.TextColumn("Nombre", width="large"),
            "Monto": st.column_config.NumberColumn("Monto", format="$%d"),
            "URL": st.column_config.LinkColumn("Link", display_text="Abrir"),
            "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        }

        # Unique Key forces refresh when data changes
        ukey = f"main_{len(df_display)}_{st.session_state.get('last_update',0)}"
        
        edited_main = st.data_editor(
            df_display,
            column_config=column_cfg,
            column_order=["⭐", "🗑️", "Nuevo", "Categoria", "Codigo", "Nombre", "Monto", "Fecha", "URL"],
            hide_index=True,
            use_container_width=True,
            height=600,
            key=ukey
        )
        
        if handle_editor_changes(edited_main, df_display):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()

# --- TAB 2 ---
with tab_saved:
    if not df_saved_view.empty:
        ukey_saved = f"saved_{len(df_saved_view)}_{st.session_state.get('last_update',0)}"
        
        edited_saved = st.data_editor(
            df_saved_view,
            column_config={
                "⭐": st.column_config.CheckboxColumn("Guardada", width="small"),
                "🗑️": st.column_config.CheckboxColumn("Ocultar", width="small"),
                "Codigo": st.column_config.TextColumn("ID", width="medium"),
                "URL": st.column_config.LinkColumn("Link", display_text="Abrir"),
            },
            column_order=["⭐", "Codigo", "Nombre", "Categoria", "Monto", "Fecha", "URL"],
            hide_index=True,
            use_container_width=True,
            key=ukey_saved
        )
        
        if handle_editor_changes(edited_saved, df_saved_view):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()
    else:
        st.info("No hay licitaciones guardadas.")

# --- TAB 3 ---
with tab_detail:
    if st.session_state.selected_code and st.session_state.selected_code in full_map:
        code = st.session_state.selected_code
        data = full_map[code]
        
        st.subheader(data.get("Nombre"))
        st.caption(f"ID: {code} | Categ: {data.get('Match_Category', 'General')}")
        
        # Actions
        col_a, col_b = st.columns([1, 4])
        with col_a:
            is_s = code in saved_ids
            if st.button("❌ Quitar" if is_s else "⭐ Guardar", key="btn_det_save"):
                db_toggle_save(code, not is_s)
                st.rerun()
        
        st.divider()
        c1, c2 = st.columns(2)
        sec1 = data.get("ExtendedMetadata", {}).get("Section_1_Características", {})
        
        with c1:
             st.write(f"**Organismo:** {data.get('Comprador', {}).get('NombreOrganismo', '-')}")
             st.write(f"**Tipo:** {sec1.get('Tipo de Licitación', '-')}")
             st.write(f"**Estado:** {sec1.get('Estado', '-')}")
        with c2:
             st.markdown(f"[🔗 Ver en MercadoPúblico]({data.get('URL_Publica')})")
             if data.get("MontoEstimado"):
                 st.write(f"**Monto:** :blue[${float(data.get('MontoEstimado')):,.0f}]")
             else:
                 st.write(f"**Presupuesto:** {sec1.get('Presupuesto', 'No informado')}")

        st.markdown("##### Descripción")
        st.info(data.get("Descripcion", ""))
        
        # Items Table
        items = data.get('Items', {}).get('Listado', [])
        if not items and 'DetalleArticulos' in data: items = data['DetalleArticulos']
        
        if items:
            st.markdown("###### Items")
            st.dataframe(pd.json_normalize(items), use_container_width=True)
    else:
        st.markdown("<br><h3 style='text-align:center; color:#ccc'>👈 Selecciona un ID en el buscador superior</h3>", unsafe_allow_html=True)
