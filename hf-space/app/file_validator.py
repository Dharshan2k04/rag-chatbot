"""File upload validation: MIME type, size, magic bytes, sanitization"""

import os
import re
import secrets
from fastapi import UploadFile, HTTPException, status
from .config import settings

# PDF magic bytes
PDF_MAGIC_BYTES = b"%PDF-"
MAX_FILE_SIZE_BYTES = settings.max_file_size_mb * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.

    - Remove path separators
    - Remove special characters
    - Keep only alphanumeric, dash, underscore, period
    - Limit length
    """
    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "").replace("\0", "")

    # Remove non-ASCII characters
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # Keep only safe characters: alphanumeric, dash, underscore, period
    filename = re.sub(r"[^a-zA-Z0-9\-_.]+", "_", filename)

    # Remove leading/trailing dots and dashes
    filename = filename.strip(".-")

    # Limit length (keep extension)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext

    return filename


async def validate_pdf_file(file: UploadFile, user_id: int) -> tuple[str, str]:
    """
    Validate PDF file and return sanitized path and original filename.

    Checks:
    - File size <= 10MB
    - MIME type == application/pdf
    - PDF magic bytes present (%PDF-)
    - Filename sanitization

    Returns:
        (sanitized_file_path, original_filename)

    Raises:
        HTTPException if validation fails
    """
    # Validate filename
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename"
        )

    original_filename = file.filename

    # Validate MIME type
    if file.content_type not in ["application/pdf", "application/x-pdf"]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type. Expected PDF, got {file.content_type}"
        )

    # Read file content for magic bytes check and size validation
    file_content = await file.read()

    # Validate file size
    file_size = len(file_content)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = settings.max_file_size_mb
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb}MB"
        )

    # Validate PDF magic bytes
    if not file_content.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file. File does not start with PDF magic bytes"
        )

    # Sanitize filename
    safe_filename = sanitize_filename(original_filename)
    if not safe_filename or safe_filename == ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename after sanitization"
        )

    # Create user directory if it doesn't exist
    user_dir = f"data/{user_id}"
    os.makedirs(user_dir, exist_ok=True)

    # Generate random suffix to prevent collisions and hide original filename
    random_suffix = secrets.token_hex(8)  # 16 character hex string
    final_filename = f"{os.path.splitext(safe_filename)[0]}_{random_suffix}.pdf"
    file_path = f"{user_dir}/{final_filename}"

    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(file_content)

    return file_path, original_filename
