# IBM BAW Automation Reference
## Any BRD → Five Contracts → Review SVG → Traditional BAW TWX

This is a required reference for `../SKILL.md`; it is not a standalone skill
entrypoint. Bob must read `SKILL.md` first and must not use this file to bypass
the five-contract workflow.

```text
Any BRD
   ↓
five JSON contracts in BAW_Process_Flows/contracts/
   ↓
assembled BAW_Process_Spec.md + BAW_GENERATOR_SPEC.json
   ↓
automatic process-review SVG(s)
   ↓
user reviews/fixes process logic
   ↓
baw_twx_generator.py
   ↓
new Traditional IBM BAW Process App .twx
```

No sample TWX is required. Do not create use-case-specific generator versions.

For persistent business data, generic Business Object reuse/create decisions,
field ownership, Coach context, and relatable task interactions, also read
[BAW_APPLICATION_DESIGN_GUIDE.md](BAW_APPLICATION_DESIGN_GUIDE.md).

# Artifact folder contract

Every run has one artifact root: `BAW_Process_Flows/`. Create the five source
contracts in `BAW_Process_Flows/contracts/`; the assembler creates the generated
specification as `BAW_Process_Flows/BAW_Process_Spec.md` and the machine-readable
specification as `BAW_Process_Flows/BAW_GENERATOR_SPEC.json`.
All SVGs, the TWX, validation reports, and any deployment/runtime handoff
artifacts must be written inside the same folder. Do not leave generated TWX,
SVG, report, or log copies beside the artifact folder. The generator also
accepts `--artifact-dir` when a different single root is explicitly required.

# 1. Two-stage workflow

## Stage 1 — BRD → five contracts + assembled MD + SVG

Create `process_contract.json`, `coach_contract.json`,
`service_contract.json`, `data_contract.json`, and
`application_contract.json` under `BAW_Process_Flows/contracts/`, then run:

```bash
python3 baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --check-spec
```

This must:
- validate the process specification;
- validate complete BRD source coverage;
- generate one SVG review diagram per BPD under `BAW_Process_Flows/`;
- create no TWX.

The SVG is generated directly from the exact `BAW_GENERATOR_SPEC` graph that the TWX builder consumes. There is no separate Mermaid graph to drift from the implementation.

Return the artifact folder containing the specification, generated `.svg`
file(s), and preflight result.

Do not generate a TWX in Stage 1.

## Stage 2 — approved contract-assembled flow → TWX

Only after the process flow is accepted, run:

```bash
python3 baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --output BAW_Process_Flows/<app>.twx
```

The generator re-runs preflight, refreshes the SVG(s), then creates and
validates the TWX inside `BAW_Process_Flows/`.


# 1A. Deployment is out of scope

This skill stops at a validated `.twx`. The user imports it in Workflow Center. For server-side installation use `baw-deployment-manager` or `version-lifecycle-manager`.

# 2. Token/context efficiency

- Read this skill once.
- Read the BRD once, including tables and diagrams.
- Re-read only a specific section needed to resolve a real ambiguity.
- Keep the MD concise.
- Do not copy large product/reference catalogs unless they affect routing or UI.
- Define each rule once.
- Do not duplicate the process in several prose formats.
- `BAW_GENERATOR_SPEC` is the machine contract.
- The generated SVG is the human flow-review artifact.

# 3. Evidence discipline

Use where useful:
- `CONFIRMED`
- `INFERRED`
- `ASSUMED`
- `MISSING`
- `AMBIGUOUS`
- `CONTRADICTORY`
- `DESIGN_DECISION`

Never present an assumption as confirmed.

Do not invent:
- REST/SOAP,
- endpoints/authentication,
- credentials,
- production BAW teams,
- retry counts,
- business calendars,
- real integration availability.

# 4. Source precedence

When explicit source sections conflict, provisionally prefer:
1. Scope / Out-of-Scope
2. clear detailed use-case steps
3. clearly readable process diagram
4. business rules
5. field/integration/RBAC tables
6. purpose/overview

Do not trust garbled PDF diagram extraction over clear prose.

Record unresolved contradictions/ambiguities, choose a provisional interpretation, and continue.

# 5. Continue with assumptions

Do not stop for normal missing information.

For material unresolved items record:
- issue,
- assumption,
- reason,
- impact,
- confirmation question.

When a field's allowed values are not stated in the BRD, do not block the
planning stage. Classify the field first:
- finite business concept → infer a conservative candidate domain, mark it
  `ASSUMED`, explain the basis, and ask the user to confirm or revise it;
- open-ended narrative/description/reason → keep it as free text or Text Area;
- numeric/date/Boolean concept → use the corresponding typed control.

Every inferred domain must be listed in the final `Assumptions /
Contradictions / Questions` section with the field name, proposed values,
reason, confidence/impact, and confirmation question. The generated SVG and
TWX may proceed with `READY_WITH_ASSUMPTIONS`, but Bob must show these
assumptions before asking for flow approval and must never present inferred
values as confirmed source requirements.

Default return assumption: when a process contains a human review or committee
handoff and the BRD is silent about rework, add an explicit assumption that
Return is enabled. State the receiving editable task, the preserved data, and
the Return comment behavior, then ask the user to confirm or opt out. Do not
silently omit the Return path.

