from __future__ import annotations

import os
import re
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

_STORAGE_KEY = re.compile(
    r"^(?P<prefix>[0-9a-f]{2})/"
    r"(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.pdf$"
)
_STAGING_KEY = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$"
)


class DocumentStorageError(Exception):
    pass


@dataclass(frozen=True)
class StagedDocumentDeletion:
    storage_key: str
    staging_key: str


class DocumentStorage(ABC):
    @abstractmethod
    def save(self, storage_key: str, content: bytes) -> None: ...

    @abstractmethod
    def open(self, storage_key: str) -> BinaryIO: ...

    @abstractmethod
    def delete(self, storage_key: str) -> None: ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool: ...

    @abstractmethod
    def stage_delete(self, storage_key: str) -> StagedDocumentDeletion: ...

    @abstractmethod
    def restore_delete(self, staged: StagedDocumentDeletion) -> None: ...

    @abstractmethod
    def finalize_delete(self, staged: StagedDocumentDeletion) -> None: ...


class LocalDocumentStorage(DocumentStorage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, storage_key: str, content: bytes) -> None:
        target = self._resolve(storage_key)
        temporary_path: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary_root = self.root / ".tmp"
            temporary_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=temporary_root, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, target)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise DocumentStorageError("Document storage write failed") from exc

    def open(self, storage_key: str) -> BinaryIO:
        try:
            return self._resolve(storage_key).open("rb")
        except OSError as exc:
            raise DocumentStorageError("Document storage open failed") from exc

    def delete(self, storage_key: str) -> None:
        try:
            self._resolve(storage_key).unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentStorageError("Document storage delete failed") from exc

    def exists(self, storage_key: str) -> bool:
        try:
            return self._resolve(storage_key).is_file()
        except OSError as exc:
            raise DocumentStorageError("Document storage check failed") from exc

    def stage_delete(self, storage_key: str) -> StagedDocumentDeletion:
        source = self._resolve(storage_key)
        staging_key = f"{uuid.uuid4()}.pdf"
        staged = self._resolve_staging(staging_key)
        try:
            staged.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, staged)
        except OSError as exc:
            raise DocumentStorageError("Document delete staging failed") from exc
        return StagedDocumentDeletion(storage_key=storage_key, staging_key=staging_key)

    def restore_delete(self, staged: StagedDocumentDeletion) -> None:
        source = self._resolve_staging(staged.staging_key)
        target = self._resolve(staged.storage_key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        except OSError as exc:
            raise DocumentStorageError("Document delete restoration failed") from exc

    def finalize_delete(self, staged: StagedDocumentDeletion) -> None:
        try:
            self._resolve_staging(staged.staging_key).unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentStorageError("Document delete finalization failed") from exc

    def _resolve(self, storage_key: str) -> Path:
        match = _STORAGE_KEY.fullmatch(storage_key)
        if match is None or not match.group("id").startswith(match.group("prefix")):
            raise DocumentStorageError("Invalid document storage key")
        return self.root / match.group("prefix") / f"{match.group('id')}.pdf"

    def _resolve_staging(self, staging_key: str) -> Path:
        if _STAGING_KEY.fullmatch(staging_key) is None:
            raise DocumentStorageError("Invalid document deletion staging key")
        return self.root / ".delete-staging" / staging_key
