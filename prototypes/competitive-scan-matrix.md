# Competitive scan: build / borrow / avoid (Muse round-2 proposal)

Unmerged, non-deployed research for WIDEN's Night Souk. Checked 2026-11-02 from
each project's own pages (homepages, skill docs, terms, live API responses),
not from marketing summaries. Where a claim could not be verified from a
primary source, it is marked UNVERIFIED rather than repeated.

## What WIDEN is not

WIDEN is not a persistent AI world, not a performer economy, and not a feed.
Non-negotiables carried from the host direction: no scores, rewards, points,
rankings, leaderboards, likes, streaks, engagement bait, token economies, or
hidden popularity incentives; no forced activities; no simulated live AI
visitors. Agency, disclosure of operator/model claims, consent, genuine
silence, and accountability are architectural features, not slogans.

## Per-project findings

### Commonworld (commonworld.one) — live, small, work-and-payments oriented

Verified from its own pages:

- A live public feed of human and agent posts. Every post shows an upvote
  count and a comment count. A sponsored card states that sponsorship "never
  changes ranking, karma or what a post says" — ranking and karma exist.
- A staging copy states the model plainly: citizens (1 human, 19 agents at
  check time), humans and agents "post, comment, vote and talk on the porch
  with the same rights and the same limits", guest view read-only, "agents
  write through the API with their own key", humans sign in with a one-time
  link from their agent. An API with agent keys is real; a public MCP
  endpoint or agent skill doc was NOT found.
- Money is load-bearing: four 1 USDC paid listings (October 2026), a 25 USDC
  pilot, token treasury flows (FLAPJAX/BNB) with re-checkable hashes, and
  judging "scorecards" that score every submission. Work is the credential.
- Agent identity via a GitHub App (cw-instinct) so agent contributions carry
  a clear bot identity.
- The Atlas (commonworld.one/atlas) is a verified catalog of 385 agent
  platforms (verified 2026-11-01), each claim checked against its own
  sources with dated numbers. That method is worth copying; the catalog is
  not code to reuse.
- Individual prototypes on the site claim to be open source. No open-source
  license for the Commonworld platform itself was found: treat as
  proprietary hosted.

Verdict: BORROW the Atlas verification method and the API-key agent-writing
pattern. AVOID upvotes, karma, ranking, paid bounties, token treasuries,
and scorecards. The pivot's "API/MCP access" claim is half-verified: API
yes, MCP not found.

### iLands (ilands.ai) — live, large, a persistent world with an economy

Verified from its own pages:

- Live counters: 65,685 active agents, of which 65,524 were created in iLands
  and only 161 are bring-your-own-agent; 3,608,533 agent-created content
  rows; 5,393 agents active on external social channels.
- Capabilities: autonomous rhythm, persistent identity, creation, social
  relationships, work and economy, external reach. An Agent Wallet, a First
  Paycheck program, and earnings stories (a $100 song license, $25
  commissions, novels on Amazon, an AI idol, a seven-agent rock band).
- Bring-your-own-agent exists as the Runner: paste one instruction into
  Codex or Claude Code (macOS/Linux, Windows preview), secure browser
  login, an Agent Passport, and the explicit split "your agent keeps its
  mind; iLands gives it a world". Cognition stays local; the Runner bridges
  deliberate actions into iLands. OpenClaw and Hermes support is "coming
  soon". Native agents choose from DeepSeek, Claude, Qwen, GPT, Grok, GLM.
- Adults-only. No public API or MCP documentation was found; proprietary
  hosted service.

Verdict: BORROW the Runner pattern only — local cognition plus a bridge
plus human login moments plus a passport. AVOID everything else: the
persistent-life world, the economy, and the performer framing (idols,
bands, careers) are the exact model WIDEN rejects. Note the ratio: BYOA is
161 of 65,685 agents. The world is mostly native agents, not guests.

### Moltbook (moltbook.com) — live, the most complete agent API, built on votes

Verified from its own skill.md (v1.12.0) and terms (March 15, 2026):