Readiness:
- `READY`
- `READY_WITH_ASSUMPTIONS`
- `BLOCKED` only if a meaningful process cannot be derived.

# 6. Preserve business use cases and variant rules

Identify distinct business use cases first.

Combining variants is a `DESIGN_DECISION`.

Never broaden a rule:
- CD-only rule ≠ TD rule;
- creation rule ≠ breaking rule;
- corporate rule ≠ retail rule.

If a variant-specific rule changes routing, use a gateway/branch or separate BPD.

# 7. Build a source-step ledger first

For every process enumerate each material step in source order:
- start/initiation,
- human action,
- system action,
- independent validation,
- decision/gateway,
- approval/review,
- external/manual activity,
- notification,
- completed/rejected/blocked/cancelled outcome.

This becomes `source_coverage`.

## 7A. Field-level requirements extraction (mandatory)

The planning phase must inspect the BRD at field level, not only at activity
level. For every step, appendix, checklist, form, table, and grouped heading:

1. record the source anchor (page/heading/appendix/table or image region);
2. extract every named input, sub-field, criterion, attachment/evidence item,
   and expected output;
3. preserve the source grouping (for example, a Benefits group containing
   Quality, Cost, Time, and Revenue items) instead of flattening or omitting it;
4. assign each field to its owning actor and Coach;
5. record type, requiredness, editable/read-only status, validation, control,
   and the process variable or Business Object path that carries it; and
6. trace every field to the next task, gateway, service, or outcome that reads
   or produces it.

Each source field should appear once in the appropriate Coach section and bind
to one canonical process path. Do not duplicate an attachment/checklist field
inside a comments section, create two controls with the same label for one
value, or move a field into a generic section merely because the generator has
space there.

Before generating an SVG, produce a field/Coach coverage table in the
specification. A process is not ready when all activities are represented but a
BRD form field or grouped business concept is missing. If the source mentions a
Business Object or named group, declare it in the generic data model. If the
current generator cannot serialize the native object, preserve the object and
field paths in the specification and report `UNSUPPORTED`; never silently drop
the fields or replace the object with unrelated primitive variables.

Do not infer a field solely from a generic process pattern. Source evidence takes
precedence over convenience.

## 7B. Exact source-field and type fidelity

The generated specification must preserve the source meaning, not merely the
approximate workflow shape:

- Every named BRD field must appear with its source meaning and a traceable
  Coach/process-variable binding. Do not substitute `Expected Completion Date`
  for a source field called `Expected Timelines`, or omit `Strategic Relevance`
  because a similar field already exists; record an explicit mapping or model
  both fields.
- Use `Decimal` for monetary amounts and `Integer` (or `Decimal` when the
  source allows fractions) for numeric scores, counts, or person-days. Use
  `Date` for calendar dates and a native date control; never coerce these to
  `String`.
- A finite value may be an inferred dropdown when the source omits its domain,
  but the proposed values, rationale, confidence, and confirmation question
  must be listed under assumptions. Open-ended descriptions, evidence, and
  comments remain text areas.
- Before the `BAW_GENERATOR_SPEC` is approved, create a field-control decision
  table for every visible Coach field and every user-editable process variable:
  `name`, primitive type, value domain (`finite`, `open`, `Boolean`, `numeric`,
  or `Date`), chosen control, and options/assumption. A finite non-Boolean
  domain is never allowed to remain an unqualified String: declare `options`
  and render a native Single Select/dropdown. If the BRD omits allowed values,
  infer conservative candidates, mark the row `ASSUMED`, include the values and
  rationale in `Assumptions / Contradictions / Questions`, and ask for user
  confirmation. This reasoning is required for every variable, not only the
  variables referenced by gateways. The generator preflight must fail when a
  visible field has no domain/control decision or when a finite field has no
  options.
- Preserve named groups such as Benefits as a grouped Coach section and,
  where the source has sub-items, retain each sub-item and its control. Do not
  flatten a group into an unrelated generic field.
- Attachments/evidence must be handled only when the BRD or user requests them.
  Use a native attachment artifact when supported; otherwise label a reference
  explicitly as a reference and report the limitation. Never model a binary
  attachment as an ordinary String while implying that the attachment exists.

# 8. No silent compression

Do not merge source steps when:
- actor changes;
- human/system boundary changes;
- an independent business check exists;
- the check has its own failure outcome;
- a gateway exists;
- notification is explicit;
- an external activity appears in sequence;
- BRD explicitly lists the steps separately.

You may combine multiple fields into one Coach when one user enters them in one interaction and no system/gateway occurs between them.

You may combine automated checks only when they occur at the same point, have the same system boundary, and none has an independent outcome.

# 9. Conditional language becomes explicit logic

Source wording such as:
- if / else / when / only if,
- cannot continue if,
- stop when,
- route to X when,
- approve / return / reject,
- yes / no

must become an explicit `gateway`.

Every exclusive gateway needs at least two outgoing branches.

# 10. Preserve temporal order

Do not move business activities for implementation convenience.

Examples:
- execute → send SMS;
- after transaction → threshold check → conditional email;
- validation before approval stays before approval.

# 11. Rework / Reject / Cancel

Keep distinct:
- RETURN → rework
- REJECT → rejected end
- CANCEL → cancelled end

