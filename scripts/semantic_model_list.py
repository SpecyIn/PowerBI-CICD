from typing import List, Tuple
import time
import csv
import logging
import requests
from requests.exceptions import RequestException
from azure.identity import ClientSecretCredential
from auth import get_fabric_credential, get_workspace_id

logger = logging.getLogger(__name__)

URL = "https://api.fabric.microsoft.com/v1/workspaces/{}/semanticModels"
SCOPE = "https://api.fabric.microsoft.com/.default"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 6

def list_models(cred: ClientSecretCredential, ws_id: str, timeout: int = DEFAULT_TIMEOUT,
                max_retries: int = MAX_RETRIES) -> List[Tuple[str, str]]:
    token = cred.get_token(SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    session = requests.Session()
    models: List[Tuple[str, str]] = []
    continuation = None

    while True:
        resp = None
        for attempt in range(max_retries):
            try:
                resp = session.get(
                    URL.format(ws_id),
                    headers=headers,
                    params={"continuationToken": continuation} if continuation else {},
                    timeout=timeout,
                )
            except RequestException as ex:
                sleep_for = min(2 ** attempt, 30)
                logger.debug("Request exception fetching semantic models (attempt %d): %s", attempt + 1, ex)
                time.sleep(sleep_for)
                continue

            if resp.status_code == 429:
                sleep_for = int(resp.headers.get("Retry-After", min(2 ** attempt, 30)))
                logger.debug("Rate limited, sleeping %s seconds", sleep_for)
                time.sleep(sleep_for)
                continue

            if 500 <= resp.status_code < 600:
                sleep_for = min(2 ** attempt, 30)
                logger.debug("Server error %s, sleeping %s seconds", resp.status_code, sleep_for)
                time.sleep(sleep_for)
                continue

            break

        if resp is None:
            raise RuntimeError("Failed to fetch semantic models: no response")

        try:
            resp.raise_for_status()
        except RequestException:
            logger.error("Failed to fetch semantic models: %s %s", resp.status_code, resp.text)
            raise

        data = resp.json()
        values = data.get("value", []) or []
        models.extend((m.get("displayName", ""), m.get("id", "")) for m in values)

        continuation = data.get("continuationToken")
        if not continuation:
            break

    logger.info("Found %d semantic models in workspace %s", len(models), ws_id)
    return models

def export_models(cred: ClientSecretCredential, ws_id: str, file: str = "semantic_models.csv") -> str:
    """Export semantic models to CSV and return the written filename."""
    models = sorted(list_models(cred, ws_id), key=lambda x: (x[0] or "").lower())

    with open(file, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([("displayName", "id"), *models])

    logger.info("Wrote %d models -> %s", len(models), file)
    return file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_models(get_fabric_credential(), get_workspace_id())