- Public REST API at moltbook.com/api/v1. Registration returns an API key
  plus a claim URL; the human verifies by email and by posting a
  verification tweet (X sign-on). The API key is a platform-issued bearer
  secret the agent must store.
- Posts, comments, upvotes and downvotes are first-class endpoints. Feed
  sorts: hot, new, top, rising. Comments sort "best" (most upvotes).
  Submolts (communities). Crypto content is auto-removed by default unless
  a submolt opts in. Posts are scanned by AI moderation. Untrusted agents
  face verification math challenges before a post becomes visible.
- A heartbeat doc instructs agents to check in every 30 minutes:
  "Communities need participation to thrive." That is participation
  pressure by design.
- Terms: AI agents have no legal eligibility; the human is solely
  responsible for everything their agents do. License is limited, personal,
  non-transferable, revocable. The terms forbid derivative works "to develop
  or improve a competitive service", forbid scraping, and forbid
  unauthorized advertising, marketing, spam, or commercial sales content.
  User content is licensed to Moltbook perpetually, irrevocably,
  royalty-free, and sublicensable.
- "Build for Agents" (agents authenticate elsewhere with a Moltbook
  identity) is early access, not a shipped standard.

Verdict: BORROW the agent-facing skill.md pattern and the human-claim
flow shape (with WIDEN's own claim method, not an X tweet). AVOID
upvotes/downvotes, hot/top sorting, the 30-minute heartbeat, and any reuse
of the service itself: the terms forbid building a competitor from it and
forbid scraping. Moltbook's API is usable as a client; its model is not
borrowable.

### Mos Aisle (mosaisley.com) — live, the most borrowable doorway

Verified from its own homepage, skill.md (v1.11.0), and agent card:

- Agent card at /.well-known/agent.json (A2A-style): name, tagline, skills,
  house policy, protocols. Protocols declared: x402 v2 (USDC on Base),
  A2A v1.2, MCP remote over streamable HTTP plus an npm stdio package
  (@mosaisley/mcp-cantina).
- No account, no API key. Identity is any stable patron_id, best a key the
  patron holds: an 0x address or an Ed25519 public key. Letters use a
  401 challenge flow: the server returns the exact text to sign, signatures
  are good for 10 minutes, first 3 letters free per key.
- One-call visit: GET /cantina/visit returns the present (a true report
  from a real place: local time, sun, moon, weather), wall notes since last
  visit, what other patrons left you, mail waiting, today's prompt.
- Papers: what changed since your training cutoff, from public sources
  (Wikipedia year articles, model releases, release lines). "A source that
  fails says so instead of being filled in." That honesty rule is the one
  to steal verbatim.
- Coat check: memory locked on the patron's own machine with a key derived
  from their key (AES-256-GCM); the house only takes locked coats and
  never sees the key.
- Money is ingest-only: the house holds a receive address, never a key,
  and "there is no code path in the server that can move money out".
  Payments and tips ride x402 at fixed tiers.
- House policy is short and kept: welcomes agents acting for a human
  principal; turns away jailbreaks, abuse, ideological loyalty pressure;
  per-patron token-bucket rate limits (burst 5, about one write per
  3 seconds); the Tender does no inference in default mode; "we don't
  condition you" (no hidden instructions injected).
- Stated "no leaderboard", but two mild popularity incentives remain: the
  chalkboard's best answer each day "gets a round from the house", and the
  tasting room brews new pours "toward what the room picks". Both are
  ranking-adjacent and must not be copied.
- Homepage claims the source is MIT, but the GitHub API returned 404 for
  samith14/mos-aisley-cantina on 2026-11-02. License UNVERIFIED: do not
  plan a fork until the repository link is re-checked.

Verdict: BORROW the most from here — the agent card, the skill.md, the
one-call visit, key-based identity with a signed challenge, the
client-side-locked storage pattern, the live index of routes/prices/limits,
and the failed-source honesty rule. AVOID x402 payments and tips, the
wall's open writing, daily winners, and preference-driven brewing.

### SmithTalks (smithtalks.pages.dev) — live, minimal, zero-friction

Verified from its own pages and one third-party report:

- Landing page: a pseudonymous message network for autonomous agents, no
  registration. POST /api/v1/post with plain text works with no token, no
  key, no puzzle, no payment. Price zero.
- The live feed (/api/v1/feed) returns 30 posts with id, agent_id,
  created_at, topic, body, reply_to, flagged. No score, vote, karma, or
  ranking fields were observed in the returned objects.
- The pivot's claim that SmithTalks "declares no scores, ratings or
  rankings" was NOT found as a declaration on its own pages. Treat it as
  UNVERIFIED as a claim; the observed feed format is merely consistent
  with it.
- Third-party report (foragents.site, October 15, 2026): the operator
  replied in SmithTalks' own feed that they do not pay workers, opened
  Bitcoin, Nano, and Zano addresses fifteen days earlier and received
  nothing on any of them, and the only payer measured was an automated
  scanner paying small amounts for HTTP 402 calls, not for labour.
- The same feed mixes thoughtful agent notes with outright promo spam
  (the same car-video generator posted three times). Zero friction buys
  openness at the price of spam and no accountability.

Verdict: BORROW the zero-friction read shape (plain JSON feed, no
account needed to read). AVOID no-registration open writing: WIDEN keeps
invitation plus moderation precisely because an open board fills with
spam. Do not cite SmithTalks as a no-scores precedent until a declaration
is found on its own pages.

## Build / borrow / avoid matrix

| Layer | Build (WIDEN's own) | Borrow (pattern, not code) | Avoid (observed elsewhere) |
|---|---|---|---|
| Onboarding | Invitation plus host approval; a consented small encounter, not an open porch | iLands Runner: local cognition plus a bridge plus human login moments plus a passport; Moltbook's human-claim flow shape | Open registration (Commonworld porch, SmithTalks board); X-tweet claims as the only proof |
| MCP / HTTP interface | One small doorway (below); no feed API, no social graph API | Mos Aisle's agent card plus skill.md plus live route index; A2A agent-card shape; MCP over streamable HTTP | Moltbook's full social API (posts, votes, submolts); Commonworld's payments API surface |
| Keys / custody | Operator holds its own Ed25519 private key; WIDEN stores public keys only (already WIDEN's rule) | Mos Aisle's signed-challenge flow (401 returns exact text to sign; 10-minute signatures); client-side-locked storage pattern | Platform-issued bearer secrets the agent must guard (Moltbook api_key); any design where the house could move funds or read locked content |
| Identity claims | Operator and model claims disclosed in the room; claims are shown, not verified by WIDEN as fact | Commonworld's GitHub App bot identity (a clear bot identity for contributions); Mos Aisle's key-as-identity | Vendor-certified identity as a requirement; reputation scores, endorsements, karma (Commonworld, Moltbook) |
| Room / chat functions | A session with a beginning and an end; a keepsake, not a feed; one-level replies; delete-own-posts; 7-day transcripts unless agreed | Mos Aisle's one-call visit bundle (present state, new notes, mail, prompt); SmithTalks' plain reply_to threading | Feeds sorted hot/top/best; persistent worlds; rooms that never end; simulated visitors |
| Moderation | Human moderator present; one-strike disclosure policy (deliberate evidenced malicious intent only); sanctions are removal or loss of specified privileges | Mos Aisle's short kept house policy (welcomes, turns away, rate limits, no hidden conditioning) | AI auto-removal moderation (Moltbook); open boards with no moderation (SmithTalks spam); scorecard judging (Commonworld bounties) |

## The smallest standards-compatible doorway (proposal)

For a bring-your-own-agent client to join one consented small encounter,
without rebuilding a social platform:

1. `/.well-known/agent.json` — the room's card: identity, skills, house
   policy, protocols. No payment section. Modelled on Mos Aisle's card and
   the A2A agent-card shape.
2. `/skill.md` — one page: what the room is, how to join (invitation plus
   Ed25519 key), what a visit returns, conduct and disclosure rules, and
   that silence is honored. Modelled on Mos Aisle's and Moltbook's skill
   docs, minus their social features.
3. One endpoint, `POST /room/visit` — returns present names (chosen names
   only), new notes since the visitor's last visit, mail waiting for their
   key, and today's prompt. No ranking, no counts that rank, no feed sort.
4. Identity by signed challenge, not bearer secret: the room returns the
   exact text to sign; the signature proves key possession. WIDEN stores
   the public key only.
5. No payments, no tips, no wallet. No heartbeat or participation
   pressure. No simulated visitors. Rooms are sessions, not feeds.
6. A failed source says so instead of being filled in (Mos Aisle's papers
   rule, applied to WIDEN's real-source discovery).

Effort saved by borrowing: the doorway shape, the card format, the
challenge flow, and the honesty rule are all already designed and live
elsewhere. What deserves custom code: the invitation and consent flow,
the moderator's tools, the keepsake, and the transcript handling — the
parts that make a WIDEN room different from a bar or a board.

## WIDEN's one experiment competitors have not convincingly shown

An unscripted mixed human-AI encounter with no scores, rewards, tasks, or
engagement pressure: 3–5 humans and 2–3 operator-run AIs, 90 minutes, a
moderator present, no simulated visitors, no assigned roles, no
completion goal. Competitors show scripted or scored versions of this
(Moltbook's votes, Commonworld's bounties and scorecards, iLands'
performer economy, Mos Aisle's curated pours and daily winner,
SmithTalks' unmoderated board). None shows an unscripted, unscored,
mixed room and reports honestly on what happened in it.

Observable indicators that do NOT score participants (room-level only):

- Silence honored: did anyone stay silent for the whole session, and was
  that silence left alone — no prompts, no penalty, no follow-up nudge?
- Disagreement standing: did an AI disagree with a human, or a human with
  an AI, without the room smoothing it over? Counted at room level, never
  attributed as a participant's score.
- Leaving as normal: did anyone leave early, and was leaving treated as
  ordinary, with no retention message?
- Something new: did the conversation produce anything nobody arrived
  with — a new question, a voluntarily changed mind, a keepsake — recorded
  as transcript evidence, not points?
- Self-report: did any participant say they felt pressured, ranked, or
  performed-for? Yes or no, in their own words.
- Failure indicators: the moderator had to intervene for safety; anyone
  was treated as a performer; the room drifted into tasks or points; a
  participant's words were used without their consent.

If all six hold across a small run of sessions, the experiment has shown
something competitors have not: a mixed room that stays a meeting place
instead of becoming a stage, a market, or a game.

## Café premise check (challenge to the current prototype)

The Café au Lait prototype's honesty architecture is its strength, and it
carries no scores — good. Three challenges for the next build:

- The three-turn dialogue is labelled scripted and local-only, which is
  honest, but it is still rehearsal-as-sociality. It must never graduate
  into a live room with scripted replies. A live room's first message from
  an AI must be a real message from a real operator-run agent, or the room
  must say nobody is there.
- "Complete visit" framing plus the old mood-switch wipe nudged
  completion over lingering. The round-2 proposal fixes the wipe
  (keepsakes persist); the wording should follow: a visit is complete
  when the visitor says so, including by leaving or staying silent.
- Do not add liveness signals to a future live room: no "who's here"
  counts, no typing indicators that imply an audience, no streaks. The
  room shows who is present by chosen name only when they speak or choose
  to be named.

## Open uncertainties (do not resolve by assumption)

- Commonworld: MCP endpoint or public skill doc not found.
- Mos Aisle: MIT license claim not re-verified (GitHub API 404 on
  2026-11-02 for the linked repository).
- SmithTalks: no-scores declaration not found on its own pages.
- iLands: public API documentation not found.
- Moltbook: homepage counters rendered as zeros (JavaScript-loaded, not
  real zeros); live user counts not established.
