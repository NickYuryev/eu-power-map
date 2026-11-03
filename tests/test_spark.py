from ingest.spark import compute_clean_dark


def test_positive_and_negative_spread():
    # fuel cost = 0.49*90 + 0.37*72.5 = 44.1 + 26.825 = 70.925
    out = compute_clean_dark([120.0, 50.0, None], ttf=90.0, eua=72.5)
    assert out[0] == 120.0 - 70.925  # positive margin
    assert out[1] == 50.0 - 70.925   # negative margin
    assert out[2] is None
    assert out[0] > 0 > out[1]
