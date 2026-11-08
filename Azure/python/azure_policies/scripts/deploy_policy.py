
import argparse
import json
import subprocess
import tempfile
import os
from pathlib import Path


API_VERSION = "2025-11-01"
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


def find_initiative(mg, initiative_input, base_url):
    """
    Resolve initiative using its exact resource name
    or an explicitly supplied full resource ID.
    """

    if initiative_input.startswith("/"):
        expected_prefix = (
            f"/providers/Microsoft.Management/"
            f"managementGroups/{mg}/providers/"
            f"Microsoft.Authorization/policySetDefinitions/"
        )

        if not initiative_input.lower().startswith(
            expected_prefix.lower()
        ):
            raise ValueError(
                "Initiative ID does not belong to "
                f"Management Group {mg}: {initiative_input}"
            )

        return initiative_input

    print("Discovering initiative resource ID...")

    response = az_rest(
        "GET",
        f"{base_url}/policySetDefinitions"
        f"?api-version={API_VERSION}"
    )

    expected_prefix = (
        f"/providers/Microsoft.Management/"
        f"managementGroups/{mg}/providers/"
        f"Microsoft.Authorization/policySetDefinitions/"
    )

    definitions = response.get("value", [])

    # Only consider initiatives defined directly at this MG.
    exact_scope = [
        item for item in definitions
        if item.get("id", "").lower().startswith(
            expected_prefix.lower()
        )
    ]

    for item in exact_scope:
        if item.get("name") == initiative_input:
            print("Initiative found.")
            print(f"Resource ID: {item['id']}")
            return item["id"]

    available = [
        f"{item.get('name')} -> {item.get('id')}"
        for item in exact_scope
    ]

    raise ValueError(
        f"Initiative '{initiative_input}' was not found "
        f"directly at MG '{mg}'.\n"
        "Available initiative resource IDs:\n"
        + ("\n".join(available) if available else "None found.")
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

    base_url = (
        "https://management.azure.com/providers/"
        f"Microsoft.Management/managementGroups/{mg}/"
        "providers/Microsoft.Authorization"
    )

    policy_id = (
        f"{base_url}/policyDefinitions/{policy_name}"
    )

    print("\n1. Publishing custom policy definition...")

    az_rest(
        "PUT",
        f"{policy_id}?api-version={API_VERSION}",
        policy_data
    )

    print(f"SUCCESS: {policy_name}")

    print("\n2. Resolving initiative resource ID...")

    initiative_id = find_initiative(
        mg,
        args.initiative,
        base_url
    )

    print("\n3. Reading existing initiative...")

    existing = az_rest(
        "GET",
        f"https://management.azure.com{initiative_id}"
        f"?api-version={API_VERSION}"
    )

    properties = existing["properties"]

    references = properties.get("policyDefinitions", [])

    new_reference = {
        "policyDefinitionId": policy_id,
        "policyDefinitionReferenceId": reference_id,
        "parameters": parameters
    }

    found = False

    for index, reference in enumerate(references):

        if (
            reference.get("policyDefinitionReferenceId")
            == reference_id
        ):
            references[index] = new_reference
            found = True
            break

    if not found:
        references.append(new_reference)

    properties["policyDefinitions"] = references

    print("\n4. Updating initiative...")

    az_rest(
        "PUT",
        f"https://management.azure.com{initiative_id}"
        f"?api-version={API_VERSION}",
        {"properties": properties}
    )

    print("\nDEPLOYMENT SUCCESSFUL")
    print("--------------------------------")
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
        required=True,
        help="Exact initiative resource name or full resource ID"
    )

    parser.add_argument(
        "--policy-name",
        default="Deny-Unapproved-Public-IP-Addresses"
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
