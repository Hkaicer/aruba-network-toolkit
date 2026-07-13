# Aruba Network Automation Toolkit

Tools built during an internship project for monitoring and diagnosing **HPE Aruba** network equipment (CX switches, Mobility Controllers, Access Points) via REST API and SSH.

> All credentials and device inventories are supplied by the user at runtime (`.env` files or CSV inventories). Copy the provided `*.example` templates and fill in your own values — nothing sensitive ships with this repository.

## Contents

| Folder | Description |
|---|---|
| [`diag-arubacx/`](diag-arubacx) | Diagnostic tool for **Aruba CX** switches over the REST API (system info, interfaces, transceivers). Saves JSON + CLI-style text reports, includes a small Flask API server and a static HTML dashboard. |
| [`diag-v2/`](diag-v2) | Cleaner second iteration of the CX diagnostic collector. |
| [`ssh-tools/`](ssh-tools) | SSH batch tools built on **Netmiko**: run CLI command lists against a CSV inventory of switches, export results to text/Excel. Includes a Streamlit UI (`sshV2.py`), a CLI version, and a small Flask web interface (`ssh_interface/`). |
| [`ap-monitor/`](ap-monitor) | Two Access-Point monitoring daemons for Aruba Mobility Controllers: `aruba_ap_ssh_monitor/` (daily CSV report + email) and `ap_down_monitor/` (rolling 24h/7d history, alert threshold, cooldown, daily email report). |

## Quickstart

Each folder is self-contained with its own `requirements.txt`:

```bash
cd <folder>
python -m venv .venv
.venv\Scripts\activate        # Windows  (source .venv/bin/activate on Linux)
pip install -r requirements.txt
```

Then copy the template files and fill in your values:

```bash
copy .env.example .env                      # for the AP monitors
copy devices.csv.example devices.csv        # for the diagnostic tools
```

## Requirements

- Python 3.10+
- Network reachability to your Aruba equipment (REST API enabled on CX switches for the diag tools)

## See also

- [HPE Aruba NAE scripts (official repo)](https://github.com/aruba/nae-scripts) — Network Analytics Engine scripts referenced during this project.

## License

MIT
