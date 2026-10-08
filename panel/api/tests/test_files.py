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
