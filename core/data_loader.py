import yaml
import os

SCENARIO_FILE = "config/scenarios.yaml" 


def load_yaml(filepath):
    """Loads a YAML file and returns a dictionary."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing configuration file: {filepath}")
        
    with open(filepath, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)
    
def load_scenarios():
    """Loads saved scenarios from a local YAML file."""
    if os.path.exists(SCENARIO_FILE):
        with open(SCENARIO_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) 
            return data if data is not None else {}
    return {}

def save_scenario(name, data):
    """Saves the current scenario to the YAML file."""
    scenarios = load_scenarios()
    scenarios[name] = data
    with open(SCENARIO_FILE, "w", encoding="utf-8") as f:
        # default_flow_style=False ensures it writes as a clean block layout, not inline brackets
        yaml.dump(scenarios, f, default_flow_style=False, sort_keys=False)