"""Test utilities: a fake network that answers like the AOS-CX REST API."""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeSwitches:
    """Replaces the HTTP layer only; the client code under test stays real.

    - POST .../login  -> 200 with an empty body (as AOS-CX does), or login_status[ip]
    - POST .../logout -> 200 with an empty body
    - GET  ...        -> 200 {"path": "<path?query>"}, or status[path], or a
                         ConnectionError when fail_all_gets is set
    """

    def __init__(self):
        self.calls = []          # (method, ip, path, kwargs, session.verify)
        self.status = {}         # path -> HTTP status for GETs
        self.login_status = {}   # ip -> HTTP status for login
        self.fail_all_gets = False

    def request(self, session, method, url, **kw):
        parts = urlsplit(url)
        ip = parts.hostname
        # strip "/rest/<version>"
        path = "/" + parts.path.split("/", 3)[3] if parts.path.count("/") >= 3 else parts.path
        if parts.query:
            path += "?" + parts.query
        method = method.upper()
        self.calls.append((method, ip, path, kw, session.verify))

        if method == "POST" and path.endswith("/login"):
            return self._response(url, self.login_status.get(ip, 200), b"")
        if method == "POST" and path.endswith("/logout"):
            return self._response(url, 200, b"")
        if self.fail_all_gets:
            raise requests.ConnectionError(f"unreachable: {url}")
        code = self.status.get(path, 200)
        body = json.dumps({"path": path} if code == 200 else {"error": code}).encode()
        return self._response(url, code, body)

    @staticmethod
    def _response(url, code, body):
        r = requests.Response()
        r.url = url
        r.status_code = code
        r.reason = {200: "OK", 401: "Unauthorized", 404: "Not Found"}.get(code, "")
        r._content = body
        r.encoding = "utf-8"
        r.headers["Content-Type"] = "application/json"
        return r

    def calls_for(self, ip, method=None):
        return [c for c in self.calls if c[1] == ip and (method is None or c[0] == method)]


@pytest.fixture
def switches(monkeypatch):
    fake = FakeSwitches()
    monkeypatch.setattr(
        requests.Session, "request",
        lambda self, method, url, **kw: fake.request(self, method, url, **kw),
    )
    return fake


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Run main2 from an empty folder holding only devices.csv."""
    monkeypatch.chdir(tmp_path)

    def write_devices(rows, header="ip,username,password,api_version"):
        (tmp_path / "devices.csv").write_text(
            header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
        return tmp_path

    return write_devices
