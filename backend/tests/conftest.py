"""Hermetic test configuration loaded before application modules are imported."""
from pathlib import Path
import os

TEST_ROOT = Path(__file__).resolve().parent
TEST_DB = TEST_ROOT / "test.db"
TEST_MEDIA = TEST_ROOT / "test-media"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-abcdefghijklmnopqrstuvwxyz"
os.environ["COOKIE_SECURE"] = "false"
os.environ["MEDIA_ROOT"] = str(TEST_MEDIA)
os.environ["MEDIA_STORAGE_PROVIDER"] = "local"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = ""
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["COMPANY_ADDRESS"] = "Hyderabad, Telangana"
