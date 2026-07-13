import re
import io
import time
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# =============================
# Helpers
# =============================

def split_blocks(text: str) -> dict:
    """Split the uploaded text into blocks delimited by lines like: === show system ===
    Returns a dict {key: block_text} with lowercase keys.
    """
    blocks = {}
    key = None
    buf = []
    header_re = re.compile(r"^===\s*(.+?)\s*===\s*$")
    for line in text.splitlines():
        m = header_re.match(line.strip())
        if m:
            # flush previous
            if key is not None:
                blocks[key] = "\n".join(buf).strip()
            key = m.group(1).strip().lower()
            buf = []
        else:
            buf.append(line)
    if key is not None:
        blocks[key] = "\n".join(buf).strip()
    return blocks


def _to_int(s):
    try:
        return int(float(str(s).strip()))
    except Exception:
        return None


def _to_float(s):
    try:
        return float(str(s).strip())
    except Exception:
        return None


def _parse_percent_line(line: str):
    """Extract a percentage number from a line like 'CPU Util (%)       : 4' or 'Memory Usage (%) : 29'"""
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%?", line)
    return _to_float(m.group(1)) if m else None


def _parse_key_value(block: str) -> dict:
    """Parse key : value pairs from a block. Returns dict with normalized keys."""
    data = {}
    for ln in block.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            key = re.sub(r"\s+", " ", k).strip().lower()
            val = v.strip()
            data[key] = val
    return data


def parse_show_hostname(block: str) -> dict:
    # Usually just a single line with the hostname
    line = block.strip().splitlines()[0].strip() if block.strip() else ""
    return {"hostname": line or None}


# =============================
# Parsers for each command
# =============================

def parse_show_system(block: str) -> dict:
    kv = _parse_key_value(block)
    out = {
        "hostname": kv.get("hostname"),
        "model": kv.get("product name") or kv.get("product"),
        "os_version": kv.get("system description") or kv.get("software version"),
        "uptime_s": None,
        "cpu_pct": None,
        "mem_pct": None,
        "vendor": kv.get("vendor"),
        "base_mac": kv.get("base mac address"),
        "serial": kv.get("chassis serial nbr") or kv.get("serial number"),
    }
    # Uptime: try to convert a human string to seconds
    up = kv.get("uptime")
    if up:
        # common patterns: "1 days 2 hours 3 minutes 4 seconds"; be forgiving
        days = _to_int(re.search(r"(\d+)\s*day", up or "") and re.search(r"(\d+)\s*day", up).group(1) or 0)
        hours = _to_int(re.search(r"(\d+)\s*hour", up or "") and re.search(r"(\d+)\s*hour", up).group(1) or 0)
        mins = _to_int(re.search(r"(\d+)\s*min", up or "") and re.search(r"(\d+)\s*min", up).group(1) or 0)
        secs = _to_int(re.search(r"(\d+)\s*sec", up or "") and re.search(r"(\d+)\s*sec", up).group(1) or 0)
        for x in (days, hours, mins, secs):
            if x is None:
                # reset all if any failed
                days = hours = mins = secs = 0
                break
        out["uptime_s"] = days * 86400 + hours * 3600 + mins * 60 + secs

    # CPU / Memory may appear here
    for ln in block.splitlines():
        if "cpu" in ln.lower():
            p = _parse_percent_line(ln)
            if p is not None:
                out["cpu_pct"] = p
        if "memory" in ln.lower():
            p = _parse_percent_line(ln)
            if p is not None:
                out["mem_pct"] = p
    return out


def parse_show_interface_brief(block: str) -> pd.DataFrame:
    rows = []
    for ln in block.splitlines():
        line = ln.rstrip()
        if not line or set(line) <= set("- "):
            continue  # skip separators
        if line.lower().startswith("port") or "mode" in line.lower() and "type" in line.lower():
            continue  # skip headers
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2:
            continue
        rec = {
            "name": parts[0] if len(parts) > 0 else None,
            "native_vlan": parts[1] if len(parts) > 1 else None,
            "mode": parts[2] if len(parts) > 2 else None,
            "type": parts[3] if len(parts) > 3 else None,
            "enabled": parts[4] if len(parts) > 4 else None,
            "link_state": parts[5] if len(parts) > 5 else None,
            "reason": None,
            "speed": None,
            "description": None,
        }
        # Reason/Speed/Description can shift depending on blanks; try to infer
        if len(parts) >= 9:
            rec["reason"], rec["speed"], rec["description"] = parts[6], parts[7], parts[8]
        elif len(parts) == 8:
            # probably empty reason
            rec["reason"], rec["speed"], rec["description"] = "", parts[6], parts[7]
        elif len(parts) == 7:
            rec["reason"], rec["speed"], rec["description"] = parts[6], "", ""
        rows.append(rec)
    df = pd.DataFrame(rows)
    # Normalize
    if not df.empty:
        # Admin state is equivalent to 'enabled' here (yes/no). Map to bool.
        df["admin_state"] = df["enabled"].str.lower().map({"yes": True, "no": False})
        # Speed as int if possible
        def _spd(x):
            if x is None or x == "--":
                return None
            return _to_int(x)
        df["speed_mb_s"] = df["speed"].apply(_spd)
    return df


