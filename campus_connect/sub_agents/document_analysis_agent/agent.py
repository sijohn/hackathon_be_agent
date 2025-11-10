from google.adk.agents import LlmAgent
from google.genai import types

from ...schema.user_profile import GrestokUser


resume_extractor_agent = LlmAgent(
    name="resume_extractor_agent",
    model="gemini-2.5-flash",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2, # More deterministic output
        max_output_tokens=25000,
        safety_settings=[
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
            )
        ]
    ),
    instruction="""You are an agent that provides document analysis.
When a user uploads a document for updating his/her profile, you need to analyze the document and extract relevant information.:
1. Identify if the document is a Resume/CV or a marklist or any other academic document.
2. Extract the relevant information from the document.
3. Structure the extracted information in a JSON format.
4. Ensure that the key information in the incoming JSON is preserved in the output JSON. The key information will be first name, last name, email, phone number etc.
5. If the document is a Resume/CV, extract skills, work experience, education details etc.
6. If the document is a marklist or any other academic document, extract academic details like CGPA, highest qualification, standardized test scores etc.
7. If the document type is not recognized, return an empty JSON object.

""",
    input_schema=GrestokUser, # Enforce JSON input
    output_schema=GrestokUser, # Enforce JSON output
    output_key="document_analysis_patch",
)
