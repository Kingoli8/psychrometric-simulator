import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import uuid

from core.data_loader import load_yaml
from ui.sidebar import render_sidebar
from ui.results_display import display_all_results  
import ui.expanders as exp


# ==========================================
# PAGE CONFIGURATION & INITIALIZATION
# ==========================================

st.set_page_config(
    page_title="Psychrometric Chamber Simulator",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

plt.style.use('dark_background')   

# --- 1. Load Databases ---
refrigerants_db = load_yaml("config/refrigerants.yaml")
materials_db = load_yaml("config/materials.yaml")

if "custom_materials" not in st.session_state:
    st.session_state.custom_materials = {}
full_materials_db = {**materials_db, **st.session_state.custom_materials}

if "custom_refrigerants" not in st.session_state:
    st.session_state.custom_refrigerants = {}
full_refrigerants_db = {**refrigerants_db, **st.session_state.custom_refrigerants}

# --- 2. Define Default Wall Configuration ---
default_wall_df = pd.DataFrame({
    "Material": ["PIR"], 
    "Thickness (m)": ["0.15"], 
    "k": [full_materials_db["PIR"]["k"]],
    "rho": [full_materials_db["PIR"]["rho"]], 
    "cp": [full_materials_db["PIR"]["cp"]]
}, dtype=str)

# --- 3. Initialize Session State for Zones & Results ---
def create_surface():
    return {"id": str(uuid.uuid4())[:8], "df": default_wall_df.copy()} # Creates a unique ID for each surface

if "zones" not in st.session_state:
    st.session_state.zones = {
        "Zone 1 (Indoor)": {"walls": [create_surface()]},
        "Zone 2 (Outdoor)": {"walls": [create_surface()]},
        "Shared Boundary": {"walls": [create_surface()]}
    }
    
if "thermal_results" not in st.session_state:
    st.session_state.thermal_results = {}

# ==========================================
# MAIN PAGE LAYOUT
# ==========================================

render_sidebar()

st.title("Psychrometric Chamber Simulator")

chamber_mode = st.segmented_control(
    "Chamber Configuration", 
    options=["Mono-Chamber", "Twin-Chamber"],
    default="Twin-Chamber", 
    selection_mode="single", 
    required=True,
    label_visibility="collapsed"    
)

# --- Expander 1: Wall Configuration ---
with st.expander("**Wall Configuration**", expanded=False):
    if chamber_mode == "Mono-Chamber":
        exp.render_walls_for_zone(full_materials_db, "Zone 1 (Indoor)", default_wall_df)
    elif chamber_mode == "Twin-Chamber":
        tab1, tab2, tab3 = st.tabs(["Zone 1 (Indoor)", "Zone 2 (Outdoor)", "Shared Boundary"])
        with tab1: exp.render_walls_for_zone(full_materials_db, "Zone 1 (Indoor)", default_wall_df)
        with tab2: exp.render_walls_for_zone(full_materials_db, "Zone 2 (Outdoor)", default_wall_df)
        with tab3: exp.render_walls_for_zone(full_materials_db, "Shared Boundary", default_wall_df)

# --- Expander 2: Simulation Parameters ---
with st.expander("**Simulation Parameters**", expanded=False):
    
    dt, time_steps, time_array_hours = exp.render_global_settings()
    
    st.session_state.global_time = {"dt": dt, "steps": time_steps, "hours": time_array_hours}

    st.subheader("Chamber Setpoints")
    if chamber_mode == "Mono-Chamber":
        z1 = "Zone 1 (Indoor)"
        mcol1, mcol2, mcol3 = st.columns(3, border=True)
        mcol1.number_input("Target Temp (°C)", value=-20.0, step=1.0, key=f"t_target_{z1}")
        mcol2.number_input("Appliances Heat (W)", value=0.0, step=100.0, key=f"q_app_{z1}")
        mcol3.number_input("Fan SFP [W/(m³/h)]", value=1.5, step=0.1, key=f"fan_sfp_{z1}")
        
        st.markdown("**Testbench Power**")
        exp.render_testbench_profile(z1, time_array_hours, time_steps, "Mono-Chamber")
        
    elif chamber_mode == "Twin-Chamber":
        z1 = "Zone 1 (Indoor)"
        z2 = "Zone 2 (Outdoor)"
        tcol1, tcol2 = st.columns(2)
        with tcol1:
            st.markdown("**Zone 1 (Indoor) Setpoints**")
            ttcol1, ttcol2, ttcol_f1 = st.columns(3, border=True)
            ttcol1.number_input("Target Temp (°C)", value=20.0, step=1.0, key=f"t_target_{z1}")
            ttcol2.number_input("Appliances (W)", value=200.0, step=100.0, key=f"q_app_{z1}")
            ttcol_f1.number_input("Fan SFP", value=1.5, step=0.1, key=f"fan_sfp_{z1}")
        with tcol2:
            st.markdown("**Zone 2 (Outdoor) Setpoints**")
            ttcol3, ttcol4, ttcol_f2 = st.columns(3, border=True)
            ttcol3.number_input("Target Temp (°C)", value=0.0, step=1.0, key=f"t_target_{z2}")
            ttcol4.number_input("Appliances (W)", value=200.0, step=100.0, key=f"q_app_{z2}")
            ttcol_f2.number_input("Fan SFP", value=1.5, step=0.1, key=f"fan_sfp_{z2}")
        
        tbcol1, tbcol2 = st.columns(2, border=True)
        with tbcol1:
            st.markdown("**Zone 1 Testbench Power**")
            exp.render_testbench_profile(z1, time_array_hours, time_steps, "Twin-Chamber")
        with tbcol2:
            st.markdown("**Zone 2 Testbench Power**")
            exp.render_testbench_profile(z2, time_array_hours, time_steps, "Twin-Chamber")

# --- Expander 3: Safety Parameters ---
with st.expander("**Safety Parameters (EN-378)**", expanded=False):
    def format_refrigerant(r_key):
        name = full_refrigerants_db[r_key].get('chemical_name', 'ND')
        return f"{r_key} ({name})"

    st.session_state.global_refrigerant = st.selectbox(
        "System Refrigerant", options=list(full_refrigerants_db.keys()),
        format_func=format_refrigerant, help="The fluid used inside the test bench."
    )

    pop_col1, pop_col2, pop_col3 = st.columns([0.25, 0.27, 0.5])
    with pop_col1:
        with st.popover("➕ Add Custom Refrigerant", width="content"):
            c_ref_id = st.text_input("Refrigerant ID (e.g., R-290)")
            pcol1, pcol2 = st.columns(2)
            c_ref_name = pcol1.text_input("Chemical Name")
            c_density = pcol2.number_input("Gas Density (kg/m³)", min_value=0.0, format="%.5g", value=None)
            ccol1, ccol2 = st.columns(2)
            c_class = ccol1.selectbox("Safety Class", ["A1", "A2L", "A2", "A3", "B1", "B2L", "B2", "B3"])
            c_group = ccol2.selectbox("Fluid Group", [1, 2])
            c_lfl = ccol1.number_input("LFL (kg/m³)", min_value=0.0, format="%.5g", value=None)
            c_atel = ccol2.number_input("ATEL/ODL (kg/m³)", min_value=0.0, format="%.5g", value=None)
            c_practical_limit = ccol1.number_input("Practical Limit (kg/m³)", min_value=0.0, format="%.5g", value=None)
            c_auto_ignition_temp = ccol2.number_input("Auto-Ignition Temp (°C)", format="%.5g", value=None)
            
            if st.button("Save to Session", width="content") and c_ref_id:
                st.session_state.custom_refrigerants[c_ref_id] = {
                    "chemical_name": c_ref_name if c_ref_name else "Custom", "safety_class": c_class, 
                    "fluid_group": c_group, "lfl": c_lfl, "atel_odl": c_atel,
                    "practical_limit": c_practical_limit, "auto_ignition_temp": c_auto_ignition_temp,
                    "gas_density": c_density 
                }
                st.rerun()

    with pop_col2:
        with st.popover("🔍 Refrigerant Characteristics", width="content"):
            ref_data = full_refrigerants_db[st.session_state.global_refrigerant]
            
            # 1. Create the dataframe and rename the column
            df_ref = pd.DataFrame(ref_data, index=[0]).T.rename(columns={0: "Value"})
            
            # 2. Force the entire "Value" column to be strings so PyArrow doesn't crash
            df_ref["Value"] = df_ref["Value"].astype(str)
            
            # 3. Display it safely
            st.dataframe(df_ref, width="content")

    with pop_col3:
        with st.popover("ℹ️ EN 378 Wiki", width="content"):
            try: st.markdown(Path("config/wiki.md").read_text(encoding="utf-8"))
            except FileNotFoundError: st.warning("Wiki file (config/wiki.md) not found.")

    if chamber_mode == "Mono-Chamber":
        exp.render_safety_assessment("Zone 1 (Indoor)")
    elif chamber_mode == "Twin-Chamber":
        s_tab1, s_tab2 = st.tabs(["Zone 1 Assessment", "Zone 2 Assessment"])
        with s_tab1: exp.render_safety_assessment("Zone 1 (Indoor)")
        with s_tab2: exp.render_safety_assessment("Zone 2 (Outdoor)")


# ==========================================
# SIMULATION EXECUTION & SaFETY ASSESSMENT
# ==========================================
col_btn1, col_btn2 = st.columns(2)

run_sim = col_btn1.button("🌡️ Run Thermal Simulation", type="primary", width="stretch")
run_safety = col_btn2.button("🛡️ Evaluate EN-378 Safety", type="secondary", width="stretch")

if run_sim:
    with st.spinner("Calculating transient heat transfer for all zones..."):
        exp.execute_thermal_simulation(chamber_mode, full_refrigerants_db)

if run_safety:
    with st.spinner("Evaluating EN-378 limits..."):
        exp.execute_safety_assessment(chamber_mode, full_refrigerants_db)

display_all_results(chamber_mode)