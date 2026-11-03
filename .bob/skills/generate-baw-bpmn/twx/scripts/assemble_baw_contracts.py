#!/usr/bin/env python3
"""Assemble the five BRD-to-BAW design contracts into BAW_GENERATOR_SPEC.

The assembler is intentionally conservative. It validates cross-contract
references, preserves unsupported native designs in the assembled metadata, and
never invents an endpoint, UUID, Business Object serializer, or team.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CONTRACT_FILES = {
    "process": "process_contract.json",
    "coach": "coach_contract.json",
    "service": "service_contract.json",
    "data": "data_contract.json",
    "application": "application_contract.json",
}

PRIMITIVE_TYPES = {"String", "Integer", "Decimal", "Boolean", "Date"}
SERVICE_NODE_TYPES = {"system", "external", "notification"}
ACTOR_KINDS = {"human", "bot", "rpa", "system", "external", "notification"}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing contract file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Contract {path.name} must contain a JSON object")
    return value


def load_contracts(contract_dir: Path) -> Dict[str, dict]:
    contracts: Dict[str, dict] = {}
    for key, filename in CONTRACT_FILES.items():
        contracts[key] = _read_json(contract_dir / filename)
    return contracts


def _unique_ids(items: list, label: str, errors: list) -> set:
    seen = set()
    for index, item in enumerate(items or [], 1):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            errors.append(f"{label}[{index}] requires an id")
        elif item_id in seen:
            errors.append(f"{label} contains duplicate id {item_id!r}")
        seen.add(item_id)
    return seen


def _process_indexes(process_contract: dict) -> Tuple[dict, dict, dict, dict]:
    processes = process_contract.get("processes") or []
    process_by_name = {str(p.get("name")): p for p in processes if isinstance(p, dict)}
    nodes = {}
    flows = {}
    lanes = {}
    for process in processes:
        pname = str(process.get("name") or "")
        nodes[pname] = {str(n.get("id")): n for n in process.get("nodes") or [] if isinstance(n, dict)}
        flows[pname] = process.get("flows") or []
        lanes[pname] = {
            str(l.get("name") if isinstance(l, dict) else l)
            for l in process.get("lanes") or []
        }
    return process_by_name, nodes, flows, lanes


def validate_contracts(contracts: Dict[str, dict]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) without mutating the source contracts."""
    errors: List[str] = []
    warnings: List[str] = []

    expected_types = {
        "process": "process",
        "coach": "coach",
        "service": "service",
        "data": "data",
        "application": "application",
    }
    for key, expected in expected_types.items():
        actual = str(contracts[key].get("contractType") or "").strip().lower()
        if actual != expected:
            errors.append(
                f"{CONTRACT_FILES[key]} must have contractType {expected!r}; got {actual or 'missing'}"
            )

    application = contracts["application"]
    app = application.get("app") or {}
    if not app.get("name"):
        errors.append("application_contract.json: app.name is required")
    if not app.get("acronym"):
        errors.append("application_contract.json: app.acronym is required")

    scenario = contracts["process"].get("target_scenario") or {}
    if not str(scenario.get("text") or "").strip():
        warnings.append("process_contract.json: target_scenario is MISSING")
    if str(scenario.get("status") or "").upper() in {"MISSING", "AMBIGUOUS", "CONTRADICTORY"}:
        warnings.append(
            f"process_contract.json: target_scenario status is {str(scenario.get('status')).upper()}"
        )

    process = contracts["process"]
    actor_ids = _unique_ids(process.get("actors"), "process.actors", errors)
    gateway_ids = _unique_ids(process.get("gateways"), "process.gateways", errors)
    ledger_ids = _unique_ids(process.get("sentence_ledger"), "process.sentence_ledger", errors)
    service_ids = _unique_ids(contracts["service"].get("services"), "service.services", errors)
    coach_ids = _unique_ids(contracts["coach"].get("coaches"), "coach.coaches", errors)
    variable_ids = _unique_ids(contracts["data"].get("variables"), "data.variables", errors)
    bo_ids = _unique_ids(contracts["data"].get("business_objects"), "data.business_objects", errors)
    _unique_ids(contracts["data"].get("mappings"), "data.mappings", errors)
    _unique_ids(application.get("dependencies"), "application.dependencies", errors)

    if not ledger_ids:
        warnings.append("process_contract.json: sentence_ledger is empty; source traceability is incomplete")

    process_by_name, nodes_by_process, _flows_by_process, lanes_by_process = _process_indexes(process)
    if not process_by_name:
        errors.append("process_contract.json: processes must be a non-empty array")

    all_node_ids = set()
    human_node_ids = set()
    service_node_ids = set()
    for pname, proc in process_by_name.items():
        for actor in process.get("actors") or []:
            lane = str(actor.get("lane") or "")
            if lane and lane not in lanes_by_process.get(pname, set()):
                warnings.append(f"actor {actor.get('id')!r} references lane {lane!r} not found in process {pname!r}")
            kind = str(actor.get("kind") or "").lower()
            if kind and kind not in ACTOR_KINDS:
                errors.append(f"actor {actor.get('id')!r} uses unsupported kind {kind!r}")
        for node in proc.get("nodes") or []:
            nid = str(node.get("id") or "")
            all_node_ids.add(nid)
            if node.get("type") == "human":
                human_node_ids.add(nid)
            if node.get("type") in SERVICE_NODE_TYPES:
                service_node_ids.add(nid)
        for flow in proc.get("flows") or []:
            if flow.get("from") not in nodes_by_process[pname] or flow.get("to") not in nodes_by_process[pname]:
                errors.append(f"process {pname!r}: flow references an unknown node")

    for ledger in process.get("sentence_ledger") or []:
        for field_name in ("actors", "services", "gateways", "node_ids"):
            for ref in ledger.get(field_name) or []:
                valid = {
                    "actors": actor_ids,
                    "services": service_ids,
                    "gateways": gateway_ids,
                    "node_ids": all_node_ids,
                }[field_name]
                if ref not in valid:
                    errors.append(f"sentence ledger {ledger.get('id')!r}: unknown {field_name[:-1]} reference {ref!r}")

    for gateway in process.get("gateways") or []:
        decision = str(gateway.get("decision_variable") or "").strip()
        if decision and decision not in variable_ids:
            warnings.append(
                f"gateway {gateway.get('id')!r}: decision variable {decision!r} is not declared in data_contract.json"
            )

    coach_node_ids = set()
    for coach in contracts["coach"].get("coaches") or []:
        node_id = str(coach.get("node_id") or "").strip()
        coach_node_ids.add(node_id)
        if node_id not in all_node_ids:
            errors.append(f"coach {coach.get('id')!r}: node_id {node_id!r} does not exist")
        elif node_id not in human_node_ids:
            errors.append(f"coach {coach.get('id')!r}: node_id {node_id!r} is not a human node")
        view = coach.get("view") or {}
        if view.get("reusable") and not view.get("layout"):
            warnings.append(f"coach {coach.get('id')!r}: reusable view has no layout blueprint")
        if view.get("native_status") == "UNSUPPORTED":
            warnings.append(f"coach {coach.get('id')!r}: native reusable view serialization is UNSUPPORTED")

    missing_coaches = sorted(human_node_ids - coach_node_ids)
    if missing_coaches:
        warnings.append("Human nodes without a coach contract: " + ", ".join(missing_coaches))

    history = contracts["data"].get("comment_history") or {}
    if not history:
        warnings.append(
            "data_contract.json: shared comment_history contract is missing; every human Coach should reference the append-only history list"
        )
    else:
        if str(history.get("cardinality") or "").lower() != "list":
            warnings.append("data_contract.json: comment_history should have cardinality 'list'")
        history_fields = {
            str(field.get("name"))
            for field in history.get("fields") or []
            if isinstance(field, dict) and field.get("name")
        }
        required_history_fields = {
            "occurredAt", "fromActor", "toActor", "fromCoach", "toCoach", "action", "comment"
        }
        missing_history_fields = sorted(required_history_fields - history_fields)
        if missing_history_fields:
            warnings.append(
                "data_contract.json: comment_history is missing fields: " + ", ".join(missing_history_fields)
            )
    for coach in contracts["coach"].get("coaches") or []:
        history_view = coach.get("history_view") or (coach.get("view") or {}).get("history_table")
        if human_node_ids and not history_view:
            warnings.append(
                f"coach {coach.get('id')!r}: no shared read-only history-table binding declared"
            )

    service_node_refs = set()
    for service in contracts["service"].get("services") or []:
        node_id = str(service.get("node_id") or "").strip()
        service_node_refs.add(node_id)
        if node_id not in all_node_ids:
            errors.append(f"service {service.get('id')!r}: node_id {node_id!r} does not exist")
        elif node_id not in service_node_ids:
            warnings.append(f"service {service.get('id')!r}: node {node_id!r} is not typed as system/external/notification")
        endpoint = service.get("endpoint") or {}
        if str(endpoint.get("status") or "").upper() in {"MISSING", "PLACEHOLDER"}:
            warnings.append(f"service {service.get('id')!r}: endpoint is {str(endpoint.get('status')).upper()}")

    missing_service_nodes = sorted(service_node_ids - service_node_refs)
    if missing_service_nodes:
        warnings.append("Service nodes without a service contract: " + ", ".join(missing_service_nodes))

    for variable in contracts["data"].get("variables") or []:
        vtype = str(variable.get("type") or "String")
        if vtype not in PRIMITIVE_TYPES:
            bo_ref = variable.get("business_object") or variable.get("object_ref")
            suffix = f" (object {bo_ref})" if bo_ref else ""
            warnings.append(
                f"data variable {variable.get('id') or variable.get('name')!r} uses native object type {vtype!r}{suffix}; serializer support is UNSUPPORTED"
            )
        if variable.get("business_object") and variable.get("business_object") not in bo_ids:
            errors.append(
                f"data variable {variable.get('id') or variable.get('name')!r}: unknown business_object reference"
            )

    for bo in contracts["data"].get("business_objects") or []:
        mode = str(bo.get("mode") or "create").lower()
        if mode in {"create", "existing", "toolkit"}:
            warnings.append(
                f"business object {bo.get('id')!r} is preserved in the contract; native BO serialization must be validated before claiming support"
            )

    theme = application.get("theme") or {}
    if not theme:
        warnings.append("application_contract.json: theme contract is missing; default visual profile will be used")
    elif str(theme.get("native_status") or "").upper() == "UNSUPPORTED":
        warnings.append("application theme is portable-only; native self-contained theme packaging is UNSUPPORTED")

    return errors, warnings


