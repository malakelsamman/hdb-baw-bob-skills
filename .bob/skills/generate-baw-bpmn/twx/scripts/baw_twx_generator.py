#!/usr/bin/env python3
"""
twx_generator.py — Traditional IBM BAW TWX builder for the current generator
profile (the emitted package metadata currently targets Traditional BAW 8.6.11
fix pack 26000; it is not automatically portable to another BAW release).

Usage:
    from twx_generator import ProcessSpec, LaneSpec, HumanTaskSpec, ServiceTaskSpec, FieldSpec, build_twx
    spec = ProcessSpec(...)
    build_twx(spec)

Or run directly:
    python3 baw_twx_generator.py
"""

import json
import hashlib
import io
import os
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from xml.sax.saxutils import escape

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
# Validated Traditional IBM BAW 8.6.11 / fixPack 26000 dependency identifiers.
# These constants target the standard System Data and UI Toolkit 8.6.0.0 dependencies.
SYSDATA_DEP_ID   = "2069.be4e6820-a438-4c96-a64d-37fb2ce6067a"   # from v2-coach package.xml
SYSDATA_PROJ_ID  = "2066.1b351583-e5cb-43b7-baee-340a63130ea7"
SYSDATA_BR_ID    = "2063.0798815e-0346-4ef4-8946-ab4301c9f340"
SYSDATA_SNAP_ID  = "2064.1080ded6-d153-4654-947c-2d16fce170ed"   # ...170ed (traditional)
SYSDATA_SNAP_NM  = "8.6.0.0"
UITK_DEP_ID      = "2069.7e229b41-763c-4c57-835d-9055b4ad0e81"   # from v2-coach package.xml
UITK_PROJ_ID     = "2066.ec5973da-aebe-40f6-aa02-a77962288f52"
UITK_BR_ID       = "2063.83ee2bb2-72b4-4a4d-b8ae-37ecd983c05e"
UITK_SNAP_ID     = "2064.304ac881-16c3-47d2-97d5-6e4c4a893177"
UITK_SNAP_NM     = "8.6.0.0"
# The dep UUID suffix (without "2069.") used in projectDefaults XSL/CSS/theme refs
SYSDATA_DEP_UUID = "be4e6820-a438-4c96-a64d-37fb2ce6067a"

# UI Toolkit widget UUIDs
W_TEXT_INPUT = "64.5663dd71-ff18-4d33-bea0-468d0b869816"
W_TEXT_AREA  = "64.0e61869e-73fd-4401-b156-8c11adaec3f8"
W_OUTPUT     = "64.f634f22e-7800-4bd7-9f1e-87177acfb3bc"
W_BUTTON     = "64.7133c7d4-1a54-45c8-89cd-a8e8fa4a8e36"
# UI Toolkit 8.6.0.0: Checkbox (Boolean) and Single Select (finite choices).
W_CHECKBOX   = "64.fffd1628-baee-44e8-b7ca-5ae48644b0be"
W_SINGLE_SELECT = "64.fd4da558-40d8-47be-92ca-c305708dc7b7"
W_DECIMAL    = "64.e0ede0f2-f3af-408c-af7b-e7a58eb5e2b4"
W_SECTION    = "64.455e44ab-b77b-4337-b3f9-435e234fb569"
W_HORIZONTAL = "64.44f463cc-615b-43d0-834f-c398a82e0363"
W_VERTICAL   = "64.ef447b87-24a2-42a7-b2b9-cd471e9f7b67"
W_INTEGER    = "64.a6946c4c-f73d-4ced-9216-90018985ca96"
W_DATE       = "64.aeae8953-9e72-411e-b35a-93c7ab827c5c"
# UI Toolkit Table layout widget (validated from the reference Traditional
# BAW Coach export).  A table's row controls are nested Output Text views.
W_TABLE      = "64.f515b79f-fe61-4bd3-8e26-72f00155d139"

# System Data primitive classIds (with leading slash + guid prefix)
SYSDATA_BOOL   = f"{SYSDATA_DEP_UUID}/12.83ff975e-8dbc-42e5-b738-fa8bc08274a2"
SYSDATA_STRING = f"{SYSDATA_DEP_UUID}/12.db884a3c-c533-44b7-bb2d-47bec8ad4022"
SYSDATA_INT    = f"{SYSDATA_DEP_UUID}/12.3fa0d7a0-828a-4d60-99cc-db5ed143fc2d"
SYSDATA_DECIMAL= f"{SYSDATA_DEP_UUID}/12.536b2aa5-a30f-4eca-87fa-3a28066753ee"
SYSDATA_DATE   = f"{SYSDATA_DEP_UUID}/12.68474ab0-d56f-47ee-b7e9-510b45a2a8be"


def u() -> str:
    """Generate a fresh UUID4 string."""
    return str(uuid.uuid4())

def pid(base: str) -> str:
    """Make a process-object id like 2025.<uuid>"""
    return f"2025.{base}"

# ─── SPEC DATA CLASSES ────────────────────────────────────────────────────────
@dataclass
class FieldSpec:
    name: str
    label: str
    field_type: str = "String"   # String | Integer | Decimal | Boolean | Date
    required: bool = False
    read_only: bool = False
    is_output: bool = False
    hidden: bool = False
    # Optional finite choices. Each item may be {"value": stored,
    # "label": displayed} or native {"name": stored, "value": displayed}.
    options: List[dict] = field(default_factory=list)
    placeholder: str = ""

@dataclass
class HumanTaskSpec:
    name: str
    lane: str
    fields: List[FieldSpec] = field(default_factory=list)
    submit_buttons: List[str] = field(default_factory=lambda: ["Submit"])
    # Multi-action approval/review Coaches write the clicked action here.
    decision_output: Optional[str] = None
    # Optional label -> business value override.
    action_values: Dict[str, str] = field(default_factory=dict)
    # Native CSHS parameter directions.
    input_names: List[str] = field(default_factory=list)
    output_names: List[str] = field(default_factory=list)
    # Optional shared append-only history table.  The corresponding process
    # variable is a native list Business Object, not a flattened String.
    comment_history: Optional[dict] = None
    # Every generated Coach gets a standard UI-only Close action. It ends the
    # standalone human service just like choosing "End the human service" in
    # the BAW Coach Flow editor; it is not a business decision or a Return
    # gateway branch.
    include_close: bool = True

@dataclass
class ServiceTaskSpec:
    name: str
    lane: str

@dataclass
class GatewaySpec:
    name: str
    lane: str
    gateway_type: str = "exclusive"   # exclusive | parallel

@dataclass
class LaneSpec:
    name: str

@dataclass
class FlowSpec:
    name: str
    source: str   # task/gateway name
    target: str   # task/gateway name
    condition: str = ""

@dataclass
class ProcessSpec:
    name: str
    short_name: str
    output_filename: str
    lanes: List[LaneSpec]
    human_tasks: List[HumanTaskSpec] = field(default_factory=list)
    service_tasks: List[ServiceTaskSpec] = field(default_factory=list)
    gateways: List[GatewaySpec] = field(default_factory=list)
    flows: List[FlowSpec] = field(default_factory=list)
    description: str = ""

# ─── XML BUILDERS ─────────────────────────────────────────────────────────────

def _field_class_id(ft: str) -> str:
    m = {
        "String":  SYSDATA_STRING,
        "Boolean": SYSDATA_BOOL,
        "Integer": SYSDATA_INT,
        "Decimal": SYSDATA_DECIMAL,
        "Date":    SYSDATA_DATE,
    }
    return m.get(ft, SYSDATA_STRING)


def _is_collection_meta(meta: dict) -> bool:
    return str(meta.get("type") or "") == "CommentHistoryList"


def _meta_class_id(meta: dict) -> str:
    """Qualified class id for a process variable, including the local history BO."""
    if _is_collection_meta(meta):
        return str(meta.get("class_id") or "")
    return _field_class_id(meta.get("type", "String"))


def _meta_item_subject_ref(meta: dict) -> str:
    if _is_collection_meta(meta):
        return str(meta.get("item_subject_ref") or "")
    return _item_subject_ref(meta.get("type", "String"))


def _native_variable_class_uuid(ft: str) -> str:
    """
    Return the bare primitive class UUID required by the native
    TWProcessVariable.classId field.

    Other BAW representations in this generator legitimately use values such as:
        <dependency-uuid>/12.<primitive-uuid>
    or:
        itm.12.<primitive-uuid>

    TWProcessVariableAutoGen, however, parses classId as a UUID. Passing the
    dependency-qualified form causes:
        Invalid UUID string '<dependency-uuid>/12.<primitive-uuid>'
    during TWX import.
    """
    qualified = _field_class_id(ft)
    primitive = qualified.split("/")[-1]       # 12.<uuid>
    bare = primitive.split(".", 1)[-1]         # <uuid>
    # Fail locally if a future mapping is malformed.
    uuid.UUID(bare)
    return bare

def _widget_uuid(ft: str, read_only: bool, options=None) -> str:
    if read_only:
        return W_OUTPUT
    if options and ft != "Boolean":
        return W_SINGLE_SELECT
    m = {
        "String":  W_TEXT_INPUT,
        "Integer": W_INTEGER,
        "Decimal": W_DECIMAL,
        "Boolean": W_CHECKBOX,
        "Date":    W_DATE,
    }
    return m.get(ft, W_TEXT_INPUT)


def _cfg(option_name: str, value) -> dict:
    if isinstance(value, bool):
        value = str(value).lower()
    return {
        "declaredType": "com.ibm.bpmsdk.model.coach.ConfigData",
        "id": u(),
        "optionName": option_name,
        "value": str(value),
    }


def _responsive_value(large: str, small: str) -> str:
    return json.dumps(
        {
            "isResponsiveData": True,
            "values": [
                {"deviceConfigID": "LargeID", "value": large},
                {"deviceConfigID": "SmallID", "value": small},
            ],
        },
        separators=(",", ":"),
    )


def _content_box(children: List[dict]) -> dict:
    return {
        "contributions": children,
        "contentBoxId": "ContentBox1",
        "declaredType": "com.ibm.bpmsdk.model.coach.ContentBoxContrib",
        "id": u(),
    }


def _container(view_uuid: str, layout_id: str, children: List[dict],
               label: str = "", horizontal: bool = False) -> dict:
    cfg = [
        _cfg("@label", label or layout_id),
        _cfg("@labelVisibility", "SHOW" if view_uuid == W_SECTION else "HIDE"),
    ]
    if view_uuid == W_SECTION:
        cfg.append(_cfg("colorStyle", "P"))
    else:
        cfg.append(_cfg("layoutFlow", _responsive_value("P" if horizontal else "V", "V")))
    return {
        "contentBoxContrib": [_content_box(children)],
        "layoutItemId": layout_id,
        "configData": cfg,
        "viewUUID": view_uuid,
        "declaredType": "com.ibm.bpmsdk.model.coach.ViewRef",
        "id": u(),
        "version": "8550",
    }


def _field_is_long(field_spec: FieldSpec) -> bool:
    text = (field_spec.name + " " + field_spec.label).lower()
    return any(k in text for k in (
        "comment", "reason", "note", "remark", "justification", "description",
        "details", "summary", "message", "history", "result"
    ))


def _normalise_select_options(options) -> list:
    """Return native UI Toolkit Single Select NameValuePair objects."""
    result = []
    for option in options or []:
        if isinstance(option, dict):
            if "name" in option and "value" in option:
                stored, display = option["name"], option["value"]
            elif "value" in option:
                stored = option["value"]
                display = option.get("label", option["value"])
            else:
                raise ValueError("Select option objects require value (and optional label)")
        else:
            stored = display = option
        result.append({"name": stored, "value": display})
    return result


def _field_view_item(field_spec: FieldSpec) -> dict:
    if field_spec.read_only:
        widget = W_OUTPUT
    elif _field_is_long(field_spec) and field_spec.field_type == "String":
        widget = W_TEXT_AREA
    else:
        widget = _widget_uuid(field_spec.field_type, False, field_spec.options)
    width = "100%" if _field_is_long(field_spec) else "49%"
    config = [
        _cfg("@label", field_spec.label),
        _cfg("@helpText", ""),
        _cfg("@labelVisibility", "SHOW"),
        _cfg("@required", field_spec.required),
        _cfg("@width", _responsive_value(width, "100%")),
    ]
    if field_spec.options and not field_spec.read_only and field_spec.field_type != "Boolean":
        config.extend([
            _cfg("itemLookupMode", "L"),
            _cfg("staticList", json.dumps(_normalise_select_options(field_spec.options), ensure_ascii=False)),
            _cfg("placeHolder", field_spec.placeholder or f"Select {field_spec.label}"),
        ])
    return {
        "layoutItemId": field_spec.name,
        "configData": config,
        "viewUUID": widget,
        "binding": f"tw.local.{field_spec.name}",
        "declaredType": "com.ibm.bpmsdk.model.coach.ViewRef",
        "id": u(),
        "version": "8550",
    }


def _history_table_item(history: dict) -> dict:
    """Build a native read-only Table bound to a list Business Object.

    The shape follows the table exported by the reference BAW application:
    the Table owns a content box whose contributions are Output Text widgets
    bound to ``currentItem.<field>``.  The generator deliberately keeps the
    row schema in the contract so a bank can change columns without changing
    the serializer code.
    """
    variable = str(history.get("variable_name") or history.get("name") or "commentHistory")
    label = str(history.get("label") or "Comment history")
    columns = history.get("columns") or []
    if not columns:
        columns = [
            {"field": "occurredAt", "label": "Date", "width": "20%"},
            {"field": "action", "label": "Action", "width": "20%"},
            {"field": "comment", "label": "Comment", "width": "60%"},
        ]
    children = []
    for col in columns:
        field_name = str(col.get("field") or col.get("name") or "").strip()
        if not field_name:
            continue
        column_label = str(col.get("label") or field_name)
        children.append({
            "layoutItemId": f"History_{field_name}",
            "configData": [
                _cfg("@label", column_label),
                _cfg("@helpText", ""),
                _cfg("@labelVisibility", "SHOW"),
                _cfg("@width", _responsive_value(str(col.get("width") or "100%"), "100%")),
            ],
            "viewUUID": W_OUTPUT,
            "binding": f"tw.local.{variable}.currentItem.{field_name}",
            "declaredType": "com.ibm.bpmsdk.model.coach.ViewRef",
            "id": u(),
            "version": "8550",
        })
    return {
        "layoutItemId": str(history.get("layout_id") or "CommentHistoryTable"),
        "configData": [
            _cfg("@label", label),
            _cfg("@helpText", "Read-only record of previous actions and comments."),
            _cfg("@labelVisibility", "SHOW"),
            _cfg("@width", _responsive_value("100%", "100%")),
        ],
        "viewUUID": W_TABLE,
        "binding": f"tw.local.{variable}[]",
        "contentBoxContrib": [_content_box(children)],
        "declaredType": "com.ibm.bpmsdk.model.coach.ViewRef",
        "id": u(),
        "version": "8550",
    }


def _rows_for_fields(fields: List[FieldSpec]) -> List[dict]:
    rows = []
    pending = []
    for field_spec in fields:
        item = _field_view_item(field_spec)
        if _field_is_long(field_spec):
            if pending:
                rows.append(_container(W_HORIZONTAL, f"Row{len(rows)+1}", pending, horizontal=True))
                pending = []
            rows.append(item)
            continue
        pending.append(item)
        if len(pending) == 2:
            rows.append(_container(W_HORIZONTAL, f"Row{len(rows)+1}", pending, horizontal=True))
            pending = []
    if pending:
        # One remaining normal field is full width.
        pending[0]["configData"] = [
            c for c in pending[0].get("configData", []) if c.get("optionName") != "@width"
        ] + [_cfg("@width", _responsive_value("100%", "100%"))]
        rows.append(pending[0])
    return rows


def _professional_layout(task: HumanTaskSpec, flat_items: List[dict]) -> List[dict]:
    """Build a generic client-demo Coach layout without use-case-specific code."""
    by_id = {x.get("layoutItemId"): x for x in flat_items}
    fields = [f for f in task.fields if not getattr(f, "hidden", False)]
    choice_fields = [
        f for f in fields
        if not f.read_only and bool(f.options) and f.field_type != "Boolean"
    ]
    boolean_fields = [f for f in fields if not f.read_only and f.field_type == "Boolean"]
    editable = [
        f for f in fields
        if not f.read_only and not _field_is_long(f)
        and f not in choice_fields and f not in boolean_fields
    ]
    # Finite decision-support fields are still user-entered request data. Keep
    # them in Request Details, after ordinary editable fields and before the
    # Yes/No and Comments sections; do not isolate them in a trailing section.
    request_fields = editable + choice_fields
    readonly = [f for f in fields if f.read_only]
    long_fields = [f for f in fields if _field_is_long(f) and not f.read_only]

    sections = []
    # Coach reading order is intentional: show prior context first, then all
    # data this actor must enter (including finite decision-support choices),
    # then Boolean checks, comments, and finally the action bar.
    if readonly:
        sections.append(
            _container(
                W_SECTION, "ReferenceInformation",
                [_container(W_VERTICAL, "ReferenceInformationBody", _rows_for_fields(readonly))],
                label="Reference Information",
            )
        )
    if request_fields:
        sections.append(
            _container(
                W_SECTION, "RequestDetails",
                [_container(W_VERTICAL, "RequestDetailsBody", _rows_for_fields(request_fields))],
                label="Request Details",
            )
        )
    if boolean_fields:
        sections.append(
            _container(
                W_SECTION, "BooleanChecks",
                [_container(W_VERTICAL, "BooleanChecksBody", _rows_for_fields(boolean_fields))],
                label="Yes / No Checks",
            )
        )
    # History is deliberately placed at the end of the context area, directly
    # above the single current Comments & Notes field.  It is a read-only audit
    # trail; the draft below it is the only editable comment control.
    if task.comment_history:
        history_item = next(
            (x for x in flat_items if x.get("layoutItemId") == "CommentHistoryTable"),
            _history_table_item(task.comment_history),
        )
        sections.append(
            _container(
                W_SECTION, "CommentHistory", [history_item], label=str(task.comment_history.get("label") or "Comment history"),
            )
        )
    if long_fields:
        sections.append(
            _container(
                W_SECTION, "CommentsNotes",
                [_container(W_VERTICAL, "CommentsNotesBody", _rows_for_fields(long_fields))],
                label="Comments & Notes",
            )
        )
    ui_actions = list(task.submit_buttons)
    if task.include_close and not any(str(x).strip().lower() == "close" for x in ui_actions):
        ui_actions.append("Close")
    buttons = []
    destructive = {"cancel", "reject", "return", "back", "close"}
    primary_index = next(
        (i for i, label in enumerate(ui_actions)
         if label.strip().lower() not in destructive),
        0,
    )
    count = max(1, len(ui_actions))
    large_width = "49%" if count == 2 else ("32%" if count == 3 else "24%" if count == 4 else "100%")
    for i, label in enumerate(ui_actions):
        bid = label.lower().replace(" ", "_") + "button"
        item = dict(by_id[bid])
        cfg = [dict(c) for c in item.get("configData", [])]
        cfg += [
            _cfg("@labelVisibility", "SHOW"),
            _cfg("@width", _responsive_value(large_width, "100%")),
            _cfg("preventMultipleClicks", "true"),
        ]
        if i == primary_index:
            cfg.append(_cfg("colorStyle", "P"))
        elif label.strip().lower() in {"reject", "cancel", "delete"}:
            cfg.append(_cfg("colorStyle", "D"))
        else:
            cfg.append(_cfg("colorStyle", "S"))
        item["configData"] = cfg
        item["version"] = "8550"
        buttons.append(item)

    sections.append(_container(W_HORIZONTAL, "ActionButtons", buttons, label="Actions", horizontal=True))
    return sections


def build_cshs_json(task: HumanTaskSpec, proc_id: str) -> str:
    """Build a responsive CSHS Coach.

    For approval/review tasks, each action button routes through a server-side
    script that writes the selected action to the CSHS decision output before
    End. The normal CSHS output mapping then persists it to the BPD variable.
    """
    start_id = u()
    coach_id = f"2025.{u()}"
    end_id = u()
    sf_start_coach = f"2027.{u()}"

    flat_items = [
        _field_view_item(field_spec)
        for field_spec in task.fields
        if not getattr(field_spec, "hidden", False)
    ]
    if task.comment_history:
        flat_items.append(_history_table_item(task.comment_history))

    # (button layout id, button flow id, label, script id, script->end flow, value)
    button_routes = []
    ui_actions = list(task.submit_buttons)
    if task.include_close and not any(str(x).strip().lower() == "close" for x in ui_actions):
        ui_actions.append("Close")
    for label in ui_actions:
        bid = label.lower().replace(" ", "_") + "button"
        click_sf = f"2027.{u()}"
        flat_items.append({
            "layoutItemId": bid,
            "configData": [_cfg("@label", label)],
            "viewUUID": W_BUTTON,
            "declaredType": "com.ibm.bpmsdk.model.coach.ViewRef",
            "id": u(),
            "version": "8550",
        })
        action_value = task.action_values.get(label, label)
        # Close is a standard UI-only End-the-human-service action. Do not
        # write it into a business decision variable or require a BPD branch;
        # business actions (Submit/Return/etc.) still use their decision
        # output and direct BPD sequence flows.
        is_close = label.strip().lower() == "close"
        # A history-enabled Coach needs a server-side script even when it has
        # only one business action; the script appends the row before End.
        script_id = f"2025.{u()}" if (task.decision_output or task.comment_history) and not is_close else None
        script_end_sf = f"2027.{u()}" if script_id else None
        button_routes.append((bid, click_sf, label, script_id, script_end_sf, action_value))

    layout_items = _professional_layout(task, flat_items)
    coach_outgoing = [x[1] for x in button_routes]

    flow_elements = [
        {
            "parallelMultiple": False,
            "outgoing": [sf_start_coach],
            "isInterrupting": True,
            "extensionElements": {"nodeVisualInfo": [{
                "color": "#F8F8F8", "width": 24, "x": 50, "y": 200,
                "declaredType": "TNodeVisualInfo", "height": 24
            }]},
            "name": "Start", "declaredType": "startEvent", "id": start_id,
        },
        {
            "outgoing": coach_outgoing,
            "incoming": [sf_start_coach],
            "extensionElements": {
                "nodeVisualInfo": [{
                    "width": 95, "x": 350, "y": 177,
                    "declaredType": "TNodeVisualInfo", "height": 70
                }],
                "validationStayOnPagePaths": [button_routes[0][0]] if button_routes else ["submitbutton"],
            },
            "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TFormTask",
            "isHeritageCoach": False,
            "cachePage": False,
            "startQuantity": 1,
            "formDefinition": {
                "coachDefinition": {
                    "layout": {"layoutItem": layout_items},
                    "declaredType": "com.ibm.bpmsdk.model.coach.TCoachDefinition",
                }
            },
            "commonLayoutArea": 0,
            "name": task.name,
            "isForCompensation": False,
            "completionQuantity": 1,
            "id": coach_id,
        },
        {
            "incoming": [],
            "extensionElements": {
                "nodeVisualInfo": [{
                    "color": "#F8F8F8", "width": 24, "x": 700, "y": 200,
                    "declaredType": "TNodeVisualInfo", "height": 24
                }],
                "navigationInstructions": [{
                    "targetType": "Default",
                    "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TNavigationInstructions"
                }],
            },
            "name": "End", "declaredType": "endEvent", "id": end_id,
        },
        {
            "targetRef": coach_id,
            "extensionElements": {"linkVisualInfo": [{
                "sourcePortLocation": "rightCenter",
                "showCoachControlLabel": False,
                "labelPosition": 0.0,
                "targetPortLocation": "leftCenter",
                "declaredType": "TLinkVisualInfo",
                "saveExecutionContext": False,
                "showLabel": False,
            }]},
            "name": "To coach", "declaredType": "sequenceFlow",
            "id": sf_start_coach, "sourceRef": start_id,
        },
    ]

    end_incoming = []
    for idx, (bid, click_sf, label, script_id, script_end_sf, action_value) in enumerate(button_routes):
        target = script_id or end_id
        flow_elements.append({
            "targetRef": target,
            "extensionElements": {
                "coachEventBinding": [{
                    "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TCoachEventBinding",
                    "id": u(), "coachEventPath": bid
                }],
                "sequenceFlowImplementation": [{
                    "fireValidation": "Never", "sboSyncEnabled": True,
                    "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TSequenceFlowImplementation"
                }],
                "linkVisualInfo": [{
                    "sourcePortLocation": "rightCenter",
                    "showCoachControlLabel": True,
                    "labelPosition": 0.0,
                    "targetPortLocation": "leftCenter",
                    "declaredType": "TLinkVisualInfo",
                    "saveExecutionContext": True,
                    "showLabel": False,
                }],
            },
            "name": f"Action ({label})",
            "declaredType": "sequenceFlow",
            "id": click_sf, "sourceRef": coach_id,
        })

        if script_id:
            script_lines = []
            history = task.comment_history or {}
            if history and label.strip().lower() != "close":
                variable = str(history.get("variable_name") or history.get("name") or "commentHistory")
                entry_type = str(history.get("entry_type") or history.get("class_name") or "CommentHistoryEntry")
                draft = str(history.get("draft_variable") or "")
                # No actor/recipient facts are invented.  The contract may
                # provide expressions or an explicit per-action recipient;
                # otherwise the generated row leaves that column blank for a
                # later mapping decision while still preserving the event.
                # Client-side human services run in the browser.  Their
                # JavaScript API exposes user_loginName/user_id rather than
                # the server-side userName property.
                from_actor = str(
                    history.get("from_actor_expression")
                    or "tw.system.user_loginName"
                )
                to_actor = (history.get("to_actor_by_action") or {}).get(label, history.get("to_actor_expression", ""))
                to_coach = (history.get("to_coach_by_action") or {}).get(label, history.get("to_coach", ""))
                def _js_value(value):
                    text = str(value or "")
                    return text if text.startswith("tw.") else json.dumps(text, ensure_ascii=False)
                to_coach_literal = json.dumps(str(to_coach or ""), ensure_ascii=False)
                # This is a *client-side* script.  IBM BAW requires standard
                # JavaScript literals for complex values here; tw.object and
                # TWObject list helpers exist only in server-side scripts.
                # The declared CSHS variable type supplies the BO/list schema
                # when the plain object array is serialized back to the BPD.
                script_lines.extend([
                    f"if (!Array.isArray(tw.local.{variable})) tw.local.{variable} = [];",
                    "var historyEntry = {};",
                    "historyEntry.occurredAt = new Date();",
                    f"historyEntry.fromActor = {_js_value(from_actor)};",
                    f"historyEntry.toActor = {_js_value(to_actor)};",
                    f"historyEntry.fromCoach = {json.dumps(task.name, ensure_ascii=False)};",
                    f"historyEntry.toCoach = {to_coach_literal};",
                    f"historyEntry.action = {json.dumps(str(action_value), ensure_ascii=False)};",
                    f"historyEntry.comment = tw.local.{draft};" if draft else "historyEntry.comment = \"\";",
                    f"tw.local.{variable}.push(historyEntry);",
                ])
                if draft:
                    script_lines.append(f"tw.local.{draft} = \"\";")
            if task.decision_output:
                script_lines.append(
                    f"tw.local.{task.decision_output} = "
                    + json.dumps(str(action_value), ensure_ascii=False)
                    + ";"
                )
            script_text = "\n".join(script_lines)
            flow_elements.append({
                "incoming": [click_sf],
                "outgoing": [script_end_sf],
                "startQuantity": 1,
                "default": script_end_sf,
                "extensionElements": {"nodeVisualInfo": [{
                    "x": 520, "width": 95, "y": 80 + idx * 90,
                    "declaredType": "TNodeVisualInfo", "height": 70
                }]},
                "name": ("Client-side script" if idx == 0 else f"Client-side script {idx}"),
                "isForCompensation": False,
                "completionQuantity": 1,
                "declaredType": "scriptTask",
                "id": script_id,
                "scriptFormat": "text/x-javascript",
                "script": {"content": [script_text]},
            })
            flow_elements.append({
                "targetRef": end_id,
                "extensionElements": {"linkVisualInfo": [{
                    "sourcePortLocation": "rightCenter",
                    "showCoachControlLabel": False,
                    "labelPosition": 0.0,
                    "targetPortLocation": "leftCenter",
                    "declaredType": "TLinkVisualInfo",
                    "saveExecutionContext": True,
                    "showLabel": False,
                }]},
                "name": f"Complete ({label})",
                "declaredType": "sequenceFlow",
                "id": script_end_sf, "sourceRef": script_id,
            })
            end_incoming.append(script_end_sf)
        else:
            end_incoming.append(click_sf)

    flow_elements[2]["incoming"] = end_incoming

    root = {
        "rootElement": [{
            "extensionElements": {
                "userTaskImplementation": [{
                    "flowElement": flow_elements,
                    "htmlHeaderTag": [{
                        "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.THtmlHeaderTag",
                        "id": u(), "tagName": "viewport",
                        "content": "width=device-width,initial-scale=1.0", "enabled": True
                    }],
                    "isClosed": False,
                    "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TUserTaskImplementation",
                    "id": u(), "processType": "None",
                }],
                "exposedAs": ["NotExposed"],
                "isShadow": [True],
            },
            "implementation": "##unspecified",
            "documentation": [{"content": [], "textFormat": "text/plain"}],
            "name": task.name,
            "declaredType": "globalUserTask",
            "id": proc_id,
            "ioSpecification": {
                "inputSet": [{"id": f"_{u()}"}],
                "outputSet": [{"id": f"_{u()}"}]
            },
        }],
        "targetNamespace": "",
        "typeLanguage": "http://www.w3.org/2001/XMLSchema",
        "expressionLanguage": "http://www.ibm.com/xmlns/prod/bpm/expression-lang/javascript",
        "id": u(),
    }
    return json.dumps(root, separators=(",", ":"))


