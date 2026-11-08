# Phase 3S — Escalation Rules and Notification Preferences

## Status
Stages 1–2 are implemented: versioned policy/preferences, idempotent SLA evaluation, and durable tenant-local in-app outbox intents. Stage 3 adds a recipient-scoped inbox read API and read acknowledgement. No background delivery worker or external provider is enabled.

## Goals
1. Configure severity- and SLA-state-based escalation rules without hardcoded recipient identities.
2. Allow tenant users to manage notification preferences independently by event type and channel.
3. Persist notification intent transactionally through an outbox; never call email, SMS, push, or external providers inside an investigation request transaction.
4. Make scheduling, retries, deduplication, and delivery outcomes observable and auditable.
5. Keep the initial implementation safe when no scheduler or provider adapter is configured: events remain queued or dispatch remains disabled rather than silently disappearing.

## Policy model
An escalation rule is versioned and tenant-scoped. It is keyed by severity and trigger (WARNING or BREACHED) and contains an enabled flag, optional delay in minutes, recipient role references (role IDs from the tenant role catalogue), allowed channels (IN_APP, EMAIL, SMS, PUSH) constrained by enabled provider capabilities, priority, and policy version.
Only one active rule per severity/trigger pair is permitted. Policy edits create a new version; historical versions remain available. Investigation cases retain the policy version that generated an escalation event.

## User notification preferences
Preferences are per user, event type, and channel, with explicit enabled/disabled state and update actor/time. Defaults are opt-in only for in-app operational notifications; external channels are disabled unless explicitly configured and supported. A preference cannot widen the channels allowed by the escalation policy. User deactivation and role membership are rechecked at dispatch time.

## Durable outbox
Each notification intent is written to a tenant-local outbox row in the same database transaction as evaluator work. The initial evaluator slice stores a stable idempotency key (case ID + trigger + policy ID/version + recipient + channel), event type, case ID, policy ID/version, recipient user ID, channel, minimal payload, status, available-at time, and timestamps. The schema reserves the delivery lifecycle states (PENDING, PROCESSING, DELIVERED, RETRY, DEAD_LETTER, SUPPRESSED); attempts, leases, provider message IDs, bounded errors, and retry scheduling belong to the later delivery-worker slice.
Unique idempotency keys prevent duplicate intents when the evaluator retries. A worker claims rows with a bounded lease and database locking (SKIP LOCKED on PostgreSQL; SQLite-safe serialized fallback for tests). Provider calls happen outside the transaction. Completion is recorded in a new transaction. Expired leases are reclaimable. Retries use bounded exponential backoff with jitter and a maximum attempt count; exhausted rows become dead-lettered for human review. Delivery is at-least-once; provider idempotency keys should be used where supported.

## Escalation evaluation
The evaluator is an internal idempotent service operation, not an HTTP request that sends messages. It selects open investigations, computes WARNING from the case's snapshotted SLA start/due/warning percentage and BREACHED from its snapshotted due time, applies the configured policy delay, resolves current active role membership and user preferences, and creates one outbox intent per eligible user/channel using the stable idempotency key. The caller owns commit. The outbox itself is the durable per-recipient trigger evidence in this slice; a separate escalation-event ledger is deferred.
The evaluator records a trigger observation once per case, trigger, and policy version. It does not repeatedly escalate on every scheduler run. Further escalation stages require explicit stage ordering and separate policy configuration; they must not be inferred.

## API and permissions (planned)
- POST /reconciliation/escalation-policies — finance approver creates a new version.
- GET /reconciliation/escalation-policies — finance reader lists policy history.
- PUT /reconciliation/notification-preferences/me — authenticated user updates their own preferences; no administrator may silently opt a user into external channels.
- GET /reconciliation/notification-preferences/me — authenticated user reads their preferences.
- GET /reconciliation/notifications/me — authenticated user sees only their own in-app notifications, with bounded cursor pagination and unread count.
- PATCH /reconciliation/notifications/me/{notification_id}/read — recipient-only, idempotent read acknowledgement; another user's IDs return 404.
- The inbox returns only notification ID, investigation ID, event type, severity, timestamps and read state. It never returns raw payload, idempotency key, policy internals, bank data, or investigation narrative.
- Worker/evaluator functions are internal service entry points, not public tenant API endpoints.
Exact route paths and permission names must be reconciled with the existing authorization contract before implementation.

## Security and governance constraints
- Never persist provider credentials in policy, preference, or outbox rows. Use the existing secret-management boundary.
- Do not include patient data, raw bank account details, statement descriptions, or full investigation summaries in notifications.
- Resolve recipients from tenant-local role membership at evaluation time; revalidate active users and preferences at dispatch time.
- Enforce tenant schema isolation for every query and worker connection.
- Record policy changes, preference changes, escalation observations, suppression, delivery, retry, and dead-letter transitions in append-only audit/event history.
- Do not let a user configure notifications for another user.
- Do not let notification preferences override policy channel restrictions.
- Avoid sending notifications for closed investigations; handle close-vs-dispatch races by rechecking status before provider invocation.
- Do not treat a queued notification as proof of delivery.

## Test requirements
- policy versioning and one-active-rule uniqueness;
- disabled policy creates no outbox intents;
- policy channel restrictions dominate user preferences;
- recipient resolution is tenant-local and excludes inactive users;
- user preference opt-out suppresses delivery;
- repeated evaluator runs produce one intent per idempotency key;
- concurrent evaluator runs do not duplicate intents;
- outbox worker lease expiry/reclaim and bounded retries;
- provider failure does not roll back investigation or escalation history;
- closed-case race suppresses pending dispatch;
- SQLite and PostgreSQL 17 migration parity;
- sandbox classification and purge behavior for outbox payloads and operational evidence;
- privacy route inventory and authorization tests.

## Delivery stages
1. **Implemented and validated separately:** schema, versioned policy APIs, self-service preference APIs, append-only configuration audit, sandbox purge handling. Only IN_APP is currently configurable; external channels are rejected.
2. **Implemented in this branch; validation pending:** an internal `evaluate_reconciliation_escalations(db, now, batch_size)` service evaluates open cases against their immutable SLA snapshots, applies the active severity/trigger policy delay, resolves active tenant-local role members, honors in-app opt-outs, and inserts minimal durable outbox intents. A unique database idempotency key prevents duplicate case/trigger/policy-version/recipient/channel intents across repeated or concurrent runs. The evaluator owns no transaction commit; its caller commits. It performs no provider calls and is not exposed as an HTTP route. Warning intents are not emitted after the case has breached. Evaluation is cursor-paginated by investigation ID (`after_case_id` / `next_after_case_id`) so large tenants can drain bounded batches without repeatedly scanning only the oldest cases. No recipients means no intent; later evaluations can discover newly assigned active role members.
3. **Implemented in this branch; validation pending:** recipient-scoped in-app inbox read API with bounded ID cursor pagination, unread count, minimal allow-listed response metadata, idempotent read acknowledgement, and 404 behavior that prevents cross-recipient ID probing. A notification is not marked delivered merely because it was listed; read state is tracked separately.
4. Delivery worker/lease/retry lifecycle remains deferred. Before any dispatch worker is enabled, it must recheck investigation state, recipient activity, current preference, and policy eligibility immediately before delivery.
5. External provider adapters only after secrets, consent/opt-out, rate limits, retry, and operational ownership are approved.

No external notification channel should be enabled by the schema-only or evaluator-only stages.