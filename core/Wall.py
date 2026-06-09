import pandas as pd
import numpy as np

tau_threshold = 360

def init_RC_network(wall_df, chamber_position="Building Interior"):
    """
    Calculates the Resistance and Capacitance arrays.
    Automatically collapses thin/light layers (like air gaps) into pure 
    resistances to prevent numerical instability in the Euler solver.
    """
    wall_layers = wall_df.copy()
    
    # --- Clean Data ---
    numeric_cols = ['Thickness (m)', 'k', 'cp', 'rho']
    for col in numeric_cols:
        if wall_layers[col].dtype == object or wall_layers[col].dtype == str:
            wall_layers[col] = wall_layers[col].astype(str).str.replace(',', '.')
        wall_layers[col] = pd.to_numeric(wall_layers[col], errors='coerce').fillna(0.001)
    
    # Calculate base R and C
    wall_layers['R'] = wall_layers['Thickness (m)'] / wall_layers['k']
    wall_layers['C'] = wall_layers['Thickness (m)'] * wall_layers['cp'] * wall_layers['rho']
    
    # Boundary conditions
    R_se = 0.13 if chamber_position == "Building Interior" else 0.04
    R_si = 0.17
    
    dynamic_C = []
    R_network = []
    
    # We start accumulating resistance from the outside boundary
    current_R_accumulation = R_se
    
    for i in range(len(wall_layers)):
        R_i = wall_layers['R'].iloc[i]
        C_i = wall_layers['C'].iloc[i]
        tau_i = R_i * C_i
        
        if tau_i > tau_threshold:
            current_R_accumulation += R_i / 2.0
            R_network.append(current_R_accumulation)
            dynamic_C.append(C_i)
            current_R_accumulation = R_i / 2.0
        else:
            current_R_accumulation += R_i
            
    current_R_accumulation += R_si
    R_network.append(current_R_accumulation)
    
    if len(dynamic_C) == 0:
        return np.array(R_network), np.array([1.0]), 1.0 / np.sum(R_network)
    
    U_wall = 1.0 / np.sum(R_network)
    
    return np.array(R_network), np.array(dynamic_C), U_wall


def simulate_wall_transient(R, C, area, dt, T_ext_array, T_int_target):
    """
    Simulates the transient heat transfer through a single wall structure.
    
    Returns:
    - Q_wall_total: Array of heat flux entering the room from this wall in function of time (Watts)
    - T_history: Temperature history of the internal nodes
    
    """

    time_steps = len(T_ext_array)
    nb_nodes = len(C)
    
    T_ext_initial = T_ext_array[0]
    R_total = np.sum(R)
    q_steady = (T_ext_initial - T_int_target)/R_total

    R_cumulative = np.cumsum(R[:-1])
    T_nodes = T_ext_initial - (q_steady * R_cumulative)
    
    # Arrays to store outputs
    Q_wall_total = np.zeros(time_steps)
    T_history = np.zeros((time_steps, nb_nodes))
    
    for t in range(time_steps):
        T_ext = T_ext_array[t]
        
        # 1. Construct the full temperature array: [T_outside, T_node1 ... T_nodeN, T_inside]
        T_full = np.concatenate(([T_ext], T_nodes, [T_int_target]))
        
        # 2. Calculate heat flux (q) across all resistors (W/m²) q[i] = (T[i] - T[i+1])/R[i]
        q = (T_full[:-1] - T_full[1:])/R
        
        # 3. Extract heat entering the room from the wall and convert to Watts
        Q_wall_total[t] = q[-1] * area
        
        # 4. Update internal node temperatures for the next time step (Explicit Euler)
        dT_dt = (q[:-1] - q[1:])/C
        T_nodes += dT_dt*dt
        
        # Save history
        T_history[t, :] = T_nodes
        
    return Q_wall_total, T_history