import os
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import inspect

# ----------------------------------------------------
# 1. PATH TO EXISTING DB 
# ----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_PATH = os.path.join(BASE_DIR, "invoice_agent_data", "invoices.db")

# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

# ----------------------------------------------------
# 2. CREATE ENGINE (SQLite settings)
# ----------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  
)

# ----------------------------------------------------
# 3. SESSION FACTORY
# ----------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ----------------------------------------------------
# 4. BASE CLASS FOR ALL MODELS
# ----------------------------------------------------
Base = declarative_base()


# ----------------------------------------------------
# 5. DEPENDENCY FOR FASTAPI
# ----------------------------------------------------
def get_db():
    """
    FastAPI dependency — yields a DB session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ----------------------------------------------------
# 6. AUTO-MIGRATION LOGIC FOR SQLITE
# ----------------------------------------------------
def table_exists(table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migrations():
    """
    Performs minimal SQLite migrations:
    - If table doesn't exist → create it.
    - If columns missing → ADD COLUMN.

    This avoids FULL schema rebuild (not safe for SQLite).
    """

    from apps.api.models.invoice_model import Invoice  

    model = Invoice

    # If table does not exist: CREATE ALL
    if not table_exists(model.__tablename__):
        print(f"[DB] Creating table: {model.__tablename__}")
        Base.metadata.create_all(bind=engine)
        return

    # If exists → check & migrate missing columns
    inspector = inspect(engine)
    existing_cols = [col["name"] for col in inspector.get_columns(model.__tablename__)]

    for col_name, col_obj in model.__table__.columns.items():
        if col_name not in existing_cols:
            col_type = col_obj.type.compile(engine.dialect)
            alter = f"ALTER TABLE {model.__tablename__} ADD COLUMN {col_name} {col_type}"
            print(f"[DB][MIGRATION] {alter}")
            with engine.connect() as conn:
                conn.execute(text(alter))

    print("[DB] Migration complete (SQLite-safe).")