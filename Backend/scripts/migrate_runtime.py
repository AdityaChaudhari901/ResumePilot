from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_cached_settings
from app.services.langgraph_checkpointer import setup_postgres_checkpointer


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    command.upgrade(config, "head")
    setup_postgres_checkpointer(get_cached_settings())


if __name__ == "__main__":
    main()
