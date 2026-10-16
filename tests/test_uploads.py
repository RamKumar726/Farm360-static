from io import BytesIO

import pytest

from app.storage import UploadError, store_image


def test_upload_rejects_unsafe_extension(app):
    with app.app_context(), pytest.raises(UploadError):
        store_image(
            type("Upload", (), {"filename": "payload.exe", "stream": BytesIO(b"bad")})()
        )


def test_upload_rejects_image_signature_mismatch(app):
    with app.app_context(), pytest.raises(UploadError, match="does not match"):
        store_image(
            type("Upload", (), {"filename": "photo.png", "stream": BytesIO(b"bad")})()
        )
