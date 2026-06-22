import re

VALID_SERVICES = [
    "frontend", "cartservice", "productcatalogservice",
    "currencyservice", "paymentservice", "shippingservice",
    "emailservice", "checkoutservice", "recommendationservice",
    "adservice", "loadgenerator"
]

def validate_deploy_request(
    service_name: str,
    repo_url:     str,
    changes:      str
) -> None:
    if not service_name:
        raise ValueError("service_name is required")

    if service_name not in VALID_SERVICES:
        raise ValueError(
            f"Invalid service. Must be one of: {', '.join(VALID_SERVICES)}"
        )

    if not repo_url:
        raise ValueError("repo_url is required")

    if not changes or len(changes.strip()) < 3:
        raise ValueError("changes must be at least 3 characters")

def validate_username(username: str) -> None:
    if not username or len(username) < 3:
        raise ValueError("username must be at least 3 characters")

def validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("password must be at least 6 characters")