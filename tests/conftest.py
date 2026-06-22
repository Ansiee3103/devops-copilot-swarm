import os
import pytest

os.environ["APP_ENV"]      = "testing"
os.environ["DATABASE_URL"] = "sqlite:///database/test.db"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["SECRET_KEY"]   = "test-secret-key-32-chars-minimum!"
os.environ["REDIS_HOST"]   = "localhost"

@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    """Create fresh test database once per session"""
    os.makedirs("database", exist_ok=True)

    # Delete old test db
    if os.path.exists("database/test.db"):
        os.remove("database/test.db")

    from backend.database import create_tables
    create_tables()

    # Create admin with BCRYPT hash
    from backend.database import SessionLocal
    from backend.repositories.user_repo import UserRepository
    db   = SessionLocal()
    repo = UserRepository(db)
    repo.create_admin_if_not_exists()
    db.close()

    yield

    # Cleanup
    if os.path.exists("database/test.db"):
        try:
            os.remove("database/test.db")
        except:
            pass