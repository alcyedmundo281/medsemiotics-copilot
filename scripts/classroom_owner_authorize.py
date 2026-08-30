"""One-time consent flow that mints the owner-authorized caller credential (Loop 0.7E).

Usage:
    python scripts/classroom_owner_authorize.py

Run this once, signed in as the dedicated Workspace account that owns the Apps Script deployment.
It opens a browser, asks that account to authorize the operator application, and prints the
resulting refresh token so you can store it in your secret manager.

Required environment, never in Git:

    MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_ID       OAuth client id of the operator application
    MEDSEMIOTICS_CLASSROOM_OAUTH_CLIENT_SECRET   OAuth client secret
    MEDSEMIOTICS_CLASSROOM_CALLER_SCOPES         Optional comma-separated caller scopes

The printed refresh token is a credential. Store it in the secret manager immediately, never paste
it into a ticket, chat, or file inside this repository, and revoke it from the account's security
settings if it is ever exposed.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from medsemiotics.integrations.google_classroom.owner_authorized_caller import (
    CALLER_SCOPES_SECRET,
    CLIENT_ID_SECRET,
    CLIENT_SECRET_SECRET,
    GOOGLE_TOKEN_URI,
    REFRESH_TOKEN_SECRET,
    parse_caller_scopes,
)

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"


def main() -> None:
    """Run the consent flow and print the credential to store."""
    print("=== MedSemiotics owner-authorized caller (Loop 0.7E) ===")

    client_id = os.environ.get(CLIENT_ID_SECRET, "").strip()
    client_secret = os.environ.get(CLIENT_SECRET_SECRET, "").strip()
    if not client_id or not client_secret:
        print(
            f"[FAIL] Set {CLIENT_ID_SECRET} and {CLIENT_SECRET_SECRET} before running.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    scopes = parse_caller_scopes(os.environ.get(CALLER_SCOPES_SECRET))
    print(f"  scopes: {', '.join(scopes)}")
    print("  Sign in as the Workspace account that OWNS the Apps Script deployment.\n")

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": AUTH_URI,
                "token_uri": GOOGLE_TOKEN_URI,
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=scopes,
    )

    try:
        credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    except Exception as err:
        print(f"[FAIL] Consent flow did not complete ({type(err).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None

    refresh_token = getattr(credentials, "refresh_token", None)
    if not refresh_token:
        print(
            "[FAIL] Google returned no refresh token. Revoke the app's access in the account's "
            "security settings and run again so consent is granted afresh.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    account = getattr(credentials, "id_token", None)
    print("[ OK ] Consent granted. Store these in your secret manager:\n")
    print(f"  {CLIENT_ID_SECRET}={client_id}")
    print(f"  {CLIENT_SECRET_SECRET}=<the client secret you already hold>")
    print(f"  {REFRESH_TOKEN_SECRET}={refresh_token}")
    if account:
        print("\n  (an id token was also issued and is deliberately not printed)")
    print(
        "\nThis refresh token is a credential. Store it now, do not paste it anywhere else, and "
        "revoke it from the account's security settings if it is ever exposed."
    )


if __name__ == "__main__":
    main()
