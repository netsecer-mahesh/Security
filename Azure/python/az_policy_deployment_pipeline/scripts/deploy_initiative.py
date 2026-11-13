
# SECTION 1: IMPORTS AND PROJECT INITIALIZATION

from pathlib import Path
import json
import argparse
import subprocess
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
INITIATIVE_DIR = PROJECT_ROOT / "initiatives"

az_command_path = [
    r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
]


# SECTION 2: CONFIGURATION DISCOVERY

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


# SECTION 3: CONFIGURATION LOADING AND VALIDATION

def load_deployment_config(selected_path):
    with open(selected_path, "r") as file:
        deployment_config = json.load(file)

    return deployment_config


def validate_config(config):

    required_keys = ["managementGroup"]

    for key in required_keys:
        if not config.get(key):
            raise SystemExit(
                f"Missing required key: {key}. Deployment stopped."
            )

    return True


deployment_config = load_deployment_config(selected_path)

validate_config(deployment_config)

print("SUCCESS: Deployment configuration loaded and validated.")


# SECTION 4: INITIATIVE DISCOVERY AND FILE VALIDATION

parser = argparse.ArgumentParser()

parser.add_argument(
    "--initiative-name",
    required=True
)

args = parser.parse_args()

initiative_folders = list(INITIATIVE_DIR.iterdir())


def validate_initiative_name(initiative_name):

    for folder in initiative_folders:

        if folder.is_dir() and folder.name == initiative_name:
            return True

    return False


if not validate_initiative_name(args.initiative_name):
    raise SystemExit("Invalid initiative name. Deployment stopped.")


selected_initiative_folder = INITIATIVE_DIR / args.initiative_name

initiative_files = list(selected_initiative_folder.glob("*.json"))

initiative_definition_files = []
parameter_files = []

for initiative_file in initiative_files:

    if initiative_file.name.endswith("_initiative.json"):
        initiative_definition_files.append(initiative_file)

    elif initiative_file.name.endswith("_parameters.json"):
        parameter_files.append(initiative_file)


if len(initiative_definition_files) != 1:
    raise SystemExit(
        "Expected exactly one initiative definition file. Deployment stopped."
    )

if len(parameter_files) > 1:
    raise SystemExit(
        "Expected maximum one parameter file. Deployment stopped."
    )


selected_initiative_definition_path = (
    selected_initiative_folder / initiative_definition_files[0].name
)

selected_parameter_path = (
    selected_initiative_folder / parameter_files[0].name
    if parameter_files else None
)

print("SUCCESS: Initiative folder and definition file identified.")


# SECTION 5: INITIATIVE JSON LOADING AND VALIDATION

def load_initiative_definition(initiative_definition_path):

    with open(initiative_definition_path, "r") as initiative_file:
        initiative_definition = json.load(initiative_file)

    return initiative_definition


def load_parameter_file(parameter_path):

    with open(parameter_path, "r") as parameter_file:
        parameters = json.load(parameter_file)

    return parameters


Initiative_definition = load_initiative_definition(
    selected_initiative_definition_path
)

Assignment_parameters = None

if selected_parameter_path:
    Assignment_parameters = load_parameter_file(selected_parameter_path)


if not isinstance(Initiative_definition.get("properties"), dict):
    raise SystemExit(
        "Invalid initiative JSON structure. Expected properties object."
    )


initiative_properties = Initiative_definition["properties"]

if not initiative_properties.get("policyDefinitions"):
    raise SystemExit(
        "No policy definitions found in initiative. Deployment stopped."
    )

if not isinstance(initiative_properties["policyDefinitions"], list):
    raise SystemExit(
        "policyDefinitions must be an array. Deployment stopped."
    )

print("SUCCESS: Initiative definition loaded and validated.")


# SECTION 6: AZURE CLI COMMAND EXECUTION

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


# SECTION 7: EXISTING INITIATIVE IDENTIFICATION

def identify_initiative(initiative_name, management_group):

    initiative_lookup_command = [
        "policy", "set-definition", "list",
        "--management-group", management_group,
        "--query",
        f"[?name=='{initiative_name}'].{{Name:name, DisplayName:displayName, ID:id, Type:policyType}}",
        "--output", "json"
    ]

    command_result = run_az_command(initiative_lookup_command)

    existing_initiatives = json.loads(command_result.stdout)

    return existing_initiatives


existing_initiative = identify_initiative(
    args.initiative_name,
    deployment_config["managementGroup"]
)

print("SUCCESS: Azure initiative lookup completed.")


# SECTION 8: INITIATIVE DEFINITION DEPLOYMENT

def push_initiative(initiative_name, management_group):

    initiative_definitions = initiative_properties["policyDefinitions"]

    initiative_parameters = initiative_properties.get("parameters")
    initiative_metadata = initiative_properties.get("metadata")
    initiative_groups = initiative_properties.get("policyDefinitionGroups")

    display_name = initiative_properties.get(
        "displayName",
        initiative_name
    )

    description = initiative_properties.get("description")
    version = initiative_properties.get("version")

    temporary_files = []

    def create_temp_json(data):

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            encoding="utf-8",
            delete=False
        ) as temp_file:

            json.dump(data, temp_file)
            temp_path = temp_file.name

        temporary_files.append(temp_path)

        return temp_path

    try:

        definitions_path = create_temp_json(initiative_definitions)

        initiative_create_command = [
            "policy", "set-definition", "create",
            "--name", initiative_name,
            "--management-group", management_group,
            "--display-name", display_name,
            "--definitions", f"@{definitions_path}",
            "--output", "json"
        ]

        if description:
            initiative_create_command.extend([
                "--description", description
            ])

        if initiative_parameters:
            params_path = create_temp_json(initiative_parameters)

            initiative_create_command.extend([
                "--params", f"@{params_path}"
            ])

        if initiative_metadata:
            metadata_path = create_temp_json(initiative_metadata)

            initiative_create_command.extend([
                "--metadata", f"@{metadata_path}"
            ])

        if initiative_groups:
            groups_path = create_temp_json(initiative_groups)

            initiative_create_command.extend([
                "--definition-groups", f"@{groups_path}"
            ])

        if version:
            initiative_create_command.extend([
                "--version", str(version)
            ])

        command_result = run_az_command(
            initiative_create_command
        )

        print(
            f"SUCCESS: Initiative '{initiative_name}' deployed "
            f"to Management Group '{management_group}'."
        )

        return command_result

    finally:

        for temp_path in temporary_files:
            Path(temp_path).unlink(missing_ok=True)


# SECTION 9: DEPLOYMENT CONTROLLER

if len(existing_initiative) == 0:

    print("Initiative definition not found. Starting deployment.")

    deployed_initiative = push_initiative(
        args.initiative_name,
        deployment_config["managementGroup"]
    )

elif len(existing_initiative) == 1:

    print("Initiative definition already exists.")

    print("Resource Name:", existing_initiative[0]["Name"])
    print("Display Name:", existing_initiative[0]["DisplayName"])
    print("Resource ID:", existing_initiative[0]["ID"])
    print("Type:", existing_initiative[0]["Type"])

    raise SystemExit(
        "Deployment stopped. Please review the existing initiative manually."
    )

else:

    raise SystemExit(
        "Multiple matching initiatives found. Manual investigation required."
    )