def build_cshs_xml(task: HumanTaskSpec, proc_id: str, version_id: str) -> str:
    """Build the full XML for a CSHS process object.

    Validated native CSHS structure has ZERO
    processParameter / processVariable elements on CSHS (processType=10) objects.
    All field bindings live exclusively inside <jsonData> JSON.
    Adding processVariable to a CSHS causes java.lang.NullPointerException on import.
    """
    ts = "1786377516000"
    json_data = escape(build_cshs_json(task, proc_id))
    coach_wrap_id  = f"2025.{u()}"
    end_item_id    = f"2025.{u()}"
    start_item_id  = coach_wrap_id
    # Each CSHS gets its own unique ExitPoint and CoachFlow component IDs.
    # Sharing the same tWComponentId across multiple CSHS objects causes NPE on import.
    exit_point_uuid  = u()
    coach_flow_uuid  = u()
    exit_component_id  = f"3008.{exit_point_uuid}"
    coach_component_id = f"3032.{coach_flow_uuid}"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <process id="{proc_id}" name="{escape(task.name)}">
        <lastModified>{ts}</lastModified>
        <lastModifiedBy>admin</lastModifiedBy>
        <tenantId isNull="true" />
        <processId>{proc_id}</processId>
        <image isNull="true" />
        <tabGroup isNull="true" />
        <startingProcessItemId>{start_item_id}</startingProcessItemId>
        <isRootProcess>false</isRootProcess>
        <processType>10</processType>
        <isErrorHandlerEnabled>false</isErrorHandlerEnabled>
        <errorHandlerItemId isNull="true" />
        <isLoggingVariables>false</isLoggingVariables>
        <isTransactional>false</isTransactional>
        <processTimingLevel isNull="true" />
        <participantRef isNull="true" />
        <exposedType>0</exposedType>
        <isTrackingEnabled>true</isTrackingEnabled>
        <xmlData isNull="true" />
        <cachingType>false</cachingType>
        <itemLabel isNull="true" />
        <cacheLength isNull="true" />
        <mobileReady>false</mobileReady>
        <sboSyncEnabled>true</sboSyncEnabled>
        <externalId isNull="true" />
        <isSecured>false</isSecured>
        <isAjaxExposed>false</isAjaxExposed>
        <isInvokedAsynchronously>false</isInvokedAsynchronously>
        <isTransactionalFlow>false</isTransactionalFlow>
        <description></description>
        <guid>guid:{u()}</guid>
        <versionId>{version_id}</versionId>
        <dependencySummary isNull="true" />
        <jsonData>{json_data}</jsonData>
        <businessDataAliases isNull="true" />
        <field1 isNull="true" />
        <field2 isNull="true" />
        <field3>0</field3>
        <field4 isNull="true" />
        <field5>false</field5>
        <clobField1 isNull="true" />
        <blobField1 isNull="true" />
        <item>
            <lastModified isNull="true" />
            <lastModifiedBy isNull="true" />
            <tenantId isNull="true" />
            <processItemId>{end_item_id}</processItemId>
            <processId>{proc_id}</processId>
            <name>End</name>
            <tWComponentName>ExitPoint</tWComponentName>
            <tWComponentId>{exit_component_id}</tWComponentId>
            <isLogEnabled>false</isLogEnabled>
            <isTraceEnabled>false</isTraceEnabled>
            <traceCategory isNull="true" />
            <traceLevel isNull="true" />
            <traceMessage isNull="true" />
            <traceSymbolTable isNull="true" />
            <isExecutionContextTraced>false</isExecutionContextTraced>
            <saveExecutionContext>true</saveExecutionContext>
            <documentation isNull="true" />
            <isErrorHandlerEnabled>false</isErrorHandlerEnabled>
            <errorHandlerItemId isNull="true" />
            <guid>guid:{u()}</guid>
            <versionId>{u()}</versionId>
            <externalServiceRef isNull="true" />
            <externalServiceOp isNull="true" />
            <nodeColor isNull="true" />
            <layoutData x="0" y="0">
                <errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink>
            </layoutData>
            <TWComponent>
                <lastModified isNull="true" />
                <lastModifiedBy isNull="true" />
                <tenantId isNull="true" />
                <exitPointId>{exit_component_id}</exitPointId>
                <haltProcess>false</haltProcess>
                <guid>guid:{exit_point_uuid}</guid>
                <versionId>{u()}</versionId>
            </TWComponent>
        </item>
        <item>
            <lastModified isNull="true" />
            <lastModifiedBy isNull="true" />
            <tenantId isNull="true" />
            <processItemId>{coach_wrap_id}</processItemId>
            <processId>{proc_id}</processId>
            <name>CoachFlowWrapper</name>
            <tWComponentName>CoachFlow</tWComponentName>
            <tWComponentId>{coach_component_id}</tWComponentId>
            <isLogEnabled>false</isLogEnabled>
            <isTraceEnabled>false</isTraceEnabled>
            <traceCategory isNull="true" />
            <traceLevel isNull="true" />
            <traceMessage isNull="true" />
            <traceSymbolTable isNull="true" />
            <isExecutionContextTraced>false</isExecutionContextTraced>
            <saveExecutionContext>true</saveExecutionContext>
            <documentation isNull="true" />
            <isErrorHandlerEnabled>false</isErrorHandlerEnabled>
            <errorHandlerItemId isNull="true" />
            <guid>guid:{u()}</guid>
            <versionId>{u()}</versionId>
            <externalServiceRef isNull="true" />
            <externalServiceOp isNull="true" />
            <nodeColor isNull="true" />
            <layoutData x="0" y="0">
                <errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink>
            </layoutData>
            <TWComponent />
        </item>
        <startingProcessItemId>{start_item_id}</startingProcessItemId>
        <errorHandlerItemId isNull="true" />
        <layoutData noConversion="true">
            <errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink>
        </layoutData>
        <startPoint>
            <layoutData x="0" y="0">
                <errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink>
            </layoutData>
        </startPoint>
        <startLink>
            <fromPort locationId="rightCenter" portType="1" />
            <toPort locationId="rightCenter" portType="2" />
            <layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData>
        </startLink>
        <link name="Untitled">
            <lastModified isNull="true" />
            <lastModifiedBy isNull="true" />
            <tenantId isNull="true" />
            <processLinkId>2027.{u()}</processLinkId>
            <processId>{proc_id}</processId>
            <description isNull="true" />
            <fromProcessItemId>{coach_wrap_id}</fromProcessItemId>
            <endStateId>Out</endStateId>
            <toProcessItemId>{end_item_id}</toProcessItemId>
            <guid>guid:{u()}</guid>
            <versionId>{u()}</versionId>
            <layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData>
            <fromItemPort locationId="rightCenter" portType="1" />
            <toItemPort locationId="rightCenter" portType="2" />
            <fromProcessItemId>{coach_wrap_id}</fromProcessItemId>
            <toProcessItemId>{end_item_id}</toProcessItemId>
        </link>
    </process>
</teamworks>
"""


def build_bpd_xml(spec: ProcessSpec, bpd_id: str, bpd_version_id: str,
                  task_proc_ids: dict) -> str:
    """Build the BPD XML — ground-truth verified against
    a validated Traditional BAW CSHS export.
    Key requirements confirmed from forensic analysis:
      - Full namespace set (ns2-ns22) in bpmn2Data definitions element
      - exporterVersion="8.6.11" (matches server version)
      - Every callActivity MUST have <incoming>/<outgoing> tags wired to flow ids
      - startEvent needs <outgoing>, endEvent needs <incoming>
      - sequenceFlow must NOT use <ns3:default> (causes BAW to treat every flow as default)
      - Start/end events go in lane[0] flowNodeRef
    """
    ts = "1786377516000"
    bpd_guid = u()
    defs_id  = u()

    # ── Assign bpdids to every node ──────────────────────────────────────────
    all_nodes: dict = {}
    all_nodes["__start__"] = f"bpdid:{u()}"
    all_nodes["__end__"]   = f"bpdid:{u()}"
    for ht in spec.human_tasks:
        all_nodes[ht.name] = f"bpdid:{u()}"
    for st in spec.service_tasks:
        all_nodes[st.name] = f"bpdid:{u()}"
    for gw in spec.gateways:
        all_nodes[gw.name] = f"bpdid:{u()}"

    # ── Assign bpdids to ALL sequence flows up-front ─────────────────────────
    flow_ids: dict = {}
    for i, fl in enumerate(spec.flows):
        flow_ids[i] = f"bpdid:{u()}"
    start_flow_id = f"bpdid:{u()}"
    end_flow_id   = f"bpdid:{u()}"

    # ── Build incoming/outgoing index for every node ──────────────────────────
    # Maps node_name -> list of flow_ids coming in / going out
    node_incoming: dict = {k: [] for k in all_nodes}
    node_outgoing: dict = {k: [] for k in all_nodes}

    # start → first_node
    first_node = (spec.human_tasks[0].name if spec.human_tasks
                  else spec.service_tasks[0].name if spec.service_tasks
                  else "__end__")
    node_outgoing["__start__"].append(start_flow_id)
    node_incoming[first_node].append(start_flow_id)

    # spec flows
    for i, fl in enumerate(spec.flows):
        fid = flow_ids[i]
        if fl.source in node_outgoing:
            node_outgoing[fl.source].append(fid)
        if fl.target in node_incoming:
            node_incoming[fl.target].append(fid)

    # last_node → end
    all_task_names = ([ht.name for ht in spec.human_tasks]
                      + [st.name for st in spec.service_tasks])
    wired_targets = {fl.target for fl in spec.flows}
    last_node = next((nm for nm in reversed(all_task_names)
                      if nm not in wired_targets), all_task_names[-1] if all_task_names else "__start__")
    node_outgoing[last_node].append(end_flow_id)
    node_incoming["__end__"].append(end_flow_id)

    def _inc_out(name: str) -> str:
        """Return <incoming> and <outgoing> XML tags for a node."""
        parts = ""
        for fid in node_incoming.get(name, []):
            parts += f'<ns7:incoming>{fid}</ns7:incoming>'
        for fid in node_outgoing.get(name, []):
            parts += f'<ns7:outgoing>{fid}</ns7:outgoing>'
        return parts

    # ── Build lane XML with flowNodeRefs ─────────────────────────────────────
    lane_xml_blocks = []
    lane_y = 0
    for lane_spec in spec.lanes:
        lid = f"bpdid:{u()}"
        is_system = lane_spec.name.lower() == "systems"
        lane_flag = "true" if is_system else "false"

        node_refs = ""
        task_xml  = ""
        x_pos = 158

        # Start/end events in first lane only
        if lane_spec.name == spec.lanes[0].name:
            node_refs += f"<ns7:flowNodeRef>{all_nodes['__start__']}</ns7:flowNodeRef>"
            node_refs += f"<ns7:flowNodeRef>{all_nodes['__end__']}</ns7:flowNodeRef>"

        for ht in spec.human_tasks:
            if ht.lane == lane_spec.name:
                nid = all_nodes[ht.name]
                callee = task_proc_ids[ht.name]
                node_refs += f"<ns7:flowNodeRef>{nid}</ns7:flowNodeRef>"
                task_xml  += _bpmn2_user_task(ht.name, nid, callee, x_pos, lane_y + 50,
                                              _inc_out(ht.name))
                x_pos += 220

        for st in spec.service_tasks:
            if st.lane == lane_spec.name:
                nid = all_nodes[st.name]
                node_refs += f"<ns7:flowNodeRef>{nid}</ns7:flowNodeRef>"
                task_xml  += _bpmn2_service_task(st.name, nid, x_pos, lane_y + 50,
                                                 _inc_out(st.name))
                x_pos += 220

        for gw in spec.gateways:
            if gw.lane == lane_spec.name:
                nid = all_nodes[gw.name]
                node_refs += f"<ns7:flowNodeRef>{nid}</ns7:flowNodeRef>"
                task_xml  += _bpmn2_gateway(gw.name, nid, gw.gateway_type, x_pos, lane_y + 85,
                                            _inc_out(gw.name))
                x_pos += 120

        lane_xml_blocks.append((lid, lane_spec.name, lane_flag, lane_y, node_refs, task_xml))
        lane_y += 280

    # ── Assemble laneSet XML ─────────────────────────────────────────────────
    laneset_id = f"bpdid:{u()}"
    laneset_xml = f'<ns7:laneSet id="{laneset_id}">'
    for lid, lname, lflag, ly, node_refs, task_xml in lane_xml_blocks:
        laneset_xml += (
            f'<ns7:lane name="{escape(lname)}" id="{lid}" ns3:isSystemLane="{lflag}">'
            f'<ns7:extensionElements>'
            f'<ns16:nodeVisualInfo x="0" y="{ly}" width="3000" height="280" color="#F8F8F8"/>'
            f'</ns7:extensionElements>'
            f'{node_refs}'
            f'</ns7:lane>'
        )
    laneset_xml += '</ns7:laneSet>'

    # ── Gather all task/event/gateway XML ────────────────────────────────────
    all_task_xml = ""
    for _, _, _, _, _, task_xml in lane_xml_blocks:
        all_task_xml += task_xml

    # Start event — with wired <outgoing>
    start_id = all_nodes["__start__"]
    end_id   = all_nodes["__end__"]
    all_task_xml += (
        f'<ns7:startEvent name="Start" id="{start_id}">'
        f'<ns7:extensionElements>'
        f'<ns3:activityExtension conditional="false"/>'
        f'<ns16:nodeVisualInfo x="24" y="{lane_xml_blocks[0][3] + 120}" width="32" height="32" color="#A5B7CD"/>'
        f'</ns7:extensionElements>'
        f'<ns7:outgoing>{start_flow_id}</ns7:outgoing>'
        f'</ns7:startEvent>'
    )
    # End event — with wired <incoming>
    all_task_xml += (
        f'<ns7:endEvent name="End" id="{end_id}">'
        f'<ns7:extensionElements>'
        f'<ns3:activityExtension conditional="false"/>'
        f'<ns16:nodeVisualInfo x="3000" y="{lane_xml_blocks[0][3] + 120}" width="32" height="32" color="#A5B7CD"/>'
        f'</ns7:extensionElements>'
        f'<ns7:incoming>{end_flow_id}</ns7:incoming>'
        f'</ns7:endEvent>'
    )

    # ── Sequence flows — NO <ns3:default> wrapper ─────────────────────────────
    sf_xml = ""
    sf_xml += _bpmn2_seq_flow(start_flow_id, start_id, all_nodes[first_node], "")
    for i, fl in enumerate(spec.flows):
        src = all_nodes.get(fl.source, "")
        tgt = all_nodes.get(fl.target, "")
        if src and tgt:
            sf_xml += _bpmn2_seq_flow(flow_ids[i], src, tgt, fl.name)
    sf_xml += _bpmn2_seq_flow(end_flow_id, all_nodes[last_node], end_id, "")

    # ── Embed bpmn2Data — full namespace set matching working TWX ─────────────
    inst_name = f'"' + escape(spec.name) + ':" + tw.system.process.instanceId'
    bpmn2_inner = (
        f'<ns7:definitions'
        f' xmlns:ns7="http://www.omg.org/spec/BPMN/20100524/MODEL"'
        f' xmlns:ns2="http://www.ibm.com/bpm/Extensions"'
        f' xmlns:ns3="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/wle"'
        f' xmlns:ns4="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process"'
        f' xmlns:ns5="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/case"'
        f' xmlns:ns6="http://www.ibm.com/xmlns/prod/bpm/uca"'
        f' xmlns:ns8="http://www.ibm.com/bpm/processappsettings"'
        f' xmlns:ns9="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/extservice"'
        f' xmlns:ns10="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/trackinggroup"'
        f' xmlns:ns11="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/team"'
        f' xmlns:ns12="http://www.ibm.com/xmlns/bpmnx/20100524/v1/BusinessVocabulary"'
        f' xmlns:ns13="http://www.omg.org/spec/DD/20100524/DI"'
        f' xmlns:ns14="http://www.omg.org/spec/DD/20100524/DC"'
        f' xmlns:ns15="http://www.omg.org/spec/BPMN/20100524/BPMNDI"'
        f' xmlns:ns16="http://www.ibm.com/xmlns/prod/bpm/graph"'
        f' xmlns:ns17="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/auth"'
        f' xmlns:ns18="http://www.ibm.com/bpm/CoachDesignerNG"'
        f' xmlns:ns19="http://www.ibm.com/xmlns/links"'
        f' xmlns:ns20="http://www.ibm.com/bpm/uitheme"'
        f' xmlns:ns21="http://www.ibm.com/bpm/coachview"'
        f' xmlns:ns22="http://www.ibm.com/xmlns/tagging"'
        f' id="{defs_id}" targetNamespace="" exporter="http://www.ibm.com/BPM" exporterVersion="8.6.11">'
        f'<ns7:process processType="None" isClosed="false"'
        f' name="{escape(spec.name)}" id="{bpd_id}">'
        f'<ns7:extensionElements>'
        f'<ns5:isConvergedProcess>true</ns5:isConvergedProcess>'
        f'<ns3:bpdExtension instanceName="{inst_name}"'
        f' dueDateEnabled="true" atRiskCalcEnabled="true" enableTracking="true"'
        f' allowProjectedPathManagement="false" optimizeExecForLatency="false"'
        f' sBOSyncEnabled="false" allowContentOperations="false" autoTrackingEnabled="false">'
        f'<ns3:defaultInstanceUI/>'
        f'<ns3:bpdOwnerInstanceUI/>'
        f'<ns3:dueDateSettings type="TimeCalculation">'
        f'<ns3:dueDate unit="Days" timeOfDay="00:00">1</ns3:dueDate>'
        f'</ns3:dueDateSettings>'
        f'<ns3:workSchedule><ns3:timeScheduleType>0</ns3:timeScheduleType>'
        f'<ns3:timezoneType>0</ns3:timezoneType>'
        f'<ns3:holidayScheduleType>0</ns3:holidayScheduleType></ns3:workSchedule>'
        f'</ns3:bpdExtension>'
        f'<ns5:caseExtension><ns5:caseFolder id="{u()}"/></ns5:caseExtension>'
        f'</ns7:extensionElements>'
        f'<ns7:ioSpecification/>'
        f'{laneset_xml}'
        f'{all_task_xml}'
        f'{sf_xml}'
        f'</ns7:process>'
        f'</ns7:definitions>'
    )
    bpmn2_escaped = escape(bpmn2_inner)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <bpd id="{bpd_id}" name="{escape(spec.name)}">
        <lastModified>{ts}</lastModified>
        <lastModifiedBy>admin</lastModifiedBy>
        <tenantId isNull="true" />
        <bpdId>{bpd_id}</bpdId>
        <isTrackingEnabled>true</isTrackingEnabled>
        <isSpcEnabled>false</isSpcEnabled>
        <restrictedName isNull="true" />
        <isCriticalPathEnabled>false</isCriticalPathEnabled>
        <participantRef isNull="true" />
        <businessDataParticipantRef isNull="true" />
        <perfMetricParticipantRef isNull="true" />
        <ownerTeamParticipantRef isNull="true" />
        <timeScheduleType isNull="true" />
        <timeScheduleName isNull="true" />
        <timeScheduleExpression isNull="true" />
        <holidayScheduleType isNull="true" />
        <holidayScheduleName isNull="true" />
        <holidayScheduleExpression isNull="true" />
        <timezoneType isNull="true" />
        <timezone isNull="true" />
        <timezoneExpression isNull="true" />
        <internalName isNull="true" />
        <description>{escape(spec.description)}</description>
        <type>1</type>
        <rootBpdId isNull="true" />
        <parentBpdId isNull="true" />
        <parentFlowObjectId isNull="true" />
        <xmlData isNull="true" />
        <bpmn2Data>{bpmn2_escaped}</bpmn2Data>
        <dependencySummary isNull="true" />
        <jsonData isNull="true" />
        <migrationData isNull="true" />
        <rwfData isNull="true" />
        <rwfStatus isNull="true" />
        <templateId isNull="true" />
        <externalId isNull="true" />
        <guid>guid:{bpd_guid}</guid>
        <versionId>{bpd_version_id}</versionId>
        <field1 isNull="true" />
        <field2 isNull="true" />
        <field3>0</field3>
        <field4 isNull="true" />
        <field5>false</field5>
        <clobField1 isNull="true" />
        <blobField1 isNull="true" />
    </bpd>
</teamworks>
"""


# ── BPMN2 helpers (used by build_bpd_xml bpmn2Data) ──────────────────────────

def _bpmn2_user_task(name: str, nid: str, callee: str, x: int, y: int, inc_out: str = "") -> str:
    """callActivity with activityType=InlineUserTask — verified against working TWX."""
    return (
        f'<ns7:callActivity calledElement="{callee}" name="{escape(name)}" id="{nid}">'
        f'<ns7:extensionElements>'
        f'<ns3:activityType>InlineUserTask</ns3:activityType>'
        f'<ns3:userTaskSettings>'
        f'<ns3:enableAutoFlow>false</ns3:enableAutoFlow>'
        f'<ns3:enableCleanState>false</ns3:enableCleanState>'
        f'<ns3:activityPriority type="Priority"/>'
        f'<ns3:activityDueDate type="TimeCalculation">'
        f'<ns3:dueDate unit="Hours" timeOfDay="00:00">1</ns3:dueDate>'
        f'</ns3:activityDueDate>'
        f'<ns3:activityAssignmentType>Lane</ns3:activityAssignmentType>'
        f'</ns3:userTaskSettings>'
        f'<ns3:activityExtension conditional="false"/>'
        f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="95" height="70" color="#A5B7CD"/>'
        f'</ns7:extensionElements>'
        f'{inc_out}'
        f'<ns7:ioSpecification>'
        f'<ns7:inputSet id="{u()}"/>'
        f'<ns7:outputSet id="{u()}"/>'
        f'</ns7:ioSpecification>'
        f'<ns7:resourceRole xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        f' xsi:type="ns3:tActivityPerformer" distribution="None" name="Lane">'
        f'<ns3:teamFilterService/></ns7:resourceRole>'
        f'</ns7:callActivity>'
    )


def _bpmn2_service_task(name: str, nid: str, x: int, y: int, inc_out: str = "") -> str:
    """callActivity with activityType=ServiceTask — verified against working TWX."""
    return (
        f'<ns7:callActivity name="{escape(name)}" id="{nid}">'
        f'<ns7:extensionElements>'
        f'<ns3:activityType>ServiceTask</ns3:activityType>'
        f'<ns3:deleteTaskOnCompletion>false</ns3:deleteTaskOnCompletion>'
        f'<ns3:activityExtension conditional="false"/>'
        f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="95" height="70" color="#A5B7CD"/>'
        f'</ns7:extensionElements>'
        f'{inc_out}'
        f'</ns7:callActivity>'
    )


def _bpmn2_gateway(name: str, nid: str, gw_type: str, x: int, y: int, inc_out: str = "") -> str:
    tag = "ns7:exclusiveGateway" if gw_type == "exclusive" else "ns7:parallelGateway"
    return (
        f'<{tag} name="{escape(name)}" gatewayDirection="Unspecified" id="{nid}">'
        f'<ns7:extensionElements>'
        f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="32" height="32" color="#A5B7CD"/>'
        f'</ns7:extensionElements>'
        f'{inc_out}'
        f'</{tag}>'
    )


def _bpmn2_seq_flow(fid: str, src: str, tgt: str, label: str) -> str:
    """Sequence flow — no <ns3:default> wrapper (that tag marks the default path,
    not the flow id; using fid as default value breaks all gateway routing)."""
    name_attr = f' name="{escape(label)}"' if label else ''
    return (
        f'<ns7:sequenceFlow id="{fid}"{name_attr}'
        f' sourceRef="{src}" targetRef="{tgt}"/>'
    )


