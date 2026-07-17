from engine.curriculum.progress import ProgressStore


def test_mark_complete_dedupes_and_sets_last(tmp_path):
    path = tmp_path / "progress.json"
    store = ProgressStore(str(path))
    store.mark_complete("id-a")
    store.mark_complete("id-a")
    store.mark_complete("id-b")
    state = store.load()
    assert state.completed == ["id-a", "id-b"]
    assert state.last_lesson_id == "id-b"
    assert state.updated_at


def test_corrupt_file_backed_up_and_reset(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text("{not json", encoding="utf-8")
    store = ProgressStore(str(path))
    state = store.load()
    assert state.completed == []
    assert (tmp_path / "progress.json.bak").exists()
