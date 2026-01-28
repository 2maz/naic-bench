from pathlib import Path
import pytest

@pytest.fixture
def testdir() -> Path:
    return Path(__file__).parent
