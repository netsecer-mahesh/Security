from pathlib import Path
import json
import argparse
import subprocess
import tempfile



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

if len(policy_definition_files) != 1:
    raise SystemExit(
        "Expected exactly one policy definition file. Deployment stopped."
    )

if len(parameter_files) != 1:
    raise SystemExit(
        "Expected exactly one parameter file. Deployment stopped."
    )

print("Policy definition file:", policy_definition_files[0].name)
print("Parameter file:", parameter_files[0].name)

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

print("DEBUG: Both JSON files loaded successfully")

az_command_path = [r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"]

def run_az_command(command):
    full_command = az_command_path + command
    result = subprocess.run(
        full_command,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if result.returncode != 0:
            raise SystemExit(f"Azure CLI command failed: {result.stderr}")
    return result


def identify_policy(policy_name, management_group):
    policy_lookup_command = [
    "policy", "definition", "list",
    "--management-group", management_group,
    "--query",
    f"[?displayName=='{policy_name}'].{{Name:name, DisplayName:displayName, ID:id, Type:policyType}}",
    "--output", "json"
    ]

    result = run_az_command(policy_lookup_command)
    existing_policies = json.loads(result.stdout)    
    return existing_policies    
    
existing_policy = identify_policy(
    args.policy_name,
    deployment_config["managementGroup"]
)

def push_policy(policy_name, management_group, policy_definition):

    policy_properties = policy_definition["properties"]

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        # Create temporary JSON files
        rules_file = temp_path / "rules.json"
        with open(rules_file, "w", encoding="utf-8") as file:
            json.dump(policy_properties["policyRule"], file)

        policy_create_command = [
            "policy", "definition", "create",
            "--name", policy_name,
            "--management-group", management_group,
            "--display-name", policy_name,
            "--rules", str(rules_file),
            "--mode", policy_properties.get("mode", "All"),
            "--output", "json"
        ]

        if policy_properties.get("description"):
            policy_create_command.extend([
                "--description", policy_properties["description"]
            ])

        if policy_properties.get("metadata"):
            metadata_file = temp_path / "metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as file:
                json.dump(policy_properties["metadata"], file)

            policy_create_command.extend([
                "--metadata", str(metadata_file)
            ])

        if policy_properties.get("parameters"):
            params_file = temp_path / "parameters.json"
            with open(params_file, "w", encoding="utf-8") as file:
                json.dump(policy_properties["parameters"], file)

            policy_create_command.extend([
                "--params", str(params_file)
            ])

        run_az_command(policy_create_command)

    # Verify deployment
    deployed_policy = identify_policy(policy_name, management_group)

    if (
        len(deployed_policy) == 1
        and deployed_policy[0]["Name"] == policy_name
        and deployed_policy[0]["DisplayName"] == policy_name
    ):
        print("Policy deployment verified successfully.")
        return deployed_policy[0]

    else:
        raise SystemExit("Policy deployment verification failed.")
