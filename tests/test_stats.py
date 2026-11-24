from ping_painel.stats import calc, quedas


def test_media_e_perda():
    r = calc([10.0, 20.0, None, 30.0])
    assert r["total"] == 4
    assert r["perdas"] == 1
    assert r["perda_pct"] == 25.0
    assert r["media"] == 20.0
    assert r["min"] == 10.0 and r["max"] == 30.0


def test_1pct_low_e_media_do_pior_1_porcento():
    # 200 pings: 198 de 10 ms e 2 de 500 ms -> pior 1% = 2 pings de 500
    r = calc([10.0] * 198 + [500.0, 500.0])
    assert r["low1"] == 500.0


def test_1pct_low_com_poucas_amostras_usa_o_pior_ping():
    assert calc([5.0, 7.0, 9.0])["low1"] == 9.0


def test_jitter():
    assert calc([10.0, 20.0, 10.0])["jitter"] == 10.0


def test_sem_respostas():
    r = calc([None, None])
    assert r["perda_pct"] == 100.0 and "media" not in r


def test_lista_vazia():
    assert calc([])["perda_pct"] == 0.0


def test_quedas_agrupa_perdas_seguidas():
    amostras = [(1, 10.0), (2, None), (3, None), (4, 11.0), (5, None)]
    assert quedas(amostras) == [(2, 3, 2), (5, 5, 1)]
