import os
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==========================================
# ⚙️ PDF EXPORT SETTINGS
# ==========================================
# Toggle this to True to automatically save all generated graphs as PDFs
SAVE_PLOTS_AS_PDF = True  

def save_plot_to_pdf(fig, filename):
    """Helper function to save Matplotlib figures to a local 'Pdf' directory."""
    if SAVE_PLOTS_AS_PDF:
        if not os.path.exists("Pdf"):
            os.makedirs("Pdf")
        filepath = os.path.join("Pdf", f"{filename}.pdf")
        fig.savefig(filepath, bbox_inches='tight')

# ==========================================
# MASTER DASHBOARD ROUTER
# ==========================================

def display_all_results(chamber_mode):
    """Master display function managing the Tabs and Prompts for the results."""
    st.header("📊 Results Dashboard")

    tab_thermal, tab_safety = st.tabs(["🌡️ Thermal Simulation", "🛡️ Safety Assessment"])

    has_thermal = bool(st.session_state.thermal_results)
    has_safety = any("safety_results" in z_data for z_data in st.session_state.zones.values())

    # --- TAB 1: THERMAL ---
    with tab_thermal:
        if not has_thermal:
            st.info("ℹ️ No thermal simulation data available. Click **'Run Thermal Simulation'** above to run the physics engine.")
        else:
            if chamber_mode == "Mono-Chamber":
                _display_zone_thermal_results("Zone 1 (Indoor)")
            elif chamber_mode == "Twin-Chamber":
                t_tab1, t_tab2 = st.tabs(["Zone 1 (Indoor)", "Zone 2 (Outdoor)"])
                with t_tab1: 
                    _display_zone_thermal_results("Zone 1 (Indoor)")
                with t_tab2: 
                    _display_zone_thermal_results("Zone 2 (Outdoor)")

    # --- TAB 2: SAFETY ---
    with tab_safety:
        if not has_safety:
            st.info("ℹ️ No safety assessment data available. Click **'Evaluate EN-378 Safety'** above to run the assessment.")
        else:
            if chamber_mode == "Mono-Chamber":
                _display_zone_safety_results("Zone 1 (Indoor)")
            elif chamber_mode == "Twin-Chamber":
                s_tab1, s_tab2 = st.tabs(["Zone 1 (Indoor)", "Zone 2 (Outdoor)"])
                with s_tab1:
                    _display_zone_safety_results("Zone 1 (Indoor)")
                with s_tab2:
                    _display_zone_safety_results("Zone 2 (Outdoor)")

def _display_zone_thermal_results(zone_name):
    """Helper to cleanly stack all Thermal results for a given zone with fail-safes."""
    if zone_name in st.session_state.thermal_results:
        res = st.session_state.thermal_results[zone_name]
        
        display_heat_transfer_results(res["Q_hvac"], res["dt"], res["time_hours"], zone_name)
        plot_energy_balance(res, zone_name)
        wall_hist = res.get("wall_hist", {}) 
        plot_wall_temperatures(wall_hist, res["time_hours"], zone_name)
    else:
        st.warning(f"⚠️ No thermal simulation data found for **{zone_name}**. Make sure to click **'Run Thermal Simulation'** in the right chamber mode.")

def _display_zone_safety_results(zone_name):
    """Helper to cleanly display Safety results for a given zone with fail-safes."""
    z_data = st.session_state.zones.get(zone_name, {})
    if "safety_results" in z_data:
        display_safety_results(z_data["safety_results"])
    else:
        st.warning(f"⚠️ No safety assessment data found for **{zone_name}**. Make sure to click **'Evaluate EN-378 Safety'** in the right chamber mode.")


# ==========================================
# SPECIFIC DISPLAY FUNCTIONS & CHARTS
# ==========================================

