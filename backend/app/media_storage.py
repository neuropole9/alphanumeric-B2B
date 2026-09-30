from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import re

from .config import settings


@dataclass(frozen=True)
class StoredMedia:
    file_id: str
    parent_id: str
    storage_key: str
    size: int
    checksum: str


class MediaStorageProvider(ABC):
    @abstractmethod
    def upload(self, data: bytes, *, filename: str, workspace: str, product_folder: str, mime_type: str) -> StoredMedia: ...
    @abstractmethod
    def open(self, file_id: str, storage_key: str) -> BytesIO: ...
    @abstractmethod
    def delete(self, file_id: str, storage_key: str) -> None: ...
    @abstractmethod
    def exists(self, file_id: str, storage_key: str) -> bool: ...
    def quota(self) -> dict: return {"usage": None, "limit": None, "percent": None}


def safe_component(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return (value or "file")[:120]


class LocalMediaStorageProvider(MediaStorageProvider):
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.media_root).resolve()

    def upload(self, data: bytes, *, filename: str, workspace: str, product_folder: str, mime_type: str) -> StoredMedia:
        digest = hashlib.sha256(data).hexdigest()
        folder = self.root / safe_component(workspace.lower()) / safe_component(product_folder)
        folder.mkdir(parents=True, exist_ok=True)
        stored = f"{digest[:16]}-{safe_component(filename)}"
        path = (folder / stored).resolve()
        if self.root not in path.parents: raise ValueError("Unsafe media path")
        path.write_bytes(data)
        return StoredMedia(str(path.relative_to(self.root)), str(folder.relative_to(self.root)), str(path.relative_to(self.root)), len(data), digest)

    def open(self, file_id: str, storage_key: str) -> BytesIO:
        path = (self.root / storage_key).resolve()
        if self.root not in path.parents or not path.is_file(): raise FileNotFoundError(storage_key)
        return BytesIO(path.read_bytes())

    def delete(self, file_id: str, storage_key: str) -> None:
        path = (self.root / storage_key).resolve()
        if self.root in path.parents and path.is_file(): path.unlink()

    def exists(self, file_id: str, storage_key: str) -> bool:
        path = (self.root / storage_key).resolve()
        return self.root in path.parents and path.is_file()


class GoogleDriveMediaStorageProvider(MediaStorageProvider):
    def __init__(self, service=None):
        if service is not None:
            self.service = service
            return
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        required = [settings.google_drive_client_id, settings.google_drive_client_secret,
                    settings.google_drive_refresh_token, settings.google_drive_root_folder_id]
        if not all(required): raise RuntimeError("Google Drive media configuration is incomplete")
        credentials = Credentials(None, refresh_token=settings.google_drive_refresh_token,
            token_uri="https://oauth2.googleapis.com/token", client_id=settings.google_drive_client_id,
            client_secret=settings.google_drive_client_secret,
            scopes=["https://www.googleapis.com/auth/drive.file"])
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _folder(self, name: str, parent: str) -> str:
        from googleapiclient.http import MediaIoBaseUpload
        query = f"name='{name.replace(chr(39), '')}' and '{parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        rows = self.service.files().list(q=query, spaces="drive", fields="files(id)", pageSize=1).execute().get("files", [])
        if rows: return rows[0]["id"]
        return self.service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}, fields="id").execute()["id"]

    def upload(self, data: bytes, *, filename: str, workspace: str, product_folder: str, mime_type: str) -> StoredMedia:
        from googleapiclient.http import MediaIoBaseUpload
        root = settings.google_drive_root_folder_id or ""
        application_folder = self._folder(safe_component(workspace.lower()), root)
        parent = self._folder(safe_component(product_folder), application_folder)
        media = MediaIoBaseUpload(BytesIO(data), mimetype=mime_type, resumable=True)
        row = self.service.files().create(body={"name": safe_component(filename), "parents": [parent]}, media_body=media, fields="id,size,md5Checksum").execute()
        digest = hashlib.sha256(data).hexdigest()
        return StoredMedia(row["id"], parent, row["id"], len(data), digest)

    def open(self, file_id: str, storage_key: str) -> BytesIO:
        from googleapiclient.http import MediaIoBaseDownload
        target = BytesIO(); request = self.service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(target, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        target.seek(0); return target

    def delete(self, file_id: str, storage_key: str) -> None:
        self.service.files().delete(fileId=file_id).execute()

    def exists(self, file_id: str, storage_key: str) -> bool:
        try:
            self.service.files().get(fileId=file_id, fields="id,trashed").execute(); return True
        except Exception: return False

    def quota(self) -> dict:
        about = self.service.about().get(fields="storageQuota").execute().get("storageQuota", {})
        usage, limit = int(about.get("usage", 0)), int(about.get("limit", 0) or 0)
        return {"usage": usage, "limit": limit or None, "percent": round(usage * 100 / limit, 2) if limit else None}


def get_media_provider(provider_name: str | None = None) -> MediaStorageProvider:
    """Resolve the provider recorded on the media row.

    Passing the stored provider is essential during a local-to-Drive migration:
    changing the production default must not make legacy local files unreadable.
    """
    provider = (provider_name or settings.media_storage_provider).lower()
    if provider == "google_drive": return GoogleDriveMediaStorageProvider()
    if provider != "local": raise RuntimeError(f"Unsupported media storage provider: {provider}")
    return LocalMediaStorageProvider()
