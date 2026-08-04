import os
import shutil
import logging

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


def simple_yaml_load_overrides(text: str):
    """Fallback stack-based parser for override-parameter.yml if PyYAML is not installed."""
    result = []
    current_item = None
    current_env = None

    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if stripped.startswith('-'):
            item_content = stripped[1:].strip()
            current_item = {}
            result.append(current_item)
            current_env = None

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

            if current_item is not None:
                if key in ('replace_value', 'replace_values') and not val:
                    current_item['replace_value'] = {}
                elif val == '' and 'replace_value' in current_item:
                    current_item['replace_value'][key] = {}
                    current_env = key
                elif val:
                    if current_env and 'replace_value' in current_item and isinstance(current_item['replace_value'], dict):
                        current_item['replace_value'][current_env] = val
                    elif key in ('model_name', 'model-name', 'modelName', 'find_value', 'takeover', 'take_over', 'takeOver'):
                        current_item[key] = val

    return result


def simple_yaml_dump_parameters(data: dict) -> str:
    """Format parameter dictionary back into clean YAML string."""
    lines = ["find_replace:"]
    for item in data.get("find_replace", []):
        if not isinstance(item, dict):
            continue
        fv = item.get("find_value", "")
        lines.append(f'  - find_value: "{fv}"')
        lines.append('    replace_value:')
        rv = item.get("replace_value", {})
        if isinstance(rv, dict):
            for env_k, env_v in rv.items():
                lines.append(f'      {env_k}: "{env_v}"')
        elif isinstance(rv, str):
            lines.append(f'      development: "{rv}"')
    return "\n".join(lines) + "\n"


