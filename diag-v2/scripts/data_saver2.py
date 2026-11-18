# scripts/data_saver2.py
import json
import os


def _path(ip, filename, ext):
    dir_path = os.path.join("data", ip)
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, f"{filename}.{ext}")


def save_json(data, ip, filename):
    filepath = _path(ip, filename, "json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {filepath}")


def to_text(data):
    """Readable 'key: value' report (nested values kept as compact JSON)."""
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f"{key}: {value}")
        return "\n".join(lines) + "\n"
    if isinstance(data, list):
        return "\n".join(json.dumps(item, ensure_ascii=False) for item in data) + "\n"
    return f"{data}\n"


def save_text(data, ip, filename):
    filepath = _path(ip, filename, "txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(to_text(data))
    print(f"Saved TXT: {filepath}")
