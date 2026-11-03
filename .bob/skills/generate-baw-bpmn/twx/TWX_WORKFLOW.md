# TWX with Coaches: detailed workflow

This file is the detailed workflow behind the **TWX with Coaches** output option of the `generate-baw-bpmn` skill. It builds a Traditional IBM Business Automation Workflow process app (`.twx`) from business requirements, including human services and Coaches, while keeping an explicit approval gate before generation.

## Target version check (do this first)

**Version status of the TWX option.** The TWX generator was built and structurally validated against Traditional BAW 8.6.11 only. It stamps the package as 8.6.11 and links the 8.6.0.0 System Data and UI Toolkit snapshots. Compatibility with BAW 24.0.x is **not yet confirmed**. Until a v24 import has been tested, treat TWX output for a v24 target as a pilot, import it into a development environment only, and report the exact import result. The BPMN + zip option is not affected.

Before step 1 below:

1. Ask the user which BAW version and deployment they target (for example Traditional BAW 24.0.x, CP4BA 24.0.x, or 8.6.11).
2. **8.6.11:** proceed. This is the validated target.
3. **Anything else (including 24.0.x):** say plainly that the output is untested for that version, then ask whether to continue as a pilot. If they continue, record the target version in the application contract's `runtime` section and in the final report, and tell them to import into development first.
4. If the user can export a small reference TWX (one process app with one human service and one Coach) from their own environment, offer to run `scripts/analyze_twx.py` on it. Its "Build" line and dependency snapshots show whether the generator's fixed values match their environment:
   - `buildVersion` and `fixPack` versus the generator's `8.6.11` / `26000`;
   - the System Data and UI Toolkit snapshot names versus `8.6.0.0`.
   Report any difference. Do not change the generator's constants without such an export.

## Required workflow

1. Read [references/BAW_AUTOMATION_REFERENCE.md](references/BAW_AUTOMATION_REFERENCE.md) before interpreting a BRD or changing the generator. For BRDs with meaningful human data or decisions, also read [references/BAW_APPLICATION_DESIGN_GUIDE.md](references/BAW_APPLICATION_DESIGN_GUIDE.md). If the user supplies an existing TWX as a design reference, read [references/BAW_REFERENCE_TWX_ANALYSIS.md](references/BAW_REFERENCE_TWX_ANALYSIS.md) and run `scripts/analyze_twx.py` before mapping the new BRD. Treat the reference as evidence and design inspiration, never as a source of identifiers or business facts.
2. Create one run artifact root named `BAW_Process_Flows/` and keep the generated specification, SVGs, TWX, validation reports, reference analysis, and deployment/runtime handoff artifacts inside it. Extract the process specification in this order: source-step ledger; actors/lanes; persistent data model (primitive variables and generic Business Objects); field ownership; human-task/Coach contracts; gateways/actions; integrations, notifications, validations, and exception paths. Record assumptions separately. Do not hard-code concepts from a previous use case.
3. Generate a human-readable specification and SVG process flow. Stop and ask the user to approve or revise the flow. Do not generate a TWX before approval.
4. After flow approval, generate the TWX with `scripts/baw_twx_generator.py`. Run its validation command (`--validate`) and inspect the archive.
5. Hand the `.twx` to the user to import through Workflow Center. Deployment to a server is not part of this skill; use `baw-deployment-manager` or `version-lifecycle-manager` if the user wants that. Treat a successful import as import acceptance, not runtime proof.
6. Runtime testing happens in BAW, by the user or with `generate-baw-tests`. Verify process launch, every Coach, required validation, data propagation, routing, and completion.

## Worked example

[examples/minimal-contracts/](examples/minimal-contracts/) is a complete five-file bundle (two human tasks, no services) that passes `--check-spec`, builds, and validates. Copy it as a starting point. Two requirements it demonstrates are easy to miss and each causes a generator error if absent:

- every Coach field needs `value_domain` (`finite` or `open`) and `control` (for example `text`, `single_select`);
- every Coach needs a `history_view` entry, otherwise the parent User Task does not map the shared `commentHistory` list and TWX validation fails with "does not map all CSHS inputs/outputs".

