import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--management-group", required=True)

parser.add_argument("--policy-name", required=True)

parser.add_argument("--initiative", required=True)

args = parser.parse_args()

print("Management Group:", args.management_group)
print("Policy Name:", args.policy_name)
print("Initiative:", args.initiative)