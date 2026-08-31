---
name: data-expectation-design
description: Decide which data quality expectations are actually worth enforcing on a dataset or pipeline, then emit a precise specification an implementing agent can execute on any platform (dbt, Great Expectations, Soda, Microsoft Fabric, Palantir Foundry). Use this whenever someone mentions data quality, data validation, data tests, data contracts, freshness or volume checks, pipeline monitoring, alert fatigue, "what should we be testing", or is about to add tests to a table, model, or ingestion job — even if they haven't used the word "expectation." Also use it when someone has too many alerts and wants to cut them down, or has none and doesn't know where to start.
---

# Designing data expectations

Most data quality work fails in one of two directions. Either nothing is tested
and failures are discovered by a business user looking at a wrong number, or
every column gets a null check and a type check, the alert channel fills with
noise, and people mute it. Both end in the same place: no one trusts the
monitoring.

The scarce skill is not knowing what expectations exist. Every tool ships a
catalog of them. The scarce skill is deciding which subset is worth the
maintenance cost and the interruption cost, and that decision comes from the
decision the data supports — not from the schema.

This skill walks a user from "we should probably test this" to a concrete,
justified expectation set plus instructions an agent can implement.

## How to use this

Work through the steps in order with the user. Steps 1 through 3 are an
interview; don't skip ahead to naming expectations, because the whole point is
that the expectation set falls out of the business context. If the user pushes
to skip straight to a list, give them one, but flag which parts are guesses.

Ask questions in small batches. Three or four at a time, not fifteen.

---

## Step 1 — Anchor on the decision, not the table

Before looking at columns, establish what the data is *for*.

Ask:
- What decision or action does this data drive? Who takes it?
- How often do they act on it — continuously, weekly, quarterly?
- If the data were silently wrong for a full cycle, what would happen? Money
  moved, a customer contacted, a model retrained, a slide in a QBR?
- How would anyone notice today, and how long would that take?

The last question is the most useful one and it is the one people have not
thought about. If a wrong number would be caught by a human within an hour
because it looks obviously absurd, that dataset needs far less machinery than
one feeding an automated action nobody eyeballs.

**If nothing acts on the data, say so.** A table that exists because someone
built it two years ago and no one has queried it since does not need
expectations, it needs deprecation. Recommending that is a legitimate and
valuable outcome of this process.

## Step 2 — Enumerate failure modes that have actually happened

Ask what has broken before. Real incident history beats theory every time —
people remember their outages and those memories point straight at the
expectations worth having.

Then fill gaps using the families below. Work through them as prompts, not as a
checklist to satisfy.

| Family | What it looks like | Typical trigger |
| --- | --- | --- |
| Arrival | Load didn't run, ran partially, or landed empty | Upstream job failure, credential expiry |
| Volume | Row count drops or spikes beyond normal range | Filter change upstream, backfill, duplicate load |
| Freshness | Rows arrive on time but carry stale timestamps | Source system lag, replication delay |
| Grain | Duplicates where the key should be unique | Retry without idempotency, join fan-out |
| Schema drift | Column renamed, dropped, retyped | Upstream release, SaaS API version bump |
| Semantic drift | Values still valid but meaning changed | New enum member, unit change, currency switch, code reuse |
| Referential | Orphaned foreign keys, unmatched dimension members | Late-arriving dimensions, hard deletes upstream |
| Distribution | Values in range but wrong shape | Sensor drift, pricing change, mis-mapped source field |

Semantic drift deserves attention because it is the family that standard
tooling catches least well and that causes the most damage. A new value in a
status column passes every null and type check while quietly breaking a
downstream `CASE` statement. Ask explicitly whether upstream teams can add
categories, change units, or reuse codes without telling anyone.

## Step 3 — Score each failure mode by cost asymmetry

For each failure mode that survived Step 2, get a rough read on two things:

- **Cost of a silent failure** — the failure happens and nothing fires.
- **Cost of a false alarm** — the check fires when the data is actually fine.

These two numbers determine everything downstream: whether an expectation
blocks a pipeline, pages a person, or just lands in a weekly report; and how
tight the threshold should be.

The asymmetry matters more than the absolute magnitudes. A check guarding a
payment file should be tuned to fire on anything suspicious, because a false
alarm costs an analyst ten minutes and a miss costs real money. A check on a
noisy exploratory dataset should be tuned loose, because the failure is cheap
and the interruptions are not.

Push back if the user rates everything critical. Everything critical means
nothing is, and the resulting alert channel gets muted within a month. Ask them
to rank rather than rate: which of these would you get out of bed for?

## Step 4 — Select expectations, cheapest layer first

Choose in this order, and stop as soon as coverage is adequate. Each layer
costs more to maintain than the one above it.

### First, establish the load pattern

Do this before recommending anything. The same words — "we should check that
new rows show up daily" — describe completely different checks depending on how
the table is written, and getting this wrong produces an expectation that fires
constantly or never fires at all.

