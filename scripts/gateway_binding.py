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


def bind_gateway_connection(credential, workspace_id: str, dataset_id: str,
                            connection_ids: list, gateway_object_id: str = CLOUD_GATEWAY_ID) -> bool:
    """
    Calls Power BI REST API (Default.BindToGateway) to bind dataset to specified connection IDs.
    """
    if not connection_ids:
        logger.info("[GATEWAY BINDING] No connection IDs provided for binding.")
        return False

    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.BindToGateway"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "gatewayObjectId": gateway_object_id,
        "datasourceObjectIds": connection_ids
    }

    session = requests.Session()

    for attempt in range(MAX_ATTEMPTS):
        try:
            r = session.post(url, headers=headers, json=payload, timeout=30)
        except RequestException as ex:
            sleep_for = min(2 ** attempt, BACKOFF_MAX)
            logger.debug("BindToGateway POST exception (attempt %d): %s", attempt + 1, ex)
            time.sleep(sleep_for)
            continue

        if r.status_code in (200, 202):
            print(f"[GATEWAY BINDING] ✅ Successfully bound dataset {dataset_id} to connections: {connection_ids}")
            return True

        if r.status_code in (429, 500, 502, 503, 504, 409):
            sleep_for = min(2 ** attempt, BACKOFF_MAX)
            logger.debug("Transient response %s during gateway binding, retrying after %s seconds", r.status_code, sleep_for)
            time.sleep(sleep_for)
            continue

        print(f"[GATEWAY BINDING] ❌ Gateway binding failed: {r.status_code} {r.text}")
        raise RuntimeError(f"Gateway binding failed for dataset {dataset_id}: {r.status_code} {r.text}")
    else:
        raise RuntimeError(f"Gateway binding failed after retries for dataset {dataset_id}")


def bind_gateway_if_configured(credential, workspace_id: str, dataset_id: str,
                               model_name: str, environment: str, yml_path: str = None) -> bool:
    """
    Checks if model_name is configured in gateway-binding.yml for the given environment.
    If configured, triggers gateway binding before refresh.
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