def find_override_file(repo_dir: str):
    """Find override-parameter.yml in standard locations."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(repo_dir, "override-parameter.yml"),
        os.path.join(repo_dir, "override-parameter.yaml"),
        os.path.join(repo_dir, "override_parameter.yml"),
        os.path.join(repo_dir, "override_parameter.yaml"),
        os.path.join(repo_dir, "cicd", "override-parameter.yml"),
        os.path.join(repo_dir, "cicd", "override_parameter.yml"),
        os.path.join(script_dir, "override-parameter.yml"),
        os.path.join(script_dir, "override_parameter.yml"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def should_takeover_model(repo_dir: str, model_name: str) -> bool:
    """
    Checks override-parameter.yml to see if any override entry for model_name has takeover set to 'Yes' / True.
    Returns True if at least 1 entry for model_name specifies takeover: 'Yes', else False.
    """
    override_file = find_override_file(repo_dir)
    if not override_file:
        return False

    override_items = []
    try:
        with open(override_file, "r", encoding="utf-8") as f:
            content_override = f.read()
        if yaml is not None:
            odata = yaml.safe_load(content_override) or {}
        else:
            odata = simple_yaml_load_overrides(content_override)

        if isinstance(odata, dict):
            override_items = odata.get("overrides") or odata.get("find_replace") or []
            if not isinstance(override_items, list):
                override_items = [override_items]
        elif isinstance(odata, list):
            override_items = odata
    except Exception as e:
        logger.warning("[TAKEOVER] Failed to read override file for takeover check: %s", e)
        return False

    clean_target_model = str(model_name).replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

    for item in override_items:
        if not isinstance(item, dict):
            continue

        mname = (
            item.get("model_name") or
            item.get("model-name") or
            item.get("modelName") or ""
        )
        clean_mname = str(mname).replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

        if clean_mname == clean_target_model:
            takeover_val = item.get("takeover") or item.get("take_over") or item.get("takeOver")
            if takeover_val is not None:
                str_val = str(takeover_val).strip().lower()
                if str_val in ("yes", "y", "true", "1") or takeover_val is True:
                    return True

    return False


def take_over_dataset(credential, workspace_id: str, dataset_id: str) -> bool:
    """
    Calls Power BI REST API (Default.TakeOver) to transfer dataset ownership to the Service Principal.
    """
    import requests
    try:
        token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
        url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        session = requests.Session()
        r = session.post(url, headers=headers, json={}, timeout=30)
        if r.status_code in (200, 202):
            print(f"[TAKEOVER] ✅ Dataset ownership taken over by Service Principal for dataset {dataset_id}")
            return True

        print(f"[TAKEOVER] Warning: TakeOver returned HTTP {r.status_code}: {r.text}")
        return False
    except Exception as ex:
        print(f"[TAKEOVER] ERROR taking over dataset {dataset_id}: {ex}")
        return False


def build_parameter_yml_for_model(repo_dir: str, model_name: str) -> bool:
    """
    Generates parameter.yml dynamically for a specific model_name.
    Combines base generic parameter rules with model-specific overrides from override-parameter.yml.
    """
    param_file = os.path.join(repo_dir, "parameter.yml")
    backup_file = os.path.join(repo_dir, ".parameter_base_backup.yml")

    # Create initial backup of base parameter.yml if not already created
    if not os.path.isfile(backup_file):
        if os.path.isfile(param_file):
            shutil.copy2(param_file, backup_file)
        else:
            print("[PARAMETER OVERRIDE] Base parameter.yml not found.")
            return False

    # Read base rules from backup
    base_data = None
    try:
        with open(backup_file, "r", encoding="utf-8") as f:
            content_base = f.read()
        if yaml is not None:
            base_data = yaml.safe_load(content_base) or {}
        if not base_data:
            base_data = {"find_replace": simple_yaml_load_overrides(content_base)}
    except Exception as e:
        print(f"[PARAMETER OVERRIDE] Failed to read base parameter file: {e}")
        return False

    base_rules = base_data.get("find_replace", []) if isinstance(base_data, dict) else []

    # Read override-parameter.yml
    override_file = find_override_file(repo_dir)
    override_items = []
    if override_file:
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                content_override = f.read()
            if yaml is not None:
                odata = yaml.safe_load(content_override) or {}
            else:
                odata = simple_yaml_load_overrides(content_override)

            if isinstance(odata, dict):
                override_items = odata.get("overrides") or odata.get("find_replace") or []
                if not isinstance(override_items, list):
                    override_items = [override_items]
            elif isinstance(odata, list):
                override_items = odata
        except Exception as e:
            print(f"[PARAMETER OVERRIDE] Failed to read override file: {e}")

    clean_target_model = model_name.replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

    # Collect overrides specific to THIS model_name
    model_overrides = {}
    for item in override_items:
        if not isinstance(item, dict):
            continue
        mname = (
            item.get("model_name") or
            item.get("model-name") or
            item.get("modelName") or ""
        )
        clean_mname = str(mname).replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

        if clean_mname == clean_target_model:
            fv = item.get("find_value")
            rv = item.get("replace_value")
            if fv and rv:
                model_overrides[str(fv).strip().lower()] = {
                    "find_value": fv,
                    "replace_value": rv
                }
                print(f"[PARAMETER OVERRIDE] Model '{model_name}': Applying override for find_value '{fv}'")

    # Merge base rules with model-specific overrides
    merged_rules = []
    overridden_keys = set()

    for rule in base_rules:
        if not isinstance(rule, dict):
            merged_rules.append(rule)
            continue
        fv = rule.get("find_value")
        if fv:
            fv_key = str(fv).strip().lower()
            if fv_key in model_overrides:
                merged_rules.append(model_overrides[fv_key])
                overridden_keys.add(fv_key)
            else:
                merged_rules.append(rule)
        else:
            merged_rules.append(rule)

    for fv_key, rule in model_overrides.items():
        if fv_key not in overridden_keys:
            merged_rules.append(rule)

    final_data = {"find_replace": merged_rules}

    # Write merged configuration back to parameter.yml
    with open(param_file, "w", encoding="utf-8") as f:
        if yaml is not None:
            yaml.safe_dump(final_data, f, sort_keys=False, default_flow_style=False)
        else:
            f.write(simple_yaml_dump_parameters(final_data))

    return True


def restore_base_parameter_yml(repo_dir: str):
    """Restores original parameter.yml from backup if backup exists."""
    param_file = os.path.join(repo_dir, "parameter.yml")
    backup_file = os.path.join(repo_dir, ".parameter_base_backup.yml")

    if os.path.isfile(backup_file):
        try:
            shutil.copy2(backup_file, param_file)
            os.remove(backup_file)
            print("[PARAMETER OVERRIDE] Restored original base parameter.yml.")
        except Exception as e:
            logger.warning("[PARAMETER OVERRIDE] Could not restore base parameter.yml: %s", e)
