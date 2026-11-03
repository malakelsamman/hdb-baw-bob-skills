#!/usr/bin/env python3
"""Inspect a Traditional IBM BAW TWX without executing its contents.

This is a read-only structural analyzer.  It intentionally reports evidence
from the archive and avoids copying project-specific UUIDs into generated
applications.  It is useful when a reference TWX is supplied as a design
example for a new BRD.

Usage:
    python3 analyze_twx.py reference.twx
    python3 analyze_twx.py reference.twx --json
"""

from __future__ import annotations

import argparse
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _text(node: ET.Element | None, default: str = "") -> str:
    return (node.text or "").strip() if node is not None else default


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse(raw: bytes) -> ET.Element | None:
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return None


def _package(zf: zipfile.ZipFile) -> dict[str, Any]:
    root = _parse(zf.read("META-INF/package.xml"))
    if root is None:
        return {}
    target = next((x for x in root.iter() if _local(x.tag) == "target"), None)
    target_children = list(target) if target is not None else []
    project = next((x for x in target_children if _local(x.tag) == "project"), None)
    branch = next((x for x in target_children if _local(x.tag) == "branch"), None)
    snapshot = next((x for x in target_children if _local(x.tag) == "snapshot"), None)
    deps = []
    for dep in root.iter():
        if _local(dep.tag) != "dependency":
            continue
        child = { _local(c.tag): c for c in dep }
        deps.append({
            "id": dep.attrib.get("id", ""),
            "rank": dep.attrib.get("rank", ""),
            "project": child.get("project", ET.Element("x")).attrib.get("name", ""),
            "branch": child.get("branch", ET.Element("x")).attrib.get("name", ""),
            "snapshot": child.get("snapshot", ET.Element("x")).attrib.get("name", ""),
        })
    return {
        "build_id": root.attrib.get("buildId", ""),
        "build_version": root.attrib.get("buildVersion", ""),
        "build_description": root.attrib.get("buildDescription", ""),
        "fix_pack": root.attrib.get("fixPack", ""),
        "target": {
            "project": project.attrib.get("name", "") if project is not None else "",
            "project_id": project.attrib.get("id", "") if project is not None else "",
            "branch": branch.attrib.get("name", "") if branch is not None else "",
            "branch_id": branch.attrib.get("id", "") if branch is not None else "",
            "snapshot": snapshot.attrib.get("name", "") if snapshot is not None else "",
            "snapshot_id": snapshot.attrib.get("id", "") if snapshot is not None else "",
        },
        "dependencies": deps,
    }


def _object_type(root: ET.Element | None) -> str:
    return _object_root(root)[0] if root is not None else "unparsed"


def _object_root(root: ET.Element) -> tuple[str, ET.Element]:
    """Return the object type and actual object element.

    TWX object XML commonly wraps the real element in a ``teamworks``
    container.  Normalize that wrapper before reading names or attributes.
    """
    if _local(root.tag) == "teamworks" and len(root):
        child = root[0]
        return _local(child.tag), child
    return _local(root.tag), root


def _class_report(root: ET.Element) -> dict[str, Any]:
    _, root = _object_root(root)
    props = [x for x in root.iter() if _local(x.tag) in {"property", "twClassProperty"}]
    names = []
    nested = 0
    lists = 0
    for prop in props:
        name = prop.attrib.get("name") or _text(next((c for c in prop if _local(c.tag) == "name"), None))
        if name:
            names.append(name)
        text = ET.tostring(prop, encoding="unicode")
        if "isArrayOf=\"true\"" in text or "isArrayOf>true" in text:
            lists += 1
        if "/12." not in text and "classId" in text:
            nested += 1
    return {"properties": len(props), "names": names[:15], "nested_or_custom": nested, "lists": lists}


