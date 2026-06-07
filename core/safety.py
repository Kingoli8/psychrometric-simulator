
def safety_warnings(ref_data):
    """
    Checks the refrigerant dictionary for missing values before computation.
    Returns: (can_compute: bool, issues: list of tuples)
    """
    issues = []
    can_compute = True
    
    safety_class = ref_data.get("safety_class", "")
    if not safety_class or safety_class.lower() == "none":
        issues.append(("error", "Safety Class is missing."))
        return False, issues

    tox_class = safety_class[0].upper()
    flam_class = safety_class[1:].upper() if len(safety_class) > 1 else "ND"

    # Critical Check: LFL is mandatory for Flammable classes (2L, 2, 3)
    if flam_class in ["2L", "2", "3"]:
        lfl = ref_data.get("lfl")
        if lfl is None or float(lfl) <= 0:
            issues.append(("error", f"LFL is strictly required for Flammability Class {flam_class}."))
            can_compute = False

    # Critical Check: Practical Limit mandatory for Highly Toxic Class B
    if tox_class == "B":
        p_limit = ref_data.get("practical_limit")
        if p_limit is None or float(p_limit) <= 0:
            issues.append(("error", "Practical Limit is required for Toxicity Class B."))
            can_compute = False
            
    # Non-Critical Checks (Soft Warnings)
    if ref_data.get("auto_ignition_temp") is None:
        issues.append(("warning", "Auto-ignition temperature not defined."))
    if ref_data.get("atel_odl") is None:
        issues.append(("warning", "ATEL/ODL not defined."))
        
    return can_compute, issues


def check_en378_limits(ref_id, ref_data, volume, charge, location, access, upbel, pers_dens):
    """Computes EN-378 maximum allowable charge limits."""
    
    # EXTRACT AND NORMALIZE DATA
    safety_class = ref_data.get("safety_class", "A1")
    tox_class = safety_class[0].upper()
    flam_class = safety_class[1:].upper() if len(safety_class) > 1 else "ND"
    
    acc = access.split()[-1].lower()
    loc = location.split()[-1].upper()
    
    v = float(volume)
    lfl_val = ref_data.get("lfl")
    l = float(lfl_val) if lfl_val is not None else 0.0
    
    m1 = 4 * l
    m2 = 26.0 * l
    m3 = 130.0 * l
    practical_limit = ref_data.get("practical_limit")
    p_lim = float(practical_limit) if practical_limit is not None else 0.0
    atel_odl = ref_data.get("atel_odl")
    a_o = float(atel_odl) if atel_odl is not None else 0.0

    # ==========================================
    # EN-378 TOXICITY LIMIT CALCULATIONS
    # ==========================================
    tox_limit = max(a_o, p_lim)
    tox_limit_table = float('inf')
    if loc == 'III' or loc == 'IV': tox_limit_table = float('inf')

    elif tox_class == 'A':
        tox_limit_table = tox_limit * v if (acc == 'a' or upbel) else float('inf')

    elif tox_class == 'B':
        if acc == 'a' or (acc == 'b' and upbel and loc == 'I'): tox_limit_table = tox_limit * v
        elif (acc == 'b' and loc == 'II' and (upbel or not pers_dens)) or (acc == 'c' and not pers_dens and loc == 'II'): tox_limit_table = 25.0
        elif (acc == 'b' and loc == 'I') or (acc == 'c' and not pers_dens and loc == 'I'): tox_limit_table = 10.0
        elif acc == 'c' and pers_dens and loc == 'I': tox_limit_table = 50.0
        else: tox_limit_table = float('inf')
    tox_charge_limit = max(tox_limit_table, 20*tox_limit, 0.150 if tox_class == 'A' else 0.0)

    # ==========================================
    # EN-378 FLAMMABILITY LIMIT CALCULATIONS (Assuming application is not for human comfort and above ground)
    # ==========================================
    flam_limit_table = float('inf')
    if l > 0 and flam_class in ['2L', '2', '3']:
        if flam_class == '2L':
            if loc == 'III': flam_limit_table = float('inf')
            elif loc == 'IV': flam_limit_table = m3 * 1.5
            elif acc == 'a': flam_limit_table = min(0.20 * l * v, m2 * 1.5)
            elif acc == 'b' or acc == 'c': flam_limit_table = min(0.20 * l * v, m2 * 1.5) if loc == 'I' else min(0.20 * l * v, 25.0)

        elif flam_class == '2':
            if loc == 'III': flam_limit_table = float('inf')
            elif loc == 'IV': flam_limit_table = m3
            elif acc == 'a' or acc == 'b': flam_limit_table = min(0.20 * l * v, m2)
            elif acc == 'c': flam_limit_table = min(0.20 * l * v, 10.0) if loc == 'I' else min(0.20 * l * v, 25.0)

        elif flam_class == '3':
            if loc == 'IV': flam_limit_table = m3
            elif acc == 'a': 
                flam_limit_table = min(0.20 * l * v, 1.5) if loc in ['I', 'II'] else 5.0
            elif acc == 'b':
                flam_limit_table = min(0.20 * l * v, 2.5) if loc in ['I', 'II'] else 10.0
            elif acc == 'c':
                if loc == 'I': flam_limit_table = min(0.20 * l * v, 10.0)
                elif loc == 'II': flam_limit_table = min(0.20 * l * v, 25.0)
                elif loc == 'III': flam_limit_table = float('inf')
    flam_charge_limit = max(flam_limit_table, m1*1.5 if flam_class == '2L' else 0.0, m1 if flam_class == '2' or flam_class == '3' else 0.0, 0.150)


    # ==========================================
    # FINAL EVALUATION
    # ==========================================
    max_charge = min(tox_charge_limit, flam_charge_limit) if flam_class is not 1 else tox_charge_limit
    
    if max_charge == float('inf'): limiting_factor = "No Restriction"
    elif max_charge == tox_charge_limit: limiting_factor = "Toxicity Limit"
    else: limiting_factor = "Flammability Limit"

    is_compliant = charge <= max_charge

    return {
        "refrigerant": ref_id,
        "safety_class": safety_class,
        "chamber_volume": v,
        "user_charge": charge,
        "max_allowable_charge": max_charge,
        "limiting_factor": limiting_factor,
        "is_compliant": is_compliant
    }

def en378_ventilation(charge, rho, s=4.0):
    """
    Computes the minimum ventilation required by EN 378-2 as well as the emergency ventilation rate required by EN 378-3.
    Q_min = 15 * s * (m_c / rho) >= 2 m³/h
    V_dot_emergency = 0.014 * m_c^2/3
    """
    if rho is None or rho <= 0:
        return None # Cannot compute without density
        
    q_calculated = 15.0*s*(charge/rho)
    
    # Must be at least 2 m³/h
    q_min = max(q_calculated, 2.0)
    
    # Emergency ventilation rate
    v_dot_emergency = 0.014*charge**(2/3)
    
    return q_min, v_dot_emergency


