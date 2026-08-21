import os
from pathlib import Path
import yaml

DEFAULT_CONFIG_PATH = Path("~/.config/snana-assistant/config.yaml").expanduser()

def load_config() -> dict:
    if not DEFAULT_CONFIG_PATH.exists():
        return {}
    try:
        with open(DEFAULT_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def save_config(config: dict) -> None:
    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)

def get_config_value(key: str, default: str | None = None) -> str | None:
    if key in os.environ:
        return os.environ[key]
    config = load_config()
    if key in config:
        return config[key]
    return default

def load_all_config_to_env() -> None:
    config = load_config()
    for k, v in config.items():
        if k not in os.environ and v is not None:
            os.environ[k] = str(v)


def log_uncaptured_query(query: str) -> None:
    log_path = Path("~/.config/snana-assistant/uncaptured_queries.log").expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(query.strip() + "\n")


def get_last_uncaptured_query() -> str | None:
    log_path = Path("~/.config/snana-assistant/uncaptured_queries.log").expanduser()
    if not log_path.exists():
        return None
    try:
        with open(log_path) as f:
            lines = f.readlines()
        if lines:
            return lines[-1].strip()
    except Exception:
        pass
    return None

