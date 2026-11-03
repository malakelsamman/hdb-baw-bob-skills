# BAW application-design layer

Read this reference during BRD-to-spec work when the source contains meaningful
business data, human decisions, rework, or repeated context. It adds the design
layer that makes a generated TWX recognizable to a business user; it does not
replace the native BAW/TWX invariants in `BAW_AUTOMATION_REFERENCE.md`.

## Design objective

The generated process must preserve the source's business meaning, not merely
produce an importable BPMN graph. Before choosing nodes or Coach fields, derive:

- the business concepts and data that persist across tasks;
- who creates, edits, and only reads each value;
- the context a downstream actor needs to make a decision;
- the actions, outcomes, rework paths, and business status changes;
- which activities are human, system, external, or notification work.

Do not copy roles, fields, thresholds, or objects from another use case. Examples
in this document are patterns, not names to insert into a new application.

## Generic data-model contract

The process specification may declare reusable data types at process or app
scope. A business object can be **reused from the current Process App**, **referenced
from a Toolkit**, or **created** when the current source requires a new type. It
must never be hard-coded to a sample concept such as `Benefits`.

```json
{
  "business_objects": [
    {
      "name": "RequestData",
      "mode": "create",
      "description": "Business meaning derived from the current BRD",
      "fields": [
        {"name": "title", "type": "String", "required": true},
        {"name": "amount", "type": "Decimal"},
        {"name": "items", "type": "RequestItem", "list": true}
      ]
    },
    {
      "name": "SharedCustomer",
      "mode": "existing",
      "source": "toolkit",
      "toolkit": "SharedDataToolkit"
    }
  ]
}
```

Rules:

1. Use one type for one repeated business concept; do not create near-duplicate
   objects for different tasks.
2. Keep nested objects and list cardinality explicit.
3. A process variable that uses an object must identify its object type; do not
   flatten a meaningful object into unrelated strings merely for convenience.
4. An `existing` or `toolkit` reference must include enough identity to resolve
   the object. If it cannot be resolved, mark the reference `MISSING` and stop
   before claiming that the TWX contains it.
5. If the active generator cannot safely serialize a create/reuse object into a
   native Traditional BAW artifact, preserve the design in the specification and
   report the construct as `UNSUPPORTED`; never silently emit a String variable.

## Process data and task contracts

Every persisted field must have a process-level owner and a round-trip path:

```text
process data → User Task input → Human Service/Coach
Coach → Human Service output → User Task output → process data
```

For each human task, capture in the specification:

- `purpose`: why this role receives the task;
- `inputs`: prior context required to render it;
- `outputs`: values created or changed here;
- `read_only` context fields versus editable fields;
- `required` and source-supported validation rules;
- action labels and their stored values;
- return/rework target and required reason, when present;
- assignment as a business role or safe demo placeholder.

Downstream tasks should show previously captured context as read-only and expose
only the current role's responsibility as editable. Do not make users re-enter
values already captured upstream.

## Coach design

Generate a recognizable business interaction, not a flat list of variables:

```text
Task purpose / instructions
Prior business context (read-only)
Current task data (editable)
Decision / comments (when required)
Action bar
```

Infer controls from intent where the generator supports them:

- long narrative → text area;
- numeric amount/count → Decimal/Integer;
- finite business choices → controlled select/radio;
- yes/no → Boolean control;
- prior context → read-only output;
- business object → bind the object root and its fields, not a serialized String.

Repeated context should be represented once and reused as a View or a clearly
grouped read-only section. If standalone reusable View artifacts are not enabled
by the current generator, keep the root binding and field ownership explicit in
the spec and report that limitation instead of generating duplicate, editable
copies.

## Actions and routing

An action is business behavior, not just a button label. For every multi-action
task, compile the complete chain:

```text
button → action value → CSHS output → process variable → explicit gateway comparison
```

Every outgoing branch, including the positive/Approve branch, must compare the
action variable. Keep these meanings distinct:

- Return → rework/resubmit;
- Reject → rejected outcome;
- Cancel → cancelled outcome.

Only include Save Draft/Postpone, SLA timers, attachments, extended audit
features, or notifications when the current BRD or the user explicitly requests
them. The shared append-only `commentHistory` contract is the exception: it is
required by this skill for every process with human Coaches, even when the BRD
does not explicitly request it. Each Coach shows the same read-only history
table and one separate current-comment field; business actions append and clear
the draft before routing.

## Validation and evidence

Before TWX generation, preflight must check:

- every material source step has a coverage row;
- every process variable/object type is declared and consistently used;
- task inputs/outputs and read-only/editable ownership are valid;
- controlled routing uses real variables rather than permanent `false` branches;
- object references are resolvable or explicitly marked unsupported;
- every human action has a complete output-to-route chain;
- the review SVG comes from the same graph that will become the TWX.

Report `CONFIRMED`, `INFERRED`, `ASSUMED`, `MISSING`, `AMBIGUOUS`,
`CONTRADICTORY`, `DESIGN_DECISION`, and `UNSUPPORTED` items separately. A TWX
that imports is not evidence that its Coaches, data, or routes work at runtime.
