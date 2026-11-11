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

for policy_file in policy_files:
    print("Policy file:", policy_file.name)