def _bpd_report(root: ET.Element) -> dict[str, Any]:
    if root is None:
        return {}
    _, root = _object_root(root)
    flow = [x for x in root.iter() if _local(x.tag) == "flowObject"]
    lanes = [x for x in root.iter() if _local(x.tag) == "lane"]
    gateways = [x for x in root.iter() if _local(x.tag) == "gatewayType"]
    privates = [x for x in root.iter() if _local(x.tag) == "privateVariable"]
    counts = Counter()
    names = []
    for node in flow:
        kind = node.attrib.get("componentType") or _text(next((c for c in node if _local(c.tag) in {"type", "activityType"}), None)) or "flowObject"
        component = next((c for c in node if _local(c.tag) == "component"), None)
        if kind == "Activity" and component is not None:
            implementation = _text(next((c for c in component if _local(c.tag) == "implementationType"), None))
            task_type = _text(next((c for c in component if _local(c.tag) == "bpmnTaskType"), None))
            kind = {
                ("1", "1"): "user-task",
                ("3", "4"): "script-task",
                ("4", "3"): "service-or-linked-flow",
            }.get((implementation, task_type), f"activity-{implementation or '?'}-{task_type or '?'}")
        counts[kind] += 1
        name = node.attrib.get("name") or _text(next((c for c in node if _local(c.tag) == "name"), None))
        if name:
            names.append(name)
    priv_names = []
    for p in privates:
        n = p.attrib.get("name") or _text(next((c for c in p if _local(c.tag) == "name"), None))
        if n:
            priv_names.append(n)
    return {
        "flow_objects": len(flow),
        "lanes": len(lanes),
        "gateway_markers": len(gateways),
        "private_variables": len(privates),
        "flow_object_kinds": dict(counts),
        "sample_node_names": names[:40],
        "private_variable_names": priv_names,
    }


def _view_report(root: ET.Element) -> dict[str, Any]:
    if root is None:
        return {}
    _, root = _object_root(root)
    xml = ET.tostring(root, encoding="unicode")
    # Coach view layout/contribution XML is stored as escaped XML inside the
    # outer coachView document.  Decode it for evidence extraction only; never
    # use this data to copy project-specific identifiers into generated TWXs.
    embedded = html.unescape(xml)
    refs = re.findall(r"(?:viewRef|coachViewRef|viewId)[^>]*>([^<]+)", xml)
    bindings = len(re.findall(r"tw\.(?:businessData|local|options)", xml))
    events = Counter(re.findall(r"event[A-Z_]+", xml))
    widgets = Counter(re.findall(r"64\.[0-9a-f-]{36}", xml))
    view_uuids = Counter(re.findall(r"<ns2:viewUUID>([^<]+)</ns2:viewUUID>", embedded))

    # Capture the useful part of a repeated-table contract: layout id, widget
    # type, optional label, and the collection binding.  Nested column
    # contributions are intentionally not flattened here; their bindings are
    # reported separately so a reviewer can see the row-level contract.
    table_definitions = []
    table_pattern = re.compile(
        r"<ns2:layoutItemId>(Table[^<]*)</ns2:layoutItemId>"
        r"(?P<before>.*?)<ns2:viewUUID>(?P<widget>[^<]+)</ns2:viewUUID>"
        r"(?P<after>.*?)(?=<ns2:layoutItemId>|</ns2:contributions>)",
        re.S,
    )
    for match in table_pattern.finditer(embedded):
        before = match.group("before")
        after = match.group("after")
        labels = re.findall(
            r"<ns2:optionName>@label</ns2:optionName><ns2:value>(.*?)</ns2:value>",
            before,
            re.S,
        )
        bindings_found = re.findall(r"<ns2:binding>([^<]*)</ns2:binding>", after)
        table_definitions.append({
            "layout_id": match.group(1),
            "widget_uuid": match.group("widget"),
            "label": html.unescape(labels[-1]).strip() if labels else "",
            "binding": bindings_found[0].strip() if bindings_found else "",
        })

    # The direct configData children of a table contribution are the safe
    # table options to report.  Options in nested child contributions belong to
    # those children (for example, a document explorer in the same tab), so do
    # not accidentally attribute them to the table.
    layout_start = embedded.find("<ns2:layout")
    layout_end = embedded.find("</ns2:layout>", layout_start)
    if layout_start >= 0 and layout_end >= 0:
        layout_end += len("</ns2:layout>")
        try:
            layout_root = ET.fromstring(embedded[layout_start:layout_end])
        except ET.ParseError:
            layout_root = None
        if layout_root is not None:
            for contribution in layout_root.iter():
                if _local(contribution.tag) != "contributions":
                    continue
                direct = list(contribution)
                layout_id = _text(next((x for x in direct if _local(x.tag) == "layoutItemId"), None))
                if not layout_id.startswith("Table"):
                    continue
                options = {}
                for config in (x for x in direct if _local(x.tag) == "configData"):
                    option = _text(next((x for x in config if _local(x.tag) == "optionName"), None))
                    value = _text(next((x for x in config if _local(x.tag) == "value"), None))
                    if option:
                        options[option] = value
                uuid = _text(next((x for x in direct if _local(x.tag) == "viewUUID"), None))
                binding = _text(next((x for x in direct if _local(x.tag) == "binding"), None))
                for table in table_definitions:
                    if table["layout_id"] == layout_id:
                        table["widget_uuid"] = uuid or table["widget_uuid"]
                        table["binding"] = binding or table["binding"]
                        table["options"] = options
                        break

    row_bindings = []
    for binding in re.findall(
        r"<ns2:binding>([^<]*\.currentItem\.[^<]+)</ns2:binding>", embedded
    ):
        if binding not in row_bindings:
            row_bindings.append(binding)

    layout = len(re.findall(r"layoutItem|layout", xml))
    name = root.attrib.get("name", "")
    return {
        "name": name,
        "layout_markers": layout,
        "references": len(refs),
        "bindings": bindings,
        "events": dict(events),
        "unique_widget_ids": len(widgets),
        "top_widgets": widgets.most_common(12),
        "view_uuid_counts": dict(view_uuids.most_common()),
        "table_definitions": table_definitions,
        "table_row_bindings": row_bindings,
    }


