from pathlib import Path
import pytest
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "trading_rules.yaml"


@pytest.fixture
def config() -> dict:
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)
