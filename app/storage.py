import os
import re
import uuid
from io import BytesIO
from pathlib import Path
from flask import current_app, send_from_directory, url_for


class UploadError(ValueError):
    pass


SIGNATURES = {
    "png": ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "jpg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "jpeg": ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "webp": (
        "image/webp",
        lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    ),
}


def store_image(upload):
    if not upload or not upload.filename:
        return None
    extension = Path(upload.filename).suffix.lower().lstrip(".")
    if extension not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        raise UploadError("Use a JPG, PNG, or WebP image.")
    content = upload.stream.read(5 * 1024 * 1024 + 1)
    if not content or len(content) > 5 * 1024 * 1024:
        raise UploadError("Each image must be smaller than 5 MB.")
    mime, validate_signature = SIGNATURES[extension]
    if not validate_signature(content):
        raise UploadError("The uploaded file does not match its image type.")
    stored_extension = "jpg" if extension == "jpeg" else extension
    key = f"uploads/{uuid.uuid4().hex}.{stored_extension}"
    backend = current_app.config["UPLOAD_STORAGE_BACKEND"].lower()
    if backend == "cloudinary":
        cloudinary_url = current_app.config["CLOUDINARY_URL"].strip()
        if not cloudinary_url:
            raise UploadError("Cloudinary credentials must be configured.")

        import cloudinary
        from cloudinary import uploader

        cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
        try:
            result = uploader.upload(
                BytesIO(content),
                resource_type="image",
                folder=current_app.config["CLOUDINARY_UPLOAD_FOLDER"],
                public_id=uuid.uuid4().hex,
                overwrite=False,
                unique_filename=False,
                use_filename=False,
                allowed_formats=["jpg", "png", "webp"],
            )
        except Exception as exc:
            current_app.logger.exception("Cloudinary image upload failed")
            raise UploadError("Image upload failed. Please try again.") from exc

        image_url = result.get("secure_url")
        if not image_url:
            raise UploadError("Cloudinary did not return an image URL.")
        return image_url
    if backend != "local":
        raise UploadError("Configured image storage backend is unsupported.")
    if not current_app.testing and not current_app.debug:
        raise UploadError(
            "Local image storage is disabled in production. Configure Cloudinary."
        )
    root = current_app.config["UPLOAD_LOCAL_DIRECTORY"] or os.path.join(
        current_app.instance_path, "uploads"
    )
    destination = Path(root).joinpath(*key.split("/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return url_for("public.media", key=key)


def serve_local_image(key):
    if not re.fullmatch(r"uploads/[a-f0-9]{32}\.(?:jpg|png|webp)", key or ""):
        raise UploadError("Invalid image key.")
    root = current_app.config["UPLOAD_LOCAL_DIRECTORY"] or os.path.join(
        current_app.instance_path, "uploads"
    )
    return send_from_directory(root, key, max_age=3600)
