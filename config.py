import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key"
    )

    DATABASE = str(
        BASE_DIR / "pageturner.db"
    )

    UPLOAD_FOLDER = str(
        BASE_DIR / "static" / "images"
    )

    # Allow request to reach our own
    # 1 MB image validation.
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024

    ALLOWED_IMAGE_EXTENSIONS = {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }

    MAX_IMAGE_SIZE = 1024 * 1024