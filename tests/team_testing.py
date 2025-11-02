# team_testing.py

from engine.Plastic.operative import load_all_operatives, filter_operatives_by_team, Operative
from engine.Plastic.teams import parse_team_csv, parse_choices, validate_team_selection

import pprint

import os

def resolve_path(filename):
    base_dir = os.path.dirname(os.path.dirname(__file__))  # goes from /tests to /KillTeam
    return os.path.join(base_dir, "data", filename)

def run_team_test(team_name, selected_roles):
    # Load data
    operatives = load_all_operatives(resolve_path("operatives.csv"))
    teams = parse_team_csv(resolve_path("teams.csv"))

    # Get team rules
    team = teams.get(team_name)
    if not team:
        print(f"Team '{team_name}' not found.")
        return

    # Validate selection (excluding must_take)
    choices = team["choices"]
    print("Parsed choices structure:")
    for option in choices:
        print(option)

    is_valid, message = validate_team_selection(choices, selected_roles[1:])  # skip must_take
    print(f"\nTesting team: {team_name}")
    print(f"Selected roles: {selected_roles}")
    print(f"Validation result: {message}")

    # Optional: show matching operatives
    team_ops = [op for op in operatives if op["team"] == team_name and op["role"] in selected_roles]
    print("\nMatching Operatives:")
    pprint.pprint(team_ops)

# === Run a test ===
if __name__ == "__main__":
    run_team_test(
        team_name="plague_marines",
        selected_roles=["Bombardier", "Fighter", "Heavy_Gunner", "Plaguecaster", "Warrior"]
    )


