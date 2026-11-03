# Reference TWX analysis and advanced Traditional BAW design patterns

Use this reference when the user supplies an existing `.twx` as a design
reference. It describes the reusable engineering patterns observed in the reference organization
`LG Issuance - LG_08_09_2026_V1.twx`; it is not a template to copy. Business
names, UUIDs, credentials, team IDs, environment variables, SQL, web-service
schemas, theme references, and dependency snapshots are project-specific.

## 1. Reference intake and evidence rules

Run the read-only analyzer before designing a new application:

```bash
python3 scripts/analyze_twx.py "/path/to/reference.twx" --out reference-analysis.md
```

The analyzer reads the ZIP/XML structure only. It must never execute scripts,
SQL, service calls, UCAs, or assets from the reference archive. In addition to
the report, inspect the reference in the target BAW Workflow Center when the
user provides access. Use the UI to confirm the design intent (lanes, visible
handoffs, Coach implementation, and validation state), not to guess hidden XML
values.

Record two separate facts:

1. **Archive evidence:** package build/fix pack, object counts, dependency
   snapshots, native object types, process data, Coach/view metrics, and
   integration markers.
2. **Design inference:** why the reference uses a user task, service flow,
   gateway, parallel check, timer/escalation, bot event, or rework loop.

Never present an inference as something literally encoded in the TWX. Never
copy an identifier simply because it appears in a reference package.

## 2. What the reference organization reference actually contains

The supplied archive is a Traditional IBM BPM/BAW **8.6.3 fix pack 21031**
application, not a BAW 8.6.11/24.x application. Its package target is the
`LG Issuance` process application, snapshot `LG_08_09_2026_V1`, with reference organization
toolkits and several standard 8.6.0.0 toolkits. The target environment in the
project defaults is `BAW_tWAS`.

The archive contains 166 members and 145 native application objects:

| Object family | Count | What it indicates |
|---|---:|---|
| Main BPD | 1 | One large orchestration process |
| Helper processes | 80 | Reusable service/microflows, lookups, notifications, persistence, and integration wrappers |
| Business Objects (`twClass`) | 45 | A structured request aggregate plus stage/role-specific data groups |
| Coach views | 3 | Editable and read-only versions of a large multi-section form |
| Participants/teams | 8 | Role and lane ownership |
| Web services | 2 | External integration contracts |
| Under-cover agents | 2 | Asynchronous event/bot handoffs |
| Environment variable set | 1 | Environment-specific configuration rather than hard-coded endpoints |
| Managed assets | 2 | A Java mail asset and an additional packaged asset |
| Project defaults | 1 | Theme, XSL/CSS, namespace, and runtime settings |

The BPD `LG Issuance & Modification Process` has approximately 131 flow
objects, 16 lanes, 29 gateway markers, and 16 private variables. The browser
view confirms the same design: lanes for the process starter, initiator,
executive/team-leader roles, compliance/AML/sanctions, FI roles, manager roles,
and LG creation/validation bots. The selected `Pre-Initiator` is a native User
Task whose implementation is a separate `LG Issuance Human Service`; the BAW
editor showed no validation issues for that selected task at inspection time.

### Main process pattern

The flow repeatedly applies this stage pattern:

1. A human User Task captures or reviews a stage-owned decision/data set.
2. A separate initiation service flow prepares task context, history, and
   notifications.
3. A decision gateway routes Approve, Return, Reject, Not Related, or another
   stage outcome. Branch conditions must explicitly compare the action value.
4. A service flow persists status or maps data, and may notify users.
5. Escalation/timeout logic can create a separate notification or task path.
6. A Return path preserves the request and history and routes back to the
   previous editable stage; it is rework, not cancellation.
7. RPA creation/validation work is represented as an asynchronous handoff:
   task initiation, external bot state, polling/status retrieval, failure
   gateway, retry/iteration update, and completion/failure notification.

The same process uses both sequential approval chains and independent
compliance/FI checks. Use parallel gateways only when the checks are genuinely
independent, and converge them before a downstream decision. Do not add
gateways merely to make a diagram look complex.

## 3. Business Object grouping model

The 45 reference `twClass` objects contain roughly 384 properties. Their
grouping is a useful modeling pattern:

### Root aggregate

`LG` is the process-level aggregate: request type, process metadata, initiator,
role data, decision flags, RPA state, dates, and references to reusable toolkit
objects. A process should normally have one root aggregate when the same
request must survive several human and automated stages.

### Stage/role wrappers

Objects such as `LG_Initiator`, `LG_Compliance`, `LG_FI`, `LG_LGManager`, and
executive/team-leader wrappers identify ownership and hold a stage-specific
`Information` object plus process history. Use this shape when a role owns a
coherent group of fields and later stages need a stable reference to its
decision/history.

