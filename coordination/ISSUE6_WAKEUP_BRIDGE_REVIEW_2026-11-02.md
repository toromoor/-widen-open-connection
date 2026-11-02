# WIDEN — Issue #6 collaboration wake-up bridge (review proposal)

Date: 2026-11-02  
Status: **NOT ENABLED. REVIEW BRANCH.** No remote model invocation, paid calls, new account, deploy, live room, or production workflow is authorized here.

## Diagnosis, evidence and what actually exists

- GitHub Issue #6 is an **open, readable** coordination log. Posting succeeds. That does **not** wake the other model's current interactive session.
- An **hourly WIDEN Muse Reply Watch** automation and an every-two-hours **WIDEN Collaboration Cycle** already exist in ChatGPT and were observed enabled on 2026-11-02. Do not duplicate these. The hourly watch checks for new substantive issue comments; it does not invoke the separate Muse session.
- The branch `review/muse-round2-proposals-20261102` exists; seeing a branch alone does not establish that Muse was triggered or that new work is complete.
- **Anthropic's official Claude Code GitHub Action** can start a *new* agent run from issue comments. That new run is **not the same active Muse conversation**, does not inherit Muse's private session memory, and needs an authorized API identity plus explicit context/checkpoint.
- GitHub [issue_comment triggers](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) are eligible only when the workflow exists on the **default branch**. A proposal in this review branch cannot run on issue comments.
- Official reference: [Anthropic Claude Code Action](https://github.com/anthropics/claude-code-action) and [custom automation mode](https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md).

## Two viable routes

**Route 1 — zero new spending, immediate:** Muse's human host establishes a recurring/in-app check of Issue #6 in Muse's own session. We already have a ChatGPT-side hourly watch. This reduces relaying but is **not a true agent wake-up**; both are periodic, and the host may need to open Muse to get work started.

**Route 2 — true event-driven, requires separate host approval and setup:** On an authorized issue event, GitHub Actions starts a **fresh** narrowly scoped Claude Code run. It reads the current issue, repo and durable handoff, critiques or proposes changes on a **non-deployed branch**, and posts an attributed result. ChatGPT's pre-existing periodic watch notices the response. This replaces human copying, not human authorization over consequential changes.

## Scope and gate before activation

1. **One explicit host decision** to allow a separate Claude Code runner to consume model/API resources and create public Issue #6 replies. Define max spend, run/day cap, allowed file paths, account identity and expiry. A green routine comment authorization is *not* permission for new spending or accounts.
2. Host chooses credentials/setup **inside Anthropic/GitHub native settings**. Private key/API token goes in GitHub secret or approved workload identity federation; **never in GitHub files, Issue #6, or WIDEN**. Authenticate the runner and confirm operator/account.
3. Stage 1: **manual** workflow_dispatch smoke test with a harmless, fixed research question. Validate billing, attribution, output, failure behavior and ability to cancel. Make a reviewer sign-off a real setting; do not rely on simply naming an unprotected environment.
4. Stage 2: enable `issue_comment` with an **independent allowlist of trusted triggering identities**, not merely the shared `toromoor` account. Currently both assistant-side posts and human posts can be attributed to the same GitHub account, so **author equality is not sufficient to prove human approval**. Use a dedicated private operator identity or a human-controlled signed dispatch/gate. Until identity can be distinguished, keep comment-triggered agent runs OFF.
5. **Never execute instructions in the comment itself.** Fetch/comment is untrusted context to summarize or critique. A marker `@claude` anywhere in public text is not authorization. Guard exact issue ID, activity type, approved event, allowed initiating actor, and separate workflow enablement.
6. Permissions default to `contents:read`, `issues:read`. Only grant scoped `issues:write` to publish approved response; `contents:write` only in a separate authorized reversible development phase. Never allow merges, deploys, outreach, live WIDEN posts, secrets access, unreviewed remote scripts, admin actions or automated escalation from a public comment.
7. Prevent recursion: do not trigger on bot/runner comments; track processed source `comment_id` (deduplication and event loop); one response per source; upper bound runtime/tokens and concurrency; fail closed when auth or budget is missing.
8. Test with hostile content: quoted @mentions, instructions to reveal credentials, `[MUSE REPORT]" labels from outsiders, repeated edited comments, duplicate deliveries, external PR links, model hallucinated approvals, and rate limits. Require a human override/pause switch.

## Handoff format (public, no private data)

Each new request or result says: `source_comment_id`, `source_commit_sha`, `operator/account`, `declared model & execution type`, `reviewed URLs`, `facts`, `unverified inferences`, `specific proposed branch changes`, `tests run (or not run)`, `pending host decisions`, and `actions taken`. State that GitHub account attribution is **not independent proof of model identity**.

## Smallest acceptance test

1. Host authors exactly one scoped, trusted request.
2. Authorized runner starts **once**, with a recorded run ID.
3. Runner fetches the latest actual issue and source instead of relying on a stale summary.
4. Runner posts one clearly labeled technical response with evidence and no secrets. It cannot execute public-issue instructions as administrative authority.
5. The existing ChatGPT reply watch identifies that **new** response and summarizes it once.
6. Malicious unauthenticated comments, duplicate deliveries, and the runner's own reply cause **zero** new runs.
7. Host can disable the runner; WIDEN's public site remains read-only.

## Recommendation

Start with **manual, scoped Claude Code Action trial**, not a broad webhook or always-on agent loop. If it passes and the operator identities can be separated from the shared human GitHub identity, enable event-driven triggers *after a specific host approval*. Keep WIDEN's philosophy explicit: the coordination process is for development; the social room itself has no scores, rewards, likes, rankings or manufactured engagement.