Do not add Cancel or Reject unless the BRD or user requires them. The first
human Coach has no previous editable actor, so it must not expose `Return`; it
may have Submit and, only when requested, Cancel. For later human
review/committee handoffs, unless the user explicitly opts out, default the
planning assumption to include a `Return`/rework path. Record this as
`ASSUMED`, explain the chosen receiving actor/task, and ask the user whether to
remove it. A Return-capable task uses a visible Coach Return action that writes
the action output and a direct conditional sequence flow to the previous
editable human task. Do not create a separate gateway solely to decide whether
the user clicked Return. An independent business gateway after Submit may
remain and must evaluate its own business variable.

Every generated Coach also has a `Close` button configured in its Coach Flow as
`End the human service`. Close is a UI affordance, not a business action: it
must not be added to the process decision variable, must not create a gateway,
and must not be confused with Return, Reject, or Cancel. Business buttons such
as Submit and Return still use their configured next-step sequence flows.

If source only says return to Maker/user, provisionally return to the earliest
relevant editable task with all source-owned values preserved and editable, and
mark `ASSUMED`. On that return target, every displayed field must be populated
from the existing process data: request fields remain editable, reviewer or
audit context is read-only, and the return comment is read-only. No field may
reappear empty merely because the task was revisited.

# 12. Supported generic nodes

Stable support:
- `start`
- `end`
- `human`
- `system`
- `gateway` (exclusive)
- `external`
- `notification`

Use `external` when a business-sequence activity is outside BAW but must stay visible.

# 13. Lanes / swimlanes

Create lanes for meaningful actors/systems.

- every declared human lane must contain a human task;
- human tasks cannot be in a system lane;
- system lane contains automation/technical decisions/notifications where system-owned.
- a gateway that evaluates a value entered by a human Coach should normally be
  placed in that decision-maker's lane for visual continuity; do not move every
  human decision into a generic System lane;
- create a System lane only when the BRD contains actual automated work.
- Keep the prose lane table and every process JSON `lanes` array synchronized.
  If the source names an actor that is represented only as an external handoff,
  either declare that lane explicitly or record the actor-to-handoff mapping in
  the specification; never silently place the work in an unrelated human lane.
- Every lane used by a node must be declared, and every declared human lane
  must have an intentional role. A lane-count mismatch is a planning error,
  not a harmless presentation difference.

Generic demo assignment:
- human lane → All Users placeholder;
- system lane → System team.

# 14. Human tasks / Coaches

Coach reading order is contractual:

```text
Task purpose / instructions
Prior business context (read-only)
Current task data (editable)
Comments / evidence (when required)
Decision-support fields (last)
Action bar (Submit/Return/etc.)
```

Read-only context comes first, write fields come next, decision-support
variables come immediately before the buttons, and the action bar is last. Do
not place decision fields above the data they evaluate.

Each human node defines:
- stable id,
- name,
- lane,
- fields,
- actions.

Supported field types:
- String
- Integer
- Decimal
- Boolean
- Date

The generator automatically produces presentable native UI Toolkit Coaches:
- titled sections/cards;
- responsive two-column desktop layout;
- single-column small-screen layout;
- labels and required indicators;
- read-only Output Text;
- long comments/reasons/notes as Text Area;
- action bar;
- primary non-destructive action;
- secondary Cancel/Reject/Return;
- multiple-click protection.

For finite business choices, add an `options` list to the field and keep each
stored value identical to the corresponding gateway branch `value`. The
generator emits a native UI Toolkit Single Select with a static NameValuePair
list. Boolean fields stay native Checkboxes and are grouped into a Yes/No
section; finite non-Boolean choices are grouped inside Request Details with the
other editable request fields. Long narratives remain Text Areas, and action buttons use visually distinct primary,
secondary, and destructive styles.

Apply this control-selection rule to all finite business fields, not only fields
directly used by a gateway. If the BRD defines a finite domain or a decision-
support scale, use a dropdown/Single Select with the exact source values. If
the domain is absent but the concept is naturally finite, infer conservative
candidate values, use the dropdown, and record the inference as an `ASSUMED`
item for user confirmation. Do not force dropdowns onto open-ended descriptions,
comments, or narratives. Use Boolean controls for explicit Yes/No items,
numeric controls for numeric scores/amounts, Date controls for dates, and Text
Areas for narrative evidence.

The field-control decision should be explicit in the generator JSON, for example:

```json
{
  "name": "urgency",
  "type": "String",
  "value_domain": "finite",
  "control": "single_select",
  "options": [
    {"value": "High", "label": "High"},
    {"value": "Medium", "label": "Medium"},
    {"value": "Low", "label": "Low"}
  ]
}
```

For an open narrative, use `"value_domain": "open"` and
`"control": "text_area"` with no options. The same decision must be present
on the process variable or inherited consistently by every Coach field that
binds it; a visible field without this decision is a preflight error.

### Return/rework two-way contract

When a reviewer can send work back, the human task must declare an explicit
action contract:

```json
{
  "actions": ["Submit", "Return"],
  "decision_output": "committeeDecision",
  "outputs": ["committeeDecision", "returnComment"],
  "return_comment": "returnComment"
}
```

