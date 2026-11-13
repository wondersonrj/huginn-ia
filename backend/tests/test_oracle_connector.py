from app.oracle_connector import OracleConfig
import pytest

def test_missing_credentials():
    with pytest.raises(ValueError):
        OracleConfig("db.local", 1521, "ORCL", "reader", "").validate()

def test_invalid_port():
    with pytest.raises(ValueError):
        OracleConfig("db.local", 99999, "ORCL", "reader", "test").validate()

def test_invalid_host():
    with pytest.raises(ValueError):
        OracleConfig("db.local;DROP", 1521, "ORCL", "reader", "test").validate()

def test_valid_config():
    OracleConfig("db.local", 1521, "ORCL", "reader", "test").validate()
