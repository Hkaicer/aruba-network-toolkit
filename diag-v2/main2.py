import pandas as pd
from scripts.api_client2 import ArubaCXAPIClient
from scripts.data_saver2 import save_json, save_text

def main():
    # Lire le CSV des devices
    df = pd.read_csv('devices.csv', dtype=str).fillna('')

    for index, row in df.iterrows():
        ip = row["ip"]
        username = row["username"]
        password = row["password"]
        api_version = row["api_version"]

        print(f"\n📡 Connexion à {ip}...")

        client = ArubaCXAPIClient(ip, username, password, api_version)
        if client.login():

            try:
                data_system = client.get_system()
                data_version = client.get_version()
                data_interface_brief = client.get_interface_brief()
                data_transceiver = client.get_transceiver()
                data_transceiver_detail = client.get_transceiver_detail()
                data_environment = client.get_environment()
                data_cpu = client.get_cpu()
                data_memory = client.get_memory()
                data_health = client.get_health()
                data_process_cpu = client.get_process_cpu()
                data_process_memory = client.get_process_memory()
                data_logging = client.get_logging()
                data_event_history = client.get_event_history()

                save_json(data_system, ip, "system")
                save_text(data_system, ip, "system")

                save_json(data_version, ip, "version")
                save_text(data_version, ip, "version")

                save_json(data_interface_brief, ip, "interface_brief")
                save_text(data_interface_brief, ip, "interface_brief")

                save_json(data_transceiver, ip, "transceiver")
                save_text(data_transceiver, ip, "transceiver")

                save_json(data_transceiver_detail, ip, "transceiver_detail")
                save_text(data_transceiver_detail, ip, "transceiver_detail")

                save_json(data_environment, ip, "environment")
                save_text(data_environment, ip, "environment")

                save_json(data_cpu, ip, "cpu")
                save_text(data_cpu, ip, "cpu")

                save_json(data_memory, ip, "memory")
                save_text(data_memory, ip, "memory")

                save_json(data_health, ip, "health")
                save_text(data_health, ip, "health")

                save_json(data_process_cpu, ip, "process_cpu")
                save_text(data_process_cpu, ip, "process_cpu")
    
                save_json(data_process_memory, ip, "process_memory")
                save_text(data_process_memory, ip, "process_memory")

                save_json(data_logging, ip, "logging")
                save_text(data_logging, ip, "logging")

                save_json(data_event_history, ip, "event_history")
                save_text(data_event_history, ip, "event_history")

                print(f"✅ Données sauvegardées pour {ip}")

            except Exception as e:
                print(f"❌ Erreur avec {ip}: {e}")
        else:
            print("❌ Échec de l'authentification pour", ip)
    
if __name__ == "__main__":
    main()