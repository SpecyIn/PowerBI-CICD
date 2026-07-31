import os
import time
import logging
import requests
from requests.exceptions import RequestException

try:
    import yaml
except ImportError:
    yaml = None

try:
    from azure.identity import ClientSecretCredential
except ImportError:
    ClientSecretCredential = None

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
BACKOFF_MAX = 30
CLOUD_GATEWAY_ID = "00000000-0000-0000-0000-000000000000"


def simple_yaml_load(text: str):
    """Fallback basic stack-based YAML parser for gateway-binding.yml if PyYAML is not installed."""
    result = []
    current_item = None
    stack = []  # list of (indent, dict_ref)

    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        indent = len(line) - len(line.lstrip(' '))

        # Handle top-level list item e.g., - model-name: "CaPex_KPI_SM_Gateway_Test"
        if stripped.startswith('-'):
            item_content = stripped[1:].strip()
            current_item = {}
            result.append(current_item)
            stack = [(indent, current_item)]

            if ':' in item_content:
                parts = item_content.split(':', 1)
                k = parts[0].strip().strip('"\'')
                v = parts[1].strip().strip('"\'')
                if k:
                    current_item[k] = v
            continue

        if ':' in line:
            parts = line.split(':', 1)
            key = parts[0].strip().strip('"\'')
            val = parts[1].strip().strip('"\'')

            while stack and stack[-1][0] >= indent:
                stack.pop()

            parent_dict = stack[-1][1] if stack else current_item
            if parent_dict is None:
                parent_dict = {}
                current_item = parent_dict
                result.append(current_item)
                stack = [(indent, parent_dict)]

            if val == '':
                new_dict = {}
                parent_dict[key] = new_dict
                stack.append((indent, new_dict))
            else:
                parent_dict[key] = val

    return result


def parse_yaml_file(file_path: str):
    """Load YAML content using PyYAML if available, or fallback to simple_yaml_load."""
    with open(file_path, "r", encoding="utf-8") as f:
        content_str = f.read()

    if yaml is not None:
        try:
            return yaml.safe_load(content_str)
        except Exception as e:
            logger.warning(f"[GATEWAY BINDING] PyYAML failed to parse {file_path}, trying fallback parser: {e}")

    return simple_yaml_load(content_str)


def find_gateway_binding_config(yml_path: str = None):
    """Find and load the gateway-binding.yml configuration file."""
    search_paths = []
    if yml_path:
        search_paths.append(yml_path)

    # Standard locations
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    search_paths.extend([
        os.path.join(script_dir, "gateway-binding.yml"),
        os.path.join(script_dir, "gateway-binding.yaml"),
        os.path.join(repo_dir, "gateway-binding.yml"),
        os.path.join(repo_dir, "gateway-binding.yaml"),
    ])

    for path in search_paths:
        if os.path.isfile(path):
            try:
                content = parse_yaml_file(path)
                if content:
                    return path, content
            except Exception as e:
                logger.warning(f"[GATEWAY BINDING] Failed to read {path}: {e}")

    return None, None


def get_connection_ids_for_model(config_data, model_name: str, environment: str):
    """
    Extract list of connection_id strings for a given model_name and environment
    from gateway-binding.yml structure.
    """
    if not config_data:
        return []

    # Config can be a list or a dictionary
    items = config_data if isinstance(config_data, list) else [config_data]
    target_model_lower = model_name.strip().lower()
    target_env_lower = environment.strip().lower()

    connection_ids = []

    for item in items:
        if not isinstance(item, dict):
            continue

        item_model_name = (
            item.get("model-name") or
            item.get("model_name") or
            item.get("modelName") or ""
        )

        if str(item_model_name).strip().lower() == target_model_lower:
            replace_value = (
                item.get("replace_value") or
                item.get("replace_values") or {}
            )
            if not isinstance(replace_value, dict):
                continue

            # Find matching environment key case-insensitively
            env_config = None
            for env_key, env_data in replace_value.items():
                if str(env_key).strip().lower() == target_env_lower:
                    env_config = env_data
                    break

            if env_config and isinstance(env_config, dict):
                for ds_key, ds_data in env_config.items():
                    if isinstance(ds_data, dict):
                        cid = ds_data.get("connection_id") or ds_data.get("connection_id".lower())
                        if cid:
                            connection_ids.append(str(cid).strip())
                    elif isinstance(ds_data, str) and ds_data.strip():
                        connection_ids.append(ds_data.strip())

    return connection_ids


