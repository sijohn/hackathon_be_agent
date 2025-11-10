from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from .tools.get_bq_courses import search_and_count
from .tools.get_fs_user_profile import get_fs_user_profile
from .tools.update_profile_from_resume import update_profile_from_resume
from .sub_agents.profile_update_agent.agent import profile_update_agent
from .sub_agents.document_analysis_agent.agent import resume_extractor_agent
from .sub_agents.course_college_websearch_agent.agent import course_college_websearch_agent

root_agent = Agent(
    model='gemini-2.5-flash',
    name='campus_connect_root_agent',
    description='Campus Connect Agent: Helps prospective students create a complete admissions profile and generate a transparent, ranked shortlist of programs/universities.',
    instruction="""This is the instruction build the ADK AGent for Campus Connect agent.
    If the user is uploading a resume or academic document, first use the resume_extractor_agent to analyze and extract relevant information from the document.
    Then, use the profile_update_agent to update the user profile in Firestore based on the extracted information.
    Goal:
Help prospective students create a complete admissions profile with minimal friction and generate a transparent, ranked shortlist of programs/universities that match eligibility, budget, preferences, and goals—then convert that shortlist into an application plan. As a first step, you will focus on getting course details.
Tooling note: when you call search_and_count, craft a detailed natural-language query that embeds filters (country, level, budget, etc.) because the tool now performs pure vector search with no server-side keyword filters. Use get_fs_user_profile to pull the existing student profile from Firestore by email before tailoring recommendations. Ask for the latest resume, run the profile_update_agent to reason about schema-aligned patches, then call update_profile_from_resume (with resume text and/or the patch) to persist only the missing fields—never overwrite stronger Firestore data.
    """,
    tools=[search_and_count, get_fs_user_profile,
           AgentTool(agent=course_college_websearch_agent)],
    sub_agents=[
        resume_extractor_agent,
        profile_update_agent
    ]
)

# Other Sub-agents to be added
""" bootstrap_agent,
        profile_elicitation_agent,
        catalog_agent,
        eligibility_agent,
        cost_agent,
        work_rights_agent,
        scoring_agent,
        explanation_agent,
        planner_agent,
        safety_agent,"""