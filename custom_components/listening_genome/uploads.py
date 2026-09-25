"""Take a file uploaded through Home Assistant's ``/api/file_upload`` before it is deleted."""

from __future__ import annotations

import os
import shutil
import uuid
from typing import TYPE_CHECKING

from homeassistant.components.file_upload import process_uploaded_file

from .const import STORAGE_DIRNAME, UPLOADS_DIRNAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class UploadError(Exception):
    """The upload could not be taken (unknown or expired file id, disk trouble)."""


async def async_take_upload(hass: HomeAssistant, file_id: str) -> str:
    """
    Move an uploaded file into ``<config>/listening_genome/uploads`` and return its path.

    Home Assistant deletes an upload when :func:`process_uploaded_file`'s block ends, and an
    import of a large export runs for minutes, so the file is copied out first. The caller
    removes the copy when the import is done.
    """
    target_dir = hass.config.path(STORAGE_DIRNAME, UPLOADS_DIRNAME)
    target = os.path.join(target_dir, f"{uuid.uuid4().hex}.csv")

    def _take() -> None:
        os.makedirs(target_dir, exist_ok=True)
        with process_uploaded_file(hass, file_id) as source:
            shutil.copyfile(source, target)

    try:
        await hass.async_add_executor_job(_take)
    except ValueError as err:  # process_uploaded_file: unknown or already-consumed file id
        raise UploadError("That upload was not found; upload the file again") from err
    except OSError as err:
        raise UploadError(f"Could not read the upload: {err.strerror or err}") from err
    return target
