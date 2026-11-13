from pathlib import Path
import json
import argparse
import subprocess
import tempfile
from unittest import result



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
print("DEBUG: Policy parameters:")
print(json.dumps(
    Policy_definition["properties"]["parameters"],
    indent=4
))
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

    command_result = run_az_command(policy_lookup_command)
    existing_policies = json.loads(command_result.stdout)
    return existing_policies

print("DEBUG: Starting Azure policy lookup")

existing_policy = identify_policy(
    args.policy_name,
    deployment_config["managementGroup"]
)

print("DEBUG: Azure lookup result:", existing_policy)



def push_policy(policy_name, management_group):
   
    policy_rule = {
        "if": {
            "field": "type",
            "equals": "Microsoft.Network/networkSecurityGroups"
             },
        "then": {
             "effect": "[parameters('nsgEffect')]"
            }
        }
    

    # Define policy parameters
    policy_parameters = {
        "nsgEffect": {
            "type": "String",
            "metadata": {
                "displayName": "NSG Policy Effect",
                "description": "Effect applied to matching NSG rules."
            },
            "allowedValues": [
                "Audit",
                "Deny",
                "Disabled"
            ],
            "defaultValue": "Audit"
        }
    }
    
    policy_definition_file = load_policy_definition(selected_policy_definition_path)

    policy_rule = policy_definition_file["properties"]["policyRule"]

    policy_parameters = policy_definition_file["properties"]["parameters"]

    assignment_parameters = load_parameter_file(selected_parameter_path)


    print("DEBUG: Extracted policy rule:")
    print(json.dumps(policy_rule, indent=4))

    print("DEBUG: Extracted policy parameters:")
    print(json.dumps(policy_parameters, indent=4))
    print("DEBUG: Extracted assignment parameters:")
    print(json.dumps(assignment_parameters, indent=4))

    with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", encoding="utf-8",
    delete=False
        ) as rules_file:
        json.dump(policy_rule, rules_file)
    rules_path = rules_file.name

    with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", encoding="utf-8",
    delete=False
        ) as params_file:
        json.dump(policy_parameters, params_file)
    params_path = params_file.name

  

    policy_create_command = [
        "policy",
        "definition",
        "create",
        "--name", policy_name,
        "--management-group", management_group,
        "--display-name", policy_name,
        "--description", "Temporary NSG audit policy for deployment testing",
        "--mode", "All",
        "--rules", f"@{rules_path}",
        "--params", f"@{params_path}",
        "--output", "json"
    ]

    print("DEBUG: Azure CLI arguments:")
    for item in policy_create_command:
        print(repr(item))

    command_result= run_az_command(policy_create_command)

    print("Policy creation response:")
    print(command_result.stdout)

    return command_result


if len(existing_policy) == 0:

    print(
        "Policy definition not found. Starting deployment in:",
        deployment_config["managementGroup"]
    )

    deployed_policy = push_policy(
        args.policy_name,
        deployment_config["managementGroup"]
    )


elif len(existing_policy) == 1:

    print("Policy definition found:")
    print("Resource Name:", existing_policy[0]["Name"])
    print("Display Name:", existing_policy[0]["DisplayName"])
    print("Resource ID:", existing_policy[0]["ID"])
    print("Policy Type:", existing_policy[0]["Type"])

    raise SystemExit(
        "Policy already exists. Existing-policy workflow not implemented."
    )

else:
    raise SystemExit(
        "Multiple matching policies found. Deployment stopped."
    )