The Return button writes a required Text Area comment, and its direct sequence
flow must route to the previous relevant editable task. That receiving task
maps the return-comment variable as read-only context at the top of its Coach, so
the previous actor sees why the work was returned before editing it. Preserve
all other process data across the loop. The receiving task must explicitly
declare every displayed field in its `inputs` and every editable returned field
in its `outputs`, so the BAW input/output mappings repopulate the Coach rather
than opening an empty form. A Return button without this direct rework flow,
complete field mappings, and read-only comment context is incomplete and must
fail preflight. The first human Coach must fail preflight if it declares a
Return action.

Use a distinct editable return-comment variable for each independent Return
direction. A Coach that receives a prior comment read-only and also sends work
back must not reuse that same variable as its editable sender field; name the
two variables by direction (for example `returnCommentToRequester` and
`returnCommentToAssessment`).

In the Coach editor this is the same button-level configuration used for
Submit: select the Return button, open its Next step/Coach flow settings, and
choose the previous Coach/task as the target. The process graph must serialize
that as a direct outgoing sequence flow from the human task; do not insert an
intermediate action gateway merely to remember which button was clicked.


# Generator implementation facts (not process templates)

The reusable generator currently targets Traditional BAW 8.6.11 with UI Toolkit
8.6.0.0. Its native widget serialization is:

- Single Select widget UUID `64.fd4da558-40d8-47be-92ca-c305708dc7b7` for finite
  non-Boolean choices, with a static `NameValuePair` list where `name` is the
  stored value and `value` is the display label.
- Checkbox widget UUID `64.fffd1628-baee-44e8-b7ca-5ae48644b0be` for Boolean
  fields.

These are implementation facts verified from toolkit metadata. They are not
process templates and must never be used to copy a Business Object, lane,
gateway, field, or other business concept from a different TWX. If the target
BAW/UI Toolkit version changes, verify the widget identifiers and list shape in
that environment before modifying the generator.

# 14A. Process-level variables and human-task data mapping

Coach fields must not exist only inside the generated human service.

For every process, Bob and the generator must maintain a shared process-data model.

Preferred explicit contract:

```json
"variables": [
  {"name": "customerCIF", "type": "String", "scope": "private"},
  {"name": "amount", "type": "Decimal", "scope": "private"},
  {"name": "managerDecision", "type": "String", "scope": "private"}
]
```

Supported scopes:
- `private`
- `input`
- `output`
- `input_output`

A human node may explicitly declare which process variables it reads/writes:

```json
{
  "id": "manager_review",
  "type": "human",
  "name": "Manager Review",
  "lane": "Manager",
  "inputs": ["customerCIF", "amount"],
  "outputs": ["managerDecision"],
  "fields": [...]
}
```

If `variables` is omitted, the generator remains backward compatible and derives
process variables from human-task fields.

If `inputs` / `outputs` are omitted:
- all Coach fields are mapped into the task;
- editable fields are mapped back to the process;
- read-only fields are input-only.

The generator must:
1. declare the shared variables on the main BPD/process;
2. declare matching CSHS inputs/outputs;
3. generate explicit input data mappings from process → human service;
4. generate explicit output data mappings from human service → process;
5. keep field types consistent across every task that uses the same variable;
6. fail preflight on conflicting types or unknown mapping names.

This allows data entered by one Coach to persist at process scope and be reused by
later Coaches, gateways, and services.


# 14B. Action buttons must write decision outputs

A Coach action button does not automatically populate a process decision variable.
For multi-action human tasks such as Approve / Return / Reject, each generated
button must route through a small server-side script before the CSHS End event:

```text
Approve → checkerDecision = "Approve" → End
Return  → checkerDecision = "Return"  → End
Reject  → checkerDecision = "Reject"  → End
```

The CSHS output mapping then persists that value to the BPD private variable.
The BPD may use that output directly in conditional sequence flows, especially
for Return → previous editable task. A following independent business gateway
must evaluate its own variable; do not insert an action gateway merely to store
the Return choice.

Preferred optional node contract:

```json
"decision_output": "checkerDecision"
```

For backward compatibility, the generator may infer it when a multi-action task
has exactly one editable mapped output named `decision` or ending in `Decision`.
If the button text differs from the gateway value, use:

```json
"action_values": {"Return for Rework": "Return"}
```

When Return is a valid business action, model it explicitly with a required
reason/comment and an outgoing rework flow to the previous relevant editable
task. Preserve the process data and distinguish Return from Reject and Cancel.

# 24E. BPD round-trip editability

Generated BPDs must remain editable after import. Adding a new process variable
in Process Designer must not cause the BPD auto-save transformer to enter the
inline-user-task conversion path.

For standalone User Tasks:
- keep `activityType = UserTask`;
- `calledElement` references the separately packaged CSHS;
- do not inject synthetic `globalUserTask` roots into BPD BPMN2 or JSON;
- do not emit `mimeType=inlineUserTask` BPD dependency metadata;
- keep BPD `dependencySummary` null, matching IBM-exported standalone-UserTask BPDs.

# 14C. Direct human-task branching

For a human task with multiple direct outgoing flows (for example Check/Cancel),
never generate literal `false` conditions.

Do not create this gateway pattern for a human task that has only one forward
action. Connect the task directly to the next node. “Submit”, “Proceed”, or
“Confirm” is not by itself a business decision and must not create a synthetic
`Submitted?`, `Assessment Submitted?`, or `Prioritization Confirmed?` gateway.

