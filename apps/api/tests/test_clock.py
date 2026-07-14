import datetime

from app.clock import IST, now_ist, today_ist


def test_ist_is_utc_plus_530():
    assert IST.utcoffset(None) == datetime.timedelta(hours=5, minutes=30)


def test_now_ist_is_utc_shifted_naive():
    utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    delta = now_ist() - utc
    assert abs(delta - datetime.timedelta(hours=5, minutes=30)) < datetime.timedelta(seconds=5)
    assert now_ist().tzinfo is None  # naive, matching the DateTime columns
    assert today_ist() == datetime.datetime.now(IST).date()
