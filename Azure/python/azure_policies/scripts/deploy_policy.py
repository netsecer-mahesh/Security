
import argparse
import json
import subprocess
from pathlib import Path


API_VERSION = "2025-11-01"


def az_rest(method, url, body=None):
    command = [
        "az", "rest",
        "--method", method,
        "--url", url,
        "--output", "json"
    ]

    if body is not None:
        command.extend(["--body", json.dumps(body)])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return json.loads(result.stdout) if result.stdout.strip() else {}


def deploy_policy(args):
    mg = args.management_group
    initiative = args.initiative

    policy_file = Path(args.policy_file)
    parameter_file = Path(args.parameter_file)

    policy_data = json.loads(policy_file.read_text())
    parameters = json.loads(parameter_file.read_text())

    policy_name = args.policy_name
    reference_id = args.reference_id or policy_name

    base_url = (
        f"https://management.azure.com/providers/"
        f"Microsoft.Management/managementGroups/{mg}/"
        f"providers/Microsoft.Authorization"
    )

    policy_id = (
        f"{base_url}/policyDefinitions/{policy_name}"
    )

    initiative_id = (
        f"{base_url}/policySetDefinitions/{initiative}"
    )

    print("1. Publishing custom policy definition...")

    az_rest(
        "PUT",
        f"{policy_id}?api-version={API_VERSION}",
        policy_data
    )

    print(f"SUCCESS: {policy_name}")

    print("2. Reading existing initiative...")

    existing = az_rest(
        "GET",
        f"{initiative_id}?api-version={API_VERSION}"
    )

    properties = existing["properties"]

    references = properties.get("policyDefinitions", [])

    new_reference = {
        "policyDefinitionId": policy_id,
        "policyDefinitionReferenceId": reference_id,
        "parameters": parameters
    }

    # Update an existing reference or append a new one.
    found = False

    for index, reference in enumerate(references):
        if reference.get("policyDefinitionReferenceId") == reference_id:
            references[index] = new_reference
            found = True
            break

    if not found:
        references.append(new_reference)

    properties["policyDefinitions"] = references

    print("3. Updating initiative...")

    az_rest(
        "PUT",
        f"{initiative_id}?api-version={API_VERSION}",
        {"properties": properties}
    )

    print("SUCCESS: Initiative updated.")
    print(f"Management Group : {mg}")
    print(f"Initiative       : {initiative}")
    print(f"Policy           : {policy_name}")
    print(f"Reference ID     : {reference_id}")
    print(f"Effect           : {parameters['effect']['value']}")
    print(f"Approval tag     : "
          f"{parameters['tagName']['value']}="
          f"{parameters['tagValue']['value']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy Azure Public IP governance policy"
    )

    parser.add_argument("--management-group", required=True)
    parser.add_argument("--initiative", required=True)
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
        default="\\Azure\\python\\azure_policies\\definitions\\deny-unapproved-public-ip.json"
    )
    parser.add_argument(
        "--parameter-file",
        default="\\Azure\\python\\azure_policies\\parameters\\az_policy_unapproved_public-ip.parameters.json"
    )

    args = parser.parse_args()

    try:
        deploy_policy(args)
    except Exception as error:
        print(f"DEPLOYMENT FAILED: {error}")
        raise SystemExit(1)
