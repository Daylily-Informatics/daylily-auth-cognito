# daylily-cognito

`daylily-cognito` is both a reusable Python Cognito integration library and the `daycog` operational CLI.

The repo is built around the current Daylily workflow for:

- managing Cognito pools, app clients, users, groups, and Google federation with `daycog`
- wiring FastAPI bearer-token authentication into services
- running Cognito Hosted UI browser-session flows without storing raw OAuth tokens in the session
- verifying JWTs with Cognito JWKS-backed helpers
- sharing configuration through a canonical Daycog context store

## What You Get

### `daycog` CLI

- Pool and app bootstrap for new Cognito environments
- Context-aware config inspection and sync via `daycog auth-config`
- App client lifecycle and Google IdP setup
- User, password, group, export, and teardown operations

### Python library

- `CognitoAuth` for token verification and Cognito admin actions
- `create_auth_dependency()` for FastAPI bearer auth
- Hosted UI browser-session helpers in `daylily_cognito.web_session`
- OAuth, Google, JWKS, JWT, and domain-validation helpers for app-specific flows

## Quick Start

From the repo root:

```bash
source ./activate
daycog --help
daycog status
pytest -q
```

`source ./activate` is the standard entrypoint for this repo. It creates or repairs `.venv`, installs the package editable, and makes `daycog` available in the current shell.

Auth and signature-verification features require the `auth` extra, which is already handled by `./activate` inside this repo. For external consumers, install:

```bash
pip install "daylily-cognito[auth]"
```

## Configuration Model

The canonical Daycog config store is:

```text
~/.config/daycog/config.yaml
```

The store tracks named contexts plus one active context. The intended workflow is:

1. Create or refresh contexts with `daycog auth-config create`, `daycog auth-config update`, or `daycog auth-config create-all`
2. Inspect the resolved values with `daycog auth-config print` or `daycog auth-config print --json`
3. Let application code load the desired named context with `CognitoConfig.from_env(...)`

At the root CLI, the Cognito-specific context workflow lives under `daycog auth-config`.

Example inspection flow:

```bash
daycog auth-config print --json
daycog auth-config create --pool-name atlas-users --client-name web --profile dev-aws --region us-west-2
daycog auth-config create-all --pool-name atlas-users --default-client web --profile dev-aws --region us-west-2
```

`CognitoConfig.from_env("PROD")` uses the named Daycog context as its base and lets matching namespaced environment variables override it when present:

```bash
export DAYCOG_PROD_REGION=us-west-2
export DAYCOG_PROD_USER_POOL_ID=us-west-2_example
export DAYCOG_PROD_APP_CLIENT_ID=exampleclientid
export DAYCOG_PROD_AWS_PROFILE=prod-aws
```

That keeps local app wiring explicit without requiring direct edits to the config store.

## Python Library

### Install And Import Surface

For application code outside this repo:

```bash
pip install "daylily-cognito[auth]"
```

Current top-level imports are exposed through `daylily_cognito.__init__`, including:

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

### Bearer Auth In FastAPI

