from pathlib import Path

import pytest

from app.config import settings
from app.media_storage import GoogleDriveMediaStorageProvider, LocalMediaStorageProvider


class Reply:
    def __init__(self, value=None, error=None): self.value, self.error = value, error
    def execute(self):
        if self.error: raise self.error
        return self.value


class FakeFiles:
    def __init__(self): self.folder_number = 0; self.deleted = []; self.missing = False
    def list(self, **kwargs): return Reply({"files": []})
    def create(self, body, **kwargs):
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            self.folder_number += 1
            return Reply({"id": f"folder-{self.folder_number}"})
        return Reply({"id": "drive-file-1", "size": "7", "md5Checksum": "unused"})
    def get(self, **kwargs):
        return Reply(error=RuntimeError("missing")) if self.missing else Reply({"id": kwargs["fileId"], "trashed": False})
    def get_media(self, **kwargs): return object()
    def delete(self, **kwargs): self.deleted.append(kwargs["fileId"]); return Reply({})


class FakeAbout:
    def get(self, **kwargs): return Reply({"storageQuota": {"usage": "75", "limit": "100"}})


class FakeDrive:
    def __init__(self): self.file_api = FakeFiles()
    def files(self): return self.file_api
    def about(self): return FakeAbout()


def test_local_provider_success_missing_and_path_safety(tmp_path: Path):
    provider = LocalMediaStorageProvider(tmp_path)
    stored = provider.upload(b"content", filename="../safe.webp", workspace="LIGHTING", product_folder="family_1", mime_type="image/webp")
    assert stored.size == 7 and provider.exists(stored.file_id, stored.storage_key)
    assert provider.open(stored.file_id, stored.storage_key).read() == b"content"
    provider.delete(stored.file_id, stored.storage_key)
    assert not provider.exists(stored.file_id, stored.storage_key)
    with pytest.raises(FileNotFoundError): provider.open(stored.file_id, stored.storage_key)


def test_google_drive_provider_success_delete_quota_and_missing(monkeypatch):
    drive = FakeDrive(); provider = GoogleDriveMediaStorageProvider(drive)
    monkeypatch.setattr(settings, "google_drive_root_folder_id", "root-id")
    stored = provider.upload(b"content", filename="image.webp", workspace="AUTOMATION", product_folder="fan_1", mime_type="image/webp")
    assert (stored.file_id, stored.parent_id, stored.size) == ("drive-file-1", "folder-2", 7)
    assert provider.exists(stored.file_id, stored.storage_key)
    assert provider.quota() == {"usage": 75, "limit": 100, "percent": 75.0}
    provider.delete(stored.file_id, stored.storage_key)
    assert drive.file_api.deleted == ["drive-file-1"]
    drive.file_api.missing = True
    assert not provider.exists(stored.file_id, stored.storage_key)


def test_google_drive_provider_propagates_retryable_upload_failure(monkeypatch):
    drive = FakeDrive(); provider = GoogleDriveMediaStorageProvider(drive)
    monkeypatch.setattr(settings, "google_drive_root_folder_id", "root-id")
    monkeypatch.setattr(drive.file_api, "create", lambda *args, **kwargs: Reply(error=RuntimeError("temporary Drive failure")))
    with pytest.raises(RuntimeError, match="temporary Drive failure"):
        provider.upload(b"content", filename="image.webp", workspace="LIGHTING", product_folder="light_1", mime_type="image/webp")
