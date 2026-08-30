"""Query the read-only MedSemiotics backend from a shell or a conversational surface.

Usage:
    python scripts/backend_query.py /v1/courses/NEURO/next-topic

Required environment, never in Git:

    MEDSEMIOTICS_API_BASE_URL   Base URL of the deployed backend
    MEDSEMIOTICS_API_TOKEN      The surface's backend token, or a mounted secret directory

The token is read from the secret store and never printed. This script issues GET requests only.
"""

import json
import os
import sys

from medsemiotics.api.client import BASE_URL_ENV_VAR, BackendClient, BackendClientError
from medsemiotics.api.settings import API_TOKEN_SECRET
from medsemiotics.integrations.secrets import build_secret_source


def main() -> None:
    """Fetch one contract and print its JSON payload."""
    if len(sys.argv) != 2:
        print("[FAIL] Usage: python scripts/backend_query.py <path>", file=sys.stderr)
        raise SystemExit(2)

    token = build_secret_source(os.environ).read(API_TOKEN_SECRET)
    try:
        client = BackendClient(
            base_url=os.environ.get(BASE_URL_ENV_VAR, ""),
            token=token or "",
        )
        payload = client.get(sys.argv[1])
    except BackendClientError as err:
        print(f"[FAIL] {err}", file=sys.stderr)
        raise SystemExit(1) from None

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