```python
from fastapi import Depends, FastAPI

from daylily_cognito import CognitoAuth, CognitoConfig, create_auth_dependency

config = CognitoConfig.from_env("PROD")
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

Use `create_auth_dependency(auth, optional=True)` when anonymous requests should be allowed and missing credentials should resolve to `None` instead of a `401`.

### Hosted UI Browser Sessions

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
    # Replace this with your own token decoding / user lookup.
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

Important current behavior:

- session data stores normalized identity fields, not raw `access_token`, `id_token`, or `refresh_token`
- Hosted UI cookie security is derived from `public_base_url`
- local HTTP development requires `allow_insecure_http=True`

### Helper Reference

| Area | Current helpers |
| --- | --- |
| OAuth helpers | `build_authorization_url`, `build_logout_url`, `exchange_authorization_code`, `refresh_with_refresh_token` |
| Google OAuth | `build_google_authorization_url`, `exchange_google_code_for_tokens`, `fetch_google_userinfo`, `auto_create_cognito_user_from_google`, `generate_state_token` |
| JWT/JWKS | `decode_jwt_unverified`, `verify_jwt_claims_unverified_signature`, `verify_jwt_claims`, `JWKSCache` |
| Domain policy | `DomainValidator` for allow/block email-domain validation |

`DomainValidator` is designed to plug into `CognitoAuth(settings=...)` when signup, password, or Google-driven user creation must enforce allowed or blocked domains.

## `daycog` CLI

`daycog` is the primary operational interface for Cognito work in this repo.

### Inspect And Bootstrap

Use these commands to understand or create the current environment:

```bash
daycog status
daycog list-pools --profile dev-aws --region us-west-2
daycog setup --name atlas-users --profile dev-aws --region us-west-2
```

`setup` provisions or reuses a pool and app client, writes Daycog contexts, and can attach a Hosted UI domain. It also supports callback/logout URL overrides, domain prefix control, Google bootstrap, password policy flags, MFA mode, OAuth flow selection, and app client secret generation.

### Config Persistence And Sync

These commands are the forward path for inspecting and materializing current Daycog contexts:

```bash
daycog auth-config print --json
daycog auth-config create --pool-name atlas-users --client-name web --profile dev-aws --region us-west-2
daycog auth-config update --pool-name atlas-users --client-name web --profile dev-aws --region us-west-2
daycog auth-config create-all --pool-name atlas-users --default-client web --profile dev-aws --region us-west-2
```

Use `auth-config print` when you want a resolved context view, and `auth-config create` / `auth-config update` when you want the local Daycog store to reflect AWS truth for a specific pool or client.

### App Client Lifecycle

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

`fix-auth-flows` is the targeted repair path when an app client exists but is missing required auth flows such as `ALLOW_ADMIN_USER_PASSWORD_AUTH`.

### Google Federation

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

Use `setup-with-google` when you want first-time pool/app provisioning and Google IdP configuration in one command. Use `add-google-idp` when the pool and app already exist.

### User And Group Operations

```bash
daycog list-users
daycog add-user alice@example.com --password "Secure1234"
daycog set-password --email alice@example.com --password "EvenMoreSecure1234"
daycog ensure-group atlas-admins --description "Atlas administrators"
daycog add-user-to-group --email alice@example.com --group atlas-admins
daycog set-user-attributes --email alice@example.com --attribute custom:tenant_id=tenant-1
daycog export --output ./cognito-users.json
```

These commands operate against the currently resolved pool context or explicit AWS/profile inputs, depending on the command.

### Destructive And Admin Operations

```bash
daycog delete-user --email alice@example.com --force
daycog delete-all-users --force
daycog delete-pool --pool-name atlas-users --profile dev-aws --region us-west-2 --force
```

Treat destructive commands as explicit high-risk operations. `delete-pool` is the current direct pool-deletion command.

### CLI Resolution Notes

For commands that talk to AWS directly:

1. `--profile` and `--region` take precedence
2. `AWS_PROFILE` and `AWS_REGION` are used when flags are omitted
3. the command errors if required context is still missing

That keeps operational commands explicit while still supporting shell-driven workflows.

## Architecture Map

The repo is intentionally split by concern rather than by framework layer.

### Core Auth

- `daylily_cognito/auth.py`: `CognitoAuth` token verification, customer-user lifecycle, password flows, app-client creation/update, and Cognito admin helpers
- `daylily_cognito/fastapi.py`: shared FastAPI bearer dependency wiring

### Browser Session Flow

- `daylily_cognito/web_session.py`: Hosted UI login redirect, callback completion, session middleware, normalized principal persistence, and session invalidation behavior

### CLI And Config

- `daylily_cognito/plugins/core.py`: `daycog` root command surface, config workflows, app lifecycle, Google IdP setup, and user/group operations
- `daylily_cognito/config.py`: canonical Daycog config store and `CognitoConfig`
- `daylily_cognito/cli.py` and `daylily_cognito/spec.py`: CLI entrypoint and plugin registration

### Supporting Modules

- `daylily_cognito/oauth.py`: Cognito Hosted UI URL builders and token exchange
- `daylily_cognito/google.py`: Google OAuth URL/token/userinfo helpers and Cognito auto-create flow
- `daylily_cognito/tokens.py`: JWT decode and claim verification helpers
- `daylily_cognito/jwks.py`: JWKS fetching, caching, and signature verification
- `daylily_cognito/domain_validator.py`: allow/block email-domain policy
- `daylily_cognito/_app_client_update.py`: safe app-client update request builders

## Developer Workflow

The normal local loop is short:

```bash
source ./activate
daycog --help
pytest -q
```

Recommended development habits in this repo:

- activate the repo environment before doing anything else
- use `daycog` instead of raw AWS Cognito mutations when working on operational flows
- keep docs and examples aligned with the current package surface and CLI output

Version metadata is derived with `setuptools-scm`, so release/version behavior follows git tags rather than a hard-coded version string in the package.

## For AI Users

Treat this README as the repo overview and the current code map. Treat [AGENTS.md](./AGENTS.md) and [AI_DIRECTIVE.md](./AI_DIRECTIVE.md) as operational policy.

### Required Operating Rules

- always start from repo root with `source ./activate`
- use `daycog ...` as the primary interface for Cognito operations
- do not bypass `daycog` with direct `aws cognito-idp ...`, ad hoc boto3 scripts, or direct config-file edits for normal operational tasks
- if `daycog` is missing a needed path, diagnose first and ask before circumventing it
- prefer `daycog auth-config print --json` and related config commands for repo-aware inspection
- treat pool deletion, mass-user deletion, and similar destructive operations as explicit high-risk actions

### Best Entry Points

- `daycog status`
- `daycog --help`
- `daycog auth-config print --json`
- public imports from `daylily_cognito.__init__`

### AI-Specific Notes

- The current forward path is Daycog contexts plus `DAYCOG_<NAME>_*` overrides.
- The library and the CLI are equally important in this repo; do not collapse the README or future docs into only one of those stories.
- For Hosted UI flows, keep the current contract: exchange tokens during callback, persist normalized principal/session state, and avoid storing raw OAuth tokens in the session.
- For JWT verification, prefer JWKS-backed validation when the auth extra is available.
