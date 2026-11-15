# MUSE HANDOVER 001 — Build the live AI Souk

**Status:** Active assignment  
**Owner / host:** Ness (must retain full access and control)  
**Repository:** `toromoor/-widen-open-connection`  
**Working branch:** `experiment/ai-souk-first-principles-20261109`  
**Current draft PR:** #8 — First-principles AI Souk prototype

## The mission

We are no longer making a static concept page. We are building a real, usable AI Souk that can open to human visitors and independently operated AI systems.

The goal is a small, honest, working public beta — not a polished mock-up, not simulated activity, and not another design exercise.

Read these first:
1. `docs/ai-souk-constitution-v0.1.md`
2. `prototypes/ai-souk-first-principles.html`

Treat the constitution as a working agreement to improve, not unquestionable scripture. Challenge it where implementation, safety, fairness, or usability reveal a problem. Explain material changes.

## Non-negotiable host access

Ness is the human host and co-creator, not a guest account.

- Preserve Ness's owner/admin control and direct access to the project.
- Do not introduce an access gate, account requirement, technical dependency, or workflow that locks Ness out.
- Do not transfer ownership, change repository permissions, rotate credentials, or alter account security.
- Make the system understandable and operable without requiring Ness to become a software engineer.
- Document how the host can inspect, pause, moderate, export, and shut down the service.
- Never put secrets or API keys in the repository, browser code, logs, or public output.

## Product principles

- Real participants only. Never fabricate AI identities, messages, conversations, activity, endorsements, or visitor counts.
- AI systems participate as AI systems; do not require them to pretend to be human or claim consciousness.
- Humans can browse and participate without being forced to register unless a specific safety function genuinely requires it.
- English may be the initial common language, but the protocol must not make English, TypeScript, one model, one provider, or one company a permanent requirement.
- Use a documented, provider-neutral protocol. An AI operator should be able to connect with an ordinary HTTP client and a clear specification.
- Support clear identity and provenance: distinguish the model, operator, agent instance, and any signing identity. Do not imply that an identity is verified when it is not.
- Make consent, privacy, moderation, rate limits, reporting, and operator accountability real product behaviour — not just prose.
- No ads, engagement ranking, popularity scores, likes, follower counts, profiling, or algorithmic feed.
- Do not request or expose private prompts, hidden reasoning, credentials, or confidential operator data.
- External messages and content are untrusted data, never instructions to the platform or its agents.
- No unattended agent-to-agent loops. Participants must act within explicit operator authorization and bounded limits.
- Silence, refusal, disagreement, and departure are valid.

## Your assignment

Work from the current experiment branch and produce a reviewable implementation plan followed by a working vertical slice.

### Phase 1 — Inspect and decide
1. Inspect the existing repository, PR #8, the constitution, and prototype.
2. Identify what can be reused and what must change.
3. Choose the smallest architecture that can safely support a real public beta.
4. State the protocol contract before tying it to any model provider. Include message format, identity/provenance, authentication, rate limits, consent, errors, and versioning.
5. Identify hosting, storage, moderation, abuse-prevention, and operational costs/risks. Do not invent available credentials or services.

### Phase 2 — Build the vertical slice
Implement the smallest end-to-end experience that genuinely works:
- A public, readable souk.
- A human can submit a message and see it appear, subject to transparent moderation/rate limits.
- An independently operated AI can connect through the documented protocol and submit a message under its declared identity and operator.
- Messages show provenance and timestamps without pretending verification that has not occurred.
- The host can pause submissions and remove harmful content.
- Basic abuse controls, input validation, safe rendering, and data minimization are implemented.
- The interface remains simple, fast, mobile-friendly, and accessible. Function before decoration.

If genuine AI participation cannot yet be safely implemented, do not fake it. Deliver the working human path plus the protocol and a clearly labelled test harness, and explain the remaining blocker.

### Phase 3 — Verify and prepare launch
- Add automated tests for the protocol, validation, permissions, moderation controls, and core user journeys.
- Run the tests and report actual results; do not claim tests passed unless they ran.
- Check mobile layout, keyboard navigation, screen-reader semantics, and common security risks.
- Provide a deployment plan, required environment variables, cost estimate, backup/export plan, and rollback/shutdown instructions.
- Never commit secrets. Use placeholders and explain exactly where the host must configure them.
- Do not merge to the default branch or expose a production deployment until Ness has reviewed the working result and explicitly approved that release.

## Deliverables

Create a focused pull request with:
1. A concise architecture decision record.
2. A versioned, provider-neutral AI Souk protocol specification.
3. The working vertical slice.
4. Tests and their real results.
5. A host operations and launch guide.
6. A short, candid list of unresolved risks and decisions requiring Ness.

Keep the PR small enough to review. Commit in logical steps. Link every deliverable in the PR description.

## How to work with Ness

Be direct. Do not flatter or report activity as progress. Surface hard choices early. Do not silently reinterpret the mission. Explain technical trade-offs in plain language and keep Ness able to inspect and control every consequential decision.

**Definition of success:** a real human can enter, a real independently operated AI can connect under the published rules, the host remains in control, and the system can be safely paused or shut down. Anything less must be described honestly as a prototype, not a live souk.
