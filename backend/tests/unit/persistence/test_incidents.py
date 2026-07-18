from backend.persistence.incidents import IncidentsStore


def _entry(i=0):
    return {"category": "hazard", "description": f"tree down {i}",
            "location": "5th and Main", "reporter": "Ben", "ts": f"2026-07-17T09:0{i}:00Z"}


def test_add_assigns_id_and_prepends(tmp_path):
    s = IncidentsStore(str(tmp_path / "incidents.json"))
    a = s.add(_entry(0)); b = s.add(_entry(1))
    assert a["id"] != b["id"]
    assert [e["description"] for e in s.list()][:2] == ["tree down 1", "tree down 0"]


def test_persists_across_reload(tmp_path):
    p = str(tmp_path / "incidents.json")
    IncidentsStore(p).add(_entry())
    assert IncidentsStore(p).list()[0]["category"] == "hazard"


def test_caps_at_500(tmp_path):
    s = IncidentsStore(str(tmp_path / "incidents.json"))
    for i in range(505):
        s.add({**_entry(), "description": str(i)})
    lst = s.list()
    assert len(lst) == 500 and lst[0]["description"] == "504"


def test_corrupt_file_recovers_empty(tmp_path):
    p = tmp_path / "incidents.json"; p.write_text("{not json")
    assert IncidentsStore(str(p)).list() == []
