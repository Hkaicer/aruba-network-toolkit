import pandas as pd
from netmiko import ConnectHandler
import csv
from datetime import datetime
import re

def run_ssh_tasks():
    df_switches = pd.read_csv('data/switch.csv', dtype=str).fillna('')
    commands = ["show hostname", "show system", "show interface transceiver"]
    logfile = open("logs/ssh_logs.txt", "a", encoding="utf-8")
    csv_file = open("data/transceivers.csv", "w", newline='', encoding='utf-8')

    fieldnames = ['hostname', 'chassis_serial', 'port', 'type', 'product_number', 'serial_number', 'part_number']
    csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
    csv_writer.writeheader()

    for idx, row in df_switches.iterrows():
        device = {
            'device_type': row['device_type'],
            'ip': row['ip'],
            'username': row['username'],
            'password': row['password'],
        }
        try:
            conn = ConnectHandler(**device)
            outputs = {}
            for cmd in commands:
                output = conn.send_command(cmd)
                outputs[cmd] = output
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logfile.write(f"[{timestamp}] IP={device['ip']} CMD=\"{cmd}\" ✅ OK\n")

            # Parse system info
            hostname = None
            chassis_serial = None
            for line in outputs.get("show system", "").splitlines():
                line = line.strip()
                if line.startswith("Hostname"):
                    hostname = line.split(":")[1].strip()
                elif line.startswith("Chassis Serial Nbr"):
                    chassis_serial = line.split(":")[1].strip()

            # Parse transceivers
            parsing = False
            transceivers_found = False
            for line in outputs.get("show interface transceiver", "").splitlines():
                line = line.strip()
                if line.startswith("----"):
                    parsing = True
                    continue
                if parsing and line:
                    parts = re.split(r'\s{2,}', line)
                    if len(parts) >= 5:
                        port, type_, product_number, serial_number, part_number = parts[0], parts[1], parts[2], parts[3], parts[4]
                        transceivers_found = True
                        csv_writer.writerow({
                            'hostname': hostname,
                            'chassis_serial': chassis_serial,
                            'port': port,
                            'type': type_,
                            'product_number': product_number,
                            'serial_number': serial_number,
                            'part_number': part_number
                        })
            if not transceivers_found:
                csv_writer.writerow({
                    'hostname': hostname,
                    'chassis_serial': chassis_serial,
                    'port': None,
                    'type': None,
                    'product_number': None,
                    'serial_number': None,
                    'part_number': None
                })
            conn.disconnect()

        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logfile.write(f"[{timestamp}] IP={device['ip']} ❌ ERREUR CONNEXION : {e}\n")

    logfile.close()
    csv_file.close()

    # Nettoyer et exporter Excel
    df = pd.read_csv('data/transceivers.csv', dtype=str).fillna('')
    df_clean = df.drop(columns=['port','type','part_number'])
    df_clean.to_excel('data/output.xlsx', index=False)
