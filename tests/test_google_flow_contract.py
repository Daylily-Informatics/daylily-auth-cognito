"""Offline Google-flow cases; execution requires separate user authorization."""
import time
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from daylily_auth_cognito.browser.oauth import build_authorization_url
from daylily_auth_cognito.runtime.verifier import CognitoTokenVerifier


def test_provider_selection_keeps_client_callback_and_state():
    url = build_authorization_url(
        domain="auth.example.test", client_id="google-client",
        redirect_uri="https://login.example.test/auth/google/callback",
        state="flow-state", identity_provider="Google",
    )
    params = parse_qs(urlparse(url).query)
    assert params["identity_provider"] == ["Google"]
    assert params["client_id"] == ["google-client"]
    assert params["state"] == ["flow-state"]
    assert params["redirect_uri"] == ["https://login.example.test/auth/google/callback"]


@pytest.mark.parametrize("override", [
    {"aud": "native-client"}, {"aud": None}, {"token_use": "access"},
    {"sub": None}, {"exp": time.time() - 60},
])
def test_id_token_requires_exact_client_and_id_claims(monkeypatch, override):
    claims = {"aud": "google-client", "token_use": "id", "sub": "subject", "exp": time.time() + 60}
    claims.update(override)
    verify = Mock(return_value=claims)
    monkeypatch.setattr("daylily_auth_cognito.runtime.verifier.verify_token_with_jwks", verify)
    verifier = CognitoTokenVerifier("us-west-2", "pool", "google-client", cache=Mock())
    with pytest.raises(HTTPException) as failure:
        verifier.verify_id_token("token")
    assert failure.value.status_code == 401
    assert verify.call_args.kwargs["audience"] == "google-client"
