import os
import tempfile

# Tests start the app, which creates tables in the configured database.
# Point that at a throwaway file so test runs never touch backend/easy_sched.db.
os.environ.setdefault("EASY_SCHED_DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))