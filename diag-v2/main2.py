"""Collect diagnostic data from every AOS-CX switch listed in devices.csv.

devices.csv columns: ip,username,password,api_version[,verify]
  verify (optional): empty/false = lab mode (self-signed cert accepted),
                     true = system CAs, or a path to a CA bundle (.pem).
Results: data/<ip>/<dataset>.json and .txt
"""
import pandas as pd
import requests

from scripts.api_client2 import ArubaCXAPIClient
from scripts.data_saver2 import save_json, save_text

# (dataset name, client method)
DATASETS = [
    ("system", "get_system"),
    ("version", "get_version"),
    ("interface_brief", "get_interface_brief"),
    ("transceiver", "get_interface_transceiver"),
    ("transceiver_detail", "get_interface_transceiver_detail"),
    ("environment", "get_environment"),
    ("health", "get_health"),
    ("resource_utilization", "get_resource_utilization"),
    ("process_cpu", "get_processes_cpu"),
    ("process_memory", "get_processes_memory"),
    ("logging", "get_logging"),
    ("event_history", "get_event_history"),
]


def parse_verify(value):
    v = (value or "").strip()
    if v.lower() in ("", "false", "0", "no"):
        return False
    if v.lower() in ("true", "1", "yes"):
        return True
    return v


def collect_device(ip, username, password, api_version, verify=False):
    """Collect every dataset from one switch. Returns the number of datasets saved."""
    print(f"\nConnecting to {ip}...")
    client = ArubaCXAPIClient(ip, username, password, api_version, verify=verify)
    try:
        if not client.login():
            print(f"Login rejected by {ip}")
            return 0
    except requests.RequestException as e:
        print(f"Cannot reach {ip}: {e}")
        return 0

    saved = 0
    try:
        for name, method in DATASETS:
            try:
                data = getattr(client, method)()
            except (requests.RequestException, ValueError) as e:
                print(f"  {ip} {name}: skipped ({e})")
                continue
            save_json(data, ip, name)
            save_text(data, ip, name)
            saved += 1
    finally:
        client.logout()
    print(f"{ip}: {saved}/{len(DATASETS)} datasets saved")
    return saved


def main(csv_path="devices.csv"):
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    for _, row in df.iterrows():
        collect_device(
            row["ip"], row["username"], row["password"],
            row["api_version"] or "v10.11",
            verify=parse_verify(row.get("verify", "")),
        )


if __name__ == "__main__":
    main()
