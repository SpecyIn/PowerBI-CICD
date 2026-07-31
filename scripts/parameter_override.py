import os
import logging
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

BINARY_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pbix', '.zip', '.exe', '.dll', '.bin'}


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
                        current_item['replace_value'][current_env] = val
                    elif key in ('model_name', 'model-name', 'modelName', 'find_value'):
                        current_item[key] = val

    return result


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


def replace_in_folder(folder_path: Path, rules: dict):
    """Replace text occurrences of find_value -> replace_value across text files in folder_path."""
    if not rules:
        return

    count = 0
    for root, _, files in os.walk(folder_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in BINARY_EXTENSIONS:
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                modified = content
                for find_val, replace_val in rules.items():
                    if find_val and find_val in modified and find_val != replace_val:
                        modified = modified.replace(find_val, str(replace_val))

                if modified != content:
                    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                        f.write(modified)
                    count += 1
            except Exception as e:
                logger.debug("Failed to process %s: %s", fpath, e)

    print(f"[PARAMETER OVERRIDE] Updated {count} file(s) under '{folder_path.name}'.")


def apply_parameter_overrides(repo_dir: str, target_dir: str, environment: str = "development") -> bool:
    """
    Applies model-specific parameter overrides directly to each semantic model under target_dir.
    For each model, combines generic parameter.yml rules with override-parameter.yml rules
    for that specific model name, and updates that model's files in place.
    """
    param_file = os.path.join(repo_dir, "parameter.yml")
    if not os.path.isfile(param_file):
        param_file = os.path.join(repo_dir, "parameter.yaml")

    base_rules = []
    if os.path.isfile(param_file):
        try:
            with open(param_file, "r", encoding="utf-8") as f:
                content = f.read()
            if yaml is not None:
                data = yaml.safe_load(content) or {}
                base_rules = data.get("find_replace", []) if isinstance(data, dict) else []
            else:
                base_rules = simple_yaml_load_overrides(content)
        except Exception as e:
            print(f"[PARAMETER OVERRIDE] Warning reading base parameter.yml: {e}")

    override_file = find_override_file(repo_dir)
    override_items = []
    if override_file:
        try:
            with open(override_file, "r", encoding="utf-8") as f:
                content = f.read()
            if yaml is not None:
                odata = yaml.safe_load(content) or {}
            else:
                odata = simple_yaml_load_overrides(content)

            if isinstance(odata, dict):
                override_items = odata.get("overrides") or odata.get("find_replace") or []
                if not isinstance(override_items, list):
                    override_items = [override_items]
            elif isinstance(odata, list):
                override_items = odata
        except Exception as e:
            print(f"[PARAMETER OVERRIDE] Warning reading override-parameter.yml: {e}")

    # Find all *.SemanticModel folders under target_dir
    model_dirs = [p for p in Path(target_dir).rglob("*.SemanticModel") if p.is_dir()]
    if not model_dirs:
        print(f"[PARAMETER OVERRIDE] No *.SemanticModel folders found under {target_dir}")
        return False

    env_lower = environment.strip().lower()

    for model_path in model_dirs:
        model_folder_name = model_path.name
        model_stem = model_path.stem.replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

        # Build base rules dictionary for this environment
        effective_rules = {}

        for rule in base_rules:
            if isinstance(rule, dict):
                fv = rule.get("find_value")
                rv = rule.get("replace_value")
                if fv and rv:
                    val_for_env = fv
                    if isinstance(rv, dict):
                        for k, v in rv.items():
                            if str(k).strip().lower() == env_lower:
                                val_for_env = v
                                break
                    elif isinstance(rv, str):
                        val_for_env = rv
                    effective_rules[fv] = val_for_env

        # Overlay overrides matching THIS model name
        for item in override_items:
            if not isinstance(item, dict):
                continue
            item_model = (
                item.get("model_name") or
                item.get("model-name") or
                item.get("modelName") or ""
            )
            clean_item_model = str(item_model).replace(".SemanticModel", "").replace(".semanticmodel", "").strip().lower()

            if clean_item_model == model_stem:
                fv = item.get("find_value")
                rv = item.get("replace_value")
                if fv and rv:
                    val_for_env = fv
                    if isinstance(rv, dict):
                        for k, v in rv.items():
                            if str(k).strip().lower() == env_lower:
                                val_for_env = v
                                break
                    elif isinstance(rv, str):
                        val_for_env = rv
                    effective_rules[fv] = val_for_env
                    print(f"[PARAMETER OVERRIDE] Model '{model_folder_name}': Overriding '{fv}' -> '{val_for_env}' for env '{environment}'")

        print(f"[PARAMETER OVERRIDE] Applying parameters to model '{model_folder_name}' for environment '{environment}'...")
        replace_in_folder(model_path, effective_rules)

    print(f"[PARAMETER OVERRIDE] ✅ Finished parameter processing for models in {target_dir}.")
    return True
