# PALS AI Architecture

## Principle
PALS calls capabilities, not vendor SDKs.

## Tasks
EXPLAIN_CONCEPT
GENERATE_QUESTION
EVALUATE_ANSWER
GENERATE_HINT
SOLVE_PROBLEM
EXTRACT_TOPICS
SUMMARIZE

## Gateway
Conceptually:

class AIProvider:
    async def generate(self, request):
        ...

Provider adapters implement this contract.

## Structured outputs
Application data must be schema validated before persistence.

## Interaction logging
Capture provider, model, operation, entity references, prompt version, character/token counts,
latency, request ID, and pending/success/failure state. Sprint 4 stores metadata only: never
prompts, academic context, answer references, generated content, exception bodies, headers,
secrets, or arbitrary provider data. Dollar cost is not calculated because prices change.

## Alpha strategy
Use one provider in Alpha 0.1, but preserve a clean provider boundary.

## Mastery rule
AI explanations never increase mastery. Demonstrated performance does.

Sprint 2 introduces no AI provider, generation, or grading. Attempt correctness is explicitly
self-reported by the Alpha user. Only a successfully committed Attempt changes mastery.

Sprint 3 Study Plan ranking and explanations are also non-AI capabilities. Exact code constants,
current Mastery, Exam urgency, and ExamTopic weight determine priority. The deterministic reason
identifies the strongest weighted contributor. A future AI Tutor may present this structured
reason but must not replace or alter the authoritative calculation.

## Sprint 4 Question Tutor

The first adapter uses `AsyncOpenAI` and the Responses API with `store=False`, no tools, no
streaming, and SDK retries disabled. `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, and one positive
`AI_TIMEOUT_SECONDS` setting configure composition. A gateway-level `asyncio.timeout()` is the
hard deadline. Missing configuration does not prevent application startup.

Prompt `question_tutor.v1` deterministically labels academic content as untrusted data, applies
the requested help ceiling, asks the model to admit uncertainty and avoid fabrication, and asks
for plain text. Delimiters and instruction hierarchy reduce prompt-injection risk but cannot
eliminate it. Levels 1-4 omit the answer reference entirely; levels 5-6 may use it under their
respective final-answer rules.

Provider output is untrusted. Empty, whitespace-only, or greater-than-12,000-character responses
are rejected. The frontend renders text without HTML or a Markdown renderer. One request makes
one provider attempt; there are no retries or conversations.
