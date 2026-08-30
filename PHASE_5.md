# Phase 5 — Ontology diagram and data model section

One session. Independent of Phase 4B — run either order. Phase 4A must be
committed first, since this edits `eval_boards/index.html`.

The rules from `EVAL_BOARDS_KICKOFF.md` apply: execute only this phase, stop at
the checkpoint, don't commit, and if something here looks wrong, stop and say so
rather than working around it.

---

## Goal

Make the shape of the ontology visible, so a reader understands why the flagship
trace took four hops and that the agent navigated a defined graph rather than
guessing at joins.

Four pieces, in this order on the page:

1. A hand-authored inline SVG diagram of the object types and links
2. A table of all eight links with cardinality and descriptions
3. A compact table of the nine object types with row counts and columns
4. Sample rows for only the three object types in the flagship chain

**Placement:** after the flagship trace and the scorecard, adjacent to the
architecture write-up. This is supporting evidence, not the lead. Do not push
the trace down the page.

---

## Design constraints

1. **The diagram is hand-authored inline SVG, committed to the repo.** Not
   Mermaid, not a CDN library, not client-side generation. The site has no build
   step and no external script dependencies — see CLAUDE.md. Inline SVG also
   renders with JS disabled and appears in link previews.

2. **Tables are generated from the ontology**, never hand-typed. Hand-typed
   schema docs drift the moment the ontology changes.

3. **No new CSS.** Reuse the existing `.case-study` / `.stat-tile` /
   `.trace-step` / `.tag` block and the `--ink` / `--paper` / `--accent` /
   `--bord` / `--shadow` tokens. If you think you need a style that doesn't
   exist, stop and ask.

4. **Static-first**, matching Phase 4A. The diagram and link table must be
   readable with JavaScript disabled.

---

## Steps

> **1. Add descriptions to the ontology.** Add a one-sentence `description`
> field to each entry under `object_types` and each entry under `links` in
> `agent/ontology/eval_boards.yml`. Write them for a reader who doesn't know the
> domain — what the entity or relationship means in the real business, not what
> columns it has. Update the Pydantic models in `agent/ontology/schema.py` to
> accept and require the field. Confirm validation still passes.
>
> **2. Author the diagram** as inline SVG in `eval_boards/index.html`.
>
> Layout — the flagship chain runs left to right as a visible spine:
>
> ```
> WarrantyClaim --concerns--> Deck --produced_by--> ProductionBatch
>     --consumes--> MaterialLot --supplied_by--> Supplier
> ```
>
> Branching off ProductionBatch:
> - QualityInspection --inspected_by--> ProductionBatch (above the spine)
> - ProductionBatch --ran_on--> PressLine (below the spine)
> - Order --fulfilled_from--> ProductionBatch, and
>   Order --placed_by--> RetailAccount (below, to the left)
>
> All eight links must appear, with the link name labeling each arrow and arrow
> direction matching the ontology's `from`/`to`.
>
> Style: boxes with 3px borders and 6px hard shadows, Space Grotesk for node
> labels, JetBrains Mono for link names, drawn with the existing color tokens.
> Use the accent color for the five-node flagship spine only; everything else in
> `--ink` on `--paper`. That contrast is the point — it makes the diagram a
> legend for the trace above it.
>
> Give the SVG a `viewBox` and wrap it in a horizontally scrollable container
> with a sensible `min-width`, so on a narrow screen it scrolls rather than
> shrinking to unreadable. Check at 375px. Include a `<title>` and `<desc>` for
> accessibility.
>
> **3. Write a generator** at `agent/ontology/describe.py` that reads the
> ontology and `agent/data/eval_boards.duckdb` and emits
> `eval_boards/data/datamodel.json` with:
>
> - `links`: source, name, target, cardinality, description
> - `object_types`: name, description, warehouse row count, column names with
>   types
> - `samples`: 5 deterministically chosen rows for **only** WarrantyClaim,
>   MaterialLot, and ProductionBatch. Choose rows that connect to the flagship
>   story — `LOT-MAP-011` must appear in the MaterialLot sample, a batch that
>   consumed it in ProductionBatch, and a delamination claim in WarrantyClaim.
>   A reader who spots the same lot ID here that appears in the trace gets the
>   connection for free.
> - `generated_at`
>
> **4. Add two guard tests** in the existing eval/test suite:
>
> - Every object type and link in the YAML appears in `datamodel.json`.
> - Every object type name and link name in the YAML appears as text in the
>   committed SVG markup. The diagram is hand-authored, so this is what stops it
>   drifting out of sync with the ontology.
>
> **5. Render the section** in `eval_boards/index.html`, below the diagram:
>
> - A short plain-language intro: these are the entities the agent may reason
>   about and the relationships it may traverse, and it cannot reference
>   anything outside them.
> - The links table, expanded: From, Link, To, Cardinality, Description. Order
>   the rows so the flagship chain reads top to bottom in sequence, with the
>   branching links after it.
> - The object types table: name, description, row count, columns.
> - The three sample previews, collapsed by default.
> - Tables scroll horizontally on narrow screens rather than overflowing.
>
> Static fallback: the diagram, the links table, and the object types table
> render directly in the HTML. JS may add the sample rows and collapse behavior
> only.
>
> **6. Update `agent/README.md`** with how to regenerate `datamodel.json`, and
> note that the SVG is hand-maintained and guarded by a test.

**Checkpoint:** section renders at desktop and 375px, reads correctly with JS
disabled, all eight links appear in both the diagram and the table, and
LOT-MAP-011 appears in the MaterialLot preview. Report anything left out. Stop.

---

## What to check when reviewing

- **Does the spine read as a path?** Someone should be able to follow
  claim → deck → batch → lot → supplier without instruction. If the accent
  coloring doesn't make that obvious at a glance, the diagram isn't done.
- **Read your own descriptions.** Generated ones tend to restate the table name.
  Rewrite any that don't add meaning — these are the sentences that explain your
  data model to someone non-technical.
- **Length.** If the section buries the trace, cut the sample previews first.
  The diagram and link table are what earn their place.
