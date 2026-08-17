from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialise la base de données.

    Priorité :
    - exécuter les migrations Alembic
    Fallback (dev) :
    - si le schéma existe déjà (ou migrations non appliquées), on conserve un comportement sûr en retombant sur create_all.
    """

    def run_alembic_upgrade() -> None:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        alembic_ini_path = (  # backend/alembic.ini
            __import__("pathlib").Path(__file__).resolve().parents[2] / "alembic.ini"
        )
        cfg = AlembicConfig(str(alembic_ini_path))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")

    try:
        run_alembic_upgrade()
    except Exception:
        # Fallback : ancien MVP / DB déjà initialisée.
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        from app.models import Base

        Base.metadata.create_all(bind=engine)
