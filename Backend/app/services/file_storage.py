from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.services.hashing import sha256_bytes


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


async def store_resume_upload(file: UploadFile, settings: Settings) -> StoredUpload:
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

    file_hash = sha256_bytes(content)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = settings.upload_dir / f"{file_hash}{extension}"
    if not stored_path.exists():
        stored_path.write_bytes(content)

    return StoredUpload(
        original_name=original_name,
        extension=extension,
        content_type=file.content_type,
        content=content,
        file_hash=file_hash,
        stored_path=stored_path,
    )
