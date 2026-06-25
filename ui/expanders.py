import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import uuid

from ui.wall_schematics import draw_wall_layers
from core.Wall import init_RC_network, simulate_wall_transient
from core.safety import en378_ventilation, safety_warnings, check_en378_limits

unit_to_seconds = {"Days": 86400, "Hours": 3600, "Minutes": 60, "Seconds": 1}

# --- STATE HELPER FUNCTION ---
def init_state(key, default_val, cast_to_float=False):
    """Elegantly initializes session state and prevents YAML float-crashes."""
    if key not in st.session_state:
        st.session_state[key] = default_val
    elif cast_to_float:
        st.session_state[key] = float(st.session_state[key])

# ==========================================
# EXPANDER RENDERING FUNCTIONS
# ==========================================

def render_walls_for_zone(full_materials_db, zone_name, default_wall_df):
    """Renders the UI for adding, editing, and deleting walls for a specific zone."""
    zone_data = st.session_state.zones[zone_name]
    
    for i, surface in enumerate(zone_data["walls"]):
        uid = surface["id"]
        wall_df = surface["df"] 

        header_col, button_col = st.columns([0.8, 0.2], vertical_alignment="bottom")
        with header_col:
            st.subheader(f"Surface {i + 1}")
        with button_col:
            if len(zone_data["walls"]) > 1:
                if st.button("🗑️ Remove", key=f"del_{zone_name}_{uid}", width="content"):
                    zone_data["walls"].pop(i)
                    st.rerun()

        scol1, scol2 = st.columns(2, vertical_alignment="bottom")
        with scol1:
            default_area = 16.0 if zone_name == "Shared Boundary" else 64.0
            init_state(f"area_{zone_name}_{uid}", default_area, cast_to_float=True)
            st.number_input("Wall Area (m²)", min_value=0.01, step=1.0, key=f"area_{zone_name}_{uid}")
        with scol2:
            if zone_name == "Shared Boundary":
                st.info("Boundary is strictly the adjacent zone (Zone 1 ↔ Zone 2)")
                st.session_state[f"bound_{zone_name}_{uid}"] = "Shared (Zone 1 ↔ Zone 2)"
            else:
                init_state(f"bound_{zone_name}_{uid}", "Building interior")
                st.selectbox("External Boundary Condition", options=["Building interior", "Open air"], key=f"bound_{zone_name}_{uid}")

        edited_wall_df = st.data_editor(
            wall_df, key=f"editor_{zone_name}_{uid}", num_rows="dynamic",
            column_config={
                "Material": st.column_config.SelectboxColumn("Material", options=list(full_materials_db.keys()), required=True),
                "Thickness (m)": st.column_config.TextColumn("Thickness (m)", validate=r"^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", required=True),
                "k": st.column_config.TextColumn("k [W/(m.K)]", validate=r"^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", required=False),
                "rho": st.column_config.TextColumn("ρ [kg/m³]", validate=r"^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", required=False),
                "cp": st.column_config.TextColumn("Cp [J/(kg.K)]", validate=r"^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$", required=False)
            },
            width="stretch"
        )

        needs_rerun = False
        if len(edited_wall_df) != len(wall_df): needs_rerun = True

        for idx, row in edited_wall_df.iterrows():
            is_new_row = idx not in wall_df.index
            material_changed = not is_new_row and row['Material'] != wall_df.at[idx, 'Material']
            
            if (is_new_row or material_changed) and pd.notna(row['Material']):
                mat = row['Material']
                if mat in full_materials_db:
                    edited_wall_df.at[idx, 'k'] = str(full_materials_db[mat].get('k', 'ND'))
                    edited_wall_df.at[idx, 'rho'] = str(full_materials_db[mat].get('rho', 'ND'))
                    edited_wall_df.at[idx, 'cp'] = str(full_materials_db[mat].get('cp', 'ND'))
                    needs_rerun = True

        if needs_rerun:
            zone_data["walls"][i]["df"] = edited_wall_df
            st.rerun()

        clean_df = edited_wall_df.copy()
        for col in ["Thickness (m)", "k", "rho", "cp"]:
            clean_df[col] = clean_df[col].str.replace(",", ".")  
            clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0.001)

        plot_df = clean_df.copy()
        plot_df['Color'] = plot_df['Material'].apply(lambda x: full_materials_db[x].get('color', "#F505A1"))
        draw_wall_layers(plot_df, unique_key=f"plot_{zone_name}_{uid}")
        
        current_area = st.session_state.get(f"area_{zone_name}_{uid}", 50.0)
        current_bound = st.session_state.get(f"bound_{zone_name}_{uid}", "Building Interior")
        
        U_wall = init_RC_network(clean_df, chamber_position=current_bound)[2]
        AU_wall = U_wall*current_area
        st.caption(f"Overall heat transfer coefficient: AU = {AU_wall:.4f} W/(m².K)")
        st.write("")

    btn_col, mat_add_col, mat_manage_col = st.columns([0.19, 0.2, 0.61])
    
    with btn_col:
        if st.button("➕ Add Another Surface", key=f"add_btn_{zone_name}", width="content"):
            zone_data["walls"].append({
                "id": str(uuid.uuid4())[:8], 
                "df": default_wall_df.copy()
            })
            st.rerun()
            
    with mat_add_col:
        with st.popover("🧱 Add Custom Material", width="content"):
            pop_col1, pop_col2 = st.columns(2)
            with pop_col1:
                c_name = st.text_input("Material Name", placeholder="Glass", key=f"c_name_{zone_name}")
                c_k = st.text_input("k [W/(m.K)]", placeholder="0.5", key=f"c_k_{zone_name}")
            with pop_col2:
                c_rho = st.text_input("ρ [kg/m³]", placeholder="150", key=f"c_rho_{zone_name}")
                c_cp = st.text_input("Cp [J/(kg.K)]", placeholder="800", key=f"c_cp_{zone_name}")

            all_fields_filled = bool(c_name and c_k and c_rho and c_cp)

            if st.button("➕ Add to Library", key=f"add_lib_btn_{zone_name}", width="content"):
                if not all_fields_filled:
                    st.error("⚠️ Please fill out all 4 fields before adding.")
                elif c_name in full_materials_db or c_name in st.session_state.custom_materials:
                    st.warning(f"⚠️ The material '{c_name}' already exists!")
                else:
                    custom_palette = ["#2ECC71", "#9B59B6", "#3498DB", "#E67E22", "#1ABC9C", "#E74C3C", "#34495E", "#F1C40F"]
                    color_index = len(st.session_state.custom_materials) % len(custom_palette)
                    st.session_state.custom_materials[c_name] = {
                        "k": c_k, "rho": c_rho, "cp": c_cp, "color": custom_palette[color_index]
                    }
                    st.rerun()

    with mat_manage_col:
        if st.session_state.custom_materials:        
            with st.popover("🛠️ Manage Custom Materials", width="content"):
                st.markdown("**Custom Materials Library:**")
                for mat_name in list(st.session_state.custom_materials.keys()):
                    is_used = any(mat_name in surface['df']['Material'].values for z_data in st.session_state.zones.values() for surface in z_data["walls"])
                    
                    d_col1, d_col2 = st.columns([0.75, 0.25], vertical_alignment="center")
                    with d_col1: 
                        st.write(f"• {mat_name}")
                    with d_col2:
                        help_text = "Cannot delete: currently used in a wall." if is_used else "Delete material"
                        if st.button("❌", key=f"del_mat_{mat_name}_{zone_name}", disabled=is_used, help=help_text):
                            st.session_state.custom_materials.pop(mat_name)
                            st.rerun()

