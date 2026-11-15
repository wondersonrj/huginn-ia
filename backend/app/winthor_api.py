"""Local authenticated catalog API with metadata-only audit records."""
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from app import winthor
from app.connection_store import Conflict, SelectionRequired
from app.windows_secrets import VaultError
from app.local_session import app_port, session_authorized, automatic, current_sid
from app.oracle_connector import connection_diagnostic

router = APIRouter(prefix='/api/winthor')
audit = logging.getLogger('huginn.audit')
audit.setLevel(logging.INFO)
if not audit.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    audit.addHandler(handler)
if automatic():
    from pathlib import Path
    from logging.handlers import RotatingFileHandler
    from app.windows_secrets import private_permissions
    state_path = Path(os.environ['HUGINN_STATE_DIR'])
    private_permissions(state_path, current_sid())
    audit_path = state_path / 'audit.jsonl'
    file_handler = RotatingFileHandler(audit_path, maxBytes=1024 * 1024, backupCount=2, encoding='utf-8')
    private_permissions(audit_path, current_sid())
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    audit.addHandler(file_handler)
ORIGINS = {f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (app_port(), 5173)}
HOSTS = {f'{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (app_port(), 5173)}


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    connection_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    connection_revision: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


class SearchRequest(ContextRequest):
    codigo: int | None = Field(default=None, ge=1, le=9999999999)
    nome: str = Field(default='', max_length=80)
    pagina: int = Field(default=1, ge=1, le=100)
    tamanho: int = Field(default=20, ge=1, le=50)


def authorize(request):
    if (not request.client or request.client.host not in {'127.0.0.1', '::1'}
            or request.headers.get('host') not in HOSTS
            or (request.headers.get('origin') is not None and request.headers['origin'] not in ORIGINS)):
        raise HTTPException(403, 'Acesso permitido somente pela interface local autorizada')
    if session_authorized(request):
        return
    expected = os.environ.get('HUGINN_API_TOKEN', '')
    if len(expected) < 32:
        raise HTTPException(503, 'Configure um token de acesso local com pelo menos 32 caracteres')
    supplied = request.headers.get('authorization', '')
    if not hmac.compare_digest(supplied.encode('utf-8'), f'Bearer {expected}'.encode('utf-8')):
        raise HTTPException(401, 'Token de acesso local inválido ou ausente', headers={'WWW-Authenticate': 'Bearer'})


def record(action, request_id, started, status, count=0, mode='unknown'):
    audit.info(json.dumps(dict(instante_utc=datetime.now(timezone.utc).isoformat(), evento='winthor', acao=action, request_id=request_id,
                              status=status, modo=mode, registros=count,
                              duracao_ms=round((time.monotonic() - started) * 1000)), ensure_ascii=False))


async def handle(request, action):
    started, request_id, status, count, mode = time.monotonic(), uuid.uuid4().hex, 500, 0, 'unknown'
    try:
        authorize(request)
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise HTTPException(415, 'Envie uma solicitação JSON')
        # Never rely on Content-Length supplied by the caller; bound streamed bodies.
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 2048:
                raise HTTPException(413, 'Solicitação acima do limite permitido')
            body.extend(chunk)
        try:
            data = json.loads(body)
            if action in {'health', 'diagnostico'}:
                query = ContextRequest.model_validate(data)
            else:
                query = SearchRequest.model_validate(data)
        except (ValueError, ValidationError):
            raise HTTPException(422, 'Filtros inválidos: código positivo, nome até 80 caracteres, página 1–100 e tamanho 1–50') from None
        try:
            settings = await run_in_threadpool(winthor.Settings.load, query.connection_id, query.connection_revision)
        except (SelectionRequired, Conflict):
            raise HTTPException(409, 'Selecione e confirme a conexão atual antes de consultar; nenhum destino alternativo foi usado') from None
        except (VaultError, OSError):
            raise HTTPException(503, 'Senha/cofre indisponível para este usuário; revise a conexão salva sem fallback automático') from None
        except ValueError:
            raise HTTPException(503, 'Configuração local inválida: revise modo, schema e variáveis Oracle no servidor') from None
        mode = 'simulado' if settings.mode == 'demo' else 'oracle'
        try:
            if action == 'health':
                result = await run_in_threadpool(winthor.health, settings)
                if not result['disponivel']:
                    raise HTTPException(502, 'Oracle não confirmou a conectividade')
            elif action == 'diagnostico':
                result = await run_in_threadpool(winthor.diagnostic, settings)
            else:
                result = await run_in_threadpool(winthor.search, settings, action,
                                                query.codigo, query.nome, query.pagina, query.tamanho)
                count = len(result['itens'])
        except winthor.SchemaUnavailable:
            raise HTTPException(409, 'Schema não confirmado: execute Diagnosticar estrutura; confira owner e colunas. Não é possível presumir falta de SELECT.') from None
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, connection_diagnostic(exc)) from None
        status = 200
        return dict(**result, request_id=request_id, connection=settings.profile and {k: settings.profile[k] for k in ('id', 'revision', 'name', 'environment')})
    except HTTPException as exc:
        status = exc.status_code
        # Correlate rejected requests as well, without recording their content.
        exc.headers = {**(exc.headers or {}), 'X-Request-ID': request_id, 'Cache-Control': 'no-store'}
        raise
    finally:
        record(action, request_id, started, status, count, mode)


@router.post('/health')
async def health(request: Request):
    return await handle(request, 'health')


@router.post('/diagnostico')
async def diagnostic(request: Request):
    return await handle(request, 'diagnostico')


@router.post('/produtos')
async def products(request: Request):
    return await handle(request, 'produtos')


@router.post('/fornecedores')
async def suppliers(request: Request):
    return await handle(request, 'fornecedores')
