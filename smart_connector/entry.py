"""Frozen service entry point; maintenance switches carry no secrets."""
import logging
from logging.handlers import RotatingFileHandler
import sys
import threading

from smart_connector import config
from smart_connector.api import make_server


def main():
    if "--runtime-check" in sys.argv:
        import oracledb
        import tkinter
        import win32crypt
        import servicemanager
        if not oracledb.is_thin_mode():
            raise SystemExit(1)
        return
    if any(arg in sys.argv for arg in ("--install-service", "--stop-service", "--remove-service")):
        from smart_connector.maintenance import run
        run(sys.argv[1])
        return
    if "--init" in sys.argv:
        config.initialize()
        return
    if "--configure" in sys.argv:
        from smart_connector.wizard import run
        run()
        return
    import servicemanager
    import win32service
    import win32serviceutil

    class ConnectorService(win32serviceutil.ServiceFramework):
        _svc_name_ = "HUGINNSmartConnector"
        _svc_display_name_ = "HUGINN Smart Connector"

        def __init__(self, args):
            super().__init__(args)
            self.stopping = threading.Event()
            self.server = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.stopping.set()

        def SvcDoRun(self):
            try:
                handler = RotatingFileHandler(config.data_dir() / "connector.log", maxBytes=1024*1024,
                                              backupCount=5, encoding="utf-8")
                logging.basicConfig(level=logging.INFO, handlers=[handler],
                                    format="%(asctime)s %(levelname)s %(message)s")
                self.server = make_server(config.load())
                worker = threading.Thread(target=self.server.serve_forever, daemon=True)
                worker.start()
                logging.info("Service listening; configuration loaded")
                self.stopping.wait()
                self.server.shutdown()
                self.server.server_close()
                worker.join(timeout=10)
                logging.info("Service stopped")
            except Exception:
                # Fixed diagnostic deliberately excludes raw paths, passwords and driver errors.
                servicemanager.LogErrorMsg("HUGINN: startup failed; check protected configuration, port, TLS and data ACL")
                raise SystemExit(1) from None

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(ConnectorService)
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    main()
