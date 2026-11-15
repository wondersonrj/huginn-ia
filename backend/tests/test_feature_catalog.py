"""Versioned user inventory cannot advertise nonexistent APIs or test evidence."""
import ast
from datetime import date
import json
from pathlib import Path
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / 'frontend/src/data/features.json').read_text())
NAV = json.loads((ROOT / 'frontend/src/data/navigation.json').read_text())


def test_evidence_symbols_and_routes_exist():
    assert CATALOG['schema_version'] == 1
    assert date.fromisoformat(CATALOG['reviewed_at']) <= date.today()
    ids = set()
    routes = set(app.openapi()['paths'])
    if '/api/updates/{action}' in routes:
        routes |= {'/api/updates/check', '/api/updates/apply'}
    modules = {n['id'] for n in NAV}
    for feature in CATALOG['features']:
        assert feature['id'] not in ids; ids.add(feature['id'])
        assert feature['module'] in modules
        assert feature['status'] in {'disponivel','em_homologacao','planejado'}
        for key in ('title','purpose','inputs','expected','steps','limits'):
            assert feature[key]
        validation = feature['validation']
        assert validation['scope'] and validation['gap'] and validation['evidence']
        assert date.fromisoformat(validation['last_checked']) <= date.fromisoformat(CATALOG['reviewed_at'])
        for evidence in validation['evidence']:
            path = (ROOT / evidence['file']).resolve()
            assert path.is_relative_to(ROOT) and path.is_file()
            symbols = {n.name for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
            assert evidence['symbol'] in symbols, evidence
        assert set(feature['api_routes']) <= routes
    assert {'nfe-xml','products','suppliers','saved-profiles','schema','windows-setup','signed-update','local-access','validation-report'} <= ids


def test_planned_features_have_no_active_api():
    planned = [f for f in CATALOG['features'] if f['status'] == 'planejado']
    assert {f['id'] for f in planned} == {'sefaz','erp-comparison'}
    assert all(not f['api_routes'] for f in planned)
    assert not any('sefaz' in path.lower() for path in app.openapi()['paths'])


def test_browser_catalog_evidence_is_executed_not_only_declared():
    tree = ast.parse((ROOT / 'packaging/windows/browser_smoke.py').read_text())
    run = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'run')
    calls = {n.func.id for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    for feature in CATALOG['features']:
        for evidence in feature['validation']['evidence']:
            if evidence['file'] == 'packaging/windows/browser_smoke.py':
                assert evidence['symbol'] in calls


def test_one_connection_ui_and_no_frontend_persistence():
    main = (ROOT / 'frontend/src/main.tsx').read_text()
    assert 'OracleConnection' not in main
    assert main.count('<ConnectionManager ') == 1
    assert len(NAV) == len({n['id'] for n in NAV}) == 7
    for path in (ROOT / 'frontend/src').glob('*.tsx'):
        assert 'localStorage.setItem' not in path.read_text() and 'sessionStorage.setItem' not in path.read_text()