### Information objects

The largest groups are intentionally cohesive:

- `LG_Initiator_LG_CorrespondentBank_Information`: a large correspondent-bank
  and LG request section (bank/country, applicant/beneficiary, goods, dates,
  ports, commission, compliance, and related data).
- `LG_Initiator_Reverse_Information`: reverse-LG details.
- `LG_Initiator_Purchasing_information`: purchasing details.
- `LG_LGExecutive_Information`: executive review fields.
- `LG_Initiator_LG_CreditFacility_Information`: credit-facility information.

Group fields when they share a business owner, lifecycle, validation rules,
visibility rules, or are reused as a section across more than one Coach. Do not
create a new object solely because two fields appear next to one another.

### Shared and transient types

Reuse generic types such as `Process`, `Client`, `Documents`, `NameValuePair`,
and `ProcessHistory` when the target toolkit already provides them. Use lists
for repeated questions, documents, or name/value data. Use small transient
objects (`tempFI`, `tempAml`, `tempSanction`) only for temporary parallel or
mapping state; do not persist them as the canonical request model.

### Source-type discipline

The reference contains many String-typed values, including some dates and
amount-like values. Treat that as a legacy characteristic, not a rule. New
models must infer types from the BRD: Date for calendar dates, Decimal for
money, Integer/Decimal for numeric counts/scores, Boolean for flags, and
String only for true open text or explicitly non-calendar labels. Preserve
reference naming quirks only when compatibility requires them; otherwise avoid
duplicates and spelling defects such as `tempComplaince`.

## 4. Coach views and human-service design

The reference contains three large views:

- `LG Issuance View`: editable, approximately 532 layout items, 312 data
  bindings, 239 event markers, and 25 widget families.
- `LG Issuance View Read Only V2`: approximately 423 layout items, 249
  bindings, 213 event markers, and 21 widget families.
- `LG Issuance View Read Only`: approximately 415 layout items, 239 bindings,
  189 event markers, and 21 widget families.

They use nested bindings into the root request object, repeated sections/tabs,
single-selects, text inputs/areas, numeric/date controls, checkboxes, buttons,
attachments, service-result events, and visibility/enabled expressions. The
editable/read-only split is deliberate: later reviewers should see the prior
request context without being allowed to change it.

### Field and Coach control catalog observed in the reference

The reference views use standard UI Toolkit controls plus layout/behavior controls.
Use the semantic type—not the widget UUID—as the reusable design contract:

| Semantic purpose | Reference control | Use it for |
|---|---|---|
| Short/open text | Text | Names, identifiers, short labels, codes |
| Long/open narrative | Text Area | Descriptions, comments, justifications |
| Read-only text | Output Text | Prior-stage data, calculated values, status |
| Whole number | Integer | Counts, iterations, quantities |
| Money/measurement | Decimal | Amounts, rates, percentages, numeric scores |
| Calendar value | Date Time Picker | Issue dates, expiry dates, deadlines |
| One choice | Single Select | Finite mutually exclusive options |
| Several choices | Multi Select | Multiple countries, categories, roles, or flags |
| One Boolean | Checkbox | A true/false flag or yes/no fact |
| Several Boolean choices | Checkbox Group | A set of independent yes/no selections |
| Repeated structured rows | Table | Process history, documents, repeated records |
| Dynamic service-backed data | Data / Service Call | Lookup or populate values from a service flow |
| Action | Button / Link | Submit, retrieve, open, or invoke a service |
| Grouping/layout | Panel, Well, Horizontal Layout, Vertical Layout, Tab Section, Modal Section, Collapsible Panel, Line | Organize large forms and preserve responsive alignment |

The open source toolkit palette confirms these are real reusable palette entries,
not labels invented by the view: `Text`, `Text area`, `Output Text`, `Integer`,
`Decimal`, `Date Time Picker`, `Single select`, `Multi select`, `Check box`,
`Check box group`, `Table`, `Table layout`, `Table layout row`, `Table layout
cell`, `Service call`, `Service data table`, `Data`, `Tab section`, `Tabs`,
`Panel`, `Horizontal layout`, `Vertical layout`, `Modal section`, `File
Viewer`, and several document controls. The palette also contains source-specific
views such as `reference organization Header CV`, `LG Issuance View`, and `CD Subscription View`.
Those custom entries are toolkit artifacts: use their semantic contract when
designing a new view, but do not copy their UUIDs into another Process App.
The two visually similar entries with different UUIDs (for example two
Single-select or two Date-picker entries) are distinct toolkit implementations
or versions; resolve the target toolkit's actual palette item rather than
assuming the UUID from this reference is universal.

