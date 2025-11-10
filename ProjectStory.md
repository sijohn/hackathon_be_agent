# Project Story

## Inspiration
We wanted prospective students in emerging markets to get transparent admissions guidance without waiting for a counselor. Watching human advisors juggle profile gaps, program research, and funding constraints inspired us to encode the same workflow inside a reliable agent that can appear in any chat interface.

## What it does
- Authenticates learners through Firebase, then passes their prompts—tagged with verified email context—to the CampusConnect root agent.
- Uses ADK tools to pull/update Firestore profiles, parse resumes, and perform BigQuery-powered course searches.
- Serves a Next.js experience with chat, **My Profile**, and **My Applications** views, backed by the same Cloud Run endpoint.

## How we built it
- **Agent core**: Google ADK orchestrates the CampusConnect root agent plus sub-agents for document analysis and profile updates.
- **Serverless runner**: FastAPI on Cloud Run verifies JWTs, initializes the Runner + session service, and forwards messages to the agent.
- **Data + auth**: Firestore and BigQuery hold student data and catalog insights, while Firebase Authentication unifies email/social logins.
- **Frontend**: Next.js consumes Firebase client SDKs for auth and calls `/grestok-agent/` for chat + dashboard data.

## Challenges we ran into
- **Token verification**: Supporting both inline JSON credentials and ADC fallback was essential for local dev vs. Cloud Run.
- **Streaming UX**: Server-sent events complicated the frontend, so we aggregate the final response while logging intermediate events.
- **Prompt rigor**: Vector-search tooling demanded detailed natural-language filters; we added guardrails to avoid empty results.
- **Time pressure**: Parallelizing Cloud Build and IaC early saved us from last-minute deployment surprises.

## Accomplishments that we're proud of
- Hit sub-second cold starts on Cloud Run even after initializing Firebase Admin and ADK.
- Maintained deterministic behavior by tying `user_id` to Firebase UID and injecting authenticated email text into every prompt.
- Produced a reusable agent runner template that other Grestok teams can fork for their own AI agent surfaces.

## What we learned
1. Fine-grained session management in ADK matters—tying `user_id` to Firebase UID keeps context isolated.
2. Cloud Run cold starts can be mitigated by warming long-lived singletons during the FastAPI `startup` event.
3. Prompt hygiene matters; surfacing the authenticated email in every message reduces hallucinated personas.
4. Visualizing tool flows helped verify that $f(x)=\operatorname{Agent}(x)$ stays deterministic despite branching logic.

## What's next for CampusConnect Agent
- Expand the tool catalog with financial-aid estimators, visa-readiness checklists, and application timeline planners.
- Add multilingual prompts plus translation layers so non-English speakers can participate.
- Reintroduce streaming responses via WebSockets once the frontend can display token-level updates.
- Layer analytics dashboards to highlight where students drop off and when a human counselor should intervene.