def render_global_settings():
    """Renders the global settings part of the expander"""
    col1, col2 = st.columns([0.6, 0.4], vertical_alignment="bottom")
    cont1 = col1.container(border=True)
    cont2 = col2.container(border=True)

    with cont1:
        ccol1, ccol2 = st.columns([0.3, 0.7])
        
        init_state("t_ext_mode_summary", "Constant")
        t_ext_mode = ccol1.selectbox("External Temperature", ["Constant", "Sine Wave", "File Upload"], key="t_ext_mode_summary")

        ccol3, ccol4 = st.columns([0.7, 0.3])
        sccol3, sccol4 = ccol3.columns([0.6, 0.4])
        sim_time = sccol3.number_input("Duration", value=24.0, step=1.0)
        sim_unit = sccol4.selectbox("Unit", ["Days", "Hours", "Minutes", "Seconds"], index=1, label_visibility="hidden")
        sim_seconds = sim_time * unit_to_seconds[sim_unit]

        dt = ccol4.number_input("Time Step (s)", min_value=1, value=60, step=10)
        time_steps = int(sim_seconds/dt)
        time_array_hours = (np.arange(time_steps)*dt)/3600

        if t_ext_mode == "Constant":
            init_state("t_ext_val_summary", 20.0, cast_to_float=True)
            t_ext_val = ccol2.number_input("Constant Temp (°C)", step=0.5, key="t_ext_val_summary")
            T_ext_array = np.ones(time_steps) * t_ext_val
            
        elif t_ext_mode == "Sine Wave":
            sccol1, sccol2 = ccol2.columns([0.5, 0.5])
            init_state("mean_temp_summary", 15.0, cast_to_float=True)
            init_state("amp_temp_summary", 10.0, cast_to_float=True)
            
            mean_temp = sccol1.number_input("Mean Temp (°C)", step=1.0, key="mean_temp_summary")
            amplitude = sccol2.number_input("Amplitude (± °C)", step=1.0, key="amp_temp_summary")
            T_ext_array = mean_temp + amplitude * np.sin(2 * np.pi * time_array_hours / 24 - np.pi/2)
            
        elif t_ext_mode == "File Upload":
            t_ext_file = ccol2.file_uploader("Upload Temp Profile", type=['csv', 'xlsx'], key="t_ext_file_summary", label_visibility="collapsed")
            if t_ext_file is not None:
                df_t = pd.read_csv(t_ext_file) if t_ext_file.name.endswith('.csv') else pd.read_excel(t_ext_file)
                T_ext_array = np.interp(time_array_hours, df_t.iloc[:, 0], df_t.iloc[:, 1])
            else:
                T_ext_array = np.ones(time_steps) * 20.0 

    with cont2:
        fig_temp, ax_temp = plt.subplots(figsize=(6, 2.25))
        ax_temp.plot(time_array_hours, T_ext_array, color='#FF4B4B')
        ax_temp.set_ylabel("Temp (°C)")
        ax_temp.set_xlabel("Time (h)")
        ax_temp.grid(True, linestyle=':', alpha=0.6)
        st.pyplot(fig_temp)
        plt.close(fig_temp) 
        
        st.session_state.T_ext_array = T_ext_array

    return dt, time_steps, time_array_hours