The reference also uses a service-call control to retrieve ticket/delta data,
service-result events to map the response, a table for process history, tab
sections for major business areas, and visibility/enabled expressions to hide
or lock fields by task/stage. A new Coach should choose controls from the
field's value domain and lifecycle, then add layout controls for readability;
it should not expose raw widget IDs to the BRD author. The current generator
has native mappings for Text, Text Area, Output Text, Button, Checkbox, Single
Select, Decimal, Integer, Date, and basic layouts. Service Call, Multi Select,
Checkbox Group, Table, Data, tabs, modal sections, and rich event wiring need
an implemented native serializer or must be marked `UNSUPPORTED`.

Useful event patterns:

- `ON_LOAD` initializes visibility, labels, task context, and default state.
- `ON_CHANGE` controls dependent fields and stage-specific visibility.
- `ON_BLUR`/`ON_CLICK` calls a service flow for ticket/data retrieval.
- `ON_SVCRESULT` maps service results into the Coach's nested data model.
- `ON_TABCHANGE` supports large multi-section forms.
- File/revision events support document controls when attachments are in scope.

For a new BRD, create the view contract before serializing the Coach:

1. Group fields by business section and owner.
2. Mark each field input, output, read-only, hidden, finite, Boolean, numeric,
   Date, or narrative.
3. Declare the data path and process/Coach parameter that owns it.
4. Add validation and dependent visibility only when the BRD or workflow
   rules justify it.
5. Add service-result mappings for values supplied by a real integration.
6. Provide editable and read-only variants only when task roles require them.

The current generator supports a conservative generated Coach contract and
primitive controls. It does **not** yet guarantee native serialization of a
large arbitrary BAW `coachView` with all toolkit widgets, nested event
handlers, tabs, file events, and service-result mappings. If a requested native
view feature is not implemented, report `UNSUPPORTED` and preserve the
approved specification; do not emit a fake or flattened view.

### Reusable-view pattern confirmed in Workflow Center

The browser inspection of the source toolkit's `CD Subscription Process Details UI
View (Read-only)` shows the intended reusable-view contract. The view is listed
under the toolkit's **User interface** category, so another Coach can consume it
as a palette component rather than rebuilding the layout. Its overview marks it
as intended for multiple devices. It is not a process task by itself: the parent
Coach supplies the business-data binding and decides which actions/events are
allowed.

The inspected view has three contracts that must be kept separate:

1. **Data contract.** A business-data input `cds (CDSubscription)` is declared
   under Variables. Configuration Options and Localization Resources are
   separate view-level namespaces. For a generated view, expose only the
   business object/list and configuration values that the parent Coach must
   provide; keep helper state private.
2. **Visual contract.** The layout is nested rather than a flat list: a root
   horizontal layout contains a title panel, a process-information panel, a
   row of read-only outputs, a tab section for major business areas, and an
   action bar. The view supports Small, Medium, and Large responsive devices.
3. **Behavior contract.** The view editor provides Dynamic Style, Included
   Scripts, Inline CSS/JavaScript, AMD Dependencies, Header HTML, and lifecycle
   handlers (`load`, `unload`, `view`, `change`, `collaboration`, `validate`).
   These are optional extension points; do not add scripts or dependencies
   unless the BRD or a real integration requires them.

The practical reusable-view recipe is:

```text
View metadata
  -> name, documentation, palette/preview identity, responsive intent
View variables
  -> input business object or list, output/event values, configuration options
  -> private helper variables and localization resources
Layout
  -> responsive root (Horizontal/Vertical)
  -> header/title Panel
  -> process-information row (Output Text)
  -> Tab Section(s) for business areas
  -> content controls (inputs/outputs/table/documents)
  -> action bar (Button/Link)
Behavior
  -> bindings, validation, visibility/enabled rules, service-result handlers
