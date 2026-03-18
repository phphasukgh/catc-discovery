# CATC Discovery

CLI utility for running Cisco Catalyst Center (CATC) discovery jobs from CSV input, monitoring task completion, exporting discovery results, and optionally handling IP-conflict rediscovery.

## What It Does

- Creates CATC discovery jobs from a CSV file.
- Polls CATC task status until each discovery job finishes.
- Polls discovery status until each successful discovery completes.
- Exports task and discovery results to CSV files.
- Optionally deletes previously discovered devices that caused IP conflicts, then runs a targeted rediscovery for those IPs.
- Supports assigning devices to sites from CSV input.
- Supports deleting all discovery jobs from CATC.

## Repository Layout

- `catc_discovery.py`: Main CLI entry point.
- `catc_config.py`: CATC controller connection target.
- `shared_utils/`: Reusable CATC REST client, logging, and CSV utilities.
- `logs/`: Runtime log output.

## Project Structure

```text
catc-discovery/
|-- catc_config.py
|-- catc_discovery.py
|-- discovery_data.csv
|-- discovery_result.csv
|-- discovery_result_rediscovery.csv
|-- task_result.csv
|-- task_result_rediscovery.csv
|-- README.md
|-- logs/
|   `-- application_run.log
`-- shared_utils/
  |-- catc_restapi_lib.py
  |-- CHANGELOG.md
  |-- log_setup.py
  |-- MIGRATION_GUIDE.md
  |-- README.md
  `-- util.py
```

## Requirements

- Python 3.10 or newer recommended.
- Network connectivity to Cisco Catalyst Center.
- A CATC user account with permissions for discovery, device delete, and site assignment as needed.
- Python packages:
  - `requests`
  - `urllib3`

Install dependencies:

```bash
pip install requests urllib3
```

## Configuration

The target CATC controller is configured in `catc_config.py`:

```python
CATC_IP = '10.122.21.37'
CATC_PORT = 443
```

Update these values before running the tool against a different environment.

Credentials are not stored in the repository. The script prompts for:

- `Username`
- `Password`

## Usage

```bash
python catc_discovery.py --help
```

```text
usage: catc_discovery.py [-h] [--file FILE] [--mode MODE]
                         [--remove_old_device_with_ip_conflict]
