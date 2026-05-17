import os
import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# ---------- Connection String Helpers ----------

def _parse_conn(conn: str):
    """Parse a SQL-style connection string into list of (Key, normalized_key, Value).

    Preserves quoting on values (i.e. values may include surrounding quotes).
    """
    parts, buf, in_q = [], [], False

    for ch in conn:
        if ch == '"':
            in_q = not in_q

        if ch == ';' and not in_q:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)

    if buf:
        parts.append(''.join(buf).strip())

    kvs = []
    for p in parts:
        if '=' in p:
            k, v = p.split('=', 1)
            kvs.append((k.strip(), k.strip().lower(), v.strip()))
        else:
            kvs.append((p, p.lower(), ""))

    return kvs


def _rebuild_conn(kvs):
    return ';'.join(f"{k}={v}" if v else k for k, _, v in kvs)


def _get_vals(conn: str) -> Tuple[Optional[str], Optional[str]]:
    init_cat = None
    sem_id = None

    for _, k, v in _parse_conn(conn):
        # strip surrounding quotes for value comparisons
        raw = v.strip('"')

        if k == "initial catalog":
            init_cat = raw
        elif k == "semanticmodelid":
            sem_id = raw

    return init_cat, sem_id


# ---------- Core Logic ----------

def load_model_map(file: str) -> Dict[str, str]:
    with open(file, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = {c.lower(): c for c in reader.fieldnames or []}

        if "displayname" not in headers or "id" not in headers:
            raise ValueError(f"Invalid headers in {file}: {reader.fieldnames}")

        model_map: Dict[str, str] = {}
        for row in reader:
            display_name = row.get(headers["displayname"], "")
            model_id = row.get(headers["id"], "")

            if display_name and model_id:
                model_map[display_name.strip().lower()] = model_id.strip()

        return model_map

def find_pbir(root: str):
    pbir_files = []
    root_path = Path(root)

    for p in root_path.rglob("definition.pbir"):
        if p.is_file():
            pbir_files.append(str(p))

    return pbir_files


def update_file(path: str, model_map: Dict[str, str], dry: bool = False) -> Tuple[bool, str]:
    path_obj = Path(path)
    with open(path_obj, encoding="utf-8-sig") as f:
        data = json.load(f)

    dataset_ref = data.get("datasetReference") or {}
    by_path = dataset_ref.get("byPath")
    by_connection = dataset_ref.get("byConnection")

    if by_connection is None:
        if by_path:
            return False, f"SKIP: Local byPath reference in {path}"
        return False, f"SKIP: No byConnection in {path}"

    if not isinstance(by_connection, dict):
        return False, f"SKIP: Invalid byConnection format in {path}"

    conn = by_connection.get("connectionString")
    if not conn:
        return False, f"SKIP: No connectionString in {path}"

    init_cat, cur_id = _get_vals(conn)
    if not init_cat:
        return False, f"SKIP: No initial catalog in {path}"

    target = model_map.get(init_cat.lower())
    if not target:
        return False, f"SKIP: No match for semantic model '{init_cat}' in {path}"

    if cur_id and cur_id.lower() == target.lower():
        return False, f"OK: Already correct in {path}"

    kvs = _parse_conn(conn)
    replaced = False

    for i, (k, normalized_key, v) in enumerate(kvs):
        if normalized_key == "semanticmodelid":
            # preserve quote style if present
            has_quotes = v.startswith('"') and v.endswith('"')
            new_value = f'"{target}"' if has_quotes else target
            kvs[i] = (k, normalized_key, new_value)
            replaced = True
            break

    if not replaced:
        # append new semanticmodelid without quotes by default
        kvs.append(("semanticmodelid", "semanticmodelid", target))

    new_conn = _rebuild_conn(kvs)
    if new_conn == conn:
        return False, f"OK: No change needed in {path}"

    if dry:
        return True, f"DRYRUN: Would update '{init_cat}' -> {target} in {path}"

    # safe write: backup original, write to temp and atomically replace
    backup = path_obj.with_suffix(path_obj.suffix + ".bak")
    try:
        shutil.copy2(path_obj, backup)
    except Exception:
        logger.debug("Could not create backup for %s", path)

    data["datasetReference"]["byConnection"]["connectionString"] = new_conn

    # write to temp and move into place
    fd, tmp = tempfile.mkstemp(prefix=path_obj.name, dir=str(path_obj.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\r\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path_obj)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    logger.info("UPDATED: '%s' -> %s in %s", init_cat, target, path)
    return True, f"UPDATED: '{init_cat}' -> {target} in {path}"


def replace_ids(repo: str, file="semantic_models.csv", dry=False):
    model_map = load_model_map(file)

    stats = {
        "files_scanned": 0,
        "updated": 0,
        "ok": 0,
        "skipped": 0,
        "changed_files": []
    }

    for p in find_pbir(repo):
        stats["files_scanned"] += 1

        changed, msg = update_file(p, model_map, dry)

        print(msg)

        if changed:
            stats["updated"] += 1
            stats["changed_files"].append(p)
        elif msg.startswith("OK"):
            stats["ok"] += 1
        else:
            stats["skipped"] += 1

    logger.info("replace_ids: scanned=%d updated=%d ok=%d skipped=%d",
                stats["files_scanned"], stats["updated"], stats["ok"], stats["skipped"])
    return stats


if __name__ == "__main__":
    print("Summary:", replace_ids(".", dry=False))