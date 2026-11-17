"""SCM lifecycle with bounded waits; invoked elevated by Setup/uninstaller."""
import sys
import time

NAME = "HUGINNSmartConnector"


def run(action):
    import pywintypes
    import win32service as svc
    scm = svc.OpenSCManager(None, None, svc.SC_MANAGER_ALL_ACCESS)
    service = None
    try:
        try:
            service = svc.OpenService(scm, NAME, svc.SERVICE_ALL_ACCESS)
        except pywintypes.error as exc:
            if exc.winerror != 1060:
                raise
        if action == "--install-service":
            binary = '"' + sys.executable + '" --service'
            if service is None:
                service = svc.CreateService(scm, NAME, "HUGINN Smart Connector",
                    svc.SERVICE_ALL_ACCESS, svc.SERVICE_WIN32_OWN_PROCESS,
                    svc.SERVICE_AUTO_START, svc.SERVICE_ERROR_NORMAL, binary,
                    None, 0, None, r"NT AUTHORITY\LocalService", None)
            else:
                svc.ChangeServiceConfig(service, svc.SERVICE_NO_CHANGE, svc.SERVICE_AUTO_START,
                    svc.SERVICE_ERROR_NORMAL, binary, None, 0, None,
                    r"NT AUTHORITY\LocalService", None, "HUGINN Smart Connector")
            svc.ChangeServiceConfig2(service, svc.SERVICE_CONFIG_DESCRIPTION,
                                     "HUGINN Oracle Thin read-only local API")
            svc.StartService(service, None)
            wait(service, svc.SERVICE_RUNNING)
        elif service is not None:
            if svc.QueryServiceStatus(service)[1] != svc.SERVICE_STOPPED:
                svc.ControlService(service, svc.SERVICE_CONTROL_STOP)
                wait(service, svc.SERVICE_STOPPED)
            if action == "--remove-service":
                svc.DeleteService(service)
    finally:
        if service is not None:
            svc.CloseServiceHandle(service)
        svc.CloseServiceHandle(scm)


def wait(service, state):
    import win32service
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if win32service.QueryServiceStatus(service)[1] == state:
            return
        time.sleep(.25)
    raise TimeoutError("SCM transition timed out")
