from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from routers.files import FileAction, file_action, upload_file


ADMIN = {"id": 1, "role": "admin"}


@pytest.fixture(autouse=True)
def registered_root_stub(monkeypatch):
    async def allow_test_path(path):
        return Path(path).resolve()

    monkeypatch.setattr("routers.files.ensure_registered_path", allow_test_path)


@pytest.mark.asyncio
async def test_file_lifecycle_in_unprotected_directory(tmp_path):
    directory = tmp_path / "managed"
    await file_action(FileAction(action="mkdir", path=str(directory)), ADMIN)

    source = directory / "source.txt"
    source.write_text("pi-control", encoding="ascii")
    copied = directory / "copied.txt"
    await file_action(
        FileAction(action="copy", path=str(source), destination=str(copied)),
        ADMIN,
    )
    assert copied.read_text(encoding="ascii") == "pi-control"

    await file_action(
        FileAction(action="rename", path=str(copied), new_name="renamed.txt"),
        ADMIN,
    )
    renamed = directory / "renamed.txt"
    assert renamed.exists()

    await file_action(FileAction(action="delete", path=str(renamed)), ADMIN)
    assert not renamed.exists()


@pytest.mark.asyncio
async def test_protected_path_preserves_forbidden_status():
    with pytest.raises(HTTPException) as exc_info:
        await file_action(FileAction(action="delete", path="/etc/passwd"), ADMIN)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_symlink_to_protected_path_is_rejected(tmp_path):
    link = tmp_path / "etc-link"
    link.symlink_to("/etc", target_is_directory=True)

    with pytest.raises(HTTPException) as exc_info:
        await file_action(FileAction(action="delete", path=str(link)), ADMIN)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_upload_rejects_path_traversal_filename(tmp_path):
    upload = UploadFile(filename="../escape.txt", file=BytesIO(b"blocked"))

    with pytest.raises(HTTPException) as exc_info:
        await upload_file(str(tmp_path), [upload], ADMIN)

    assert exc_info.value.status_code == 400
    assert not (tmp_path.parent / "escape.txt").exists()


@pytest.mark.asyncio
async def test_upload_refuses_existing_file_without_overwriting(tmp_path):
    target = tmp_path / 'keep.txt'
    target.write_bytes(b'original')
    with pytest.raises(HTTPException) as error:
        await upload_file(str(tmp_path), [UploadFile(filename='keep.txt', file=BytesIO(b'replaced'))], ADMIN)
    assert error.value.status_code == 409
    assert target.read_bytes() == b'original'


@pytest.mark.asyncio
async def test_upload_does_not_follow_existing_symlink(tmp_path):
    outside = tmp_path / 'outside.txt'
    outside.write_bytes(b'original')
    directory = tmp_path / 'managed'
    directory.mkdir()
    (directory / 'link.txt').symlink_to(outside)
    with pytest.raises(HTTPException):
        await upload_file(str(directory), [UploadFile(filename='link.txt', file=BytesIO(b'replaced'))], ADMIN)
    assert outside.read_bytes() == b'original'


@pytest.mark.asyncio
async def test_interrupted_upload_removes_only_its_partial_file(tmp_path):
    class InterruptedFile(BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise OSError('Transfer interrupted')
            return super().read(2)
    with pytest.raises(HTTPException):
        await upload_file(str(tmp_path), [UploadFile(filename='partial.txt', file=InterruptedFile(b'abcdef'))], ADMIN)
    assert not (tmp_path / 'partial.txt').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['copy', 'move', 'rename'])
async def test_destination_conflicts_preserve_both_files(tmp_path, operation):
    source, target = tmp_path / 'source.txt', tmp_path / 'target.txt'
    source.write_text('source')
    target.write_text('target')
    action = FileAction(action=operation, path=str(source), destination=str(target), new_name=target.name)
    with pytest.raises(HTTPException) as error:
        await file_action(action, ADMIN)
    assert error.value.status_code == 409
    assert source.read_text() == 'source'
    assert target.read_text() == 'target'


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['.', '..', 'a/b', ''])
async def test_rename_rejects_invalid_names(tmp_path, name):
    source = tmp_path / 'source.txt'
    source.write_text('source')
    with pytest.raises(HTTPException) as error:
        await file_action(FileAction(action='rename', path=str(source), new_name=name), ADMIN)
    assert error.value.status_code == 400
    assert source.read_text() == 'source'


@pytest.mark.asyncio
async def test_copy_directory_rejects_links_without_reading_outside_files(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('private')
    (source / 'link.txt').symlink_to(outside)
    target = tmp_path / 'target'
    with pytest.raises(HTTPException) as error:
        await file_action(FileAction(action='copy', path=str(source), destination=str(target)), ADMIN)
    assert error.value.status_code == 403
    assert not target.exists()


@pytest.mark.parametrize('operation', ['mkdir', 'delete', 'move', 'copy'])
def test_file_actions_reject_a_swapped_parent_symlink(tmp_path, operation):
    from routers.files import perform_file_action
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep.txt').write_text('private')
    parent = tmp_path / 'registered'
    parent.symlink_to(outside, target_is_directory=True)
    source = parent / ('new' if operation == 'mkdir' else 'keep.txt')
    with pytest.raises(OSError):
        perform_file_action(operation, str(source), str(tmp_path / 'target') if operation in {'move', 'copy'} else None)
    assert (outside / 'keep.txt').read_text() == 'private'
    assert not (outside / 'new').exists()
    assert not (tmp_path / 'target').exists()


@pytest.mark.parametrize('operation', ['move', 'rename'])
def test_competing_destination_creation_never_overwrites(tmp_path, monkeypatch, operation):
    from routers.files import perform_file_action
    import os
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.write_text('source')
    original = os.path.lexists
    def competing_create(path):
        if path == str(target):
            target.write_text('concurrent user data')
            return False
        return original(path)
    monkeypatch.setattr(os.path, 'lexists', competing_create)
    with pytest.raises(FileExistsError):
        perform_file_action(operation, str(source), str(target))
    assert target.read_text() == 'concurrent user data'
    assert source.read_text() == 'source'
