import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from ..services.google_token_encryption import encrypt_refresh_token
from .plan import get_db_session

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from ..services.google_calendar_service import (
    GOOGLE_CALENDAR_SCOPES,
    build_google_calendar_service,
)

from ..db.repositories import (
    get_google_calendar_connection,
    save_google_calendar_connection,
    set_google_calendar_target,
)
from ..schemas.google_calendar import (
    GoogleCalendarResponse,
    SetTargetCalendarRequest,
)

# Connect a Google Calendar account through OAuth.
router = APIRouter(prefix="/auth/google", tags=["Google Calendar"])

REDIRECT_URI = "http://localhost:8000/auth/google/callback"


# Create the OAuth flow using the web client from Google Cloud.
def create_oauth_flow(
    state: str | None = None,
    code_verifier: str | None = None,
) -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_CALENDAR_SCOPES,
        state=state,
        code_verifier=code_verifier,
    )
    flow.redirect_uri = REDIRECT_URI
    return flow


# Send the user to Google to approve calendar access.
@router.get("/connect")
def connect_google_calendar() -> RedirectResponse:
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    response = RedirectResponse(authorization_url)
    response.set_cookie(
        "google_oauth_state",
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=REDIRECT_URI.startswith("https://"),
    )
    response.set_cookie(
        "google_oauth_code_verifier",
        flow.code_verifier or "",
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=REDIRECT_URI.startswith("https://"),
    )
    return response


# Check Google's callback and save the encrypted refresh token.
@router.get("/callback")
def google_calendar_callback(
    request: Request,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    if request.query_params.get("error"):
        raise HTTPException(
            status_code=400,
            detail="Google Calendar access was not granted.",
        )

    returned_state = request.query_params.get("state", "")
    saved_state = request.cookies.get("google_oauth_state", "")
    saved_verifier = request.cookies.get("google_oauth_code_verifier", "")

    if not saved_state or not secrets.compare_digest(returned_state, saved_state):
        raise HTTPException(
            status_code=400,
            detail="OAuth state check failed. Please try connecting again.",
        )

    if not saved_verifier:
        raise HTTPException(
            status_code=400,
            detail="OAuth verifier is missing. Please try connecting again.",
        )

    authorization_code = request.query_params.get("code")
    if not authorization_code:
        raise HTTPException(
            status_code=400,
            detail="Google did not return an authorization code.",
        )

    flow = create_oauth_flow(
        state=saved_state,
        code_verifier=saved_verifier,
    )
    flow.fetch_token(code=authorization_code)

    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Please try connecting again.",
        )

    encrypted_token = encrypt_refresh_token(refresh_token)

    with session.begin():
        save_google_calendar_connection(session, encrypted_token)

    response = JSONResponse({"status": "Google Calendar connected."})
    response.delete_cookie("google_oauth_state")
    response.delete_cookie("google_oauth_code_verifier")
    return response

# Return calendar names and IDs from the connected Google account.
@router.get(
    "/calendars",
    response_model=list[GoogleCalendarResponse],
)
def read_google_calendars(
    session: Session = Depends(get_db_session),
) -> list[GoogleCalendarResponse]:
    connection = get_google_calendar_connection(session)
    if connection is None:
        raise HTTPException(
            status_code=409,
            detail="Connect Google Calendar before listing calendars.",
        )

    calendar_api = build_google_calendar_service(
        connection.refresh_token_encrypted,
        GOOGLE_CALENDAR_SCOPES,
    )

    calendars: list[GoogleCalendarResponse] = []
    page_token = None

    try:
        while True:
            request_parameters = {
                "maxResults": 250,
                "fields": "nextPageToken,items(id,summary,primary,accessRole)",
            }
            if page_token is not None:
                request_parameters["pageToken"] = page_token

            result = (
                calendar_api.calendarList()
                .list(**request_parameters)
                .execute()
            )

            for item in result.get("items", []):
                access_role = item.get("accessRole", "")
                calendars.append(
                    GoogleCalendarResponse(
                        calendar_id=item["id"],
                        name=item.get("summary") or "(untitled calendar)",
                        is_primary=item.get("primary", False),
                        access_role=access_role,
                        can_be_target=access_role == "owner",
                    )
                )

            page_token = result.get("nextPageToken")
            if page_token is None:
                break

    except RefreshError as error:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar access expired. Connect it again.",
        ) from error
    except HttpError as error:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve Google calendars.",
        ) from error

    return calendars


# Save a calendar as the planner's workout destination.
@router.put(
    "/target-calendar",
    response_model=GoogleCalendarResponse,
)
def select_target_calendar(
    request: SetTargetCalendarRequest,
    session: Session = Depends(get_db_session),
) -> GoogleCalendarResponse:
    calendars = read_google_calendars(session)
    selected_calendar = next(
        (
            calendar
            for calendar in calendars
            if calendar.calendar_id == request.calendar_id
        ),
        None,
    )

    if selected_calendar is None:
        raise HTTPException(
            status_code=404,
            detail="That calendar is not available in your Google account.",
        )

    if not selected_calendar.can_be_target:
        raise HTTPException(
            status_code=403,
            detail="Choose a calendar you own for workout events.",
        )

    connection = set_google_calendar_target(
        session,
        request.calendar_id,
    )
    if connection is None:
        raise HTTPException(
            status_code=409,
            detail="Connect Google Calendar before choosing a target.",
        )

    session.commit()
    return selected_calendar