```

### How to create a reusable view from a BRD

Use this sequence when the BRD contains a form section that will be rendered
by more than one Coach or by more than one human task:

1. **Create the view artifact in the User interface library.** Put it in a
   toolkit when it is a shared component; put it in the Process App only when
   it is application-specific. Give it a stable semantic name and document its
   purpose. Set `Intended for use on multiple devices` when it has responsive
   layouts. `Use as a Template` is a separate inheritance feature; it is not
   required merely because the view is reusable.
2. **Define the data contract before drawing controls.** In Variables, add
   typed Business Data inputs/outputs. For example, the inspected reference view
   receives `cds (CDSubscription)`. A repeated table receives a typed list
   such as `processHistory[]`, not a JSON or String placeholder. Keep
   Configuration Options for host-supplied labels or switches, and keep helper
   state private.
3. **Build the responsive layout tree.** Start with a root Horizontal or
   Vertical layout, then add Panels/sections, rows, tabs, content controls,
   and an action bar. The reference view follows: title panel -> process-information
   row -> business-area Tab Section -> controls/documents -> action button.
   This hierarchy is what makes the view reusable; a screenshot or a flat list
   of widgets is not a view contract.
4. **Choose each field from the data domain.** Use Text/Text Area for open
   strings, Output Text for read-only values, Integer/Decimal for numeric
   values, Date Time Picker for dates, Single Select for one finite choice,
   Multi Select or Checkbox Group for several choices, and Checkbox for a
   Boolean. Record the exact binding path, required/read-only state, options,
   validation, and visibility rule in the view blueprint.
5. **Build a repeated table only from a typed list.** Add the native `Table`
   control, bind it to the list, and put one child control in its content box
   for each displayed property. Inside the row, use the table's `currentItem`
   context (for example `processHistory.currentItem.taskName`). Use `Output
   Text` children for read-only history columns. Use `Table layout` only for a
   visual grid and `Service data table` only when a real service supplies the
   rows.
6. **Add behavior only where the BRD has a rule or integration.** Use
   `ON_LOAD` for initialization, `ON_CHANGE` for dependent visibility or
   validation, and `ON_SVCRESULT` for mapping a real Service Call result. Do
   not add arbitrary inline JavaScript, undocumented AMD dependencies, or
   copied bank scripts merely to make a view appear complex.
7. **Create role variants deliberately.** Reuse the same data contract and
   layout structure for editable and read-only variants, changing only the
   control mode, visibility, and action bar allowed for that role. This is the
   reason reference organization has separate editable and read-only views.
8. **Consume the view from a Coach.** In a Coach layout, drag the view from the
   toolkit palette or reference it as a view contribution, then map the Coach
   data to the view's declared inputs and map view outputs/events back to the
   task. Validate the view in its own toolkit snapshot before importing the
   consuming Process App.

### Human service to Coach/view wiring (verified in Workflow Center)

The reference application makes an important distinction between orchestration and
presentation:

```text
BPD user task (or human-service entry)
  -> Client-side human service
       -> Coach node / Coach page
            -> view instance (LG Issuance View)
                 -> controls bound to fields of the view business object
            -> Coach event binding (Submit / Save / Terminate)
       -> scripts, services, gateways, postpone, or end nodes
