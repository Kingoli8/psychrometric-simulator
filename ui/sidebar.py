import streamlit as st
import pandas as pd
import yaml

# We define the prefixes of all the widget keys we want to save
WIDGET_PREFIXES = (
    "t_target_", "q_app_", "fan_sfp_", "area_", "bound_",
    "q_tb_mode_", "q_c_", "q_on_", "q_off_", "q_cyc_",
    "s_vol_", "s_vunit_", "s_charge_", "s_loc_", "s_acc_", "s_upbel_", "s_pers_",
    "t_ext_mode", "t_ext_val", "mean_temp", "amp_temp", "chamber_mode"
)

def render_sidebar():
    """Renders the sidebar, handles scenario export/import, and complex state serialization."""
    st.sidebar.header("🗂️ Scenario Manager")
    st.sidebar.caption("Save scenarios directly to your computer to save the current state of the inputs.")

    st.sidebar.divider()
    st.sidebar.subheader("📤 Export Scenario")

    # --- 1. EXPORT (Download) ---
    scenario_data = _get_serializable_state()
    # Convert the dictionary to a YAML string in memory
    yaml_str = yaml.dump(scenario_data, default_flow_style=False, sort_keys=False)

    st.sidebar.download_button(
        label="⬇️ Download Current State (.yaml)",
        data=yaml_str,
        file_name="psychrometric_scenario.yaml",
        mime="text/yaml",
        use_container_width=True
    )

    st.sidebar.divider()
    st.sidebar.subheader("📥 Import Scenario")

    # --- 2. IMPORT (Upload) ---
    uploaded_file = st.sidebar.file_uploader("Upload a saved scenario", type=['yaml', 'yml'], label_visibility="collapsed")

    if uploaded_file is not None:
        if st.sidebar.button("Load Uploaded Scenario", type="primary", use_container_width=True):
            try:
                loaded_data = yaml.safe_load(uploaded_file)
                _load_state_from_scenario(loaded_data)
                st.sidebar.success("Scenario loaded successfully!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error loading file: {e}")

# --- HELPER FUNCTIONS ---

def _get_serializable_state():
    """Extracts nested data and converts DataFrames to dicts for YAML serialization."""
    data = {
        "zones": {},
        "custom_materials": st.session_state.get("custom_materials", {}),
        "custom_refrigerants": st.session_state.get("custom_refrigerants", {}),
        "global_refrigerant": st.session_state.get("global_refrigerant", "R290"),
        "widgets": {}
    }
    
    # 1. Serialize Zones (DataFrames -> dictionaries)
    for z_name, z_data in st.session_state.zones.items():
        data["zones"][z_name] = {"walls": []}
        for w in z_data["walls"]:
            data["zones"][z_name]["walls"].append({
                "id": w["id"],
                "df": w["df"].to_dict(orient="records")
            })
            
    # 2. Serialize standard Streamlit widget states based on engineering prefixes
    for key, val in st.session_state.items():
        if key.startswith(WIDGET_PREFIXES):
            data["widgets"][key] = val
            
    return data

def _load_state_from_scenario(scenario_data):
    """Reconstructs the Streamlit session state from a loaded YAML dictionary."""
    # 1. Restore Zones (dictionaries -> DataFrames) 
    if "zones" in scenario_data:
        restored_zones = {}
        for z_name, z_data in scenario_data["zones"].items():
            restored_zones[z_name] = {"walls": []}
            for w in z_data["walls"]:
                # Force DataFrame to strings so st.data_editor validation doesn't crash on floats
                restored_zones[z_name]["walls"].append({
                    "id": w["id"],
                    "df": pd.DataFrame(w["df"]).astype(str) 
                })
        st.session_state.zones = restored_zones

    # 2. Restore Database Additions & Global Selections
    if "custom_materials" in scenario_data:
        st.session_state.custom_materials = scenario_data["custom_materials"]
    if "custom_refrigerants" in scenario_data:
        st.session_state.custom_refrigerants = scenario_data["custom_refrigerants"]
    if "global_refrigerant" in scenario_data:
        st.session_state.global_refrigerant = scenario_data["global_refrigerant"]

    # 3. Restore Widget Inputs directly into session_state
    if "widgets" in scenario_data:
        for key, val in scenario_data["widgets"].items():
            st.session_state[key] = val