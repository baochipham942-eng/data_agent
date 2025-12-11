import os
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
ENV_FILE: Final[Path] = PROJECT_ROOT / ".env"

# 导出 PROJECT_ROOT 供其他模块使用
__all__ = [
    "PROJECT_ROOT", 
    "DATA_DB_PATH", 
    "LOGS_DB_PATH", 
    "SYSTEM_DB_PATH",  # 系统数据库（合并了 memory, knowledge, prompt, evaluation）
    "VANNA_DATA_DIR", 
    "DEEPSEEK_API_KEY", 
    "DEEPSEEK_MODEL", 
    "DEEPSEEK_BASE_URL"
]


def _load_env_file() -> None:
    """简易 .env 加载器：在缺省情况下读取项目根目录的 .env。"""
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _resolve_path(setting_name: str, default_relative: str) -> Path:
    raw = os.getenv(setting_name)
    if raw:
        return Path(raw).expanduser().resolve()
    return (PROJECT_ROOT / default_relative).resolve()


def _require_env(setting_name: str) -> str:
    value = os.getenv(setting_name)
    if value:
        return value
    raise RuntimeError(
        f"缺少必要配置 {setting_name}。请设置环境变量，"
        f"或在 {ENV_FILE} 中添加 {setting_name}=<your_value> 后重新运行。"
    )


_load_env_file()

DATA_DB_PATH: Final[Path] = _resolve_path("DATA_DB_PATH", "data/data.db")
LOGS_DB_PATH: Final[Path] = _resolve_path("LOGS_DB_PATH", "logs/logs.db")
# 系统数据库：合并了 memory, knowledge, prompt, evaluation 等系统数据
SYSTEM_DB_PATH: Final[Path] = _resolve_path("SYSTEM_DB_PATH", "logs/system.db")
VANNA_DATA_DIR: Final[Path] = _resolve_path("VANNA_DATA_DIR", "vanna_data")

# 向后兼容：保留旧的路径配置（如果环境变量中设置了，则使用旧路径）
MEMORY_DB_PATH: Final[Path] = _resolve_path("MEMORY_DB_PATH", str(SYSTEM_DB_PATH))
KNOWLEDGE_DB_PATH: Final[Path] = _resolve_path("KNOWLEDGE_DB_PATH", str(SYSTEM_DB_PATH))

DEEPSEEK_API_KEY: Final[str] = _require_env("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL: Final[str] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL: Final[str] = os.getenv(
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com",
)

