from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_ENV_PATH = PROJECT_ROOT / "config" / "database.env"
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    app_name: str = "工程计价与投标策略平台"
    environment: str = "local"
    output_dir: Path = Path("outputs")
    upload_dir: Path = Path("uploads")
    default_tenant_code: str = "default"
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "boq_pricing"
    mysql_bin: str = "mysql"
    auth_secret: str = "boq-pricing-local-secret"
    auth_token_minutes: int = 480


def load_settings() -> Settings:
    local_env = load_local_env()
    return Settings(
        environment=get_config_value("BOQ_ENVIRONMENT", local_env, "local"),
        output_dir=Path(get_config_value("BOQ_OUTPUT_DIR", local_env, "outputs")),
        upload_dir=Path(get_config_value("BOQ_UPLOAD_DIR", local_env, "uploads")),
        default_tenant_code=get_config_value("BOQ_TENANT_CODE", local_env, "default"),
        mysql_user=get_config_value("BOQ_MYSQL_USER", local_env, "root"),
        mysql_password=get_config_value("BOQ_MYSQL_PASSWORD", local_env, ""),
        mysql_host=get_config_value("BOQ_MYSQL_HOST", local_env, "127.0.0.1"),
        mysql_port=int(get_config_value("BOQ_MYSQL_PORT", local_env, "3306")),
        mysql_database=get_config_value("BOQ_MYSQL_DATABASE", local_env, "boq_pricing"),
        mysql_bin=get_config_value("BOQ_MYSQL_BIN", local_env, "mysql"),
        auth_secret=get_config_value("BOQ_AUTH_SECRET", local_env, "boq-pricing-local-secret"),
        auth_token_minutes=int(get_config_value("BOQ_AUTH_TOKEN_MINUTES", local_env, "480")),
    )


def get_config_value(key: str, local_env: dict[str, str], default: str) -> str:
    return os.getenv(key) or local_env.get(key) or default


def load_local_env(path: Path = LOCAL_ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    for env_path in (path, DATABASE_ENV_PATH):
        if not env_path.exists():
            continue
        values.update(parse_env_file(env_path))
    return values


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
