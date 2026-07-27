import os

from dotenv import load_dotenv

load_dotenv()

def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


class Config:
    PROFILE = "base"
    DEBUG = False
    TESTING = False

    PULP_TIMELIMIT_SECONDS = os.getenv("PULP_TIMELIMIT_SECONDS")

    RATE_LIMIT_ENABLED = False
    RATE_LIMIT_REQUESTS = _int_env("RATE_LIMIT_REQUESTS", 120)
    RATE_LIMIT_WINDOW_SECONDS = _int_env("RATE_LIMIT_WINDOW_SECONDS", 60)
    RATE_LIMIT_TRUST_PROXY_HEADERS = _bool_env("RATE_LIMIT_TRUST_PROXY_HEADERS", False)

    TASK_LIMIT_ENABLED = False
    MAX_TASKS_PER_REQUEST = _int_env("MAX_TASKS_PER_REQUEST", 200)

    CONCURRENT_REQUEST_LIMIT_ENABLED = False
    MAX_RUNNING_REQUESTS_PER_IP = _int_env("MAX_RUNNING_REQUESTS_PER_IP", 2)


class DevConfig(Config):
    PROFILE = "dev"
    DEBUG = True
    RATE_LIMIT_ENABLED = False


class ProdConfig(Config):
    PROFILE = "prod"
    DEBUG = False
    RATE_LIMIT_ENABLED = _bool_env("RATE_LIMIT_ENABLED", True)
    TASK_LIMIT_ENABLED = _bool_env("TASK_LIMIT_ENABLED", True)
    CONCURRENT_REQUEST_LIMIT_ENABLED = _bool_env(
        "CONCURRENT_REQUEST_LIMIT_ENABLED",
        True,
    )


CONFIG_BY_PROFILE = {
    "dev": DevConfig,
    "development": DevConfig,
    "prod": ProdConfig,
    "production": ProdConfig,
}


def get_config():
    profile = os.getenv("RUNSOC_PROFILE") or os.getenv("FLASK_ENV") or "dev"
    normalized_profile = profile.strip().lower()

    try:
        return CONFIG_BY_PROFILE[normalized_profile]
    except KeyError as exc:
        supported_profiles = ", ".join(sorted(CONFIG_BY_PROFILE))
        raise ValueError(
            f"Unsupported RUNSOC_PROFILE '{profile}'. "
            f"Supported profiles: {supported_profiles}."
        ) from exc
