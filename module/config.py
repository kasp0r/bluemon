import json
import os
from dataclasses import dataclass, asdict

DEFAULT_CONFIG_PATH = "config.json"


@dataclass
class AppConfig:
    scan_duration: int = 5
    scan_interval: int = 3
    sleep_duration: int = 1
    db_path: str = "bluemon.sqlite"
    host: str = "0.0.0.0"
    port: int = 8080


def load_config(path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not os.path.exists(path):
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return AppConfig(
        scan_duration=int(data.get("scan_duration", 5)),
        scan_interval=int(data.get("scan_interval", 3)),
        sleep_duration=int(data.get("sleep_duration", 1)),
        db_path=str(data.get("db_path", "bluemon.sqlite")),
        host=str(data.get("host", "0.0.0.0")),
        port=int(data.get("port", 8080)),
    )


def save_config(cfg: AppConfig, path: str = DEFAULT_CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)