```bash
python3 scripts/baw_twx_generator.py --contracts-dir examples/minimal-contracts --check-spec
```

Run that command from a scratch copy, not from inside the skill folder, because the generator writes its output next to the contracts directory.

## BRD decomposition and contract stage

Keep the workflow above unchanged, but add this contract stage after reading the
BRD/reference TWX and before the SVG approval gate. Read
[references/BAW_CONTRACT_BUNDLE.md](references/BAW_CONTRACT_BUNDLE.md) for the
schemas and cross-contract rules.

1. **Find the target scenario.** Look for an explicit target scenario, happy
   path, exception path, or process narrative. If none exists, record
   `MISSING` and ask for confirmation; do not invent a business flow.
2. **Create a sentence-level evidence ledger.** For every material BRD sentence,
   identify the actor, BPMN activity/node, field, gateway/condition, service or
   system call, human task/Coach, view, notification/SLA, and exception path it
   implies. Preserve the source text and mark each conclusion
   `CONFIRMED`, `INFERRED`, `ASSUMED`, `MISSING`, `AMBIGUOUS`, or
   `CONTRADICTORY`.
3. **Map participants to BPM.** Every person, role, team, department, bot, or
   RPA mentioned as doing work becomes an actor/lane candidate. External
   databases, APIs, tools, and back-end systems become explicit service
   boundaries and service/system/external/notification nodes. Gateways must
   have a named decision variable and evidence for each outgoing condition.
4. **Design human work and data.** Use the BRD's required-fields section as
   authoritative Coach input when present; do not replace it with inferred
   fields. For each human task define its editable fields, read-only context,
   validation, actions, output mappings, and whether a reusable view is
   appropriate. If the BRD specifies a layout or visual design, preserve it;
   otherwise use the supported control catalog and presentable grouped Coach
   layout documented in `BAW_REFERENCE_TWX_ANALYSIS.md`. Mark native tables,
   tabs, rich views, and other unsupported artifacts `UNSUPPORTED` instead of
   flattening them.
   Every process with human Coaches must also define a shared, append-only
   `commentHistory` Business Object/list and a reusable read-only history-table
   view for every human Coach (the first Coach simply shows an empty history).
   Each row records at
   least `occurredAt`, `fromActor`, `toActor`, `fromCoach`, `toCoach`, `action`,
   and `comment`. A Return, Submit, Forward, Escalate, or similar business
   action appends a row before routing; Close does not. The receiving Coach
   receives the complete history and shows it read-only in chronological append
   order unless the contract explicitly requests another ordering. By default,
   the table exposes only `Date`, `Action`, and `Comment`; sender, recipient,
   and Coach metadata remain stored for audit and routing but are not displayed.
   A Return row targets the
   previous editable actor; a forward row targets the next actor determined by
   the approved flow. Never let users type the recipient or overwrite existing
   rows. Keep the current comment/draft separate from the history list, and
   use a distinct Return-comment variable per independent Return direction.
   The generator supports this standard history pattern as a native local
   list Business Object, read-only Table with nested Output Text columns, and
   append script. Other arbitrary list Business Objects, service-backed tables,
   and reusable native `coachView` artifacts remain `UNSUPPORTED` unless their
   serializers are explicitly implemented; never replace this history with one
   String or claim bidirectional history works without the native artifacts.
   Every history-enabled CSHS and its parent BPD User Task must map the shared
   history list in both directions: process -> CSHS input and CSHS output ->
   process. Validation must fail when either mapping is missing; a Coach-local
   append that is not returned to the process is not persisted history.
5. **Define the data model.** Enumerate process variables, types, ownership,
   input/output mappings, gateway decision values, and the number and reuse
   mode of Business Objects. Group fields into an object only when the BRD
   shows a reusable business concept or the approved design explicitly calls
   for one. Never turn a required object into a String merely to make the
   serializer pass.
