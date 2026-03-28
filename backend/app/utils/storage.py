"""Supabase Storage upload utility.

Setup required in Supabase dashboard:
  1. Create a Storage bucket named "project-assets"
  2. Set the bucket to Public (so audio/caption URLs work in the browser)
     Storage → project-assets → Settings → Public bucket: ON

Bucket name can be overridden via SUPABASE_STORAGE_BUCKET env var.
"""
import logging
import os

logger = logging.getLogger(__name__)

BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "project-assets")


def upload_file(
    project_id: str,
    filename: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload a file to Supabase Storage and return its public URL.

    Files are stored at: {bucket}/{project_id}/{filename}
    Existing files with the same path are overwritten (upsert=true).

    Args:
        project_id:   Project UUID — used as the folder prefix.
        filename:     Target filename, e.g. "voice.mp3" or "captions.srt".
        data:         Raw file bytes.
        content_type: MIME type, e.g. "audio/mpeg" or "text/plain".

    Returns:
        Public URL string for the uploaded file.

    Raises:
        RuntimeError: If the upload fails.
    """
    from app.database import get_db  # local import to avoid circular dependency

    db = get_db()
    path = f"{project_id}/{filename}"

    try:
        db.storage.from_(BUCKET).upload(
            path=path,
            file=data,
            file_options={
                "content-type": content_type,
                "upsert": "true",
            },
        )
        logger.info(f"[storage] Uploaded {len(data):,} bytes → {BUCKET}/{path}")
    except Exception as exc:
        raise RuntimeError(
            f"Supabase Storage upload failed for {BUCKET}/{path}: {exc}"
        ) from exc

    url: str = db.storage.from_(BUCKET).get_public_url(path)
    return url
