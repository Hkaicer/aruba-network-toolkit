#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aruba AP SSH Monitor
- SSH to Aruba controller(s)
- Run "show ap database long status" and "... status down"
- Parse tabular CLI output (robust to variable spacing)
- Save CSV daily snapshot
- Maintain rolling 24h history of "down" AP appearances
- Send daily report email, and an ALERT email if >= ALERT_THRESHOLD APs down in last 24h
"""

import os
import re
import csv
import json
import time
import ssl
import socket
import getpass
import datetime as dt
from typing import List, Dict, Tuple, Optional

import paramiko
from dotenv import load_dotenv
from email.message import EmailMessage
import smtplib

# ---- Helpers ----------------------------------------------------------------

def now_utc() -> dt.datetime:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def split_columns(line: str) -> List[str]:
    """Split a row by 2+ spaces; trims each cell."""
    return [c.strip() for c in re.split(r"\s{2,}", line.strip()) if c.strip()]

def detect_header_cols(header_line: str) -> List[str]:
    cols = split_columns(header_line)
    return cols

def find_table_bounds(lines: List[str]) -> Tuple[int, Optional[int], List[str]]:
    """
    Return (start_index, end_index_exclusive, header_cols)
    Finds the header line containing both 'AP' and 'Status' (case-insensitive).
    End is first blank/underline or end of lines.
    """
    header_idx = None
    header_cols: List[str] = []
    for i, l in enumerate(lines):
        if re.search(r"\bAP\b", l, re.I) and re.search(r"Status", l, re.I):
            header_idx = i
            header_cols = detect_header_cols(l)
            break
    if header_idx is None:
        # Fallback: try first line that has 4+ columns
        for i, l in enumerate(lines):
            cols = split_columns(l)
            if len(cols) >= 4:
                header_idx = i
                header_cols = cols
                break
    if header_idx is None:
        raise ValueError("Unable to locate table header in CLI output.")
    # Find end
    end_idx = None
    for j in range(header_idx + 1, len(lines)):
        if not lines[j].strip():
            end_idx = j
            break
    return header_idx, end_idx, header_cols

def parse_table(text: str) -> List[Dict[str, str]]:
    """
    Parse Aruba CLI 'show ap database long status*' output into a list of dicts.
    We rely on column splitting by 2+ spaces to be resilient.
    """
    lines = [l.rstrip("\r") for l in text.splitlines() if l is not None]
    # Skip banner / prompts
    content = []
    for l in lines:
        if l.strip().startswith(("(", "[")) and l.strip().endswith((") #", ") #end", ") $")):
            # prompt line; skip
            continue
        content.append(l)
    if not content:
        return []
    start, end, header_cols = find_table_bounds(content)
    body = content[start + 1: end if end else None]

    rows: List[Dict[str, str]] = []
    for raw in body:
        if not raw.strip():
            continue
        cells = split_columns(raw)
        # Normalize row dict to header size
        row = {}
        for idx, key in enumerate(header_cols):
            val = cells[idx] if idx < len(cells) else ""
            row[key] = val
        rows.append(row)
    return rows

def normalize_status(val: str) -> str:
    v = (val or "").strip().lower()
    if "up" in v and "down" not in v:
        return "up"
    if "down" in v:
        return "down"
    return val.strip()

def extract_status_key(row: Dict[str, str]) -> str:
    # Try common header names
    for k in row.keys():
        if k.lower() in ("status", "state", "ap status", "ap-state"):
            return k
    # Fallback: any column containing 'up' or 'down'
    for k, v in row.items():
        if re.search(r"\b(up|down)\b", v, re.I):
            return k
    return list(row.keys())[0] if row else "status"

def key_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "")

# ---- SSH --------------------------------------------------------------------

def ssh_run(host: str, username: str, password: Optional[str] = None,
            key_path: Optional[str] = None, commands: List[str] = None,
            timeout: int = 25) -> Dict[str, str]:
    """Run commands over SSH and return {command: output}."""
    if commands is None:
        commands = []
    outputs: Dict[str, str] = {}

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        if key_path:
            pkey = paramiko.RSAKey.from_private_key_file(key_path)
            client.connect(hostname=host, username=username, pkey=pkey, timeout=timeout, look_for_keys=False)
        else:
            client.connect(hostname=host, username=username, password=password, timeout=timeout, look_for_keys=False)
        chan = client.invoke_shell()
        time.sleep(0.5)
        # Assume 'no paging' command exists; Aruba often supports "no paging"
        chan.send("no paging\n")
        time.sleep(0.3)
        for cmd in commands:
            chan.recv(65535)  # clear buffer
            chan.send(cmd + "\n")
            time.sleep(0.6)   # wait a bit
            buf = []
            t0 = time.time()
            while True:
                if chan.recv_ready():
                    chunk = chan.recv(65535).decode(errors="ignore")
                    buf.append(chunk)
                    # Heuristic: break if prompt shows again
                    if re.search(r"[#>$]\s*$", chunk):
                        break
                if time.time() - t0 > timeout:
                    break
                time.sleep(0.1)
            outputs[cmd] = "".join(buf)
    finally:
        try:
            client.close()
        except Exception:
            pass

    return outputs

# ---- Email ------------------------------------------------------------------

def send_email(smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
               sender: str, recipients: List[str], subject: str, html_body: str,
               attachments: List[Tuple[str, bytes]] = None) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content("This email has an HTML body. Please use an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    if attachments:
        for fname, data in attachments:
            msg.add_attachment(data, maintype="text", subtype="csv", filename=fname)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.send_message(msg)

# ---- History ----------------------------------------------------------------

def prune_history(entries: List[Dict], window_seconds: int = 86400) -> List[Dict]:
    cutoff = now_utc().timestamp() - window_seconds
    return [e for e in entries if e.get("ts", 0) >= cutoff]

def count_unique_down(entries: List[Dict]) -> int:
    return len({(e.get("controller"), e.get("ap_name")) for e in entries})

# ---- Main -------------------------------------------------------------------

def main():
    load_dotenv()
    controllers = [c.strip() for c in os.getenv("CONTROLLERS", "").split(",") if c.strip()]
    if not controllers:
        raise SystemExit("Please set CONTROLLERS in .env (comma-separated).")

    username = os.getenv("SSH_USERNAME", "")
    password = os.getenv("SSH_PASSWORD", "")
    key_path = os.getenv("SSH_KEY_PATH", "").strip() or None

    data_dir = os.getenv("DATA_DIR", "./data")
    ensure_dir(data_dir)

    alert_threshold = int(os.getenv("ALERT_THRESHOLD", "5"))

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or f"{getpass.getuser()}@localhost")
    smtp_to = [x.strip() for x in os.getenv("SMTP_TO", "").split(",") if x.strip()]

    commands = [
        "show ap database long status",
        "show ap database long status down",
    ]

    all_rows: List[Dict[str, str]] = []
    down_rows: List[Dict[str, str]] = []

    for host in controllers:
        outputs = ssh_run(host, username, password, key_path, commands)
        for cmd, text in outputs.items():
            try:
                rows = parse_table(text)
            except Exception as e:
                # In case of parse failure, store raw output line-by-line minimally
                rows = []
            if "status down" in cmd:
                # Mark controller
                for r in rows:
                    r["_controller"] = host
                down_rows.extend(rows)
            else:
                for r in rows:
                    r["_controller"] = host
                all_rows.extend(rows)

    # Normalize status and count
    total_up = total_down = 0
    for r in all_rows:
        skey = extract_status_key(r)
        status = normalize_status(r.get(skey, ""))
        if status == "up":
            total_up += 1
        elif status == "down":
            total_down += 1

    # Save daily CSV
    today = dt.date.today().isoformat()
    csv_path = os.path.join(data_dir, f"ap_status_{today}.csv")
    # Determine headers (union across rows)
    headers = set()
    for r in all_rows:
        headers.update(r.keys())
    headers = ["_controller"] + sorted([h for h in headers if h != "_controller"])

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    # Update down history
    hist_path = os.path.join(data_dir, "down_history.json")
    history: List[Dict] = []
    if os.path.exists(hist_path):
        try:
            history = json.load(open(hist_path, "r", encoding="utf-8"))
        except Exception:
            history = []

    now_ts = now_utc().timestamp()
    # Record each seen-down AP from the "status down" output
    # Try to pick AP name from common column names
    def find_ap_name(row: Dict[str, str]) -> str:
        for key in row.keys():
            if key.lower() in ("ap name", "ap-name", "name", "ap"):
                return row[key]
        # fallback: first column
        return next(iter(row.values()), "")

    for r in down_rows:
        history.append({
            "ts": now_ts,
            "controller": r.get("_controller", ""),
            "ap_name": find_ap_name(r),
            "row": r
        })
    history = prune_history(history, 86400)
    json.dump(history, open(hist_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    unique_down_24h = count_unique_down(history)

    # Build HTML email
    def html_escape(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def rows_to_html_table(rows: List[Dict[str, str]], max_rows: int = 50) -> str:
        if not rows:
            return "<p><em>Aucune borne Down dans la commande filtrée.</em></p>"
        cols = list(rows[0].keys())
        # Move controller first if present
        if "_controller" in cols:
            cols.remove("_controller")
            cols = ["_controller"] + cols
        head = "".join(f"<th>{html_escape(c)}</th>" for c in cols)
        body = ""
        for r in rows[:max_rows]:
            body += "<tr>" + "".join(f"<td>{html_escape(str(r.get(c,'')))}</td>" for c in cols) + "</tr>"
        return f"<table border='1' cellpadding='5' cellspacing='0'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    html_body = f"""
    <h2>Rapport Aruba AP – {today}</h2>
    <p><b>Contrôleurs :</b> {', '.join(controllers)}</p>
    <ul>
      <li><b>AP Up :</b> {total_up}</li>
      <li><b>AP Down :</b> {total_down}</li>
      <li><b>AP Down (24h uniques) :</b> {unique_down_24h} (fenêtre glissante)</li>
    </ul>
    <h3>Bornes Down (extrait)</h3>
    {rows_to_html_table(down_rows, max_rows=100)}
    <p>CSV complet en pièce jointe : <code>{os.path.basename(csv_path)}</code></p>
    <p style="color:#888"><em>Note :</em> La détection 24h se base sur l'historique local mis à jour à chaque exécution. Planifiez le script au moins <b>toutes les heures</b> pour une meilleure précision.</p>
    """

    subject = f"Rapport Aruba AP – {today} – {total_up} UP / {total_down} DOWN"
    attachments = []
    try:
        with open(csv_path, "rb") as fh:
            attachments.append((os.path.basename(csv_path), fh.read()))
    except Exception:
        pass

    if smtp_host and smtp_to:
        try:
            send_email(smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_to, subject, html_body, attachments)
        except Exception as e:
            print(f"[WARN] Failed to send report email: {e}")

        # Send alert if threshold reached
        if unique_down_24h >= alert_threshold:
            alert_subject = f"[ALERTE] {unique_down_24h} AP Down sur 24h – Aruba"
            alert_body = f"<p>Seuil: {alert_threshold} | Observé: {unique_down_24h}</p>" + html_body
            try:
                send_email(smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_to, alert_subject, alert_body, attachments=None)
            except Exception as e:
                print(f"[WARN] Failed to send alert email: {e}")
    else:
        print("[INFO] SMTP not configured or no recipients; skipping email send.")

    print(f"[OK] Snapshot saved: {csv_path}")
    print(f"[OK] 24h unique down APs: {unique_down_24h} (threshold={alert_threshold})")

if __name__ == "__main__":
    main()
