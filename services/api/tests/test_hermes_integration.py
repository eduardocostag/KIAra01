import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.http.errors import ApiError
from kiara_api.integrations import _validate_credentials


def test_hermes_instance_requires_public_https_and_unique_id():
    _validate_credentials("hermes", {"endpoint_url": "https://hermes-client.example.com", "api_key": "secret", "instance_id": "client_001"})


@pytest.mark.parametrize("endpoint", [
    "http://hermes.example.com", "https://localhost", "https://127.0.0.1",
    "https://10.0.0.1", "https://hermes.example.com/v1/responses",
    "https://user:pass@hermes.example.com", "https://hermes.example.com?x=1",
])
def test_hermes_instance_rejects_unsafe_endpoints(endpoint):
    with pytest.raises(ApiError):
        _validate_credentials("hermes", {"endpoint_url": endpoint, "api_key": "secret", "instance_id": "client_001"})
