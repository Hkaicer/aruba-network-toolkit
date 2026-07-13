# scripts/api_client.py
import requests

class ArubaCXAPIClient:
    def __init__(self, ip, username, password, api_version="v10.11"):
        self.ip = ip
        self.username = username
        self.password = password
        self.api_version = api_version
        self.base_url = f"https://{ip}/rest/{api_version}"
        self.session = requests.Session()
        self.session.verify = False  # désactive SSL vérif pour tests en lab

    def login(self):
        url = f"{self.base_url}/login"
        payload = {"username": self.username, "password": self.password}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def logout(self):
        url = f"{self.base_url}/logout"
        resp = self.session.post(url)
        resp.raise_for_status()
        return resp.json()

    def get_interface_brief(self):
        url = f"{self.base_url}/system/interfaces"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_interface_transceiver(self):
        url = f"{self.base_url}/system/interfaces/transceivers"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_system(self):
        url = f"{self.base_url}/system"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()


    def get_version(self):
        # parfois la version est déjà incluse dans /system
        url = f"{self.base_url}/system/status"
        resp = self.session.get(url)
        if resp.status_code == 404:
            # fallback
            url = f"{self.base_url}/system"
            resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_environment(self):
        url = f"{self.base_url}/system/environment"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # Interfaces
    # -------------------------
    def get_interface_brief(self):
        url = f"{self.base_url}/system/interfaces"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_interface_transceiver(self):
        url = f"{self.base_url}/system/interfaces/transceivers"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_interface_transceiver_detail(self):
        url = f"{self.base_url}/system/interfaces/transceivers?details=true"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # Health & Resources
    # -------------------------
    def get_health(self):
        url = f"{self.base_url}/system/health"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_resource_utilization(self):
        url = f"{self.base_url}/system/resource-utilization"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # Processes
    # -------------------------
    def get_processes_cpu(self):
        url = f"{self.base_url}/system/processes?type=cpu"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_processes_memory(self):
        url = f"{self.base_url}/system/processes?type=memory"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # Logs & Events
    # -------------------------
    def get_logging(self):
        url = f"{self.base_url}/system/logs"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_event_history(self):
        url = f"{self.base_url}/system/event-logs"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()
