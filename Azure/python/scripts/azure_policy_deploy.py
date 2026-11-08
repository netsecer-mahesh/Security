import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--management-group", required=True)

parser.add_argument("--policy-name", required=True)

parser.add_argument("--initiative", required=True)

parser.add_argument("--file-name", required=True)

args = parser.parse_args()

print("Management Group:", args.management_group)
print("Policy Name:", args.policy_name)
print("Initiative:", args.initiative)

import json

with open(args.file_name, "r") as file:
    policy_data = json.load(file)

print("Original keys", policy_data.keys())


print("Policy Effect:", policy_data["properties"]["parameters"]["nsgEffect"]["allowedValues"])


print("properties keys:", policy_data["properties"].keys())
print("parameter keys:", policy_data["properties"]["parameters"].keys())


for parameter_name in policy_data["properties"]["parameters"]:
    print("Parameter Name:", parameter_name)