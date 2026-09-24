import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.adapters.postgres import PostgresRepository


def test_workspace_provisioning_is_idempotent_across_concurrent_first_requests() -> None:
    source = inspect.getsource(PostgresRepository._transaction)

    assert "ON CONFLICT DO NOTHING" in source
    assert "ON CONFLICT (id) DO NOTHING" not in source
    assert 'f"workspace-{organization_uuid}"' in source
    assert "[:18]" not in source
