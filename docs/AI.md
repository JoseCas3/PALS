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
Capture provider, model, task, tokens, latency, success/failure, error and estimated cost when available.

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
