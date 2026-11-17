"""Windows integration using only fake data; never connects to an Oracle server."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from smart_connector import config
import win32service
import win32serviceutil
import win32api
import win32process

APP = Path(os.environ["ProgramW6432"]) / "HUGINN Smart Connector"
EXE = APP / "HUGINNConnector.exe"
NAME = "HUGINNSmartConnector"
OUTPUT = ROOT / "work/connector-output"
SETUP = OUTPUT / "HUGINN_Smart_Connector_Setup.exe"
results = []


def command(exe, *args):
    env = dict(os.environ, PATH=os.path.join(os.environ["SystemRoot"], "System32"),
               PYTHONHOME="", PYTHONPATH="")
    subprocess.run([str(exe), *args], env=env, check=True, timeout=120)


def health(token):
    request = urllib.request.Request("http://127.0.0.1:8765/health", headers={"Authorization": "Bearer " + token})
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)
        except urllib.error.HTTPError:
            raise
        except OSError:
            time.sleep(.3)
    raise AssertionError("Local health did not become ready")


def install(path):
    command(path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")


def uninstall(purge=False):
    command(APP / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/PURGEDATA=1" if purge else "/PURGEDATA=0")
    assert not EXE.exists()
    try:
        win32serviceutil.QueryServiceStatus(NAME)
    except Exception as exc:
        assert exc.winerror == 1060
    else:
        raise AssertionError("Service still registered")


def main():
    digest = hashlib.sha256(SETUP.read_bytes()).hexdigest()
    assert (SETUP.with_suffix(".exe.sha256")).read_text().split()[0] == digest
    install(ROOT / "work/connector-upgrade-fixture/HUGINN_Smart_Connector_Setup.exe")
    command(EXE, "--runtime-check")
    cfg = config.load()
    assert cfg["host"] == "127.0.0.1" and not cfg["oracle_password"]
    assert health(cfg["token"])["status"] == "ok"
    # All request parameters are fake, and no DB is configured or contacted.
    try:
        health("incorrect-token")
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    else:
        raise AssertionError("API accepted wrong token")
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    service = win32service.OpenService(scm, NAME, win32service.SERVICE_QUERY_CONFIG | win32service.SERVICE_QUERY_STATUS)
    details = win32service.QueryServiceConfig(service)
    pid = win32service.QueryServiceStatusEx(service)["ProcessId"]
    win32service.CloseServiceHandle(service)
    win32service.CloseServiceHandle(scm)
    assert details[1] == win32service.SERVICE_AUTO_START
    assert "LocalService" in details[7]
    assert str(EXE).lower() in details[3].lower()
    # Exercise driver import in the service account, without any configured DB or network call.
    request = urllib.request.Request("http://127.0.0.1:8765/oracle/test",
                                    headers={"Authorization": "Bearer " + cfg["token"]})
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        assert exc.code == 503 and json.load(exc)["error"] == "oracle_unavailable"
    else:
        raise AssertionError("Unconfigured Oracle unexpectedly succeeded")
    process = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
    try:
        modules = [win32process.GetModuleFileNameEx(process, module).lower()
                   for module in win32process.EnumProcessModules(process)]
    finally:
        win32api.CloseHandle(process)
    python_dlls = [name for name in modules if Path(name).name.startswith("python") and name.endswith(".dll")]
    assert python_dlls and all(name.startswith(str(APP).lower() + "\\") for name in python_dlls)
    assert not any(Path(name).name == "oci.dll" for name in modules)
    results.append("install + bundled Thin runtime + auto LocalService + authenticated local health: PASS")
    command(EXE, "--stop-service")
    assert win32serviceutil.QueryServiceStatus(NAME)[1] == win32service.SERVICE_STOPPED
    cfg["oracle_password"] = "FAKE-CI-NOT-A-CREDENTIAL"
    config.save(cfg)
    before = (config.data_dir() / "config.dpapi").read_bytes()
    marker = config.data_dir() / "upgrade-marker.log"
    marker.write_text("preserve logs")
    install(SETUP)
    assert health(cfg["token"])["version"] == "0.2.1"
    assert (config.data_dir() / "config.dpapi").read_bytes() == before
    assert marker.read_text() == "preserve logs"
    command(EXE, "--stop-service")
    command(EXE, "--install-service")
    assert health(cfg["token"])["status"] == "ok"
    results.append("stop/start + synthetic 0.2.0 metadata to 0.2.1 update preserves config/token/logs: PASS")
    uninstall()
    assert (config.data_dir() / "config.dpapi").read_bytes() == before
    # Reinstall restores operation with the same protected configuration.
    install(SETUP)
    assert health(cfg["token"])["status"] == "ok"
    uninstall(purge=True)
    assert not config.data_dir().exists()
    results.append("uninstall removes service/binaries; retained configuration survives reinstall; explicit purge removes data: PASS")
    report = dict(tests=results, oracle_real="NOT RUN", totvs_cloud="NOT RUN",
                  environment="GitHub hosted Windows; Python removed from child PATH, bundled runtime checked; not a pristine VM")
    (OUTPUT / "windows-test-results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
