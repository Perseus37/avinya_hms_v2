# Reconciliation SLA clock controls

## Scope

The reconciliation SLA clock is attached to each persisted investigation. Its target is captured from the effective SLA policy when the investigation is created, or when its severity changes. Publishing a new policy does not rewrite existing investigation targets.

## Clock calculation

- The clock starts at `first_detected_at`.
- The configured `sla_target_hours` is the active-time target.
- `sla_paused_seconds` accumulates completed, authorized pauses.
- `sla_paused_at` marks an active pause. While paused, the clock does not accrue active time.
- The clock stops at `resolved_at` for resolved or dismissed investigations.
- Reopening an investigation continues the same clock and preserves its accumulated pause duration and any recorded breach.
- The first breach instant is calculated from the clock origin, target, and completed pause duration. It is returned as `sla_breached_at`; pause/resume/closure transitions persist it when it has already occurred.

The queue exposes both wall-clock case age (`age_hours`) and active SLA elapsed time (`sla_elapsed_hours`). These are intentionally distinct.

## Pause and resume governance

Only users with `finance:sla:manage` can pause or resume an investigation SLA clock.

- Pause: `POST /api/procurement/reconciliation/exceptions/{id}/sla/pause`
- Resume: `POST /api/procurement/reconciliation/exceptions/{id}/sla/resume`

Both operations require a reason between 10 and 2,000 characters. The reason, actor, timestamp, target, and clock values are recorded in the append-only investigation event history. Repeated pause/resume operations without a state transition return a conflict.

When an investigation reaches a terminal state while paused, the pause is finalized automatically at the resolution timestamp and an `SLA_AUTO_RESUMED` audit event is recorded. This prevents a terminal investigation from retaining a running pause interval.

## Read models

The reconciliation exception queue reports:

- `sla_elapsed_hours` and `sla_remaining_hours`
- `sla_paused`, `sla_paused_at`, and `sla_paused_seconds`
- `sla_due_at` and `sla_breached_at`
- `sla_overdue`, based on active SLA time rather than wall-clock age

The queue summary and finance dashboard also expose paused-investigation counts. Assignment workload overdue calculations use the same clock helper so that dashboard, queue, and workload rankings do not disagree.

## Audit and isolation

Clock state is stored on the reconciliation exception in the tenant's active database schema. State changes are appended to the existing immutable reconciliation exception event log. The API uses the existing tenant database context and row-level update locking; no cross-tenant lookup is introduced.

## Operational limitations

Breach state and breach time are calculated on read from the stored clock origin, target, and pause history. This phase does not introduce a background scheduler, automatic escalation, or notification delivery. Those controls belong to the later escalation-governance workstream.
