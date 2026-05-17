import os
from azure.identity import ClientSecretCredential

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


_ALIASES = {
    "FABRIC_TENANT_ID": ["TENANT_ID", "AZURE_TENANT_ID"],
    "FABRIC_CLIENT_ID": ["CLIENT_ID", "AZURE_CLIENT_ID"],
    "FABRIC_CLIENT_SECRET": ["CLIENT_SECRET", "AZURE_CLIENT_SECRET"],
    "FABRIC_WORKSPACE_ID": ["WORKSPACE_ID"],
    "FABRIC_ENVIRONMENT": ["ENVIRONMENT"],
}


def get_env_variable(name: str, default: str = None) -> str:
    """Get an environment variable with optional legacy aliases.

    If no value is found and no default is provided, raises ValueError.
    """
    value = os.getenv(name)
    if value is None:
        for alias in _ALIASES.get(name, []):
            value = os.getenv(alias)
            if value is not None:
                break

    if value is None:
        value = default

    if value is None:
        raise ValueError(f"Environment variable '{name}' is not set and no default value provided.")

    return value

def get_fabric_credential() -> ClientSecretCredential:
    tenant_id = get_env_variable("FABRIC_TENANT_ID")
    client_id = get_env_variable("FABRIC_CLIENT_ID")
    client_secret = get_env_variable("FABRIC_CLIENT_SECRET")

    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )

def get_workspace_id() -> str:
    return get_env_variable("FABRIC_WORKSPACE_ID")

def get_environment() -> str:
    return get_env_variable("FABRIC_ENVIRONMENT", "development").strip().lower()