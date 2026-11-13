"""Prevent unintended real Oracle access in every automated backend test."""
from unittest.mock import Mock
import oracledb
import pytest


@pytest.fixture(autouse=True)
def prohibit_real_oracle(monkeypatch):
    monkeypatch.setattr(oracledb, 'connect', Mock(side_effect=AssertionError('Real Oracle access forbidden in tests')))