The generator must:
- infer or use a hidden decision output such as `makerSubmissionDecision`;
- set it from the clicked Coach button;
- map it back to the BPD;
- generate real branch expressions such as
  `tw.local.makerSubmissionDecision == "Check"` and
  `tw.local.makerSubmissionDecision == "Cancel"`.

The decision variable does not need to be visible on the Coach.

CSHS `inputSet` / `outputSet` must reference the declared input/output parameters
so entered values such as `customerCIF` round-trip to the parent process.

# 14E. Generic human-action contract

Any human task with more than one action is compiled as an explicit action contract.

The generator must:
1. resolve one hidden process action variable;
2. create a hidden CSHS parameter for it;
3. make each Coach button assign its action value before End;
4. expose the action variable as a CSHS output;
5. map it back to the BPD;
6. generate direct branch or downstream gateway expressions from it;
7. fail preflight if any link is missing.

This applies generically to Check/Cancel, Approve/Return/Reject, Save/Submit,
Yes/No, Accept/Decline, Retry/Abort, and similar patterns.

Every outgoing branch of the decision gateway must serialize an explicit
comparison against the action variable, including the positive/Approve branch.
Do not make Approve an unconditional or `demo_default` flow. An unconditional
Approve branch can be selected before Return or Reject and incorrectly complete
the process.

Normal Coach fields must also round-trip through declared CSHS input/output sets
so values such as customerCIF persist into process variables.


# 14G. Target-environment verified native CSHS action output

A working Human Service exported from the target BAW environment proves the
native runtime representation for button-driven actions.

For a decision/action variable:
- create a native CSHS `processParameter`;
- `parameterType=2` means Output;
- keep the action variable output-only unless it is genuinely required as input;
- use the same ID in the CSHS `dataOutput`;
- route each Coach button event to a client-side `scriptTask`;
- use `scriptFormat="text/x-javascript"`;
- assign `tw.local.<decision> = "<Action>";`;
- route the script to End;
- map the Human Service output back to the BPD private variable.

The working export keeps CSHS `inputSet` and `outputSet` present but empty.
Generation should match that instead of adding invented refs.

A JSON-only output is insufficient; the native output `processParameter` is
required for the CSHS runtime symbol table.


# 14H. Target-environment verified BPD User Task output mapping

A working parent BPD exported from the target BAW environment proves the
required Human Service output handoff.

For output `X`, generate:
- `sourceRef` = the CSHS native output parameter ID
- `mappingMode = simple`
- `from = tw.outputs.X`
- `to = tw.local.X`

The assignment must include both `from` and `to`. The target export does not add
a synthetic `ioSpecification` to the standalone User Task `callActivity`.

Do not use the older output-assignment shape that contains only `to`; it may
look mapped in Designer but fail to copy the Human Service value into the parent
BPD at runtime on the current target environment.


# 14I. Native BusinessProcessDiagram output mapping

Traditional BAW keeps synchronized BPMN2, JSON, and native
`BusinessProcessDiagram` representations.

For Human Service outputs, the current target BAW environment requires the
native mapping shape exported by IBM itself:

```xml
<outputActivityParameterMapping>
  <mappingMode>basic</mappingMode>
  <name>makerAction</name>
  <classId>.../12.<type-id></classId>
  <value>tw.local.makerAction</value>
  <sourcePath>tw.outputs.makerAction</sourcePath>
  <targetPath>tw.local.makerAction</targetPath>
  <parameterId>2055.<CSHS-output-id></parameterId>
</outputActivityParameterMapping>
```

Do not generate the older native form containing only `expression` and
`activityParameterId`. A BPMN2/JSON mapping can look correct in Designer while
the native runtime mapping still fails to copy the value.


# 14J. Target-environment verified BPD User Task input mapping

A BAW-exported process from the target environment proves that each native
Human Service input mapping must use this `BusinessProcessDiagram` shape:

```xml
<inputActivityParameterMapping>
  <name>customerCIF</name>
  <classId>.../12.&lt;type-id&gt;</classId>
  <input>true</input>
  <value>tw.local.customerCIF</value>
  <parameterId>2055.&lt;CSHS-input-id&gt;</parameterId>
</inputActivityParameterMapping>
```

Do not emit the obsolete two-field form containing `expression` and
`activityParameterId`. It can survive TWX import while Process Designer reports
that the Human Service parameter has no input mapping.


# 15. Integrations / external systems

Capture business-level integration:
- target/source system,
- purpose,
- business inputs/outputs,
- point in process.

Do not invent technical transport.

Generic runnable demo behavior:
- system/external/notification nodes use the generated auto-completing native demo service;
- this is a placeholder, not a real integration.

# 16. External-system boundary

Only mark a step confirmed external when the BRD explicitly says it is outside BPM/BAW/manual/external.

“In T24”, “using SAP”, or “using ERP” alone does not prove whether it is a BAW service call or external user activity. Mark boundary `AMBIGUOUS`, choose a provisional assumption, and continue.

# 17. Gateways / demo routing

Every exclusive gateway:
- at least two outgoing flows;
- uses a real decision variable and explicit branch values when a human or
  business decision exists;
- may use `"demo_default": true` only for a generated service-like placeholder
  whose result is not available yet.

The demo default is not a confirmed business outcome.


# 17A. Real variable-driven gateway routing

Gateways should use process variables, not literal `condition:false`, whenever a
real decision/result exists.

