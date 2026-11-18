"""diag-v2 collection run, end to end against a fake AOS-CX REST API."""
import main2

DATASETS = [
    "system", "version", "interface_brief", "transceiver", "transceiver_detail",
    "environment", "health", "resource_utilization", "process_cpu",
    "process_memory", "logging", "event_history",
]


def test_saves_every_dataset_as_json_and_text(switches, workdir):
    root = workdir(["192.0.2.10,admin,pw-123,v10.11"])

    main2.main()

    out = root / "data" / "192.0.2.10"
    missing = [f"{d}.{ext}" for d in DATASETS for ext in ("json", "txt")
               if not (out / f"{d}.{ext}").exists()]
    assert missing == []


def test_text_report_is_human_readable(switches, workdir):
    root = workdir(["192.0.2.10,admin,pw-123,v10.11"])

    main2.main()

    text = (root / "data" / "192.0.2.10" / "system.txt").read_text(encoding="utf-8")
    assert "path: /system" in text


def test_failing_endpoint_does_not_block_other_datasets(switches, workdir):
    root = workdir(["192.0.2.10,admin,pw-123,v10.11"])
    switches.status["/system/health"] = 404

    main2.main()

    out = root / "data" / "192.0.2.10"
    assert not (out / "health.json").exists()
    assert (out / "system.json").exists()
    assert (out / "event_history.json").exists()


def test_logout_is_sent_even_when_every_request_fails(switches, workdir):
    workdir(["192.0.2.10,admin,pw-123,v10.11"])
    switches.fail_all_gets = True

    main2.main()

    posts = [path for _, _, path, _, _ in switches.calls_for("192.0.2.10", "POST")]
    assert posts == ["/login", "/logout"]


def test_login_sends_credentials_in_form_body_not_in_url(switches, workdir):
    workdir(["192.0.2.10,admin,pw-123,v10.11"])

    main2.main()

    _, _, path, kw, _ = switches.calls_for("192.0.2.10", "POST")[0]
    assert path == "/login"
    assert kw.get("data") == {"username": "admin", "password": "pw-123"}
    assert kw.get("params") is None and kw.get("json") is None


def test_failed_login_skips_device_and_continues_with_next(switches, workdir):
    root = workdir(["192.0.2.10,admin,wrong,v10.11", "192.0.2.11,admin,pw-123,v10.11"])
    switches.login_status["192.0.2.10"] = 401

    main2.main()

    assert not (root / "data" / "192.0.2.10").exists()
    assert (root / "data" / "192.0.2.11" / "system.json").exists()


def test_tls_verification_follows_optional_verify_column(switches, workdir):
    workdir(["192.0.2.10,admin,pw,v10.11,ca.pem", "192.0.2.11,admin,pw,v10.11,"],
            header="ip,username,password,api_version,verify")

    main2.main()

    assert {c[4] for c in switches.calls_for("192.0.2.10")} == {"ca.pem"}
    assert {c[4] for c in switches.calls_for("192.0.2.11")} == {False}
