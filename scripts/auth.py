import os
from azure.identity import ClientSecretCredential

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"

def get_env_variable(name: str, default: str = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Environment variable '{name}' is not set and no default value provided.")
    return value

def get_fabric_credential() -> ClientSecretCredential:
    return ClientSecretCredential(
        tenant_id=get_env_variable("TENANT_ID"),
        client_id=get_env_variable("CLIENT_ID"),
        client_secret=get_env_variable("CLIENT_SECRET")
    )

def get_workspace_id() -> str:
    return get_env_variable("WORKSPACE_ID")

def get_environment() -> str:
    return get_env_variable("ENVIRONMENT", "development").strip().lower()