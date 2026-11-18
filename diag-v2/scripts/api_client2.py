# scripts/api_client2.py
"""Minimal Aruba AOS-CX REST client (session-cookie authentication)."""
import requests
import urllib3


class ArubaCXAPIClient:
    def __init__(self, ip, username, password, api_version="v10.11", verify=False, timeout=10):
        """verify: False (lab, self-signed cert), True (system CAs) or a CA bundle path."""
        self.ip = ip
        self.username = username
        self.password = password
        self.api_version = api_version
        self.timeout = timeout
        self.base_url = f"https://{ip}/rest/{api_version}"
        self.session = requests.Session()
        self.session.verify = verify
        self.logged_in = False
        if verify is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # -------------------------
    # Session
    # -------------------------
    def login(self):
        """Open a session. Credentials go in the form body, never in the URL.

        AOS-CX answers 200 with an empty body and a session cookie.
        Returns True on success, False when the switch rejects the login.
        Network errors raise requests.RequestException.
        """
        resp = self.session.post(
            f"{self.base_url}/login",
            data={"username": self.username, "password": self.password},
            timeout=self.timeout,
        )
        self.logged_in = resp.status_code == 200
        return self.logged_in

    def logout(self):
        """Close the session (best effort): AOS-CX allows few sessions per user."""
        if not self.logged_in:
            return
        try:
            self.session.post(f"{self.base_url}/logout", timeout=self.timeout)
        except requests.RequestException:
            pass
        finally:
            self.logged_in = False

    def _get(self, path):
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # -------------------------
    # System
    # -------------------------
    def get_system(self):
        return self._get("/system")

    def get_version(self):
        # some releases expose /system/status, otherwise the version is in /system
        try:
            return self._get("/system/status")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return self._get("/system")
            raise

    def get_environment(self):
        return self._get("/system/environment")

    # -------------------------
    # Interfaces
    # -------------------------
    def get_interface_brief(self):
        return self._get("/system/interfaces")

    def get_interface_transceiver(self):
        return self._get("/system/interfaces/transceivers")

    def get_interface_transceiver_detail(self):
        return self._get("/system/interfaces/transceivers?details=true")

    # -------------------------
    # Health & Resources
    # -------------------------
    def get_health(self):
        return self._get("/system/health")

    def get_resource_utilization(self):
        return self._get("/system/resource-utilization")

    # -------------------------
    # Processes
    # -------------------------
    def get_processes_cpu(self):
        return self._get("/system/processes?type=cpu")

    def get_processes_memory(self):
        return self._get("/system/processes?type=memory")

    # -------------------------
    # Logs & Events
    # -------------------------
    def get_logging(self):
        return self._get("/system/logs")

    def get_event_history(self):
        return self._get("/system/event-logs")