def _merge_coaches(spec: dict, coach_contract: dict) -> None:
    by_node = {
        str(coach.get("node_id")): coach
        for coach in coach_contract.get("coaches") or []
        if isinstance(coach, dict)
    }
    views = []
    for process in spec.get("processes") or []:
        for node in process.get("nodes") or []:
            coach = by_node.get(str(node.get("id")))
            if not coach:
                continue
            for key in (
                "fields", "actions", "inputs", "outputs", "decision_output",
                "action_values", "return_comment", "history_view", "comment_channel",
            ):
                if key in coach:
                    node[key] = copy.deepcopy(coach[key])
            view = coach.get("view")
            if view:
                view_copy = copy.deepcopy(view)
                view_copy.setdefault("id", coach.get("id"))
                view_copy.setdefault("node_id", node.get("id"))
                views.append(view_copy)
    spec["coach_views"] = views


def _merge_services(spec: dict, service_contract: dict) -> None:
    by_node = {
        str(service.get("node_id")): service
        for service in service_contract.get("services") or []
        if isinstance(service, dict)
    }
    # Start with every descriptor so an unbound/placeholder service is not
    # silently dropped from the assembled handoff.
    integrations_by_id = {
        str(service.get("id")): copy.deepcopy(service)
        for service in service_contract.get("services") or []
        if isinstance(service, dict)
    }
    for process in spec.get("processes") or []:
        for node in process.get("nodes") or []:
            service = by_node.get(str(node.get("id")))
            if not service:
                continue
            kind = str(service.get("kind") or "system").lower()
            if kind in {"notification", "mail", "email"}:
                node["type"] = "notification"
            elif kind in {"external", "api", "soap"}:
                node["type"] = "external"
            else:
                node["type"] = "system"
            node["service_ref"] = service.get("id")
            service_id = str(service.get("id"))
            integrations_by_id.setdefault(service_id, copy.deepcopy(service))
            integrations_by_id[service_id].setdefault("node_refs", []).append(node.get("id"))
    spec["integrations"] = list(integrations_by_id.values())


