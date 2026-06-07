# ui/sidebar.py
import streamlit as st
import pandas as pd

from core.data_loader import load_scenarios, save_scenario


def render_sidebar():
    """Renders the sidebar, handles scenario saving/loading, and basic inputs."""
    st.sidebar.header("🗂️ Scenario Manager")
    
    scenarios = load_scenarios()
    scenario_names = ["Default"] + list(scenarios.keys())

    col1, col2 = st.sidebar.columns([0.7,0.3], vertical_alignment="bottom")

    with col1:
        selected_scenario = st.selectbox("Load Scenario", options=scenario_names)
    
    with col2:
        if st.button("Load"):
            if selected_scenario != "Default":
                data = scenarios[selected_scenario]
                # Overwrite session state with loaded data
                st.session_state.refrigerant = data["refrigerant"]
                st.session_state.room_vol = data["room_vol"]
                st.session_state.charge = data["charge"]
                st.session_state.walls = [pd.DataFrame(w) for w in data["walls"]] # Adapted for your list of walls!
                st.rerun()
        
    st.sidebar.divider()

    st.sidebar.subheader("💾 Save Current State")

    col1, col2 = st.sidebar.columns([0.7,0.3], vertical_alignment="bottom")

    with col1:
        new_scenario_name = st.text_input("Scenario Name")
    with col2:
        if st.button("Save"):
            if new_scenario_name:
                
                walls_to_save = st.session_state.walls
                
                current_data = {
                    "refrigerant": st.session_state.refrigerant,
                    "room_vol": st.session_state.room_vol,
                    "charge": st.session_state.charge,
                    # Convert the active DataFrames back to dictionaries for YAML
                    "walls": [w.to_dict(orient="records") for w in walls_to_save]
                }
                save_scenario(new_scenario_name, current_data)
                st.sidebar.success(f"Saved '{new_scenario_name}'!")
            else:
                st.sidebar.error("Please enter a name.")