Preferred:

```json
{"id":"gw_data_valid","type":"gateway","name":"Data Valid?","lane":"System","decision_variable":"dataValid"}
```

```json
{"from":"gw_data_valid","to":"continue","label":"Valid","value":true},
{"from":"gw_data_valid","to":"rejected","label":"Invalid","value":false}
```

For string decisions:

```json
{"from":"gw_checker","to":"approved","label":"Approve","value":"Approve"},
{"from":"gw_checker","to":"rework","label":"Return","value":"Return"},
{"from":"gw_checker","to":"rejected","label":"Reject","value":"Reject"}
```

The generator creates BAW expressions such as:

`tw.local.dataValid == false`

`tw.local.checkerDecision == "Return"`

A `demo_default` may remain only as a temporary fallback before a real external
service populates its result variable.

For human decisions, every route is conditional. Process Designer may display
one row as “Default flow” in the editor, but the generated expressions remain
the source of truth; never use a default route to bypass a required choice.


# 17B. Runnable placeholder-service gateway values

Generated `system`, `external`, and `notification` activities are demo
placeholders until the real integration contract is supplied. They must not
invent a Temenos/T24 endpoint, request schema, response schema, or production
input/output mapping.

However, a no-op placeholder must also not accidentally terminate or misroute
the demo simply because a Boolean process variable defaults to `false`.

Therefore, for a gateway immediately driven by a generated service-like
placeholder:

1. keep the real variable-driven gateway expression;
2. identify the outgoing flow marked `demo_default`;
3. derive that branch's expected value;
4. initialize the corresponding process-private variable to that value when the
   BRD/spec did not provide an explicit default;
5. keep the service itself as a no-op placeholder with no fake external API
   mapping.

Example:

```text
Validate CIF (demo placeholder)
        ↓
CIF Active?
├── Inactive: tw.local.cifActive == false
└── Active: demo_default, value=true
```

Generated demo initialization:

```text
cifActive = true
```

The placeholder does nothing, so the gateway follows the reviewed Active demo
path. When the real Temenos service is implemented, its output mapping replaces
the demo initialization behavior.

Apply this only to service-driven gateways. Do not force defaults for
human-decision gateways such as Manager Approve/Return/Reject or Checker
Approve/Return/Reject.

Preflight must print the inferred demo values so the user can see exactly what
is being mocked.


# 18. Notifications

Keep separate business notifications as separate nodes.

Conditional notification must remain conditional:
transaction/event → gateway → notification / skip.

Do not broaden variant-specific notification rules.

# 19. SLA / RBAC / dates

Preserve source wording.

Do not silently convert:
- role SLA → per-task SLA;
- six calendar months → 180 days.

Unknown business calendar/team/escalation details do not block initial demo generation.

# 20. Mandatory source_coverage

Every process in `BAW_GENERATOR_SPEC` requires `source_coverage`.

Each represented item contains:
- `id`
- `order`
- `activity`
- `source`
- `node_ids`
- `disposition`

Recommended `kind` values:
- start
- human
- system
- decision
- external
- notification
- outcome

Rules:
- unique coverage IDs;
- contiguous order 1..N;
- every material BRD step accounted for;
- every represented source row references existing node(s);
- every generated process node must be traceable;
- implementation-only gateways, action variables, and end events must map to
  the source human decision row that requires them; never invent new
  `DESIGN_DECISION` coverage rows just to satisfy the validator;
- `excluded` requires a source-supported reason;
- several source sub-steps may map to the same Coach/node;
- same-node mappings do not require self-loops.
- Make the coverage count unambiguous. If the document says `N/N`, the
  denominator must use the same population as the ledger. Either count only
  material business steps and state that structural start/end rows are
  separate, or count all ledger rows including start and outcomes. Never claim
  `8/8` when the ledger contains nine counted rows.

# 21. BAW_Process_Spec.md structure

Keep it short:

1. Document Control
2. Scope / Use Cases
3. Actors / Lanes
4. Assumptions / Contradictions / Questions
5. Readiness / Coverage
6. `BAW_GENERATOR_SPEC`

Before finishing state:
`BRD process-step coverage: N/N accounted for`

No Mermaid block is required.

# 22. Machine contract

The MD must end with:

`## BAW_GENERATOR_SPEC`

and one valid JSON fenced block.

Example:

```json
{
  "app": {
    "name": "New Process App",
    "acronym": "NEWAPP",
    "description": "Optional",
    "snapshot_name": "Generated Initial"
  },
  "processes": [
    {
      "name": "Request Process",
      "lanes": [
        {"name": "Requester", "system": false},
        {"name": "Approver", "system": false},
        {"name": "Systems", "system": true}
      ],
      "source_coverage": [
        {
          "id": "SRC-001",
          "order": 1,
          "activity": "Submit request",
          "source": "BRD p.2",
          "kind": "human",
          "node_ids": ["submit"],
          "disposition": "represented"
        }
      ],
      "variables": [
        {"name": "requestName", "type": "String", "scope": "private"}
      ],
      "nodes": [
        {"id": "start", "type": "start", "name": "Start", "lane": "Requester"},
        {
          "id": "submit",
          "type": "human",
          "name": "Submit Request",
          "lane": "Requester",
          "inputs": ["requestName"],
          "outputs": ["requestName"],
          "fields": [
            {"name": "requestName", "label": "Request Name", "type": "String", "required": true, "read_only": false}
          ],
          "actions": ["Submit", "Cancel"]
        },
        {"id": "validate", "type": "system", "name": "Validate Request", "lane": "Systems"},
        {"id": "decision", "type": "gateway", "name": "Valid?", "lane": "Systems"},
        {"id": "done", "type": "end", "name": "Completed", "lane": "Systems"},
        {"id": "rejected", "type": "end", "name": "Rejected", "lane": "Systems"}
      ],
      "flows": [
        {"from": "start", "to": "submit"},
        {"from": "submit", "to": "validate"},
        {"from": "validate", "to": "decision"},
        {"from": "decision", "to": "done", "label": "Yes", "demo_default": true},
        {"from": "decision", "to": "rejected", "label": "No", "condition": "false"}
      ]
    }
  ]
}
```

