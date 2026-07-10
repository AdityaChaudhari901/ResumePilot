import os
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.services.hashing import sha256_bytes

MAX_DOCX_ENTRIES = 1_000
MAX_DOCX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 200


class StoredUpload:
    def __init__(
        self,
        *,
        original_name: str,
        extension: str,
        content_type: str | None,
        content: bytes,
        file_hash: str,
        stored_path: Path,
    ) -> None:
        self.original_name = original_name
        self.extension = extension
        self.content_type = content_type
        self.content = content
        self.file_hash = file_hash
        self.stored_path = stored_path


async def store_resume_upload(
    file: UploadFile,
    settings: Settings,
    *,
    owner_namespace: str | None = None,
) -> StoredUpload:
    original_name = Path(file.filename or "resume").name
    extension = Path(original_name).suffix.lower()
    if extension not in settings.allowed_resume_extensions:
        allowed = ", ".join(sorted(settings.allowed_resume_extensions))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported resume file type. Allowed extensions: {allowed}",
        )

    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Resume upload exceeds {settings.max_upload_bytes} bytes",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Resume upload is empty"
        )
    _validate_resume_content(content, extension)

    file_hash = sha256_bytes(content)
    upload_dir = _upload_dir_for_owner(settings, owner_namespace)
    stored_path = upload_dir / f"{file_hash}{extension}"

    return StoredUpload(
        original_name=original_name,
        extension=extension,
        content_type=file.content_type,
        content=content,
        file_hash=file_hash,
        stored_path=stored_path,
    )


def persist_resume_upload(upload: StoredUpload) -> bool:
    """Persist a validated upload atomically; return whether a new file was created."""
    if upload.stored_path.exists():
        return False
    upload.stored_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=upload.stored_path.parent,
            prefix=".resume-upload-",
            delete=False,
        ) as temporary_file:
            temporary_file.write(upload.content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        temporary_path.chmod(0o600)
        os.replace(temporary_path, upload.stored_path)
        return True
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _validate_resume_content(content: bytes, extension: str) -> None:
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF does not have a valid PDF signature",
        )
    if extension == ".docx":
        _validate_docx_archive(content)
    if extension in {".txt", ".md", ".markdown"} and b"\x00" in content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text resume contains invalid binary data",
        )


def _validate_docx_archive(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded DOCX is missing required document parts",
                )
            if len(entries) > MAX_DOCX_ENTRIES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded DOCX contains too many archive entries",
                )
            total_uncompressed = sum(entry.file_size for entry in entries)
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded DOCX expands beyond the safe processing limit",
                )
            for entry in entries:
                if entry.file_size <= 1024 * 1024:
                    continue
                compressed_size = max(entry.compress_size, 1)
                if entry.file_size / compressed_size > MAX_DOCX_COMPRESSION_RATIO:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded DOCX has an unsafe compression ratio",
                    )
    except BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded DOCX is not a valid Office document",
        ) from exc


def _upload_dir_for_owner(settings: Settings, owner_namespace: str | None) -> Path:
    if not owner_namespace:
        return settings.upload_dir
    safe_namespace = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in owner_namespace.strip()
    )
    return settings.upload_dir / "users" / (safe_namespace or "unknown")
