"""OAuth2 authentication routes.

YouTube upload requires user-level OAuth2.  Use these endpoints once to obtain
a refresh token, then save it as YOUTUBE_OAUTH_TOKEN_JSON in your .env file.

Setup flow
----------
1. Visit  GET /auth/youtube          → redirected to Google consent screen
2. Approve access in the browser
3. Google redirects to GET /auth/youtube/callback?code=...
4. The response body contains the token JSON — copy it into your .env:
       YOUTUBE_OAUTH_TOKEN_JSON=<paste here>
5. Restart the backend server.  Step 8 will now use the saved token.
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from app.utils.youtube_api import get_oauth_auth_url, exchange_oauth_code

router = APIRouter()

# The redirect URI must exactly match one of the "Authorized redirect URIs"
# configured in your Google Cloud Console OAuth2 client.
_REDIRECT_URI_ENV = "YOUTUBE_OAUTH_REDIRECT_URI"
_DEFAULT_REDIRECT_URI = "http://localhost:8000/auth/youtube/callback"


def _redirect_uri() -> str:
    return os.getenv(_REDIRECT_URI_ENV, _DEFAULT_REDIRECT_URI)


@router.get("/youtube", summary="Start YouTube OAuth2 flow")
async def youtube_auth_start():
    """Redirect the browser to the Google OAuth2 consent screen.

    Requires YOUTUBE_CLIENT_SECRETS_JSON to be set in the environment.
    """
    try:
        auth_url = get_oauth_auth_url(redirect_uri=_redirect_uri())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return RedirectResponse(url=auth_url)


@router.get("/youtube/callback", summary="Handle YouTube OAuth2 callback")
async def youtube_auth_callback(code: str = "", error: str = ""):
    """Exchange the authorization code for an OAuth2 token.

    On success, returns JSON containing the token.
    Copy the `token_json` value into your .env as YOUTUBE_OAUTH_TOKEN_JSON,
    then restart the server.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth2 error from Google: {error}",
        )
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing 'code' parameter in callback URL",
        )

    try:
        token_json = exchange_oauth_code(code=code, redirect_uri=_redirect_uri())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {exc}")

    return JSONResponse(
        content={
            "success": True,
            "message": (
                "OAuth2 token obtained. "
                "Save the value of 'token_json' as YOUTUBE_OAUTH_TOKEN_JSON in your .env file, "
                "then restart the backend server."
            ),
            "token_json": token_json,
        }
    )
