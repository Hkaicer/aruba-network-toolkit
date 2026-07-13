# scripts/data_saver.py
import json
import os

def save_json(data, ip, filename):
    dir_path = f"data/{ip}"
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{filename}.json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"📂 Sauvegardé JSON : {filepath}")

def save_text(data, ip, filename):
    dir_path = f"data/{ip}"
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{filename}.txt")
    with open(filepath, 'w') as f:
        f.write(data)
    print(f"📝 Sauvegardé TXT : {filepath}")