def render_testbench_profile(zone_name, time_array_hours, time_steps, mode):
    """Renders the UI for the testbench power profile"""
    if mode == "Mono-Chamber":
        input_col, plot_col = st.columns([0.6, 0.4], vertical_alignment="bottom")
    else:
        input_col = st.container()
        plot_col = st.container()

    with input_col:
        init_state(f"q_tb_mode_{zone_name}", "Constant")
        q_tb_mode = st.segmented_control("Testbench Profile Type", ["Constant", "Step Cycle (On/Off)", "File Upload"], key=f"q_tb_mode_{zone_name}")
        
        if q_tb_mode == "Constant":
            default_power = -7000.0 if zone_name == "Zone 2 (Outdoor)" else 10000.0
            init_state(f"q_c_{zone_name}", default_power, cast_to_float=True)
            q_tb_val = st.number_input("Constant Load (W)", step=1000.0, key=f"q_c_{zone_name}")
            Q_tb_array = np.ones(time_steps)*q_tb_val
            
        elif q_tb_mode == "Step Cycle (On/Off)":
            s_col1, s_col2, s_col3 = st.columns(3)
            init_state(f"q_on_{zone_name}", -200.0, cast_to_float=True)
            init_state(f"q_off_{zone_name}", 0.0, cast_to_float=True)
            init_state(f"q_cyc_{zone_name}", 5.0, cast_to_float=True)
            
            q_on = s_col1.number_input("ON Power (W)", step=100.0, key=f"q_on_{zone_name}")
            q_off = s_col2.number_input("OFF Power (W)", step=100.0, key=f"q_off_{zone_name}")
            cycle_hours = s_col3.number_input("Cycle (hours)", step=0.5, key=f"q_cyc_{zone_name}")
            Q_tb_array = np.where((time_array_hours % cycle_hours) < (cycle_hours / 2), q_on, q_off)
            
        elif q_tb_mode == "File Upload":
            q_tb_file = st.file_uploader("Upload Power Profile (in W)", type=['csv', 'xlsx'], key=f"q_file_{zone_name}")
            if q_tb_file is not None:
                df_q = pd.read_csv(q_tb_file) if q_tb_file.name.endswith('.csv') else pd.read_excel(q_tb_file)
                Q_tb_array = np.interp(time_array_hours, df_q.iloc[:, 0], df_q.iloc[:, 1])
            else:
                Q_tb_array = np.zeros(time_steps)

    with plot_col:
        fig_w = 6 if mode == "Mono-Chamber" else 5
        fig_h = 2.25 if mode == "Mono-Chamber" else 2
        
        fig_tb, ax_tb = plt.subplots(figsize=(fig_w, fig_h))
        ax_tb.plot(time_array_hours, Q_tb_array/1000, color='#0068C9')
        ax_tb.set_ylabel("Power (kW)")
        ax_tb.set_xlabel("Time (h)")
        ax_tb.grid(True, linestyle=':', alpha=0.6)
        
        st.pyplot(fig_tb)
        plt.close(fig_tb) 
    
    st.session_state[f"q_tb_array_{zone_name}"] = Q_tb_array