6. **Write five named contracts.** Create `process_contract.json`,
   `coach_contract.json`, `service_contract.json`, `data_contract.json`, and
   `application_contract.json` in a `contracts/` directory. The contracts must
   contain, respectively: scenario/ledger/actors/lanes/nodes/gateways/flows;
   human services/Coach and reusable-view blueprints; service integrations and
   placeholder operations; variables/Business Objects/mappings; and app
   metadata/theme/dependencies/runtime assumptions. The contract names should
   describe their contents, and the bundle must retain assumptions and source
   references.
7. **Declare integrations without fabricating connectivity.** Create a service
   descriptor for every required DB/API/SOAP/backend/tool/RPA/notification
   boundary even when its URL, credentials, or schema is not supplied. Use
   `MISSING`/`PLACEHOLDER` endpoint status, list the empty configuration in the
   phase-1 handoff, and never claim the service is connected.
8. **Apply the shared theme contract.** Use
   `assets/enterprise-burgundy-theme.json` as the default visual profile. The
   generator combines that profile with the complete BAW 8.6.11-compatible
   LESS variable contract in
   `assets/enterprise-burgundy-baw-8.6.11-theme.less`, then emits a companion
   Theme toolkit with a native `uiTheme`. The process app depends on that
   toolkit snapshot and its project defaults reference the toolkit-owned
   Theme. The toolkit snapshot is embedded under `toolkits/` in the one
   generated process-app TWX, so the user receives and imports one file. Never copy
   source repository UUIDs or organization-specific names. A palette-only
   `uiTheme` is invalid even when the TWX imports: it can fail LESS compilation
   (for example, an undefined `@bpm-border-normal`) and surface as a misleading
   runtime "no theme set" error. The target BAW runtime test remains required.
9. **Assemble and validate before SVG/TWX.** The generator can assemble the
   five contracts directly:

   ```bash
   python3 scripts/baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --check-spec
   python3 scripts/baw_twx_generator.py --contracts-dir BAW_Process_Flows/contracts --output BAW_Process_Flows/<app>.twx
   ```

   This writes `BAW_Process_Spec.md` and `BAW_GENERATOR_SPEC.json`, validates
   cross-contract references, and then runs the existing generator preflight.
   Keep the existing SVG approval gate: contract assembly and validation do not
   authorize TWX generation or deployment by themselves.

When preflight fails, fix one contract error at a time and rerun before
rewriting the full JSON. Use the generator's field-control, same-Coach mapping,
and Return-contract diagnostics as the source of truth; do not work around a
late TWX `KeyError` by adding process variables that are not displayed on the
task's Coach.

See [references/HANDOFF_RUNBOOK.md](references/HANDOFF_RUNBOOK.md) for commands, environment setup, runtime checks, import order, and diagnostic signatures. Never place credentials in the skill or generated artifacts. For demo outputs, use the visual profile in [assets/enterprise-burgundy-theme.json](assets/enterprise-burgundy-theme.json) as the default color/layout contract and the complete native source in [assets/enterprise-burgundy-baw-8.6.11-theme.less](assets/enterprise-burgundy-baw-8.6.11-theme.less) as its BAW compile-time contract. Together they reproduce the approved enterprise burgundy palette and behavior without copying any source repository IDs.

For a supplied reference TWX, report its product/fix-pack fingerprint,
dependency snapshots, native object families, main-process shape, Business
Object groupings, Coach/view complexity, integration boundaries, and theme
defaults before proposing a generalized design. Read-only UI inspection may
confirm visible lanes, task implementation, and validation status; it does not
replace archive evidence. Do not claim that the generator can reproduce a
reference's native Business Objects, complex `coachView` artifacts, service
flows, themes, or toolkit widgets unless the serializer actually implements
those artifacts. Mark unsupported native capabilities as `UNSUPPORTED` at the
specification gate.

