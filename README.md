# daylily-cognito

`daylily-cognito` is both a reusable Python Cognito integration library and the `daycog` operational CLI.

The current repo workflow is built around:

- managing Cognito pools, app clients, users, groups, and Google federation with `daycog`
- wiring FastAPI bearer-token authentication into services
- running Cognito Hosted UI browser-session flows without storing raw OAuth tokens in the session
- verifying JWTs with Cognito JWKS-backed helpers
- sharing one flat YAML config file per environment

## Quick Start

From the repo root:

```bash
source ./activate
daycog --help
daycog status
pytest -q
```

`source ./activate` is the standard entrypoint for this repo. It prepares `.venv`, installs the package editable, exposes `daycog`, and points imports at the sibling `../cli-core-yo` checkout when present.

For application code outside this repo:

```bash
pip install "daylily-cognito[auth]"
```

## Configuration Model

The canonical config file is the one reported by:

```bash
daycog config path
```

By default that is:

```text
~/.config/daycog/config.yaml
```

You can override it for a single invocation with the root `--config PATH` option:

```bash
daycog --config ./staging.yaml status
daycog --config ./staging.yaml auth-config print --json
```

### Flat YAML shape

Required keys:

- `COGNITO_REGION`
- `COGNITO_USER_POOL_ID`
- `COGNITO_APP_CLIENT_ID`

Optional non-AWS keys:

- `COGNITO_CLIENT_NAME`
- `COGNITO_CALLBACK_URL`
- `COGNITO_LOGOUT_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `COGNITO_DOMAIN`

Optional AWS keys:

- `AWS_PROFILE`
- `AWS_REGION`

Example:

```yaml
COGNITO_REGION: us-west-2
COGNITO_USER_POOL_ID: us-west-2_example
COGNITO_APP_CLIENT_ID: example-client-id
COGNITO_CLIENT_NAME: web
COGNITO_CALLBACK_URL: https://app.example.com/auth/callback
COGNITO_LOGOUT_URL: https://app.example.com/logout
COGNITO_DOMAIN: example.auth.us-west-2.amazoncognito.com
GOOGLE_CLIENT_ID: your-google-client-id
GOOGLE_CLIENT_SECRET: your-google-client-secret
AWS_PROFILE: dev-aws
AWS_REGION: us-west-2
```

### Resolution rules

- Non-`AWS_*` values come from the config file only.
- AWS profile precedence is `--profile`, then file `AWS_PROFILE`, then env `AWS_PROFILE`.
- AWS region precedence is `--region`, then file `COGNITO_REGION`, then file `AWS_REGION`, then env `AWS_REGION`.
- The old named-context and namespaced env-override model is gone. Use flat YAML config files and `CognitoConfig.from_file(...)`.

## Python Library

### Core imports

Top-level imports are exposed through `daylily_cognito.__init__`, including:

- `CognitoConfig`
- `CognitoAuth`
- `create_auth_dependency`
- `CognitoWebSessionConfig`
- `configure_session_middleware`
- `start_cognito_login`
- `complete_cognito_callback`
- `load_session_principal`
- `SessionPrincipal`
- `build_authorization_url`
- `build_logout_url`
- `exchange_authorization_code`
- `refresh_with_refresh_token`
- `build_google_authorization_url`
- `exchange_google_code_for_tokens`
- `fetch_google_userinfo`
- `auto_create_cognito_user_from_google`
- `decode_jwt_unverified`
- `verify_jwt_claims`
- `verify_jwt_claims_unverified_signature`
- `JWKSCache`
- `DomainValidator`

### Bearer auth in FastAPI

```python
from fastapi import Depends, FastAPI

from daylily_cognito import CognitoAuth, CognitoConfig, create_auth_dependency

config = CognitoConfig.from_file("~/.config/daycog/config.yaml")
auth = CognitoAuth(
    region=config.region,
    user_pool_id=config.user_pool_id,
    app_client_id=config.app_client_id,
    profile=config.aws_profile,
)
get_current_user = create_auth_dependency(auth)

