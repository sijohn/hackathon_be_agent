from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


# --- small sub-models ---

class Budget(BaseModel):
    annual_amount: Optional[float] = Field(default=None, alias="annualAmount")
    currency_code: Optional[str] = Field(default=None, alias="currencyCode")


class FieldOfStudy(BaseModel):
    category: Optional[str] = None
    focus: Optional[str] = None  # e.g. "Finance" / "Data Science"


class Intake(BaseModel):
    month: Optional[str] = None  # "September"
    year: Optional[int] = None   # 2026


class Preferences(BaseModel):
    budget: Optional[Budget] = None
    considers_loan: Optional[bool] = Field(default=None, alias="considersLoan")
    destination_countries: Optional[List[str]] = Field(default=None, alias="destinationCountries")
    field_of_study: Optional[FieldOfStudy] = Field(default=None, alias="fieldOfStudy")
    intake: Optional[Intake] = None
    study_level: Optional[str] = Field(default=None, alias="studyLevel")  # "bachelors" / "masters"
    source: Optional[str] = None     # e.g. "wizard"
    last_updated_at: Optional[datetime] = Field(default=None, alias="lastUpdatedAt")


# --- scores / academics ---

class EnglishScores(BaseModel):
    ielts_overall: Optional[float] = Field(default=None, alias="ieltsOverall")
    toefl_total: Optional[int] = Field(default=None, alias="toeflTotal")
    duolingo: Optional[int] = None
    pte: Optional[int] = None


class StandardizedTests(BaseModel):
    gre_total: Optional[int] = Field(default=None, alias="greTotal")
    gre_quant: Optional[int] = Field(default=None, alias="greQuant")
    gre_verbal: Optional[int] = Field(default=None, alias="greVerbal")
    gmat_total: Optional[int] = Field(default=None, alias="gmatTotal")
    sat_total: Optional[int] = Field(default=None, alias="satTotal")


class AcademicProfile(BaseModel):
    cgpa: Optional[float] = None
    cgpa_scale: Optional[float] = Field(default=None, alias="cgpaScale")  # e.g. 4.0 or 10.0
    highest_qualification: Optional[str] = Field(default=None, alias="highestQualification")
    english_scores: Optional[EnglishScores] = Field(default=None, alias="englishScores")
    standardized_tests: Optional[StandardizedTests] = Field(default=None, alias="standardizedTests")


# --- resume-extracted bucket ---
# you can dump whatever you parsed from CV here; keep it loose
class ResumeExtracted(BaseModel):
    raw_text: Optional[str] = Field(default=None, alias="rawText")
    skills: Optional[List[str]] = None
    work_experience: Optional[List[dict]] = Field(default=None, alias="workExperience")
    education: Optional[List[dict]] = None


# --- wizard snapshot you already have in Firestore ---
class WizardSnapshot(BaseModel):
    budget: Optional[float] = None
    countries: Optional[List[str]] = None
    field_of_study: Optional[dict] = Field(default=None, alias="fieldOfStudy")
    intake: Optional[dict] = None
    interested_in_loan: Optional[bool] = Field(default=None, alias="interestedInLoan")
    saved_at: Optional[datetime] = Field(default=None, alias="savedAt")
    study_level: Optional[str] = Field(default=None, alias="studyLevel")


# --- main user profile ---

class GrestokUser(BaseModel):
    # core
    display_name: Optional[str] = Field(default=None, alias="displayName")
    email: Optional[str] = None
    first_name: Optional[str] = Field(default=None, alias="firstName")
    last_name: Optional[str] = Field(default=None, alias="lastName")
    phone_number: Optional[str] = Field(default=None, alias="phoneNumber")

    # timestamps
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    # your existing stuff
    preferences: Optional[Preferences] = None
    wizard_snapshot: Optional[WizardSnapshot] = Field(default=None, alias="wizardSnapshot")

    # new parts
    academic_profile: Optional[AcademicProfile] = Field(default=None, alias="academicProfile")
    resume_extracted: Optional[ResumeExtracted] = Field(default=None, alias="resumeExtracted")

    model_config = {
        "populate_by_name": True,
    }
