import streamlit as st
import pandas as pd
from netmiko import ConnectHandler
from datetime import datetime
import re
import csv
import io

def run_ssh_on_switches(df_switches):
    output = io.BytesIO()
    fieldnames = ['hostname', 'chassis_serial', 'port', 'type', 'product_number', 'serial_number', 'part_number']
    
    # On sauvegarde d'abord dans un CSV en mémoire
    csv_buffer = io.StringIO()
    csv_writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
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
            commands = ["show hostname", "show system", "show interface transceiver"]
            for cmd in commands:
                outputs[cmd] = conn.send_command(cmd)

            # Parse system info
            hostname, chassis_serial = None, None
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
                            'hostname': "",
                            'chassis_serial': "",
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
            st.error(f"Erreur connexion SSH pour {device['ip']} : {e}")

    # On transforme le CSV en dataframe
    csv_buffer.seek(0)
    df = pd.read_csv(csv_buffer)
    df_clean = df.drop(columns=['port', 'type', 'part_number'])
    df_clean.to_excel(output, index=False)
    output.seek(0)
    return df_clean, output

# === STREAMLIT UI ===
st.title("SSH Switch Collector")

uploaded_file = st.file_uploader("Upload your switch.csv file", type=["csv"])
if uploaded_file:
    df_switches = pd.read_csv(uploaded_file, dtype=str).fillna('')
    st.write("### Switches loaded :")
    st.dataframe(df_switches)

    if st.button("Run SSH and generate Excel"):
        df_result, excel_file = run_ssh_on_switches(df_switches)
        st.success("✅ SSH done. Here is your data:")
        st.dataframe(df_result)
        st.download_button(
            label="Download Excel file",
            data=excel_file,
            file_name=f"transceivers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
