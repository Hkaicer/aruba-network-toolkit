import streamlit as st
import pandas as pd
from netmiko import ConnectHandler
from datetime import datetime
import os

st.title("SSH Switch Collector")

# Input CSV uploader
uploaded_file = st.file_uploader("Upload your switches CSV", type=["csv"])

commands = ["show hostname", "show system", "show interface transceiver", "show interface brief"]

if uploaded_file:
    # Read CSV into DataFrame
    df_switches = pd.read_csv(uploaded_file, dtype=str).fillna('')

    st.write("Switches to process:")
    st.dataframe(df_switches)

    # Directory to save output files
    output_dir = "ssh_outputs"
    os.makedirs(output_dir, exist_ok=True)

    if st.button("Run SSH commands"):
        logfile_path = os.path.join(output_dir, "ssh_logs.txt")
        with open(logfile_path, "a", encoding="utf-8") as logfile:

            for idx, row in df_switches.iterrows():
                device = {
                    'device_type': row['device_type'],
                    'ip': row['ip'],
                    'username': row['username'],
                    'password': row['password'],
                }

                st.write(f"Connecting to {device['ip']}...")

                try:
                    conn = ConnectHandler(**device)
                    st.success(f"Connected to {device['ip']} ✅")

                    output_file = os.path.join(output_dir, f"{device['ip']}.txt")
                    with open(output_file, "w", encoding="utf-8") as f:
                        for cmd in commands:
                            try:
                                output = conn.send_command(cmd)
                                f.write(f"=== {cmd} ===\n")
                                f.write(output + "\n\n\n\n\n")

                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                logfile.write(f"[{timestamp}] IP={device['ip']} CMD=\"{cmd}\" ✅ OK\n")

                            except Exception as e_cmd:
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                logfile.write(f"[{timestamp}] IP={device['ip']} CMD=\"{cmd}\" ❌ ERROR: {e_cmd}\n")
                                st.error(f"Error on command '{cmd}' for {device['ip']}: {e_cmd}")

                    conn.disconnect()

                except Exception as e:
                    st.error(f"SSH connection error for {device['ip']}: {e}")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logfile.write(f"[{timestamp}] IP={device['ip']} ❌ CONNECTION ERROR\n")

        st.success(f"Finished. Outputs saved to `{output_dir}` folder.")

        # Optionally provide links to download files
        st.write("Output files:")
        for file in os.listdir(output_dir):
            if file.endswith(".txt"):
                st.write(f"- {file}")

