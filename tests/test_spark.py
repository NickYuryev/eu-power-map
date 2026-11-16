from ingest.spark import compute_clean_spark


def test_positive_and_negative_spread():
    # fuel cost = 90/0.49 + 0.37*72.5 = 183.673... + 26.825 = 210.498...
    fuel = 90.0 / 0.49 + 0.37 * 72.5
    out = compute_clean_spark([250.0, 100.0, None], ttf=90.0, eua=72.5)
    assert out[0] == 250.0 - fuel  # positive margin
    assert out[1] == 100.0 - fuel  # negative margin
    assert out[2] is None
    assert out[0] > 0 > out[1]
