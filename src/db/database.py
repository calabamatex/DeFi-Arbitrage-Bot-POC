"""
Database connection and session management
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from src.config import config
from src.db.models import Base

# Create engine
engine = create_engine(
    config.db.url,
    poolclass=QueuePool,
    pool_size=config.db.pool_size,
    max_overflow=config.db.max_overflow,
    pool_pre_ping=True,  # Verify connections before using
    echo=config.db.echo,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Initialize database - create all tables
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully")


def drop_db() -> None:
    """
    Drop all tables (WARNING: DESTRUCTIVE)
    """
    Base.metadata.drop_all(bind=engine)
    print("⚠️  All database tables dropped")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session as context manager

    Usage:
        with get_db() as db:
            # Use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get database session (must be closed manually)

    Usage:
        db = get_db_session()
        try:
            # Use db session
            pass
        finally:
            db.close()
    """
    return SessionLocal()


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Set SQLite pragma for testing (if using SQLite)
    """
    if "sqlite" in config.db.url:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Health check
def check_db_connection() -> bool:
    """
    Check if database connection is healthy

    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Initialize database when run directly
    print("Initializing database...")

    # Check connection
    if check_db_connection():
        print("✅ Database connection successful")
    else:
        print("❌ Database connection failed")
        exit(1)

    # Create tables
    init_db()

    # Verify tables were created
    with get_db() as db:
        result = db.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
        )
        tables = [row[0] for row in result]

        print(f"\n✅ Created {len(tables)} tables:")
        for table in tables:
            print(f"   - {table}")