def _human_service_report(root: ET.Element) -> dict[str, Any]:
    """Report the native Coach/view/event contract of a human service.

    Traditional BAW stores a human-service Coach as a BPMN ``formTask``.  The
    Coach layout contains a top-level ``ViewRef`` (the reusable Coach view),
    while the outgoing sequence flows carry ``coachEventBinding`` entries that
    connect button/event paths in that view to the human-service orchestration.
    This report keeps those relationships explicit instead of treating a
    Coach as a flat collection of widgets.
    """
    if root is None:
        return {}
    _, root = _object_root(root)
    form_tasks = [x for x in root.iter() if _local(x.tag) == "formTask"]
    if not form_tasks:
        return {}

    coaches = []
    for task in form_tasks:
        task_id = task.attrib.get("id", "")
        coach = {
            "name": task.attrib.get("name", ""),
            "id": task_id,
            "heritage": task.attrib.get("isHeritageCoach", ""),
            "view_refs": [],
            "event_routes": [],
        }
        layout = next((x for x in task.iter() if _local(x.tag) == "layout"), None)
        if layout is not None:
            for item in layout.iter():
                if _local(item.tag) != "layoutItem":
                    continue
                layout_id = _text(next((x for x in item if _local(x.tag) == "layoutItemId"), None))
                view_uuid = _text(next((x for x in item if _local(x.tag) == "viewUUID"), None))
                binding = _text(next((x for x in item if _local(x.tag) == "binding"), None))
                if not view_uuid:
                    continue
                options = {}
                for config in (x for x in item if _local(x.tag) == "configData"):
                    option = _text(next((x for x in config if _local(x.tag) == "optionName"), None))
                    value = _text(next((x for x in config if _local(x.tag) == "value"), None))
                    if option:
                        options[option] = value
                coach["view_refs"].append({
                    "layout_id": layout_id,
                    "view_uuid": view_uuid,
                    "binding": binding,
                    "options": options,
                })

        # A sequence flow sourced by the Coach is the executable bridge from a
        # Coach button/event to the next human-service node.
        for flow in root.iter():
            if _local(flow.tag) != "sequenceFlow" or flow.attrib.get("sourceRef") != task_id:
                continue
            event_path = _text(next((x for x in flow.iter() if _local(x.tag) == "coachEventPath"), None))
            impl = next((x for x in flow.iter() if _local(x.tag) == "sequenceFlowImplementation"), None)
            coach["event_routes"].append({
                "event_path": event_path,
                "flow_name": flow.attrib.get("name", ""),
                "target_ref": flow.attrib.get("targetRef", ""),
                "sbo_sync_enabled": impl.attrib.get("sboSyncEnabled", "") if impl is not None else "",
                "fire_validation": impl.attrib.get("fireValidation", "") if impl is not None else "",
            })
        coaches.append(coach)

    # Process parameters are declared in the XML, while their semantic names
    # are repeated in the native ioSpecification JSON.  Read the JSON-shaped
    # names when available and preserve parameter type/collection evidence from
    # the XML without guessing types from UUIDs.
    io_names = {"inputs": [], "outputs": []}
    for marker, key in (("dataInput", "inputs"), ("dataOutput", "outputs")):
        for match in re.finditer(
            rf'"{marker}"\s*:\s*\[(.*?)\]',
            ET.tostring(root, encoding="unicode"),
            re.S,
        ):
            for name in re.findall(r'"name":"([^"]+)"[^}]*?"isCollection":(true|false)', match.group(1)):
                io_names[key].append({"name": name[0], "is_collection": name[1] == "true"})
            break

    return {
        "coaches": coaches,
        "parameter_io": io_names,
    }