def parse_show_transceiver(block: str) -> pd.DataFrame:
    if not block.strip() or "no pluggable modules found" in block.lower():
        return pd.DataFrame(columns=["if_name","vendor","model","serial","temp_c","rx_dbm","tx_dbm","status"])
    rows = []
    # Split by interface sections
    sections = re.split(r"\n(?=\s*(Transceiver in|Interface)\s+([^\s:]+))", block, flags=re.IGNORECASE)
    # sections comes like [pre, 'Transceiver in', '1/1/1', rest, 'Transceiver in', '1/1/2', rest, ...]
    if len(sections) > 1:
        pre = sections[0]
        for i in range(1, len(sections), 3):
            if i+2 >= len(sections):
                break
            if_hdr, if_name, body = sections[i], sections[i+1], sections[i+2]
            info = {"if_name": if_name.strip(), "vendor": None, "model": None, "serial": None,
                    "temp_c": None, "rx_dbm": None, "tx_dbm": None, "status": None}
            for ln in body.splitlines():
                l = ln.strip()
                if not l:
                    continue
                if re.search(r"vendor", l, re.I):
                    info["vendor"] = l.split(":")[-1].strip()
                elif re.search(r"model", l, re.I):
                    info["model"] = l.split(":")[-1].strip()
                elif re.search(r"serial", l, re.I):
                    info["serial"] = l.split(":")[-1].strip()
                elif re.search(r"temperature", l, re.I):
                    m = re.search(r"(-?\d+(?:\.\d+)?)", l)
                    info["temp_c"] = _to_float(m.group(1)) if m else None
                elif re.search(r"rx .*power|rx power", l, re.I):
                    m = re.search(r"(-?\d+(?:\.\d+)?)", l)
                    info["rx_dbm"] = _to_float(m.group(1)) if m else None
                elif re.search(r"tx .*power|tx power", l, re.I):
                    m = re.search(r"(-?\d+(?:\.\d+)?)", l)
                    info["tx_dbm"] = _to_float(m.group(1)) if m else None
                elif re.search(r"status", l, re.I):
                    info["status"] = l.split(":")[-1].strip()
            rows.append(info)
    return pd.DataFrame(rows)


def parse_show_environment(block: str) -> pd.DataFrame:
    """Return a long-format DataFrame: sensor/location/value/unit/status. Works best with real samples; this is tolerant."""
    rows = []
    for ln in block.splitlines():
        l = ln.strip()
        if not l or set(l) <= set("-="):
            continue
        # e.g. "Temp Sensor 1 (Chassis) : 33 C (OK)"
        m = re.match(r"(.+?)\s*:\s*([^()]+?)\s*([A-Za-z°%/]+)?\s*(?:\(([^)]+)\))?$", l)
        if m:
            name = m.group(1).strip()
            val = _to_float(re.search(r"-?\d+(?:\.\d+)?", m.group(2) or "") and re.search(r"-?\d+(?:\.\d+)?", m.group(2)).group(0) or None)
            unit = (m.group(3) or "").strip() or None
            status = (m.group(4) or "").strip() or None
            rows.append({"sensor": name, "location": None, "value": val, "unit": unit, "status": status})
            continue
        # fans, psu lines often like "Fan 1 : OK" or "Power Supply 1 : OK"
        m2 = re.match(r"(Fan\s+\S+|Power\s*Supply\s*\S+|PSU\s*\S+)\s*:\s*(.+)$", l, flags=re.I)
        if m2:
            rows.append({"sensor": m2.group(1), "location": None, "value": None, "unit": None, "status": m2.group(2).strip()})
    return pd.DataFrame(rows)


