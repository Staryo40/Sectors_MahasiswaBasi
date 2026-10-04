"""Read only channel settings without enabling ingestion or exposing secrets."""
import os
from radar import config


def settings(keys):
    values = {}
    if config.ENV_PATH.exists():
        for line in config.ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() in keys:
                values[key.strip()] = value.strip().strip("'\"")
    return {key: os.environ.get(key, values.get(key, "")).strip() for key in keys}