def display_heat_transfer_results(total_Q_hvac, dt, time_array_hours, zone_title):
    """Displays metric cards and the total HVAC power plot."""
    st.subheader(f"HVAC Requirements & Energy Consumption")
    
    total_kw = total_Q_hvac/1000.0
    heating_kw = np.maximum(total_kw, 0) # Positive values are retained
    cooling_kw = np.abs(np.minimum(total_kw, 0)) # Negative values are retained and inverted to positive for display reasons
    
    dt_hours = dt/3600.0
    heating_energy_kwh = np.sum(heating_kw)*dt_hours
    cooling_energy_kwh = np.sum(cooling_kw)*dt_hours
    total_energy_kwh = heating_energy_kwh + cooling_energy_kwh

    heating_max_kw = np.max(heating_kw)
    cooling_max_kw = np.max(cooling_kw)
    
    col_chart, col_metric = st.columns([0.8, 0.2])
    
    with col_metric:
        st.write("") 
        st.metric(label="Total Energy Used", value=f"{total_energy_kwh:.1f} kWh", help="The total thermal equivalent energy required by the HVAC system over the simulation period.")
        st.markdown(f"**🔥 Heating:** {heating_energy_kwh:.1f} kWh")
        st.markdown(f"**Max heating power:** {heating_max_kw:.1f} kW")
        st.markdown(f"**❄️ Cooling:** {cooling_energy_kwh:.1f} kWh")
        st.markdown(f"**Max cooling power:** {cooling_max_kw:.1f} kW")

    with col_chart:
        fig_res, ax_res = plt.subplots(figsize=(10, 4))
        
        ax_res.plot(time_array_hours, heating_kw, color='#FF4B4B', linewidth=2, label="Heating Capacity")
        ax_res.fill_between(time_array_hours, heating_kw, 0, color='#FF4B4B', alpha=0.3)
        ax_res.plot(time_array_hours, cooling_kw, color='#29B5E8', linewidth=2, label="Cooling Capacity")
        ax_res.fill_between(time_array_hours, cooling_kw, 0, color='#29B5E8', alpha=0.3)
        
        ax_res.set_ylabel("Absolute HVAC Power (kW)", fontweight='bold')
        ax_res.set_xlabel("Time (hours)", fontweight='bold')
        ax_res.set_ylim(bottom=0, top=max(heating_max_kw, cooling_max_kw)*1.5) 
        ax_res.grid(True, linestyle='--', alpha=0.7)
        ax_res.legend(loc="upper right")
        
        st.pyplot(fig_res)
        save_plot_to_pdf(fig_res, f"HVAC_Power_{zone_title.replace(' ', '_')}")
        plt.close(fig_res)

