import os
import sys
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/forecast_dcic"
).replace("postgresql+asyncpg", "postgresql+psycopg2")

# Importar todos los modelos ORM para que autogenerate los detecte
_backend = os.path.dirname(os.path.dirname(__file__))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from database import Base
import models.models               # Producto, Venta, Stock, etc.
import forecast.models.forecast_models  # tablas forecast dinámico

# Stub para tablas raw-SQL referenciadas por FK en el ORM
from sqlalchemy import Table, Column, Integer, String
Table("usuarios", Base.metadata,
      Column("id", Integer, primary_key=True),
      Column("email", String(200)),
      extend_existing=True)

target_metadata = Base.metadata

# Tablas gestionadas fuera del ORM (raw SQL) — excluir de autogenerate
_TABLAS_EXCLUIDAS = {
    "usuarios", "roles", "forecast", "forecast_2027", "forecast_snapshots",
    "forecast_snapshot_filas", "forecast_intervalos", "forecast_metricas",
    "forecast_hw_2027", "alembic_version",
}


def include_object(object, name, type_, reflected, compare_to):
    """Excluye tablas no-ORM del autogenerate para evitar falsos cambios."""
    if type_ == "table" and name in _TABLAS_EXCLUIDAS:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
