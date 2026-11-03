# IBM® Business Automation Workflow Skills and Bob Modes

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

A growing collection of skills and IBM Bob modes that accelerate development with IBM Business Automation Workflow.

## IBM public repository disclosure

All content in this repository including code has been provided by IBM under the associated open source software license and IBM is under no obligation to provide enhancements, updates, or support. IBM developers produced this code as an open source project (not as an IBM product), and IBM makes no assertions as to the level of quality nor security, and will not be maintaining this code going forward.

## Table of contents

- [Overview](#overview)
- [Concepts](#concepts)
- [HDB customizations](#hdb-customizations)
- [Prerequisites](#prerequisites)
- [Getting started (no installer)](#getting-started-no-installer)
- [BAW credentials and configuration](#baw-credentials-and-configuration)
- [Using with another AI agent](#using-with-another-ai-agent)
- [Available modes](#available-modes)
- [Available skills](#available-skills)
- [License](#license)

## Overview

This repository provides ready-to-use Bob modes and skills that accelerate IBM Business Automation Workflow (BAW) development across a range of tasks. It works with:

- [IBM Business Automation Workflow](https://www.ibm.com/products/business-automation-workflow)
- [IBM® Cloud Pak® for Business Automation (CP4BA)](https://www.ibm.com/products/cloud-pak-for-business-automation)

## Concepts

### What is Bob?

[IBM Bob](https://bob.ibm.com/) is an AI coding assistant and agent framework. This repository extends Bob with BAW-specific modes and skills.

### Modes

A **mode** shapes how Bob approaches a task — its role, expertise, and which skills it reaches for. Both modes are defined in `.bob/custom_modes.yaml`, which Bob loads automatically when you open this repository.

### Skills

A **skill** is a focused instruction set that gives Bob a specific capability. Each skill lives in its own folder under `.bob/skills/` with a `SKILL.md` that tells Bob what to do, what inputs to expect, and how to respond. Some skills also include helper scripts that Bob can run as part of the workflow.

## HDB customizations

This is the HDB-customized copy of the IBM BAW skills and Bob modes. Changes from upstream:

- `generate-baw-bpmn` now has a second output option, **TWX with Coaches**, that builds a native process app `.twx` with human services (separate from the process, not inline), Coaches, and a theme. See [`.bob/skills/generate-baw-bpmn/twx/TWX_WORKFLOW.md`](.bob/skills/generate-baw-bpmn/twx/TWX_WORKFLOW.md) and the working example in [`twx/examples/minimal-contracts/`](.bob/skills/generate-baw-bpmn/twx/examples/minimal-contracts/).
- The `IBM BAW Author` mode mentions the TWX option.
- **Version status:** the TWX option was validated on Traditional BAW 8.6.11 only. **BAW 24.0.x is untested.** Import generated TWX files into a development environment first and report the result. The BPMN + zip option and the other skills are labelled 22.x and later.
- The skills and modes live in `.bob/` so that **no installer is needed**.

## Prerequisites

- [IBM Bob](https://bob.ibm.com/) installed and signed in
- Git, to clone and update this repository
- Python 3 (standard library only) for `generate-baw-bpmn`, including the TWX option. A few other skills need `pyyaml` and `lxml`; those are listed in each skill's `SKILL.md`
- Any other skill-specific prerequisites are noted in the skill's `SKILL.md`

## Getting started (no installer)

Skills and modes are loaded from the `.bob/` folder of the project you open, so there is nothing to install.

1. Clone the repository:
   ```bash
   git clone <your-internal-repo-url> baw-bob
   cd baw-bob
   ```
2. Open the `baw-bob` folder **as the workspace** in Bob (File > Open Folder). Bob must be opened on the repository root so it finds `.bob/`.
3. Reload the Bob window.
4. Pick **IBM BAW Author** or **IBM BAW Admin** from the mode selector to the left of the chat input. The selector is hidden while a task is running; start a new chat if you do not see it.
5. Make a natural-language request. You do not need to name a skill. For example:

   > "Generate a TWX with Coaches for a leave request process."

6. If you work in a different project folder, copy `.bob/skills/` and `.bob/custom_modes.yaml` into that project's `.bob/`. If that project already has a `.bob/custom_modes.yaml`, add the two mode entries to it instead of overwriting.

> **Settings page note:** Settings > Skills may not list project skills immediately. Close and reopen the Settings tab, or reload the window. The skills still work.

### Updating

```bash
git pull
```

then reload the Bob window.

### Do not use global scope by accident

Skills in `~/.bob/skills/` on a machine are separate from this repository. If a same-named skill exists in both places, Bob uses the project-level one. If you see old behavior, check `~/.bob/skills/` for stale copies.

## BAW credentials and configuration

Several skills connect to a live BAW environment through the REST API. Skills read these values from a `.env` file in the workspace. The offline skills (for example `baw-project-doc`, `review-baw-code`, `generate-baw-bpmn` including the TWX option) do not need it.

1. Copy `.env.example` to `.env` in the repository root.
2. Fill in the three values:

| Variable | Description |
|---|---|
| `BAW_BASE_URL` | Base URL of your BAW server, no trailing slash (for example `https://baw.example.com:9443`; for CP4BA authoring `https://cpd.example.com/bas`) |
| `BAW_USERNAME` | A BAW account with the permissions the task needs |
| `BAW_PASSWORD` | Password for that account |

### Credential security

- **Never commit `.env`.** It is in `.gitignore`. If it was staged by mistake, run `git rm --cached .env`.
- Use a least-privilege account, and a separate one per environment.
- Do not paste passwords into chat or hard-code them in scripts or skill files.

## Using with another AI agent

Skills are plain folders, so another agent can use them by copying `.bob/skills/*` into the directory that agent reads (for example `~/.claude/skills/`). Skills that connect to BAW read credentials from `.env` using shell commands, so the agent must be able to run them.

## Available modes

| Mode | Description |
|---|---|
| [`IBM BAW Author`](.bob/custom_modes.yaml) | Full IBM BAW expert covering process authoring, BPEL-to-BPMN conversion, coach view development, service flow design, artifact analysis, and documentation. |
| [`IBM BAW Admin`](.bob/custom_modes.yaml) | IBM BAW operations and administration assistant. Monitor, inspect, and act on running process instances — find failed/stuck/overdue/broken processes, retry, suspend, resume, terminate, or change due dates. Administer the BAW environment: deployments, snapshots, environment variables, containers, and health. Troubleshoot failures from runtime error logs, compare application versions across deployments, and assess process applications for audit readiness and compliance. |

### Required skills per mode

Each mode relies on specific skills that must be present in your `.bob/skills/` folder. If a skill is missing, the mode will not be able to perform the associated function. When a missing skill is needed, the mode will tell you which skill to install and where to copy it from.

#### IBM BAW Author

| Skill | Source path in this repository | Purpose |
|---|---|---|
| `generate-baw-bpmn` | `.bob/skills/generate-baw-bpmn/` | Generate BPMN 2.0 XML importable into BAW, or a process app TWX with Coaches |
| `generate-baw-business-objects` | `.bob/skills/generate-baw-business-objects/` | Generate BAW Business Object import files |
| `baw-project-doc` | `.bob/skills/baw-project-doc/` | Generate documentation from a TWX or BPMN + XSD |
| `generate-baw-tests` | `.bob/skills/generate-baw-tests/` | Generate and execute automated test suites |
| `test-baw-service-flows` | `.bob/skills/test-baw-service-flows/` | Generate and run test suites for Service Flows against a live environment |
| `review-baw-code` | `.bob/skills/review-baw-code/` | Code quality reviews of BAW JS, HTML, and CSS artifacts |
| `create-baw-portal` | `.bob/skills/create-baw-portal/` | Build or adapt custom BAW task portals |
| `create-baw-widget` | `.bob/skills/create-baw-widget/` | Scaffold, author, and package custom Coach View widgets into importable .twx toolkit files |
| `create-baw-external-task-ui` | `.bob/skills/create-baw-external-task-ui/` | Generate a React + Express external task UI for BAW Custom URL human tasks |
| `compare-baw-versions` | `.bob/skills/compare-baw-versions/` | Diff two snapshots or branches |
| `audit-baw-readiness` | `.bob/skills/audit-baw-readiness/` | Score a process app against compliance domains |
| `baw-dependency-mapper` | `.bob/skills/baw-dependency-mapper/` | Map BO and variable dependencies across a TWX |
| `baw-toolkit-analyzer` | `.bob/skills/baw-toolkit-analyzer/` | Analyze toolkit dependencies and upgrade impact from a TWX |
| `baw-endpoint-validation` | `.bob/skills/baw-endpoint-validation/` | Validate TWX endpoints before a server migration |
| `baw-export-import-helper` | `.bob/skills/baw-export-import-helper/` | Migrate process apps and toolkits between environments in the correct import order |
| `process-compliance-violation-detection` | `.bob/skills/process-compliance-violation-detection/` | Evaluate a process app against compliance documents |

#### IBM BAW Admin

| Skill | Source path in this repository | Purpose |
|---|---|---|
| `inspect-baw-processes` | `.bob/skills/inspect-baw-processes/` | Find, inspect, and act on running process instances |
| `troubleshoot-baw-logs` | `.bob/skills/troubleshoot-baw-logs/` | Diagnose runtime failures from BAW error logs |
| `compare-baw-versions` | `.bob/skills/compare-baw-versions/` | Diff two snapshots or branches |
| `audit-baw-readiness` | `.bob/skills/audit-baw-readiness/` | Score a process app against compliance domains |
| `version-lifecycle-manager` | `.bob/skills/version-lifecycle-manager/` | Activate, deactivate, delete snapshots; manage env vars |
| `version-inspector` | `.bob/skills/version-inspector/` | Browse containers and inspect snapshot metadata |
| `baw-container-inventory` | `.bob/skills/baw-container-inventory/` | List all Process Apps and Toolkits on a BAW server |
| `baw-deployment-manager` | `.bob/skills/baw-deployment-manager/` | Install and monitor snapshot deployments |
| `baw-endpoint-validation` | `.bob/skills/baw-endpoint-validation/` | Validate TWX endpoints before a server migration |

## Available skills

### Authoring

*Creating artifacts, generating documentation, and reviewing code quality and compliance.*

| Skill | Description |
|---|---|
| [`generate-baw-bpmn`](.bob/skills/generate-baw-bpmn/) | Generates BPMN 2.0 XML that imports cleanly into IBM BAW — processes and complex business object variables — from a process description, requirements doc, SOP, or existing config JSON. Also offers a TWX output option that builds a native process app with human services and Coaches from a BRD. |
| [`generate-baw-business-objects`](.bob/skills/generate-baw-business-objects/) | Generates and modifies BAW Business Object import files — valid OpenAPI 3.0 JSON that IBM BAW WebPD imports via the "Import business objects" option in the Data menu. |
| [`generate-baw-tests`](.bob/skills/generate-baw-tests/) | Generates and executes automated tests for an IBM BAW process app, case application, or service flow — covering happy paths, alternative paths, edge cases, and Coach UI validation across two phases: test suite generation (Phase A) and end-to-end MCP execution (Phase B). |
| [`test-baw-service-flows`](.bob/skills/test-baw-service-flows/) | Generates and executes automated test suites for IBM BAW Service Flows against live BAW and CP4BA environments. Discovers the service flow, reads its input/output contract, and produces structured test cases covering happy path, error paths, and boundary conditions — then invokes the service and returns a structured pass/fail report. |
| [`create-baw-portal`](.bob/skills/create-baw-portal/) | Provides API knowledge and portal development guidance for IBM BAW. Guides developers on which BAW REST APIs to use for portal builds, covering authentication, CORS, XSRF, pagination, and proxy configuration. Supports non-federated (WLE REST) and federated (PFS) environments. |
| [`baw-project-doc`](.bob/skills/baw-project-doc/) | Generates comprehensive, up-to-date documentation for IBM BAW applications by analyzing process models, services, integrations, business objects, and application artifacts — accepts a TWX export, a BPMN + XSD pair, or a ZIP archive. No MCP server or live server connection required. |
| [`baw-dependency-mapper`](.bob/skills/baw-dependency-mapper/) | Maps all usages and dependencies of a specified variable or Business Object (BO) across an entire IBM BAW process application by analyzing the TWX export. Produces a dependency graph showing declarations, read/write usages, service I/O bindings, and coach bindings; detects circular BO references, redundant service calls, and over-coupling. |
| [`compare-baw-versions`](.bob/skills/compare-baw-versions/) | Compares two versions (snapshots or branches) of an IBM BAW process application. Exports both and produces a structured diff by artifact type — process steps, gateways, variables, business objects, services, scripts, and configuration — flagging artifacts modified in both versions as conflict hints. |
| [`review-baw-code`](.bob/skills/review-baw-code/) | Performs automated, severity-ranked code quality reviews across IBM BAW artifacts — server scripts, coach scripts, integration service scripts, HTML, and CSS. Flags hardcoded values, undeclared variables, inconsistent error-logging patterns, synchronous `Thread.sleep` calls, unbounded loops, and other performance anti-patterns. Each finding includes the artifact name, location, rule violated, severity, and a recommended fix. |
| [`audit-baw-readiness`](.bob/skills/audit-baw-readiness/) | Evaluates an IBM BAW process application's design for compliance and audit readiness — scores six domains (traceability, separation of duties, access control, SLA/timeliness, data completeness, error handling) and produces a Markdown scorecard with specific gaps and remediation steps. |
| [`process-compliance-violation-detection`](.bob/skills/process-compliance-violation-detection/) | Evaluates IBM BAW and CP4BA process applications against compliance, governance, regulatory, business policy, architecture, or standards documents. Detects violations, gaps, risks, and missing controls, then recommends remediation using documented BAW/CP4BA platform capabilities. |
| [`create-baw-widget`](.bob/skills/create-baw-widget/) | Scaffolds, authors, and packages custom Coach View widgets for IBM BAW and CP4BA. Creates the full widget folder structure (Layout.html, InlineCSS.css, inlineJavascript.js, config.json, business objects, event handlers, and AdvancePreview files), then packages them into an importable `.twx` toolkit file using the bundled Python packaging toolkit. |
| [`create-baw-external-task-ui`](.bob/skills/create-baw-external-task-ui/) | Generates a custom external task UI for an IBM BAW human task configured with a Custom URL — a Node.js Express server with a React (default) or user-specified frontend, styled with Carbon, that fetches task data from the BAW `/bpm/user-tasks` REST API and completes the task on submission. Accepts a verbal field description or an exported task schema file, and includes instructions for exporting the schema and setting the External Implementation URL with `{tw.system.task_id}`. |
| [`baw-toolkit-analyzer`](.bob/skills/baw-toolkit-analyzer/) | Analyzes IBM BAW toolkit dependencies from a TWX export. Maps direct and transitive toolkit dependencies, tracks snapshot versions, and flags missing, conflicting, circular, outdated, and unused dependencies. Supports where-used and what-uses analysis to assess upgrade impact before deployment. |

### Administration and Operations

*Deploying and configuring environments, managing snapshot lifecycles, and inspecting runtime health.*

| Skill | Description |
|---|---|
| [`baw-deployment-manager`](.bob/skills/baw-deployment-manager/) | Deploys IBM BAW Process App and Toolkit snapshots to workflow environments via the REST API — lists available process apps, toolkits, snapshots, and servers, then installs and monitors deployment progress. Supports BAW on-premises, BAW on Cloud, and CP4BA. |
| [`version-lifecycle-manager`](.bob/skills/version-lifecycle-manager/) | Manages IBM BAW Process App and Toolkit version lifecycle via the Operations REST API — installing apps, activating, deactivating, and deleting snapshots, and reading, setting, and syncing environment variables — no Process Admin Console needed. Supports BAW on-premises, BAW on Cloud, and CP4BA. |
| [`baw-endpoint-validation`](.bob/skills/baw-endpoint-validation/) | Identifies what needs to change when an IBM BAW process application is installed on a new server. Reads BPMConfig properties files to extract source and target endpoints, scans the TWX export for hardcoded references to the old server, and generates a validation report of findings. |
| [`inspect-baw-processes`](.bob/skills/inspect-baw-processes/) | Finds, investigates, and acts on running IBM BAW process instances — retry failed processes, suspend or resume instances, change due dates, drill into business data and task history. Covers the full Process Inspector workflow searching by status, app, owner, and date. |
| [`troubleshoot-baw-logs`](.bob/skills/troubleshoot-baw-logs/) | Diagnoses IBM BAW runtime failures by analyzing error logs, stack traces, and FFDC files. Identifies root causes, correlates entries across log types, and provides structured remediation steps for errors found in `SystemOut.log`, `messages.log`, `trace.log`, and Liberty FFDC files. |
| [`version-inspector`](.bob/skills/version-inspector/) | Inspects IBM BAW snapshots and browses deployed containers. Retrieves a plain-language metadata summary — version name, lifecycle status, creation date, and toolkit dependencies — for a specific snapshot. Also lists all Process Apps and Toolkits when the user does not know which container or snapshot to inspect. Works for Process Apps and Toolkits on BAW on-premises, BAW on Cloud, and CP4BA. |
| [`baw-container-inventory`](.bob/skills/baw-container-inventory/) | Inspects the container inventory of a live IBM BAW server — lists, counts, and searches Process Apps and Toolkits by name or acronym, shows container metadata, and confirms whether a specific container exists. Read-only; no Workflow Center or Business Automation Studio needed. |
| [`baw-export-import-helper`](.bob/skills/baw-export-import-helper/) | Migrates IBM BAW and CP4BA Process Apps, toolkits, case solutions, and Business Applications between environments, automatically resolving toolkit dependencies and determining the correct import order. Supports environment promotion (dev → test → prod), consolidation, and disaster recovery restores. |

## License

This project is licensed under the [Apache License 2.0](LICENSE).
