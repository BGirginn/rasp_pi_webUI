import io
import tarfile

import pytest


def test_project_parent_allowlist_rejects_sibling(tmp_path):
    from services.project_service import ensure_within

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    with pytest.raises(ValueError):
        ensure_within(tmp_path / "sibling", [allowed])


def test_project_snapshot_extraction_rejects_traversal(tmp_path):
    from services.project_service import ProjectService

    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"unsafe"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with tarfile.open(archive_path, "r:gz") as archive:
        with pytest.raises(ValueError):
            ProjectService._safe_extract(archive, tmp_path / "target")


def test_audit_hash_changes_when_event_is_modified():
    from services.audit_chain import event_hash

    row = {
        "id": 1, "user_id": 1, "action": "login", "resource_id": None,
        "resource_type": None, "details": None, "result": None,
        "ip_address": "127.0.0.1", "user_agent": "test", "created_at": "2026-01-01",
    }
    original = event_hash(row, "0" * 64)
    row["action"] = "admin.delete"
    assert event_hash(row, "0" * 64) != original
