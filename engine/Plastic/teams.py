import csv
import re
from collections import Counter

def parse_team_csv(csv_path):
    teams = {}

    with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            team_name = row["team_name"]
            teams[team_name] = {
                "total_operatives": int(row["total_operatives"]),
                "must_take": row["must_take"],
                "choices": parse_choices(row["choices"]),
                "faction_rules": row["faction_rules"].split(",") if row["faction_rules"] else [],
                "faction_equipment": row["faction_equipment"].split(",") if row["faction_equipment"] else [],
                "strategy_ploys": row["strategy_ploys"].split(",") if row["strategy_ploys"] else [],
                "firefight_ploys": row["firefight_ploys"].split(",") if row["firefight_ploys"] else []
            }

    return teams

def parse_choices(choice_str):
    # Example: 'choose(5,"Bombardier,Fighter,...")|choose(3,"...")'
    blocks = choice_str.split("|")
    parsed = []

    for block in blocks:
        match = re.match(r'choose\((\d+),"(.*?)"\)', block)
        if match:
            count = int(match.group(1))
            options = match.group(2).split(",")
            parsed.append({"count": count, "options": options})
    return parsed

def validate_team_selection(choices, selected_roles):
    selected_counts = Counter(selected_roles)

    for or_option in choices:  # each OR option is a list of AND blocks
        remaining_counts = selected_counts.copy()
        valid = True

        for block in or_option:

            if not isinstance(block, dict) or "count" not in block or "options" not in block:
                valid = False
                break

            required = block["count"]
            pool = block["options"]
            pool_counts = Counter(pool)

            taken = 0
            for role in pool_counts:
                take = min(pool_counts[role], remaining_counts[role])
                taken += take
                remaining_counts[role] -= take

            if taken < required:
                valid = False
                break

        if valid:
            return True, "Valid team composition"

    return False, "No valid choice block satisfied"


