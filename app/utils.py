"""
Utility functions for file uploads.
Local storage (development) or Cloudinary (production).
"""

import os
from typing import TYPE_CHECKING

from werkzeug.utils import secure_filename

if TYPE_CHECKING:
    from flask import Flask
    from werkzeug.datastructures import FileStorage


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def save_upload_file(file, folder: str, prefix: str = "") -> str | None:
    """
    Save uploaded file and return filename.
    
    Args:
        file: FileStorage from request.files
        folder: Target folder path
        prefix: Optional prefix for filename (e.g. 'team_123')
    
    Returns:
        Saved filename or None
    """
    if not file or file.filename == "":
        return None

    filename = secure_filename(file.filename)
    if not filename:
        return None

    ext = filename.rsplit(".", 1)[1].lower()
    base = prefix or "upload"
    new_name = f"{base}_{os.urandom(8).hex()}.{ext}"
    path = os.path.join(folder, new_name)
    os.makedirs(folder, exist_ok=True)
    file.save(path)
    return new_name


def upload_image(
    file: "FileStorage",
    folder: str,
    prefix: str,
    app: "Flask | None" = None,
) -> str | None:
    """
    Upload image: local file storage (development) or Cloudinary (production).
    Returns: filename (local) or full URL (Cloudinary).
    """
    if not file or file.filename == "":
        return None

    if app is None:
        from flask import current_app
        app = current_app

    if app.config.get("USE_CLOUDINARY") and all([
        app.config.get("CLOUDINARY_CLOUD_NAME"),
        app.config.get("CLOUDINARY_API_KEY"),
        app.config.get("CLOUDINARY_API_SECRET"),
    ]):
        return _upload_to_cloudinary(file, folder, prefix, app)
    return save_upload_file(file, folder, prefix)


def _upload_to_cloudinary(
    file: "FileStorage",
    folder: str,
    prefix: str,
    app: "Flask",
) -> str | None:
    """Upload file to Cloudinary. Returns secure_url."""
    try:
        import cloudinary.uploader
        import cloudinary

        # Debug: Check credentials
        cloud_name = app.config.get("CLOUDINARY_CLOUD_NAME")
        api_key = app.config.get("CLOUDINARY_API_KEY")
        api_secret = app.config.get("CLOUDINARY_API_SECRET")
        
        print(f"Cloudinary config - Cloud: {cloud_name}, Key: {api_key[:10] if api_key else 'None'}...")
        
        if not all([cloud_name, api_key, api_secret]):
            print("❌ Cloudinary credentials missing!")
            return None

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
        )

        # folder is e.g. "team_logos" or "player_photos" (last part of path)
        cloud_folder = folder.split(os.sep)[-1] if os.sep in folder else folder
        public_id = f"{prefix}_{os.urandom(6).hex()}"
        
        print(f"Uploading to Cloudinary - Folder: {cloud_folder}, Public ID: {public_id}")
        
        result = cloudinary.uploader.upload(
            file,
            folder=cloud_folder,
            public_id=public_id,
            overwrite=True,
        )
        
        url = result.get("secure_url")
        print(f"✅ Cloudinary upload successful: {url}")
        return url
        
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_image_url(identifier: str | None, asset_type: str = "team", app: "Flask | None" = None) -> str | None:
    """
    Resolve image URL from stored value.
    - If identifier is a full URL (http/https), return as-is.
    - Otherwise return local route URL.
    """
    if not identifier:
        return None
    if identifier.startswith(("http://", "https://")):
        return identifier
    if app is None:
        from flask import current_app, url_for
        return url_for("team_logo" if asset_type == "team" else "player_photo", filename=identifier)
    from flask import url_for
    return url_for("team_logo" if asset_type == "team" else "player_photo", filename=identifier)