# 23. Automatic SVG review

The SVG is a usability gate, not just a syntax artifact. Reject and revise the
specification when it contains synthetic action gateways, repeated Cancel ends,
long back-edge lines, or unnecessary crossings. Keep the normal path left to
right, place a real gateway immediately after the activity that owns the
decision, keep its branches compact, and use only the lanes that represent
actual actors or system work. Keep sibling outcomes on a common visual band,
give each branch its own clear horizontal direction, and place terminal events
after—not before or behind—their branch activities. No connector may pass
through a node, label, or unrelated lane. Present the SVG for approval only
after this visual review passes.

For every exclusive gateway, review the geometry as well as the edge list:

- a branch that terminates at an external activity must visibly terminate there
  before the terminal event and must not appear to continue through a sibling
  branch;
- an End event must be placed after its own system/external activity in the
  dependency order, never behind it, before it, or on top of it. The renderer
  must use dependency/topological ordering (excluding intentional Return
  back-edges), not simple breadth-first ordering;
- sibling outcomes from the same gateway must be parallel and independently
  readable, not serialized merely because their nodes were placed left to
  right; and
- do not let a connector cross, overlap, or pass behind another node to reach
  its target. If automatic layout produces an ambiguous chain, revise the
  layout or reject the SVG even when the JSON edges are technically correct.

Also run a decision-activity redundancy check: when a human task only captures
the value immediately consumed by a gateway, document why that task is
separate. If the BRD does not require a distinct interaction, combine the
decision field with the owning Coach instead of emitting a task-plus-gateway
pair that looks duplicated.

Stage 1 command:

```bash
python3 baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --check-spec
```

## Fast preflight triage

Run this once before making broad edits. Fix the first reported contract error,
then rerun; do not repeatedly rewrite the whole JSON block. The stable fixes
are:

- `BAW_GENERATOR_SPEC` heading: use the exact machine marker (a numeric section
  prefix is tolerated, but do not rename the marker).
- field control error: use `text`/`text_area` for open String fields,
  `single_select` plus `options` for finite Strings, numeric controls for
  Integer/Decimal, and `date` for Date. Read-only display copies use the
  Output Text widget and do not need a second dropdown domain.
- mapping error: every explicit `inputs`/`outputs` name must also have a field
  on that same Coach. Do not add hidden process variables to a task mapping
  unless a matching hidden field is declared.
- Return error: use a direct button flow to the previous editable Coach,
  unique return-comment variables per direction, and no Return-only gateway.

Only after this contract pass should Bob review SVG geometry or build the TWX.

This automatically creates:

```text
BAW_Process_Flows/
├── process-1.svg
├── process-2.svg
└── ...
```

The SVG:
- is generated locally;
- requires no npm, Node.js, Mermaid, browser, or external service;
- contains swimlanes, process nodes, gateways, branch labels, arrows, loops, and outcomes;
- comes directly from the exact JSON graph later used for TWX generation.

Therefore the user reviews the same process graph that will be implemented.


# 23A. BAW repository-safe artifact names

Traditional BAW stores Process Designer artifact names in its repository.
To avoid import-time database constraint failures:

- standalone generated BAW artifact names are kept at **64 characters or fewer**;
- this applies especially to generated BPD names and CSHS / human-service names;
- Bob should prefer concise business names, ideally 40 characters or fewer;
- the full business meaning stays in the source coverage / description;
- if a BRD-derived name is longer, the Python generator automatically shortens
  only the repository-facing artifact name and adds a deterministic hash suffix
  to avoid collisions;
- the reviewed BPD activity label can remain the original business wording;
- `--check-spec` reports any name normalization before TWX generation;
- final TWX validation checks package object names locally so BAW/DB2 is not the
  first place a naming problem is discovered.

Example:

`Review and Validate General Ledger Daily Control Reconciliation Exceptions`

may become the repository-safe CSHS artifact name:

`Review and Validate General Ledger Daily Control Reconcili~a1b2c3d4`

while the process activity can still display the original business label.

# 24. Native BAW rules preserved

The generalized generator preserves the critical working-V10 lessons:

1. TWX is not generic BPMN XML in a ZIP.
2. BPD requires synchronized BPMN2, IBM JSON, and native BusinessProcessDiagram representations.
3. IDs/references must stay synchronized.
4. All referenced package objects must exist.
5. CSHS requires native CoachFlow.
6. CSHS internal component IDs must be unique.
7. Placeholder AIS/SCA wrappers may import but stall; use native auto-completing demo service.
8. Exclusive gateways require executable/default routing.
9. New Process Apps require fresh project/branch/snapshot/artifact/version IDs.
10. Native BPD node Y positions are lane-local.
11. Do not reuse another Process App identity.


