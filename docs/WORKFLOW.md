# Multi-Model Workflow

## Roles
- Human: product owner + functional tester
- Architecture/specification: defines requirements and contracts
- Codex: primary implementer
- Claude: code reviewer, no editing while reviewing
- Gemini: technical researcher
- GPT-6 Astra: milestone architecture/integration reviewer

## Feature flow
Requirement → specification → Codex implementation → tests → Claude review → Codex fixes → human test → merge

## Milestone flow
Merged sprint → GPT-6 Astra integration review → follow-ups/ADRs → next sprint

## Important anti-pattern
Do not ask several models to independently build the same feature. Use one specification, one primary implementer and independent reviewers.

## Astra use
Best for end-to-end architecture reviews, difficult debugging, migrations, security-sensitive design and major AI gateway changes.
Avoid using it for routine CRUD, boilerplate or trivial fixes.

## End-of-Alpha integration verification

Sprint 7 closes with the full backend and frontend suites, migration drift checks, the Docker smoke
pass, and `npm run test:e2e`. The Playwright test provisions a disposable PostgreSQL/API stack,
runs the real browser flow without an AI key, and removes that stack afterward. A short human pass
then checks hierarchy, selected-context clarity, conflict feedback, and narrow-screen usability.
