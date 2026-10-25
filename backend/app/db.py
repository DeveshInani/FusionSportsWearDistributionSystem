from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

DATABASE_URL = settings.DATABASE_URL
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif DATABASE_URL.startswith("mysql") and settings.DATABASE_SSL_REQUIRED:
    connect_args["ssl"] = {"check_hostname": True, "verify_mode": "required"}
    if settings.DATABASE_SSL_CA:
        ca_path = Path(settings.DATABASE_SSL_CA.replace("\\", "/"))
        if not ca_path.is_absolute():
            ca_path = Path(__file__).resolve().parents[1] / ca_path
        if not ca_path.is_file():
            raise FileNotFoundError(f"DATABASE_SSL_CA file does not exist: {ca_path}")
        connect_args["ssl"]["ca"] = str(ca_path)
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401

    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    legacy_tables = set(Base.metadata.tables) - {"email_logs"}
    with engine.connect() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        version_table_is_empty = (
            inspector.has_table("alembic_version")
            and connection.execute(text("SELECT version_num FROM alembic_version")).first()
            is None
        )
    if (
        ("alembic_version" not in existing_tables or version_table_is_empty)
        and legacy_tables.issubset(existing_tables)
    ):
        from alembic.script import ScriptDirectory

        base_revision = ScriptDirectory.from_config(config).get_base()
        if base_revision is None:
            raise RuntimeError("Alembic has no base revision to stamp.")
        command.stamp(config, base_revision)
    command.upgrade(config, "head")
