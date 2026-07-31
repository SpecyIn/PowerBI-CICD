"""
Power BI / Fabric CI/CD Deployment Orchestrator Script.
Publishes semantic models, updates report dataset bindings, binds cloud gateways, and triggers model refreshes.
"""
import os
import time
import csv
from pathlib import Path

from fabric_cicd import FabricWorkspace, publish_all_items, append_feature_flag
from auth import get_fabric_credential, get_workspace_id, get_environment
from semantic_model_list import export_models
from semantic_model_id_replace import replace_ids
from semantic_model_refresh import refresh_semantic_model
from gateway_binding import bind_gateway_if_configured
from parameter_override import build_parameter_yml_for_model, restore_base_parameter_yml

append_feature_flag("enable_experimental_features")
append_feature_flag("enable_include_folder")

start_time = time.time()
repo_dir = "."
report_folder = os.getenv("REPORT_FOLDER", "Reports")

if not report_folder:
    raise ValueError("REPORT_FOLDER environment variable is not set (e.g., SalesDashboard).")

reports_dir = os.path.join(repo_dir, "Reports")
target_dir = os.path.join(reports_dir, report_folder)

if not os.path.isdir(target_dir):
    raise FileNotFoundError(f"Expected deployment folder not found: {target_dir}")

credential = get_fabric_credential()
workspace_id = get_workspace_id()
environment = get_environment()

workspace_Report = FabricWorkspace(
    workspace_id=workspace_id,
    repository_directory=repo_dir,
    item_type_in_scope=["Report"],
    token_credential=credential,
    environment=environment
)

print("### STEP 1: Publish Semantic Models")
sm_folders = [p for p in Path(target_dir).rglob("*.SemanticModel") if p.is_dir()]

if not sm_folders:
    print("[PUBLISH] SKIP: No *.SemanticModel folders found under target_dir.")
else:
    try:
        for sm_path in sm_folders:
            sm_name = sm_path.stem
            print(f"\n[PUBLISH] Processing Semantic Model: {sm_name}")
            build_parameter_yml_for_model(repo_dir, sm_name)

            workspace_SM = FabricWorkspace(
                workspace_id=workspace_id,
                repository_directory=repo_dir,
                item_type_in_scope=["SemanticModel"],
                token_credential=credential,
                environment=environment
            )

            rel = os.path.relpath(sm_path, repo_dir).replace('\\', '/')
            workspace_path = f"/{rel}" if not rel.startswith('/') else rel
            publish_all_items(workspace_SM, folder_path_to_include=[workspace_path])
    finally:
        restore_base_parameter_yml(repo_dir)

print("\n### STEP 2: Fetch Model IDs")
models_file = export_models(credential, workspace_id)
print(f"Models exported to: {models_file}")

print("\n### STEP 3: Replace Model IDs in Reports")
replace_summary = replace_ids(target_dir, dry=False) or {}
print("Replace summary:", replace_summary)

print("\n### STEP 4: Publish Report Files")
include_paths = set()
for dirpath, _, _ in os.walk(target_dir):
    rel = os.path.relpath(dirpath, repo_dir).replace('\\', '/')
    workspace_path = f"/{rel}" if not rel.startswith('/') else rel
    include_paths.add(workspace_path)

publish_all_items(workspace_Report, folder_path_to_include=sorted(include_paths))
print(f"Deployment to workspace {workspace_id} completed successfully.")

print("\n### STEP 5: Refresh Published Semantic Models")

sms = [p.stem for p in Path(target_dir).rglob("*.SemanticModel") if p.is_dir()]
if not sms:
    print("[REFRESH] SKIP: No *.SemanticModel folders found under target_dir.")
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

print(f"\nTotal execution time: {time.time() - start_time:.2f}s")