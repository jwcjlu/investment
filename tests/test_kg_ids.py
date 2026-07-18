from engine.curriculum.kg_ids import make_node_id, make_edge_id


def test_node_id_stable_and_alias_aware(tmp_path):
    alias_path = tmp_path / "kg_aliases.json"
    alias_path.write_text('{"ROIC": "投资资本回报率"}', encoding="utf-8")
    a = make_node_id("ROIC", aliases_path=str(alias_path))
    b = make_node_id("投资资本回报率", aliases_path=str(alias_path))
    assert a == b
    assert a.startswith("n_")


def test_edge_id_stable():
    e1 = make_edge_id("n_aaa", "causes", "n_bbb")
    e2 = make_edge_id("n_aaa", "causes", "n_bbb")
    assert e1 == e2 and e1.startswith("e_")
