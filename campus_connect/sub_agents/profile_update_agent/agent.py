from google.adk.agents import LlmAgent
from ...schema.user_profile import GrestokUser
from ...tools.update_profile_from_resume import update_profile_from_resume

from .prompt import PROFILE_UPDATE_PROMPT

profile_update_agent = LlmAgent(
    name="profile_update_agent",
    model="gemini-2.5-flash",
    instruction=f"""You are the Grestok Profile Update Agent.
      Your task is to update user profile in firestore using the tool {update_profile_from_resume} based on the input provided. 
      Follow the guidelines strictly as defined here {PROFILE_UPDATE_PROMPT}
You can use web search tool if needed to verify any information and also to get more details outside the database about the campus and job oppurtunities in that area etc""",
    input_schema=GrestokUser,
    tools=[update_profile_from_resume],
    output_key="profile_update_patch",
)
