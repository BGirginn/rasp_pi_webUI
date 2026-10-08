import os


# Every temporary test database must use an explicit non-production seed.
os.environ.setdefault(
    "DEFAULT_ADMIN_PASSWORD",
    "test-only-bootstrap-password-never-use-in-production",
)
