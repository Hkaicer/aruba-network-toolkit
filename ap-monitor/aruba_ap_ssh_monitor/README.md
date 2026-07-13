# Aruba AP SSH Monitor (Python)

Connects over **SSH** to an Aruba Mobility Controller, runs:

- `show ap database long status`
- `show ap database long status down`

Parses the CLI tables, generates a daily CSV report, emails a summary, and sends an **alert** email if the number of unique APs that were *down at any monitored run within the last 24 hours* is **>= `ALERT_THRESHOLD`**.

> ✅ Works on Windows 10 (Task Scheduler) or Linux (cron). No SNMP required.

## Quickstart

1. **Create a venv & install deps**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate    # on Windows
   pip install -r requirements.txt
   ```

2. **Create `.env` from the example and edit values**
   ```bash
   copy .env.example .env   # Windows
   ```

3. **Run once**
   ```bash
   python ap_monitor.py
   ```

4. **Schedule**
   - **Windows Task Scheduler** (hourly):
     ```cmd
     schtasks /Create /SC HOURLY /MO 1 /TN "Aruba AP Monitor" /TR "C:\\Path\\to\\python.exe C:\\Path\\to\\ap_monitor.py" /F
     ```
   - **Linux cron** (hourly):
     ```cron
     0 * * * * /usr/bin/python3 /opt/aruba_ap_ssh_monitor/ap_monitor.py
     ```

## How the 24h alert works

Each run appends currently **down** APs to a small history file (`data/down_history.json`) with timestamps, then prunes entries older than 24 hours. The alert compares the **unique APs** seen down in the rolling 24h window against your `ALERT_THRESHOLD`.

> For best accuracy, schedule **hourly**. If you run daily, the alert only reflects the single daily snapshot.

## Output

- `data/ap_status_YYYY-MM-DD.csv`: full snapshot of the parsed table
- `data/down_history.json`: lightweight rolling history (for 24h alert)
- Email body contains a quick summary + a small HTML table of the **down** APs

## Troubleshooting

- If parsing fails due to unexpected columns, the script falls back to a generic **2+ spaces split**. You can customize `EXPECTED_COLUMNS` in `ap_monitor.py` to match your exact controller output.
- For Gmail, use an **app password** and keep `SMTP_PORT=587` with STARTTLS.
- Private key auth: set `SSH_KEY_PATH` in `.env` and remove `SSH_PASSWORD`.