def build_env_vars_xml(ev_id: str, version_id: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <environmentVariableSet id="{ev_id}" name="Environment Variables">
        <lastModified isNull="true" />
        <lastModifiedBy isNull="true" />
        <tenantId isNull="true" />
        <envVarSetId>{ev_id}</envVarSetId>
        <description isNull="true" />
        <guid>guid:{ev_id.split('.', 1)[1]}</guid>
        <versionId>{version_id}</versionId>
    </environmentVariableSet>
</teamworks>
"""


def build_project_defaults_xml(pd_id: str, version_id: str, short_name: str, theme_ref: Optional[str] = None) -> str:
    ns = f"http://{short_name}"
    theme_ref = theme_ref or f"{SYSDATA_DEP_UUID}/72.993e03e9-2574-40fc-807c-65b06be378fd"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <projectDefaults id="{pd_id}" name="Process App Settings">
        <lastModified isNull="true" />
        <lastModifiedBy isNull="true" />
        <tenantId isNull="true" />
        <projectDefaultsId>{pd_id}</projectDefaultsId>
        <description isNull="true" />
        <guid>guid:{pd_id.split('.', 1)[1]}</guid>
        <versionId>{version_id}</versionId>
        <participantRef isNull="true" />
        <defaultXslRef>{SYSDATA_DEP_UUID}/61.140920b1-a53c-4d72-b6bb-60776f49f7f2</defaultXslRef>
        <defaultCssRef>{SYSDATA_DEP_UUID}/61.aabe9f91-df4b-43db-857c-41dbed4820a3</defaultCssRef>
        <defaultTheme>{escape(theme_ref)}</defaultTheme>
        <themeVersion isNull="true" />
        <defaultJsRefs isNull="true" />
        <isWbmEnabled>false</isWbmEnabled>
        <namespace>{escape(ns)}</namespace>
        <isIidOptimized>true</isIidOptimized>
        <isQueueBypass>1</isQueueBypass>
        <templateAcronymReference isNull="true" />
        <templateSnapshotReference isNull="true" />
        <targetEnvironment>BAW_tWAS</targetEnvironment>
        <subtype isNull="true" />
        <capability isNull="true" />
        <solutionTargetStore isNull="true" />
        <appLoggingEnabled>false</appLoggingEnabled>
        <logName isNull="true" />
        <logLevel>0</logLevel>
    </projectDefaults>
</teamworks>
"""


def build_package_xml(proj_id: str, branch_id: str, snap_id: str,
                      spec: ProcessSpec, objects: list) -> str:
    """Build META-INF/package.xml"""
    obj_entries = ""
    for obj_id, version_id, name, obj_type in objects:
        obj_entries += f'\n        <object id="{obj_id}" versionId="{version_id}" name="{escape(name)}" type="{obj_type}"/>'

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:package buildId="BPM8600-20260615-202317" buildVersion="8.6.11" buildDescription="IBM Business Process Manager V8.6.11.26000 - 20260615_2154 - BPM8600-20260615-202317" fixPack="26000" containsECM="false" containsBPMN2="false" xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/package.xsd">
    <target>
        <project id="{proj_id}" name="{escape(spec.name)}" description="{escape(spec.description)}" shortName="{escape(spec.short_name)}" isToolkit="false" isHidden="false" isSystem="false" solutionID="" solutionServerName="" solutionPrefix="" type="" isTemplate="false" isIconSet="false" caseDisplayName=""/>
        <branch id="{branch_id}" name="Main" acronym="Main" description=""/>
        <snapshot id="{snap_id}" name="Initial Import" acronym="II" originalCreationDate="2026-01-01T00:00:00.000-07:00" description="Generated by twx_generator.py"/>
    </target>
    <governanceAssignments/>
    <dependencies>
        <dependency rank="0" isManaged="false" id="{SYSDATA_DEP_ID}">
            <project id="{SYSDATA_PROJ_ID}" name="System Data" shortName="TWSYS" isToolkit="true" isHidden="false" isSystem="true"/>
            <branch id="{SYSDATA_BR_ID}" name="Main"/>
            <snapshot id="{SYSDATA_SNAP_ID}" name="{SYSDATA_SNAP_NM}" originalCreationDate="2015-08-24T17:00:00.000-07:00"/>
        </dependency>
        <dependency rank="1" isManaged="false" id="{UITK_DEP_ID}">
            <project id="{UITK_PROJ_ID}" name="UI Toolkit" shortName="SYSBPMUI" isToolkit="true" isHidden="false" isSystem="true"/>
            <branch id="{UITK_BR_ID}" name="Main"/>
            <snapshot id="{UITK_SNAP_ID}" name="{UITK_SNAP_NM}" originalCreationDate="2017-05-24T16:23:53.574-07:00"/>
        </dependency>
    </dependencies>
    <objects>{obj_entries}
    </objects>
    <files/>
    <migrationPolicies/>
</p:package>
"""


def build_manifest() -> str:
    return "Manifest-Version: 1.0\r\n\r\n"


def build_metadata_xml(proj_id: str, spec: ProcessSpec) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:metadata xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/metadata.xsd">
    <projectType>processApp</projectType>
    <projectId>{proj_id}</projectId>
    <name>{escape(spec.name)}</name>
    <shortName>{escape(spec.short_name)}</shortName>
    <description>{escape(spec.description)}</description>
</p:metadata>
"""




# Proven native CSHS serializer merged from the earlier fixed generator.
def _item_subject_ref(ft: str) -> str:
    """Return BAW CoachFlow itemSubjectRef for a primitive field type."""
    class_id = _field_class_id(ft)
    # Primitive class ids end with 12.<uuid>. CoachFlow uses itm.12.<uuid>.
    primitive = class_id.split('/')[-1]
    return f"itm.{primitive}"


def _make_io(task: HumanTaskSpec) -> dict:
    io = {}
    for f in task.fields:
        io[f.name] = {
            "input_id": f"2055.{u()}",
            "output_id": f"2055.{u()}",
            "class_id": _field_class_id(f.field_type),
            "item_subject_ref": _item_subject_ref(f.field_type),
        }
    if task.comment_history:
        variable = str(task.comment_history.get("variable_name") or task.comment_history.get("name") or "commentHistory")
        entry_id = str(task.comment_history.get("entry_class_id") or task.comment_history.get("class_id") or "")
        if entry_id:
            bare = entry_id.split("/")[-1]
            if not bare.startswith("12."):
                bare = "12." + bare.split(".", 1)[-1]
            io[variable] = {
                "input_id": f"2055.{u()}",
                "output_id": f"2055.{u()}",
                "class_id": f"/{bare}",
                "item_subject_ref": f"itm.{bare}",
                "is_collection": True,
            }
    return io


def _patch_json_io(task: HumanTaskSpec, jdata: dict, io: dict) -> None:
    root = jdata["rootElement"][0]
    root["ioSpecification"] = {
        "dataInput": [
            {
                "itemSubjectRef": io[name]["item_subject_ref"],
                "name": name,
                "isCollection": bool(io[name].get("is_collection", False)),
                "id": io[name]["input_id"],
            }
            for name in task.input_names
        ],
        "dataOutput": [
            {
                "itemSubjectRef": io[name]["item_subject_ref"],
                "name": name,
                "isCollection": bool(io[name].get("is_collection", False)),
                "id": io[name]["output_id"],
            }
            for name in task.output_names
        ],
        # Matches the working CSHS exported from this BAW environment.
        "inputSet": [{"id": f"_{u()}"}],
        "outputSet": [{"id": f"_{u()}"}],
    }

    impl = root["extensionElements"]["userTaskImplementation"][0]
    flows = impl["flowElement"]
    end_event = next(x for x in flows if x.get("declaredType") == "endEvent")
    end_event["incoming"] = [
        x["id"]
        for x in flows
        if x.get("declaredType") == "sequenceFlow"
        and x.get("targetRef") == end_event["id"]
    ]


def _config_xml(c: dict) -> str:
    value = c.get("value", "")
    if isinstance(value, (dict, list)):
        value = json.dumps(value, separators=(",", ":"))
    return (
        "<ns17:configData>"
        f"<ns17:id>{escape(str(c.get('id', u())))}</ns17:id>"
        f"<ns17:optionName>{escape(str(c.get('optionName', '')))}</ns17:optionName>"
        f"<ns17:value>{escape(str(value))}</ns17:value>"
        "</ns17:configData>"
    )



def _viewref_body_xml(item: dict) -> str:
    cfg = "".join(_config_xml(c) for c in item.get("configData", []))
    binding = item.get("binding")
    binding_xml = f"<ns17:binding>{escape(str(binding))}</ns17:binding>" if binding else ""
    cboxes = []
    for box in item.get("contentBoxContrib", []):
        contributions = "".join(_contribution_xml(child) for child in box.get("contributions", []))
        cboxes.append(
            "<ns17:contentBoxContrib>"
            f"<ns17:id>{escape(str(box.get('id', u())))}</ns17:id>"
            f"<ns17:contentBoxId>{escape(str(box.get('contentBoxId', 'ContentBox1')))}</ns17:contentBoxId>"
            f"{contributions}"
            "</ns17:contentBoxContrib>"
        )
    return (
        f"<ns17:id>{escape(str(item.get('id', u())))}</ns17:id>"
        f"<ns17:layoutItemId>{escape(str(item.get('layoutItemId', 'item')))}</ns17:layoutItemId>"
        f"{cfg}"
        f"<ns17:viewUUID>{escape(str(item.get('viewUUID', W_TEXT_INPUT)))}</ns17:viewUUID>"
        f"{binding_xml}{''.join(cboxes)}"
    )


def _contribution_xml(item: dict) -> str:
    return (
        '<ns17:contributions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:type="ns17:ViewRef" version="{escape(str(item.get("version", "8550")))}">'
        f"{_viewref_body_xml(item)}"
        "</ns17:contributions>"
    )


def _viewref_xml(item: dict) -> str:
    """Serialize flat or nested UI Toolkit Coach controls."""
    return (
        '<ns17:layoutItem xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:type="ns17:ViewRef" version="{escape(str(item.get("version", "8550")))}">'
        f"{_viewref_body_xml(item)}"
        "</ns17:layoutItem>"
    )


def _coachflow_from_json(task: HumanTaskSpec, proc_id: str, jdata: dict, io: dict) -> str:
    """Serialize the generated Coach JSON into the native <coachflow> representation.

    The working Hiring Sample contains both jsonData and coachflow. The uploaded
    Earlier generators emitted jsonData only; this function restores the missing native
    CoachFlow structure while reusing exactly the same task/flow/view ids.
    """
    root = jdata["rootElement"][0]
    impl = root["extensionElements"]["userTaskImplementation"][0]
    elements = impl["flowElement"]

    start = next(x for x in elements if x.get("declaredType") == "startEvent")
    form = next(
        x
        for x in elements
        if x.get("declaredType") == "com.ibm.bpmsdk.model.bpmn20.ibmext.TFormTask"
    )
    end = next(x for x in elements if x.get("declaredType") == "endEvent")
    seqs = [x for x in elements if x.get("declaredType") == "sequenceFlow"]
    scripts = [x for x in elements if x.get("declaredType") == "scriptTask"]

    layout_items = (
        form.get("formDefinition", {})
        .get("coachDefinition", {})
        .get("layout", {})
        .get("layoutItem", [])
    )
    layout_xml = "".join(_viewref_xml(item) for item in layout_items)

    def refs(tag: str, values) -> str:
        return "".join(f"<ns16:{tag}>{escape(str(v))}</ns16:{tag}>" for v in values or [])

    seq_xml = ""
    for sf in seqs:
        ext = sf.get("extensionElements", {})
        coach_bindings = ext.get("coachEventBinding", [])
        ceb = "".join(
            (
                f'<ns3:coachEventBinding id="{escape(str(cb.get("id", u())))}">'
                f'<ns3:coachEventPath>{escape(str(cb.get("coachEventPath", "")))}</ns3:coachEventPath>'
                "</ns3:coachEventBinding>"
            )
            for cb in coach_bindings
        )
        impls = ext.get("sequenceFlowImplementation", [])
        seq_impl = ""
        if impls:
            imp = impls[0]
            seq_impl = (
                "<ns3:sequenceFlowImplementation>"
                f"<ns3:fireValidation>{escape(str(imp.get('fireValidation', 'Never')))}</ns3:fireValidation>"
                f"<ns3:sboSyncEnabled>{str(bool(imp.get('sboSyncEnabled', True))).lower()}</ns3:sboSyncEnabled>"
                "</ns3:sequenceFlowImplementation>"
            )
        seq_xml += (
            f'<ns16:sequenceFlow sourceRef="{escape(str(sf.get("sourceRef", "")))}" '
            f'targetRef="{escape(str(sf.get("targetRef", "")))}" '
            f'name="{escape(str(sf.get("name", "")))}" id="{escape(str(sf.get("id", "")))}">'
            "<ns16:extensionElements>"
            "<ns13:linkVisualInfo>"
            "<ns13:sourcePortLocation>rightCenter</ns13:sourcePortLocation>"
            "<ns13:targetPortLocation>leftCenter</ns13:targetPortLocation>"
            "<ns13:showLabel>false</ns13:showLabel>"
            f"<ns13:showCoachControlLabel>{str(bool(coach_bindings)).lower()}</ns13:showCoachControlLabel>"
            "<ns13:labelPosition>0.0</ns13:labelPosition>"
            "<ns13:saveExecutionContext>true</ns13:saveExecutionContext>"
            "</ns13:linkVisualInfo>"
            f"{ceb}{seq_impl}"
            "</ns16:extensionElements>"
            "</ns16:sequenceFlow>"
        )

    script_xml = ""
    for st in scripts:
        vis = ((st.get("extensionElements") or {}).get("nodeVisualInfo") or [{}])[0]
        content = "".join((st.get("script") or {}).get("content") or [])
        default_attr = (
            f' default="{escape(str(st.get("default")))}"'
            if st.get("default") else ""
        )
        script_xml += (
            f'<ns16:scriptTask scriptFormat="{escape(str(st.get("scriptFormat", "text/x-javascript")))}"'
            f'{default_attr} name="{escape(str(st.get("name", "Set decision")))}" '
            f'id="{escape(str(st.get("id")))}">'
            '<ns16:extensionElements>'
            f'<ns13:nodeVisualInfo x="{escape(str(vis.get("x", 520)))}" '
            f'y="{escape(str(vis.get("y", 120)))}" width="{escape(str(vis.get("width", 95)))}" '
            f'height="{escape(str(vis.get("height", 70)))}" />'
            '</ns16:extensionElements>'
            f'{refs("incoming", st.get("incoming"))}{refs("outgoing", st.get("outgoing"))}'
            f'<ns16:script>{escape(content)}</ns16:script>'
            '</ns16:scriptTask>'
        )

    data_inputs = "".join(
        (
            f'<ns16:dataInput name="{escape(name)}" '
            f'itemSubjectRef="{escape(io[name]["item_subject_ref"])}" '
            f'isCollection="{str(bool(io[name].get("is_collection", False))).lower()}" id="{io[name]["input_id"]}" />'
        )
        for name in task.input_names
    )
    data_outputs = "".join(
        (
            f'<ns16:dataOutput name="{escape(name)}" '
            f'itemSubjectRef="{escape(io[name]["item_subject_ref"])}" '
            f'isCollection="{str(bool(io[name].get("is_collection", False))).lower()}" id="{io[name]["output_id"]}" />'
        )
        for name in task.output_names
    )

    return (
        "<coachflow>"
        '<ns16:definitions xmlns:ns16="http://www.omg.org/spec/BPMN/20100524/MODEL" '
        'xmlns:ns2="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/case" '
        'xmlns:ns3="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process" '
        'xmlns:ns4="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/wle" '
        'xmlns:ns5="http://www.ibm.com/bpm/Extensions" '
        'xmlns:ns6="http://www.ibm.com/xmlns/prod/bpm/uca" '
        'xmlns:ns7="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/trackinggroup" '
        'xmlns:ns8="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/team" '
        'xmlns:ns9="http://www.ibm.com/xmlns/bpmnx/20100524/v1/BusinessVocabulary" '
        'xmlns:ns10="http://www.omg.org/spec/DD/20100524/DI" '
        'xmlns:ns11="http://www.omg.org/spec/DD/20100524/DC" '
        'xmlns:ns12="http://www.omg.org/spec/BPMN/20100524/BPMNDI" '
        'xmlns:ns13="http://www.ibm.com/xmlns/prod/bpm/graph" '
        'xmlns:ns14="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/extservice" '
        'xmlns:ns15="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/auth" '
        'xmlns:ns17="http://www.ibm.com/bpm/CoachDesignerNG" '
        'xmlns:ns18="http://www.ibm.com/xmlns/links" '
        'xmlns:ns19="http://www.ibm.com/bpm/uitheme" '
        'xmlns:ns20="http://www.ibm.com/bpm/coachview" '
        'xmlns:ns21="http://www.ibm.com/xmlns/tagging" '
        f'id="{escape(str(jdata.get("id", u())))}" targetNamespace="" '
        'expressionLanguage="http://www.ibm.com/xmlns/prod/bpm/expression-lang/javascript">'
        f'<ns16:globalUserTask name="{escape(task.name)}" id="{proc_id}">'
        f'<ns16:documentation>Generated CSHS for {escape(task.name)}</ns16:documentation>'
        "<ns16:extensionElements>"
        f'<ns3:userTaskImplementation id="{escape(str(impl.get("id", u())))}">'
        f'<ns16:startEvent name="Start" id="{escape(str(start["id"]))}">'
        '<ns16:extensionElements><ns13:nodeVisualInfo x="50" y="200" width="24" height="24" color="#F8F8F8" /></ns16:extensionElements>'
        f'{refs("outgoing", start.get("outgoing"))}</ns16:startEvent>'
        f'<ns3:formTask name="{escape(task.name)}" id="{escape(str(form["id"]))}">'
        '<ns16:extensionElements><ns13:nodeVisualInfo x="350" y="177" width="95" height="70" color="#FFFDD3" /></ns16:extensionElements>'
        f'{refs("incoming", form.get("incoming"))}{refs("outgoing", form.get("outgoing"))}'
        f'<ns3:formDefinition><ns17:coachDefinition><ns17:layout>{layout_xml}</ns17:layout></ns17:coachDefinition></ns3:formDefinition>'
        "</ns3:formTask>"
        f"{script_xml}"
        f'<ns16:endEvent name="End" id="{escape(str(end["id"]))}">'
        '<ns16:extensionElements><ns13:nodeVisualInfo x="700" y="200" width="24" height="24" color="#F8F8F8" />'
        '<ns3:navigationInstructions><ns3:targetType>Default</ns3:targetType></ns3:navigationInstructions></ns16:extensionElements>'
        f'{refs("incoming", end.get("incoming"))}</ns16:endEvent>'
        f"{seq_xml}"
        "</ns3:userTaskImplementation>"
        "</ns16:extensionElements>"
        "<ns16:ioSpecification>"
        f"{data_inputs}{data_outputs}"
        f'<ns16:inputSet id="_{u()}" />'
        f'<ns16:outputSet id="_{u()}" />'
        "</ns16:ioSpecification>"
        "</ns16:globalUserTask>"
        "</ns16:definitions>"
        "</coachflow>"
    )


def _process_parameters_xml(task: HumanTaskSpec, proc_id: str, io: dict) -> str:
    blocks = []
    seq = 1

    def add_param(name: str, ptype: int, pid: str):
        nonlocal seq
        meta = io[name]
        blocks.append(
            f'<processParameter name="{escape(name)}">'
            '<lastModified isNull="true" />'
            '<lastModifiedBy isNull="true" />'
            '<tenantId isNull="true" />'
            f'<processParameterId>{pid}</processParameterId>'
            f'<processId>{proc_id}</processId>'
            f'<parameterType>{ptype}</parameterType>'
            f'<isArrayOf>{str(bool(meta.get("is_collection", False))).lower()}</isArrayOf>'
            f'<classId>{escape(meta["class_id"])}</classId>'
            f'<seq>{seq}</seq>'
            '<hasDefault>false</hasDefault>'
            '<defaultValue isNull="true" />'
            '<isLocked>false</isLocked>'
            '<description isNull="true" />'
            f'<guid>guid:{u()}</guid>'
            f'<versionId>{u()}</versionId>'
            '</processParameter>'
        )
        seq += 1

    for name in task.input_names:
        add_param(name, 1, io[name]["input_id"])
    for name in task.output_names:
        add_param(name, 2, io[name]["output_id"])

    return "".join(blocks)


def fixed_build_cshs_xml(task: HumanTaskSpec, proc_id: str, version_id: str, io: Optional[dict] = None) -> str:
    """Generate a CSHS with declared parameters and native CoachFlow."""
    ts = "1786377516000"
    io = io or _make_io(task)

    jdata = json.loads(build_cshs_json(task, proc_id))
    _patch_json_io(task, jdata, io)
    json_data = escape(json.dumps(jdata, separators=(",", ":")))
    params_xml = _process_parameters_xml(task, proc_id, io)
    coachflow_xml = _coachflow_from_json(task, proc_id, jdata, io)

    coach_wrap_id = f"2025.{u()}"
    end_item_id = f"2025.{u()}"
    start_item_id = coach_wrap_id
    exit_uuid = u()
    coach_uuid = u()
    exit_component_id = f"3008.{exit_uuid}"
    coach_component_id = f"3032.{coach_uuid}"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
  <process id="{proc_id}" name="{escape(task.name)}">
    <lastModified>{ts}</lastModified><lastModifiedBy>admin</lastModifiedBy><tenantId isNull="true" />
    <processId>{proc_id}</processId><image isNull="true" /><tabGroup isNull="true" />
    <startingProcessItemId>{start_item_id}</startingProcessItemId><isRootProcess>false</isRootProcess>
    <processType>10</processType><isErrorHandlerEnabled>false</isErrorHandlerEnabled><errorHandlerItemId isNull="true" />
    <isLoggingVariables>false</isLoggingVariables><isTransactional>false</isTransactional><processTimingLevel isNull="true" />
    <participantRef isNull="true" /><exposedType>0</exposedType><isTrackingEnabled>true</isTrackingEnabled><xmlData isNull="true" />
    <cachingType>false</cachingType><itemLabel isNull="true" /><cacheLength isNull="true" /><mobileReady>false</mobileReady>
    <sboSyncEnabled>true</sboSyncEnabled><externalId isNull="true" /><isSecured>false</isSecured><isAjaxExposed>false</isAjaxExposed>
    <isInvokedAsynchronously>false</isInvokedAsynchronously><isTransactionalFlow>false</isTransactionalFlow>
    <description>Generated CSHS for {escape(task.name)}</description><guid>guid:{u()}</guid><versionId>{version_id}</versionId>
    <dependencySummary isNull="true" /><jsonData>{json_data}</jsonData><businessDataAliases isNull="true" />
    <field1 isNull="true" /><field2 isNull="true" /><field3>0</field3><field4 isNull="true" /><field5>false</field5>
    <clobField1 isNull="true" /><blobField1 isNull="true" />
    {params_xml}
    <item>
      <lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processItemId>{end_item_id}</processItemId><processId>{proc_id}</processId><name>End</name>
      <tWComponentName>ExitPoint</tWComponentName><tWComponentId>{exit_component_id}</tWComponentId>
      <isLogEnabled>false</isLogEnabled><isTraceEnabled>false</isTraceEnabled><traceCategory isNull="true" /><traceLevel isNull="true" />
      <traceMessage isNull="true" /><traceSymbolTable isNull="true" /><isExecutionContextTraced>false</isExecutionContextTraced>
      <saveExecutionContext>true</saveExecutionContext><documentation isNull="true" /><isErrorHandlerEnabled>false</isErrorHandlerEnabled>
      <errorHandlerItemId isNull="true" /><guid>guid:{u()}</guid><versionId>{u()}</versionId><externalServiceRef isNull="true" />
      <externalServiceOp isNull="true" /><nodeColor isNull="true" />
      <layoutData x="0" y="0"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
      <TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <exitPointId>{exit_component_id}</exitPointId><haltProcess>false</haltProcess><guid>guid:{exit_uuid}</guid><versionId>{u()}</versionId></TWComponent>
    </item>
    <item>
      <lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processItemId>{coach_wrap_id}</processItemId><processId>{proc_id}</processId><name>CoachFlowWrapper</name>
      <tWComponentName>CoachFlow</tWComponentName><tWComponentId>{coach_component_id}</tWComponentId>
      <isLogEnabled>false</isLogEnabled><isTraceEnabled>false</isTraceEnabled><traceCategory isNull="true" /><traceLevel isNull="true" />
      <traceMessage isNull="true" /><traceSymbolTable isNull="true" /><isExecutionContextTraced>false</isExecutionContextTraced>
      <saveExecutionContext>true</saveExecutionContext><documentation isNull="true" /><isErrorHandlerEnabled>false</isErrorHandlerEnabled>
      <errorHandlerItemId isNull="true" /><guid>guid:{u()}</guid><versionId>{u()}</versionId><externalServiceRef isNull="true" />
      <externalServiceOp isNull="true" /><nodeColor isNull="true" />
      <layoutData x="0" y="0"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
      <TWComponent />
    </item>
    <startingProcessItemId>{start_item_id}</startingProcessItemId><errorHandlerItemId isNull="true" />
    <layoutData noConversion="true"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
    <startPoint><layoutData x="0" y="0"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData></startPoint>
    <startLink><fromPort locationId="rightCenter" portType="1" /><toPort locationId="rightCenter" portType="2" />
    <layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData></startLink>
    {coachflow_xml}
    <link name="Untitled"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processLinkId>2027.{u()}</processLinkId><processId>{proc_id}</processId><description isNull="true" />
      <fromProcessItemId>{coach_wrap_id}</fromProcessItemId><endStateId>Out</endStateId><toProcessItemId>{end_item_id}</toProcessItemId>
      <guid>guid:{u()}</guid><versionId>{u()}</versionId><layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData>
      <fromItemPort locationId="rightCenter" portType="1" /><toItemPort locationId="rightCenter" portType="2" />
      <fromProcessItemId>{coach_wrap_id}</fromProcessItemId><toProcessItemId>{end_item_id}</toProcessItemId>
    </link>
  </process>
</teamworks>
'''




# =============================================================================
# Generic Markdown -> TWX layer
# =============================================================================

import argparse
import html
import re
import time
import xml.etree.ElementTree as ET
from html import unescape
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

# Exact ids from the validated Traditional System Data 8.6.0.0 dependency.
ALL_USERS_TEAM = f"{SYSDATA_DEP_UUID}/24.da7e4d23-78cb-4483-98ed-b9c238308a03"
SYSTEM_TEAM = f"{SYSDATA_DEP_UUID}/24.6fd38d02-81cf-48ab-bd42-8ff4c0a1628b"

SUPPORTED_NODE_TYPES = {"start", "end", "human", "system", "gateway", "external", "notification"}
SERVICE_LIKE_NODE_TYPES = {"system", "external", "notification"}
SUPPORTED_FIELD_TYPES = {"String", "Integer", "Decimal", "Boolean", "Date"}


# IBM BAW repository object-name safety.
#
# The HDB import failure reported DB2 SQLCODE=-545 / SQLSTATE=23513 on
# LSW_PO_VERSIONS.PO_NAME. Generated Process Designer artifacts are stored
# through this repository column, so standalone generated BAW object names
# must be kept within the repository-safe limit.
BAW_OBJECT_NAME_MAX = 64


def _baw_safe_name(value: str, max_len: int = BAW_OBJECT_NAME_MAX) -> str:
    """
    Return a deterministic BAW-safe repository object name.

    - strips leading/trailing whitespace;
    - collapses internal whitespace;
    - removes control characters;
    - keeps names <= max_len unchanged;
    - shortens longer names and appends an 8-char SHA1 suffix so two long
      names with the same prefix do not silently collide.

    Example:
      "A very long human task name ..." ->
      "A very long human task name ...~1a2b3c4d"
    """
    raw = str(value or "")
    cleaned = "".join(ch for ch in raw if ch >= " " and ch != "\x7f")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        raise ValueError("BAW repository object name cannot be empty")

    if len(cleaned) <= max_len:
        return cleaned

    suffix = "~" + hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
    prefix_len = max_len - len(suffix)
    return cleaned[:prefix_len].rstrip() + suffix


def _report_baw_name_adjustments(spec: dict) -> None:
    """
    Print any names that will be shortened during TWX generation.
    This is informational: preflight still succeeds because the generator
    fixes the repository-facing name automatically.
    """
    adjustments = []

    app = spec.get("app") or {}
    app_name = str(app.get("name") or "")
    if app_name and _baw_safe_name(app_name) != app_name.strip():
        adjustments.append(("Process App", app_name, _baw_safe_name(app_name)))

    for proc in spec.get("processes") or []:
        pname = str(proc.get("name") or "")
        if pname and _baw_safe_name(pname) != pname.strip():
            adjustments.append(("BPD", pname, _baw_safe_name(pname)))

        for node in proc.get("nodes") or []:
            if node.get("type") != "human":
                continue
            nname = str(node.get("name") or "")
            if nname and _baw_safe_name(nname) != nname.strip():
                adjustments.append(("Human Service", nname, _baw_safe_name(nname)))

    if adjustments:
        print("⚠️  BAW repository-name normalization will be applied:")
        for kind, original, safe in adjustments:
            print(f"   • {kind}: {original!r}")
            print(f"     → {safe!r} ({len(safe)} chars)")


def _validate_package_object_names(objects: list) -> None:
    """Fail locally if a generated repository object name is still unsafe."""
    seen = {}
    for oid, _ver, name, typ in objects:
        safe = _baw_safe_name(name)
        if name != safe:
            raise ValueError(
                f"Internal generator error: {typ} object {oid} still has an unsafe "
                f"repository name {name!r}; expected {safe!r}"
            )
        key = (typ, name.casefold())
        if key in seen:
            raise ValueError(
                f"Generated BAW object-name collision: {name!r} is used by both "
                f"{seen[key]} and {oid}. Rename one source task/process."
            )
        seen[key] = oid


def _x(s):
    return escape(str(s if s is not None else ""))


def _bid():
    return f"bpdid:{u()}"


def _now_ms():
    return str(int(time.time() * 1000))


def _slug(s):
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", str(s)).strip("-").lower()
    return s or "process"


def _normalize_acronym(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]", "", value or "").upper()
    if not value:
        value = "BAWAPP"
    return value[:12]


def extract_generator_spec(markdown_path: Path) -> dict:
    text = markdown_path.read_text(encoding="utf-8")
    # Preferred explicit marker. Tolerate json/JSON fenced blocks.
    patterns = [
        r"##\s+(?:\d+(?:\.\d+)*\s+)?BAW_GENERATOR_SPEC\s*\n\s*```(?:json|JSON)?\s*\n(.*?)\n```",
        r"<!--\s*BAW_GENERATOR_SPEC\s*-->\s*```(?:json|JSON)?\s*\n(.*?)\n```",
    ]
    raw = None
    for pat in patterns:
        m = re.search(pat, text, flags=re.S | re.I)
        if m:
            raw = m.group(1)
            break
    if raw is None:
        raise ValueError(
            "Markdown has no BAW_GENERATOR_SPEC JSON block. "
            "Ask Bob to read ibm-baw-twx-builder/SKILL.md and regenerate it "
            "by assembling the five JSON contracts with --contracts-dir."
        )
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"BAW_GENERATOR_SPEC is invalid JSON: {exc}") from exc
    validate_generator_spec(spec)
    return spec



def _validate_source_coverage(proc: dict, pname: str, node_ids) -> None:
    coverage = proc.get("source_coverage")
    if not isinstance(coverage, list) or not coverage:
        raise ValueError(
            f"{pname}: source_coverage is required. "
            "Every material BRD process step must be mapped before TWX generation."
        )

    seen_ids = set()
    seen_orders = set()
    represented_nodes = set()

    for idx, item in enumerate(coverage, 1):
        if not isinstance(item, dict):
            raise ValueError(f"{pname}: source_coverage[{idx}] must be an object")
        cid = str(item.get("id") or "").strip()
        activity = str(item.get("activity") or "").strip()
        source = str(item.get("source") or "").strip()
        order = item.get("order")
        disposition = str(item.get("disposition") or "represented").lower()
        refs = item.get("node_ids") or []

        if not cid or cid in seen_ids:
            raise ValueError(f"{pname}: every coverage item needs a unique id")
        seen_ids.add(cid)
        if not activity:
            raise ValueError(f"{pname}/{cid}: activity is required")
        if not source:
            raise ValueError(f"{pname}/{cid}: source reference is required")
        if not isinstance(order, int) or order < 1 or order in seen_orders:
            raise ValueError(f"{pname}/{cid}: order must be a unique positive integer")
        seen_orders.add(order)

        if disposition == "excluded":
            if not str(item.get("reason") or "").strip():
                raise ValueError(f"{pname}/{cid}: excluded step requires a source-supported reason")
            continue
        if disposition != "represented":
            raise ValueError(f"{pname}/{cid}: disposition must be represented or excluded")
        if not isinstance(refs, list) or not refs:
            raise ValueError(f"{pname}/{cid}: represented step requires node_ids")

        for nid in refs:
            if nid not in node_ids:
                raise ValueError(f"{pname}/{cid}: source coverage references unknown node {nid!r}")
            represented_nodes.add(nid)

    orders = sorted(seen_orders)
    if orders != list(range(1, len(orders) + 1)):
        raise ValueError(f"{pname}: source_coverage.order must be contiguous 1..N")

    required_nodes = {
        n["id"] for n in proc.get("nodes", [])
        if n.get("type") not in {"start", "end"}
    }
    missing = sorted(required_nodes - represented_nodes)
    if missing:
        raise ValueError(
            f"{pname}: generated nodes lack BRD source coverage: {', '.join(missing)}"
        )

    # Optional adjacency assertion. Multiple BRD sub-steps may legitimately map
    # to the same Coach/system node, so same-node pairs are not errors.
    flow_pairs = {(f.get("from"), f.get("to")) for f in proc.get("flows", [])}
    represented = sorted(
        [x for x in coverage if str(x.get("disposition") or "represented").lower() == "represented"],
        key=lambda x: x["order"],
    )
    for left, right in zip(represented, represented[1:]):
        if left.get("enforce_direct_flow", False) is not True:
            continue
        lrefs = left.get("node_ids") or []
        rrefs = right.get("node_ids") or []
        if len(lrefs) != 1 or len(rrefs) != 1:
            continue
        if lrefs[0] == rrefs[0]:
            continue
        if (lrefs[0], rrefs[0]) not in flow_pairs:
            raise ValueError(
                f"{pname}: source order mismatch between {left['id']} ({lrefs[0]}) "
                f"and {right['id']} ({rrefs[0]})."
            )


def _validate_graph(proc: dict, pname: str, node_by_id: dict, flows: List[dict]) -> None:
    incoming = {nid: [] for nid in node_by_id}
    outgoing = {nid: [] for nid in node_by_id}
    for flow in flows:
        incoming[flow["to"]].append(flow["from"])
        outgoing[flow["from"]].append(flow["to"])

    starts = [nid for nid, n in node_by_id.items() if n["type"] == "start"]
    ends = [nid for nid, n in node_by_id.items() if n["type"] == "end"]

    for nid, node in node_by_id.items():
        if node["type"] != "start" and not incoming[nid]:
            raise ValueError(f"{pname}/{nid}: non-start node has no incoming flow")
        if node["type"] != "end" and not outgoing[nid]:
            raise ValueError(f"{pname}/{nid}: non-end node has no outgoing flow")

    reachable = set(starts)
    stack = list(starts)
    while stack:
        cur = stack.pop()
        for nxt in outgoing[cur]:
            if nxt not in reachable:
                reachable.add(nxt)
                stack.append(nxt)
    unreachable = sorted(set(node_by_id) - reachable)
    if unreachable:
        raise ValueError(f"{pname}: unreachable nodes: {', '.join(unreachable)}")

    reverse_reachable = set(ends)
    stack = list(ends)
    while stack:
        cur = stack.pop()
        for prev in incoming[cur]:
            if prev not in reverse_reachable:
                reverse_reachable.add(prev)
                stack.append(prev)
    no_end_path = sorted(set(node_by_id) - reverse_reachable)
    if no_end_path:
        raise ValueError(f"{pname}: nodes cannot reach any end: {', '.join(no_end_path)}")


def _validate_return_contract(
    proc: dict,
    pname: str,
    node_by_id: dict,
    flows: List[dict],
    variable_catalog: dict,
) -> None:
    """Require a real two-way Return/rework loop with a visible comment."""
    outgoing = {nid: [] for nid in node_by_id}
    incoming = {nid: [] for nid in node_by_id}
    for flow in flows:
        outgoing[flow["from"]].append(flow)
        incoming[flow["to"]].append(flow["from"])

    def is_return(flow: dict, action_values: dict) -> bool:
        label = str(flow.get("label") or "").strip().lower()
        value = str(flow.get("value") or "").strip().lower()
        mapped = str(action_values.get(flow.get("label"), "")).strip().lower()
        return label == "return" or value == "return" or mapped == "return"

    def has_path(start: str, target: str) -> bool:
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur == target:
                return True
            for flow in outgoing.get(cur, []):
                nxt = flow["to"]
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    def has_previous_human(task_id: str) -> bool:
        """Return is valid only when an earlier human task can receive it."""
        seen = {task_id}
        stack = list(incoming.get(task_id, []))
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if node_by_id.get(cur, {}).get("type") == "human":
                return True
            stack.extend(incoming.get(cur, []))
        return False

    # A Coach may receive one return comment as read-only context while also
    # sending a different return comment onward. Reusing one variable for both
    # directions creates an impossible editable/read-only contract and caused
    # Bob to repair the same spec repeatedly. Require one sender variable per
    # independent Return edge so the receiver mapping is unambiguous.
    return_senders = {}
    for node in node_by_id.values():
        if node.get("type") != "human":
            continue
        actions = [str(x).strip() for x in (node.get("actions") or [])]
        action_values = dict(node.get("action_values") or {})
        if not any(
            label.lower() == "return" or str(action_values.get(label, "")).strip().lower() == "return"
            for label in actions
        ):
            continue
        history_cfg = node.get("comment_history") or node.get("history_view") or {}
        shared_draft = str(history_cfg.get("draft_variable") or "").strip()
        if shared_draft:
            # A single shared draft is intentionally reused by all human
            # tasks; it is not a separate sender-owned return variable.
            continue
        comment_name = shared_draft or str(node.get("return_comment") or "").strip()
        if not comment_name:
            candidates = [
                str(f.get("name") or "")
                for f in node.get("fields") or []
                if "comment" in str(f.get("name") or "").lower()
                or "reason" in str(f.get("name") or "").lower()
            ]
            if len(candidates) == 1:
                comment_name = candidates[0]
        if comment_name:
            sender = return_senders.get(comment_name)
            if sender and sender != node["id"]:
                raise ValueError(
                    f"{pname}: Return comment variable {comment_name!r} is written by "
                    f"both {sender!r} and {node['id']!r}; use a separate comment variable "
                    "for each Return direction"
                )
            return_senders[comment_name] = node["id"]

    for node in node_by_id.values():
        if node.get("type") != "human":
            continue
        actions = [str(x).strip() for x in (node.get("actions") or [])]
        action_values = dict(node.get("action_values") or {})
        if not any(
            label.lower() == "return" or str(action_values.get(label, "")).strip().lower() == "return"
            for label in actions
        ):
            continue

        if not has_previous_human(node["id"]):
            raise ValueError(
                f"{pname}/{node['id']}: the first human Coach cannot have a Return action; "
                "Return is only valid when a previous editable human task exists"
            )

        decision = str(node.get("decision_output") or "").strip()
        if not decision:
            raise ValueError(f"{pname}/{node['id']}: Return requires decision_output")
        if decision not in variable_catalog:
            raise ValueError(f"{pname}/{node['id']}: Return decision_output {decision!r} is undeclared")

        history_cfg = node.get("comment_history") or node.get("history_view") or {}
        shared_draft = str(history_cfg.get("draft_variable") or "").strip()
        comment_name = shared_draft or str(node.get("return_comment") or "").strip()
        if not comment_name:
            candidates = [
                str(f.get("name") or "")
                for f in node.get("fields") or []
                if "comment" in str(f.get("name") or "").lower()
                or "reason" in str(f.get("name") or "").lower()
            ]
            if len(candidates) == 1:
                comment_name = candidates[0]
        if not comment_name:
            raise ValueError(f"{pname}/{node['id']}: Return requires return_comment")

        current_field = next(
            (f for f in node.get("fields") or [] if f.get("name") == comment_name),
            None,
        )
        if not current_field or current_field.get("read_only") or (not shared_draft and not current_field.get("required")):
            raise ValueError(
                f"{pname}/{node['id']}: Return comment {comment_name!r} must be an editable field"
            )
        if comment_name not in variable_catalog:
            raise ValueError(f"{pname}/{node['id']}: Return comment {comment_name!r} is undeclared")

        # Return is a Coach action with a direct sequence flow to the previous
        # editable task. Do not synthesize a separate gateway solely to store
        # whether the user clicked Return; the Coach action output is enough.
        return_targets = [
            flow["to"]
            for flow in outgoing.get(node["id"], [])
            if is_return(flow, action_values)
        ]
        indirect_return = any(
            node_by_id.get(flow["to"], {}).get("type") == "gateway"
            and any(is_return(branch, action_values) for branch in outgoing.get(flow["to"], []))
            for flow in outgoing.get(node["id"], [])
        )
        if indirect_return:
            raise ValueError(
                f"{pname}/{node['id']}: Return must be a direct Coach action flow to the previous editable task; "
                "do not add a Return-only gateway"
            )
        if not return_targets:
            raise ValueError(f"{pname}/{node['id']}: Return has no explicit rework flow")

        for target_id in return_targets:
            target = node_by_id[target_id]
            if target.get("type") != "human" or target_id == node["id"]:
                raise ValueError(
                    f"{pname}/{node['id']}: Return must target a previous editable human task"
                )
            target_field = next(
                (f for f in target.get("fields") or [] if f.get("name") == comment_name),
                None,
            )
            target_inputs = target.get("inputs")
            if not target_field or (not shared_draft and not target_field.get("read_only")):
                raise ValueError(
                    f"{pname}/{node['id']}: receiving task {target_id!r} must show {comment_name!r} in its input contract"
                )
            if target_inputs is not None and comment_name not in target_inputs:
                raise ValueError(
                    f"{pname}/{node['id']}: receiving task {target_id!r} must input {comment_name!r}"
                )
            # A returned Coach must reopen with its complete context and with
            # source-owned fields still editable. Omitting those input mappings
            # causes BAW to render an empty form on the return path.
            target_fields = [
                str(field.get("name") or "").strip()
                for field in target.get("fields") or []
                if str(field.get("name") or "").strip()
            ]
            if target_inputs is None:
                raise ValueError(
                    f"{pname}/{node['id']}: receiving task {target_id!r} must explicitly declare inputs for Return/rework"
                )
            missing_inputs = [name for name in target_fields if name not in target_inputs]
            if missing_inputs:
                raise ValueError(
                    f"{pname}/{node['id']}: receiving task {target_id!r} must input every displayed field on Return; missing {', '.join(missing_inputs)}"
                )
            target_outputs = set(str(x).strip() for x in (target.get("outputs") or []) if str(x).strip())
            editable_fields = [
                str(field.get("name") or "").strip()
                for field in target.get("fields") or []
                if not field.get("read_only") and str(field.get("name") or "").strip()
            ]
            missing_outputs = [name for name in editable_fields if name not in target_outputs]
            if missing_outputs:
                raise ValueError(
                    f"{pname}/{node['id']}: receiving task {target_id!r} must output every editable returned field; missing {', '.join(missing_outputs)}"
                )
            if not has_path(target_id, node["id"]):
                raise ValueError(
                    f"{pname}/{node['id']}: Return target {target_id!r} is not a previous loop task"
                )


def validate_generator_spec(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise ValueError("Generator spec must be a JSON object")
    _apply_comment_history_contract(spec)
    app = spec.get("app") or {}
    for key in ("name", "acronym"):
        if not app.get(key):
            raise ValueError(f"app.{key} is required")
    if ":" in app.get("name", ""):
        raise ValueError("Process App name must not contain ':'")

    processes = spec.get("processes")
    if not isinstance(processes, list) or not processes:
        raise ValueError("processes must be a non-empty array")

    proc_names = set()
    for pidx, proc in enumerate(processes, 1):
        pname = proc.get("name")
        if not pname:
            raise ValueError(f"processes[{pidx}].name is required")
        if ":" in pname:
            raise ValueError(f"Process name {pname!r} must not contain ':'")
        if pname in proc_names:
            raise ValueError(f"Duplicate process name: {pname}")
        proc_names.add(pname)

        lanes = proc.get("lanes") or []
        lane_specs = _lane_specs(proc)
        lane_names = [x["name"] for x in lane_specs]
        if not lane_names or len(set(lane_names)) != len(lane_names):
            raise ValueError(f"{pname}: lanes must be a non-empty unique list")
        lane_system = {x["name"]: x["system"] for x in lane_specs}

        nodes = proc.get("nodes") or []
        node_ids = set()
        starts = 0
        ends = 0
        for node in nodes:
            nid = node.get("id")
            ntype = node.get("type")
            if not nid or nid in node_ids:
                raise ValueError(f"{pname}: every node needs a unique id")
            node_ids.add(nid)
            if ntype not in SUPPORTED_NODE_TYPES:
                raise ValueError(f"{pname}/{nid}: unsupported node type {ntype!r}")
            lane = node.get("lane")
            if lane not in lane_system:
                raise ValueError(f"{pname}/{nid}: lane {lane!r} is not declared")
            if ntype == "start":
                starts += 1
            if ntype == "end":
                ends += 1
            if ntype == "human":
                if lane_system[lane]:
                    raise ValueError(f"{pname}/{nid}: human task cannot be placed in a system lane")
                if not node.get("actions"):
                    node["actions"] = ["Submit"]
                if any(str(action).strip().lower() == "close" for action in node.get("actions") or []):
                    raise ValueError(
                        f"{pname}/{nid}: Close is generated as a UI-only Coach Flow action; "
                        "do not declare it in business actions or route it through a gateway"
                    )
                for field_spec in node.get("fields", []):
                    field_type = field_spec.get("type", "String")
                    if field_type not in SUPPORTED_FIELD_TYPES:
                        raise ValueError(
                            f"{pname}/{nid}: field {field_spec.get('name')!r} uses unsupported "
                            f"type {field_type!r}; refusing to flatten it to String"
                        )
                    options = field_spec.get("options") or []
                    if options and field_type == "Boolean":
                        raise ValueError(
                            f"{pname}/{nid}: Boolean field {field_spec.get('name')!r} should use "
                            "the native checkbox; use options only for finite non-Boolean choices"
                        )
                    if options:
                        try:
                            normalized = _normalise_select_options(options)
                        except ValueError as exc:
                            raise ValueError(
                                f"{pname}/{nid}: invalid options for field {field_spec.get('name')!r}: {exc}"
                            ) from exc
                        names = [str(item["name"]) for item in normalized]
                        if len(names) != len(set(names)):
                            raise ValueError(
                                f"{pname}/{nid}: select options for field {field_spec.get('name')!r} "
                                "must have unique stored values"
                            )

        if starts < 1 or ends < 1:
            raise ValueError(f"{pname}: at least one start and one end node are required")

        # Do not allow an empty declared human lane.
        for lane in lane_specs:
            if lane["system"]:
                continue
            has_human = any(n.get("type") == "human" and n.get("lane") == lane["name"] for n in nodes)
            if not has_human:
                raise ValueError(
                    f"{pname}: human lane {lane['name']!r} has no human task. "
                    "Remove the lane or represent the missing reviewer/user activity."
                )

        flows = proc.get("flows") or []
        if not flows:
            raise ValueError(f"{pname}: flows are required")
        for flow in flows:
            if flow.get("from") not in node_ids or flow.get("to") not in node_ids:
                raise ValueError(f"{pname}: flow references unknown node: {flow}")

        node_by_id = {n["id"]: n for n in nodes}
        _validate_graph(proc, pname, node_by_id, flows)

        by_src = {}
        for flow in flows:
            by_src.setdefault(flow["from"], []).append(flow)
        for nid, outs in by_src.items():
            if node_by_id[nid]["type"] != "gateway" or len(outs) <= 1:
                continue
            defaults = [f for f in outs if f.get("demo_default") is True]
            if len(defaults) == 0:
                outs[0]["demo_default"] = True
            elif len(defaults) > 1:
                raise ValueError(f"{pname}/{nid}: only one outgoing flow may be demo_default=true")

        # Validate process-variable catalog and human-task mappings.
        variable_catalog = _process_variable_catalog(proc)
        _validate_field_control_contract(proc, pname, variable_catalog)
        for node in nodes:
            if node.get("type") == "human":
                field_names = {
                    str(field.get("name") or "").strip()
                    for field in node.get("fields") or []
                    if str(field.get("name") or "").strip()
                }
                decision_name = node.get("decision_output") or _infer_human_decision_variable(node, variable_catalog)
                allowed_mapping_names = field_names | ({str(decision_name).strip()} if decision_name else set())
                for direction in ("inputs", "outputs"):
                    declared = node.get(direction)
                    if declared is None:
                        continue
                    extras = sorted({str(name).strip() for name in declared if str(name).strip()} - allowed_mapping_names)
                    if extras:
                        raise ValueError(
                            f"{pname}/{node['id']}: {direction} contains {', '.join(extras)} "
                            "but the Coach has no matching field; add a visible, read-only, "
                            "or hidden field before declaring that mapping"
                        )
                _human_mapping_names(node, variable_catalog)
                if len(node.get("actions") or []) > 1:
                    decision = node.get("decision_output") or _infer_human_decision_variable(node, variable_catalog)
                    if not decision:
                        raise ValueError(
                            f"{pname}/{node['id']}: multi-action human task requires "
                            "decision_output or one mapped output named decision/action/choice/selection"
                        )
                    if decision not in variable_catalog:
                        raise ValueError(
                            f"{pname}/{node['id']}: decision_output {decision!r} is not a declared process variable"
                        )
            elif node.get("type") == "gateway" and node.get("decision_variable"):
                if node["decision_variable"] not in variable_catalog:
                    raise ValueError(f"{pname}/{node['id']}: undeclared gateway decision_variable {node['decision_variable']!r}")

        _validate_return_contract(proc, pname, node_by_id, flows, variable_catalog)

        _validate_source_coverage(proc, pname, node_ids)


def _lane_specs(proc):
    result = []
    for lane in proc["lanes"]:
        if isinstance(lane, str):
            result.append({"name": lane, "system": lane.strip().lower() in {"system", "systems"}})
        else:
            result.append({"name": lane["name"], "system": bool(lane.get("system", False))})
    return result



def _process_variable_catalog(proc: dict) -> dict:
    """
    Build the process-level variable catalog.

    Preferred contract:
        proc["variables"] = [
            {"name": "customerCIF", "type": "String", "scope": "private"},
            ...
        ]

    Backward-compatible behavior:
    If variables are not explicitly declared, derive them from all human-task
    fields. A field name may appear on multiple Coaches, but its type must be
    consistent across the process.
    """
    catalog = {}

    explicit = proc.get("variables") or []
    for v in explicit:
        name = str(v.get("name") or "").strip()
        if not name:
            raise ValueError(f"{proc['name']}: process variable name is required")
        vtype = v.get("type", "String")
        if vtype not in SUPPORTED_FIELD_TYPES and vtype != "CommentHistoryList":
            raise ValueError(
                f"{proc['name']}: process variable {name!r} uses unsupported type "
                f"{vtype!r}; define a verified native Business Object mapping or use a primitive"
            )
        scope = str(v.get("scope") or "private").lower()
        if scope not in {"private", "input", "output", "input_output"}:
            scope = "private"
        catalog[name] = {
            "name": name,
            "type": vtype,
            "scope": scope,
        }
        for key in ("value_domain", "control", "options"):
            if key in v:
                catalog[name][key] = v[key]
        if "default" in v:
            catalog[name]["default"] = v["default"]
        if vtype == "CommentHistoryList":
            catalog[name]["history"] = deepcopy(v.get("history") or {})
            history = catalog[name]["history"]
            entry_id = str(history.get("entry_class_id") or history.get("class_id") or "")
            if entry_id:
                bare = entry_id.split("/")[-1]
                if not bare.startswith("12."):
                    bare = "12." + bare.split(".", 1)[-1]
                catalog[name]["class_id"] = f"/{bare}"
                catalog[name]["item_subject_ref"] = f"itm.{bare}"
            catalog[name]["is_collection"] = True

    for node in proc.get("nodes") or []:
        if node.get("type") != "human":
            continue
        for field_spec in node.get("fields") or []:
            name = str(field_spec.get("name") or "").strip()
            if not name:
                continue
            ftype = field_spec.get("type", "String")
            if ftype not in SUPPORTED_FIELD_TYPES:
                raise ValueError(
                    f"{proc['name']}: field {name!r} uses unsupported type {ftype!r}; "
                    "refusing to flatten it to String"
                )
            if name in catalog and catalog[name]["type"] != ftype:
                raise ValueError(
                    f"{proc['name']}: process variable {name!r} is used with "
                    f"conflicting types {catalog[name]['type']!r} and {ftype!r}"
                )
            catalog.setdefault(name, {
                "name": name,
                "type": ftype,
                # Derived Coach data must persist across activities, therefore
                # it is process-private unless the spec explicitly exposes it.
                "scope": "private",
            })
            # Field-level metadata is also retained at process level so a
            # declared variable and every Coach occurrence can be checked
            # against the same value-domain/control decision.
            for key in ("value_domain", "control", "options"):
                if key in field_spec and key not in catalog[name]:
                    catalog[name][key] = field_spec[key]

    # Placeholder system services intentionally do not call the real external
    # system yet. For a system-driven gateway, preflight may infer a demo
    # initialization value from the gateway's demo_default branch. This keeps
    # the executable demo on the reviewed happy/default path without inventing
    # a fake Temenos/API contract or service mapping.
    for name, value in (proc.get("_demo_variable_defaults") or {}).items():
        if name in catalog and "default" not in catalog[name]:
            catalog[name]["default"] = value

    return catalog


def _validate_field_control_contract(proc: dict, pname: str, variable_catalog: dict) -> None:
    """Require an explicit domain/control decision for every visible Coach field.

    This prevents a String field from silently becoming free text when the
    value is actually a finite business choice.  Bob may infer a conservative
    domain when the BRD is silent, but it must put the proposed values in
    ``options`` and record the inference in the specification assumptions.
    """
    finite_domains = {"finite", "enum", "categorical", "bounded", "finite_choice"}
    open_domains = {"open", "open_text", "narrative", "free_text"}
    choice_controls = {"single_select", "dropdown", "select"}
    text_controls = {"text", "text_area", "textarea", "free_text"}
    numeric_controls = {"number", "numeric", "decimal", "integer"}
    date_controls = {"date", "date_picker", "datepicker"}

    for node in proc.get("nodes") or []:
        if node.get("type") != "human":
            continue
        for field in node.get("fields") or []:
            if field.get("hidden"):
                continue
            name = str(field.get("name") or "").strip()
            if not name:
                raise ValueError(f"{pname}/{node.get('id')}: every Coach field needs a name")
            ftype = str(field.get("type") or "String")
            meta = variable_catalog.get(name) or {}
            read_only = bool(field.get("read_only", False))
            domain = str(field.get("value_domain") or meta.get("value_domain") or "").strip().lower()
            control = str(field.get("control") or meta.get("control") or "").strip().lower()
            options = field.get("options")
            if options is None:
                options = meta.get("options")
            options = options or []

            # A read-only occurrence is rendered with the native Output Text
            # widget, even when the same process variable is finite or numeric
            # on its editable Coach. Do not force Bob to relabel a display copy
            # as a dropdown or invent a second domain just to satisfy the
            # editable-field contract; type safety is still checked below.
            if read_only and ftype == "String":
                if control and control not in text_controls | choice_controls:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: read-only String field {name!r} "
                        f"has unsupported display control {control!r}"
                    )
                continue

            if ftype == "Boolean":
                if options:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: Boolean field {name!r} must use a native checkbox, not options"
                    )
                if control and control not in {"checkbox", "boolean"}:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: Boolean field {name!r} has invalid control {control!r}"
                    )
                continue

            if ftype == "Date":
                if control and control not in date_controls:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: Date field {name!r} must use a native date control"
                    )
                continue

            if ftype in {"Integer", "Decimal"}:
                if options:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: numeric field {name!r} cannot use dropdown options"
                    )
                if control and control not in numeric_controls:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: numeric field {name!r} must use a numeric control"
                    )
                continue

            if not domain:
                raise ValueError(
                    f"{pname}/{node.get('id')}: field {name!r} must declare value_domain "
                    "(finite or open) and control before generation"
                )
            if domain in finite_domains:
                if not options:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: finite field {name!r} must declare options for a dropdown"
                    )
                if control and control not in choice_controls:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: finite field {name!r} must use Single Select/dropdown"
                    )
            elif domain in open_domains:
                if options:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: open field {name!r} must not declare dropdown options"
                    )
                if control and control not in text_controls:
                    raise ValueError(
                        f"{pname}/{node.get('id')}: open field {name!r} must use text or Text Area"
                    )
            else:
                raise ValueError(
                    f"{pname}/{node.get('id')}: field {name!r} has unsupported value_domain {domain!r}"
                )


def _human_mapping_names(node: dict, catalog: dict):
    """
    Resolve which process variables a human task reads/writes.

    Explicit node["inputs"] / node["outputs"] override inference.
    Backward-compatible inference:
      - every Coach field is an input, so later/rework tasks can see values;
      - editable fields are outputs;
      - read-only fields are input-only.
    """
    fields = node.get("fields") or []
    field_names = [str(f.get("name") or "").strip() for f in fields if f.get("name")]
    inferred_inputs = field_names
    inferred_outputs = [
        str(f.get("name") or "").strip()
        for f in fields
        if f.get("name") and not bool(f.get("read_only", False))
    ]

    inputs = node.get("inputs")
    outputs = node.get("outputs")
    if inputs is None:
        inputs = inferred_inputs
    if outputs is None:
        outputs = inferred_outputs

    inputs = list(dict.fromkeys(str(x).strip() for x in inputs if str(x).strip()))
    outputs = list(dict.fromkeys(str(x).strip() for x in outputs if str(x).strip()))

    # Comment history is shared process data, not a Coach-local display value.
    # A history-enabled CSHS already declares the list as an input/output and
    # appends the new row before End.  The parent BPD User Task must mirror
    # that contract even when the BRD-facing node lists explicit inputs and
    # outputs that omit this implementation-owned audit variable.  Without
    # these two activity mappings the append succeeds inside the first human
    # service, but the updated list is discarded when that service completes,
    # so the following Coach receives an empty history.
    history = node.get("comment_history") or node.get("history_view") or {}
    if history:
        history_name = str(
            history.get("variable_name") or history.get("name") or "commentHistory"
        ).strip()
        history_meta = catalog.get(history_name)
        if not history_meta or not _is_collection_meta(history_meta):
            raise ValueError(
                f"{node.get('name', node.get('id'))}: comment-history variable "
                f"{history_name!r} is not declared as CommentHistoryList"
            )
        if history_name not in inputs:
            inputs.append(history_name)
        if history_name not in outputs:
            outputs.append(history_name)

    unknown = sorted((set(inputs) | set(outputs)) - set(catalog))
    if unknown:
        raise ValueError(
            f"{node.get('name', node.get('id'))}: task mapping references unknown "
            f"process variables: {', '.join(unknown)}"
        )
    return inputs, outputs


def _make_process_io(proc: dict) -> dict:
    """Assign native/BPMN ids to the process-level variable catalog."""
    catalog = _process_variable_catalog(proc)
    result = {}
    for name, meta in catalog.items():
        result[name] = {
            **meta,
            "class_id": _meta_class_id(meta),
            "item_subject_ref": _meta_item_subject_ref(meta),
            "is_collection": _is_collection_meta(meta),
            "input_id": f"2055.{u()}",
            "output_id": f"2055.{u()}",
        }
    return result


def _bpmn_io_spec_xml(io_map: dict, names_in=None, names_out=None, prefix="ns7") -> str:
    names_in = list(names_in if names_in is not None else io_map.keys())
    names_out = list(names_out if names_out is not None else io_map.keys())

    data_inputs = "".join(
        f'<{prefix}:dataInput id="{io_map[n]["input_id"]}" '
        f'name="{_x(n)}" itemSubjectRef="{_x(io_map[n]["item_subject_ref"])}" '
        f'isCollection="{str(bool(io_map[n].get("is_collection", False))).lower()}"/>'
        for n in names_in
    )
    data_outputs = "".join(
        f'<{prefix}:dataOutput id="{io_map[n]["output_id"]}" '
        f'name="{_x(n)}" itemSubjectRef="{_x(io_map[n]["item_subject_ref"])}" '
        f'isCollection="{str(bool(io_map[n].get("is_collection", False))).lower()}"/>'
        for n in names_out
    )
    input_refs = "".join(
        f'<{prefix}:dataInputRefs>{io_map[n]["input_id"]}</{prefix}:dataInputRefs>'
        for n in names_in
    )
    output_refs = "".join(
        f'<{prefix}:dataOutputRefs>{io_map[n]["output_id"]}</{prefix}:dataOutputRefs>'
        for n in names_out
    )
    return (
        f'<{prefix}:ioSpecification>'
        f'{data_inputs}{data_outputs}'
        f'<{prefix}:inputSet id="_{u()}">{input_refs}</{prefix}:inputSet>'
        f'<{prefix}:outputSet id="_{u()}">{output_refs}</{prefix}:outputSet>'
        f'</{prefix}:ioSpecification>'
    )


def _bpmn_activity_mapping_xml(process_io: dict, task_io: dict, inputs, outputs, prefix="ns7") -> str:
    """Create explicit input/output data associations for a human activity."""
    parts = []
    for name in inputs:
        parts.append(
            f'<{prefix}:dataInputAssociation id="_{u()}">'
            f'<{prefix}:sourceRef>{process_io[name]["input_id"]}</{prefix}:sourceRef>'
            f'<{prefix}:targetRef>{task_io[name]["input_id"]}</{prefix}:targetRef>'
            f'</{prefix}:dataInputAssociation>'
        )
    for name in outputs:
        parts.append(
            f'<{prefix}:dataOutputAssociation id="_{u()}">'
            f'<{prefix}:sourceRef>{task_io[name]["output_id"]}</{prefix}:sourceRef>'
            f'<{prefix}:targetRef>{process_io[name]["output_id"]}</{prefix}:targetRef>'
            f'</{prefix}:dataOutputAssociation>'
        )
    return "".join(parts)



def _bpmn_process_data_objects(process_io: dict, prefix="ns7") -> str:
    parts = []
    for name, meta in process_io.items():
        typ = meta.get("type", "String")
        if _is_collection_meta(meta):
            parts.append(
                f'<{prefix}:dataObject itemSubjectRef="{_x(meta["item_subject_ref"])}" '
                f'isCollection="true" name="{_x(name)}" id="{_bid()}"><{prefix}:extensionElements>'
                f'<ns3:isProcessIdentifier>false</ns3:isProcessIdentifier></{prefix}:extensionElements></{prefix}:dataObject>'
            )
            continue
        if "default" in meta:
            val = meta["default"]
        elif typ == "Boolean":
            val = False
        elif typ in {"Integer", "Decimal"}:
            val = 0
        elif typ == "String":
            val = ""
        else:
            val = None

        default_expr = None
        if val is not None:
            if typ == "Boolean":
                default_expr = "true" if bool(val) else "false"
            elif typ in {"Integer", "Decimal"}:
                default_expr = str(val)
            elif typ == "String":
                default_expr = '"' + str(val).replace("\\", "\\\\").replace('"', '\\"') + '"'

        ext = f'<{prefix}:extensionElements>'
        if default_expr is not None:
            ext += f'<ns2:defaultValue useDefault="true">{_x(default_expr)}</ns2:defaultValue>'
        ext += f'<ns3:isProcessIdentifier>false</ns3:isProcessIdentifier></{prefix}:extensionElements>'
        parts.append(
            f'<{prefix}:dataObject itemSubjectRef="{_x(meta["item_subject_ref"])}" '
            f'isCollection="{str(bool(meta.get("is_collection", False))).lower()}" name="{_x(name)}" id="{_bid()}">{ext}</{prefix}:dataObject>'
        )
    return "".join(parts)


def _json_process_data_objects(process_io: dict) -> list:
    result = []
    for name, meta in process_io.items():
        typ = meta.get("type", "String")
        if _is_collection_meta(meta):
            result.append({
                "declaredType": "dataObject",
                "id": _bid(),
                "name": name,
                "itemSubjectRef": meta["item_subject_ref"],
                "isCollection": True,
                "extensionElements": {"isProcessIdentifier": [False]},
            })
            continue
        if "default" in meta:
            val = meta["default"]
        elif typ == "Boolean":
            val = False
        elif typ in {"Integer", "Decimal"}:
            val = 0
        elif typ == "String":
            val = ""
        else:
            val = None

        ext = {"isProcessIdentifier": [False]}
        if val is not None:
            if typ == "Boolean":
                dv = "true" if bool(val) else "false"
            elif typ in {"Integer", "Decimal"}:
                dv = str(val)
            else:
                dv = '"' + str(val).replace("\\", "\\\\").replace('"', '\\"') + '"'
            ext["defaultValue"] = [{
                "declaredType": "com.ibm.bpmsdk.model.bpmn20.ibmext.TDefaultValue",
                "useDefault": True,
                "value": dv,
            }]
        result.append({
            "declaredType": "dataObject",
            "id": _bid(),
            "name": name,
            "itemSubjectRef": meta["item_subject_ref"],
            "isCollection": bool(meta.get("is_collection", False)),
            "extensionElements": ext,
        })
    return result


def _bpmn_activity_assignment_mapping_xml(task_io: dict, inputs, outputs, prefix="ns7") -> str:
    parts = []
    for name in inputs:
        typeref = "/" + task_io[name]["item_subject_ref"].replace("itm.", "")
        parts.append(
            f'<{prefix}:dataInputAssociation>'
            f'<{prefix}:targetRef>{task_io[name]["input_id"]}</{prefix}:targetRef>'
            f'<{prefix}:assignment>'
            f'<{prefix}:from xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="{prefix}:tFormalExpression" evaluatesToTypeRef="{_x(typeref)}">'
            f'tw.local.{_x(name)}</{prefix}:from>'
            f'</{prefix}:assignment>'
            f'</{prefix}:dataInputAssociation>'
        )
    for name in outputs:
        item_ref = task_io[name]["item_subject_ref"]
        parts.append(
            f'<{prefix}:dataOutputAssociation>'
            f'<{prefix}:sourceRef>{task_io[name]["output_id"]}</{prefix}:sourceRef>'
            f'<{prefix}:assignment>'
            f'<{prefix}:extensionElements><ns4:mappingMode>simple</ns4:mappingMode></{prefix}:extensionElements>'
            f'<{prefix}:from xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="{prefix}:tFormalExpression" evaluatesToTypeRef="{_x(item_ref)}">'
            f'tw.outputs.{_x(name)}</{prefix}:from>'
            f'<{prefix}:to xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="{prefix}:tFormalExpression" evaluatesToTypeRef="{_x(item_ref)}">'
            f'tw.local.{_x(name)}</{prefix}:to>'
            f'</{prefix}:assignment>'
            f'</{prefix}:dataOutputAssociation>'
        )
    return "".join(parts)


def _json_activity_assignment_associations(task_io: dict, inputs, outputs):
    return {
        "dataInputAssociation": [
            {
                "targetRef": task_io[name]["input_id"],
                "assignment": [{
                    "from": {
                        "declaredType": "TFormalExpression",
                        "evaluatesToTypeRef": "/" + task_io[name]["item_subject_ref"].replace("itm.", ""),
                        "content": [f"tw.local.{name}"],
                    }
                }],
            }
            for name in inputs
        ],
        "dataOutputAssociation": [
            {
                "sourceRef": [task_io[name]["output_id"]],
                "assignment": [{
                    "extensionElements": {"mappingMode": ["simple"]},
                    "from": {
                        "declaredType": "TFormalExpression",
                        "evaluatesToTypeRef": task_io[name]["item_subject_ref"],
                        "content": [f"tw.outputs.{name}"],
                    },
                    "to": {
                        "declaredType": "TFormalExpression",
                        "evaluatesToTypeRef": task_io[name]["item_subject_ref"],
                        "content": [f"tw.local.{name}"],
                    },
                }],
            }
            for name in outputs
        ],
    }


def _json_io_spec(io_map: dict, names_in=None, names_out=None) -> dict:
    names_in = list(names_in if names_in is not None else io_map.keys())
    names_out = list(names_out if names_out is not None else io_map.keys())
    return {
        "dataInput": [
            {
                "id": io_map[n]["input_id"],
                "name": n,
                "itemSubjectRef": io_map[n]["item_subject_ref"],
                "isCollection": bool(io_map[n].get("is_collection", False)),
            }
            for n in names_in
        ],
        "dataOutput": [
            {
                "id": io_map[n]["output_id"],
                "name": n,
                "itemSubjectRef": io_map[n]["item_subject_ref"],
                "isCollection": bool(io_map[n].get("is_collection", False)),
            }
            for n in names_out
        ],
        "inputSet": [{
            "id": f"_{u()}",
            "dataInputRefs": [io_map[n]["input_id"] for n in names_in],
        }],
        "outputSet": [{
            "id": f"_{u()}",
            "dataOutputRefs": [io_map[n]["output_id"] for n in names_out],
        }],
    }


def _json_activity_associations(process_io: dict, task_io: dict, inputs, outputs):
    return {
        "dataInputAssociation": [
            {
                "id": f"_{u()}",
                "sourceRef": [process_io[n]["input_id"]],
                "targetRef": task_io[n]["input_id"],
            }
            for n in inputs
        ],
        "dataOutputAssociation": [
            {
                "id": f"_{u()}",
                "sourceRef": [task_io[n]["output_id"]],
                "targetRef": process_io[n]["output_id"],
            }
            for n in outputs
        ],
    }


def _infer_human_decision_variable(node: dict, catalog: Optional[dict] = None) -> Optional[str]:
    catalog = catalog or {}

    explicit = str(node.get("decision_output") or "").strip()
    if explicit and (not catalog or explicit in catalog):
        return explicit

    outputs = [str(x).strip() for x in (node.get("outputs") or []) if str(x).strip()]
    direct = [x for x in outputs if re.search(r"(decision|action|choice|selection)$", x, re.I)]
    if len(direct) == 1:
        return direct[0]

    candidates = [name for name in catalog if re.search(r"(decision|action|choice|selection)$", name, re.I)]
    if not candidates:
        return None

    ctx = " ".join([str(node.get("name") or ""), str(node.get("lane") or ""), str(node.get("id") or "")]).lower()
    scored = []
    for name in candidates:
        low = name.lower()
        score = 0
        for token in ("maker","checker","manager","approver","reviewer","operator"):
            if token in ctx and token in low:
                score += 10
        if "break" in ctx and "break" in low:
            score += 8
        if "creation" in ctx and "creation" in low:
            score += 8
        if any(t in ctx for t in ("capture","submit","request","check","cancel")) and any(t in low for t in ("submission","submit")):
            score += 5
        scored.append((score, name))
    scored.sort(reverse=True)

    if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _human_task_from_node(node: dict, catalog: Optional[dict] = None) -> HumanTaskSpec:
    fields = []
    for f in node.get("fields", []):
        fields.append(FieldSpec(
            name=f.get("name") or _slug(f.get("label", "field")).replace("-", "_"),
            label=f.get("label") or f.get("name") or "Field",
            field_type=f.get("type", "String"),
            required=bool(f.get("required", False)),
            read_only=bool(f.get("read_only", False)),
            hidden=bool(f.get("hidden", False)),
            options=list(
                f.get("options")
                or (catalog or {}).get(str(f.get("name") or "").strip(), {}).get("options")
                or []
            ),
            placeholder=str(f.get("placeholder") or ""),
        ))

    field_names = [f.name for f in fields]
    raw_inputs = node.get("inputs")
    raw_outputs = node.get("outputs")
    if raw_inputs is None:
        raw_inputs = field_names
    if raw_outputs is None:
        raw_outputs = [f.name for f in fields if not f.read_only]

    input_names = list(dict.fromkeys(
        str(x).strip() for x in raw_inputs if str(x).strip()
    ))
    output_names = list(dict.fromkeys(
        str(x).strip() for x in raw_outputs if str(x).strip()
    ))

    history_meta = next(
        (
            meta for meta in (catalog or {}).values()
            if meta.get("type") == "CommentHistoryList"
        ),
        None,
    )
    history = node.get("comment_history") or node.get("history_view")
    if history_meta:
        history = dict(history_meta.get("history") or {}, **(history or {}))
        history_name = str(history.get("variable_name") or history.get("name") or "commentHistory")
        if history_name not in input_names:
            input_names.append(history_name)
        # The Coach appends rows on submit/return/forward.  Map the shared
        # list back out of the human service so those mutations persist in
        # the process variable rather than remaining only in the Coach.
        if history_name not in output_names:
            output_names.append(history_name)

    actions = list(node.get("actions") or ["Submit"])
    decision_output = None
    if len(actions) > 1:
        decision_output = node.get("decision_output") or _infer_human_decision_variable(node, catalog)

    # Target-environment verified behavior:
    # action/decision state is a hidden CSHS OUTPUT.
    if decision_output:
        if decision_output not in output_names:
            output_names.append(decision_output)
        if all(f.name != decision_output for f in fields):
            fields.append(FieldSpec(
                name=decision_output,
                label=decision_output,
                field_type=(catalog or {}).get(decision_output, {}).get("type", "String"),
                required=False,
                read_only=False,
                is_output=True,
                hidden=True,
            ))

    return HumanTaskSpec(
        name=node["name"],
        lane=node["lane"],
        fields=fields,
        submit_buttons=actions,
        decision_output=decision_output,
        action_values=dict(node.get("action_values") or {}),
        input_names=input_names,
        output_names=output_names,
        comment_history=history,
    )


def build_noop_system_service(proc_id: str, version_id: str) -> str:
    # Native General System Service containing one auto-completing script.
    script_item = f"2025.{u()}"
    end_item = f"2025.{u()}"
    script_component = f"3011.{u()}"
    exit_component = f"3008.{u()}"
    ts = _now_ms()
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
  <process id="{proc_id}" name="BAW Generic Auto Complete">
    <lastModified>{ts}</lastModified><lastModifiedBy>admin</lastModifiedBy><tenantId isNull="true" />
    <processId>{proc_id}</processId><image isNull="true" /><tabGroup isNull="true" />
    <startingProcessItemId>{script_item}</startingProcessItemId><isRootProcess>false</isRootProcess>
    <processType>4</processType><isErrorHandlerEnabled>false</isErrorHandlerEnabled><errorHandlerItemId isNull="true" />
    <isLoggingVariables>false</isLoggingVariables><isTransactional>false</isTransactional><processTimingLevel isNull="true" />
    <participantRef isNull="true" /><exposedType isNull="true" /><isTrackingEnabled>true</isTrackingEnabled><xmlData isNull="true" />
    <cachingType>false</cachingType><itemLabel isNull="true" /><cacheLength>43200</cacheLength><mobileReady>false</mobileReady>
    <sboSyncEnabled>true</sboSyncEnabled><externalId isNull="true" /><isSecured>false</isSecured><isAjaxExposed>false</isAjaxExposed>
    <isInvokedAsynchronously>false</isInvokedAsynchronously><isTransactionalFlow>false</isTransactionalFlow>
    <description>DEMO system-service placeholder. Auto-completes without calling an external system.</description>
    <guid>guid:{u()}</guid><versionId>{version_id}</versionId><dependencySummary isNull="true" /><jsonData isNull="true" />
    <businessDataAliases isNull="true" /><field1 isNull="true" /><field2 isNull="true" /><field3>0</field3>
    <field4 isNull="true" /><field5>false</field5><clobField1 isNull="true" /><blobField1 isNull="true" />
    <item><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processItemId>{end_item}</processItemId><processId>{proc_id}</processId><name>End</name>
      <tWComponentName>ExitPoint</tWComponentName><tWComponentId>{exit_component}</tWComponentId>
      <isLogEnabled>false</isLogEnabled><isTraceEnabled>false</isTraceEnabled><traceCategory isNull="true" /><traceLevel isNull="true" />
      <traceMessage isNull="true" /><traceSymbolTable isNull="true" /><isExecutionContextTraced>false</isExecutionContextTraced>
      <saveExecutionContext>true</saveExecutionContext><documentation isNull="true" /><isErrorHandlerEnabled>false</isErrorHandlerEnabled>
      <errorHandlerItemId isNull="true" /><guid>guid:{u()}</guid><versionId>{u()}</versionId><externalServiceRef isNull="true" />
      <externalServiceOp isNull="true" /><nodeColor isNull="true" />
      <layoutData x="388" y="102"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
      <TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <exitPointId>{exit_component}</exitPointId><haltProcess>false</haltProcess><guid>guid:{u()}</guid><versionId>{u()}</versionId></TWComponent>
    </item>
    <item><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processItemId>{script_item}</processItemId><processId>{proc_id}</processId><name>Auto Complete</name>
      <tWComponentName>Script</tWComponentName><tWComponentId>{script_component}</tWComponentId>
      <isLogEnabled>false</isLogEnabled><isTraceEnabled>false</isTraceEnabled><traceCategory isNull="true" /><traceLevel isNull="true" />
      <traceMessage isNull="true" /><traceSymbolTable isNull="true" /><isExecutionContextTraced>false</isExecutionContextTraced>
      <saveExecutionContext>false</saveExecutionContext><documentation>Generated demo no-op.</documentation><isErrorHandlerEnabled>false</isErrorHandlerEnabled>
      <errorHandlerItemId isNull="true" /><guid>guid:{u()}</guid><versionId>{u()}</versionId><externalServiceRef isNull="true" />
      <externalServiceOp isNull="true" /><nodeColor isNull="true" />
      <layoutData x="182" y="87"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
      <TWComponent><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <scriptId>{script_component}</scriptId><scriptTypeId>2</scriptTypeId><isActive>true</isActive>
      <script>// Generated demo system task: intentionally no external call.</script><isRule>false</isRule>
      <guid>guid:{u()}</guid><versionId>{u()}</versionId></TWComponent>
    </item>
    <startingProcessItemId>{script_item}</startingProcessItemId><errorHandlerItemId isNull="true" />
    <layoutData noConversion="true"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData>
    <startPoint><layoutData x="20" y="102"><errorLink><controlPoints /><showEndState>false</showEndState><showName>false</showName></errorLink></layoutData></startPoint>
    <startLink><fromPort locationId="rightCenter" portType="1" /><toPort locationId="leftCenter" portType="2" />
      <layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData></startLink>
    <link name="Untitled"><lastModified isNull="true" /><lastModifiedBy isNull="true" /><tenantId isNull="true" />
      <processLinkId>2027.{u()}</processLinkId><processId>{proc_id}</processId><description isNull="true" />
      <fromProcessItemId>{script_item}</fromProcessItemId><endStateId>Out</endStateId><toProcessItemId>{end_item}</toProcessItemId>
      <guid>guid:{u()}</guid><versionId>{u()}</versionId><layoutData><controlPoints /><showEndState>false</showEndState><showName>false</showName></layoutData>
      <fromItemPort locationId="rightCenter" portType="1" /><toItemPort locationId="leftCenter" portType="2" />
      <fromProcessItemId>{script_item}</fromProcessItemId><toProcessItemId>{end_item}</toProcessItemId>
    </link>
  </process>
</teamworks>'''


def _io_tags(incoming, outgoing, prefix="ns7"):
    return "".join(f"<{prefix}:incoming>{x}</{prefix}:incoming>" for x in incoming) + \
           "".join(f"<{prefix}:outgoing>{x}</{prefix}:outgoing>" for x in outgoing)



def _gateway_decision_variable(proc: dict, gateway: dict, process_vars: dict) -> Optional[str]:
    explicit = str(gateway.get("decision_variable") or "").strip()
    if explicit:
        if explicit not in process_vars:
            raise ValueError(f"{proc['name']}/{gateway['id']}: undeclared decision_variable {explicit!r}")
        return explicit

    flows = proc.get("flows") or []
    nodes = {n["id"]: n for n in proc.get("nodes") or []}
    incoming_sources = [f["from"] for f in flows if f.get("to") == gateway["id"]]
    tokens = ("decision","action","opinion","result","status","valid","approved","approval","choice","outcome")
    candidates = []
    for src in incoming_sources:
        node = nodes.get(src) or {}
        names = list(node.get("outputs") or [])
        names += [f.get("name") for f in node.get("fields") or [] if f.get("name")]
        for name in names:
            if name in process_vars and any(t in name.lower() for t in tokens):
                candidates.append(name)
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) == 1:
        return candidates[0]

    # Match gateway wording to a variable, e.g. "Data Valid?" -> dataValid
    g = re.sub(r"[^a-z0-9]", "", str(gateway.get("name") or "").lower())
    matches = [n for n in process_vars if re.sub(r"[^a-z0-9]", "", n.lower()) == g]
    return matches[0] if len(matches) == 1 else None

