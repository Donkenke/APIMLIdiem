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
        .stDataFrame { border: 1px solid #e0e0e0; border-radius: 5px; }
        div.stButton > button:first-child { border-radius: 5px; }
        /* Style for the 'New' badge logic if used in text, though we use columns now */
    </style>
""", unsafe_allow_html=True)

if 'selected_code' not in st.session_state:
    st.session_state.selected_code = None

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
    """ action: True (Save), False (Unsave) """
    c = conn.cursor()
    if action:
        c.execute('INSERT OR REPLACE INTO saved (code, timestamp) VALUES (?, ?)', (code, datetime.now()))
        # If it was hidden, remove from hidden
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
        
        # Monto
        monto = 0
        if item.get("MontoEstimado") and float(item.get("MontoEstimado") or 0) > 0:
            monto = float(item.get("MontoEstimado"))
        else:
            ext = item.get("ExtendedMetadata", {}).get("Section_1_Características", {})
            monto = clean_money_string(ext.get("Presupuesto"))
            if monto == 0:
                monto = estimate_monto(ext.get("Tipo de Licitación", ""))

        # Fecha handling (Convert to proper date object for filtering)
        fecha_str = item.get("Fechas", {}).get("FechaPublicacion", "")[:10]
        fecha_obj = None
        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        except: pass

        rows.append({
            "Codigo": code,
            "Nombre": item.get("Nombre", ""),
            "Organismo": item.get("Comprador", {}).get("NombreOrganismo", ""),
            "Categoria": item.get("Match_Category", "Sin Categoría"), # From scraper.py logic
            "Monto": monto,
            "Fecha": fecha_obj, 
            "URL": item.get("URL_Publica")
        })
        full_map[code] = item
        
    return pd.DataFrame(rows), full_map

# Load
df_raw, full_map = load_data()
hidden_ids, saved_ids, history_ids = get_db_lists()

# ==========================================
# 🔍 FILTERS (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("🎛️ Filtros")
    
    # 1. Date Range Filter
    if not df_raw.empty:
        min_d = df_raw["Fecha"].min()
        max_d = df_raw["Fecha"].max()
        # Handle cases where dates might be NaT
        if pd.isna(min_d): min_d = date.today()
        if pd.isna(max_d): max_d = date.today()
        
        date_range = st.date_input("📅 Rango Fecha Publicación", [min_d, max_d])
    else:
        date_range = []

    # 2. Category Filter
    all_cats = sorted(df_raw["Categoria"].astype(str).unique().tolist()) if not df_raw.empty else []
    sel_cats = st.multiselect("🏷️ Categoría", all_cats, default=[])
    
    # 3. Organismo Filter
    all_orgs = sorted(df_raw["Organismo"].astype(str).unique().tolist()) if not df_raw.empty else []
    sel_orgs = st.multiselect("🏢 Organismo", all_orgs, default=[])

    st.divider()
    if st.button("🔄 Refrescar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 🧠 APPLY FILTERS & LOGIC
# ==========================================
if not df_raw.empty:
    # A. Filter Hidden (Base)
    df_visible = df_raw[~df_raw["Codigo"].isin(hidden_ids)].copy()

    # B. Apply Sidebar Filters
    if len(date_range) == 2:
        df_visible = df_visible[
            (df_visible["Fecha"] >= date_range[0]) & 
            (df_visible["Fecha"] <= date_range[1])
        ]
    if sel_cats:
        df_visible = df_visible[df_visible["Categoria"].isin(sel_cats)]
    if sel_orgs:
        df_visible = df_visible[df_visible["Organismo"].isin(sel_orgs)]

    # C. Prepare UI Columns
    # 1. New Flag
    new_mask = ~df_visible["Codigo"].isin(history_ids)
    df_visible["Nuevo"] = False
    df_visible.loc[new_mask, "Nuevo"] = True
    
    # 2. Saved Flag (Checkbox)
    df_visible["⭐"] = df_visible["Codigo"].isin(saved_ids)
    
    # 3. Delete Flag (Checkbox - Default False)
    df_visible["🗑️"] = False
    
    # D. Mark New as Seen (in DB)
    new_codes = df_visible.loc[new_mask, "Codigo"].tolist()
    if new_codes:
        db_mark_seen(new_codes)
        
    # E. Create Saved Subset for Tab 2
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

tab_main, tab_saved, tab_detail = st.tabs(["📥 Disponibles", "⭐ Guardadas", "📄 Ficha Técnica"])

# --- DATA EDITOR HANDLER ---
def handle_editor_changes(edited_df, original_df):
    """Detects clicks on checkboxes and updates DB."""
    # 1. Detect Save Changes
    changes_save = edited_df["⭐"] != original_df["⭐"]
    changed_rows_save = edited_df[changes_save]
    
    for idx, row in changed_rows_save.iterrows():
        code = row["Codigo"]
        is_checked = row["⭐"]
        db_toggle_save(code, is_checked)
        return True # Trigger rerun

    # 2. Detect Delete Clicks
    # Note: Trigger if User checks the Trash bin
    changes_hide = edited_df["🗑️"] == True 
    changed_rows_hide = edited_df[changes_hide]
    
    for idx, row in changed_rows_hide.iterrows():
        code = row["Codigo"]
        db_hide_permanent(code)
        return True
        
    return False

# --- TAB 1: DISPONIBLES ---
with tab_main:
    st.caption(f"Mostrando {len(df_visible)} licitaciones según filtros.")
    
    if not df_visible.empty:
        # Configuration for the Editable Grid
        column_cfg = {
            "⭐": st.column_config.CheckboxColumn("Guardar", help="Marcar como interesante", width="small"),
            "🗑️": st.column_config.CheckboxColumn("Ocultar", help="Mover a papelera", width="small"),
            "Nuevo": st.column_config.CheckboxColumn("🆕", width="small", disabled=True), # Read-only
            "Codigo": st.column_config.TextColumn("ID", width="medium"),
            "Nombre": st.column_config.TextColumn("Nombre Licitación", width="large"),
            "Categoria": st.column_config.TextColumn("Categoría", width="medium"),
            "Monto": st.column_config.NumberColumn("Monto ($)", format="$%d"),
            "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "URL": st.column_config.LinkColumn("Link", display_text="Ver"),
            "Organismo": st.column_config.TextColumn("Organismo"),
        }
        
        # We use a key based on length/filter to ensure freshness
        unique_key = f"editor_main_{len(df_visible)}_{st.session_state.get('last_update', 0)}"

        edited_main = st.data_editor(
            df_visible,
            column_config=column_cfg,
            column_order=["⭐", "🗑️", "Nuevo", "Codigo", "Nombre", "Categoria", "Monto", "Fecha", "Organismo"],
            hide_index=True,
            use_container_width=True,
            height=600,
            key=unique_key,
            on_select="rerun", # Allow row selection
            selection_mode="single-row"
        )
        
        # Detect Checkbox Clicks
        if handle_editor_changes(edited_main, df_visible):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()

        # Detect Row Selection (for Detail View)
        if len(edited_main.selection.rows) > 0:
            idx = edited_main.selection.rows[0]
            code = df_visible.iloc[idx]["Codigo"]
            if st.session_state.selected_code != code:
                st.session_state.selected_code = code
                st.rerun()

# --- TAB 2: GUARDADAS ---
with tab_saved:
    if not df_saved_view.empty:
        column_cfg_saved = {
            "⭐": st.column_config.CheckboxColumn("Guardada", width="small"),
            "🗑️": st.column_config.CheckboxColumn("Ocultar", width="small"),
            "Nuevo": st.column_config.Column(hidden=True),
            "Codigo": st.column_config.TextColumn("ID", width="medium"),
            "Nombre": st.column_config.TextColumn("Nombre", width="large"),
            "Monto": st.column_config.NumberColumn("Monto", format="$%d"),
            "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        }
        
        unique_key_saved = f"editor_saved_{len(df_saved_view)}_{st.session_state.get('last_update', 0)}"
        
        edited_saved = st.data_editor(
            df_saved_view,
            column_config=column_cfg_saved,
            column_order=["⭐", "Codigo", "Nombre", "Categoria", "Monto", "Fecha", "Organismo"],
            hide_index=True,
            use_container_width=True,
            key=unique_key_saved,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if handle_editor_changes(edited_saved, df_saved_view):
            st.session_state.last_update = datetime.now().timestamp()
            st.rerun()
            
        if len(edited_saved.selection.rows) > 0:
            idx = edited_saved.selection.rows[0]
            code = df_saved_view.iloc[idx]["Codigo"]
            if st.session_state.selected_code != code:
                st.session_state.selected_code = code
                st.rerun()
    else:
        st.info("No tienes licitaciones guardadas.")

# --- TAB 3: DETAIL VIEW ---
with tab_detail:
    if st.session_state.selected_code and st.session_state.selected_code in full_map:
        code = st.session_state.selected_code
        data = full_map[code]
        
        # Header
        st.subheader(data.get("Nombre"))
        st.caption(f"ID: {code} | Categ: {data.get('Match_Category', 'General')}")
        
        # Actions (Backup buttons in detail view)
        c1, c2 = st.columns([1, 4])
        is_saved = code in saved_ids
        with c1:
             if st.button("⭐/❌ Toggle Guardar", key="btn_detail_save"):
                 db_toggle_save(code, not is_saved)
                 st.rerun()
        
        st.divider()
        
        # Content
        col1, col2 = st.columns(2)
        sec1 = data.get("ExtendedMetadata", {}).get("Section_1_Características", {})
        
        with col1:
             st.write(f"**Organismo:** {data.get('Comprador', {}).get('NombreOrganismo', '-')}")
             st.write(f"**Tipo:** {sec1.get('Tipo de Licitación', '-')}")
             st.write(f"**Cierre:** {data.get('Fechas', {}).get('FechaCierre', '')}")
             
        with col2:
             st.markdown(f"[🔗 Abrir en MercadoPúblico]({data.get('URL_Publica')})")
             if data.get("MontoEstimado"): 
                 st.write(f"**Monto:** :blue[${float(data.get('MontoEstimado')):,.0f}]")
             elif sec1.get("Presupuesto"):
                 st.write(f"**Presupuesto:** {sec1.get('Presupuesto')}")

        st.markdown("##### Descripción")
        st.info(data.get("Descripcion", ""))
        
        items = data.get('Items', {}).get('Listado', [])
        if not items and 'DetalleArticulos' in data: items = data['DetalleArticulos']
        
        if items:
            st.markdown("###### Items")
            st.dataframe(pd.json_normalize(items), use_container_width=True)
    else:
        st.markdown("<br><h3 style='text-align:center; color:#ccc'>👈 Selecciona una fila para ver detalle</h3>", unsafe_allow_html=True)