app = FastAPI()


@app.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "sub": user["sub"],
        "email": user.get("email"),
    }
```

Use `create_auth_dependency(auth, optional=True)` when anonymous requests should resolve to `None` instead of a `401`.

### Hosted UI browser sessions

`daylily_cognito.web_session` is the forward path for cookie-backed browser auth. The helpers exchange the authorization code during the callback, then persist a normalized `SessionPrincipal` in the session rather than raw OAuth tokens.

```python
from fastapi import FastAPI, Request

from daylily_cognito import (
    CognitoWebSessionConfig,
    SessionPrincipal,
    complete_cognito_callback,
    configure_session_middleware,
    load_session_principal,
    start_cognito_login,
)

app = FastAPI()
config = CognitoWebSessionConfig(
    domain="example.auth.us-west-2.amazoncognito.com",
    client_id="example-client-id",
    client_secret="example-client-secret",
    redirect_uri="https://app.example.com/auth/callback",
    logout_uri="https://app.example.com/logout",
    public_base_url="https://app.example.com",
    session_cookie_name="app_session",
    session_secret_key="replace-me",
)

configure_session_middleware(app, config)


@app.get("/auth/login")
async def login(request: Request):
    return start_cognito_login(request, config, next_path="/")


async def resolve_principal(tokens: dict, request: Request) -> SessionPrincipal:
    del request
    return SessionPrincipal(
        user_sub="sub-from-id-token",
        email="user@example.com",
        roles=["admin"],
        auth_mode="cognito",
    )


