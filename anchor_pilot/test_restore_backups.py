"""Restoration must preserve local work and reject corrupt or unsafe archives."""
import hashlib
import io
import tarfile

import pytest

from .restore_backups import digest, restore


def make_archive(tmp_path, name='anchor_pilot/outputs/run/value.txt', data=b'saved result'):
    archive = tmp_path / 'bundle.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        info = tarfile.TarInfo(name); info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    spec = {'bytes': archive.stat().st_size, 'sha256': digest(archive), 'files': {
        name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}}
    return archive, spec


def test_restore_is_repeatable_and_preserves_conflicts(tmp_path):
    archive, spec = make_archive(tmp_path)
    root = tmp_path / 'checkout'
    assert restore(archive, spec, root, verify_only=True)['restored'] == 0
    assert not root.exists()
    assert restore(archive, spec, root)['restored'] == 1
    assert restore(archive, spec, root)['already_present'] == 1
    target = root / next(iter(spec['files']))
    target.write_bytes(b'local changes')
    with pytest.raises(FileExistsError):
        restore(archive, spec, root)
    assert target.read_bytes() == b'local changes'


def test_rejects_corrupt_archive_before_writing(tmp_path):
    archive, spec = make_archive(tmp_path)
    archive.write_bytes(archive.read_bytes() + b'corruption')
    root = tmp_path / 'checkout'
    with pytest.raises(ValueError, match='checksum/size'):
        restore(archive, spec, root)
    assert not root.exists()


@pytest.mark.parametrize('name', ['../escaped.txt', '/absolute.txt', 'anchor_pilot/../../escaped.txt'])
def test_rejects_path_traversal(tmp_path, name):
    archive, spec = make_archive(tmp_path, name)
    with pytest.raises(ValueError, match='unsafe'):
        restore(archive, spec, tmp_path / 'checkout')


def test_rejects_destination_symlinks(tmp_path):
    archive, spec = make_archive(tmp_path)
    root = tmp_path / 'checkout'; root.mkdir()
    outside = tmp_path / 'outside'; outside.mkdir()
    (root / 'anchor_pilot').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symbolic link'):
        restore(archive, spec, root)
    assert not list(outside.iterdir())


def test_rejects_wrong_member_hash(tmp_path):
    archive, spec = make_archive(tmp_path)
    spec['files'][next(iter(spec['files']))]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='Member checksum'):
        restore(archive, spec, tmp_path / 'checkout')
