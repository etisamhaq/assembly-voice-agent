import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from app.compliance import ComplianceEngine, LLMJudge, RuleEngine
from app.config import settings


@pytest.fixture(scope="session")
def rules() -> RuleEngine:
    return RuleEngine.from_path(settings.rules_path)


@pytest.fixture
def engine(rules) -> ComplianceEngine:
    # No API key -> Tier 2 disabled, so tests exercise the deterministic path
    # and never touch the network.
    return ComplianceEngine(rules, LLMJudge())
