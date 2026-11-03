from datetime import date

from ingest.labels import hour_labels


def test_regular_day_is_24_hours():
    assert len(hour_labels(date(2026, 6, 15))) == 24


def test_spring_forward_is_23_hours():
    # Last Sunday of March in the EU.
    assert len(hour_labels(date(2026, 3, 29))) == 23


def test_fall_back_is_25_hours():
    # Last Sunday of October in the EU.
    assert len(hour_labels(date(2026, 10, 25))) == 25
