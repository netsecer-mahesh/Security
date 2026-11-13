
# ============================================================
# SECTION 1: IMPORTS AND PROJECT INITIALIZATION
# Purpose: Import required libraries and define project paths.
# ============================================================

from pathlib import Path
import json
import argparse
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
POLICY_DIR = PROJECT_ROOT / "policies"

az_command_path = [
    r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
]


# ============================================================
# SECTION 2: CONFIGURATION DISCOVERY
# Purpose: Discover and select the deployment configuration.
# ============================================================

config_files = list(CONFIG_DIR.glob("*.json"))

if len(config_files) == 0:
    raise SystemExit("No configuration files found. Deployment stopped.")

elif len(config_files) == 1:
    selected_file = config_files[0].name
    selected_path = CONFIG_DIR / selected_file

else:
    for config_file in config_files:
        print("Available configuration:", config_file.name)

    selected_file = input("Enter configuration filename: ")
    selected_path = CONFIG_DIR / selected_file

if not selected_path.exists():
    raise SystemExit("Invalid configuration filename. Deployment stopped.")

print("SUCCESS: Deployment configuration selected.")


# ============================================================
# SECTION 3: CONFIGURATION LOADING AND VALIDATION
# Purpose: Load configuration and validate mandatory settings.
# ============================================================

def load_deployment_config(selected_path):

    with open(selected_path, "r") as file:
        deployment_config = json.load(file)

    return deployment_config


def validate_config(config):

    required_keys = ["managementGroup", "initiativeId"]

    for key in required_keys:

        if not config.get(key):
            raise SystemExit(
                f"Missing required key: {key}. Deployment stopped."
            )

    return True


deployment_config = load_deployment_config(selected_path)

validate_config(deployment_config)

print("SUCCESS: Deployment configuration loaded and validated.")


# ============================================================
# SECTION 4: POLICY DISCOVERY AND FILE VALIDATION
# Purpose: Identify the selected policy folder and locate its
# definition and assignment parameter JSON files.
# ============================================================

parser = argparse.ArgumentParser()

parser.add_argument("--policy-name", required=True)

args = parser.parse_args()

policy_folders = list(POLICY_DIR.iterdir())


def validate_policy_name(policy_name):

    for folder in policy_folders:

        if folder.is_dir() and folder.name == policy_name:
            return True

    return False


if not validate_policy_name(args.policy_name):
    raise SystemExit("Invalid policy name. Deployment stopped.")


selected_policy_folder = POLICY_DIR / args.policy_name

policy_files = list(selected_policy_folder.glob("*.json"))

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


selected_policy_definition_path = (
    selected_policy_folder / policy_definition_files[0].name
)

selected_parameter_path = (
    selected_policy_folder / parameter_files[0].name
)

print("SUCCESS: Policy folder and required JSON files identified.")


# ============================================================
# SECTION 5: POLICY JSON LOADING
# Purpose: Load the policy definition and assignment parameters
# into Python for subsequent deployment operations.
# ============================================================

def load_policy_definition(policy_definition_path):

    with open(policy_definition_path, "r") as policy_file:
        policy_definition = json.load(policy_file)

    return policy_definition


def load_parameter_file(parameter_path):

    with open(parameter_path, "r") as parameter_file:
        parameters = json.load(parameter_file)

    return parameters


Policy_definition = load_policy_definition(
    selected_policy_definition_path
)

Parameters = load_parameter_file(
    selected_parameter_path
)

print("SUCCESS: Policy definition and assignment parameters loaded.")


# ============================================================
# SECTION 6: AZURE CLI COMMAND EXECUTION
# Purpose: Execute Azure CLI commands and handle command errors.
# ============================================================

def run_az_command(command):

    full_command = az_command_path + command

    command_result = subprocess.run(
        full_command,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if command_result.returncode != 0:
        raise SystemExit(
            f"Azure CLI command failed: {command_result.stderr}"
        )

    return command_result


# ============================================================
# SECTION 7: EXISTING POLICY IDENTIFICATION
# Purpose: Query Azure at Management Group scope and identify
# whether the selected policy definition already exists.
# ============================================================

def identify_policy(policy_name, management_group):

    policy_lookup_command = [
        "policy",
        "definition",
        "list",
        "--management-group", management_group,
        "--query",
        f"[?displayName=='{policy_name}'].{{Name:name, DisplayName:displayName, ID:id, Type:policyType}}",
        "--output", "json"
    ]

    command_result = run_az_command(policy_lookup_command)

    existing_policies = json.loads(command_result.stdout)

    return existing_policies


existing_policy = identify_policy(
    args.policy_name,
    deployment_config["managementGroup"]
)

print("SUCCESS: Azure policy lookup completed.")


# ============================================================
# SECTION 8: POLICY DEFINITION DEPLOYMENT
# Purpose: Extract the policy rule and parameter definitions,
# prepare temporary JSON files, and create the policy in Azure.
# ============================================================

def push_policy(policy_name, management_group):

    # Extract policy rule from the local definition file
    policy_rule = Policy_definition["properties"]["policyRule"]

    # Extract parameter definitions from the local definition file
    policy_parameters = Policy_definition["properties"]["parameters"]

    # Assignment values are loaded separately for future assignment use
    assignment_parameters = Parameters

    # Prepare temporary JSON file containing the policy rule
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        encoding="utf-8",
        delete=False
    ) as rules_file:

        json.dump(policy_rule, rules_file)
        rules_path = rules_file.name

    # Prepare temporary JSON file containing policy parameter definitions
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        encoding="utf-8",
        delete=False
    ) as params_file:

        json.dump(policy_parameters, params_file)
        params_path = params_file.name

    # Construct Azure CLI policy creation command
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

    command_result = run_az_command(policy_create_command)

    print(
        f"SUCCESS: Policy definition '{policy_name}' deployed "
        f"to Management Group '{management_group}'."
    )

    return command_result


# ============================================================
# SECTION 9: DEPLOYMENT CONTROLLER
# Purpose: Decide whether to create the policy or stop deployment
# when an existing policy requires manual investigation.
# ============================================================

if len(existing_policy) == 0:

    print("Policy definition not found. Starting deployment.")

    deployed_policy = push_policy(
        args.policy_name,
        deployment_config["managementGroup"]
    )


elif len(existing_policy) == 1:

    print("Policy definition already exists.")
    print("Resource Name:", existing_policy[0]["Name"])
    print("Display Name:", existing_policy[0]["DisplayName"])
    print("Resource ID:", existing_policy[0]["ID"])
    print("Policy Type:", existing_policy[0]["Type"])

    raise SystemExit(
        "Deployment stopped. Please review the existing policy manually."
    )


else:

    raise SystemExit(
        "Multiple matching policies found. Manual investigation required."
    )