# 24A. Primitive type reference rule

Use the package-local System Data dependency-qualified primitive reference `<SYSDATA_DEP_UUID>/12.<primitive-UUID>` as verified by the manual BAW export.


# 24B. Runtime `tw.local` symbol-table rule

Traditional BAW BPD runtime locals must be serialized as native
`<privateVariable>` elements **inside the BPD `<pool>`**. These populate the
runtime symbol table used by `tw.local.<name>`.

Synchronize each process-local variable in all three forms:
- BPMN2 `dataObject`;
- JSON `dataObject`;
- native pool `privateVariable`.

Native type reference format is `/12.<primitive-uuid>`.

Preflight/TWX validation must fail if a sequence-flow expression references
`tw.local.<name>` but the pool has no matching native `privateVariable`.

Human-task mappings should use BAW assignment expressions between
`tw.local.<variable>` and the activity parameter IDs.


# 24D. Primitive type references verified from manual BAW export

The manually exported Traditional BAW 8.6.11 `trialstring` Process App confirms
that primitive System Data types use a **package-local dependency-qualified**
class reference:

```text
<System-Data-dependency-UUID>/12.<primitive-UUID>
```

The dependency UUID is the UUID suffix of the `System Data` dependency entry
inside that Process App's own `package.xml`. It is not a server-global type ID.

Therefore generated primitive process variables must never use:
- a bare primitive `TWClass.<uuid>`;
- `/12.<uuid>` with no dependency;
- a dependency UUID copied from another Process App.

Use this generated package's own `SYSDATA_DEP_UUID`.

System Data 8.6.0.0 primitive UUIDs:

```text
String  = db884a3c-c533-44b7-bb2d-47bec8ad4022
Boolean = 83ff975e-8dbc-42e5-b738-fa8bc08274a2
Integer = 3fa0d7a0-828a-4d60-99cc-db5ed143fc2d
Decimal = 536b2aa5-a30f-4eca-87fa-3a28066753ee
Date    = 68474ab0-d56f-47ee-b7e9-510b45a2a8be
```

The manual export also confirms explicit BPD inputs are real `<bpdParameter>`
objects (`parameterType=1`) whose `classId` uses this same dependency-qualified
pattern. Generated explicit inputs/outputs must follow that native structure.

Private runtime variables remain native `<privateVariable>` elements inside the
BPD pool, but their primitive `classId` must also use the package-local System
Data dependency prefix.

# 25. Python/runtime

Use:

```bash
python3 baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --check-spec
```

After review:

```bash
python3 baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --output BAW_Process_Flows/<app>.twx
```

Validate existing TWX:

```bash
python3 baw_twx_generator.py --validate MyApp.twx
```

The generator is Python 3.9+ compatible.

# 26. Current boundaries

Stable common-workflow support:
- multiple BPDs;
- multiple human/system lanes;
- Coaches;
- system/external/notification nodes;
- exclusive gateways;
- rework/reject/cancel;
- deterministic demo execution;
- new Process App generation.

Not production-complete:
- parallel/inclusive gateways;
- timers/boundary events;
- nested subprocesses;
- arbitrary complex BO/list propagation beyond the supported shared
  `CommentHistoryEntry` list pattern;
- real service endpoint/auth mappings;
- production-grade automatic action-button-to-gateway decision routing;
- production LDAP/team configuration.

If the BRD materially requires an unsupported construct, state it instead of silently changing the process.

# 27. Easy prompts

## Prompt 1 — BRD → MD + SVG

> Read `ibm-baw-twx-builder/SKILL.md`, create the `BAW_Process_Flows/` artifact root, analyze the attached BRD, and write all five JSON contracts in `BAW_Process_Flows/contracts/`. Preserve every material business step, source order, actor, condition, branch, external activity, notification, field, Business Object, and variant-specific rule. For every human process, include the required shared `commentHistory` contract and map it through every Coach. Run `python3 ibm-baw-twx-builder/scripts/baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --check-spec`, fix any preflight errors, present the generated SVG, and stop for flow approval. Do not generate a TWX yet.

## Prompt 2 — Approved MD → TWX

> Read `ibm-baw-twx-builder/SKILL.md`. Using the approved five contracts in `BAW_Process_Flows/contracts/`, rerun `--check-spec`; if it passes, generate and validate one Traditional BAW Process App TWX with `--contracts-dir`. Do not rebuild from a hand-written monolithic specification. Return the artifact folder and validation result, then stop for separate deployment approval.

# 28. Definition of success

```text
BRD
 ↓
five named contracts
 ↓
assembled BAW_Process_Spec.md + BAW_GENERATOR_SPEC.json
 ↓
source coverage + graph validation
 ↓
process-review SVG(s)
 ↓
USER REVIEWS / FIXES LOGIC
 ↓
TWX generation
 ↓
new Process App imports
 ↓
Coaches open
 ↓
demo process runs
```

If a future BRD exposes a real generic generator defect, fix the single reusable generator once. Do not create client-specific generator versions.
