import json
import os
from datetime import datetime

def save_json(data, ip, directory="data/json"):
    os.makedirs(directory, exist_ok=True)
    ip_safe = ip.replace(".", "_")
    timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
    filename = f"{ip_safe}_{timestamp}.json"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)
    print(f"JSON sauvegardé : {filepath}")
    return filepath

def save_text(content_lines, ip, directory="data/text"):
    """
    content_lines : liste de strings type ["Interface: ...", "Status: ..."]
    """
    os.makedirs(directory, exist_ok=True)
    ip_safe = ip.replace(".", "_")
    timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
    filename = f"{ip_safe}_{timestamp}.txt"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        for line in content_lines:
            f.write(line + "\n")
    print(f"TXT sauvegardé : {filepath}")
    return filepath
