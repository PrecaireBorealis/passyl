import numpy as np

from app.engine.pooling import pooled


def test_no_shop_samples_equals_peer_mean():
    r = pooled([], [-0.10, -0.12, -0.14])
    assert abs(r["mean"] - (-12.0)) < 1e-9


def test_large_shop_sample_close_to_shop_mean():
    shop = list(np.random.default_rng(0).normal(-0.30, 0.02, 400))
    assert abs(pooled(shop, [-0.10] * 50)["mean"] - (-30.0)) < 1.0