def _default_theme_contract() -> dict:
    """Load the portable enterprise-burgundy visual profile when none was supplied."""
    profile_path = Path(__file__).resolve().parent.parent / "assets" / "enterprise-burgundy-theme.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "name": "enterprise-burgundy-theme",
            "native_status": "UNSUPPORTED",
            "status": "MISSING",
        }
    return {
        "name": profile.get("name", "enterprise-burgundy-theme"),
        "native_status": "UNSUPPORTED",
        "status": "PORTABLE_ONLY",
        "profile_path": str(profile_path),
        "profile": profile,
    }


def assemble_contract_bundle(
    contract_dir: Path,
    output_md: Optional[Path] = None,
    output_json: Optional[Path] = None,
) -> dict:
    contracts = load_contracts(contract_dir)
    errors, warnings = validate_contracts(contracts)
    if errors:
        raise ValueError("Contract bundle validation failed:\n- " + "\n- ".join(errors))

    application = contracts["application"]
    theme_contract = copy.deepcopy(application.get("theme") or {})
    if not theme_contract:
        theme_contract = _default_theme_contract()
        warnings.append("application theme was missing; the default portable visual profile was injected")

    spec = {
        "app": copy.deepcopy(application.get("app") or {}),
        "processes": copy.deepcopy(contracts["process"].get("processes") or []),
        "business_objects": copy.deepcopy(contracts["data"].get("business_objects") or []),
        "integrations": copy.deepcopy(contracts["service"].get("services") or []),
        "theme": theme_contract,
        "comment_history": copy.deepcopy(contracts["data"].get("comment_history") or {}),
        "dependencies": copy.deepcopy(application.get("dependencies") or []),
        "contract_bundle": {
            "version": "1.0",
            "source_directory": str(contract_dir),
            "files": list(CONTRACT_FILES.values()),
            "target_scenario": copy.deepcopy(contracts["process"].get("target_scenario") or {}),
            "actors": copy.deepcopy(contracts["process"].get("actors") or []),
            "gateways": copy.deepcopy(contracts["process"].get("gateways") or []),
            "sentence_ledger": copy.deepcopy(contracts["process"].get("sentence_ledger") or []),
            "warnings": warnings,
            "native_unsupported": copy.deepcopy(application.get("unsupported") or []),
        },
        "runtime_contract": copy.deepcopy(application.get("runtime") or {}),
        "data_mappings": copy.deepcopy(contracts["data"].get("mappings") or []),
    }

    process_variables = copy.deepcopy(contracts["data"].get("variables") or [])
    for process in spec["processes"]:
        existing = {str(v.get("name")): v for v in process.get("variables") or [] if isinstance(v, dict)}
        for variable in process_variables:
            name = str(variable.get("name") or "").strip()
            if not name:
                continue
            if name not in existing:
                existing[name] = copy.deepcopy(variable)
        process["variables"] = list(existing.values())

    _merge_coaches(spec, contracts["coach"])
    _merge_services(spec, contracts["service"])
    spec["contracts"] = {key: copy.deepcopy(value) for key, value in contracts.items()}

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(spec, indent=2, ensure_ascii=False)
        output_md.write_text(
            "# Assembled BAW Process Specification\n\n"
            "This file was assembled from the five BRD-to-BAW contracts.\n\n"
            "## BAW_GENERATOR_SPEC\n\n```json\n" + raw + "\n```\n",
            encoding="utf-8",
        )
    print(f"Contract bundle assembled from {contract_dir}")
    for warning in warnings:
        print(f"⚠️ {warning}")
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble five BRD-to-BAW contracts into BAW_GENERATOR_SPEC")
    parser.add_argument("contracts_dir", help="Directory containing the five *_contract.json files")
    parser.add_argument("--output-md", help="Write an assembled BAW_Process_Spec.md")
    parser.add_argument("--output-json", help="Write the assembled specification JSON")
    args = parser.parse_args()
    assemble_contract_bundle(
        Path(args.contracts_dir),
        Path(args.output_md) if args.output_md else None,
        Path(args.output_json) if args.output_json else None,
    )


if __name__ == "__main__":
    main()