def _flow_expected_value(flow: dict, meta: dict):
    if "value" in flow:
        return flow["value"]
    label = str(flow.get("label") or "").strip()
    low = label.lower()
    typ = meta.get("type","String")
    if typ == "Boolean":
        if low in {"yes","true","valid","approved","approve","satisfactory","active","found","authorized","authorised"}:
            return True
        if low in {"no","false","invalid","reject","rejected","not satisfactory","inactive","not found","return"}:
            return False
        raise ValueError(f"Cannot infer Boolean branch value from {label!r}; add flow.value")
    if typ == "Integer":
        return int(label)
    if typ == "Decimal":
        return float(label)
    if not label:
        raise ValueError("String decision branch requires label or flow.value")
    return label

def _gateway_condition_expression(var_name: str, meta: dict, expected) -> str:
    ref = f"tw.local.{var_name}"
    typ = meta.get("type","String")
    if typ == "Boolean":
        return f"{ref} == {'true' if bool(expected) else 'false'}"
    if typ in {"Integer","Decimal"}:
        return f"{ref} == {expected}"
    val = str(expected).replace("\\\\","\\\\\\\\").replace('"','\\\\"')
    return f'{ref} == "{val}"'

def _prepare_gateway_routing(proc: dict) -> None:
    catalog = _process_variable_catalog(proc)
    nodes = {n["id"]: n for n in proc.get("nodes") or []}
    flows = proc.get("flows") or []

    # Recompute on each preflight so stale transient values cannot survive.
    proc["_demo_variable_defaults"] = {}

    for gw in [n for n in proc.get("nodes") or [] if n.get("type") == "gateway"]:
        outs = [f for f in flows if f.get("from") == gw["id"]]
        if len(outs) < 2:
            continue

        var = _gateway_decision_variable(proc, gw, catalog)
        if not var:
            gw["_routing_mode"] = "demo"
            continue

        gw["decision_variable"] = var
        gw["_routing_mode"] = "variable"
        meta = catalog[var]

        incoming_sources = [
            f.get("from") for f in flows if f.get("to") == gw["id"]
        ]
        service_driven = any(
            (nodes.get(src) or {}).get("type") in SERVICE_LIKE_NODE_TYPES
            for src in incoming_sources
        )

        defaults = [
            f for f in outs
            if f.get("demo_default") is True or f.get("default") is True
        ]
        # An unconditional/default path is safe only for a generated service
        # placeholder whose demo value is initialized below. Human decisions
        # (Approve/Return/Reject, etc.) must condition every branch explicitly;
        # otherwise BAW can take the unconditional path before Return/Reject.
        default_flow = defaults[0] if defaults and service_driven else None

        # Keep normal executable gateway conditions.
        for f in outs:
            if f is default_flow:
                f.pop("condition", None)
            else:
                f.pop("default", None)
                f.pop("demo_default", None)
                f["condition"] = _gateway_condition_expression(
                    var, meta, _flow_expected_value(f, meta)
                )

        # Demo placeholder behavior:
        # If the gateway is immediately fed by a generated service-like node,
        # that upstream activity is currently a no-op placeholder and cannot
        # populate its real result yet. Initialize the process variable to the
        # value represented by the reviewed demo_default branch.
        #
        # We intentionally do this only for service-driven gateways, not
        # human-decision gateways such as managerDecision/checkerDecision.
        if default_flow is not None:
            if service_driven:
                expected_default = _flow_expected_value(default_flow, meta)
                existing = proc["_demo_variable_defaults"].get(var, None)
                if var in proc["_demo_variable_defaults"] and existing != expected_default:
                    raise ValueError(
                        f"{proc['name']}/{gw['id']}: conflicting demo defaults for "
                        f"process variable {var!r}: {existing!r} vs {expected_default!r}"
                    )
                proc["_demo_variable_defaults"][var] = expected_default

    # Generic multi-action human-task routing.
    for human in [n for n in proc.get("nodes") or [] if n.get("type") == "human"]:
        actions = [str(x) for x in (human.get("actions") or [])]
        if len(actions) < 2:
            continue

        decision_var = _infer_human_decision_variable(human, catalog)
        if not decision_var or decision_var not in catalog:
            continue

        human["decision_output"] = decision_var
        outputs = list(human.get("outputs") or [])
        if decision_var not in outputs:
            outputs.append(decision_var)
        human["outputs"] = outputs

        meta = catalog[decision_var]
        action_values = dict(human.get("action_values") or {})
        outs = [f for f in flows if f.get("from") == human["id"]]

        if len(outs) >= 2:
            for idx, flow in enumerate(outs):
                label = str(flow.get("label") or "").strip()
                if "value" in flow:
                    expected = flow["value"]
                elif label in action_values:
                    expected = action_values[label]
                elif label:
                    expected = label
                elif idx < len(actions):
                    expected = action_values.get(actions[idx], actions[idx])
                else:
                    continue
                flow["condition"] = _gateway_condition_expression(decision_var, meta, expected)
                flow.pop("default", None)
                flow.pop("demo_default", None)

        # explicit gateway immediately after human task
        next_ids = [f.get("to") for f in flows if f.get("from") == human["id"]]
        for nid in next_ids:
            gw = nodes.get(nid)
            if gw and gw.get("type") == "gateway" and not gw.get("decision_variable"):
                gw["decision_variable"] = decision_var