def take_over_dataset(credential, workspace_id: str, dataset_id: str) -> bool:
    """
    Calls Power BI REST API (Default.TakeOver) to transfer dataset ownership to the Service Principal.
    """
    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    session = requests.Session()
    for attempt in range(MAX_ATTEMPTS):
        try:
            r = session.post(url, headers=headers, json={}, timeout=30)
            if r.status_code in (200, 202):
                print(f"[GATEWAY BINDING] ✅ Dataset ownership taken over by Service Principal for dataset {dataset_id}")
                return True
            
            if r.status_code in (429, 500, 502, 503, 504, 409):
                sleep_for = min(2 ** attempt, BACKOFF_MAX)
                time.sleep(sleep_for)
                continue

            print(f"[GATEWAY BINDING] Warning: TakeOver returned HTTP {r.status_code}: {r.text}")
            return False
        except RequestException as ex:
            sleep_for = min(2 ** attempt, BACKOFF_MAX)
            time.sleep(sleep_for)

    return False


def bind_gateway_connection(credential, workspace_id: str, dataset_id: str,
                            connection_ids: list, gateway_object_id: str = CLOUD_GATEWAY_ID) -> bool:
    """
    Calls Power BI / Fabric REST API to bind semantic model data sources to Cloud Connections.
    Takes over dataset ownership first to satisfy owner permissions requirement.
    """
    if not connection_ids:
        print("[GATEWAY BINDING] No connection IDs provided for binding.")
        return False

    # Take over dataset ownership first so Service Principal has full rights to bind gateways
    take_over_dataset(credential, workspace_id, dataset_id)

    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
    session = requests.Session()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    errors = []

    # Step 0: Try to query GET gateways for dataset to find available gateway/cloud connection IDs
    url_get_gw = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/gateways"
    discovered_gateway_id = gateway_object_id
    try:
        r_gw = session.get(url_get_gw, headers=headers, timeout=30)
        if r_gw.status_code == 200:
            gw_data = r_gw.json()
            gw_list = gw_data.get("value", [])
            if gw_list:
                discovered_gateway_id = gw_list[0].get("id") or gateway_object_id
                print(f"[GATEWAY BINDING] Discovered gateway/cloud ID for dataset: {discovered_gateway_id}")
    except Exception as ex:
        logger.debug("GET gateways failed: %s", ex)

    # Method 1: Power BI REST API Default.BindToGateway
    url_pbi = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.BindToGateway"

    gateway_ids_to_try = [discovered_gateway_id]
    if CLOUD_GATEWAY_ID not in gateway_ids_to_try:
        gateway_ids_to_try.append(CLOUD_GATEWAY_ID)

    for gw_id in gateway_ids_to_try:
        payload_pbi = {
            "gatewayObjectId": gw_id,
            "datasourceObjectIds": connection_ids
        }
        for attempt in range(MAX_ATTEMPTS):
            try:
                r = session.post(url_pbi, headers=headers, json=payload_pbi, timeout=30)
                if r.status_code in (200, 202):
                    print(f"[GATEWAY BINDING] ✅ Cloud connections bound for dataset {dataset_id} using gatewayObjectId '{gw_id}' to connection IDs: {connection_ids}")
                    return True

                if r.status_code in (429, 500, 502, 503, 504, 409):
                    sleep_for = min(2 ** attempt, BACKOFF_MAX)
                    time.sleep(sleep_for)
                    continue

                msg = f"Default.BindToGateway (gatewayObjectId={gw_id}) returned HTTP {r.status_code}: {r.text}"
                print(f"[GATEWAY BINDING] Warning: {msg}")
                errors.append(msg)
                break
            except RequestException as ex:
                sleep_for = min(2 ** attempt, BACKOFF_MAX)
                time.sleep(sleep_for)

    # Method 2: Power BI REST API without gatewayObjectId
    payload_pbi_nogw = {
        "datasourceObjectIds": connection_ids
    }
    try:
        r2 = session.post(url_pbi, headers=headers, json=payload_pbi_nogw, timeout=30)
        if r2.status_code in (200, 202):
            print(f"[GATEWAY BINDING] ✅ Cloud connections bound (datasourceObjectIds only) for dataset {dataset_id}: {connection_ids}")
            return True
        msg2 = f"Default.BindToGateway (no gatewayObjectId) returned HTTP {r2.status_code}: {r2.text}"
        print(f"[GATEWAY BINDING] Warning: {msg2}")
        errors.append(msg2)
    except Exception as ex:
        errors.append(f"No-gatewayObjectId payload exception: {ex}")

    # Method 3: Fabric REST API bindConnection
    try:
        fabric_token = credential.get_token("https://api.fabric.microsoft.com/.default").token
        fabric_headers = {
            "Authorization": f"Bearer {fabric_token}",
            "Content-Type": "application/json",
        }
        url_fabric = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/semanticModels/{dataset_id}/bindConnection"

        success_count = 0
        for cid in connection_ids:
            payload_fabric = {
                "connectionBinding": {
                    "id": cid,
                    "connectivityType": "ShareableCloudConnection"
                }
            }
            try:
                rf = session.post(url_fabric, headers=fabric_headers, json=payload_fabric, timeout=30)
                if rf.status_code in (200, 202):
                    success_count += 1
                else:
                    msg_fab = f"Fabric bindConnection for {cid} returned HTTP {rf.status_code}: {rf.text}"
                    print(f"[GATEWAY BINDING] Warning: {msg_fab}")
                    errors.append(msg_fab)
            except Exception as ex:
                errors.append(f"Fabric bindConnection exception for {cid}: {ex}")

        if success_count > 0:
            print(f"[GATEWAY BINDING] ✅ Bound {success_count}/{len(connection_ids)} cloud connection(s) via Fabric API for dataset {dataset_id}")
            return True
    except Exception as ex:
        errors.append(f"Fabric token acquisition exception: {ex}")

    print(f"[GATEWAY BINDING] ❌ Cloud connection binding failed for dataset {dataset_id}.")
    print("[GATEWAY BINDING] Detailed diagnostic error log:")
    for err in errors:
        print(f"  - {err}")

    raise RuntimeError(f"Cloud connection binding failed for dataset {dataset_id}. Details: {'; '.join(errors)}")


def bind_gateway_if_configured(credential, workspace_id: str, dataset_id: str,
                               model_name: str, environment: str, yml_path: str = None) -> bool:
    """
    Checks if model_name is configured in gateway-binding.yml for the given environment.
    If configured, triggers gateway/cloud connection binding before refresh.
    """
    found_path, config_data = find_gateway_binding_config(yml_path)
    if not found_path or not config_data:
        print(f"[GATEWAY BINDING] SKIP: gateway-binding.yml not found or empty.")
        return False

    connection_ids = get_connection_ids_for_model(config_data, model_name, environment)
    if not connection_ids:
        print(f"[GATEWAY BINDING] SKIP: Model '{model_name}' not found in {os.path.basename(found_path)} for environment '{environment}'")
        return False

    print(f"[GATEWAY BINDING] Found gateway binding configuration for '{model_name}' in environment '{environment}' with connection ID(s): {connection_ids}")
    return bind_gateway_connection(credential, workspace_id, dataset_id, connection_ids)