def _project_defaults_report(root: ET.Element) -> dict[str, str]:
    _, root = _object_root(root)
    values = {}
    for field in ("defaultXslRef", "defaultCssRef", "defaultTheme", "targetEnvironment", "namespace", "isIidOptimized", "isQueueBypass"):
        values[field] = _text(next((x for x in root if _local(x.tag) == field), None))
    return values


def _integration_hints(text: str) -> list[str]:
    checks = [
        ("SQL/DQL/DML", r"SQLStatement|Execute DQL|Execute DML|select .* from|update .* set"),
        ("external web service connector", r"externalServiceRef|##WebService|webService"),
        ("environment configuration", r"tw\.env\.|environmentVariable"),
        ("notifications/mail", r"mailSender|Send Mail|sendmail|mail"),
        ("RPA/asynchronous event", r"underCoverAgent|UCA|RPA|eventSubscription|Task Scheduler"),
        ("escalation/SLA", r"escalat|timer|deadline|SLA"),
    ]
    return [label for label, pattern in checks if re.search(pattern, text, re.I)]


def analyze(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        object_types = Counter()
        classes = []
        bpds = []
        views = []
        process_names = []
        integration_counts = Counter()
        main_bpd = None
        project_defaults = None
        human_services = []
        for name in names:
            if not name.startswith("objects/") or not name.endswith(".xml"):
                continue
            raw = zf.read(name)
            root = _parse(raw)
            typ, obj = _object_root(root) if root is not None else ("unparsed", None)
            object_types[typ] += 1
            text = raw.decode("utf-8", "replace")
            for hint in _integration_hints(text):
                integration_counts[hint] += 1
            if typ in {"twClass", "TWClass"} and obj is not None:
                classes.append({"file": name, "name": obj.attrib.get("name", ""), **_class_report(root)})
            elif typ == "bpd" and obj is not None:
                main_bpd = {"file": name, "name": obj.attrib.get("name", ""), **_bpd_report(root)}
                bpds.append(main_bpd)
            elif typ == "coachView" and obj is not None:
                views.append({"file": name, **_view_report(root)})
            elif typ == "projectDefaults" and obj is not None:
                project_defaults = {"file": name, **_project_defaults_report(root)}
            elif typ == "process" and obj is not None:
                process_names.append({"file": name, "name": obj.attrib.get("name", "")})
                human_service = _human_service_report(root)
                if human_service:
                    human_services.append({"file": name, "name": obj.attrib.get("name", ""), **human_service})
        return {
            "archive": str(path),
            "members": len(names),
            "package": _package(zf),
            "object_types": dict(object_types),
            "main_bpd": main_bpd,
            "bpds": bpds,
            "business_objects": sorted(classes, key=lambda x: x["properties"], reverse=True),
            "coach_views": views,
            "project_defaults": project_defaults,
            "processes": process_names,
            "human_services": human_services,
            "integration_hints": dict(integration_counts),
        }


def _markdown(report: dict[str, Any]) -> str:
    pkg = report.get("package", {})
    target = pkg.get("target", {})
    lines = [
        f"# TWX structural analysis: {Path(report['archive']).name}",
        "",
        f"- Build: `{pkg.get('build_version','?')}` fix pack `{pkg.get('fix_pack','?')}` ({pkg.get('build_description','')})",
        f"- Target: `{target.get('project','')}` / `{target.get('snapshot','')}`",
        f"- Archive members: {report['members']}",
        "",
        "## Object composition",
        "",
    ]
    lines.extend(f"- `{k}`: {v}" for k, v in sorted(report["object_types"].items()))
    bpd = report.get("main_bpd") or {}
    if bpd:
        lines += ["", "## Main process", "", f"- `{bpd.get('name','')}`: {bpd.get('flow_objects',0)} flow objects, {bpd.get('lanes',0)} lanes, {bpd.get('private_variables',0)} private variables"]
        lines.append(f"- Gateway markers: {bpd.get('gateway_markers',0)}")
        lines.append(f"- Private variables: {', '.join(bpd.get('private_variable_names', []))}")
    lines += ["", "## Largest business objects", ""]
    for obj in report.get("business_objects", [])[:12]:
        lines.append(f"- `{obj.get('name','')}`: {obj['properties']} properties; {obj['nested_or_custom']} nested/custom; {obj['lists']} lists")
    lines += ["", "## Coach views", ""]
    for view in report.get("coach_views", []):
        lines.append(f"- `{view.get('name','')}`: {view['references']} refs, {view['bindings']} bindings, {view['unique_widget_ids']} widget IDs, {view['events']} event markers")
        for table in view.get("table_definitions", []):
            binding = table.get("binding") or "(not bound)"
            options = ", ".join(f"{key}={value}" for key, value in table.get("options", {}).items() if key not in {"@helpText"})
            suffix = f"; options: {options}" if options else ""
            lines.append(f"  - Table `{table.get('layout_id','')}` ({table.get('label','') or 'unlabelled'}): `{binding}`; row bindings: {len(view.get('table_row_bindings', []))}{suffix}")
    lines += ["", "## Human services and Coach/view wiring", ""]
    for service in report.get("human_services", []):
        lines.append(f"- `{service.get('name','')}`: {len(service.get('coaches', []))} Coach node(s)")
        for coach in service.get("coaches", []):
            lines.append(f"  - Coach `{coach.get('name','')}`: {len(coach.get('view_refs', []))} view reference(s), {len(coach.get('event_routes', []))} event route(s)")
            for ref in coach.get("view_refs", []):
                lines.append(f"    - View `{ref.get('view_uuid','')}` at `{ref.get('layout_id','')}` bound to `{ref.get('binding','')}`")
            for route in coach.get("event_routes", []):
                event = route.get("event_path") or "(unbound flow)"
                lines.append(f"    - `{event}` -> `{route.get('flow_name','')}` -> `{route.get('target_ref','')}`")
    lines += ["", "## Integration evidence", ""]
    lines.extend(f"- {k}: {v} XML objects" for k, v in sorted(report.get("integration_hints", {}).items()))
    lines += ["", "## Dependencies", ""]
    lines.extend(f"- {d.get('project','')} — {d.get('snapshot','')} (rank {d.get('rank','')})" for d in pkg.get("dependencies", []))
    defaults = report.get("project_defaults") or {}
    if defaults:
        lines += ["", "## Project defaults", ""]
        lines.extend(f"- {key}: `{value}`" for key, value in defaults.items() if key != "file" and value)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("twx", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze(args.twx)
    output = json.dumps(report, indent=2, ensure_ascii=False) if args.as_json else _markdown(report)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
