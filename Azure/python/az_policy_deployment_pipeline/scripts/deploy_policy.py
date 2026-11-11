from pathlib import Path
import json
import argparse



PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
config_files = list(CONFIG_DIR.glob("*.json"))
print("Total configuration files:", len(config_files))

if len(config_files) == 0:
    print("No configuration files found.")
    raise SystemExit("Deployment stopped: configuration missing.")
elif len(config_files) == 1:
    selected_file = config_files[0].name
    print("Configuration selected:", selected_file)
    selected_path = CONFIG_DIR / selected_file
   
else:
    for config_file in CONFIG_DIR.glob("*.json"):
            print("Available configuration:", config_file.name)
    selected_file = input("Enter configuration filename: ")
    print("Selected configuration:", selected_file)
    selected_path = CONFIG_DIR / selected_file
       
print("selected_path", selected_path)    
if not selected_path.exists():
    raise SystemExit("Invalid configuration filename. Deployment stopped.")

def display_config(config):

    for key, value in config.items():
        print(key, ":", value)


def load_deployment_config(selected_path):

    with open(selected_path, "r") as file:
        deployment_config = json.load(file)

    return deployment_config
deployment_config = load_deployment_config(selected_path)

required_keys = ["managementGroup", "initiativeId"]

def validate_config(config):
    for key in required_keys:
        if not config.get(key):
            raise SystemExit(f"Missing required key: {key}. Deployment stopped.")
          
        else:
            print(f"{key} = {config.get(key)}")
    print("Configuration validated successfully")

validate_config(deployment_config)

POLICY_DIR = PROJECT_ROOT / "policies"

print("Policy Directory:", POLICY_DIR)
print("Directory Exists:", POLICY_DIR.exists())

policy_folders = list(POLICY_DIR.iterdir())

def validate_policy_name(policy_name):
    for folder in policy_folders:
        if folder.is_dir() and folder.name == policy_name:
            print(f"Policy : {policy_name}  found in {folder.parent}")
        
            return True
    return False
parser = argparse.ArgumentParser()

parser.add_argument("--policy-name", required=True)

args = parser.parse_args()

print("Selected Policy:", args.policy_name)

if not validate_policy_name(args.policy_name):
    raise SystemExit("Invalid policy name. Deployment stopped.")

selected_policy_folder = POLICY_DIR / args.policy_name

policy_files = list(selected_policy_folder.glob("*.json"))

print("Total policy JSON files:", len(policy_files))

policy_definition_files = []
parameter_files = []

for policy_file in policy_files:
    if policy_file.name.endswith("_policy.json"):
        policy_definition_files.append(policy_file)

    elif policy_file.name.endswith("_parameters.json"):
        parameter_files.append(policy_file)


if len(policy_definition_files) == 1 and len(parameter_files) == 1:
    print("Policy definition file:", policy_definition_files[0].name)
    print("Parameter file:", parameter_files[0].name)   
elif len(policy_definition_files) == 0:
    raise SystemExit("No policy definition file found. Deployment stopped.")
elif len(parameter_files) == 0:
    raise SystemExit("No parameter file found. Deployment stopped.")

selected_policy_definition_path = POLICY_DIR / args.policy_name / policy_definition_files[0].name
print("Selected policy definition path:", selected_policy_definition_path)
selected_parameter_path = POLICY_DIR / args.policy_name / parameter_files[0].name
print("Selected parameter path:", selected_parameter_path)

def load_policy_definition(policy_definition_path):
    with open(policy_definition_path, "r") as policy_file:
        policy_definition = json.load(policy_file)
    return policy_definition

def load_parameter_file(parameter_path):
    with open(parameter_path, "r") as parameter_file:
        parameters = json.load(parameter_file)
    return parameters

Policy_definition = load_policy_definition(selected_policy_definition_path)
Parameters = load_parameter_file(selected_parameter_path)