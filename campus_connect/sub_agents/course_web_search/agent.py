"""Course and University search agent for finding courses and universities using search tools."""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-flash"


course_college_websearch_agent = Agent(
    model=MODEL,
    name="course_college_websearch_agent",
    instruction=prompt.COURSE_COLLEGE_WEBSEARCH_PROMPT,
    output_key="course_college_citing",
    tools=[google_search],
)