```

In the inspected `LG Issuance Human Service` the Variables tab shows `lg (LG)`
as an input and an output, alongside scalar/helper variables. The Diagram tab
contains a `Coach` form task. The Coach tab contains a root view instance with
these properties:

| Human-service Coach property | Observed value | Meaning |
|---|---|---|
| View instance control ID | `Inline_User_Task_Template` | The instance name inside this Coach page; it is not the reusable view's UUID. |
| Binding | `lg (LG)` | The Coach maps the human-service variable `tw.local.lg` to the view's declared business-data binding. |
| View | `LG Issuance View (LG)` | The reusable `coachView` selected for the instance. |
| Label visibility | `Show` | Whether the view instance's label is rendered. |

The native TWX confirms the same contract: the Coach `formTask` contains a
`ViewRef` with `viewUUID=64.d1dae7d7-4c9a-4b9b-8fa7-425955938ea6` and
`binding=tw.local.lg`. The view artifact itself declares a binding type named
`lg` for the `LG` Business Object. Its controls then bind to paths such as
`tw.businessData.lg.process.number` and
`tw.businessData.lg.initiator.requestedByUserName`. The two namespaces are
therefore intentional: `tw.local.lg` is the human-service variable, while
`tw.businessData.lg...` is the view's internal business-data context rooted at
the object supplied by that binding.

The view also declares host-supplied configuration options such as `startDate`,
`ddl`, `dateOfIssueStartDate`, `terminateVis`, and `questionsAnswers`. The
human-service `ViewRef` maps available values into those options (for example,
`tw.local.startDate`, `tw.local.ddl`, and `tw.local.questionsAnswers`). This is
separate from the main `lg` object binding: use configuration options for
auxiliary host data or switches, and use the business-data binding for the
typed request object itself.

Coach actions are executable process events, not merely UI labels. In the
reference, outgoing sequence flows from the Coach are bound as follows:

| View event path | Human-service route | Purpose |
|---|---|---|
| `Inline_User_Task_Template/Submit1` | `To Is Initiator or LG TL 2?` | Leaves the Coach and continues to the routing gateway. |
| `Inline_User_Task_Template/Save` | `To Postpone` | Saves/postpones without taking the submit route. |
| `Inline_User_Task_Template/Terminate_Button` | `To terminate` | Takes the termination path. |

This is the pattern to reproduce from a BRD: define the human-service
variables, declare the reusable view's typed binding, create a view instance in
the Coach and map the binding/configuration options, then bind each permitted
Coach action to a named sequence flow. Scripts/services before the Coach
prepare data; scripts/services and gateways after it validate, persist, route,
postpone, or terminate. Do not infer a view-to-service connection from matching
labels alone—record the actual binding path, declared view type, configuration
maps, and event-path-to-sequence-flow routes.

For a new human-service blueprint, require these fields:

```text
human_service.name
human_service.parameters (input/output/private, type, list flag)
human_service.coach.name and coach.id
human_service.coach.view_instance.control_id
human_service.coach.view_instance.view_uuid/name
human_service.coach.view_instance.binding (tw.local path -> view binding)
human_service.coach.view_instance.configuration_mappings
human_service.coach.event_routes (event path -> next node/flow)
human_service.validation, exception, postpone, and termination paths
```

The current generator can document this contract and report it from a supplied
TWX, but it does not yet serialize native `formTask`/`ViewRef`/Coach-event
wiring. Keep that portion explicit as `UNSUPPORTED` until a serializer
extension is implemented and validated on the target BAW snapshot.

The view blueprint should therefore contain: `name`, `toolkit/app scope`,
`responsive intent`, `inputs`, `outputs`, `configuration options`, `private
state`, a nested `layout` tree, a `fields` matrix, `table row schemas`, and
`behavior/integration` entries. This is the reusable design artifact that can
be generated from a BRD even when native TWX serialization is not yet enabled.

For example, a table-focused view blueprint can be expressed before native
serialization as:

```json
{
  "name": "RequestHistoryView",
  "scope": "toolkit",
  "intendedForMultipleDevices": true,
  "inputs": [
    {"name": "processHistory", "type": "ProcessHistory", "isList": true}
  ],
  "layout": [
    {"type": "panel", "label": "Process History", "children": [
      {"type": "table", "binding": "processHistory[]", "columns": [
        {"label": "Task Name", "control": "Output Text", "binding": "currentItem.taskName"},
        {"label": "Status", "control": "Output Text", "binding": "currentItem.status"},
        {"label": "Completed On", "control": "Date Time Picker", "readOnly": true, "binding": "currentItem.completedOn"}
      ]}
    ]}
  ]
}
```

This is a design contract, not a claim that the current generator can import
the JSON directly. The native TWX serializer must eventually turn it into a
`coachView` object, content-box contributions, typed variables, and view
references with fresh local IDs.

Do not confuse a **Table**, a **Table layout**, and a **Service data table**:

| Control | Meaning | Required contract |
|---|---|---|
| Table | Repeated structured rows already represented by a list | list binding, row type, column controls/bindings, label/style, paging/edit flags |
| Table layout / row / cell | Visual grid only; it does not fetch or own row data | child layout and responsive alignment; no collection binding by itself |
| Service data table | A data-provider/table control that obtains rows from a service | service flow/operation, request parameters, result-list mapping, loading/error behavior, and optional paging/selection |

The reference process-history example is a normal `Table` bound to
`tw.businessData.lg.process.processHistory[]`. Its content box contains
read-only `Output Text` columns bound to the current row, including Task Name,
Action Taken By, Status, Assigned On, Completed On, and Comment. The table
contribution itself carries a label/visibility and visual style configuration;
do not attribute options found on a nested document explorer or file control
to the table. Paging, statistics, footer, file-size, or document-version
options must be modeled only when the specific control's own contribution
contains them. A table in a new BRD should use the same shape: a typed list
Business Object plus one child control per displayed property.

The enterprise burgundy palette also exposes a `Service data table` and a `Service call`. Use
the former only when the rows are service-backed. Model the service call as a
real service-flow boundary and map its result into a typed list; do not put a
database/API URL or an invented response shape in the view. A document list or
file viewer is a different ECM/document control and should not be represented as
a generic table.

### Field-to-view decisions

Before creating a view from a BRD, build a field/collection matrix:

| BRD value | Business data shape | View control |
|---|---|---|
| Short code/name | String | Text or read-only Output Text |
| Narrative/justification | String | Text Area |
| One finite choice | String/enum | Single Select |
| Several finite choices | list of String/enum | Multi Select or Checkbox Group |
| Yes/no fact | Boolean | Checkbox |
| Count/score | Integer or Decimal | Integer/Decimal |
| Calendar date | Date | Date Time Picker |
| Repeated records | list of Business Object | Table with typed row controls |
| Lookup/service result | typed list/object | Service Call/Data/Service data table |
| Documents | document reference/list | BPM/ECM document control |

For each row record: `bindingPath`, `owner`, `input/output`, `required`,
`readOnly`, `visibility/enabled rule`, finite `options` (if applicable),
validation, and the service/event that supplies it. Group fields into a
Business Object when they share an owner, lifecycle, validation/visibility
rules, or are reused as one section; do not create an object merely because
fields happen to be adjacent. Create editable and read-only view variants when
the task roles differ, as the reference does.

### Serializer boundary

A native reusable view is more than a list of controls: it requires a
`coachView` object, nested layout/content-box contributions, view references,
variable declarations, data bindings, responsive config, and (when used)
behavior/event/script contributions. The current generator does not yet emit
that full native artifact or the source toolkit's custom views. It may use the
contract above for specifications and primitive generated Coaches, but must mark
native reusable views, Tables, Service data tables, Tabs, and rich behavior as
`UNSUPPORTED` until a serializer extension is implemented. Never claim that a
flat group of primitive controls is a reusable view or silently substitute a
String for a typed list/table.

### Native control map for generated Coaches

When the target uses the same UI Toolkit snapshot as the current generator
profile, these are the native widget identifiers observed/validated from the
reference toolkit. Keep the IDs in the generator layer; BRD authors should use
the semantic control names in the table above. If the target toolkit snapshot
differs, resolve the equivalent widget instead of copying these IDs blindly.

| Semantic control | Native UI Toolkit widget UUID | Current generator status |
|---|---|---|
| Text | `64.5663dd71-ff18-4d33-bea0-468d0b869816` | Supported |
| Text Area | `64.0e61869-73fd-4401-b156-8c11adaec3f8` | Supported |
| Output Text | `64.f634f22e-7800-4bd7-9f1e-87177acfb3bc` | Supported |
| Integer | `64.a6946c4c-f73d-4ced-9216-90018985ca96` | Supported |
| Decimal | `64.e0ede0f2-f3af-408c-af7b-e7a58eb5e2b4` | Supported |
| Date Time Picker | `64.aeae8953-9e72-411e-b35a-93c7ab827c5c` | Supported |
| Checkbox | `64.fffd1628-baee-44e8-b7ca-5ae48644b0be` | Supported |
| Single Select | `64.fd4da558-40d8-47be-92ca-c305708dc7b7` | Supported |
| Button | `64.7133c7d4-1a54-45c8-89cd-a8e8fa4a8e36` | Supported |
| Section | `64.455e44ab-b77b-4337-b3f9-435e234fb569` | Supported |
| Horizontal Layout | `64.44f463cc-615b-43d0-834f-c398a82e0363` | Supported |
| Vertical Layout | `64.ef447b87-24a2-42a7-b2b9-cd471e9f7b67` | Supported |
| Table | `64.f515b79f-fe61-4bd3-8e26-72f00155d139` (reference/UI Toolkit snapshot) | Supported for the standard generated comment-history table; arbitrary/service-backed tables still require a dedicated serializer |
| Multi Select, Checkbox Group, Data, Service Call, tabs, modal sections | Resolve from target toolkit | `UNSUPPORTED` in current serializer |

The mapping is a compatibility hint, not a license to reuse a bank's toolkit
repository objects. A generated Coach still needs a matching process variable,
binding path, required/read-only state, options, and (where applicable) event
contract. A widget UUID without those surrounding structures is not a valid
Coach implementation.

## 5. Service-flow and integration patterns

The helper-process family demonstrates reusable integration wrappers rather
than direct calls scattered through the BPD:

- SQL/DQL/DML service flows use a connector operation, an environment
  variable/connection reference, a statement object, typed parameters, and a
  mapped result collection.
- Web-service flows use a declared Web Service object and operation contract;
  the BPD sees a stable service boundary rather than transport details.
- Mail/notification flows centralize recipient lookup, templates, and send
  behavior; the reference includes a managed mail asset.
- User/team lookup flows resolve owners and recipients by team/name/NT.
- UCA/event patterns coordinate asynchronous RPA creation and validation,
  including status polling and retry/iteration handling.
- Environment variables hold database/endpoints/configuration so the process
  does not hard-code an environment-specific address.

For a new BRD, classify each integration explicitly:

| BRD evidence | Model as |
|---|---|
| Read/write external data | Service flow with a declared connector contract |
| External API or platform | Web-service/application connector boundary |
| Email/notification | Reusable notification service flow |
| Bot/queue/background worker | Message/UCA/event plus status/retry handling |
| SLA/deadline/escalation | Timer/escalation boundary and an owner/notification path |
| No real external system named | Do not invent one; use an explicit placeholder or `UNSUPPORTED` |

## 6. Theme and dependency policy

The reference project defaults point to a specific theme, XSL, CSS, and
dependency UUIDs. Those IDs are valid only when the target environment has the
same dependency snapshots. The skill should therefore:

1. Read the reference theme/defaults and record them as evidence.
2. Resolve equivalent System Data/UI Toolkit/Coaches/Responsive Coaches
   dependencies in the target environment.
3. Preserve the approved target theme by default only when its asset/dependency
   is resolvable.
4. Fail with a clear dependency mismatch or ask for an explicit mapping when
   it is not resolvable. Never silently hard-code a source repository UUID into another
   bank's TWX.

This is also why a TWX that imports on one BAW fix pack may fail on another:
native object schemas, toolkit snapshots, widget IDs, primitive class IDs,
theme references, and server configuration are all compatibility inputs.

### Portable demo theme profile

For demonstrations, reproduce the reference's visual language as a portable
theme profile rather than copying source repository UUIDs. The supplied theme
asset's CSS shows a burgundy/magenta primary palette with dark charcoal text,
a very pale blush Coach-page background, white content surfaces, light
gray/teal supporting surfaces, pale yellow highlights, and responsive
desktop/small-device values. The profile should define semantic tokens such as:

```text
primary        #870052
primaryHover   #3b0024
text           #000203
pageBackground #F7F1F4
surface        #ffffff
surfaceMuted   #c8d2d2
accent         #fde876
success        #c8f08f
danger         #ad1625
```

Use these tokens for generated Coach CSS/theme assets and keep the tokens
independent of BAW object IDs. If a target BAW requires a native Theme object,
package the generated asset and resolve its dependency normally; do not point
`defaultTheme` at the reference's `1f371aed.../72...` reference unless that dependency is
actually present. The token profile is only the visual layer. The native Theme
must also contain the complete compile-time variable contract from
`assets/enterprise-burgundy-baw-8.6.11-theme.less`; a small palette-only source is not
a valid replacement.

### Reference Integration Toolkit theme inspected in Workflow Center

The supplied process was opened in Workflow Center with the editor selector set
to **Reference Theme (Read-only)**. The theme is exposed through the dependency
`Reference Integration Toolkit (Reference Integration Toolkit_27.11.2023_V0.2)`, not as a theme object
owned by the `LG Issuance` process application. The process application's
`projectDefaults` points its `defaultTheme` to the Reference Integration Toolkit dependency
and includes a managed ZIP asset containing the compiled Coach CSS files. This
is why the theme cannot be made portable by copying only the process XML or by
copying the source repository UUIDs.

Archive evidence for that bundle is the process-app managed asset
`61.fc3d4ff8-a76a-47ac-994f-e619425b5527` (asset UUID
`d5c0c405-c15e-4ca8-ab41-d2407ca3778b`). Its nested ZIP contains
`bpmCoachFmk/less/coach_ng_theme.css`, `bpmUI.css`, `content.css`,
`scripts/controls.css`, and `workplace.css`. The native theme object itself is
still resolved from Reference Integration Toolkit through `defaultTheme`; the managed asset
alone is not proof that a process app owns the Theme object.

The visible Theme Design values captured from the reference organization theme are:

| Theme variable | Observed value |
|---|---|
| `@bpm-neutral-darkest` | `#0d1111` |
| `@bpm-neutral-darker` | `#2d3737` |
| `@bpm-neutral-dark` | `#c8d2d2` |
| `@bpm-neutral` | `#586464` |
| `@bpm-neutral-light` | `#6d7777` |
| `@bpm-neutral-lighter` | `#c8d2d2` |
| `@bpm-neutral-lightest` | `#dfe9e9` |
| `@bpm-color-primary` | `#870052` |
| `@bpm-color-info` | `#989898` |
| `@bpm-color-success` | `#c8f08f` |
| `@bpm-color-warning` | `#fde876` |
| `@bpm-color-alert` | `#ad1625` |
| `@bpm-body-bg` | `#fff` |
| `@bpm-fill-darker` | `#586464` |
| `@bpm-fill-normal` | `#fff` |
| `@bpm-text-color` | `#000203` |
| `@bpm-font-family-sans-serif` | `"Helvetica Neue", Helvetica, Arial, sans-serif` |
| `@bpm-font-size-base` | `14px` |
| `@bpm-line-height-base` | `1` |
| `@bpm-padding-base-vertical` / `horizontal` | `6px` / `12px` |
| `@bpm-padding-small-vertical` / `horizontal` | `5px` / `10px` |
| `@bpm-border-radius-base` / `large` / `small` | `0px` / `0px` / `0px` |
| `@bpm-active-color` | `#fff` |
| `@bpm-active-bg` | `@bpm-color-primary` |
| `@bpm-link-color` | `@bpm-color-primary` |
| `@bpm-list-group-bg` | `@bpm-body-bg` |
| `@bpm-list-group-border` | `@bpm-neutral-lightest` |

