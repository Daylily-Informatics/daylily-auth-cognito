# daylily-auth-cognito

`daylily-auth-cognito` is the standalone Cognito auth repo for Daylily. It publishes the `daylily_auth_cognito` Python package and the `daycog` CLI.

The `2.0` line is a breaking refactor with hard boundaries:
- `runtime/`: JWT verification and FastAPI bearer auth
- `browser/`: Hosted UI session auth with token-free session storage
- `admin/`: Cognito pool, app-client, user, password, and federation mutations
- `cli/`: `daycog` wiring only
- `policy/`: email-domain policy helpers

## Install

```bash
pip install daylily-auth-cognito
```

For development in this repo:

```bash
source ./activate
pytest -q
```

`activate` installs the editable repo and the published `cli-core-yo==2.1.1` dependency.

## Public API

The top-level package is intentionally small:

```python
from daylily_auth_cognito import (
    CognitoTokenVerifier,
    CognitoWebSessionConfig,
    JWKSCache,
    SessionPrincipal,
    clear_session_principal,
    complete_cognito_callback,
    configure_session_middleware,
    create_auth_dependency,
    load_session_principal,
    start_cognito_login,
    store_session_principal,
    verify_m2m_token_with_jwks,
)
```

Use submodules directly for admin and CLI-specific work. CLI config handling lives under `daylily_auth_cognito.cli.config` and is CLI-only.

## Runtime Example

```python
from daylily_auth_cognito import CognitoTokenVerifier, create_auth_dependency

verifier = CognitoTokenVerifier(
    region="us-west-2",
    user_pool_id="us-west-2_example",
    app_client_id="client-123",
)

current_principal = create_auth_dependency(verifier)
```

## Browser Session Example

```python
from daylily_auth_cognito import CognitoWebSessionConfig, configure_session_middleware

config = CognitoWebSessionConfig(
    domain="auth.example.test",
    client_id="client-123",
    redirect_uri="https://app.example.test/auth/callback",
    logout_uri="https://app.example.test/logout",
    session_secret_key="replace-me",
    session_cookie_name="app_session",
    public_base_url="https://app.example.test",
    server_instance_id="server-1",
)

configure_session_middleware(app, config)
```

Hosted UI callbacks exchange the authorization code asynchronously in the web path and only persist normalized principal data in the session. Raw OAuth tokens are rejected.

Set `CognitoWebSessionConfig.identity_provider="Google"` to select Google explicitly at the Cognito authorize endpoint. The app client must separately restrict its supported providers and password authentication flows. A callback principal resolver can use `CognitoTokenVerifier.verify_id_token(token)` to require the pool signature/issuer, exact client audience, ID token use, subject and expiry. This method always verifies the signature.

## CLI

Activate the repo, then use `daycog`:

```bash
source ./activate
daycog --help
daycog status
daycog auth-config print
daycog setup --help
```

CLI config remains at `~/.config/daycog/config.yaml`.

`daycog add-app` and `daycog edit-app` accept `--explicit-auth-flows` as a nonempty comma-separated list. A Google-only OAuth client uses `--idp Google --oauth-flows code --generate-secret --explicit-auth-flows ALLOW_REFRESH_TOKEN_AUTH`; restricting displayed providers alone does not disable SDK password authentication. Existing defaults remain unchanged when the explicit-auth-flows option is omitted.

Use `--read-attributes email,email_verified` for a pool whose Google mapping exposes those standard fields. This selects readable attributes explicitly and avoids the admin helper's historical custom-attribute default, which is invalid for pools without that attribute.

The flat-file config model is implemented in `daylily_auth_cognito.cli.config`; its internal config helper is not part of the runtime surface.

## Layout

```text
daylily_auth_cognito/
  runtime/
  browser/
  admin/
  cli/
  policy/
```

## Docs

- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [Migrating to 2.0.0](MIGRATING_TO_2_0_0.md)
- [2.0.0 Changelog](CHANGELOG_2_0_0.md)
 
 
 
