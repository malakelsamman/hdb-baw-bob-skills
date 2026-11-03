# BAW contract bundle

Use this contract bundle when a BRD describes a business scenario, roles,
human work, services, data, or a specific presentation. The bundle is a
planning and traceability layer between the BRD and `BAW_GENERATOR_SPEC`; it
does not replace the native BAW serializer or the existing generator checks.

## Why the bundle exists

A BRD usually mixes business narrative, actors, decisions, data, UI wishes,
and integration needs in prose. A single flat generator JSON makes it easy to
lose a field, miss an actor, or connect a Coach to the wrong task. The bundle
separates the decisions into five named contracts and then assembles them into
the exact graph consumed by the TWX generator.

The five files are:

1. `process_contract.json` - target scenario, sentence ledger, actors, BPMN
   nodes, gateways, flows, and source coverage.
2. `coach_contract.json` - human services, Coach instances, reusable-view
   blueprints, field ownership, layout, controls, actions, and mappings.
3. `service_contract.json` - database/API/SOAP/RPA/notification services,
   operations, schemas, endpoint status, retries, and service-node references.
4. `data_contract.json` - process variables, Business Object designs, field
   groups, ownership, mappings, and gateway decision variables.
5. `application_contract.json` - application metadata, default theme profile,
   toolkit/dependency intent, RBAC, SLA/notification requirements, assumptions,
   and validation policy.

## Contract lifecycle

1. Locate the BRD target scenario or target flow. If it is absent, record
   `MISSING` and create a clearly labelled design assumption; do not silently
   invent a detailed process.
2. Build a sentence-level ledger. Every material sentence or requirement is
   classified as one or more of: actor, activity, field, service, gateway,
   human task, Coach/view, notification, SLA, validation, or exception.
3. Create stable local IDs such as `actor.initiator`, `gateway.compliance`,
   `service.customerLookup`, `task.review`, and `view.review`. These IDs are
   contract references only; they are not BAW UUIDs.
4. Draft the five contracts and cross-reference their IDs.
5. Assemble the contracts into `BAW_GENERATOR_SPEC`, run the existing
   generator preflight, create SVG review flows, and stop for flow approval.
6. After approval, generate and structurally validate the TWX. A contract may
   remain present in the bundle while its native serialization is reported as
   `UNSUPPORTED`.

## Source status vocabulary

Use these statuses in the contracts and in the final report:

- `CONFIRMED` - stated directly in the BRD.
- `INFERRED` - a conservative interpretation supported by the BRD wording.
- `ASSUMED` - a design choice made because the BRD is silent.
- `MISSING` - required information is not supplied.
- `AMBIGUOUS` - multiple interpretations remain possible.
- `CONTRADICTORY` - the BRD contains conflicting values.
- `DESIGN_DECISION` - implementation choice made to make the workflow usable.
- `UNSUPPORTED` - the design is captured, but the current serializer cannot
  emit the native BAW artifact safely.

## Process contract minimum shape

```json
{
  "contractType": "process",
  "contractVersion": "1.0",
  "target_scenario": {
    "status": "CONFIRMED",
    "text": "...",
    "source_refs": ["BRD section 3"]
  },
  "actors": [
    {"id": "actor.requester", "name": "Requester", "kind": "human", "lane": "Requester", "participant": true},
    {"id": "actor.creationBot", "name": "Creation bot", "kind": "rpa", "lane": "Automation", "participant": true}
  ],
  "gateways": [
    {"id": "gateway.review", "name": "Review required", "type": "exclusive", "decision_variable": "reviewRequired"}
  ],
  "sentence_ledger": [
    {"id": "S-001", "text": "...", "source": "BRD p. 2", "actors": ["actor.requester"], "node_ids": ["task.capture"], "fields": ["request"], "services": [], "gateways": []}
  ],
  "processes": []
}
```

The process entries use the existing generator shape: `lanes`, `nodes`,
`flows`, and `source_coverage`. System, external, notification, and RPA work
must be represented as non-human nodes; the actor remains visible in the
actor list and lane model.

## Coach contract decisions

For every human node, identify:

- human-service ID and task purpose;
- input context and output values;
- editable versus read-only fields;
- required validation and finite-value options;
- action labels, action values, and return/rework target;
- view ID, reusable status, root binding, and nested layout;
- whether the view is editable, read-only, or a read-only variant;
- shared read-only comment-history view binding and action-to-recipient rules;
- table row schema and service/event dependencies when a table is requested.

If the BRD contains a required-fields section, treat it as authoritative and
use those fields in the Coach. Inferred fields must be marked `INFERRED` or
`ASSUMED`. Use the supported control catalog in
`BAW_REFERENCE_TWX_ANALYSIS.md`. Tables, tabs, document controls, service
tables, rich lifecycle events, and native reusable `coachView` artifacts must
remain explicit and must be marked `UNSUPPORTED` until a serializer extension
has been implemented and validated.

## Shared comment-history contract