```

Arguments:

- `--mode`: Operation mode. Supported values: `add`, `delete`, `assign`.
- `--file`: Input CSV file for `add` and `assign` modes.
- `--remove_old_device_with_ip_conflict`: In `add` mode, deletes conflicting devices and starts rediscovery for affected IPs.

## Modes

### 1. Add Discovery Jobs

Creates discovery jobs from a CSV file, waits for task completion, waits for discovery completion, and writes result CSVs.

Example:

```bash
python catc_discovery.py --mode add --file discovery_data.csv
```

With IP-conflict cleanup and rediscovery:

```bash
python catc_discovery.py --mode add --file discovery_data.csv --remove_old_device_with_ip_conflict
```

Expected CSV columns for discovery input are based on the payload expected by the CATC discovery API. The sample file in this repository uses:

```csv
No,name,discoveryType,enablePasswordList,ipAddressList,passwordList,snmpAuthPassphrase,snmpAuthProtocol,snmpMode,snmpPrivPassphrase,snmpPrivProtocol,snmpROCommunity,snmpRWCommunity,snmpVersion,userNameList,preferredMgmtIPMethod
1,Edge,MULTI RANGE,<ENABLE_PASSWORD>,10.30.200.4-10.30.200.6,<DEVICE_LOGIN_PASSWORD>,<SNMP_AUTH_PASSPHRASE>,,,<SNMP_PRIV_PASSPHRASE>,,<SNMP_RO_COMMUNITY>,<SNMP_RW_COMMUNITY>,v2,<DEVICE_USERNAME>,None
```

Credential fields in this CSV format are:

- `enablePasswordList`
- `passwordList`
- `snmpAuthPassphrase`
- `snmpPrivPassphrase`
- `snmpROCommunity`
- `snmpRWCommunity`
- `userNameList`

Notes:

- The script reads the CSV as-is and passes each row to `add_discovery_node`.
- Column names must match what the CATC API client expects.
- The first CSV column can be an index such as `No`; it is not used directly by the script logic.

### 2. Delete All Discoveries

Deletes all discovery jobs from CATC.

Example:

```bash
python catc_discovery.py --mode delete
```

### 3. Assign Devices to Sites

Reads device IP and site name from CSV, resolves each site ID, assigns the device to that site, and writes `assign_site_result.csv`.

Example:

```bash
python catc_discovery.py --mode assign --file assign_data.csv
```

Expected CSV columns:

```csv
ip,site
10.30.200.4,Global/USA/SanJose/HQ
```

## Output Files

The script generates these files in the repository root:

- `task_result.csv`: Discovery task status for the main run.
- `discovery_result.csv`: Summary and per-device discovery results for the main run.
- `task_result_rediscovery.csv`: Task status for rediscovery jobs created from IP-conflict handling.
- `discovery_result_rediscovery.csv`: Rediscovery summary and per-device detail rows.
- `assign_site_result.csv`: Results for site assignment mode.
- `logs/application_run.log`: Rotating application log.

### task_result.csv

Columns:

```csv
id,Name,taskId,taskResult,failureReason
```

### discovery_result.csv

The discovery export contains two row types:

- `SUMMARY`: One row per discovery job.
- `DETAIL`: One row per discovered device returned by CATC.

Columns:

```csv
id,rowType,Name,discId,taskResult,IpAddress,Status,ping,snmp,cli,http,netconf,invCollection,invReachability,deviceHostname,deviceId,errorCode,errorParamCode,errorParams
```

## API Endpoints Used By This Program

This section includes only APIs used by `catc_discovery.py` through `shared_utils/catc_restapi_lib.py`.

Primary API documentation pointer:

- Cisco Catalyst Center API docs: https://developer.cisco.com/docs/catalyst-center/2-3-7-9/

Used endpoints:

| Program flow | Client method | HTTP | Endpoint |
| --- | --- | --- | --- |
| Login during client initialization | `get_token` | POST | `/dna/system/api/v1/auth/token` |
| Logout at end of mode execution | `logout` | GET | `/logout?nocache` |
| Add discovery jobs (`add` mode) | `add_discovery_node` | POST | `/dna/intent/api/v1/discovery` |
| Poll discovery task status (`add` + rediscovery) | `get_task_info` | GET | `/dna/intent/api/v1/task/{tid}` |
| Check discovery job status (`add` + rediscovery) | `get_discovery_info` | GET | `/dna/intent/api/v1/discovery/{did}` |
| Fetch discovered devices (`add` + rediscovery) | `get_discovery_result` | GET | `/dna/intent/api/v1/discovery/{did}/network-device` |
| Delete conflicting inventory device (`add` with conflict cleanup) | `delete_device_by_id` | DELETE | `/dna/intent/api/v1/network-device/{did}` |
| Delete all discoveries (`delete` mode) | `delete_alldiscovery` | DELETE | `/dna/intent/api/v1/discovery` |
| Resolve site ID by hierarchy (`assign` mode) | `get_siteid_by_name` | GET | `/dna/intent/api/v2/site` |
| Assign device to site (`assign` mode) | `assign_device_to_site` | POST | `/dna/system/api/v1/site/{site_id}/device` |
| Poll assignment execution status (`assign` mode) | `assign_device_to_site` | GET | Dynamic `executionStatusUrl` returned by assignment API |

Notes:

- `get_task_info` and `assign_device_to_site` are marked as deprecated in the client library but are still used by this script.
- Newer APIs are available and documented in Cisco Catalyst Center API docs:
  - Task API (newer than `/dna/intent/api/v1/task/{tid}`): `/dna/intent/api/v1/tasks/{task_id}`
  - Site assignment API (newer than `/dna/system/api/v1/site/{site_id}/device`): `/dna/intent/api/v1/networkDevices/assignToSite/apply`
  - Reference: https://developer.cisco.com/docs/catalyst-center/2-3-7-9/
- Migrating this script to the newer APIs may require flow changes (request/response handling, task tracking, and status polling behavior) and should be followed by full regression testing.
- The assignment status polling endpoint is dynamic because the API returns a full execution status path per request.

## IP Conflict Handling

When `--remove_old_device_with_ip_conflict` is enabled during `add` mode, the script:

1. Parses discovery detail results for conflict-related error information.
2. Detects IP-conflict cases from `errorCode`, parsed error metadata, or error text.
3. Deletes the existing CATC device record associated with each conflicting IP.
4. Builds a targeted rediscovery payload for each affected IP.
5. Runs rediscovery and writes separate rediscovery CSV outputs.

This is useful when CATC already has a stale device record that prevents a clean rediscovery of the same management IP.

## Logging

Runtime logs are written to `logs/application_run.log` using a rotating file handler.

Current logging behavior:

- File logging enabled.
- Console logging disabled.
- Max log file size set to 50 MB.

## Example Workflow

1. Update `catc_config.py` with the CATC IP and port.
2. Prepare `discovery_data.csv` with the discovery parameters required by your CATC environment.
3. Run:

```bash
python catc_discovery.py --mode add --file discovery_data.csv
```

4. Enter CATC credentials when prompted.
5. Review:

- `task_result.csv`
- `discovery_result.csv`
- `logs/application_run.log`

If discovery fails because of stale device records with duplicate IPs, rerun with:

```bash
python catc_discovery.py --mode add --file discovery_data.csv --remove_old_device_with_ip_conflict
```

## Limitations

- The script prompts interactively for credentials, which makes non-interactive automation harder.
- Input CSV validation is minimal; malformed or incomplete rows will fail in downstream CATC API calls.
- `delete` mode deletes all discoveries through the shared CATC client method. Use carefully.

## Related Files

- `shared_utils/README.md`: Documentation for the shared CATC utility library.
- `shared_utils/MIGRATION_GUIDE.md`: Notes about the newer CATC client library naming and usage.

## License

Copyright (c) 2021–2026 Cisco and/or its affiliates.

Licensed under the Cisco Sample Code License, Version 1.1.

License information: https://developer.cisco.com/docs/licenses
