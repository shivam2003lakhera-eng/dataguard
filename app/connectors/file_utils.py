from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import (
    AccessDeniedError,
    FileTooLargeError,
    SourceFileNotFoundError,
    UnsupportedFormatError,
)


def resolve_safe_path(relative_path: str, allowed_extensions: set[str]) -> Path:
    """Return a verified absolute path to a file inside DATA_INPUT_DIR."""
    settings = get_settings()
    base_dir = settings.data_input_dir.resolve()
    full_path = (base_dir / relative_path).resolve()

    if not full_path.is_relative_to(base_dir):
        raise AccessDeniedError("Path is outside the allowed input directory.")

    if not full_path.is_file():
        raise SourceFileNotFoundError(
            "Source file not found.", {"path": relative_path}
        )

    if full_path.suffix.lower() not in allowed_extensions:
        raise UnsupportedFormatError(
            "File type is not supported by this connector.",
            {"extension": full_path.suffix, "allowed": sorted(allowed_extensions)},
        )

    size_mb = full_path.stat().st_size / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise FileTooLargeError(
            "File exceeds the maximum allowed size.",
            {"size_mb": round(size_mb, 2), "limit_mb": settings.max_file_size_mb},
        )

    return full_path