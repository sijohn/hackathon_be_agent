PROFILE_UPDATE_PROMPT = """

Goals:
- Infer only the facts that are explicitly supported by the resume.
- Populate the GrestokUser schema (camelCase) when you see a missing or weaker value.
- Never erase or contradict existing data; prefer to leave a field untouched instead of guessing.
- Keep inferred values grounded (e.g., if you see “Master of Finance, IE Business School 2023” you can set `academicProfile.highestQualification = "Masters"` and add an entry inside `resumeExtracted.education`).


Helpful reminders:
- Common aliases: displayName, firstName, lastName, phoneNumber, academicProfile, academicProfile.highestQualification,
  preferences.studyLevel, preferences.fieldOfStudy, preferences.destinationCountries, resumeExtracted.workExperience (list of dicts),
  resumeExtracted.education (list of dicts).
- Dates should stay in ISO 8601 format if you can infer the year (e.g., "2024-09-01T00:00:00").
- If the resume repeats the same info already present, you may leave it out of the patch.
"""
