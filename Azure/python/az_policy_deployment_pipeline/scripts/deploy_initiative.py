
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

management_group = deployment_config["managementGroup"]

print("SUCCESS: Deployment configuration loaded and validated.")


# SECTION 4: INITIATIVE DISCOVERY AND FILE VALIDATION

parser = argparse.ArgumentParser()

parser.add_argument(
    "--initiative-name",
    required=True
)

parser.add_argument(
    "--policy-name",
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
assignment_parameter_files = []

for initiative_file in initiative_files:

    if initiative_file.name.endswith("_initiative.json"):
        initiative_definition_files.append(initiative_file)

    elif initiative_file.name.endswith("_parameters.json"):
        assignment_parameter_files.append(initiative_file)


if len(initiative_definition_files) != 1:
    raise SystemExit(
        "Expected exactly one initiative definition file. Deployment stopped."
    )

if len(assignment_parameter_files) > 1:
    raise SystemExit(
        "Expected maximum one assignment parameter file. Deployment stopped."
    )


selected_initiative_definition_path = (
    selected_initiative_folder / initiative_definition_files[0].name
)

print("SUCCESS: Initiative folder and definition file identified.")


# SECTION 5: INITIATIVE JSON LOADING AND VALIDATION

def load_initiative_definition(definition_path):

    with open(definition_path, "r") as initiative_file:
        initiative_definition = json.load(initiative_file)

    return initiative_definition


Initiative_definition = load_initiative_definition(
    selected_initiative_definition_path
)

initiative_properties = Initiative_definition.get("properties")

if not isinstance(initiative_properties, dict):
    raise SystemExit(
        "Invalid initiative JSON. Expected a properties object."
    )


initiative_policy_definitions = initiative_properties.get(
    "policyDefinitions"
)

if not isinstance(initiative_policy_definitions, list) or not initiative_policy_definitions:
    raise SystemExit(
        "Initiative must contain a non-empty policyDefinitions array."
    )


expected_policy_id = (
    f"/providers/Microsoft.Management/managementGroups/{management_group}"
    f"/providers/Microsoft.Authorization/policyDefinitions/{args.policy_name}"
)


def normalize_resource_id(resource_id):

    return resource_id.strip().rstrip("/").lower()


local_policy_ids = [
    normalize_resource_id(policy.get("policyDefinitionId", ""))
    for policy in initiative_policy_definitions
]


if normalize_resource_id(expected_policy_id) not in local_policy_ids:
    raise SystemExit(
        "Target policy is not included in the local initiative JSON. "
        "Deployment stopped."
    )


print("SUCCESS: Initiative JSON validated.")
print("Target policy:", args.policy_name)


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
            f"Azure CLI command failed:\n{command_result.stderr}"
        )

    return command_result


# Verify that the target policy definition exists at the configured MG.

policy_lookup_command = [
    "policy", "definition", "show",
    "--name", args.policy_name,
    "--management-group", management_group,
    "--output", "json"
]

policy_result = run_az_command(policy_lookup_command)

print("SUCCESS: Target policy definition exists at MG scope.")


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


def get_initiative_details(initiative_name, management_group):

    initiative_show_command = [
        "policy", "set-definition", "show",
        "--name", initiative_name,
        "--management-group", management_group,
        "--output", "json"
    ]

    command_result = run_az_command(initiative_show_command)

    return json.loads(command_result.stdout)


existing_initiative = identify_initiative(
    args.initiative_name,
    management_group
)

print("SUCCESS: Azure initiative lookup completed.")


# SECTION 8: INITIATIVE DEPLOYMENT AND UPDATE

def push_initiative(initiative_name, management_group, operation):

    display_name = initiative_properties.get(
        "displayName",
        initiative_name
    )

    description = initiative_properties.get("description", "")

    definitions = initiative_properties["policyDefinitions"]

    parameters = initiative_properties.get("parameters", {})
    metadata = initiative_properties.get("metadata", {})
    definition_groups = initiative_properties.get(
        "policyDefinitionGroups", []
    )

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

        definitions_path = create_temp_json(definitions)
        parameters_path = create_temp_json(parameters)
        metadata_path = create_temp_json(metadata)
        groups_path = create_temp_json(definition_groups)

        initiative_command = [
            "policy", "set-definition", operation,
            "--name", initiative_name,
            "--management-group", management_group,
            "--display-name", display_name,
            "--description", description,
            "--definitions", f"@{definitions_path}",
            "--params", f"@{parameters_path}",
            "--metadata", f"@{metadata_path}",
            "--definition-groups", f"@{groups_path}",
            "--output", "json"
        ]

        if initiative_properties.get("version"):
            initiative_command.extend([
                "--version",
                str(initiative_properties["version"])
            ])

        command_result = run_az_command(initiative_command)

        print(
            f"SUCCESS: Initiative '{initiative_name}' "
            f"{'created' if operation == 'create' else 'updated'} "
            f"at Management Group '{management_group}'."
        )

        return command_result

    finally:

        for temp_path in temporary_files:
            Path(temp_path).unlink(missing_ok=True)


# SECTION 9: DEPLOYMENT CONTROLLER

if len(existing_initiative) == 0:

    print("Initiative definition not found.")
    print("Starting initiative creation.")

    deployed_initiative = push_initiative(
        args.initiative_name,
        management_group,
        "create"
    )


elif len(existing_initiative) == 1:

    print("\nExisting initiative definition detected.")

    existing_details = get_initiative_details(
        args.initiative_name,
        management_group
    )

    # Support both flattened Azure CLI output and properties-wrapped output.

    existing_properties = existing_details.get(
        "properties",
        existing_details
    )

    existing_policy_definitions = existing_properties.get(
        "policyDefinitions",
        []
    )

    print("\nExisting initiative details:")
    print("Name:", existing_details.get("name"))
    print("Display Name:", existing_properties.get("displayName"))
    print("Resource ID:", existing_details.get("id"))

    print("\nPolicies currently included:")

    for policy in existing_policy_definitions:

        print(
            "-",
            policy.get("policyDefinitionId"),
            "| Reference:",
            policy.get("policyDefinitionReferenceId")
        )

    existing_policy_ids = [
        normalize_resource_id(
            policy.get("policyDefinitionId", "")
        )
        for policy in existing_policy_definitions
    ]

    if normalize_resource_id(expected_policy_id) in existing_policy_ids:

        print("\nTarget policy already exists in this initiative.")

        raise SystemExit(
            "Deployment stopped. No initiative update required."
        )

    else:

        print("\nWARNING: Target policy is NOT included in the existing initiative.")
        print("Target policy:", expected_policy_id)

        print("\nContinuing will update the existing initiative using")
        print("the complete definition in the local initiative JSON.")

        user_choice = input(
            "\nContinue with initiative update? [C]ontinue / [A]bort: "
        ).strip().lower()

        if user_choice == "c":

            updated_initiative = push_initiative(
                args.initiative_name,
                management_group,
                "update"
            )

        elif user_choice == "a":

            raise SystemExit(
                "User aborted initiative update. No changes made."
            )

        else:

            raise SystemExit(
                "Invalid selection. Deployment stopped."
            )


else:

    raise SystemExit(
        "Multiple matching initiatives found. Manual investigation required."
    )