For a process with human Coaches, add a single shared history list instead of
one comment variable per Coach. The list is append-only and is shown as a
read-only table on every human Coach; the first Coach simply shows an empty
history. A recommended data-contract shape is:

```json
{
  "comment_history": {
    "id": "bo.commentHistory",
    "name": "Comment History Entry",
    "variable_name": "commentHistory",
    "cardinality": "list",
    "native_status": "SUPPORTED",
    "fields": [
      {"name": "occurredAt", "type": "Date"},
      {"name": "fromActor", "type": "String"},
      {"name": "toActor", "type": "String"},
      {"name": "fromCoach", "type": "String"},
      {"name": "toCoach", "type": "String"},
      {"name": "action", "type": "String"},
      {"name": "comment", "type": "String"}
    ]
  }
}
```

Each Coach contract should reference the same list and declare a reusable
history view with read-only `Date`, `Action`, and `Comment` columns and approved
ordering. Keep sender, recipient, and Coach fields in the Business Object for
audit and routing even though they are hidden from the standard table. The
Coach action handling must append a new row before the process routes to the
next or previous human task. `Return` appends a row addressed to the previous
editable actor; `Submit`/`Forward`/`Escalate` appends a row addressed to the
next actor; `Close` does not create a business-history row. The sender's
current comment is a separate editable field and must be cleared after a
successful append. The recipient is derived from the process flow, never from
free text. Use a separate Return-comment variable for each independent Return
direction so the receiving read-only mapping remains unambiguous.

The list must cross both orchestration boundaries for every history-enabled
task: the parent BPD maps the process list into the CSHS, and maps the CSHS
list output back to the same process variable after the append. Declaring the
list only on the CSHS is insufficient because the updated value is discarded
when the human service ends and the next Coach receives the old list.

The generator now serializes this specific history pattern as a local native
`twClass` row object, a process-private collection variable, a read-only native
Table with nested Output Text columns, and an append script on business Coach
actions. The contract must still retain the row schema and actor/recipient
mapping because those are process-specific. Other arbitrary list Business
Objects, service-backed tables, and reusable native `coachView` artifacts
remain `UNSUPPORTED` unless their serializers are explicitly implemented and
validated against the target toolkit snapshot.

## Service contract decisions

Create a service descriptor even when the BRD does not provide a URL or API
contract. Set its endpoint status to `MISSING` or `PLACEHOLDER`, record the
required inputs and outputs, and keep the node in the reviewed flow. Do not
claim that a placeholder is connected. The final report must list every empty
service that the bank must provide before runtime testing.

## Data contract decisions

Group fields into Business Objects when they represent a reusable business
concept or cross-task context. Keep primitive process variables for simple
gateway/action values. Declare field types, list cardinality, ownership,
read-only behavior, mappings, and source status. If a native Business Object
artifact cannot be emitted by the current generator, preserve the complete
design in this contract and report it as `UNSUPPORTED` rather than flattening
it into a String.

## Application contract decisions

The default theme is the profile in `assets/enterprise-burgundy-theme.json`
unless the user explicitly selects a different visual direction. This is a
visual contract, not evidence that a source toolkit or source repository UUID can be reused.
The profile is overlaid on the complete BAW 8.6.11-compatible native source in
`assets/enterprise-burgundy-baw-8.6.11-theme.less`. The generator serializes the
result as a native `uiTheme` in a newly generated toolkit, using fresh
target-environment IDs. The process app depends on that toolkit snapshot, its
`projectDefaults/defaultTheme` points to the toolkit-owned Theme, and the
toolkit snapshot is embedded in the one outer TWX under `toolkits/`. Do not replace the complete source
with a short token list: such a Theme can import but fail LESS compilation in
Workflow Center.

Include dependencies, target BAW fingerprint, role/team intent, SLA and
notification rules, business-calendar requirements, assumptions, and the
validation policy. Unknown endpoint, team, calendar, or escalation values are
reported as `MISSING`; they are not invented.

## Assembly and validation

The assembler must validate:

- all five contract files exist and have the expected `contractType`;
- all IDs are unique within their contract;
- sentence-ledger references resolve to actors, nodes, fields, services, and
  gateways;
- each Coach references a real human node and each service references a real
  system, external, or notification node;
- all process lanes, nodes, flows, and decision variables remain compatible
  with the current generator;
- data fields and mappings use consistent names and supported primitive types;
- missing or unsupported capabilities are preserved in the report;
- the assembled `BAW_GENERATOR_SPEC` passes the existing source-coverage,
  routing, field-control, Return-contract, and TWX structural validations.

The assembler is a consistency and traceability layer. It must not silently
drop a contract section, replace a missing service with a fake endpoint, or
claim that a native BAW artifact exists when the serializer does not support
it. The generator accepts the bundle directly with
`python3 scripts/baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts`;
it writes the assembled `BAW_Process_Spec.md` and
`BAW_GENERATOR_SPEC.json` into the artifact directory before running the
existing preflight and TWX serializer.