Theme status is explicit: `assets/enterprise-burgundy-theme.json` is the shared
visual contract for the enterprise burgundy palette, typography, responsive behavior, and
semantic states; `assets/enterprise-burgundy-baw-8.6.11-theme.less` supplies the full
native variable definitions required by the Theme editor and Coach runtime.
The generator emits one self-contained process-app TWX. Inside it, a neutral
Theme toolkit snapshot is packaged at `toolkits/<snapshot-id>.zip` with fresh
project, snapshot, dependency, Theme, and version IDs. The process app lists
that toolkit snapshot as a dependency and references the toolkit-owned Theme
from `projectDefaults/defaultTheme`. Do not embed the Theme directly as an
app-owned object: Traditional
BAW can display such an object in Designer while Coach runtime still reports
that no theme is set. Structural validation rejects a palette-only Theme. The
target BAW import and runtime Coach rendering remain the final compatibility
checks.

The Coach control catalog learned from the reference is documented in
`BAW_REFERENCE_TWX_ANALYSIS.md`. The current serializer supports Text, Text
Area, Output Text, Integer, Decimal, Date, Checkbox, Single Select, Button,
Section, Horizontal Layout, and Vertical Layout. Multi Select, Checkbox Group,
Table, Data/Service Call, tabs, modal sections, file events, and rich nested
event wiring require a native serializer extension and must be reported as
`UNSUPPORTED` until implemented.

When the requested design includes a reusable Coach view or a repeated/table
field, also read the **Reusable-view pattern** and **Field-to-view decisions**
sections in `BAW_REFERENCE_TWX_ANALYSIS.md`. Treat a reusable view as a typed
contract—business-data inputs/outputs, configuration options, responsive nested
layout, bindings, validation, and optional lifecycle events—not as a screenshot
or a flat group of widgets. Distinguish a bound `Table` from a visual `Table
layout` and from a service-backed table. The current generator documents these
contracts but does not emit native `coachView` artifacts, table/service-table
contributions, or reference organization custom views; label those parts `UNSUPPORTED` rather than
flattening them or copying the bank's toolkit identifiers.

For every requested reusable view, produce a view blueprint before TWX
serialization. The blueprint must state the toolkit or Process App scope,
responsive intent, typed inputs/outputs, configuration options, private helper
state, nested layout tree, field-control matrix, table row schema (including
`currentItem` bindings), validation/visibility rules, and real service/event
dependencies. Use the inspected reference organization pattern—title/process-information area,
business tabs, typed controls/table/document content, and an action bar—only as
a reusable layout pattern; do not clone its business fields or UUIDs. If the
requested view contains a Table, Service data table, Tabs, custom reference view,
file/document events, or rich lifecycle scripts, keep those items explicit in
the blueprint and mark native serialization as `UNSUPPORTED` unless the
serializer has been extended and validated against the target toolkit
snapshot.

When the request includes a human service, inspect both sides of the UI
boundary. Treat the human service as the orchestration layer (variables,
Coach/form task, scripts, services, gateways, validation, postpone,
termination, and end paths) and the reusable Coach view as the presentation
layer. Record the actual view-instance binding (`tw.local` path to the view's
declared business-data binding), the selected `viewUUID`/name, host-supplied
configuration mappings, and each Coach event path mapped to its outgoing
sequence flow. In the reference pattern, `tw.local.lg` is the human-service
variable, the Coach view declares the `lg` Business Object binding, and
`Submit`, `Save`, and `Terminate` are bound to different service-flow routes.
Never claim that a view is connected merely because labels match. The current
serializer reports native `formTask`/`ViewRef`/Coach-event wiring as
`UNSUPPORTED` unless that extension has been implemented and validated.

## TWX invariants

