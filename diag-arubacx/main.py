import pandas as pd
from scripts.api_client import ArubaCXAPIClient
from scripts.data_saver import save_json, save_text

df = pd.read_csv('scripts/devices.csv', dtype=str).fillna('')

for index, row in df.iterrows():
    ip = row["ip"]
    username = row["username"]
    password = row["password"]
    api_version = row["api_version"]

    print("\n==============================")
    print(f"🔍 Traitement du switch {ip}")
    print("==============================")
    client = ArubaCXAPIClient(ip, username, password, api_version)

    if client.login():
        # GET SYSTEM
        system_data = client.get_system_info()
        if system_data:
            save_json(system_data, ip, directory="data/json/system")
            cli_lines = []
            for key, value in system_data.items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        cli_lines.append(f"{key}.{subkey}: {subvalue}")
                else:
                    cli_lines.append(f"{key}: {value}")
            save_text(cli_lines, ip, directory="data/text/system")

        # GET INTERFACES DETAILS (avec GET sur chaque URI)
        interfaces_details = client.get_interfaces_details()
        if interfaces_details:
            save_json(interfaces_details, ip, directory="data/json/interfaces")
            # TXT style CLI protégé
            cli_lines = []
            for intf in interfaces_details:
                name = intf.get("name", "N/A")
                admin = intf.get("admin")
                if isinstance(admin, dict):
                    status = admin.get("state", "N/A")
                else:
                    status = "N/A"
                speed = intf.get("speed", "N/A")
                cli_lines.append(f"Interface: {name}  Status: {status}  Speed: {speed}")
            save_text(cli_lines, ip, directory="data/text/interfaces")


        ## GET TRANSCEIVERS
        transceivers_data = client.get_transceivers()
        if transceivers_data:
            save_json(transceivers_data, ip, directory="data/json/transceivers")
            # TXT style CLI
            cli_lines = []
            for port, details in transceivers_data.items():
                cli_lines.append(f"Port: {port}  -> {details}")
            save_text(cli_lines, ip, directory="data/text/transceivers")

        client.logout()
    else:
        print(f"❌ Connexion impossible pour {ip}")