def _demo_value_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _report_gateway_routing(spec: dict) -> None:
    real = demo = 0
    mock_values = []
    for proc in spec.get("processes") or []:
        _prepare_gateway_routing(proc)
        for gw in [n for n in proc.get("nodes") or [] if n.get("type") == "gateway"]:
            if gw.get("_routing_mode") == "variable":
                real += 1
            elif gw.get("_routing_mode") == "demo":
                demo += 1

        for name, value in (proc.get("_demo_variable_defaults") or {}).items():
            mock_values.append(
                f"{proc['name']}.{name}={_demo_value_text(value)}"
            )

    if real:
        print(f"✅ Variable-driven gateway routing prepared: {real} gateway(s)")
    if mock_values:
        print(
            "✅ Demo placeholder gateway values initialized: "
            + ", ".join(mock_values)
        )
    if demo:
        print(f"⚠️  Gateways still using demo-only routing: {demo}")

def _flow_expr(flow: dict, is_default: bool) -> Optional[str]:
    if is_default:
        return None
    value = flow.get("condition")
    if value is None or str(value).strip() == "":
        return "false"
    return str(value).strip()



def _compute_process_layout(proc: dict, lanes: List[dict]) -> dict:
    """
    V10-compatible layout semantics:
      - lane Y is absolute in the lane visual definition;
      - node Y is lane-local in all three BPD representations;
      - node X follows the end-to-end business sequence globally, not per lane.
    """
    nodes = proc["nodes"]
    flows = proc["flows"]
    coverage = proc.get("source_coverage") or []

    first_order = {}
    for item in coverage:
        if str(item.get("disposition") or "represented").lower() != "represented":
            continue
        order = item.get("order")
        for nid in item.get("node_ids") or []:
            if nid not in first_order or order < first_order[nid]:
                first_order[nid] = order

    # Stable global columns from source order. Start nodes first; uncovered end
    # events are placed one column after their furthest predecessor.
    ordered_business = sorted(
        [n for n in nodes if n["id"] in first_order],
        key=lambda n: (first_order[n["id"]], n["id"]),
    )
    column = {}
    next_col = 1
    for node in ordered_business:
        if node["id"] not in column:
            column[node["id"]] = next_col
            next_col += 1
    for node in nodes:
        if node["type"] == "start":
            column[node["id"]] = 0

    incoming = {n["id"]: [] for n in nodes}
    for flow in flows:
        incoming[flow["to"]].append(flow["from"])

    # Resolve end/uncovered helper positions iteratively.
    for _ in range(len(nodes) + 1):
        changed = False
        for node in nodes:
            nid = node["id"]
            if nid in column:
                continue
            pred_cols = [column[p] for p in incoming[nid] if p in column]
            if pred_cols:
                column[nid] = max(pred_cols) + 1
                changed = True
        if not changed:
            break
    for node in nodes:
        column.setdefault(node["id"], next_col)
        if column[node["id"]] == next_col:
            next_col += 1

    lane_height = {}
    lane_y = {}
    current_y = 0
    for lane in lanes:
        # Match the stable V10 idea of roomy lanes. Human lanes with alternate
        # rejection/end branches get extra height; system lanes are also roomy.
        lname = lane["name"]
        lane_nodes = [n for n in nodes if n["lane"] == lname]
        has_branch_end = any(
            n["type"] == "end" and any(k in n["name"].lower() for k in ("reject", "inactive", "blocked", "error", "cancel", "cannot"))
            for n in lane_nodes
        )
        height = 280 if lane["system"] or has_branch_end else 230
        lane_height[lname] = height
        lane_y[lname] = current_y
        current_y += height

    positions = {}
    for node in nodes:
        x = 70 + column[node["id"]] * 150
        height = lane_height[node["lane"]]
        if node["type"] == "end" and any(
            k in node["name"].lower() for k in ("reject", "inactive", "blocked", "error", "cancel", "cannot")
        ):
            y = max(30, height - 90)
        else:
            y = max(30, (height - (24 if node["type"] in {"start", "end"} else 32 if node["type"] == "gateway" else 70)) // 2)
        positions[node["id"]] = (x, y)

    max_x = max(x for x, _ in positions.values()) if positions else 1500
    pool_width = max(1800, max_x + 300)
    pool_height = sum(lane_height.values())
    return {
        "positions": positions,
        "lane_height": lane_height,
        "lane_y": lane_y,
        "pool_width": pool_width,
        "pool_height": pool_height,
    }



def _bpd_parameter_xml(proc: dict, bpd_id: str) -> str:
    parts = []
    seq = 0
    for v in proc.get("variables") or []:
        scope = str(v.get("scope") or "private").lower()
        if scope not in {"input", "output", "input_output"}:
            continue
        scopes = ["input", "output"] if scope == "input_output" else [scope]
        for one_scope in scopes:
            name = str(v["name"])
            typ = v.get("type", "String")
            cid = _meta_class_id(v)
            parts.append(
                f'<bpdParameter name="{_x(name)}">'
                f'<lastModified isNull="true" />'
                f'<lastModifiedBy isNull="true" />'
                f'<tenantId isNull="true" />'
                f'<bpdParameterId>2007.{u()}</bpdParameterId>'
                f'<bpdId>{_x(bpd_id)}</bpdId>'
                f'<parameterType>{1 if one_scope == "input" else 2}</parameterType>'
                f'<isArrayOf>{str(bool(v.get("type") == "CommentHistoryList")).lower()}</isArrayOf>'
                f'<classId>{_x(cid)}</classId>'
                f'<seq>{seq}</seq>'
                f'<documentation></documentation>'
                f'<hasDefault>false</hasDefault>'
                f'<defaultValue isNull="true" />'
                f'<isReadOnly>false</isReadOnly>'
                f'<guid>guid:{u()}</guid>'
                f'<versionId>{u()}</versionId>'
                f'</bpdParameter>'
            )
            seq += 1
    return "".join(parts)


def build_generic_bpd_xml(proc: dict, bpd_id: str, bpd_version: str,
                          human_proc_ids: dict[str, str], noop_service_id: str,
                          human_ios: Optional[dict] = None) -> str:
    lanes = _lane_specs(proc)
    nodes = proc["nodes"]
    flows = proc["flows"]
    node_by_key = {n["id"]: n for n in nodes}
    human_ios = human_ios or {}

    # Process-level variables. These are the shared data model visible on the
    # main process and are mapped to/from each generated human service.
    _prepare_gateway_routing(proc)
    process_io = _make_process_io(proc)

    node_ids = {n["id"]: _bid() for n in nodes}
    flow_ids = {i: _bid() for i in range(len(flows))}
    lane_ids = {l["name"]: _bid() for l in lanes}
    pool_id = _bid()

    incoming = {n["id"]: [] for n in nodes}
    outgoing = {n["id"]: [] for n in nodes}
    for i, f in enumerate(flows):
        incoming[f["to"]].append(flow_ids[i])
        outgoing[f["from"]].append(flow_ids[i])

    # Which flow is the deterministic default for a branching gateway.
    default_by_gateway = {}
    for n in nodes:
        if n["type"] != "gateway":
            continue
        candidates = [(i, f) for i, f in enumerate(flows) if f["from"] == n["id"]]
        if not candidates:
            continue
        chosen = next(
            (
                i for i, f in candidates
                if f.get("demo_default") is True or f.get("default") is True
            ),
            None,
        )
        if chosen is not None:
            default_by_gateway[n["id"]] = flow_ids[chosen]

    # V10-style lane-local Y coordinates and global business-sequence X columns.
    lane_index = {l["name"]: i for i, l in enumerate(lanes)}
    layout = _compute_process_layout(proc, lanes)
    positions = layout["positions"]
    lane_height = layout["lane_height"]
    lane_y = layout["lane_y"]
    pool_width = layout["pool_width"]
    pool_height = layout["pool_height"]

    # ---------------- bpmn2Data ----------------
    lane_xml = []
    for l in lanes:
        refs = "".join(f"<ns7:flowNodeRef>{node_ids[n['id']]}</ns7:flowNodeRef>" for n in nodes if n["lane"] == l["name"])
        team_id = SYSTEM_TEAM.split("/",1)[-1] if l["system"] else ALL_USERS_TEAM.split("/",1)[-1]
        li = lane_index[l["name"]]
        lane_xml.append(
            f'<ns7:lane name="{_x(l["name"])}" partitionElementRef="{team_id}" id="{lane_ids[l["name"]]}" ns3:isSystemLane="{str(l["system"]).lower()}">'
            f'<ns7:extensionElements><ns16:nodeVisualInfo x="0" y="{li*260}" width="3000" height="260" color="#F8F8F8" /></ns7:extensionElements>'
            f'{refs}</ns7:lane>'
        )

    node_xml = []
    for n in nodes:
        nid = node_ids[n["id"]]
        x, y = positions[n["id"]]
        incout = _io_tags(incoming[n["id"]], outgoing[n["id"]])
        default_attr = f' default="{default_by_gateway[n["id"]]}"' if n["type"] == "gateway" and n["id"] in default_by_gateway else ""
        if n["type"] == "start":
            node_xml.append(
                f'<ns7:startEvent name="{_x(n["name"])}" id="{nid}"><ns7:extensionElements>'
                f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="24" height="24" color="#A5B7CD" />'
                f'</ns7:extensionElements>{incout}</ns7:startEvent>'
            )
        elif n["type"] == "end":
            node_xml.append(
                f'<ns7:endEvent name="{_x(n["name"])}" id="{nid}"><ns7:extensionElements>'
                f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="24" height="24" color="#A5B7CD" />'
                f'</ns7:extensionElements>{incout}<ns7:terminateEventDefinition id="{_bid()}" eventImplId="{_bid()}">'
                f'<ns7:extensionElements><ns3:terminateEventSettings><ns3:terminateEntireProcess>false</ns3:terminateEntireProcess>'
                f'<ns3:deleteProcessInstance>false</ns3:deleteProcessInstance><ns3:deleteCaseFolder>false</ns3:deleteCaseFolder>'
                f'</ns3:terminateEventSettings></ns7:extensionElements></ns7:terminateEventDefinition></ns7:endEvent>'
            )
        elif n["type"] == "gateway":
            node_xml.append(
                f'<ns7:exclusiveGateway{default_attr} gatewayDirection="Unspecified" name="{_x(n["name"])}" id="{nid}">'
                f'<ns7:extensionElements><ns16:nodeVisualInfo x="{x}" y="{y}" width="32" height="32" color="#A5B7CD" /></ns7:extensionElements>'
                f'{incout}</ns7:exclusiveGateway>'
            )
        else:
            called = human_proc_ids[n["id"]] if n["type"] == "human" else noop_service_id
            act_type = "UserTask" if n["type"] == "human" else "ServiceTask"
            one_default = outgoing[n["id"]][0] if len(outgoing[n["id"]]) == 1 else None
            da = f' default="{one_default}"' if one_default else ''
            resource = ''
            activity_io_xml = f'<ns7:ioSpecification><ns7:inputSet id="_{u()}"/><ns7:outputSet id="_{u()}"/></ns7:ioSpecification>'
            mapping_xml = ''

            if n["type"] == "human":
                resource = ('<ns7:resourceRole xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns3:tActivityPerformer" distribution="None" name="Lane">'
                            '<ns3:teamFilterService /></ns7:resourceRole>'
                            '<ns7:resourceRole xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns3:tActivityPerformer" distribution="None" name="Team">'
                            '<ns3:teamFilterService /></ns7:resourceRole>')

                task_io = human_ios.get(n["id"]) or {}
                inputs, outputs = _human_mapping_names(n, process_io)
                activity_io_xml = ""
                mapping_xml = _bpmn_activity_assignment_mapping_xml(
                    task_io, inputs, outputs, "ns7"
                )

            node_xml.append(
                f'<ns7:callActivity calledElement="{called}"{da} name="{_x(n["name"])}" id="{nid}"><ns7:extensionElements>'
                f'<ns3:activityType>{act_type}</ns3:activityType>'
                + ('<ns3:deleteTaskOnCompletion>false</ns3:deleteTaskOnCompletion>' if n["type"] in SERVICE_LIKE_NODE_TYPES else '') +
                '<ns3:userTaskSettings><ns3:enableAutoFlow>false</ns3:enableAutoFlow><ns3:enableCleanState>false</ns3:enableCleanState>'
                '<ns3:activityPriority type="Priority"/><ns3:activityDueDate type="TimeCalculation"><ns3:dueDate unit="Hours" timeOfDay="00:00">1</ns3:dueDate></ns3:activityDueDate>'
                '<ns3:activityAssignmentType>Lane</ns3:activityAssignmentType></ns3:userTaskSettings>'
                '<ns3:activityExtension conditional="false"/>'
                f'<ns16:nodeVisualInfo x="{x}" y="{y}" width="95" height="70" color="#A5B7CD" /></ns7:extensionElements>'
                f'{incout}{activity_io_xml}{mapping_xml}{resource}</ns7:callActivity>'
            )

    sf_xml = []
    for i, f in enumerate(flows):
        fid = flow_ids[i]
        src = node_ids[f["from"]]
        tgt = node_ids[f["to"]]
        label = f.get("label", "")
        src_node = node_by_key[f["from"]]
        is_default = src_node["type"] == "gateway" and default_by_gateway.get(src_node["id"]) == fid
        expr = _flow_expr(f, is_default)
        cond = '' if expr is None else f'<ns7:conditionExpression xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="ns7:tFormalExpression">{_x(expr)}</ns7:conditionExpression>'
        sf_xml.append(
            f'<ns7:sequenceFlow sourceRef="{src}" targetRef="{tgt}" name="{_x(label)}" id="{fid}"><ns7:extensionElements>'
            '<ns4:happySequence>true</ns4:happySequence><ns16:linkVisualInfo><ns16:sourcePortLocation>rightCenter</ns16:sourcePortLocation>'
            '<ns16:targetPortLocation>leftCenter</ns16:targetPortLocation><ns16:showLabel>true</ns16:showLabel>'
            '<ns16:showCoachControlLabel>false</ns16:showCoachControlLabel><ns16:labelPosition>0.0</ns16:labelPosition>'
            '<ns16:saveExecutionContext>false</ns16:saveExecutionContext></ns16:linkVisualInfo></ns7:extensionElements>'
            f'{cond}</ns7:sequenceFlow>'
        )

    # Standalone CSHSs are separately packaged artifacts referenced by
    # callActivity.calledElement. IBM-exported standalone UserTask BPDs do not
    # inject globalUserTask roots into the BPD itself.
    global_user_tasks = ""
    defs_id = u()
    bpmn_inner = (
        f'<ns7:definitions xmlns:ns7="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:ns2="http://www.ibm.com/bpm/Extensions" '
        'xmlns:ns3="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/wle" xmlns:ns4="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process" '
        'xmlns:ns5="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/case" xmlns:ns6="http://www.ibm.com/xmlns/prod/bpm/uca" '
        'xmlns:ns8="http://www.ibm.com/bpm/processappsettings" xmlns:ns9="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/extservice" '
        'xmlns:ns10="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/trackinggroup" xmlns:ns11="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/team" '
        'xmlns:ns12="http://www.ibm.com/xmlns/bpmnx/20100524/v1/BusinessVocabulary" xmlns:ns13="http://www.omg.org/spec/DD/20100524/DI" '
        'xmlns:ns14="http://www.omg.org/spec/DD/20100524/DC" xmlns:ns15="http://www.omg.org/spec/BPMN/20100524/BPMNDI" '
        'xmlns:ns16="http://www.ibm.com/xmlns/prod/bpm/graph" xmlns:ns17="http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/auth" '
        'xmlns:ns18="http://www.ibm.com/bpm/CoachDesignerNG" xmlns:ns19="http://www.ibm.com/xmlns/links" xmlns:ns20="http://www.ibm.com/bpm/uitheme" '
        'xmlns:ns21="http://www.ibm.com/bpm/coachview" xmlns:ns22="http://www.ibm.com/xmlns/tagging" '
        f'id="{defs_id}" targetNamespace="" exporter="http://www.ibm.com/BPM" exporterVersion="8.6.11">'
        f'<ns7:process processType="None" isClosed="false" name="{_x(proc["name"])}" id="{bpd_id}"><ns7:extensionElements>'
        '<ns5:isConvergedProcess>true</ns5:isConvergedProcess>'
        f'<ns3:bpdExtension instanceName="&quot;{_x(proc["name"])}:&quot; + tw.system.process.instanceId" dueDateEnabled="true" atRiskCalcEnabled="true" enableTracking="true" '
        'allowProjectedPathManagement="false" optimizeExecForLatency="false" sBOSyncEnabled="false" allowContentOperations="false" autoTrackingEnabled="false">'
        '<ns3:defaultInstanceUI/><ns3:bpdOwnerInstanceUI/><ns3:dueDateSettings type="TimeCalculation"><ns3:dueDate unit="Days" timeOfDay="00:00">1</ns3:dueDate></ns3:dueDateSettings>'
        '<ns3:workSchedule><ns3:timeScheduleType>0</ns3:timeScheduleType><ns3:timezoneType>0</ns3:timezoneType><ns3:holidayScheduleType>0</ns3:holidayScheduleType></ns3:workSchedule>'
        '</ns3:bpdExtension><ns5:caseExtension><ns5:caseFolder id="'+u()+'"/></ns5:caseExtension></ns7:extensionElements>'
        f'<ns7:laneSet id="{pool_id}">{"".join(lane_xml)}</ns7:laneSet>'
        + _bpmn_process_data_objects(process_io, "ns7") +
        f'{"".join(node_xml)}{"".join(sf_xml)}'
        '<ns7:resourceRole name="participantRef"/><ns7:resourceRole name="businessDataParticipantRef"/><ns7:resourceRole name="perfMetricParticipantRef"/><ns7:resourceRole name="ownerTeamParticipantRef"/>'
        f'</ns7:process><ns7:interface name="{_x(proc["name"])}Interface" id="_{u()}"/>{global_user_tasks}</ns7:definitions>'
    )

    # ---------------- jsonData ----------------
    flow_elements = []
    for n in nodes:
        nid = node_ids[n["id"]]
        x, y = positions[n["id"]]
        base_ext = {"nodeVisualInfo": [{"color":"#A5B7CD","width":24 if n["type"] in {"start","end"} else 32 if n["type"]=="gateway" else 95,
                                         "x":x,"y":y,"declaredType":"TNodeVisualInfo","height":24 if n["type"] in {"start","end"} else 32 if n["type"]=="gateway" else 70}]}
        obj = {"name": n["name"], "id": nid}
        if incoming[n["id"]]: obj["incoming"] = incoming[n["id"]]
        if outgoing[n["id"]]: obj["outgoing"] = outgoing[n["id"]]
        if n["type"] == "start":
            obj.update({"parallelMultiple":False,"isInterrupting":True,"declaredType":"startEvent","extensionElements":base_ext})
            if outgoing[n["id"]]: obj["extensionElements"]["default"] = [outgoing[n["id"]][0]]
        elif n["type"] == "end":
            obj.update({"declaredType":"endEvent","extensionElements":base_ext})
        elif n["type"] == "gateway":
            obj.update({"declaredType":"exclusiveGateway","gatewayDirection":"Unspecified","extensionElements":base_ext})
            if n["id"] in default_by_gateway: obj["default"] = default_by_gateway[n["id"]]
        else:
            called = human_proc_ids[n["id"]] if n["type"] == "human" else noop_service_id
            ext = deepcopy(base_ext)
            ext["activityType"] = ["UserTask" if n["type"]=="human" else "ServiceTask"]
            ext["activityExtension"] = [{"conditional":False,"transactionalBehavior":"NotSet","declaredType":"com.ibm.bpmsdk.model.bpmn20.ibmwleext.TActivityExtension"}]
            if n["type"] in SERVICE_LIKE_NODE_TYPES: ext["deleteTaskOnCompletion"] = [False]
            if n["type"] == "human":
                task_io = human_ios.get(n["id"]) or {}
                inputs, outputs = _human_mapping_names(n, process_io)
                associations = _json_activity_assignment_associations(
                    task_io, inputs, outputs
                )
                obj.update({
                    "declaredType":"callActivity",
                    "calledElement":called,
                    "startQuantity":1,
                    "completionQuantity":1,
                    "isForCompensation":False,
                    "extensionElements":ext,
                    "dataInputAssociation":associations["dataInputAssociation"],
                    "dataOutputAssociation":associations["dataOutputAssociation"],
                })
            else:
                obj.update({"declaredType":"callActivity","calledElement":called,"startQuantity":1,"completionQuantity":1,"isForCompensation":False,"extensionElements":ext,
                            "ioSpecification":{"inputSet":[{"id":u()}],"outputSet":[{"id":u()}]}})
            if len(outgoing[n["id"]]) == 1: obj["default"] = outgoing[n["id"]][0]
        flow_elements.append(obj)

    for i, f in enumerate(flows):
        srcn = node_by_key[f["from"]]
        fid = flow_ids[i]
        is_default = srcn["type"] == "gateway" and default_by_gateway.get(srcn["id"]) == fid
        expr = _flow_expr(f, is_default)
        sf = {"targetRef":node_ids[f["to"]],"sourceRef":node_ids[f["from"]],"name":f.get("label", ""),"declaredType":"sequenceFlow","id":fid,
              "extensionElements":{"happySequence":[True],"linkVisualInfo":[{"sourcePortLocation":"rightCenter","showCoachControlLabel":False,"labelPosition":0.0,"targetPortLocation":"leftCenter","declaredType":"TLinkVisualInfo","saveExecutionContext":False,"showLabel":True}]}}
        sf["conditionExpression"] = {} if expr is None else {"declaredType":"TFormalExpression","content":[expr]}
        flow_elements.append(sf)

    lane_json = []
    for l in lanes:
        li=lane_index[l["name"]]
        team_id = SYSTEM_TEAM.split("/",1)[-1] if l["system"] else ALL_USERS_TEAM.split("/",1)[-1]
        lane_json.append({"flowNodeRef":[node_ids[n["id"]] for n in nodes if n["lane"]==l["name"]],
                          "extensionElements":{"nodeVisualInfo":[{"color":"#F8F8F8","width":pool_width,"x":0,"y":lane_y[l["name"]],"declaredType":"TNodeVisualInfo","height":lane_height[l["name"]]}]},
                          "name":l["name"],"partitionElementRef":team_id,"declaredType":"lane","id":lane_ids[l["name"]],
                          "otherAttributes":{"{http://www.ibm.com/xmlns/prod/bpm/bpmn/ext/process/wle}isSystemLane":str(l["system"]).lower()}})
    flow_elements.extend(_json_process_data_objects(process_io))
    process_json = {
        "declaredType":"process",
        "id":bpd_id,
        "name":proc["name"],
        "processType":"None",
        "isClosed":False,
        "ioSpecification":{},
        "flowElement":flow_elements,
        "laneSet":[{"id":pool_id,"lane":lane_json}],
        "extensionElements":{"isConvergedProcess":[True]},
    }
    # Match IBM-exported standalone-UserTask BPD JSON: process + interface only.
    root_elements = [
        process_json,
        {"declaredType":"interface","id":"_"+u(),"name":proc["name"]+"Interface"},
    ]
    jdata = {"exporter":"http://www.ibm.com/BPM","exporterVersion":"8.6.11","rootElement":root_elements,"targetNamespace":"","typeLanguage":"http://www.w3.org/2001/XMLSchema","expressionLanguage":"http://www.w3.org/1999/XPath","id":u()}
    json_text = json.dumps(jdata, separators=(",",":"), ensure_ascii=False)

    # ---------------- native BusinessProcessDiagram ----------------
    # Traditional BAW runtime locals are native <privateVariable> elements
    # inside the BPD <pool>. These populate the tw.local symbol table.
    def _native_default_value(meta: dict):
        typ = meta.get("type", "String")
        if "default" in meta:
            val = meta["default"]
        elif typ == "Boolean":
            val = False
        elif typ in {"Integer", "Decimal"}:
            val = 0
        elif typ == "String":
            val = ""
        else:
            return None

        if typ == "Boolean":
            return "true" if bool(val) else "false"
        if typ in {"Integer", "Decimal"}:
            return str(val)
        if typ == "String":
            escaped = str(val).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return None

    native_private_variables = []
    for name, meta in process_io.items():
        if _is_collection_meta(meta):
            class_id = str(meta.get("class_id") or "")
            if not class_id:
                raise ValueError(f"{proc['name']}: history variable {name!r} has no Business Object class id")
            default_expr = None
            array_of = "true"
        else:
            primitive_uuid = _native_variable_class_uuid(meta["type"])
            class_id = f"{_x(SYSDATA_DEP_UUID)}/12.{_x(primitive_uuid)}"
            default_expr = _native_default_value(meta)
            array_of = "false"
        has_default = default_expr is not None
        native_private_variables.append(
            f'<privateVariable id="{_bid()}">'
            f'<name>{_x(name)}</name>'
            f'<description></description>'
            f'<classId>{_x(class_id)}</classId>'
            f'<arrayOf>{array_of}</arrayOf>'
            f'<hasDefault>{str(has_default).lower()}</hasDefault>'
            + (f'<defaultValue>{_x(default_expr)}</defaultValue>' if has_default else '') +
            f'<visibleInSearch>false</visibleInSearch>'
            f'<isProcessInstanceCorrelator>false</isProcessInstanceCorrelator>'
            f'<isSharedContext>false</isSharedContext>'
            f'</privateVariable>'
        )

    native_flows = []
    for i, f in enumerate(flows):
        fid=flow_ids[i]; srcn=node_by_key[f["from"]]
        is_default=srcn["type"]=="gateway" and default_by_gateway.get(srcn["id"])==fid
        expr=_flow_expr(f,is_default)
        cond_id=_bid()
        cond_xml=f'<condition id="{cond_id}" />' if expr is None else f'<condition id="{cond_id}"><expression>{_x(expr)}</expression></condition>'
        native_flows.append(f'<flow id="{fid}" connectionType="SequenceFlow"><name>{_x(f.get("label",""))}</name><documentation></documentation><nameVisible>{str(bool(f.get("label"))).lower()}</nameVisible><metricSettings itemType="32"/><connection><lineType>0</lineType>{cond_xml}</connection></flow>')

    def ports(nkey):
        ins=''; outs=''
        for fid in incoming[nkey]:
            ins += f'<inputPort id="{_bid()}"><positionId>leftCenter</positionId><input>true</input><flow ref="{fid}"/></inputPort>'
        for fid in outgoing[nkey]:
            outs += f'<outputPort id="{_bid()}"><positionId>rightCenter</positionId><flow ref="{fid}"/></outputPort>'
        return ins+outs

    lane_native=[]
    for l in lanes:
        li=lane_index[l["name"]]
        team = SYSTEM_TEAM if l["system"] else ALL_USERS_TEAM
        fos=[]
        for n in [x for x in nodes if x["lane"]==l["name"]]:
            nid=node_ids[n["id"]]; x,y=positions[n["id"]]; pp=ports(n["id"])
            common=f'<name>{_x(n["name"])}</name><documentation></documentation><position><location x="{x}" y="{y}"/></position><dropIconUrl>0</dropIconUrl><colorInput>#A5B7CD</colorInput>'
            if n["type"] in {"start","end"}:
                et=1 if n["type"]=="start" else 2
                comp=f'<component><nameVisible>true</nameVisible><eventType>{et}</eventType><cancelActivity>true</cancelActivity><repeatable>false</repeatable><doCloseTask>true</doCloseTask></component>'
                fos.append(f'<flowObject id="{nid}" componentType="Event">{common}{comp}{pp}</flowObject>')
            elif n["type"]=="gateway":
                comp='<component><nameVisible>true</nameVisible><gatewayType>1</gatewayType><splitJoinType>0</splitJoinType></component>'
                fos.append(f'<flowObject id="{nid}" componentType="Gateway">{common}{comp}{pp}</flowObject>')
            else:
                called=human_proc_ids[n["id"]] if n["type"]=="human" else noop_service_id
                btask=1 if n["type"]=="human" else 3
                lane_filter=''
                if n["type"]=="human":
                    lane_filter=f'<laneFilter id="{_bid()}"><serviceType>1</serviceType><teamRef>{ALL_USERS_TEAM}</teamRef></laneFilter><teamFilter id="{_bid()}"><serviceType>1</serviceType></teamFilter>'
                native_mapping = ''
                if n["type"] == "human":
                    task_io = human_ios.get(n["id"]) or {}
                    map_inputs, map_outputs = _human_mapping_names(n, process_io)
                    for vname in map_inputs:
                        native_mapping += (
                            f'<inputActivityParameterMapping id="{_bid()}">'
                            f'<name>{_x(vname)}</name>'
                            f'<classId>{_x(task_io[vname]["class_id"])}</classId>'
                            f'<input>true</input>'
                            f'<value>tw.local.{_x(vname)}</value>'
                            f'<parameterId>{_x(task_io[vname]["input_id"])}</parameterId>'
                            f'</inputActivityParameterMapping>'
                        )
                    for vname in map_outputs:
                        native_mapping += (
                            f'<outputActivityParameterMapping id="{_bid()}">'
                            f'<mappingMode>basic</mappingMode>'
                            f'<name>{_x(vname)}</name>'
                            f'<classId>{_x(task_io[vname]["class_id"])}</classId>'
                            f'<value>tw.local.{_x(vname)}</value>'
                            f'<sourcePath>tw.outputs.{_x(vname)}</sourcePath>'
                            f'<targetPath>tw.local.{_x(vname)}</targetPath>'
                            f'<parameterId>{_x(task_io[vname]["output_id"])}</parameterId>'
                            f'</outputActivityParameterMapping>'
                        )

                impl=(f'<implementation><attachedActivityId>/{called}</attachedActivityId><sendToType>1</sendToType><taskRouting>0</taskRouting>'
                      '<dueDateType>1</dueDateType><dueDateTime>1</dueDateTime><dueDateTimeResolution>1</dueDateTimeResolution><dueDateTimeTOD>00:00</dueDateTimeTOD>'
                      '<priorityType>0</priorityType><forceSend>true</forceSend><timeSchedule>(use default)</timeSchedule><timeScheduleType>0</timeScheduleType>'
                      '<timeZone>(use default)</timeZone><timeZoneType>0</timeZoneType><holidaySchedule>(use default)</holidaySchedule><holidayScheduleType>0</holidayScheduleType>'
                      f'<isDueDateEnabled>true</isDueDateEnabled>{lane_filter}{native_mapping}</implementation>')
                comp=(f'<component><loopType>0</loopType><loopMaximum>1</loopMaximum><startQuantity>1</startQuantity><isAutoflowable>false</isAutoflowable>'
                      f'<MIOrdering>1</MIOrdering><MIFlowCondition>0</MIFlowCondition><cancelRemainingInstances>false</cancelRemainingInstances><metricSettings itemType="4"/>'
                      f'<implementationType>1</implementationType><isConditional>false</isConditional><bpmnTaskType>{btask}</bpmnTaskType><activityOptionType>REQUIRED</activityOptionType>'
                      '<activityExecutionType>NONE</activityExecutionType><activityExecutionTypePreviousValue>AUTOMATIC</activityExecutionTypePreviousValue><isHidden>false</isHidden>'
                      f'<isRepeatable>false</isRepeatable><transactionalBehavior>0</transactionalBehavior><isRobotTask>false</isRobotTask>{impl}</component>')
                fos.append(f'<flowObject id="{nid}" componentType="Activity">{common}{comp}{pp}</flowObject>')
        lane_native.append(f'<lane id="{lane_ids[l["name"]]}"><name>{_x(l["name"])}</name><height>{lane_height[l["name"]]}</height><laneColor>0</laneColor><systemLane>{str(l["system"]).lower()}</systemLane><attachedParticipant>{team}</attachedParticipant>{"".join(fos)}</lane>')

    native = (
        f'<BusinessProcessDiagram id="{_bid()}"><metadata><entry><key>SAP_META.SHOULDRECOVER</key><value>no</value></entry></metadata>'
        f'<name>{_x(proc["name"])}</name><documentation></documentation><name>{_x(proc["name"])}</name><dimension><size w="0" h="0"/></dimension>'
        f'<author>admin</author><isTrackingEnabled>true</isTrackingEnabled><isCriticalPathEnabled>false</isCriticalPathEnabled><isSpcEnabled>false</isSpcEnabled>'
        f'<isDueDateEnabled>true</isDueDateEnabled><isAtRiskCalcEnabled>true</isAtRiskCalcEnabled><creationDate>{_now_ms()}</creationDate><modificationDate>{_now_ms()}</modificationDate>'
        '<metricSettings itemType="2"/><instanceNameExpression>"'+_x(proc["name"])+':" + tw.system.process.instanceId</instanceNameExpression>'
        '<dueDateType>1</dueDateType><dueDateTime>1</dueDateTime><dueDateTimeResolution>2</dueDateTimeResolution><dueDateTimeTOD>00:00</dueDateTimeTOD>'
        '<timeScheduleType>0</timeScheduleType><holidayScheduleType>0</holidayScheduleType><timezoneType>0</timezoneType><executionProfile>default</executionProfile>'
        '<isSBOSyncEnabled>false</isSBOSyncEnabled><allowContentOperations>false</allowContentOperations><isLegacyCaseMigrated>false</isLegacyCaseMigrated><hasCaseObjectParams>false</hasCaseObjectParams>'
        f'<defaultPool><BpmnObjectId id="{pool_id}"/></defaultPool><defaultInstanceUI id="{_bid()}"/><ownerTeamInstanceUI id="{_bid()}"/>'
        f'<simulationScenario id="{_bid()}"><name>Default</name><simNumInstances>100</simNumInstances><simMinutesBetween>30</simMinutesBetween><maxInstances>100</maxInstances>'
        '<useMaxInstances>true</useMaxInstances><continueFromReal>false</continueFromReal><useParticipantCalendars>false</useParticipantCalendars><useDuration>false</useDuration>'
        f'<duration>86400</duration><startTime>{_now_ms()}</startTime></simulationScenario>'
        f'{"".join(native_flows)}<pool id="{pool_id}"><name>Pool</name><documentation></documentation><dimension><size w="{pool_width}" h="{pool_height}"/></dimension>'
        f'<autoTrackingEnabled>false</autoTrackingEnabled>{"".join(lane_native)}{"".join(native_private_variables)}</pool>'
        f'<extension id="{_bid()}" type="CASE"><caseFolder id="{u()}"><allowLocalDoc>false</allowLocalDoc><allowExternalDoc>false</allowExternalDoc>'
        '<allowSubfoldersCreation>false</allowSubfoldersCreation><allowExternalFolder>false</allowExternalFolder></caseFolder></extension></BusinessProcessDiagram>'
    )

    # Match IBM-exported BPDs with standalone User Tasks. The calledElement
    # refs are sufficient; dependencySummary stays null.
    dep_summary = None

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
  <bpd id="{bpd_id}" name="{_x(proc["name"])}">
    {_bpd_parameter_xml(proc, bpd_id)}
    <lastModified>{_now_ms()}</lastModified><lastModifiedBy>admin</lastModifiedBy><tenantId isNull="true"/><bpdId>{bpd_id}</bpdId>
    <isTrackingEnabled>true</isTrackingEnabled><isSpcEnabled>false</isSpcEnabled><restrictedName isNull="true"/><isCriticalPathEnabled>false</isCriticalPathEnabled>
    <participantRef isNull="true"/><businessDataParticipantRef isNull="true"/><perfMetricParticipantRef isNull="true"/><ownerTeamParticipantRef isNull="true"/>
    <timeScheduleType isNull="true"/><timeScheduleName isNull="true"/><timeScheduleExpression isNull="true"/><holidayScheduleType isNull="true"/>
    <holidayScheduleName isNull="true"/><holidayScheduleExpression isNull="true"/><timezoneType isNull="true"/><timezone isNull="true"/><timezoneExpression isNull="true"/>
    <internalName isNull="true"/><description>{_x(proc.get("description", ""))}</description><type>1</type><rootBpdId isNull="true"/><parentBpdId isNull="true"/><parentFlowObjectId isNull="true"/>
    <xmlData isNull="true"/><bpmn2Data>{escape(bpmn_inner)}</bpmn2Data><dependencySummary isNull="true"/><jsonData>{escape(json_text)}</jsonData>
    <migrationData isNull="true"/><rwfData isNull="true"/><rwfStatus isNull="true"/><templateId isNull="true"/><externalId isNull="true"/>
    <guid>guid:{u()}</guid><versionId>{bpd_version}</versionId><field1 isNull="true"/><field2 isNull="true"/><field3>0</field3><field4 isNull="true"/><field5>false</field5>
    <clobField1 isNull="true"/><blobField1 isNull="true"/>{native}
  </bpd>
</teamworks>'''


def _theme_profile_from_application(app: dict) -> dict:
    """Return the portable theme profile embedded in the application contract.

    The profile is deliberately data-only.  It is used to generate a fresh
    BAW uiTheme toolkit; no source repository UUIDs are copied into generated
    artifacts.
    """
    theme = app.get("theme") or {}
    profile = theme.get("profile") if isinstance(theme, dict) else None
    if isinstance(profile, dict):
        return profile
    profile_path = theme.get("profile_path") if isinstance(theme, dict) else None
    candidates = []
    if profile_path:
        candidates.append(Path(str(profile_path)))
    candidates.append(Path(__file__).resolve().parents[1] / "assets" / "enterprise-burgundy-theme.json")
    for candidate in candidates:
        try:
            if candidate.exists():
                return json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return {
        "name": "Generated BAW Theme",
        "tokens": {"primary": "#870052", "primaryHover": "#3b0024", "text": "#000203", "surface": "#ffffff", "pageBackground": "#F7F1F4", "neutralLightest": "#dfe9e9", "success": "#c8f08f", "warning": "#fde876", "danger": "#ad1625"},
        "themeVariables": {"bodyBackground": "#F7F1F4", "fontFamilySansSerif": "Helvetica Neue, Helvetica, Arial, sans-serif", "fontSizeBase": "14px", "lineHeightBase": "1", "paddingBaseVertical": "6px", "paddingBaseHorizontal": "12px", "borderRadiusBase": "0px"},
    }


def _theme_less(profile: dict) -> str:
    """Build a complete Traditional BAW theme, then apply profile overrides.

    A native ``uiTheme`` is not a small list of brand tokens.  Workflow Center
    appends and compiles IBM's Coach theme implementation against this source,
    so the source must define the complete BAW variable contract (including
    values such as ``@bpm-border-normal`` and the variables consumed by
    ``.patch-spark-vars()``).  Emitting only the visible base palette imports
    successfully but fails at runtime with a misleading "no theme set" Coach
    banner.

    The bundled LESS template was exported from the inspected, compiling BAW
    8.6.11 theme.  It contains no customer repository object IDs.  Generated
    TWXs still allocate fresh object/version IDs and only reuse the complete
    variable structure and approved visual design.
    """
    tokens = dict(profile.get("tokens") or {})
    vars_ = dict(profile.get("themeVariables") or {})

    def v(name: str, fallback: str) -> str:
        return str(tokens.get(name) or vars_.get(name) or fallback)

    template_path = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "enterprise-burgundy-baw-8.6.11-theme.less"
    )
    if not template_path.exists():
        raise ValueError(
            "Complete BAW theme template is missing: " + str(template_path)
        )
    template = template_path.read_text(encoding="utf-8")

    # LESS resolves variables lazily, so these final assignments safely
    # customize the complete template without deleting any IBM-required
    # derived variables, editor metadata, or compatibility mappings.
    overrides = [
        "",
        "/* Generated portable profile overrides; repository IDs stay fresh. */",
        f"@bpm-neutral-darkest: {v('neutralDarkest', '#0d1111')};",
        f"@bpm-neutral-darker: {v('neutralDarker', '#2d3737')};",
        f"@bpm-neutral-dark: {v('surfaceMuted', '#c8d2d2')};",
        f"@bpm-neutral: {v('neutral', '#586464')};",
        f"@bpm-neutral-light: {v('neutralLight', '#6d7777')};",
        f"@bpm-neutral-lighter: {v('neutralLighter', '#c8d2d2')};",
        f"@bpm-neutral-lightest: {v('neutralLightest', '#dfe9e9')};",
        f"@bpm-color-primary: {v('primary', '#870052')};",
        f"@bpm-color-info: {v('info', '#989898')};",
        f"@bpm-color-success: {v('success', '#c8f08f')};",
        f"@bpm-color-warning: {v('warning', '#fde876')};",
        f"@bpm-color-alert: {v('danger', '#ad1625')};",
        f"@bpm-body-bg: {v('bodyBackground', '#F7F1F4')};",
        f"@bpm-fill-darker: {v('fillDarker', '#586464')};",
        f"@bpm-fill-normal: {v('fillNormal', '#ffffff')};",
        f"@bpm-text-color: {v('text', '#000203')};",
        f"@bpm-font-family-sans-serif: {v('fontFamilySansSerif', '\"Helvetica Neue\", Helvetica, Arial, sans-serif')};",
        f"@bpm-font-size-base: {v('fontSizeBase', '14px')};",
        f"@bpm-line-height-base: {v('lineHeightBase', '1')};",
        f"@bpm-padding-base-vertical: {v('paddingBaseVertical', '6px')};",
        f"@bpm-padding-base-horizontal: {v('paddingBaseHorizontal', '12px')};",
        f"@bpm-padding-small-vertical: {v('paddingSmallVertical', '5px')};",
        f"@bpm-padding-small-horizontal: {v('paddingSmallHorizontal', '10px')};",
        f"@bpm-border-radius-base: {v('borderRadiusBase', '0px')};",
        f"@bpm-border-radius-large: {v('borderRadiusLarge', '0px')};",
        f"@bpm-border-radius-small: {v('borderRadiusSmall', '0px')};",
        f"@bpm-active-color: {v('activeColor', '#ffffff')};",
        f"@bpm-active-bg: {v('activeBackground', '@bpm-color-primary')};",
        f"@bpm-link-color: {v('linkColor', '@bpm-color-primary')};",
        f"@bpm-list-group-bg: {v('listGroupBackground', '@bpm-body-bg')};",
        f"@bpm-list-group-border: {v('listGroupBorder', '@bpm-neutral-lightest')};",
        "@theme-identity: ENTERPRISE_BURGUNDY_COMPLETE;",
    ]
    return template.rstrip() + "\n" + "\n".join(overrides) + "\n"


def build_ui_theme_xml(theme_id: str, version_id: str, name: str, profile: dict) -> str:
    content = _theme_less(profile)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <uiTheme id="{escape(theme_id)}" name="{escape(name)}">
        <lastModified>{_now_ms()}</lastModified>
        <lastModifiedBy>admin</lastModifiedBy>
        <tenantId isNull="true" />
        <uithemeId>{escape(theme_id)}</uithemeId>
        <themeContent>{escape(content)}</themeContent>
        <description>Generated enterprise Coach theme. Fresh IDs are used for portability.</description>
        <guid>guid:{escape(theme_id.split('.', 1)[-1])}</guid>
        <versionId>{escape(version_id)}</versionId>
    </uiTheme>
</teamworks>
'''


def _theme_css(profile: dict) -> str:
    t = dict(profile.get("tokens") or {})
    theme_vars = dict(profile.get("themeVariables") or {})
    def c(name: str, fallback: str) -> str:
        return str(t.get(name) or fallback)
    def tv(name: str, fallback: str) -> str:
        return str(theme_vars.get(name) or t.get(name) or fallback)
    return f''':root {{
  --baw-primary: {c("primary", "#870052")};
  --baw-primary-hover: {c("primaryHover", "#3b0024")};
  --baw-page-background: {tv("bodyBackground", "#F7F1F4")};
  --baw-surface: {c("surface", "#ffffff")};
  --baw-text: {c("text", "#000203")};
  --baw-border: {c("border", "#a9b9b9")};
  --baw-neutral-lightest: {c("neutralLightest", "#dfe9e9")};
  --baw-success: {c("success", "#c8f08f")};
  --baw-warning: {c("warning", "#fde876")};
  --baw-danger: {c("danger", "#ad1625")};
}}
body {{ background: var(--baw-page-background); color: var(--baw-text); }}
a, .bpm-link {{ color: var(--baw-primary); }}
.btn-primary, button.bpm-primary {{ background: var(--baw-primary); border-color: var(--baw-primary); color: #fff; }}
.btn-primary:hover, button.bpm-primary:hover {{ background: var(--baw-primary-hover); border-color: var(--baw-primary-hover); }}
input, textarea, select {{ border-color: var(--baw-border); color: var(--baw-text); }}
.bpm-section-header, .section-header {{ border-color: var(--baw-primary); }}
.bpm-alert-success {{ background: var(--baw-success); }}
.bpm-alert-warning {{ background: var(--baw-warning); }}
.bpm-alert-danger {{ background: var(--baw-danger); color: #fff; }}
'''


def build_theme_asset_zip(profile: dict) -> bytes:
    css = _theme_css(profile).encode("utf-8")
    files = {
        "bpmCoachFmk/less/coach_ng_theme.css": css,
        "bpmUI.css": css,
        "content.css": css,
        "scripts/controls.css": css,
        "workplace.css": css,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, data in files.items():
            z.writestr(path, data)
    return buf.getvalue()


def build_managed_asset_xml(asset_id: str, version_id: str, asset_uuid: str, name: str, length: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
    <managedAsset id="{escape(asset_id)}" name="{escape(name)}">
        <lastModified>{_now_ms()}</lastModified><lastModifiedBy>admin</lastModifiedBy>
        <managedAssetId>{escape(asset_id)}</managedAssetId><assetUuid>{escape(asset_uuid)}</assetUuid>
        <mimeType>application/zip</mimeType><charEncoding isNull="true" /><assetTypeCode>T</assetTypeCode>
        <length>{int(length)}</length><localLastModification>0</localLastModification>
        <description>Generated local theme CSS asset.</description><isDocumentationFile>false</isDocumentationFile>
        <guid>guid:{escape(asset_uuid)}</guid><versionId>{escape(version_id)}</versionId>
    </managedAsset>
</teamworks>
'''


def build_package_xml_generic(
    proj_id, branch_id, snap_id, app, objects, files=None,
    theme_toolkit=None,
):
    obj_entries=''.join(f'<object id="{oid}" versionId="{ver}" name="{_x(name)}" type="{typ}"/>' for oid,ver,name,typ in objects)
    file_entries = ''.join(f'<file path="{_x(item["path"])}" id="{_x(item["id"])}"/>' for item in (files or []))
    snapshot_name = app.get("snapshot_name") or "Generated Initial"
    snapshot_acronym = _normalize_acronym(app.get("snapshot_acronym") or "GEN")[:8]
    theme_dependency = ""
    if theme_toolkit:
        theme_dependency = f'''
  <dependency rank="2" isManaged="false" id="{_x(theme_toolkit["dependency_id"])}"><project id="{_x(theme_toolkit["project_id"])}" name="{_x(theme_toolkit["name"])}" shortName="{_x(theme_toolkit["acronym"])}" isToolkit="true" isHidden="false" isSystem="false"/><branch id="{_x(theme_toolkit["branch_id"])}" name="Main"/><snapshot id="{_x(theme_toolkit["snapshot_id"])}" name="{_x(theme_toolkit["snapshot_name"])}"/></dependency>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<p:package buildId="BPM8600-20260615-202317" buildVersion="8.6.11" buildDescription="IBM Business Process Manager V8.6.11.26000" fixPack="26000" containsECM="false" containsBPMN2="false" xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/package.xsd">
 <target><project id="{proj_id}" name="{_x(app["name"])}" description="{_x(app.get("description", ""))}" shortName="{_x(_normalize_acronym(app["acronym"]))}" isToolkit="false" isHidden="false" isSystem="false" solutionID="" solutionServerName="" solutionPrefix="" type="" isTemplate="false" isIconSet="false" caseDisplayName=""/>
 <branch id="{branch_id}" name="Main" acronym="Main" description=""/><snapshot id="{snap_id}" name="{_x(snapshot_name)}" acronym="{snapshot_acronym}" originalCreationDate="{datetime.now(timezone.utc).isoformat()}" description="Generated by baw_twx_generator.py"/></target>
 <governanceAssignments/><dependencies>
  <dependency rank="0" isManaged="false" id="{SYSDATA_DEP_ID}"><project id="{SYSDATA_PROJ_ID}" name="System Data" shortName="TWSYS" isToolkit="true" isHidden="false" isSystem="true"/><branch id="{SYSDATA_BR_ID}" name="Main"/><snapshot id="{SYSDATA_SNAP_ID}" name="{SYSDATA_SNAP_NM}"/></dependency>
  <dependency rank="1" isManaged="false" id="{UITK_DEP_ID}"><project id="{UITK_PROJ_ID}" name="UI Toolkit" shortName="SYSBPMUI" isToolkit="true" isHidden="false" isSystem="true"/><branch id="{UITK_BR_ID}" name="Main"/><snapshot id="{UITK_SNAP_ID}" name="{UITK_SNAP_NM}"/></dependency>{theme_dependency}
 </dependencies><objects>{obj_entries}</objects><files>{file_entries}</files><migrationPolicies/>
</p:package>'''


def build_theme_toolkit_package_xml(theme_toolkit: dict, objects) -> str:
    """Build a portable toolkit package that owns the runtime Theme.

    Traditional BAW resolves ``projectDefaults/defaultTheme`` through a
    toolkit dependency UUID.  A Theme object embedded only in a process app is
    visible in Designer but is not reliably resolved by Coach runtime.  The
    generated toolkit mirrors the supported dependency architecture while
    keeping every repository ID fresh and customer-neutral.
    """
    obj_entries = ''.join(
        f'<object id="{oid}" versionId="{ver}" name="{_x(name)}" type="{typ}"/>'
        for oid, ver, name, typ in objects
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<p:package buildId="BPM8600-20260615-202317" buildVersion="8.6.11" buildDescription="IBM Business Process Manager V8.6.11.26000" fixPack="26000" containsECM="false" containsBPMN2="false" xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/package.xsd">
 <target><project id="{_x(theme_toolkit["project_id"])}" name="{_x(theme_toolkit["name"])}" description="Portable enterprise Coach theme generated with fresh repository identifiers." shortName="{_x(theme_toolkit["acronym"])}" isToolkit="true" isHidden="false" isSystem="false" solutionID="" solutionServerName="" solutionPrefix="" type="" isTemplate="false" isIconSet="false" caseDisplayName=""/>
 <branch id="{_x(theme_toolkit["branch_id"])}" name="Main" acronym="Main" description=""/><snapshot id="{_x(theme_toolkit["snapshot_id"])}" name="{_x(theme_toolkit["snapshot_name"])}" acronym="ENTTHM10" originalCreationDate="{datetime.now(timezone.utc).isoformat()}" description="Generated enterprise theme toolkit"/></target>
 <governanceAssignments/><dependencies>
  <dependency rank="0" isManaged="false" id="{SYSDATA_DEP_ID}"><project id="{SYSDATA_PROJ_ID}" name="System Data" shortName="TWSYS" isToolkit="true" isHidden="false" isSystem="true"/><branch id="{SYSDATA_BR_ID}" name="Main"/><snapshot id="{SYSDATA_SNAP_ID}" name="{SYSDATA_SNAP_NM}"/></dependency>
  <dependency rank="1" isManaged="false" id="{UITK_DEP_ID}"><project id="{UITK_PROJ_ID}" name="UI Toolkit" shortName="SYSBPMUI" isToolkit="true" isHidden="false" isSystem="true"/><branch id="{UITK_BR_ID}" name="Main"/><snapshot id="{UITK_SNAP_ID}" name="{UITK_SNAP_NM}"/></dependency>
 </dependencies><objects>{obj_entries}</objects><files></files><migrationPolicies/>
</p:package>'''


def build_theme_toolkit_archive(theme_toolkit: dict, theme_id: str,
                                theme_ver: str, theme_name: str,
                                profile: dict) -> bytes:
    """Build the toolkit archive embedded inside the process-app TWX.

    BAW's one-file process-app exports place included toolkit snapshots under
    ``toolkits/<snapshot-id>.zip``.  Keeping the Theme in that nested toolkit
    preserves runtime Theme resolution while the caller receives one TWX.
    """
    theme_xml = build_ui_theme_xml(theme_id, theme_ver, theme_name, profile)
    objects = [(theme_id, theme_ver, theme_name, "uiTheme")]
    entries = {
        f"objects/{theme_id}.xml": theme_xml.encode(),
        "META-INF/package.xml": build_theme_toolkit_package_xml(theme_toolkit, objects).encode(),
        # Included-toolkit archives exported by Traditional BAW use an
        # unnamespaced metadata document.  Object membership is authoritative
        # in package.xml; no repository-specific tags are required here.
        "META-INF/metadata.xml": b'<?xml version="1.0" encoding="UTF-8"?>\n<metadata/>\n',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def _history_entry_class_name(history: dict) -> str:
    return _baw_safe_name(str(history.get("entry_type") or history.get("class_name") or "CommentHistoryEntry"))


def build_history_entry_twclass(history: dict, class_id: str, version_id: str) -> str:
    """Emit a self-contained local twClass for the shared history row.

    This is intentionally a normal application Business Object.  It does not
    copy a bank/toolkit UUID; every generated package receives fresh IDs and
    therefore remains portable across BAW repositories.
    """
    name = _history_entry_class_name(history)
    fields = history.get("fields") or []
    if not fields:
        fields = [
            {"name": "occurredAt", "type": "Date"},
            {"name": "fromActor", "type": "String"},
            {"name": "toActor", "type": "String"},
            {"name": "fromCoach", "type": "String"},
            {"name": "toCoach", "type": "String"},
            {"name": "action", "type": "String"},
            {"name": "comment", "type": "String"},
        ]
    props_json = []
    props_xml = []
    for fld in fields:
        fname = str(fld.get("name") or fld.get("field") or "").strip()
        if not fname:
            continue
        ftype = str(fld.get("type") or "String")
        if ftype not in SUPPORTED_FIELD_TYPES:
            raise ValueError(f"comment history field {fname!r} uses unsupported type {ftype!r}")
        class_ref = _field_class_id(ftype)
        primitive = class_ref.split("/")[-1]
        props_json.append({
            "annotation": {"documentation": [{}], "appinfo": [{"propertyName": [fname], "propertyRequired": [False], "propertyHidden": [False], "advancedParameterProperties": [{}]}]},
            "name": fname,
            "type": "{http://lombardi.ibm.com/schema/}" + ftype,
            "otherAttributes": {"{http://www.ibm.com/bpmsdk}refid": primitive},
        })
        props_xml.append(
            f'<property><name>{_x(fname)}</name><description isNull="true" />'
            f'<classRef>{_x(class_ref)}</classRef><arrayProperty>false</arrayProperty>'
            '<propertyDefault isNull="true" /><propertyRequired>false</propertyRequired><propertyHidden>false</propertyHidden>'
            '<annotation type="com.lombardisoftware.core.xml.XMLFieldAnnotation" version="2.0">'
            '<exclude isNull="true" /><nodeType isNull="true" /><name isNull="true" /><namespace isNull="true" />'
            '<typeName isNull="true" /><typeNamespace isNull="true" /><minOccurs isNull="true" />'
            '<maxOccurs isNull="true" /><nillable isNull="true" /><order isNull="true" /><wrapArray isNull="true" />'
            '<arrayTypeName isNull="true" /><arrayTypeAnonymous isNull="true" /><arrayItemName isNull="true" />'
            '<arrayItemWildcard isNull="true" /><wildcard isNull="true" /><wildcardVariety isNull="true" />'
            '<wildcardMode isNull="true" /><wildcardNamespace isNull="true" /><timeZone isNull="true" />'
            '</annotation></property>'
        )
    json_data = {
        "attributeFormDefault": "unqualified",
        "elementFormDefault": "unqualified",
        "targetNamespace": "http://BAWGenerated",
        "complexType": [{
            "annotation": {"documentation": [{}], "appinfo": [{"shared": [False], "advancedProperties": [{}], "shadow": [False]}]},
            "sequence": {"element": props_json},
            "name": name,
        }],
        "id": "_" + class_id,
    }
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<teamworks>
  <twClass id="{class_id}" name="{_x(name)}">
    <lastModified>{_now_ms()}</lastModified><lastModifiedBy>admin</lastModifiedBy>
    <classId>{class_id}</classId><type>1</type><isSystem>false</isSystem><shared>false</shared>
    <isShadow>false</isShadow><globalLifetime>false</globalLifetime><internalName isNull="true" />
    <extensionType isNull="true" /><saveServiceRef isNull="true" /><bpmn2Data isNull="true" />
    <externalId>itm.{class_id}</externalId><dependencySummary isNull="true" />
    <jsonData>{_x(json.dumps(json_data, separators=(",", ":"), ensure_ascii=False))}</jsonData>
    <description isNull="true" /><guid>guid:{u()}</guid><versionId>{version_id}</versionId>
    <definition>{''.join(props_xml)}</definition>
  </twClass>
</teamworks>'''


def _apply_comment_history_contract(spec: dict) -> None:
    """Materialize the shared history contract as a generated local BO.

    The contract remains the source of truth.  This helper only allocates
    repository IDs for serialization and adds a process-private collection
    variable to each process that has human work.
    """
    history = spec.get("comment_history") or {}
    has_human_work = any(
        node.get("type") == "human"
        for proc in spec.get("processes") or []
        for node in proc.get("nodes") or []
    )
    if not history:
        if has_human_work:
            raise ValueError(
                "Human Coaches require the shared top-level comment_history contract. "
                "Create and assemble all five contract files with "
                "data_contract.comment_history; do not generate a human workflow from "
                "a monolithic specification or separate comment String variables."
            )
        return
    if str(history.get("cardinality") or "list").lower() != "list":
        raise ValueError("comment_history must have cardinality 'list'")
    # `name` is the human-readable BO label (for example, "Comment History
    # Entry"), not necessarily a legal tw.local identifier.  Keep the
    # process variable explicit and use a safe default when the contract did
    # not provide one.
    history.setdefault("variable_name", "commentHistory")
    history.setdefault("entry_type", history.get("class_name") or "CommentHistoryEntry")
    if not history.get("entry_class_id"):
        history["entry_class_id"] = f"12.{u()}"
    entry_id = history["entry_class_id"]
    if not str(entry_id).startswith("12."):
        entry_id = str(entry_id).split("/")[-1]
        if not entry_id.startswith("12."):
            entry_id = "12." + entry_id.split(".", 1)[-1]
        history["entry_class_id"] = entry_id
    history["class_id"] = "/" + entry_id
    history["item_subject_ref"] = "itm." + entry_id
    history["native_status"] = "SUPPORTED"
    for proc in spec.get("processes") or []:
        if not any(n.get("type") == "human" for n in proc.get("nodes") or []):
            continue
        proc["comment_history"] = deepcopy(history)
        variables = proc.setdefault("variables", [])
        var_name = history["variable_name"]
        existing = next((v for v in variables if str(v.get("name")) == var_name), None)
        if existing:
            existing.update({"type": "CommentHistoryList", "scope": existing.get("scope", "private"), "history": deepcopy(history), "class_id": "/" + entry_id, "item_subject_ref": "itm." + entry_id})
        else:
            variables.append({"name": var_name, "type": "CommentHistoryList", "scope": "private", "history": deepcopy(history), "class_id": "/" + entry_id, "item_subject_ref": "itm." + entry_id})


def build_from_generator_spec(spec: dict, output: Path) -> Path:
    _apply_comment_history_contract(spec)
    validate_generator_spec(spec)
    for _proc in spec.get("processes") or []:
        _prepare_gateway_routing(_proc)

    # Work on a copy so the approved process specification / SVG labels are
    # not mutated. Only repository-facing BAW artifact names are normalized.
    spec = deepcopy(spec)
    app = dict(spec["app"])
    # The contract assembler keeps the application theme as a top-level
    # contract section.  Fold it into the local app view used by the TWX
    # serializer so the native uiTheme receives the requested palette.
    if spec.get("theme") and not app.get("theme"):
        app["theme"] = deepcopy(spec["theme"])
    app["name"] = _baw_safe_name(app["name"])
    app["acronym"] = _normalize_acronym(app["acronym"])
    output.parent.mkdir(parents=True, exist_ok=True)

    proj_id=f"2066.{u()}"; branch_id=f"2063.{u()}"; snap_id=f"2064.{u()}"
    noop_id=f"1.{u()}"; noop_ver=u()
    env_id=f"62.{u()}"; env_ver=u(); pd_id=f"63.{u()}"; pd_ver=u()
    theme_id=f"72.{u()}"; theme_ver=u()
    profile = _theme_profile_from_application(app)
    theme_name = str((app.get("theme") or {}).get("name") or "Enterprise Burgundy Theme")
    theme_toolkit = {
        "dependency_id": f"2069.{u()}",
        "project_id": f"2066.{u()}",
        "branch_id": f"2063.{u()}",
        "snapshot_id": f"2064.{u()}",
        "name": "Enterprise Design Theme",
        "acronym": "ENTTHM",
        "snapshot_name": "1.0.0",
    }
    objects=[]; entries={}
    entries[f"objects/{noop_id}.xml"] = build_noop_system_service(noop_id, noop_ver).encode()
    objects.append((noop_id, noop_ver, "BAW Generic Auto Complete", "process"))

    # Runtime Theme resolution in Traditional BAW is dependency-based.  Keep
    # the Theme in a generated toolkit, then embed that toolkit snapshot in the
    # outer process-app TWX so the skill still produces one self-contained
    # deliverable.
    entries[f"toolkits/{theme_toolkit['snapshot_id']}.zip"] = (
        build_theme_toolkit_archive(
            theme_toolkit, theme_id, theme_ver, theme_name, profile
        )
    )

    history = spec.get("comment_history") or {}
    if history:
        history_id = str(history.get("entry_class_id"))
        history_ver = u()
        entries[f"objects/{history_id}.xml"] = build_history_entry_twclass(history, history_id, history_ver).encode()
        objects.append((history_id, history_ver, _history_entry_class_name(history), "twClass"))

    for proc in spec["processes"]:
        human_ids={}
        human_ios={}
        for n in proc["nodes"]:
            if n["type"] != "human":
                continue

            pid=f"1.{u()}"; ver=u(); human_ids[n["id"]]=pid

            # Keep the BPD activity label as written in the approved spec, but
            # give the standalone generated CSHS a repository-safe object name.
            task=_human_task_from_node(n, _process_variable_catalog(proc))
            task.name = _baw_safe_name(task.name)

            # Allocate the CSHS interface once and reuse the exact ids in the
            # BPD call-activity interface + data mappings.
            task_io = _make_io(task)
            human_ios[n["id"]] = task_io

            entries[f"objects/{pid}.xml"] = fixed_build_cshs_xml(
                task,pid,ver,io=task_io
            ).encode()
            objects.append((pid,ver,task.name,"process"))

        bpd_id=f"25.{u()}"; bpd_ver=u()

        # A BPD itself is also a repository Process Designer object.
        # Shorten only its repository-facing process name when necessary.
        proc_for_baw = deepcopy(proc)
        proc_for_baw["name"] = _baw_safe_name(proc_for_baw["name"])

        entries[f"objects/{bpd_id}.xml"] = build_generic_bpd_xml(
            proc_for_baw,bpd_id,bpd_ver,human_ids,noop_id,human_ios=human_ios
        ).encode()
        objects.append((bpd_id,bpd_ver,proc_for_baw["name"],"bpd"))

    entries[f"objects/{env_id}.xml"] = build_env_vars_xml(env_id,env_ver).encode()
    theme_ref = f"{theme_toolkit['dependency_id'].split('.', 1)[1]}/{theme_id}"
    entries[f"objects/{pd_id}.xml"] = build_project_defaults_xml(pd_id,pd_ver,app["acronym"],theme_ref=theme_ref).encode()
    objects += [(env_id,env_ver,"Environment Variables","environmentVariableSet"),(pd_id,pd_ver,"Process App Settings","projectDefaults")]

    # Catch IBM repository-name issues locally before the TWX reaches BAW/DB2.
    _validate_package_object_names(objects)
    entries["META-INF/package.xml"] = build_package_xml_generic(
        proj_id, branch_id, snap_id, app, objects,
        theme_toolkit=theme_toolkit,
    ).encode()
    entries["META-INF/metadata.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<p:metadata xmlns:p="http://lombardisoftware.com/schema/teamworks/7.0.0/metadata.xsd">\n'
        f'    <projectType>processApp</projectType>\n'
        f'    <projectId>{proj_id}</projectId>\n'
        f'    <name>{escape(app["name"])}</name>\n'
        f'    <shortName>{escape(app["acronym"])}</shortName>\n'
        f'    <description>{escape(app.get("description",""))}</description>\n'
        f'</p:metadata>\n'
    ).encode()
    entries["META-INF/MANIFEST.MF"] = b'Manifest-Version: 1.0\r\n\r\n'
    entries["META-INF/properties.json"] = b'{"twxWithoutToolkits":"false"}'

    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items(): z.writestr(name,data)
    validate_twx_generic(output,spec)
    return output



def validate_twx_generic(path: Path, spec: Optional[dict] = None) -> None:
    errors = []
    if not zipfile.is_zipfile(path):
        raise ValueError("Output is not a valid ZIP/TWX")

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for req in (
            "META-INF/package.xml", "META-INF/metadata.xml",
            "META-INF/MANIFEST.MF", "META-INF/properties.json"
        ):
            if req not in names:
                errors.append(f"missing {req}")

        try:
            pkg = ET.fromstring(z.read("META-INF/package.xml"))
        except Exception as exc:
            raise ValueError(f"package.xml invalid: {exc}")

        objects = [x for x in pkg.iter() if x.tag.endswith("object")]

        # A self-contained one-file export carries each non-system toolkit
        # dependency as toolkits/<snapshot-id>.zip.  Validate the generated
        # Theme toolkit's identity and complete Theme source before import.
        dependencies = [x for x in pkg.iter() if x.tag.endswith("dependency")]
        for dep in dependencies:
            dep_project = next(
                (x for x in dep.iter() if x.tag.endswith("project")), None
            )
            dep_snapshot = next(
                (x for x in dep.iter() if x.tag.endswith("snapshot")), None
            )
            if dep_project is None or dep_snapshot is None:
                continue
            if dep_project.attrib.get("isToolkit") != "true":
                continue
            if dep_project.attrib.get("isSystem") == "true":
                continue
            snapshot_id = dep_snapshot.attrib.get("id") or ""
            toolkit_path = f"toolkits/{snapshot_id}.zip"
            if toolkit_path not in names:
                errors.append(
                    f"custom toolkit dependency {dep_project.attrib.get('name')!r} "
                    f"is not embedded at {toolkit_path}"
                )
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(z.read(toolkit_path))) as nested:
                    nested_pkg = ET.fromstring(nested.read("META-INF/package.xml"))
                    nested_target = next(
                        x for x in nested_pkg.iter() if x.tag.endswith("target")
                    )
                    nested_project = next(
                        x for x in nested_target.iter() if x.tag.endswith("project")
                    )
                    nested_snapshot = next(
                        x for x in nested_target.iter() if x.tag.endswith("snapshot")
                    )
                    if nested_project.attrib.get("id") != dep_project.attrib.get("id"):
                        errors.append(
                            f"{toolkit_path}: toolkit project ID does not match dependency"
                        )
                    if nested_snapshot.attrib.get("id") != snapshot_id:
                        errors.append(
                            f"{toolkit_path}: toolkit snapshot ID does not match dependency"
                        )
                    theme_objects = [
                        x for x in nested_pkg.iter()
                        if x.tag.endswith("object") and x.attrib.get("type") == "uiTheme"
                    ]
                    if not theme_objects:
                        errors.append(f"{toolkit_path}: embedded toolkit has no uiTheme")
                    for theme_obj in theme_objects:
                        theme_path = f"objects/{theme_obj.attrib.get('id')}.xml"
                        theme_root = ET.fromstring(nested.read(theme_path))
                        theme_content = theme_root.findtext(".//themeContent") or ""
                        for symbol in (
                            "@bpm-border-normal:",
                            "@bpm-font-family-base:",
                            "@bpm-text-color-primary:",
                            "@bpm-input-border:",
                            "@bpm-btn-primary-bg:",
                            "@bpm-section-header-default-bg:",
                            "@bpm-table-bg:",
                            "@bpm-note-default-bg:",
                            "@bpm-pagination-bg:",
                            "#Theme_Level_Id#",
                        ):
                            if symbol not in theme_content:
                                errors.append(
                                    f"{toolkit_path}/{theme_path}: incomplete Theme "
                                    f"source; missing {symbol}"
                                )
                        if len(theme_content) < 50000:
                            errors.append(
                                f"{toolkit_path}/{theme_path}: Theme source is "
                                f"suspiciously small ({len(theme_content)} characters)"
                            )
            except Exception as exc:
                errors.append(f"{toolkit_path}: invalid embedded toolkit archive: {exc}")

        # Mirror the BAW repository PO_NAME safety check locally so a TWX
        # fails with a readable message instead of DB2 SQLCODE=-545.
        for obj in objects:
            obj_name = (obj.attrib.get("name") or "").strip()
            if not obj_name:
                errors.append(f"{obj.attrib.get('id')}: package object name is empty")
            elif len(obj_name) > BAW_OBJECT_NAME_MAX:
                errors.append(
                    f"{obj.attrib.get('id')}: package object name exceeds "
                    f"{BAW_OBJECT_NAME_MAX} characters: {obj_name!r}"
                )

        for obj in objects:
            fn = f"objects/{obj.attrib.get('id')}.xml"
            if fn not in names:
                errors.append(f"missing {fn}")
                continue
            raw = z.read(fn)
            try:
                root = ET.fromstring(raw)
            except Exception as exc:
                errors.append(f"{fn}: XML invalid: {exc}")
                continue

            if obj.attrib.get("type") == "uiTheme":
                ui_theme = root.find("uiTheme")
                content = ui_theme.findtext("themeContent") if ui_theme is not None else ""
                if not content:
                    errors.append(f"{fn}: uiTheme themeContent missing")
                else:
                    # These are representative compile-time dependencies from
                    # the BAW 8.6.11 Theme editor/runtime.  Their presence is a
                    # much stronger portability check than merely accepting a
                    # syntactically valid uiTheme XML object.
                    required_theme_symbols = (
                        "@bpm-border-normal:",
                        "@bpm-font-family-base:",
                        "@bpm-text-color-primary:",
                        "@bpm-input-border:",
                        "@bpm-btn-primary-bg:",
                        "@bpm-section-header-default-bg:",
                        "@bpm-table-bg:",
                        "@bpm-note-default-bg:",
                        "@bpm-pagination-bg:",
                        "#Theme_Level_Id#",
                    )
                    missing_symbols = [
                        symbol for symbol in required_theme_symbols
                        if symbol not in content
                    ]
                    if missing_symbols:
                        errors.append(
                            f"{fn}: incomplete BAW theme source; missing "
                            + ", ".join(missing_symbols)
                        )
                    if len(content) < 50000:
                        errors.append(
                            f"{fn}: BAW theme source is suspiciously small "
                            f"({len(content)} characters); a palette-only theme "
                            "will import but fail LESS compilation at runtime"
                        )

            if obj.attrib.get("type") == "bpd":
                bpd = root.find("bpd")
                if bpd is None:
                    errors.append(f"{fn}: missing bpd")
                    continue
                if not bpd.findtext("bpmn2Data"):
                    errors.append(f"{fn}: missing bpmn2Data")
                if not bpd.findtext("jsonData"):
                    errors.append(f"{fn}: missing jsonData")
                native = bpd.find("BusinessProcessDiagram")
                if native is None:
                    errors.append(f"{fn}: missing native BusinessProcessDiagram")
                else:
                    pool = native.find("pool")
                    if pool is not None:
                        private_vars = {
                            (pv.findtext("name") or "").strip(): pv
                            for pv in pool.findall("privateVariable")
                        }
                        for pv_name, pv in private_vars.items():
                            class_id = (pv.findtext("classId") or "").strip()
                            expected_prefix = f"{SYSDATA_DEP_UUID}/12."
                            local_object_class = re.fullmatch(r"/12\.[0-9a-fA-F-]{36}", class_id)
                            if not (local_object_class or (
                                class_id.startswith(expected_prefix)
                                and re.fullmatch(
                                    re.escape(expected_prefix) + r"[0-9a-fA-F-]{36}",
                                    class_id
                                )
                            )):
                                errors.append(
                                    f"{fn}: process variable {pv_name!r} has invalid native "
                                    f"classId {class_id!r}; expected package-local "
                                    f"System Data dependency UUID + /12.<primitive-uuid>"
                                )
                        refs = set(re.findall(
                            r"tw\.local\.([A-Za-z_]\w*)",
                            unescape(bpd.findtext("bpmn2Data") or "")
                        ))
                        missing = sorted(refs - set(private_vars))
                        if missing:
                            errors.append(
                                f"{fn}: runtime tw.local variables missing native privateVariable: "
                                + ", ".join(missing)
                            )
                    if pool is None:
                        errors.append(f"{fn}: native pool missing")
                    else:
                        for lane in pool.findall("lane"):
                            try:
                                lane_h = int(float(lane.findtext("height") or "0"))
                            except ValueError:
                                lane_h = 0
                            lname = lane.findtext("name") or "<unnamed>"
                            if lane_h <= 0:
                                errors.append(f"{fn}: lane {lname!r} has invalid height")
                            for fo in lane.findall("flowObject"):
                                loc = fo.find("./position/location")
                                if loc is None:
                                    continue
                                try:
                                    y = int(float(loc.attrib.get("y", "0")))
                                except ValueError:
                                    y = -1
                                if y < 0 or y >= lane_h:
                                    errors.append(
                                        f"{fn}: node {fo.findtext('name')!r} lies outside lane "
                                        f"{lname!r} (y={y}, laneHeight={lane_h})"
                                    )

                                implementation = fo.find("./component/implementation")
                                if implementation is None:
                                    continue
                                for mapping in implementation.findall(
                                    "inputActivityParameterMapping"
                                ):
                                    mapping_name = (mapping.findtext("name") or "").strip()
                                    class_id = (mapping.findtext("classId") or "").strip()
                                    input_flag = (mapping.findtext("input") or "").strip()
                                    value = (mapping.findtext("value") or "").strip()
                                    parameter_id = (
                                        mapping.findtext("parameterId") or ""
                                    ).strip()
                                    obsolete = (
                                        mapping.find("expression") is not None
                                        or mapping.find("activityParameterId") is not None
                                    )
                                    if obsolete or not all((
                                        mapping_name,
                                        class_id,
                                        input_flag == "true",
                                        value,
                                        parameter_id,
                                    )):
                                        errors.append(
                                            f"{fn}: human activity {fo.findtext('name')!r} "
                                            "has invalid native input mapping; expected "
                                            "name/classId/input/value/parameterId"
                                        )
                                        continue
                                    if value != f"tw.local.{mapping_name}":
                                        errors.append(
                                            f"{fn}: native input mapping {mapping_name!r} "
                                            f"has mismatched value {value!r}"
                                        )
                                    if not parameter_id.startswith("2055."):
                                        errors.append(
                                            f"{fn}: native input mapping {mapping_name!r} "
                                            f"has invalid parameterId {parameter_id!r}"
                                        )

                                for mapping in implementation.findall(
                                    "outputActivityParameterMapping"
                                ):
                                    mapping_name = (mapping.findtext("name") or "").strip()
                                    mapping_mode = (mapping.findtext("mappingMode") or "").strip()
                                    class_id = (mapping.findtext("classId") or "").strip()
                                    value = (mapping.findtext("value") or "").strip()
                                    source_path = (mapping.findtext("sourcePath") or "").strip()
                                    target_path = (mapping.findtext("targetPath") or "").strip()
                                    parameter_id = (
                                        mapping.findtext("parameterId") or ""
                                    ).strip()
                                    obsolete = (
                                        mapping.find("expression") is not None
                                        or mapping.find("activityParameterId") is not None
                                    )
                                    if obsolete or not all((
                                        mapping_name,
                                        mapping_mode == "basic",
                                        class_id,
                                        value,
                                        source_path,
                                        target_path,
                                        parameter_id,
                                    )):
                                        errors.append(
                                            f"{fn}: human activity {fo.findtext('name')!r} "
                                            "has invalid native output mapping; expected "
                                            "mappingMode/name/classId/value/sourcePath/"
                                            "targetPath/parameterId"
                                        )
                                        continue
                                    if value != f"tw.local.{mapping_name}":
                                        errors.append(
                                            f"{fn}: native output mapping {mapping_name!r} "
                                            f"has mismatched value {value!r}"
                                        )
                                    if source_path != f"tw.outputs.{mapping_name}":
                                        errors.append(
                                            f"{fn}: native output mapping {mapping_name!r} "
                                            f"has mismatched sourcePath {source_path!r}"
                                        )
                                    if target_path != f"tw.local.{mapping_name}":
                                        errors.append(
                                            f"{fn}: native output mapping {mapping_name!r} "
                                            f"has mismatched targetPath {target_path!r}"
                                        )
                                    if not parameter_id.startswith("2055."):
                                        errors.append(
                                            f"{fn}: native output mapping {mapping_name!r} "
                                            f"has invalid parameterId {parameter_id!r}"
                                        )

                                # Validate the complete parent/CSHS handoff,
                                # not only the shape of mappings that happen
                                # to be present.  A missing collection output
                                # otherwise imports cleanly but silently drops
                                # mutations such as appended comment history.
                                attached_id = (
                                    implementation.findtext("attachedActivityId") or ""
                                ).strip().lstrip("/")
                                attached_path = f"objects/{attached_id}.xml"
                                if attached_id and attached_path in names:
                                    try:
                                        attached_root = ET.fromstring(z.read(attached_path))
                                        attached_proc = attached_root.find("process")
                                        parameters = (
                                            attached_proc.findall("processParameter")
                                            if attached_proc is not None else []
                                        )
                                        expected_inputs = {
                                            (p.findtext("processParameterId") or "").strip()
                                            for p in parameters
                                            if (p.findtext("parameterType") or "").strip() == "1"
                                        }
                                        expected_outputs = {
                                            (p.findtext("processParameterId") or "").strip()
                                            for p in parameters
                                            if (p.findtext("parameterType") or "").strip() == "2"
                                        }
                                        mapped_inputs = {
                                            (m.findtext("parameterId") or "").strip()
                                            for m in implementation.findall(
                                                "inputActivityParameterMapping"
                                            )
                                        }
                                        mapped_outputs = {
                                            (m.findtext("parameterId") or "").strip()
                                            for m in implementation.findall(
                                                "outputActivityParameterMapping"
                                            )
                                        }
                                        missing_inputs = sorted(expected_inputs - mapped_inputs)
                                        missing_outputs = sorted(expected_outputs - mapped_outputs)
                                        if missing_inputs:
                                            errors.append(
                                                f"{fn}: human activity {fo.findtext('name')!r} "
                                                "does not map all CSHS inputs: "
                                                + ", ".join(missing_inputs)
                                            )
                                        if missing_outputs:
                                            errors.append(
                                                f"{fn}: human activity {fo.findtext('name')!r} "
                                                "does not map all CSHS outputs: "
                                                + ", ".join(missing_outputs)
                                            )
                                    except Exception as exc:
                                        errors.append(
                                            f"{fn}: cannot validate attached human service "
                                            f"{attached_id!r}: {exc}"
                                        )

                try:
                    ET.fromstring(bpd.findtext("bpmn2Data") or "")
                except Exception as exc:
                    errors.append(f"{fn}: bpmn2Data invalid: {exc}")
                try:
                    bpd_json = json.loads(bpd.findtext("jsonData") or "")
                    process_roots = [
                        x for x in bpd_json.get("rootElement", [])
                        if x.get("declaredType") == "process"
                    ]
                    if process_roots:
                        pjson = process_roots[0]
                        ios = pjson.get("ioSpecification") or {}
                        if not ios.get("dataInput") and not ios.get("dataOutput"):
                            # Processes with no Coach fields may legitimately
                            # have no generated variables.
                            pass
                        for activity in pjson.get("flowElement") or []:
                            if activity.get("declaredType") != "callActivity":
                                continue
                            if activity.get("extensionElements", {}).get("activityType") == ["UserTask"]:
                                called_id = str(activity.get("calledElement") or "").lstrip("/")
                                called_path = f"objects/{called_id}.xml"
                                if called_id and called_path in names:
                                    called_root = ET.fromstring(z.read(called_path))
                                    called_proc = called_root.find("process")
                                    parameters = (
                                        called_proc.findall("processParameter")
                                        if called_proc is not None else []
                                    )
                                    expected_input_ids = {
                                        (p.findtext("processParameterId") or "").strip()
                                        for p in parameters
                                        if (p.findtext("parameterType") or "").strip() == "1"
                                    }
                                    expected_output_ids = {
                                        (p.findtext("processParameterId") or "").strip()
                                        for p in parameters
                                        if (p.findtext("parameterType") or "").strip() == "2"
                                    }
                                    mapped_input_ids = {
                                        str(a.get("targetRef") or "")
                                        for a in activity.get("dataInputAssociation") or []
                                    }
                                    mapped_output_ids = {
                                        str(ref)
                                        for a in activity.get("dataOutputAssociation") or []
                                        for ref in (a.get("sourceRef") or [])
                                    }
                                    if expected_input_ids - mapped_input_ids:
                                        errors.append(
                                            f"{fn}: human activity {activity.get('name')!r} "
                                            "JSON input mapping is incomplete"
                                        )
                                    if expected_output_ids - mapped_output_ids:
                                        errors.append(
                                            f"{fn}: human activity {activity.get('name')!r} "
                                            "JSON output mapping is incomplete"
                                        )
                except Exception as exc:
                    errors.append(f"{fn}: jsonData invalid: {exc}")

            if obj.attrib.get("type") == "process":
                proc = root.find("process")
                if proc is not None and proc.findtext("processType") == "10":
                    if proc.find("coachflow") is None:
                        errors.append(f"{fn}: CSHS coachflow missing")
                    # Generated human Coaches must contain the professional layout.
                    jtext = proc.findtext("jsonData") or ""
                    if jtext:
                        try:
                            jdata = json.loads(jtext)
                            raw_json = json.dumps(jdata)
                            if W_SECTION not in raw_json or "ActionButtons" not in raw_json:
                                errors.append(f"{fn}: professional Coach layout missing")

                            native_outputs = {
                                (pp.attrib.get("name") or "").strip()
                                for pp in proc.findall("processParameter")
                                if (pp.findtext("parameterType") or "").strip() == "2"
                            }
                            root_el = (jdata.get("rootElement") or [{}])[0]
                            for element in (
                                root_el.get("extensionElements", {})
                                .get("userTaskImplementation", [{}])[0]
                                .get("flowElement", [])
                            ):
                                if element.get("declaredType") != "scriptTask":
                                    continue
                                client_script = "".join(
                                    (element.get("script") or {}).get("content") or []
                                )
                                if "new tw.object" in client_script:
                                    errors.append(
                                        f"{fn}: client-side script "
                                        f"{element.get('name')!r} uses server-side "
                                        "tw.object construction"
                                    )
                                if "insertIntoList" in client_script:
                                    errors.append(
                                        f"{fn}: client-side script "
                                        f"{element.get('name')!r} uses server-side "
                                        "TWObject list helpers"
                                    )
                            json_outputs = {
                                x.get("name")
                                for x in (root_el.get("ioSpecification") or {}).get("dataOutput", [])
                                if x.get("name")
                            }
                            missing_native = sorted(json_outputs - native_outputs)
                            if missing_native:
                                errors.append(
                                    f"{fn}: CSHS outputs missing native processParameter: "
                                    + ", ".join(missing_native)
                                )
                        except Exception as exc:
                            errors.append(f"{fn}: CSHS jsonData invalid: {exc}")

        # The first project element belongs to ``target``; later project
        # elements describe dependencies.  Accept both process-app and
        # companion-toolkit packages.
        project = next((x for x in pkg.iter() if x.tag.endswith("project")), None)
        if project is None:
            errors.append("package target project missing")
        elif not project.get("shortName"):
            errors.append("process app acronym missing")

    if errors:
        raise ValueError("TWX validation failed:\n- " + "\n- ".join(errors))

    if spec is not None:
        total = sum(len(p.get("source_coverage") or []) for p in spec.get("processes", []))
        print(f"✅ BRD source-coverage validation passed: {total} mapped source steps")
    print(f"✅ Generic TWX structural validation passed: {path}")



def _svg_wrap_lines(text: str, max_chars: int = 22):
    words = str(text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3] or [""]


def _process_sequence_order(proc: dict):
    """Stable dependency ordering used only for the review SVG.

    Return/rework edges intentionally point backwards.  They are excluded from
    the visual ordering pass so that a terminal event is ranked after the
    activity that actually completes its branch.  A breadth-first traversal
    could enqueue an End before a later system/external activity and render the
    End behind or before that activity even though the JSON edge is correct.
    """
    nodes = proc.get("nodes", [])
    node_by_id = {n["id"]: n for n in nodes}
    outgoing = {n["id"]: [] for n in nodes}
    incoming_count = {n["id"]: 0 for n in nodes}
    for f in proc.get("flows", []):
        label = str(f.get("label") or "").strip().lower()
        value = str(f.get("value") or "").strip().lower()
        condition = str(f.get("condition") or "").strip().lower()
        # Return/rework is a deliberate backward edge, not normal layout order.
        if label == "return" or value == "return" or "return" in condition:
            continue
        if f["from"] in outgoing and f["to"] in incoming_count:
            outgoing[f["from"]].append(f["to"])
            incoming_count[f["to"]] += 1

    # Stable Kahn topological order.  This guarantees every End follows all
    # non-return predecessors, including system/external branch activities.
    starts = [n["id"] for n in nodes if n.get("type") == "start"]
    queue = [n["id"] for n in nodes if incoming_count[n["id"]] == 0]
    queue.sort(key=lambda nid: (0 if nid in starts else 1, next(i for i, n in enumerate(nodes) if n["id"] == nid)))
    order, seen = [], set()
    while queue:
        nid = queue.pop(0)
        if nid in seen or nid not in node_by_id:
            continue
        seen.add(nid)
        order.append(nid)
        for tgt in outgoing.get(nid, []):
            incoming_count[tgt] -= 1
            if incoming_count[tgt] == 0:
                queue.append(tgt)
        queue.sort(key=lambda candidate: next(i for i, n in enumerate(nodes) if n["id"] == candidate))

    # Keep any cyclic/disconnected nodes visible.  Valid return loops should
    # already have been removed from the ordering graph; this is a safe fallback
    # for unusual but inspectable specs.
    for n in nodes:
        if n["id"] not in seen:
            order.append(n["id"])

    return order


def render_process_svg(proc: dict, output_path: Path) -> None:
    """
    Render a dependency-free SVG review diagram directly from BAW_GENERATOR_SPEC.
    The SVG is therefore the exact graph that the TWX generator consumes.
    """
    lanes = _lane_specs(proc)
    nodes = proc.get("nodes", [])
    flows = proc.get("flows", [])
    node_by_id = {n["id"]: n for n in nodes}
    order = _process_sequence_order(proc)
    order_index = {nid: i for i, nid in enumerate(order)}
    lane_index = {lane["name"]: i for i, lane in enumerate(lanes)}

    # Layout constants.
    lane_label_w = 175
    top = 58
    lane_h = 150
    node_w = 148
    node_h = 58
    x_step = 190
    left = lane_label_w + 42
    right_pad = 90
    width = max(1100, left + max(1, len(order)) * x_step + right_pad)
    height = top + max(1, len(lanes)) * lane_h + 50

    positions = {}
    for nid in order:
        n = node_by_id[nid]
        x = left + order_index[nid] * x_step
        y = top + lane_index[n["lane"]] * lane_h + (lane_h - node_h) / 2
        positions[nid] = (x, y)

    esc = html.escape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{esc(proc["name"])}</title>',
        f'<desc id="desc">Process flow generated directly from BAW_GENERATOR_SPEC with {len(nodes)} nodes and {len(flows)} flows.</desc>',
        '<defs>',
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,4 L0,8 z" fill="#475569"/></marker>',
        '<style>',
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;fill:#0f172a}',
        '.lane{font-size:14px;font-weight:600}.node{font-size:11.5px}.id{font-size:8.5px;fill:#64748b}.edge{font-size:10px;fill:#334155}',
        '</style>',
        '</defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="30" font-size="19" font-weight="700">{esc(proc["name"])}</text>',
        '<text x="14" y="30" font-size="10" fill="#64748b">BAW process review SVG</text>',
    ]

    # Swimlanes.
    for i, lane in enumerate(lanes):
        y = top + i * lane_h
        fill = "#f8fafc" if i % 2 == 0 else "#ffffff"
        parts.append(f'<rect x="8" y="{y}" width="{width-16}" height="{lane_h}" fill="{fill}" stroke="#cbd5e1"/>')
        parts.append(f'<rect x="8" y="{y}" width="{lane_label_w}" height="{lane_h}" fill="#eef2f7" stroke="#cbd5e1"/>')
        parts.append(f'<text class="lane" x="22" y="{y + lane_h/2 + 5}">{esc(lane["name"])}</text>')

    # Flows behind nodes.
    for f in flows:
        if f["from"] not in positions or f["to"] not in positions:
            continue
        sx, sy = positions[f["from"]]
        tx, ty = positions[f["to"]]
        sx2 = sx + node_w
        sy2 = sy + node_h / 2
        ty2 = ty + node_h / 2

        forward = tx >= sx
        if forward:
            ex = tx
            c1x, c2x = sx2 + 45, ex - 45
            d = f"M {sx2:.1f} {sy2:.1f} C {c1x:.1f} {sy2:.1f}, {c2x:.1f} {ty2:.1f}, {ex:.1f} {ty2:.1f}"
            lx, ly = (sx2 + ex) / 2, (sy2 + ty2) / 2 - 8
        else:
            ex = tx + node_w
            arc_y = max(top - 20, min(sy2, ty2) - 55)
            d = f"M {sx2:.1f} {sy2:.1f} C {sx2+60:.1f} {arc_y:.1f}, {ex+60:.1f} {arc_y:.1f}, {ex:.1f} {ty2:.1f}"
            lx, ly = (sx2 + ex) / 2, arc_y - 7

        parts.append(f'<path d="{d}" fill="none" stroke="#64748b" stroke-width="1.4" marker-end="url(#arrow)"/>')
        label = str(f.get("label") or "").strip()
        if label:
            safe = esc(label)
            label_w = max(42, min(120, len(label) * 6 + 16))
            parts.append(f'<rect x="{lx-label_w/2:.1f}" y="{ly-12:.1f}" width="{label_w}" height="17" rx="4" fill="white" stroke="#e2e8f0"/>')
            parts.append(f'<text class="edge" text-anchor="middle" x="{lx:.1f}" y="{ly:.1f}">{safe}</text>')

    # Nodes.
    colors = {
        "human": ("#eff6ff", "#2563eb"),
        "system": ("#f8fafc", "#64748b"),
        "external": ("#faf5ff", "#9333ea"),
        "notification": ("#ecfeff", "#0891b2"),
        "start": ("#f0fdf4", "#16a34a"),
        "end": ("#f0fdf4", "#16a34a"),
        "gateway": ("#fff7ed", "#d97706"),
    }

    for nid in order:
        n = node_by_id[nid]
        x, y = positions[nid]
        fill, stroke = colors.get(n["type"], ("#ffffff", "#64748b"))

        if n["type"] == "gateway":
            cx, cy = x + node_w/2, y + node_h/2
            pts = f"{cx:.1f},{y:.1f} {x+node_w:.1f},{cy:.1f} {cx:.1f},{y+node_h:.1f} {x:.1f},{cy:.1f}"
            parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            text_start = cy - 6
        elif n["type"] in {"start", "end"}:
            parts.append(f'<ellipse cx="{x+node_w/2:.1f}" cy="{y+node_h/2:.1f}" rx="{node_w/2:.1f}" ry="{node_h/2:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            text_start = y + 20
        else:
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
            text_start = y + 18

        for li, line in enumerate(_svg_wrap_lines(n["name"])):
            parts.append(f'<text class="node" text-anchor="middle" x="{x+node_w/2:.1f}" y="{text_start + li*14:.1f}">{esc(line)}</text>')
        parts.append(f'<text class="id" text-anchor="middle" x="{x+node_w/2:.1f}" y="{y+node_h+12:.1f}">{esc(nid)}</text>')

    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")


def _artifact_root(markdown_path: Path, artifact_dir: Optional[Path] = None) -> Path:
    """Return the single folder that owns every generated run artifact."""
    markdown_path = Path(markdown_path)
    if artifact_dir is not None:
        root = Path(artifact_dir).expanduser()
        if not root.is_absolute():
            root = markdown_path.parent / root
    elif markdown_path.parent.name == "BAW_Process_Flows":
        root = markdown_path.parent
    else:
        root = markdown_path.parent / "BAW_Process_Flows"
    return root


def _artifact_output_path(root: Path, output: Optional[Path], default_name: str) -> Path:
    """Resolve an output path and refuse to scatter artifacts outside root."""
    root = root.resolve()
    if output is None:
        result = root / default_name
    else:
        result = Path(output).expanduser()
        if not result.is_absolute():
            result = root / result
        result = result.resolve()
    try:
        result.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Generated artifacts must stay under {root}; got {result}"
        ) from exc
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def create_process_review_svgs(
    markdown_path: Path,
    spec: dict,
    artifact_dir: Optional[Path] = None,
) -> Path:
    out_dir = _artifact_root(markdown_path, artifact_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for proc in spec.get("processes", []):
        out = out_dir / f"{_slug(proc['name'])}.svg"
        render_process_svg(proc, out)
        created.append(out)

    print(f"✅ Process review SVGs created: {len(created)}")
    for p in created:
        print(f"   • {p.name}")
    print(f"📁 Review folder: {out_dir}")
    return out_dir



def _validate_human_action_contracts(spec: dict) -> None:
    errors = []
    for proc in spec.get("processes") or []:
        _prepare_gateway_routing(proc)
        catalog = _process_variable_catalog(proc)
        flows = proc.get("flows") or []

        for human in [n for n in proc.get("nodes") or [] if n.get("type") == "human"]:
            actions = [str(x) for x in (human.get("actions") or [])]
            if len(actions) < 2:
                continue

            var = _infer_human_decision_variable(human, catalog)
            if not var:
                errors.append(f"{proc['name']}/{human['id']}: no action decision variable")
                continue
            if var not in catalog:
                errors.append(f"{proc['name']}/{human['id']}: action variable {var!r} missing from process variables")
            if var not in (human.get("outputs") or []):
                errors.append(f"{proc['name']}/{human['id']}: action variable {var!r} missing from human-task outputs")

            outs = [f for f in flows if f.get("from") == human["id"]]
            if len(outs) >= 2:
                for f in outs:
                    cond = str(f.get("condition") or "").strip()
                    if not cond or cond.lower() == "false":
                        errors.append(f"{proc['name']}/{human['id']}: branch {f.get('label') or f.get('to')} has invalid condition")
                    elif var not in cond:
                        errors.append(f"{proc['name']}/{human['id']}: branch {f.get('label') or f.get('to')} does not evaluate {var}")

            # The common pattern is Human Task -> exclusive decision gateway.
            # Every outgoing gateway branch must evaluate the human action.
            next_ids = [f.get("to") for f in outs]
            for next_id in next_ids:
                gateway = next(
                    (
                        n for n in proc.get("nodes") or []
                        if n.get("id") == next_id and n.get("type") == "gateway"
                    ),
                    None,
                )
                if not gateway:
                    continue
                # A Submit branch may legitimately enter an independent
                # business gateway (for example Opportunity Type or
                # Orientation). Only an action gateway whose decision variable
                # is the human button variable must evaluate that variable.
                gateway_var = str(gateway.get("decision_variable") or "").strip()
                if gateway_var and gateway_var != var:
                    continue
                gateway_outs = [f for f in flows if f.get("from") == next_id]
                if len(gateway_outs) < 2:
                    continue
                for branch in gateway_outs:
                    cond = str(branch.get("condition") or "").strip()
                    if not cond or cond.lower() == "false":
                        errors.append(
                            f"{proc['name']}/{next_id}: human-decision branch "
                            f"{branch.get('label') or branch.get('to')} must have "
                            f"an explicit {var!r} condition"
                        )
                    elif var not in cond:
                        errors.append(
                            f"{proc['name']}/{next_id}: branch "
                            f"{branch.get('label') or branch.get('to')} does not "
                            f"evaluate {var}"
                        )

    if errors:
        raise ValueError("Human action contract validation failed:\n- " + "\n- ".join(errors))


def preflight_spec(
    markdown_path: Path,
    create_svg: bool = True,
    artifact_dir: Optional[Path] = None,
) -> dict:
    """
    Validate the exact BAW_GENERATOR_SPEC used for TWX generation and create
    one local SVG review diagram per process. No TWX is produced here.
    """
    spec = extract_generator_spec(markdown_path)
    _report_baw_name_adjustments(spec)
    _report_gateway_routing(spec)
    _validate_human_action_contracts(spec)
    if create_svg:
        create_process_review_svgs(markdown_path, spec, artifact_dir=artifact_dir)
    total = sum(len(p.get("source_coverage") or []) for p in spec.get("processes", []))
    print(f"✅ BRD source-coverage validation passed: {total} mapped source steps")
    print("✅ BAW process specification preflight passed")
    return spec


def build_from_markdown(
    markdown: Path,
    output: Optional[Path] = None,
    artifact_dir: Optional[Path] = None,
) -> Path:
    spec = preflight_spec(markdown, create_svg=True, artifact_dir=artifact_dir)
    app = spec["app"]
    root = _artifact_root(markdown, artifact_dir)
    output = _artifact_output_path(root, output, f"{_slug(app['name'])}.twx")
    return build_from_generator_spec(spec, output)


def main():
    ap = argparse.ArgumentParser(
        description="Generate a new Traditional IBM BAW Process App TWX from BAW_Process_Spec.md or five BRD-to-BAW contracts"
    )
    ap.add_argument("spec", nargs="?", help="Markdown file containing ## BAW_GENERATOR_SPEC JSON")
    ap.add_argument(
        "--contracts-dir",
        help="Directory containing process_contract.json, coach_contract.json, service_contract.json, data_contract.json, and application_contract.json; assemble it before generation",
    )
    ap.add_argument("--output", "-o", help="Output .twx path")
    ap.add_argument(
        "--artifact-dir",
        help="Single folder for all generated artifacts; defaults to the spec's BAW_Process_Flows folder",
    )
    ap.add_argument("--validate", help="Validate an existing generated .twx")
    ap.add_argument(
        "--check-spec",
        action="store_true",
        help="Validate BAW_Process_Spec.md and create process-review SVG files only; do not create a TWX",
    )
    args = ap.parse_args()

    if args.validate:
        validate_twx_generic(Path(args.validate))
        return

    if args.spec and args.contracts_dir:
        ap.error("provide either a spec Markdown file or --contracts-dir, not both")
    if not args.spec and not args.contracts_dir:
        ap.error("spec Markdown file or --contracts-dir is required unless --validate is used")

    # CLI paths are relative to the caller's working directory.  Resolve them
    # before passing them to _artifact_root; otherwise a contracts directory
    # such as ``MyApp/contracts`` is accidentally prefixed with ``MyApp`` a
    # second time and produces ``MyApp/MyApp/...`` artifacts.
    artifact_dir = (
        Path(args.artifact_dir).expanduser().resolve()
        if args.artifact_dir else None
    )
    if args.contracts_dir:
        from assemble_baw_contracts import assemble_contract_bundle

        contracts_dir = Path(args.contracts_dir)
        if artifact_dir is None:
            artifact_dir = contracts_dir.parent.expanduser().resolve()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        spec_path = artifact_dir / "BAW_Process_Spec.md"
        assembled_json = artifact_dir / "BAW_GENERATOR_SPEC.json"
        assemble_contract_bundle(contracts_dir, output_md=spec_path, output_json=assembled_json)
        print(f"✅ Contract bundle assembled: {spec_path}")
    else:
        spec_path = Path(args.spec)
    if args.check_spec:
        preflight_spec(spec_path, create_svg=True, artifact_dir=artifact_dir)
        return

    out = build_from_markdown(
        spec_path,
        Path(args.output) if args.output else None,
        artifact_dir=artifact_dir,
    )
    print(f"✅ TWX created: {out}")


if __name__ == "__main__":
    main()