- Keep the BPMN2 model, Bob JSON process model, and native BPD synchronized.
- Declare each `tw.local` variable as a native `privateVariable` inside the pool.
- Use dependency-qualified primitive `classId` values such as `<SYSDATA_DEP_UUID>/12.<primitive UUID>`; do not use bare primitive UUIDs.
- Model each human activity as a standalone native User Task connected to a separate CSHS. Do not add inline Coach metadata or global-user-task roots.
- Give CSHS action outputs `type="2"` and include the required boundary-event scripts.
- Native input mappings must contain `name`, `classId`, `input`, `value`, and `parameterId`. Do not encode an input as `expression` plus `activityParameterId`.
- Native output mappings use `activityParameterId`, `location`, and `variableId`.
- Every branch after a multi-action human decision must have an explicit comparison against the action variable, including the positive/Approve branch. Never serialize Approve as an unconditional or demo-default path.
- Treat Business Objects as a generic capability: reuse an existing Process App/Toolkit object when resolvable, create a new one only when the approved specification says `mode: create`, and never flatten an object into a String. If the current generator cannot serialize the native object artifact, report `UNSUPPORTED` rather than claiming it was generated.
- Preserve exact BRD fields and groups in the field/Coach coverage table. Do not silently substitute one source concept for another (for example, Expected Completion Date for Expected Timelines) or omit fields such as Strategic Relevance. Use `Decimal` for monetary values, `Integer`/`Decimal` for numeric scores or person-days, and `Date` plus a native date control for calendar dates; never coerce these to `String`. Model attachments only when requested and never pretend a binary attachment is an ordinary String.
- Keep the prose lane model, JSON `lanes`, and node lane assignments synchronized. External actors may be represented as explicit external handoffs, but the mapping must be documented; a lane-count mismatch is not acceptable.
- Keep source coverage counts consistent with the ledger population. Distinguish material business-step coverage from structural start/end rows instead of reporting an incorrect `N/N`.
- Treat the SVG as a semantic layout gate: branches from a gateway must remain visually independent, terminal events must follow their own branch activity, sibling outcomes must be parallel, and no connector may cross or pass behind another node. If a technically correct edge list renders as an ambiguous chain, revise or reject the SVG.
- When a human task only captures the value immediately consumed by a gateway, document why it is a distinct interaction; otherwise combine the decision field with the owning Coach to avoid a redundant task-plus-gateway pair.
- Design each Coach around purpose, prior read-only context, current editable responsibility, validation, and a grouped action bar. Before declaring every visible variable/field, make a field-control decision: classify its value domain as `finite`, `open`, `Boolean`, `numeric`, or `Date`, state the chosen UI control, and record the decision in the field/Coach coverage table. Every finite non-Boolean value must have an `options` list and a native Single Select/dropdown; this applies to all finite business fields, not only gateway variables. If the BRD omits the domain, infer conservative values, mark them `ASSUMED`, list the proposed values and rationale in the final assumptions, and ask for confirmation. Never silently leave a finite value as free text. Keep Boolean values as organized native Checkboxes, numeric values as numeric controls, calendar dates as native Date controls, and open narratives as text/Text Areas. Put editable request and decision-support fields in Request Details before Yes / No Checks and Comments & Notes. Every generated Coach must also expose a standard `Close` button configured as the BAW Coach Flow action `End the human service`; treat it as a UI-only close action, not a business decision or a Return gateway branch. The first human Coach must not expose Return because no previous editable actor exists. For later human review/committee handoffs, unless the user opts out, assume Return/rework, record that assumption, preserve all process data, show the return comment read-only on the receiving Coach, and route Return directly from the Coach action to the previous editable human task. Configure that button's next step directly; do not create a Return-only gateway. Return is rework, not Reject or Cancel. Add Postpone/SLA/attachments only when the current BRD or the user explicitly asks for them.
- Apply strict source-type inference: whenever the BRD stores or requests a calendar date (for example expected completion date, submission date, effective date, deadline, start date, end date, or due date), declare both the process variable and Coach field as `Date` and render a native date input. Never serialize a date as `String`, including when it is read-only downstream. A timeline, duration, period, or target window may remain `String` only when the BRD explicitly describes a narrative or non-calendar value. If native Date serialization is unavailable, report `UNSUPPORTED` rather than silently coercing the field to `String`.
- Require zero BAW validation errors and warnings before calling the application ready for runtime testing.

## Evidence and reporting

Report each stage independently: flow approved, TWX generated and locally validated, BAW import accepted (by the user), BAW validation clean, and runtime path tested. Never describe an imported application as fully working unless the runtime path has actually been executed. Preserve sanitized commands, relevant log excerpts, and generated artifact paths for handoff.
