import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy import create_engine

from alembic import context

# Load models
from apps.api.core.db import Base
from apps.api.models.user_model import User
from apps.api.models.company_model import Company
from apps.api.models.invoice_model import Invoice

# Alembic Config object
config = context.config

# Interpret alembic.ini for logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point to the absolute SQLite database path
target_metadata = Base.metadata

DATABASE_URL = "sqlite:////Users/farhanmohamed/CS_Projects/invoice_agent/invoice_agent_data/invoices.db"

def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()