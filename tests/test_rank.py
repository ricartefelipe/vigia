from vigia.bm25 import build_stats
from vigia.fusion import rrf


def test_termo_raro_tem_idf_maior():
    _vocab, idf, avgdl = build_stats([["alfa", "beta"], ["alfa"]])
    assert idf["beta"] > idf["alfa"]
    assert avgdl == 1.5


def test_rrf_prefere_item_que_aparece_no_topo_das_duas_listas():
    ordered = rrf([["a", "b"], ["a", "c"]])
    assert ordered[0] == "a"