def plot_energy_balance(res, zone_title):
    """Plots the Wall Heat Transfer."""
    st.subheader("Wall Heat Transfer")
    fig, ax = plt.subplots(figsize=(10, 3))
    
    ax.plot(res["time_hours"], res["Q_wall"], label="Wall Heat Transfer (W)", color="#FF4B4B")
    
    ax.set_xlabel("Time (h)", fontweight='bold')
    ax.set_ylabel("Power (W)", fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    
    st.pyplot(fig)
    save_plot_to_pdf(fig, f"Wall_Heat_Transfer_{zone_title.replace(' ', '_')}")
    plt.close(fig)

def plot_wall_temperatures(wall_hist, time_hours, zone_title):
    """Plots the temperature evolution of the nodes inside every surface, with ambient baselines."""
    st.subheader("Wall Node Temperature Profiles")
    
    # 1. Build a smart reverse-mapping dictionary to find the Human-Readable Name & DataFrame from the UID
    uid_mapping = {}
    for z_name, z_data in st.session_state.zones.items():
        for i, surface in enumerate(z_data.get("walls", [])):
            clean_name = f"Surface {i+1} (Shared)" if z_name == 'Shared Boundary' else f"Surface {i+1}"
            
            uid_mapping[surface["id"]] = {
                "name": clean_name,
                "df": surface["df"],
                "origin_zone": z_name
            }
            
    T_target_zone = st.session_state.get(f"t_target_{zone_title}", 20.0)
    
    for uid, T_hist in wall_hist.items():
        fig, ax = plt.subplots(figsize=(10, 4))
        num_nodes = T_hist.shape[1]
        
        # 2. Extract metadata using our mapping
        mapping = uid_mapping.get(uid)
        surface_name = mapping["name"] if mapping else f"Surface {uid}"
        df = mapping["df"] if mapping else None
        origin_zone = mapping["origin_zone"] if mapping else zone_title
        
        # 3. Dynamically determine the External Temperature array (T_ext)
        boundary = st.session_state.get(f"bound_{origin_zone}_{uid}", "Building interior")
        if "Shared" in boundary:
            other_z_name = "Zone 2 (Outdoor)" if zone_title == "Zone 1 (Indoor)" else "Zone 1 (Indoor)"
            T_ext_val = st.session_state.get(f"t_target_{other_z_name}", 20.0)
            T_ext_array = np.ones_like(time_hours) * T_ext_val
        else:
            T_ext_array = st.session_state.get("T_ext_array", np.ones_like(time_hours) * 20.0)
            
        # 4. Plot the Ambient/Reference lines (Target & External)
        ax.plot(time_hours, T_ext_array, label="Ambient: External", color='white', linestyle=':', linewidth=2, alpha=0.8)
        ax.plot(time_hours, np.ones_like(time_hours) * T_target_zone, label="Ambient: Target", color='yellow', linestyle=':', linewidth=2, alpha=0.8)

        # 5. Build Material Spatial Mapping
        node_materials = []
        if df is not None:
            try:
                # Convert string thicknesses (e.g., "0,15") to floats safely
                thicknesses = pd.to_numeric(df["Thickness (m)"].astype(str).str.replace(",", "."), errors='coerce').fillna(0.001).values
                materials = df["Material"].values
                total_thickness = np.sum(thicknesses)
                cum_thickness = np.cumsum(thicknesses)
                
                for n in range(num_nodes):
                    # Calculate physical depth of this specific finite-difference node
                    depth = min((n / (num_nodes - 1)) * total_thickness, total_thickness)
                    
                    # Find which layer this physical depth falls into
                    layer_idx = np.searchsorted(cum_thickness, depth, side='right')
                    layer_idx = min(layer_idx, len(materials) - 1)
                    node_materials.append(materials[layer_idx])
            except Exception:
                node_materials = ["Layer"] * num_nodes
        else:
            node_materials = ["Layer"] * num_nodes

        # 6. Determine which nodes to plot and label to avoid legend clutter
        if num_nodes <= 15:
            nodes_to_plot = list(range(num_nodes)) # Plot all of them
        else:
            step = max(1, (num_nodes - 2) // 5)
            nodes_to_plot = [0] + list(range(1, num_nodes - 1, step))[:5] + [num_nodes - 1]

        # 7. Plotting loop
        for n in range(num_nodes):
            if n in nodes_to_plot:
                label = f"Node {n} ({node_materials[n]})"
                
                line_weight = 2 if (n == 0 or n == num_nodes - 1) else 1.5
                ax.plot(time_hours, T_hist[:, n], label=label, linewidth=line_weight)
            else:
                ax.plot(time_hours, T_hist[:, n], color='gray', alpha=0.2)
            
        ax.set_ylabel("Temperature (°C)", fontweight='bold')
        ax.set_xlabel("Time (hours)", fontweight='bold')
        ax.set_title(f"Thermal Profile: {surface_name}")
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        
        st.pyplot(fig)
        save_plot_to_pdf(fig, f"Temp_Profile_{zone_title.replace(' ', '_')}_{surface_name.replace(' ', '_')}")
        plt.close(fig)

def display_safety_results(results):
    """Displays the safety compliance banners and soft warnings."""
    if results.get("bypassed"):
        st.info(results["message"])
        return
    elif results.get("error"):
        st.error(results["message"])
        return

    if results["is_compliant"]:
        st.success(f"✅ **COMPLIANT:** Testbench charge ({results['user_charge']} kg) is safely below the limit.")
    else:
        st.error(f"❌ **VIOLATION:** Testbench charge ({results['user_charge']} kg) exceeds the allowable limit!")

    col1, col2, col3, col4, col5 = st.columns([0.15, 0.25, 0.2, 0.2, 0.2])
    
    col1.metric("Safety Class", results["safety_class"])
    
    if results["max_allowable_charge"] == float('inf'):
        col2.metric("Max Allowable Charge", "No Restriction")
        col3.metric("User Charge", f"{results['user_charge']:.2f} kg", delta="Safe")
    else:
        col2.metric("Max Allowable Charge", f"{results['max_allowable_charge']:.2f} kg")
        col2.caption(f"**Limiting Factor:** {results['limiting_factor']}")
        delta_val = results["max_allowable_charge"] - results["user_charge"]
        col3.metric("User Charge", f"{results['user_charge']:.2f} kg", delta=f"{delta_val:.2f} kg margin")
        
    ventilation = results.get("required_ventilation_m3h")
    emerg_vent = results.get("emergency_ventilation_m3s")
    
    # --- Column 4: Minimum Ventilation ---
    if ventilation is not None:
        col4.metric("Min. Ventilation", f"{ventilation:.1f} m³/h")
    else:
        col4.metric("Min. Ventilation", "N/A")
        
    # --- Column 5: Emergency Exhaust ---
    if emerg_vent is not None and emerg_vent > 0:
        emerg_vent_m3h = emerg_vent * 3600
        col5.metric("Emergency Exhaust", f"{emerg_vent_m3h:.1f} m³/h", help=f"EN 378-3 Raw Output: {emerg_vent:.4f} m³/s")
    else:
        col5.metric("Emergency Exhaust", "N/A")

    # --- Contextual Banners ---
    if ventilation is not None and emerg_vent is not None:
        st.info("💨 **Ventilation Requirements (EN 378-2 & 3):** Continuous minimum ventilation is required during normal operation. Emergency mechanical exhaust must be triggered by a leak detector.")
    elif ventilation is None and emerg_vent is None:
        st.warning("⚠️ **Missing Data:** Ventilation could not be calculated. Please ensure the 'density' is defined for this specific refrigerant in your database.")