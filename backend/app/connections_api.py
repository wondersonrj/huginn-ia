"""Authenticated local CRUD. Never serialize OracleConfig or return decrypted secrets."""
import json
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from starlette.concurrency import run_in_threadpool
from app.connection_store import Conflict, SelectionRequired, current_store
from app.oracle_connector import OracleConfig, check_connection, connection_diagnostic
from app.windows_secrets import VaultError
from app.winthor_api import authorize, record
import os

router = APIRouter(prefix='/api/connections')
ID = r'^[a-f0-9]{32}$'


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str | None = Field(default=None, pattern=ID)
    revision: str | None = Field(default=None, pattern=ID)
    name: str = Field(min_length=1, max_length=80)
    environment: str = Field(pattern=r'^(TESTE|PRODUCAO)$')
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    service: str = Field(min_length=1, max_length=255)
    user: str = Field(min_length=1, max_length=128)
    owner: str = Field(pattern=r'^[A-Z][A-Z0-9_]{0,29}$')
    password: SecretStr | None = Field(default=None, min_length=1, max_length=1024)


class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=ID)
    revision: str = Field(pattern=ID)
    confirm_environment: str | None = Field(default=None, pattern=r'^(TESTE|PRODUCAO)$')


class ImportInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(min_length=1, max_length=80)
    environment: str = Field(pattern=r'^(TESTE|PRODUCAO)$')


def operate(action, data):
    store = current_store()
    if action == 'list':
        if data != {}:
            raise ValueError()
        return store.listing() if store else dict(supported=False, profiles=[], active=None, source='environment')
    if not store:
        raise VaultError('Windows secure storage required')
    if action == 'environment':
        if data != {'confirm': 'USAR CONFIGURACAO DO AMBIENTE'}:
            raise ValueError()
        store.environment()
        return dict(source='environment', active=None)
    if action == 'save':
        profile = ProfileInput.model_validate(data)
        if bool(profile.id) != bool(profile.revision):
            raise ValueError()
        fields = profile.model_dump(exclude={'id', 'revision', 'password'})
        password = profile.password.get_secret_value() if profile.password is not None else None
        return dict(profile=store.save(fields, password, profile.id, profile.revision))
    if action == 'import-environment':
        profile = ImportInput.model_validate(data)
        if os.environ.get('HUGINN_WINTHOR_MODE') != 'oracle':
            raise ValueError()
        cfg = OracleConfig.from_env(); cfg.validate()
        fields = dict(name=profile.name, environment=profile.environment, host=cfg.host,
                      port=cfg.port, service=cfg.service, user=cfg.user, owner=os.environ.get('HUGINN_ORACLE_OWNER', ''))
        return dict(profile=store.save(fields, cfg.password))
    ref = Reference.model_validate(data)
    if action == 'select':
        return dict(active=store.choose(ref.id, ref.revision, ref.confirm_environment), source='saved')
    if action in {'delete', 'remove-password'}:
        store.remove(ref.id, ref.revision, password_only=action == 'remove-password')
        return dict(active=None, status='removed')
    if action == 'test':
        resolved = store.for_test(ref.id, ref.revision, ref.confirm_environment)
        try:
            result = check_connection(resolved.config)
            if not result['conectado']:
                raise RuntimeError('Read-only check not confirmed')
        except Exception as exc:
            store.tests[ref.id] = dict(ok=False, revision=ref.revision, checked_at=datetime.now(timezone.utc).isoformat())
            raise HTTPException(502, connection_diagnostic(exc)) from None
        store.tests[ref.id] = dict(ok=True, revision=ref.revision, checked_at=datetime.now(timezone.utc).isoformat())
        return dict(conectado=True, persistent_session=False, mensagem='Teste pontual DUAL confirmado; sessão encerrada sem commit.')
    raise ValueError()


async def handle(request, action):
    started, request_id, status = time.monotonic(), uuid.uuid4().hex, 500
    try:
        authorize(request)
        if request.headers.get('content-type', '').split(';')[0] != 'application/json':
            raise HTTPException(415, 'Envie JSON')
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                raise HTTPException(413, 'Solicitação acima do limite permitido')
            body.extend(chunk)
        try:
            result = await run_in_threadpool(operate, action, json.loads(body))
        except (ValidationError, ValueError):
            raise HTTPException(422, 'Dados de conexão inválidos; revise campos e confirmação') from None
        except (Conflict, SelectionRequired):
            raise HTTPException(409, 'Conexão alterada ou confirmação ausente; recarregue e confirme o ambiente') from None
        except (VaultError, OSError):
            raise HTTPException(503, 'Cofre indisponível: requer Windows, mesmo usuário/instalação, senha válida e arquivos íntegros. Nenhum fallback de senha foi usado.') from None
        status = 200
        return dict(**result, request_id=request_id)
    except HTTPException as exc:
        status = exc.status_code
        exc.headers = {**(exc.headers or {}), 'X-Request-ID': request_id, 'Cache-Control': 'no-store'}
        raise
    finally:
        record('connections_' + action, request_id, started, status)


# Fixed actions only: no paths, SQL, export or secret-retrieval endpoint.
@router.post('/list')
async def list_profiles(request: Request):
    return await handle(request, 'list')


@router.post('/save')
async def save(request: Request):
    return await handle(request, 'save')


@router.post('/delete')
async def delete(request: Request):
    return await handle(request, 'delete')


@router.post('/remove-password')
async def remove_password(request: Request):
    return await handle(request, 'remove-password')


@router.post('/select')
async def select(request: Request):
    return await handle(request, 'select')


@router.post('/test')
async def test(request: Request):
    return await handle(request, 'test')


@router.post('/environment')
async def environment(request: Request):
    return await handle(request, 'environment')


@router.post('/import-environment')
async def import_environment(request: Request):
    return await handle(request, 'import-environment')