def render_safety_assessment(zone_name):
    """Renders the UI for EN-378 inputs for a specific zone."""
    col1, col2 = st.columns(2, border=True)
    with col1:
        vcol1, vcol2 = st.columns([0.7, 0.3], vertical_alignment="bottom")
        
        init_state(f"s_vol_{zone_name}", 64.0, cast_to_float=True)
        init_state(f"s_vunit_{zone_name}", "m³")
        init_state(f"s_charge_{zone_name}", 2.0, cast_to_float=True)
        
        vcol1.number_input("Chamber Volume", min_value=0.1, step=1.0, key=f"s_vol_{zone_name}")
        vcol2.selectbox("Unit", ["m³", "L"], key=f"s_vunit_{zone_name}", label_visibility="collapsed")
        st.number_input("Refrigerant Charge (kg)", min_value=0.0, step=0.1, key=f"s_charge_{zone_name}")
        
    with col2:
        init_state(f"s_loc_{zone_name}", "Class III")
        init_state(f"s_acc_{zone_name}", "Category c")
        st.selectbox("Location Class", ["Class I", "Class II", "Class III", "Class IV"], key=f"s_loc_{zone_name}")
        st.selectbox("Access Category", ["Category a", "Category b", "Category c"], key=f"s_acc_{zone_name}")
        
    bcol1, bcol2 = st.columns(2)
    init_state(f"s_upbel_{zone_name}", False)
    init_state(f"s_pers_{zone_name}", True)
    
    bcol1.checkbox("Upper floors or below ground", key=f"s_upbel_{zone_name}", help="No emergency exits available.")
    bcol2.checkbox("Personnel Density < 1 person/10m²", key=f"s_pers_{zone_name}")

# ==========================================
# EXECUTION SIMULATION FUNCTIONS
# ==========================================

