"""Proposed report request contract, NOT an enabled Oracle executor or live route."""
from dataclasses import dataclass
from datetime import date
import re

from smart_connector.capabilities import REPORT_MODULES


class ContractError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class Scope:
    branches: frozenset[str]
    modules: frozenset[str]


@dataclass(frozen=True)
class Request:
    module: str
    branch: str
    start: date
    end: date
    page: int
    page_size: int


def validate_request(module, pairs, scope):
    if module not in REPORT_MODULES:
        raise ContractError("unknown_operation", 404)
    values = {}
    for key, value in pairs:
        if key not in {"filial", "inicio", "fim", "pagina", "limite"} or key in values:
            raise ContractError("invalid_parameters")
        if not isinstance(value, str):
            raise ContractError("invalid_parameters")
        values[key] = value
    if not {"filial", "inicio", "fim"} <= values.keys():
        raise ContractError("missing_parameters")
    branch = values["filial"]
    if not re.fullmatch(r"[1-9][0-9]{0,5}", branch):
        raise ContractError("invalid_branch")
    # Never derive authorization from a branch supplied by the caller.
    if branch not in scope.branches or module not in scope.modules:
        raise ContractError("permission_denied", 403)
    try:
        if not all(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", values[k]) for k in ("inicio", "fim")):
            raise ValueError()
        start, end = date.fromisoformat(values["inicio"]), date.fromisoformat(values["fim"])
        if not 0 <= (end - start).days <= 30:
            raise ValueError()
        page_text, size_text = values.get("pagina", "1"), values.get("limite", "100")
        if not re.fullmatch(r"[0-9]{1,4}", page_text) or not re.fullmatch(r"[0-9]{1,3}", size_text):
            raise ValueError()
        page, size = int(page_text), int(size_text)
        if not 1 <= page <= 1000 or not 1 <= size <= 200 or (page - 1) * size > 10000:
            raise ValueError()
    except (ValueError, TypeError):
        raise ContractError("invalid_range_or_pagination") from None
    return Request(module, branch, start, end, page, size)
