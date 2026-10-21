"""Process-wide settings, database, and review service for the UI.

What it does: opens one SQLite store and one review service for the running app.
Who calls it: the Analyze callbacks and the interview callbacks.
What it returns: SETTINGS, STORE, and REVIEW.
"""

from careercrew.config import get_settings
from careercrew.review import PackageReviewService
from careercrew.session_store import SessionStore

SETTINGS = get_settings()
STORE = SessionStore(SETTINGS.db_path)
REVIEW = PackageReviewService(STORE)
