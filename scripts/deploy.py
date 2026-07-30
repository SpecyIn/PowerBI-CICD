#python -m pip install pip-system-certs to fix any certificate issues when running the script
import os, time, csv
from pathlib import Path
from fabric_cicd import FabricWorkspace, publish_all_items, append_feature_flag #, get_changed_items, change_log_level
from auth import get_fabric_credential, get_workspace_id, get_environment
from semantic_model_list import export_models
from semantic_model_id_replace import replace_ids
from semantic_model_refresh import refresh_semantic_model
from gateway_binding import bind_gateway_if_configured
append_feature_flag("enable_experimental_features")
append_feature_flag("enable_include_folder")
start = time.time()

repo_dir = (".")
report_folder = os.getenv("REPORT_FOLDER", "Reports")

if not report_folder:
    raise ValueError("REPORT_FOLDER is not set (e.g. SalesDashboard).")

reports_dir = os.path.join(repo_dir, "Reports")
target_dir = os.path.join(reports_dir, report_folder)

if not os.path.isdir(target_dir):
    raise FileNotFoundError(f"Expected folder not found: {target_dir}")

credential = get_fabric_credential()
workspace_id = get_workspace_id()
environment = get_environment()

workspace_SM = FabricWorkspace(
    workspace_id=workspace_id,
    repository_directory=repo_dir,
    item_type_in_scope=["SemanticModel"],
    token_credential=credential,
    environment=environment
)

workspace_Report = FabricWorkspace(
    workspace_id=workspace_id,
    repository_directory=repo_dir,
    item_type_in_scope=["Report"],
    token_credential=credential,
    environment=environment
)

print("### STEP 1: Publish Semantic Models")
viz_folder = f"/Reports/{report_folder}"
print(f"Including workspace folder: {viz_folder}")
print(f"Local path for replace: {target_dir}")
include_paths = set()
for dirpath, dirnames, filenames in os.walk(target_dir):
    rel = os.path.relpath(dirpath, repo_dir).replace('\\', '/')
    workspace_path = f"/{rel}" if not rel.startswith('/') else rel
    include_paths.add(workspace_path)

publish_all_items(workspace_SM, folder_path_to_include=sorted(include_paths))

print("### STEP 2: Fetch Model ID's")
models_file = export_models(credential, workspace_id)
print(f"Models exported to: {models_file}")

print("### STEP 3: Replace Model ID's")
replace_summary = replace_ids(target_dir, dry=False) or {}
print("Replace summary:", replace_summary)

print("### STEP 4: Publish Report Files")
publish_all_items(workspace_Report, folder_path_to_include=sorted(include_paths))
print(f"Deployment to workspace: {workspace_id} is completed successfully")

print("### STEP 5: Refresh Published Semantic Models")

sms = [p.stem for p in Path(target_dir).rglob("*.SemanticModel") if p.is_dir()]
if not sms:
    print("[REFRESH] SKIP: No *.SemanticModel folder found under target_dir")
else:
    with open(models_file, newline="", encoding="utf-8-sig") as f:
        name_to_id = {
            r["displayName"].strip().lower(): r["id"].strip()
            for r in csv.DictReader(f)
        }

    for sm in sms:
        did = name_to_id.get(sm.strip().lower())
        print(f"[REFRESH] {'Trigger' if did else 'SKIP'}: {sm}" + (f" ({did})" if did else ""))
        if did:
            try:
                bind_gateway_if_configured(credential, workspace_id, did, sm, environment)
                refresh_semantic_model(credential, workspace_id, did)
            except Exception as ex:
                print(f"[REFRESH] ERROR for {sm} ({did}): {ex}")
                continue

print(f"Total execution time: {time.time() - start:.2f}s")