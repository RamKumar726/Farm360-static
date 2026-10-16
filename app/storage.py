import os
import re
import uuid
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
    if backend == "s3":
        bucket = current_app.config["UPLOAD_BUCKET"]
        region = current_app.config["UPLOAD_REGION"]
        public_base = current_app.config["UPLOAD_PUBLIC_BASE_URL"]
        if not bucket or not region or not public_base:
            raise UploadError(
                "S3 bucket, region, and public asset base URL must be configured."
            )
        import boto3

        client = boto3.client("s3", region_name=region)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=mime,
            CacheControl="public, max-age=31536000, immutable",
        )
        return f"{public_base}/{key}"
    if backend != "local":
        raise UploadError("Configured image storage backend is unsupported.")
    if not current_app.testing and not current_app.debug:
        raise UploadError(
            "Local image storage is disabled in production. Configure S3-compatible storage."
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
    return send_from_directory(root, key.split("/", 1)[1], max_age=3600)
