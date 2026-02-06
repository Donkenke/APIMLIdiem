import streamlit as st
import pandas as pd
import json
import os
import re
import sqlite3
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Monitor Licitaciones IDIEM", layout="wide", page_icon="🏗️")

# UTM Value (Feb 2026 approx)
UTM_VALUE = 69611 
JSON_FILE = "FINAL_PRODUCTION_DATA.json"
DB_FILE = "licitaciones_state.db"

# Custom CSS
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .stDataFrame { border: 1px solid #e0e0e0; border-radius: 5px; }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] { height: 50px; background-color: #f0f2f6; border-radius: 4px 4px 0 0; }
        .stTabs [aria-selected="true"] { background-color: #ffffff; border-top: 2px solid #ff4b4b; }
        div.stButton > button:first-child { border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

if 'selected_code' not in st.session_state:
    st.session_state.selected_code = None

# ==========================================
# 🗄️ SQLITE DATABASE (STATE MANAGEMENT)
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

def db_toggle_save(code):
    c = conn.cursor()
    try:
        c.execute('INSERT INTO saved (code, timestamp) VALUES (?, ?)', (code, datetime.now()))
        st.toast(f"✅ Licitación {code} guardada.")
    except sqlite3.IntegrityError:
        c.execute('DELETE FROM saved WHERE code = ?', (code,))
        st.toast(f"❌ Licitación {code} eliminada de guardadas.")
    conn.commit()

def db_hide_permanent(code):
    c = conn.cursor()
    c.execute('DELETE FROM saved WHERE code = ?', (code,))
    c.execute('INSERT OR REPLACE INTO hidden (code, timestamp) VALUES (?, ?)', (code, datetime.now()))
    conn.commit()
    st.toast(f"🗑️ Licitación {code} ocultada.")

def db_mark_seen(codes):
    if not codes: return
    c = conn.cursor()
    now = datetime.now()
    data = [(c, now) for c in codes]
    c.executemany('INSERT OR IGNORE INTO history (code, first_seen) VALUES (?, ?)', data)
    conn.commit()

# ==========================================
# 🧮 HELPER FUNCTIONS
# ==========================================
def clean_money_string(text):
    if not text: return 0
    try:
        clean = re.sub(r'[^\d]', '', str(text))
        if clean: return float(clean)
    except: pass
    return 0

def estimate_monto_from_text(text):
    if not text: return 0, "No informado"
    matches = re.findall(r'(\d[\d\.]*)', text)
    numbers = []
    for m in matches:
        try:
            val = int(m.replace(".", ""))
            numbers.append(val)
        except: pass
    numbers = sorted(numbers)
    if not numbers: return 0, "No detectado"
    return numbers[0] * UTM_VALUE, "Est. UTM"

# ==========================================
# 🛠️ DATA LOADING
# ==========================================
@st.cache_data
def load_data(json_path):
    if not os.path.exists(json_path):
        return pd.DataFrame(), {}
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    rows = []
    full_details_map = {}
    
    for item in data:
        code = item.get("CodigoExterno")
        
        # Monto Logic
        monto_final = 0
        api_monto = item.get("MontoEstimado")
        if api_monto and float(api_monto) > 0:
            monto_final = float(api_monto)
        else:
            ext = item.get("ExtendedMetadata", {}).get("Section_1_Características", {})
            p_val = clean_money_string(ext.get("Presupuesto"))
            if p_val > 0: monto_final = p_val
            else:
                est, _ = estimate_monto_from_text(ext.get("Tipo de Licitación", ""))
                monto_final = est
        
        # Display Name Truncation
        name_clean = item.get("Nombre", "")
        
        row = {
            "Estado": "", # Placeholder
            "Codigo": code,
            "Nombre": name_clean,
            "Monto": monto_final,
            "Fecha": item.get("Fechas", {}).get("FechaPublicacion", "")[:10] if item.get("Fechas") else "",
            "Organismo": item.get("Comprador", {}).get("NombreOrganismo", ""),
        }
        rows.append(row)
        full_details_map[code] = item 

    return pd.DataFrame(rows), full_details_map

# Load Data
df_raw, full_map = load_data(JSON_FILE)

# --- APPLY DB STATE ---
hidden_ids, saved_ids, history_ids = get_db_lists()

if not df_raw.empty:
    # 1. Filter out Hidden
    df_visible = df_raw[~df_raw["Codigo"].isin(hidden_ids)].copy()
    
    # 2. Identify "New" (Not in history)
    # Logic: If it is NOT in history, it is New.
    new_mask = ~df_visible["Codigo"].isin(history_ids)
    
    # 3. Assign Status Label
    df_visible["Estado"] = "Leído"
    df_visible.loc[new_mask, "Estado"] = "🆕 Nuevo"
    df_visible.loc[df_visible["Codigo"].isin(saved_ids), "Estado"] = "⭐ Guardado"
    
    # 4. Auto-update History for "New" items (so they aren't new next time)
    new_codes = df_visible.loc[new_mask, "Codigo"].tolist()
    if new_codes:
        db_mark_seen(new_codes)
    
    # 5. Create specific subsets
    df_saved = df_visible[df_visible["Codigo"].isin(saved_ids)].copy()

else:
    df_visible = pd.DataFrame()
    df_saved = pd.DataFrame()

# ==========================================
# 🖥️ UI LAYOUT
# ==========================================
with st.sidebar:
    st.title("🎛️ Control")
    st.metric("Disponibles", len(df_visible))
    st.metric("Nuevas (Hoy)", len(new_codes) if 'new_codes' in locals() else 0)
    st.metric("Guardadas", len(df_saved))
    
    if st.button("🔄 Refrescar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    if st.session_state.selected_code:
        st.info(f"Viendo: {st.session_state.selected_code}")
        if st.button("🔙 Deseleccionar"):
            st.session_state.selected_code = None
            st.rerun()

st.title("🏗️ Monitor Licitaciones IDIEM")

tab_main, tab_saved, tab_detail = st.tabs(["📥 Disponibles", "⭐ Guardadas", "📄 Ficha Técnica"])

# --- GRID FUNCTION (NATIVE DATAFRAME) ---
def render_native_grid(df, key):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    # 🎨 Styling: Green for New, Yellow for Saved
    def highlight_status(val):
        if 'Nuevo' in str(val):
            return 'background-color: #d4edda; color: #155724; font-weight: bold'
        elif 'Guardado' in str(val):
            return 'background-color: #fff3cd; color: #856404; font-weight: bold'
        return ''

    # Apply Style
    styled_df = df.style.map(highlight_status, subset=['Estado'])
    
    # Formatting Monto
    styled_df = styled_df.format({"Monto": "${:,.0f}"})

    # Render with Selection
    event = st.dataframe(
        styled_df,
        column_order=["Estado", "Codigo", "Nombre", "Monto", "Organismo", "Fecha"],
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
        height=500,
        key=key
    )

    # Handle Selection
    if event.selection.rows:
        idx = event.selection.rows[0]
        # Map visual index back to dataframe index
        code = df.iloc[idx]["Codigo"]
        if st.session_state.selected_code != code:
            st.session_state.selected_code = code
            st.rerun()

# --- TAB CONTENT ---
with tab_main:
    render_native_grid(df_visible, "grid_main")

with tab_saved:
    render_native_grid(df_saved, "grid_saved")

with tab_detail:
    if st.session_state.selected_code and st.session_state.selected_code in full_map:
        code = st.session_state.selected_code
        data = full_map[code]
        
        # --- ACTION BAR ---
        c1, c2, c3 = st.columns([1.5, 1.5, 4])
        is_saved = code in saved_ids
        
        with c1:
            label = "❌ Quitar de Guardadas" if is_saved else "⭐ Guardar Interés"
            type_btn = "secondary" if is_saved else "primary"
            if st.button(label, type=type_btn, use_container_width=True):
                db_toggle_save(code)
                st.rerun()
        
        with c2:
            if st.button("🗑️ Ocultar (Irrelevante)", type="secondary", use_container_width=True):
                db_hide_permanent(code)
                st.session_state.selected_code = None
                st.rerun()
        
        st.divider()
        
        # --- DETAIL VIEW ---
        st.subheader(data.get("Nombre"))
        st.caption(f"ID: {code} | Organismo: {data.get('Comprador', {}).get('NombreOrganismo', '')}")
        
        sec1 = data.get("ExtendedMetadata", {}).get("Section_1_Características", {})
        col1, col2 = st.columns(2)
        with col1:
             st.write(f"**Tipo:** {sec1.get('Tipo de Licitación', '-')}")
             st.write(f"**Cierre:** {data.get('Fechas', {}).get('FechaCierre', '')}")
        with col2:
             st.markdown(f"[🔗 Ver en MercadoPúblico]({data.get('URL_Publica')})")
             pres = sec1.get("Presupuesto")
             if pres: st.write(f"**Presupuesto:** :green[{pres}]")
             elif data.get("MontoEstimado"): st.write(f"**Monto:** :blue[${float(data.get('MontoEstimado',0)):,.0f}]")
        
        st.markdown("##### 📝 Descripción")
        st.info(data.get("Descripcion", "No disponible"))
        
        # Items
        items = data.get('Items', {}).get('Listado', [])
        if not items and 'DetalleArticulos' in data: items = data['DetalleArticulos']
        
        if items:
            st.markdown("###### 📦 Items / Rubros")
            st.dataframe(pd.json_normalize(items), use_container_width=True)
            
    else:
        st.markdown("<br><br><h3 style='text-align: center; color: #ccc;'>👈 Selecciona una licitación</h3>", unsafe_allow_html=True)
