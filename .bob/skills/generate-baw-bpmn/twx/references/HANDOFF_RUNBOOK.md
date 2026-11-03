# IBM BAW TWX handoff runbook

## Install and configure

The scripts use only the Python standard library. No credentials are needed to generate a TWX; importing is done by the user in Workflow Center.

## Mandatory gates

1. BRD to process specification and SVG.
2. User approves the flow.
3. Generate and locally validate the TWX.
4. User imports the TWX into BAW (Workflow Center) and checks BAW validation.
5. (Reserved: server deployment is handled by `baw-deployment-manager`, not this skill.)
6. When requested, perform a real runtime test.

Never merge gates 2 and 3. A valid import is not evidence that Coaches, mappings, and routes work at runtime.

## Commands

Discover the generator interface before running it:

```bash
python3 scripts/baw_twx_generator.py --help
```

Generate using the approved process specification and validate the resulting archive with the generator's `--validate` option. Theme-enabled generation produces one process-app TWX containing its generated Theme toolkit snapshot under `toolkits/`.

## Runtime checklist

- Open the Process App in Web Process Designer and confirm zero validation errors and warnings.
- Start a new process instance rather than relying on an old claimed task.
- Open each Coach; fill required fields and exercise validation.
- Confirm input values reach the human service and output values return to BPD variables.
- Exercise every gateway outcome, rejection/rework route, integration stub, and terminal event.
- Confirm the instance completes and no new severe messages or FFDC records appear.

## Log collection

Common Traditional BAW locations on the Windows VM are:

```text
C:\IBM\Workflow\v22.0\profiles\Node1Profile\logs\SingleClusterMember1\SystemOut.log
C:\IBM\Workflow\v22.0\profiles\Node1Profile\logs\ffdc\
```

Zip logs on the VM before transferring them through RDP. Directly copied live logs can arrive as zero-filled placeholders.

Useful signatures:

- `Mix of legacy and graphical mappings`: an activity mixes incompatible mapping styles.
- A missing human-service input at runtime: inspect the native input mapping structure below.
- `Coach views require a theme ... does not have a theme set`: first open
  Process App Settings and verify the Theme reference. If the Theme is already
  selected, verify that it belongs to an installed toolkit dependency rather
  than only to the process app, then open that Theme's Design preview. A LESS error such as
  `variable @bpm-border-normal is undefined` at `.patch-spark-vars()` means the
  embedded Theme source is incomplete, not that the selection is absent.
  Regenerate with the complete
  `assets/enterprise-burgundy-baw-8.6.11-theme.less` contract; do not patch only the
  first missing variable. If the Theme compiles but runtime still shows the
  banner, regenerate the self-contained process-app TWX and verify it contains
  the matching `toolkits/<snapshot-id>.zip` entry.
- `CWLLG0380I`: import completed; this does not prove runtime correctness.
- Missing `noDrop.gif`: usually harmless UI noise.
- `BasicEventPointImpl`: collect the associated FFDC record; the summary alone is insufficient.

## VM discovery checklist

The exact path depends on whether the bank runs Traditional BAW on WebSphere
Application Server or BAW on containers. Do not assume that the path on one
bank's VM applies to another bank.

### Traditional BAW on a Linux/UNIX VM

For a WebSphere profile root, the normal runtime paths are:

```text
<profile_root>/logs/<server_name>/SystemOut.log
<profile_root>/logs/<server_name>/SystemErr.log
<profile_root>/logs/<server_name>/trace.log       # only when tracing is enabled
<profile_root>/logs/ffdc/
```

The deployment manager is commonly `dmgr`; managed nodes commonly contain
`nodeagent` and one or more application-server directories. The installation
root is not fixed, so discover it rather than hard-coding `/opt/IBM`:

```bash
printf 'WAS_HOME=%s\n' "${WAS_HOME:-unset}"
ps -ef | grep -E '[d]mgr|[n]odeagent|[s]erver1|[B]PM|[B]AW'
find /opt /usr/local /usr/IBM -type f \( -name SystemOut.log -o -name SystemErr.log -o -name trace.log \) 2>/dev/null
find /opt /usr/local /usr/IBM -type d -name ffdc 2>/dev/null
```

If those roots are not used, run the same `find` command from the approved
product mount. Collect the server log, the matching FFDC files, the timestamp,
server name, profile name, and the exact failing request. Do not copy active
logs while they are being rotated if a sanitized archive can be produced by
the administrator.

### BAW on containers/OpenShift

There may be no WebSphere `SystemOut.log` on the VM host. The log belongs to a
Workflow Server pod and is normally collected with the cluster tooling, for
example:

```bash
oc get pods -n <namespace>
oc logs -n <namespace> <workflow-server-pod> --since=2h > workflow-server.log
oc logs -n <namespace> <workflow-server-pod> --previous > workflow-server-previous.log
```

Use the bank's namespace, pod, and retention policy. Do not read or modify a
BAW PVC directly. IBM documents the container JDBC/driver filestore as a PVC
mounted inside the pod at `/opt/ibm/bawfile`; that is not the same thing as a
host filesystem path.

### Where BAW artifacts and documents live

Process applications, toolkits, services, Coaches, and snapshots are stored
in the Workflow Center repository. A downloaded `.twx` is only an export
archive; there is no supported “BAW documents folder” to edit on the VM.
Runtime process variables and attachments are persisted according to the
configured BAW database/content repository. FileNet/Content Platform Engine
attachments are stored in the configured content repository/object store, not
inside the TWX archive. Use Workflow Center, Process Designer, Admin Console,
BAW REST APIs, or the content repository tools to inspect them; never edit the
repository database or server files directly.

### How to locate the database configuration safely

BAW normally uses an external supported database (for example Db2, Oracle,
SQL Server, or PostgreSQL, depending on release/topology). Ask the BAW
administrator for the Process, Common, and Performance Data Warehouse
database names and owners. On Traditional BAW, inspect the WebSphere JDBC
data sources or export the BAW configuration with the administrator's
approved `BPMConfig -export` procedure. On containers, inspect the BAW custom
resource and referenced database Secret. Record only host, port, database
name/schema, vendor, and driver version; redact usernames, passwords, tokens,
and full connection secrets.

```bash
find /opt /usr/local /usr/IBM -type f \( -name resources.xml -o -name server.xml -o -name 100Custom.xml \) 2>/dev/null
grep -R -n -E 'jdbc:|JDBCProvider|dataSource|TeamworksDB|PerformanceDB' /opt/IBM /opt/WebSphere /opt/bpm 2>/dev/null
```

The database is not a substitute for the Workflow Center UI: database tables
are an implementation detail and direct SQL updates can corrupt process
state. Use SQL only for read-only diagnostics under the bank's change and
security controls.

## Native mapping templates

Input mapping:

```xml
<mapping>
  <name>customerCIF</name>
  <classId>SYSDATA_DEP_UUID/12.PRIMITIVE_UUID</classId>
  <input>true</input>
  <value>tw.local.customerCIF</value>
  <parameterId>HUMAN_SERVICE_INPUT_PARAMETER_ID</parameterId>
</mapping>
```

Do not use the obsolete input shape `expression` plus `activityParameterId`.

Output mapping:

```xml
<mapping>
  <activityParameterId>HUMAN_SERVICE_OUTPUT_PARAMETER_ID</activityParameterId>
  <location>tw.local.approved</location>
  <variableId>BPD_PRIVATE_VARIABLE_ID</variableId>
</mapping>
```
