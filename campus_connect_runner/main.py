import asyncio
import json
import logging
import os
from functools import wraps
from typing import Optional

import firebase_admin
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth as firebase_auth, credentials
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from pydantic import BaseModel, Field

import sys

sys.path.append("../")
from campus_connect.agent import root_agent as campus_connect_agent  # noqa: E402

from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "campus_connect_agent_runner")
DEFAULT_SESSION_PREFIX = os.getenv("DEFAULT_SESSION_PREFIX", "session")
EMAIL_INJECTION_PREFIX = os.getenv(
    "EMAIL_INJECTION_PREFIX",
    "The authenticated user's email is",
)
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")

app = FastAPI(title="Grestok Agent Runner")

allowed_origins = [
    origin.strip()
    for origin in CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]

if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

# Setup module logging.
logger = logging.getLogger("campus_connect_agent")
logger.setLevel(logging.DEBUG)
logger.propagate = False
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

runner: Optional[Runner] = None
session_service: Optional[InMemorySessionService] = None
session_lock = asyncio.Lock()


class AuthenticatedUser(BaseModel):
    uid: str
    email: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's chat message")
    session_id: Optional[str] = Field(
        default=None,
        description="Optional client-managed session identifier",
    )


class ChatResponse(BaseModel):
    session_id: str
    response: str


def initialize_firebase_app() -> None:
    """Initializes the Firebase Admin SDK if it is not already initialized."""
    if firebase_admin._apps:  # type: ignore[attr-defined]
        return

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    cred = None

    if service_account_json:
        cred_dict = json.loads(service_account_json)
        cred = credentials.Certificate(cred_dict)
    else:
        credential_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credential_path and os.path.exists(credential_path):
            cred = credentials.Certificate(credential_path)

    if cred is None:
        firebase_admin.initialize_app()
    else:
        firebase_admin.initialize_app(cred)


def authorize(endpoint_function):
    """Decorator to authenticate Firebase JWT tokens and attach user info to the request."""

    @wraps(endpoint_function)
    async def wrapper(*args, **kwargs):
        # Ensure Firebase is ready even if startup hook has not run yet.
        initialize_firebase_app()

        request: Optional[Request] = kwargs.get("request")
        if request is None:
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
        if request is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request context missing",
            )

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing bearer token",
            )

        try:
            decoded_token = firebase_auth.verify_id_token(token)
        except firebase_auth.ExpiredIdTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            ) from exc
        except firebase_auth.InvalidIdTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        except firebase_auth.RevokedIdTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Revoked token",
            ) from exc
        except Exception as exc:  # Catch-all for auth library errors
            logger.exception("Failed to verify Firebase token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to verify token",
            ) from exc

        uid = decoded_token.get("uid")
        email = decoded_token.get("email")

        if not uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token missing uid claim",
            )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token missing email claim",
            )

        request.state.user = AuthenticatedUser(uid=uid, email=email)
        return await endpoint_function(*args, **kwargs)

    return wrapper


async def ensure_runner_ready() -> None:
    """Initializes the runner and session service if they are not ready yet."""
    global runner, session_service
    if runner is not None and session_service is not None:
        return

    session_service = InMemorySessionService()
    runner = Runner(
        agent=campus_connect_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    logger.info("Runner initialized for app '%s'", APP_NAME)


async def ensure_session(user_id: str, session_id: str) -> None:
    """Creates a session for the user if it does not already exist."""
    if session_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service unavailable",
        )

    async with session_lock:
        try:
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            logger.debug(
                "Session created for user '%s' with session_id '%s'",
                user_id,
                session_id,
            )
        except Exception as exc:  # best-effort idempotent create
            message = str(exc).lower()
            if "already exists" in message or "conflict" in message:
                logger.debug(
                    "Session already exists for user '%s' and session '%s'",
                    user_id,
                    session_id,
                )
            else:
                logger.exception("Unable to create session for user '%s'", user_id)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to initialize session",
                ) from exc


def pretty_print_event(event) -> None:
    logger.debug("Event author=%s final=%s", event.author, event.is_final_response())
    if not event.content or not event.content.parts:
        return
    for part in event.content.parts:
        if part.text:
            logger.debug("  ==> text: %s", part.text)
        elif part.function_call:
            func_call = part.function_call
            logger.debug(
                "  ==> func_call: %s args=%s", func_call.name, func_call.args
            )
        elif part.function_response:
            func_response = part.function_response
            logger.debug(
                "  ==> func_response: %s response=%s",
                func_response.name,
                func_response.response,
            )


async def invoke_agent(
    user: AuthenticatedUser, session_id: str, message: str
) -> str:
    if runner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Runner not initialized",
        )

    await ensure_session(user_id=user.uid, session_id=session_id)

    content = Content(
        role="user",
        parts=[
            Part(
                text=f"{message}\n\n{EMAIL_INJECTION_PREFIX} {user.email}",
            )
        ],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id=user.uid,
        session_id=session_id,
        new_message=content,
    ):
        pretty_print_event(event)

        if event.is_final_response():
            if event.content and event.content.parts:
                response_text = "".join(
                    part.text or "" for part in event.content.parts
                ).strip()
            elif event.actions and event.actions.escalate:
                response_text = (
                    f"Agent escalated: {event.error_message or 'No specific message.'}"
                )
            break

    if not response_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent returned an empty response",
        )

    return response_text


@app.on_event("startup")
async def on_startup() -> None:
    initialize_firebase_app()
    await ensure_runner_ready()
    logger.info("Grestok Agent Runner ready")


@app.post(
    "/grestok-agent/",
    response_model=ChatResponse,
    summary="Send a chat message to the Grestok root agent",
)
@authorize
async def grestok_agent_endpoint(payload: ChatRequest, request: Request) -> ChatResponse:
    await ensure_runner_ready()

    auth_user: Optional[AuthenticatedUser] = getattr(request.state, "user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )

    session_id = payload.session_id or f"{DEFAULT_SESSION_PREFIX}-{auth_user.uid}"
    agent_response = await invoke_agent(
        user=auth_user,
        session_id=session_id,
        message=payload.message,
    )
    return ChatResponse(session_id=session_id, response=agent_response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "campus_connect_runner.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
