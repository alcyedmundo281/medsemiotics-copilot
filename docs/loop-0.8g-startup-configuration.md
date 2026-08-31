# Loop 0.8G: configure before the first request

The first deployed request answered `503 This backend has no access token configured` — with the
token correctly mounted from Secret Manager. The container had the secret; the application never
read it.

## What went wrong

Access control reads the configured token from application state. That state was only wired
lazily, from `get_services()`, which runs **inside an endpoint body** — and a FastAPI dependency
runs *before* the body it guards. On a cold container the guard therefore ran against unconfigured
state, reported the backend as unconfigured, and returned `503` before any endpoint could wire it.

Every test passed because every test called `configure()` explicitly first. The one path nobody
exercised was the one production always takes: a process that starts and receives a request.

## The fix

- A **lifespan hook** configures the application before it serves anything, which is the path
  uvicorn always runs.
- `ensure_configured()` is idempotent and is also called from the access-control dependency, so a
  server that starts without a lifespan — another ASGI runner, an embedded mount — still serves a
  configured application instead of misreporting itself.
- A `configured` flag distinguishes *not yet wired* from *wired and holding no token*. That
  distinction is the point: a backend with no token configured must still answer `503`, and it
  does.

## What the tests now cover

Three cases, written from how the failure actually reached us:

- a cold application served through the lifespan;
- a cold application with **no** lifespan, authorized by the dependency alone;
- a cold application whose environment holds no token, which must still refuse with `503`.

Each fails against the previous code and passes against this one.

## Exit criteria

- configuration performed before the first request, by a path production always takes;
- an idempotent fallback so a runner that skips the lifespan behaves identically;
- the unconfigured-backend refusal preserved and still tested;
- full pytest, Ruff, and strict mypy quality gates.
