from pokedo.data import sync


def test_queue_and_get(tmp_path, monkeypatch):
    # Use a temp sqlite file to avoid touching user's DB
    db_file = tmp_path / "test_pokedo.db"
    monkeypatch.setenv("POKEDO_DATABASE_URL", f"sqlite:///{db_file}")

    # Re-import module to pick up env override
    import importlib

    importlib.reload(sync)

    sync.init_changes_table()
    cid = sync.queue_change("task-1", "task", "CREATE", {"title": "test"})
    assert cid is not None
    unsynced = sync.get_unsynced_changes()
    assert len(unsynced) == 1
    assert unsynced[0].entity_id == "task-1"

    # mark synced
    sync.mark_synced([cid])
    unsynced2 = sync.get_unsynced_changes()
    assert len(unsynced2) == 0
