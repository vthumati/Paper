"""The platform clock: every recorded time is IST (UTC+05:30), uniformly,
regardless of the server's timezone (dev boxes vary; Cloud Run is UTC).

Columns are naive DateTime/Date, so we store naive IST wall-clock values.
Use these helpers instead of datetime.now() / date.today() anywhere a
timestamp or "today" is recorded or compared.

Exception: JWT exp/iat (app/security.py) stay UTC — token lifetimes are
epoch-based per RFC 7519, not user-facing recorded times.
"""
import datetime

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")


def now_ist() -> datetime.datetime:
    """Current IST wall-clock, naive (matches the naive DateTime columns)."""
    return datetime.datetime.now(IST).replace(tzinfo=None)


def today_ist() -> datetime.date:
    """Today's date in IST."""
    return datetime.datetime.now(IST).date()