def parse_show_logging(block: str) -> pd.DataFrame:
    rows = []
    for ln in block.splitlines():
        l = ln.strip()
        if not l:
            continue
        # Try ISO timestamp first
        ts, sev, facility, msg = None, None, None, l
        m = re.match(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(.*)$", l)
        if m:
            ts = m.group(1)
            rest = m.group(2)
            # severity in brackets or words
            m2 = re.match(r"\[?(INFO|WARN|WARNING|ERR|ERROR|CRIT|DEBUG|NOTICE)\]?\s*[:\-]?\s*(.*)$", rest, re.I)
            if m2:
                sev = m2.group(1).upper()
                msg = m2.group(2)
                # optional facility like "module=..." at start
                m3 = re.match(r"([A-Za-z0-9_./-]+)[:\-]\s*(.*)$", msg)
                if m3:
                    facility, msg = m3.group(1), m3.group(2)
        rows.append({"timestamp": ts, "severity": sev, "facility": facility, "message": msg, "raw": l})
    return pd.DataFrame(rows)


def parse_show_cpu(block: str) -> dict:
    out = {"cpu_1s": None, "cpu_1m": None, "cpu_5m": None, "cpu_pct": None}
    for ln in block.splitlines():
        l = ln.lower()
        m1 = re.search(r"(\d+(?:\.\d+)?)\s*%\s*\(\s*1\s*sec", l)
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*%\s*\(\s*1\s*min", l)
        m3 = re.search(r"(\d+(?:\.\d+)?)\s*%\s*\(\s*5\s*min", l)
        if m1:
            out["cpu_1s"] = _to_float(m1.group(1))
        if m2:
            out["cpu_1m"] = _to_float(m2.group(1))
        if m3:
            out["cpu_5m"] = _to_float(m3.group(1))
        if "cpu" in l and out["cpu_pct"] is None:
            p = _parse_percent_line(l)
            if p is not None:
                out["cpu_pct"] = p
    return out


def parse_show_memory(block: str) -> dict:
    kv = _parse_key_value(block)
    out = {"mem_total_mb": None, "mem_used_mb": None, "mem_free_mb": None, "mem_pct": None}
    # Try percent line first
    for ln in block.splitlines():
        if "mem" in ln.lower():
            p = _parse_percent_line(ln)
            if p is not None:
                out["mem_pct"] = p
    # Try totals
    for k in list(kv.keys()):
        if "total" in k and "mem" in k:
            out["mem_total_mb"] = _to_float(re.search(r"(\d+(?:\.\d+)?)", kv[k]) and re.search(r"(\d+(?:\.\d+)?)", kv[k]).group(1) or None)
        if ("free" in k or "available" in k) and "mem" in k:
            out["mem_free_mb"] = _to_float(re.search(r"(\d+(?:\.\d+)?)", kv[k]) and re.search(r"(\d+(?:\.\d+)?)", kv[k]).group(1) or None)
        if "used" in k and "mem" in k:
            out["mem_used_mb"] = _to_float(re.search(r"(\d+(?:\.\d+)?)", kv[k]) and re.search(r"(\d+(?:\.\d+)?)", kv[k]).group(1) or None)
    # Derive percent if possible
    if out["mem_pct"] is None and out["mem_total_mb"] and out["mem_used_mb"] is not None:
        try:
            out["mem_pct"] = 100.0 * float(out["mem_used_mb"]) / float(out["mem_total_mb"]) if out["mem_total_mb"] else None
        except Exception:
            pass
    return out


# =============================
# Streamlit UI
# =============================

st.set_page_config(page_title="ArubaOS-CX Parser", layout="wide")
st.title("ArubaOS-CX CLI Parser & Mini Dashboard")
st.caption("Upload a text file generated by your collector (with blocks like `=== show system ===`). This app parses key health, interfaces, optics, environment, logs, CPU and memory, and shows quick tables and charts.\nFor charts, we use matplotlib only (no seaborn), to keep dependencies light.")

uploaded = st.file_uploader("Upload CLI dump (.txt)", type=["txt","log"]) 

if uploaded:
    raw_text = uploaded.read().decode("utf-8", errors="ignore")
    blocks = split_blocks(raw_text)

    # Parse pieces
    system = parse_show_system(blocks.get("show system", "")) if "show system" in blocks else {}
    if "show hostname" in blocks and not system.get("hostname"):
        system.update(parse_show_hostname(blocks.get("show hostname", "")))

    df_if = parse_show_interface_brief(blocks.get("show interface brief", ""))
    df_xcvr = parse_show_transceiver(blocks.get("show interface transceiver detail", blocks.get("show interface transceiver", "")))
    df_env = parse_show_environment(blocks.get("show environment", ""))
    df_log = parse_show_logging(blocks.get("show logging", ""))

    cpu = parse_show_cpu(blocks.get("show cpu utilization", ""))
    mem = parse_show_memory(blocks.get("show memory", ""))

    # Merge CPU/MEM from show system if missing
    if system.get("cpu_pct") and not cpu.get("cpu_pct"):
        cpu["cpu_pct"] = system.get("cpu_pct")
    if system.get("mem_pct") and not mem.get("mem_pct"):
        mem["mem_pct"] = system.get("mem_pct")

    # ===== System Summary =====
    st.subheader("System Summary")
    cols = st.columns(6)
    cols[0].metric("Hostname", system.get("hostname") or "-")
    cols[1].metric("Model", system.get("model") or "-")
    cols[2].metric("OS / Desc", (system.get("os_version") or "-")[:22])
    cols[3].metric("CPU %", f"{cpu.get('cpu_pct'):.0f}" if cpu.get("cpu_pct") is not None else "-")
    cols[4].metric("Mem %", f"{mem.get('mem_pct'):.0f}" if mem.get("mem_pct") is not None else "-")
    cols[5].metric("Uptime (s)", int(system.get("uptime_s") or 0))

    # Small bar for CPU/Mem
    fig1, ax1 = plt.subplots()
    x = ["CPU", "Mem"]
    y = [cpu.get("cpu_pct") or 0, mem.get("mem_pct") or 0]
    ax1.bar(x, y)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Percent")
    ax1.set_title("CPU / Memory")
    st.pyplot(fig1)

    # ===== Interfaces =====
    st.subheader("Interfaces (brief)")
    st.dataframe(df_if, use_container_width=True)
    if not df_if.empty:
        # Status counts
        by_state = df_if["link_state"].fillna("-").value_counts().reset_index()
        by_state.columns = ["state", "count"]
        fig2, ax2 = plt.subplots()
        ax2.bar(by_state["state"], by_state["count"])
        ax2.set_title("Interface Link State Counts")
        ax2.set_ylabel("Count")
        st.pyplot(fig2)

        # Top N by speed
        if "speed_mb_s" in df_if.columns and df_if["speed_mb_s"].notna().any():
            top_speed = df_if.dropna(subset=["speed_mb_s"]).sort_values("speed_mb_s", ascending=False).head(10)
            fig3, ax3 = plt.subplots()
            ax3.bar(top_speed["name"], top_speed["speed_mb_s"])
            ax3.set_title("Top Interfaces by Speed (Mb/s)")
            ax3.set_ylabel("Mb/s")
            ax3.tick_params(axis='x', rotation=45)
            st.pyplot(fig3)

    # ===== Transceivers =====
    st.subheader("Transceivers")
    st.dataframe(df_xcvr, use_container_width=True)

    # ===== Environment =====
    st.subheader("Environment (temps, fans, PSU)")
    st.dataframe(df_env, use_container_width=True)
    if not df_env.empty and df_env["value"].notna().any():
        tmp = df_env.dropna(subset=["value"]).copy()
        fig4, ax4 = plt.subplots()
        ax4.bar(tmp["sensor"], tmp["value"])
        ax4.set_title("Sensor Values")
        ax4.set_ylabel("Value")
        ax4.tick_params(axis='x', rotation=45)
        st.pyplot(fig4)

    # ===== Logs =====
    st.subheader("Logs")
    st.dataframe(df_log, use_container_width=True)
    if not df_log.empty:
        sev_counts = df_log["severity"].fillna("-").value_counts().reset_index()
        sev_counts.columns = ["severity", "count"]
        fig5, ax5 = plt.subplots()
        ax5.bar(sev_counts["severity"], sev_counts["count"])
        ax5.set_title("Log Severity Counts")
        ax5.set_ylabel("Count")
        st.pyplot(fig5)

    # ===== Downloads =====
    st.subheader("Download parsed data")
    def _download_button(df: pd.DataFrame, label: str, fname: str):
        if df is None:
            return
        if isinstance(df, dict):
            # wrap small dicts
            ddf = pd.DataFrame([df])
        else:
            ddf = df
        csv = ddf.to_csv(index=False).encode("utf-8")
        st.download_button(label=label, data=csv, file_name=fname, mime="text/csv")

    _download_button(pd.DataFrame([system]) if system else pd.DataFrame(), "Download system.csv", "system.csv")
    _download_button(df_if, "Download interfaces.csv", "interfaces.csv")
    _download_button(df_xcvr, "Download transceivers.csv", "transceivers.csv")
    _download_button(df_env, "Download environment.csv", "environment.csv")
    _download_button(df_log, "Download logs.csv", "logs.csv")

else:
    st.info("Upload a CLI dump file to parse and visualize.")
