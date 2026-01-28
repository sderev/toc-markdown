import pytest
from click.testing import CliRunner


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Provides a reusable Click CLI runner."""
    return CliRunner()
