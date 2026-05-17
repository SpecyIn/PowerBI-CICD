from typing import Optional
import time
import logging

import requests
from requests.exceptions import RequestException
from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 6
BACKOFF_MAX = 30
POLL_BASE = 5

def refresh_semantic_model(credential: ClientSecretCredential, workspace_id: str, dataset_id: str,
                           timeout_sec: int = 3600, skip_non_model: bool = True) -> Optional[bool]:
    
    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token
    base = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    session = requests.Session()

    for attempt in range(MAX_ATTEMPTS):
        try:
            r = session.post(f"{base}/refreshes", headers=headers, json={}, timeout=30)
        except RequestException as ex:
            sleep_for = min(2 ** attempt, BACKOFF_MAX)
            logger.debug("Refresh POST exception (attempt %d): %s", attempt + 1, ex)
            time.sleep(sleep_for)
            continue

        if r.status_code in (200, 202):
            logger.debug("Refresh triggered for dataset %s (status %s)", dataset_id, r.status_code)
            break

        if r.status_code == 415 and skip_non_model:
            logger.info("[REFRESH] SKIP: Dataset %s is not model-based (415)", dataset_id)
            return None

        if r.status_code in (429, 500, 502, 503, 504, 409):
            sleep_for = min(2 ** attempt, BACKOFF_MAX)
            logger.debug("Transient response %s, retrying after %s seconds", r.status_code, sleep_for)
            time.sleep(sleep_for)
            continue

        logger.error("Refresh trigger failed: %s %s", r.status_code, r.text)
        raise RuntimeError(f"Refresh trigger failed: {r.status_code} {r.text}")
    else:
        raise RuntimeError(f"Refresh trigger failed after retries: {getattr(r, 'status_code', 'no-response')} {getattr(r, 'text', '')}")

    location = r.headers.get("Location", "")
    refresh_id = r.headers.get("RequestId") or r.headers.get("requestId")
    if not refresh_id and location:
        refresh_id = location.rstrip("/").split("/")[-1]

    if not refresh_id:
        logger.info("[REFRESH] Triggered refresh for dataset %s (no refresh id to poll).", dataset_id)
        return True

    start = time.monotonic()
    poll_interval = POLL_BASE

    while True:
        elapsed = time.monotonic() - start
        if elapsed > timeout_sec:
            raise TimeoutError(f"Refresh timed out after {timeout_sec}s for dataset {dataset_id}")

        try:
            s = session.get(f"{base}/refreshes/{refresh_id}", headers=headers, timeout=30)
        except RequestException as ex:
            logger.debug("Refresh status GET exception: %s", ex)
            time.sleep(min(poll_interval, BACKOFF_MAX))
            poll_interval = min(poll_interval * 2, BACKOFF_MAX)
            continue

        if s.status_code in (429, 500, 502, 503, 504):
            logger.debug("Transient status check %s, sleeping %s seconds", s.status_code, poll_interval)
            time.sleep(min(poll_interval, BACKOFF_MAX))
            poll_interval = min(poll_interval * 2, BACKOFF_MAX)
            continue

        if s.status_code not in (200, 202):
            logger.error("Refresh status check failed: %s %s", s.status_code, s.text)
            raise RuntimeError(f"Refresh status check failed: {s.status_code} {s.text}")

        data = s.json() if s.text else {}
        status = (data.get("status") or data.get("refreshStatus") or data.get("state") or "").lower()

        if status in ("completed", "succeeded"):
            logger.info("[REFRESH] ✅ Successfully Completed for dataset %s", dataset_id)
            return True

        if status in ("failed", "error"):
            logger.error("[REFRESH] ❌ Failed for dataset %s: %s", dataset_id, data)
            raise RuntimeError(f"[REFRESH] Failed for dataset {dataset_id}: {data}")

        # still running -> wait and increase polling interval
        time.sleep(min(poll_interval, BACKOFF_MAX))
        poll_interval = min(poll_interval * 2, BACKOFF_MAX)