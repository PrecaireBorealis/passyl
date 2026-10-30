from app.engine.peer_shock import split


def test_toy_world_split():
    # all peers drop 10%, the shop drops 15% → market −10, shop −5
    r = split(-0.15, [-0.10] * 12)
    assert r["market_pct"] == -10.0
    assert r["shop_pct"] == -5.0


def test_too_few_peers():
    assert split(-0.15, [-0.1] * 9)["state"] == "no_peers"
