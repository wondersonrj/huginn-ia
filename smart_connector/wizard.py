"""Elevated, local-only configuration UI; secrets never pass on the command line."""
import tkinter as tk
from tkinter import messagebox

from smart_connector import config
from smart_connector.api import oracle_operation


def run():
    config.initialize()
    cfg = config.load()
    root = tk.Tk()
    root.title("HUGINN Smart Connector — Configuração")
    fields = {}
    labels = [("oracle_host", "Host Oracle"), ("oracle_port", "Porta Oracle"),
              ("oracle_service", "Service Name (não SID)"), ("oracle_user", "Usuário somente SELECT"),
              ("oracle_password", "Senha Oracle"), ("host", "IP de escuta API"),
              ("port", "Porta API"), ("tls_cert", "Caminho certificado PEM TLS"),
              ("tls_key", "Caminho chave privada PEM TLS"), ("token", "Token Bearer da API")]
    for row, (key, label) in enumerate(labels):
        tk.Label(root, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=3)
        entry = tk.Entry(root, width=55, show="*" if key in {"token", "oracle_password"} else "")
        entry.insert(0, str(cfg[key]))
        entry.grid(row=row, column=1, padx=8)
        fields[key] = entry
    remote = tk.BooleanVar(value=cfg["remote_authorized"])
    tk.Checkbutton(root, text="Autorizo acesso remoto com TLS e regras de rede aprovadas",
                   variable=remote).grid(row=10, columnspan=2)
    tk.Label(root, text="API local por padrão. Nenhuma regra de firewall é criada.\n"
                         "Após salvar, reinicie o serviço. Oracle 19c requer conta compatível com Thin.").grid(row=11, columnspan=2)

    def current():
        result = dict(cfg, **{k: entry.get() for k, entry in fields.items()})
        result.update(port=int(result["port"]), oracle_port=int(result["oracle_port"]), remote_authorized=remote.get())
        config.validate(result)
        return result

    def save():
        try:
            config.save(current())
        except Exception:
            messagebox.showerror("Configuração", "Não foi possível salvar. Confira portas, token, TLS e permissões administrativas.")
            return
        root.destroy()

    def test():
        try:
            oracle_operation(current(), "/oracle/test")
            messagebox.showinfo("Oracle", "Conexão Thin e SELECT 1 bem-sucedidos.")
        except Exception:
            messagebox.showerror("Oracle", "Falha no teste. Confira host, Service Name, rede, senha e requisitos Thin com o DBA.")

    tk.Button(root, text="Testar Oracle", command=test).grid(row=12, column=0, pady=8)
    tk.Button(root, text="Salvar", command=save).grid(row=12, column=1)
    root.mainloop()
