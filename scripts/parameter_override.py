import os
import logging
from pathlib import Path

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
    stack = []

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
                        if current_env not in current_item['replace_value']:
                            current_item['replace_value'][current_env] = {}
                        current_item['replace_value'][current_env] = val
                    elif key in ('model_name', 'model-name', 'modelName', 'find_value'):
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


def apply_parameter_overrides(repo_dir: str, target_dir: str) -> bool:
    """
    Merges generic parameter.yml with model-specific rules from override-parameter.yml
    and rewrites parameter.yml in place before fabric_cicd publishes items.
    """
    param_file = os.path.join(repo_dir, "parameter.yml")
    if not os.path.isfile(param_file):
        param_file = os.path.join(repo_dir, "parameter.yaml")
        if not os.path.isfile(param_file):
            print("[PARAMETER OVERRIDE] parameter.yml not found, skipping override processing.")
            return False

    override_file = find_override_file(repo_dir)
    if not override_file:
        print("[PARAMETER OVERRIDE] No override-parameter.yml file found, using standard parameter.yml.")
        return False

    base_data = None
    override_data = None

    # Read base parameter.yml
    try:
        with open(param_file, "r", encoding="utf-8") as f:
            content_param = f.read()
        if yaml is not None:
            base_data = yaml.safe_load(content_param)
        if not base_data:
            base_data = {"find_replace": simple_yaml_load_overrides(content_param)}
    except Exception as e:
        print(f"[PARAMETER OVERRIDE] Failed to read {param_file}: {e}")
        return False

    # Read override-parameter.yml
    try:
        with open(override_file, "r", encoding="utf-8") as f:
            content_override = f.read()
        if yaml is not None:
            override_data = yaml.safe_load(content_override)
        if not override_data:
            override_data = simple_yaml_load_overrides(content_override)
    except Exception as e:
        print(f"[PARAMETER OVERRIDE] Failed to read {override_file}: {e}")
        return False

    # Get model names currently being deployed in target_dir
    deploying_models = set()
    for p in Path(target_dir).rglob("*.SemanticModel"):
        if p.is_dir():
            clean_name = p.stem.replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()
            deploying_models.add(clean_name)

    if not deploying_models:
        print("[PARAMETER OVERRIDE] No semantic models found under target_dir.")
        return False

    # Normalize override items list
    override_items = []
    if isinstance(override_data, dict):
        override_items = override_data.get("overrides") or override_data.get("find_replace") or []
        if not isinstance(override_items, list):
            override_items = [override_items]
    elif isinstance(override_data, list):
        override_items = override_data

    # Collect overrides applicable to models in current deployment
    applicable_overrides = {}  # find_val_key -> rule_dict
    for item in override_items:
        if not isinstance(item, dict):
            continue
        model_name = (
            item.get("model_name") or
            item.get("model-name") or
            item.get("modelName") or ""
        )
        clean_item_name = str(model_name).replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

        if clean_item_name in deploying_models:
            find_val = item.get("find_value")
            replace_val = item.get("replace_value")
            if find_val and replace_val:
                find_val_key = str(find_val).strip().lower()
                applicable_overrides[find_val_key] = {
                    "find_value": find_val,
                    "replace_value": replace_val
                }
                print(f"[PARAMETER OVERRIDE] Found model override for '{model_name}': find_value = '{find_val}'")

    if not applicable_overrides:
        print(f"[PARAMETER OVERRIDE] No model-specific overrides match deploying models: {deploying_models}")
        return False

    # Merge overrides into base find_replace list
    base_find_replace = base_data.get("find_replace", []) if isinstance(base_data, dict) else []
    merged_find_replace = []
    overridden_keys = set()

    for rule in base_find_replace:
        if not isinstance(rule, dict):
            merged_find_replace.append(rule)
            continue

        fv = rule.get("find_value")
        if fv:
            fv_key = str(fv).strip().lower()
            if fv_key in applicable_overrides:
                # Priority replacement with override rule!
                merged_find_replace.append(applicable_overrides[fv_key])
                overridden_keys.add(fv_key)
                print(f"[PARAMETER OVERRIDE] Overriding generic parameter for find_value '{fv}'")
            else:
                merged_find_replace.append(rule)
        else:
            merged_find_replace.append(rule)

    # Append any new find_value rules from override that weren't in base parameter.yml
    for fv_key, rule in applicable_overrides.items():
        if fv_key not in overridden_keys:
            merged_find_replace.append(rule)
            print(f"[PARAMETER OVERRIDE] Appending new override rule for find_value '{rule['find_value']}'")

    if isinstance(base_data, dict):
        base_data["find_replace"] = merged_find_replace
    else:
        base_data = {"find_replace": merged_find_replace}

    # Write merged configuration back to parameter.yml
    with open(param_file, "w", encoding="utf-8") as f:
        if yaml is not None:
            yaml.safe_dump(base_data, f, sort_keys=False, default_flow_style=False)
        else:
            f.write(simple_yaml_dump_parameters(base_data))

    print(f"[PARAMETER OVERRIDE] ✅ Successfully updated parameter.yml with model-specific overrides from {os.path.basename(override_file)}.")
    return True
