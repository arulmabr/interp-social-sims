from pathlib import Path
from types import SimpleNamespace
import pytest
from label_pilot import cache


def fixture_snapshot(tmp_path):
    durable=tmp_path/'durable'; repo=durable/'model'; snap=repo/'snapshots/revision'
    snap.mkdir(parents=True); (repo/'blobs').mkdir()
    (repo/'blobs/weight-hash').write_bytes(b'checkpoint-data')
    (snap/'model.safetensors').symlink_to('../../blobs/weight-hash')
    (snap/'config.json').write_text('{}')
    return durable,snap


def test_ram_cache_preserves_snapshot_links_and_reuses_complete_files(tmp_path):
    durable,snap=fixture_snapshot(tmp_path); ram=tmp_path/'ram'
    first=cache.stage(durable,[snap],ram,reserve_bytes=0)
    assert first['copied_bytes']==17
    assert (ram/'hub/model/snapshots/revision/model.safetensors').read_bytes()==b'checkpoint-data'
    second=cache.stage(durable,[snap],ram,reserve_bytes=0)
    assert second['copied_bytes']==0
    assert (ram/'READY').is_file()


def test_ram_cache_fails_before_copy_if_space_is_insufficient(tmp_path,monkeypatch):
    durable,snap=fixture_snapshot(tmp_path); ram=tmp_path/'ram'
    monkeypatch.setattr(cache.shutil,'disk_usage',lambda _:SimpleNamespace(free=0))
    with pytest.raises(RuntimeError,match='RAM cache needs'):
        cache.stage(durable,[snap],ram,reserve_bytes=0)
    assert not (ram/'READY').exists()


def test_ram_cache_refuses_snapshot_link_outside_durable_cache(tmp_path):
    durable,snap=fixture_snapshot(tmp_path)
    external=tmp_path/'unrelated'; external.write_bytes(b'not a checkpoint')
    (snap/'bad-link').symlink_to(external)
    with pytest.raises(ValueError):
        cache.stage(durable,[snap],tmp_path/'ram',reserve_bytes=0)
