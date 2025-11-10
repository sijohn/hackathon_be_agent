import os
from typing import Any, Dict, List

from google.cloud import firestore

from .config import get_logger
from ..schema.user_profile import GrestokUser

PROJECT_ID = (
    os.environ.get("GOOGLE_CLOUD_PROJECT")
    or os.environ.get("PROJECT_ID")
    or "grestok-app-dev"
)

logger = get_logger("grestok.resume_profile")
client = firestore.Client(project=PROJECT_ID)


def _flatten_skill_dict(skills: Dict[str, Any]) -> List[str]:
    flattened: List[str] = []
    for value in skills.values():
        if isinstance(value, list):
            flattened.extend([item for item in value if isinstance(item, str) and item.strip()])
        elif isinstance(value, str):
            flattened.append(value)
    return flattened


def _normalize_user_payload(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce loose resume/profile data into the GrestokUser schema shape."""
    if not isinstance(user_data, dict):
        raise ValueError("user_data must be a dict")

    normalized = dict(user_data)  # shallow copy

    prefs = normalized.get("preferences")
    if isinstance(prefs, dict):
        field_of_study = prefs.get("fieldOfStudy")
        if isinstance(field_of_study, str):
            prefs["fieldOfStudy"] = {"focus": field_of_study}
        elif field_of_study is None:
            prefs["fieldOfStudy"] = None

    resume = normalized.get("resumeExtracted")
    if isinstance(resume, dict):
        skills = resume.get("skills")
        if isinstance(skills, dict):
            resume["skills"] = _flatten_skill_dict(skills)
        elif isinstance(skills, str):
            resume["skills"] = [skills]

    return normalized


def update_profile_from_resume(email: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized_payload = _normalize_user_payload(user_data)
    grestok_user = GrestokUser.model_validate(normalized_payload)
    """
    Update Firestore user profile based on the Dict object  provided.
    Only fills in fields that are missing/empty in the existing document.
    """
    normalized_email = (email or "").strip()
    if not normalized_email:
        raise ValueError("email is required")

    logger.info("Fetching Firestore user profile for email=%s", normalized_email)
    #user_ref = client.collection("Users").document()
    users_ref = client.collection("Users")
    query = users_ref.where("email", "==", normalized_email).limit(1)
    existing_docs = list(query.stream())

    if not existing_docs:
        logger.warning("No existing Firestore document found for email: %s", email)
        return {"status": "error", "message": "User profile not found."}

    existing_doc = existing_docs[0]
    existing_data = existing_doc.to_dict() or {}
    updated_fields: Dict[str, Any] = {}

    # dump pydantic model to Firestore-shape (camelCase via alias), skip None
    new_data = grestok_user.model_dump(by_alias=True, exclude_none=True)

    def recursive_update(existing: Dict[str, Any], new: Dict[str, Any], path: str = ""):
        for key, value in new.items():
            current_path = f"{path}.{key}" if path else key

            # if this is a nested object
            if isinstance(value, dict):
                if key not in existing or not isinstance(existing.get(key), dict):
                    # whole nested object is missing, set it
                    updated_fields[current_path] = value
                else:
                    # go deeper
                    recursive_update(existing[key], value, current_path)

            # for non-dicts (str, int, list, etc.)
            else:
                # update ONLY if field missing or "emptyish" in existing
                if key not in existing or existing[key] in (None, "", [], {}):
                    updated_fields[current_path] = value

    recursive_update(existing_data, new_data)

    if updated_fields:
        # Update the Firestore document with the new fields
        user_ref = users_ref.document(existing_doc.id)
        user_ref.update(updated_fields)
        logger.info(
            "Updated Firestore document for email: %s with fields: %s",
            email,
            list(updated_fields.keys()),
        )
        return {"status": "success", "updated_fields": updated_fields}

    logger.info("No fields to update for email: %s", email)
    return {"status": "no_update", "message": "No fields were updated."}