| Load pattern | What a healthy day looks like | What to measure |
| --- | --- | --- |
| Append / incremental | Row count grows; new partition or batch appears | Rows *added* per run, not total |
| Full refresh (truncate and reload) | Total row count stays in a stable band | Total row count; delta is meaningless |
| Snapshot | One new snapshot per period, prior periods immutable | New snapshot arrived; prior counts unchanged |
| SCD Type 2 | Most days add few or zero rows | Change volume, not row count — a quiet day is normal |
| Event stream / micro-batch | Continuous arrival; volume varies by hour | Rows per window, with hour-of-day context |
| Reference / dimension | Rarely changes at all | Unexpected *change* is the anomaly, not absence of change |

Two consequences worth stating explicitly to the user. On a full-refresh table,
"new rows daily" is not observable at all without comparing snapshots, so the
useful check is total count stability. On an SCD Type 2 or reference table, a
day with zero new rows is normal, and a naive freshness check will page someone
every quiet week until they mute it.

Ask which pattern applies before proposing bounds. If the user isn't sure, the
partition structure and whether the job uses `MERGE`, `INSERT`, or
`CREATE OR REPLACE` will usually tell you.

### Table-level

A handful of checks that catch a large share of real incidents. Almost every
dataset should have these, and if the user is starting from zero this layer
alone is a big win that can often ship the same day.

**Did it run at all.** The cheapest check and the one that catches the most
common real incident. Distinct from row count: a job can complete successfully
and write nothing.

**Zero rows, as its own check.** Do not treat zero as the bottom of the row
count range. On most tables an empty load means the job failed, a credential
expired, or a source filter matched nothing — a different failure with a
different owner and usually a higher severity than "fewer rows than usual."
Fold it into the range check and it arrives with the wrong urgency. Keep it
separate.

**Row count within an expected range**, measured according to the load pattern
above. See Step 5 for how to shape the bounds.

**Freshness, on both clocks.** These are two different checks and users
routinely implement only the first:

- *Load time* — when the row landed in the table. Catches the pipeline not
  running.
- *Event time* — the business timestamp carried on the row. Catches the
  pipeline running perfectly on stale upstream data.

A replication lag or a paused source connector produces a punctual load full of
three-day-old events. Only the event-time check sees it. Where the two can
diverge, recommend both and say why; where the source writes event time at
ingestion, they're the same check and one is enough.

**Uniqueness on the declared grain.** Requires the user to state the grain,
which is worth doing regardless — teams are often surprised to find they
disagree about it.

### Column-level, restricted to columns that feed the decision

This is the discipline that separates a useful expectation set from a noisy
one. Only columns that reach the decision identified in Step 1 earn a check.
Nullability and accepted-value sets on those columns; ranges where a physical
or business bound genuinely exists.

Resist testing columns because they are there. If a column is unused, its
quality is not a monitoring problem.

### Cross-table

Referential integrity, reconciliation against a source of truth, row count
agreement across a join. Expensive, so reserve these for the relationships
where a break is both plausible and costly.

### Distributional

Mean, null rate, or category mix moving beyond a tolerance. Highest
maintenance and highest false-alarm rate. Add only where Step 3 showed a
genuinely expensive silent failure that the cheaper layers cannot catch.

Record what you *rejected* and why, alongside what you selected. When someone
asks in six months why a column isn't tested, the answer should exist in
writing. This record is also what makes the expectation set reviewable.

## Step 5 — Set thresholds from evidence

Derive thresholds from history wherever history exists. Query the last several
months of row counts, load times, and null rates and set bounds from observed
behavior rather than intuition. If the user can run queries, propose the
specific SQL for this.

### Choose the shape of the bound, not just the number

The shape matters more than the value, and this is where most row count checks
go wrong.

**Static absolute bounds** (between 10,000 and 50,000 rows) are simple and
readable, and they rot. A business growing 5% a month walks out of its own
bounds within a year. Someone raises the ceiling, then raises it again, then
stops trusting the check. Use static bounds only where a genuine hard limit
exists — a fixed roster, a bounded reference set, a physical constraint.

**Trailing relative bounds** (within 30% of the median of the last 30 comparable
runs) absorb growth without maintenance. This should be the default for volume
on any table whose size tracks the business.

**Day-of-week matched trailing bounds** compare Monday to recent Mondays. Use
these whenever the data has a weekly rhythm, which most transactional data does.
A weekday/weekend volume split is the single most common cause of a spurious row
count alert, and matching on day of week eliminates it without loosening the
check.

**Ratio checks against a related table** are often sharper than any absolute
bound — order lines per order, sessions per user, child rows per parent. The
ratio stays stable while both sides grow, so it catches a partial load that a
volume check on either table alone would miss.

Ask about seasonality, month-end and quarter-end spikes, holiday calendars, and
backfills before fixing any bound. Back