@app.get("/auth/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None):
    return await complete_cognito_callback(request, config, code, state, resolve_principal)


@app.get("/me")
async def me(request: Request):
    principal = load_session_principal(request)
    return principal.to_session_dict() if principal else {"user": None}
```

Current behavior:

- session data stores normalized identity fields, not raw OAuth tokens
- Hosted UI cookie security is derived from `public_base_url`
- local HTTP development requires `allow_insecure_http=True`

## `daycog` CLI

`daycog` is the primary operational interface for Cognito work in this repo.

### Built-in config commands

These come from `cli-core-yo`:

```bash
daycog config path
daycog config init
daycog config show
daycog config validate
```

Use `daycog config init` to create the canonical YAML file from the current template.

### Config-aware Cognito commands

Use the plugin config commands to inspect or sync the effective auth config file:

```bash
daycog auth-config print --json
daycog auth-config create --pool-name atlas-users --client-name web --profile dev-aws --region us-west-2
daycog auth-config update --pool-name atlas-users --client-name web --profile dev-aws --region us-west-2
```

- `auth-config create` writes a new flat config file from live AWS state.
- `auth-config update` refreshes an existing flat config file from live AWS state.
- `auth-config print` shows the currently selected file and resolved values.

### Inspect and bootstrap

```bash
daycog status
daycog list-pools --profile dev-aws --region us-west-2
daycog setup --name atlas-users --profile dev-aws --region us-west-2
```

`setup` provisions or reuses a pool and app client, writes the effective config file, and can attach a Hosted UI domain. It supports callback/logout URL overrides, domain prefix control, Google bootstrap, password policy flags, MFA mode, OAuth flow selection, app client secret generation, and `--print-exports` for AWS SDK env exports only.

### App client lifecycle

```bash
daycog list-apps --pool-name atlas-users --profile dev-aws --region us-west-2
daycog add-app \
  --pool-name atlas-users \
  --app-name web \
  --callback-url https://app.example.com/auth/callback \
  --logout-url https://app.example.com/logout \
  --profile dev-aws \
  --region us-west-2
daycog edit-app --pool-name atlas-users --app-name web --new-app-name web-v2 --profile dev-aws --region us-west-2
daycog remove-app --pool-name atlas-users --app-name web-v2 --profile dev-aws --region us-west-2 --force
daycog fix-auth-flows
```

`remove-app` no longer edits config files directly; it prints a reminder to run `daycog auth-config update` if the config should be repointed.

### Google federation

```bash
daycog add-google-idp \
  --pool-name atlas-users \
  --app-name web \
  --google-client-json ./google-client.json \
  --profile dev-aws \
  --region us-west-2

daycog setup-with-google \
  --name atlas-users \
  --client-name web \
  --google-client-json ./google-client.json \
  --profile dev-aws \
  --region us-west-2

daycog setup-google --client-id "$GOOGLE_CLIENT_ID" --client-secret "$GOOGLE_CLIENT_SECRET"
```

- `setup-with-google` provisions the pool/app if needed, configures Google IdP, and writes Google credentials into the effective config file.
- `add-google-idp` configures Google IdP on an existing pool/app.
- `setup-google` updates `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the effective config file and prints the redirect URI to register in Google Cloud Console.

### User and group operations

```bash
daycog list-users
daycog add-user alice@example.com --password "Secure1234"
daycog set-password --email alice@example.com --password "EvenMoreSecure1234"
daycog ensure-group atlas-admins --description "Atlas administrators"
daycog add-user-to-group --email alice@example.com --group atlas-admins
daycog set-user-attributes --email alice@example.com --attribute custom:tenant_id=tenant-1
daycog export --output ./cognito-users.json
```

These commands use the effective config file plus AWS resolution rules described above.

### Destructive operations

```bash
daycog delete-user --email alice@example.com --force
daycog delete-all-users --force
daycog delete-pool --pool-name atlas-users --profile dev-aws --region us-west-2 --force
daycog teardown --force
```

- `delete-pool` is the primary pool-deletion command.
- `teardown` remains available for compatibility, but it still operates through the current config-backed model.

## Repo Map

- `daylily_cognito/auth.py`: `CognitoAuth`, token verification, customer-user lifecycle, password flows, and Cognito admin helpers
- `daylily_cognito/fastapi.py`: shared FastAPI bearer dependency wiring
- `daylily_cognito/web_session.py`: Hosted UI login redirect, callback completion, session middleware, normalized principal persistence, and session invalidation
- `daylily_cognito/plugins/core.py`: `daycog` commands
- `daylily_cognito/config.py`: flat-file config model and `CognitoConfig`
- `daylily_cognito/cli.py` and `daylily_cognito/spec.py`: CLI entrypoint and `cli-core-yo` spec
- `daylily_cognito/oauth.py`: Cognito Hosted UI URL builders and token exchange
- `daylily_cognito/google.py`: Google OAuth helpers and Cognito auto-create flow
- `daylily_cognito/tokens.py`: JWT decode and claim verification helpers
- `daylily_cognito/jwks.py`: JWKS fetching, caching, and signature verification
- `daylily_cognito/domain_validator.py`: allow/block email-domain policy
- `daylily_cognito/_app_client_update.py`: safe app-client update request builders

## Development Notes

Recommended local loop:

```bash
source ./activate
daycog --help
pytest -q
```

Recommended habits in this repo:

- activate the repo environment before doing anything else
- use `daycog` instead of raw AWS Cognito mutations for operational flows
- keep docs and examples aligned with the current package surface and CLI output

Version metadata is derived with `setuptools-scm`.

## For AI Users

Treat this README as the current repo overview and command map. Treat [AGENTS.md](./AGENTS.md) and [AI_DIRECTIVE.md](./AI_DIRECTIVE.md) as repo-specific operating policy.

Key rules:

- always start from repo root with `source ./activate`
- use `daycog ...` as the primary interface for Cognito operations
- do not bypass `daycog` with direct `aws cognito-idp ...`, ad hoc boto3 scripts, or manual config-file edits for normal operational work
- prefer `daycog config path`, `daycog config init`, and `daycog auth-config print --json` for orientation
- keep Hosted UI behavior aligned with the current contract: exchange tokens during callback, persist normalized principal/session state, and avoid storing raw OAuth tokens in the session
