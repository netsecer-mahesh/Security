from pathlib import Path
import json

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

display_config(deployment_config)