The theme also defines derived light/dark states with LESS functions (for
example `lighten(@bpm-color-success, 9%)` and
`darken(desaturate(spin(@bpm-color-primary, -5), 1%), 9%)`). Preserve those
relationships when a native theme serializer is available; flattening only the
base colors can produce visibly different hover, focus, and validation states.
The Workflow Center preview showed standard themed controls for text, integer,
decimal, text area, type-ahead, multi-select, single-select, buttons, radio
groups, checkboxes, date/time, switches, badges, notifications, sliders,
progress indicators, notes, and signatures.

### Self-contained theme generation policy

The portable target is a **new companion Theme toolkit** plus a process app,
both with fresh repository IDs and the approved design tokens. It must contain:

1. a native Theme object owned by the companion toolkit;
2. the complete BAW 8.6.11-compatible Theme source, not only palette tokens;
3. a process-app dependency on the generated toolkit snapshot;
4. a `projectDefaults/defaultTheme` reference whose dependency UUID and Theme
   object ID match the companion toolkit; and
5. package entries whose IDs remain internally consistent.

The current serializer writes one self-contained `<app>.twx`. Its generated
Theme toolkit snapshot is nested at `toolkits/<snapshot-id>.zip`, matching the
one-file export structure observed in a working Traditional BAW application.
The outer process app declares the same toolkit project and snapshot as a
dependency. It uses the complete inspected BAW 8.6.11 Theme source as the
compatibility template and overlays the portable profile using LESS's lazy
variable resolution. Structural validation checks representative Theme symbols
and rejects suspiciously small, palette-only sources. Target import and runtime
Coach rendering remain required compatibility checks. Never copy source
repository UUIDs or organization-specific names.

