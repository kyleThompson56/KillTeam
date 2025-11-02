import csv
import os

def load_csv(filename):
    path = os.path.join("data", filename)
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def load_all_data():
    return {
        "operatives": load_csv("operatives.csv"),
        "weapons": load_csv("weapons.csv"),
        "abilities": load_csv("abilities.csv"),
        "passives": load_csv("passives.csv"),
    }