def execute_thermal_simulation(chamber_mode, full_refrigerants_db):
    """Calculates transient heat transfer through walls and determines necessary HVAC power."""

    dt = st.session_state.global_time["dt"]
    time_hours = st.session_state.global_time["hours"]
    time_steps = st.session_state.global_time["steps"]
    T_ext_array = st.session_state.T_ext_array
    
    st.session_state.thermal_results = {}
    active_zones = ["Zone 1 (Indoor)"] if chamber_mode == "Mono-Chamber" else ["Zone 1 (Indoor)", "Zone 2 (Outdoor)"]
    
    for z_name in active_zones:
        
        # 1. Retrieve parameters
        T_target = st.session_state[f"t_target_{z_name}"]
        Q_app = st.session_state[f"q_app_{z_name}"]
        Fan_SFP = st.session_state[f"fan_sfp_{z_name}"]
        Q_tb_array = st.session_state[f"q_tb_array_{z_name}"]
        
        # 2. Fan Heat Logic
        charge = st.session_state.get(f"s_charge_{z_name}", 0.0)
        rho = float(full_refrigerants_db[st.session_state.global_refrigerant].get("density", 0))
        if rho > 0 and charge > 0:
            ventilation = en378_ventilation(charge, rho)[0]
        else:
            ventilation = 0.0
            
        Q_fan_watts = ventilation*Fan_SFP
        Q_internal = Q_tb_array + Q_app + Q_fan_watts
        total_Q_walls = np.zeros(time_steps)
        
        # 3. Retrieve surface data
        wall_data_list = []
        for surface in st.session_state.zones[z_name]["walls"]:
            wall_data_list.append((z_name, surface["id"], surface["df"]))
            
        if chamber_mode == "Twin-Chamber":
            for surface in st.session_state.zones["Shared Boundary"]["walls"]:
                wall_data_list.append(("Shared Boundary", surface["id"], surface["df"]))
            
            other_z_name = "Zone 2 (Outdoor)" if z_name == "Zone 1 (Indoor)" else "Zone 1 (Indoor)"
            T_target_other_zone = st.session_state[f"t_target_{other_z_name}"]

        # 4. Simulation Loop
        wall_hist = {}
        for origin_zone, uid, wall_df in wall_data_list:
            
            area = st.session_state[f"area_{origin_zone}_{uid}"]
            boundary = st.session_state[f"bound_{origin_zone}_{uid}"]
            
            R, C, U_wall = init_RC_network(wall_df, chamber_position=boundary)
            
            if boundary == "Shared (Zone 1 ↔ Zone 2)":
                current_T_ext_array = np.ones(time_steps) * T_target_other_zone
            else:
                current_T_ext_array = T_ext_array
                
            Q_wall_flux, T_hist = simulate_wall_transient(
                R, C, area=area, dt=dt, 
                T_ext_array=current_T_ext_array, T_int_target=T_target
            )
            total_Q_walls += Q_wall_flux
            wall_hist[uid] = T_hist
            
        # Global Energy Balance
        total_Q_hvac_required = - (total_Q_walls + Q_internal)
            
        st.session_state.thermal_results[z_name] = {
            "Q_hvac": total_Q_hvac_required, 
            "Q_wall": total_Q_walls,
            "dt": dt, 
            "time_hours": time_hours, 
            "wall_hist": wall_hist
        }

def execute_safety_assessment(chamber_mode, full_refrigerants_db):
    """Calculates EN-378 safety limits based on the flattened state parameters."""
    active_zones = ["Zone 1 (Indoor)"] if chamber_mode == "Mono-Chamber" else ["Zone 1 (Indoor)", "Zone 2 (Outdoor)"]
    
    for z_name in active_zones:
        charge = st.session_state.get(f"s_charge_{z_name}", 0.0)
        
        if charge <= 0:
            st.session_state.zones[z_name]["safety_results"] = {"bypassed": True, "message": f"No refrigerant charge present in {z_name}. Assessment bypassed."}
            continue

        selected_ref_data = full_refrigerants_db[st.session_state.global_refrigerant]
        can_compute, warnings = safety_warnings(selected_ref_data)

        if not can_compute:
            st.session_state.zones[z_name]["safety_results"] = {"error": True, "message": "Critical data missing: " + ", ".join([f"{msg[1]}" for msg in warnings if msg[0] == "error"])}
        else:
            raw_vol = st.session_state[f"s_vol_{z_name}"]
            vol_unit = st.session_state[f"s_vunit_{z_name}"]
            actual_vol = raw_vol / 1000.0 if vol_unit == "L" else raw_vol
            
            results = check_en378_limits(
                ref_id=st.session_state.global_refrigerant, 
                ref_data=selected_ref_data,
                volume=actual_vol, 
                charge=charge, 
                location=st.session_state[f"s_loc_{z_name}"],
                access=st.session_state[f"s_acc_{z_name}"], 
                upbel=st.session_state[f"s_upbel_{z_name}"], 
                pers_dens=not st.session_state[f"s_pers_{z_name}"] 
            )
                        
            rho = selected_ref_data.get("density")
            
            if rho is not None and float(rho) > 0:
                q_min, v_dot_emerg = en378_ventilation(charge, float(rho))
                results["required_ventilation_m3h"] = q_min
                results["emergency_ventilation_m3s"] = v_dot_emerg
            else:
                results["required_ventilation_m3h"] = None
                results["emergency_ventilation_m3s"] = None

            st.session_state.zones[z_name]["safety_results"] = results