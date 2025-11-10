import os
from typing import Any, Dict

from google.cloud import firestore

from .config import get_logger
from ..schema.user_profile import GrestokUser

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID") or "grestok-app-dev"

logger = get_logger("grestok.firestore")
client = firestore.Client(project=PROJECT_ID)


def get_fs_user_profile(email: str) -> Dict[str, Any]:
    """
    Fetches a single user profile document from Firestore `/Users` using the email field.
    Returns a dict containing the GrestokUser schema (camelCase keys) with every field present; missing values are
    explicitly set to null so the LLM has a complete view of the shape.
    """
    normalized_email = (email or "").strip()
    if not normalized_email:
        raise ValueError("email is required")

    logger.info("Fetching Firestore user profile for email=%s", normalized_email)
    users_ref = client.collection("Users")
    query = users_ref.where("email", "==", normalized_email).limit(1)
    docs = list(query.stream())

    if not docs:
        logger.warning("No Firestore user profile found for email=%s", normalized_email)
        schema_payload = GrestokUser(email=normalized_email).model_dump(
            by_alias=True,
            exclude_none=False,
        )
        return {"found": False, "email": normalized_email, "doc_id": None, "profile": schema_payload}

    doc = docs[0]
    profile = doc.to_dict() or {}
    logger.info("Firestore user profile retrieved | doc_id=%s email=%s", doc.id, normalized_email)

    schema_payload = GrestokUser.model_validate(profile).model_dump(
        by_alias=True,
        exclude_none=False,
    )

    return {
        "found": True,
        "email": normalized_email,
        "doc_id": doc.id,
        "profile": schema_payload,
    }
