
import argparse
import json
import subprocess
import tempfile
import os
from pathlib import Path


API_VERSION = "2025-11-01"
ARM_ENDPOINT = "https://management.azure.com"

# Resolve files relative to repository root
BASE_DIR = Path(__file__).resolve().parent.parent


def az_rest(method, url, body=None):
    """Execute Azure REST API through Azure CLI."""

    command = [
        "az.cmd",
        "rest",
        "--method", method,
        "--url", url,
        "--output", "json"
    ]

    temp_file = None

    try:
        if body is not None:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                encoding="utf-8",
                delete=False
            ) as f:
                json.dump(body, f, indent=2)
                temp_file = f.name

            command.extend(["--body", f"@{temp_file}"])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr or result.stdout
            )

        return (
            json.loads(result.stdout)
            if result.stdout.strip()
            else {}
        )

    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


def resolve_file(file_path):
    """Resolve relative paths from repository root."""

    path = Path(file_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.is_file():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return path


def find_initiative(mg, initiative_input):
    """
    Resolve initiative using its full ARM resource ID
    or exact resource name.
    """

    expected_prefix = (
        f"/providers/Microsoft.Management/"
        f"managementGroups/{mg}/providers/"
        f"Microsoft.Authorization/policySetDefinitions/"
    )

    # Full ARM resource ID supplied
    if initiative_input.startswith("/"):
        if not initiative_input.lower().startswith(
            expected_prefix.lower()
        ):
            raise ValueError(
                "Initiative resource ID does not belong "
                f"to Management Group {mg}"
            )

        print(f"Using initiative ID: {initiative_input}")
        return initiative_input

    # Discover initiative by exact resource name
    mg_url = (
        f"{ARM_ENDPOINT}/providers/Microsoft.Management/"
        f"managementGroups/{mg}/providers/"
        f"Microsoft.Authorization"
    )

    print("Discovering initiative resource ID...")

    response = az_rest(
        "GET",
        f"{mg_url}/policySetDefinitions"
        f"?api-version={API_VERSION}"
    )

    definitions = response.get("value", [])

    for item in definitions:
        if item.get("name") == initiative_input:
            print("Initiative found.")
            print(f"Resource ID: {item['id']}")
            return item["id"]

    raise ValueError(
        f"Initiative '{initiative_input}' not found "
        f"at Management Group '{mg}'. "
        "Supply its full ARM resource ID."
    )


def deploy_policy(args):

    mg = args.management_group

    policy_file = resolve_file(args.policy_file)
    parameter_file = resolve_file(args.parameter_file)

    policy_data = json.loads(
        policy_file.read_text(encoding="utf-8")
    )

    parameters = json.loads(
        parameter_file.read_text(encoding="utf-8")
    )

    policy_name = args.policy_name
    reference_id = args.reference_id or policy_name

    mg_scope = (
        f"/providers/Microsoft.Management/"
        f"managementGroups/{mg}"
    )

    # ARM API URL base
    base_url = (
        f"{ARM_ENDPOINT}{mg_scope}"
        "/providers/Microsoft.Authorization"
    )

    # IMPORTANT:
    # Policy definition reference must be a relative ARM ID.
    # Do not include https://management.azure.com
    policy_id = (
        f"{mg_scope}/providers/Microsoft.Authorization/"
        f"policyDefinitions/{policy_name}"
    )

    policy_url = (
        f"{base_url}/policyDefinitions/{policy_name}"
        f"?api-version={API_VERSION}"
    )

    print("\n1. Publishing custom policy definition...")

    az_rest(
        "PUT",
        policy_url,
        policy_data
    )

    print(f"SUCCESS: {policy_name}")
    print(f"Policy ID: {policy_id}")

    print("\n2. Resolving initiative resource ID...")

    initiative_id = find_initiative(
        mg,
        args.initiative
    )

    initiative_url = (
        f"{ARM_ENDPOINT}{initiative_id}"
        f"?api-version={API_VERSION}"
    )

    print("\n3. Reading existing initiative...")

    existing = az_rest(
        "GET",
        initiative_url
    )

    properties = existing["properties"]

    references = properties.get(
        "policyDefinitions", []
    )

    new_reference = {
        "policyDefinitionId": policy_id,
        "policyDefinitionReferenceId": reference_id,
        "parameters": parameters
    }

    # Update existing reference or append new reference
    found = False

    for index, reference in enumerate(references):

        if (
            reference.get("policyDefinitionReferenceId")
            == reference_id
        ):
            references[index] = new_reference
            found = True
            print("Existing policy reference will be updated.")
            break

    if not found:
        references.append(new_reference)
        print("New policy reference will be added.")

    properties["policyDefinitions"] = references

    # Preserve other existing initiative properties,
    # including displayName, description, metadata,
    # parameters, policyDefinitionGroups and version.
    updated_body = {
        "properties": properties
    }

    print("\n4. Updating initiative...")

    az_rest(
        "PUT",
        initiative_url,
        updated_body
    )

    print("\nDEPLOYMENT SUCCESSFUL")
    print("------------------------------------")
    print(f"Management Group : {mg}")
    print(f"Initiative ID    : {initiative_id}")
    print(f"Policy Name      : {policy_name}")
    print(f"Reference ID     : {reference_id}")
    print(f"Effect           : {parameters['effect']['value']}")
    print(
        f"Approval Tag     : "
        f"{parameters['tagName']['value']}="
        f"{parameters['tagValue']['value']}"
    )
    print(f"Total References : {len(references)}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Azure Management Group Policy Deployment"
    )

    parser.add_argument(
        "--management-group",
        required=True
    )

    parser.add_argument(
        "--initiative",
        required=True
    )

    parser.add_argument(
        "--policy-name",
        default="deny-unapproved-public-ip"
    )

    parser.add_argument(
        "--reference-id",
        default=None
    )

    parser.add_argument(
        "--policy-file",
        default="definations/deny-unapproved-public-ip.json"
    )

    parser.add_argument(
        "--parameter-file",
        default="paramters/az_policy_unapproved-public-ip.parameters.json"
    )

    args = parser.parse_args()

    try:
        deploy_policy(args)

    except Exception as error:
        print(f"\nDEPLOYMENT FAILED: {error}")
        raise SystemExit(1)
