import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--management-group", required=True)

args = parser.parse_args()

print("Management Group:", args.management_group)