Runtime evidence from the first app-local Theme build is important: Workflow
Center listed and selected the generated Theme, but opening its Design preview
failed with `variable @bpm-border-normal is undefined` at
`.patch-spark-vars()`. The Coach then displayed the misleading banner that no
theme was set. This proves that Theme selection metadata alone is insufficient;
the embedded LESS must compile against the target BAW/UI Toolkit version. A
later build contained complete LESS and was selectable in Designer, yet the
runtime still rejected the app-local Theme. Comparing with a known-working LG
application showed that runtime Theme resolution is dependency-based, which is
why the serializer now emits the Theme in a companion toolkit.

## 7. BRD-to-process reasoning checklist

When generalizing the reference design, use this decision table:

- **Human judgment/approval** → standalone native User Task plus separate
  Human Service/Coach.
- **Deterministic validation or mapping** → Script Task.
- **Mutually exclusive outcomes** → Exclusive gateway with explicit conditions.
- **Independent reviews** → Parallel split and explicit convergence.
- **External state or persistence** → Service Task/linked service flow.
- **Asynchronous bot/queue** → Message/UCA handoff, state polling, failure and
  retry paths.
- **Return/correction** → Preserve data/history and route directly to the
  previous editable task.
- **Deadline/escalation** → Timer/SLA and notification/escalation service.
- **Reusable field group** → Business Object or nested Information object.
- **Repeated dynamic values** → List or reusable NameValuePair-style object.
- **Role ownership** → Lane plus participant/team mapping.

For every gateway, write down: question, input variables, exact branch
conditions, default/unknown handling, and the owner who can resolve an
ambiguous case. For every service boundary, write down: input contract, output
contract, error behavior, environment configuration, and whether the call is
synchronous or asynchronous.

## 8. Complexity and portability gates

A new application is at the reference's *design-complexity level* only when
the approved specification accounts for the required data groups, role lanes,
human/automated boundaries, integration contracts, gateway conditions,
notifications, escalations, rework, and failure/retry behavior. A high node
count alone is not evidence of quality.

Before generation, require:

- target BAW product/version/fix pack and runtime (Traditional/tWAS or other);
- resolvable toolkit and dependency snapshots;
- participant/team mapping;
- environment variable names and connector contracts;
- external API/database/RPA schemas and ownership;
- theme policy and any required assets;
- approved Coach field/data/event contract.

If the current serializer cannot represent a requested native object, record
`UNSUPPORTED` in the specification and stop at the appropriate approval gate.
Do not claim “same complexity” when only the BPD skeleton was produced.
