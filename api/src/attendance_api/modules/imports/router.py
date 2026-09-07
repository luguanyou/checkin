import os
import tempfile
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.errors import ApiError
from attendance_api.models import User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.imports.parser import MAX_FILE_SIZE
from attendance_api.modules.imports.service import confirm_import, preview_import
from attendance_api.schemas.rosters import (
    ConfirmImportRequest,
    ConfirmImportResponse,
    ImportPreviewResponse,
    ImportRow,
    ImportSummary,
)

router = APIRouter(prefix="/api/v1/classes", tags=["roster-imports"])


@router.post(
    "/{class_group_id}/roster/import-preview",
    response_model=ImportPreviewResponse,
    status_code=201,
    operation_id="previewRosterImport",
)
async def preview_roster_import(
    class_group_id: str,
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> ImportPreviewResponse:
    descriptor, temp_name = tempfile.mkstemp()
    temp_path = Path(temp_name)
    try:
        total = 0
        with os.fdopen(descriptor, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise ApiError(400, "FILE_TOO_LARGE", "名单文件不能超过 10 MiB")
                output.write(chunk)
        preview = preview_import(
            db,
            teacher=teacher,
            class_group_id=class_group_id,
            path=temp_path,
            filename=file.filename or "upload",
        )
        validation = preview.validation_result
        summary = cast(dict[str, object], validation["summary"])
        rows = cast(list[dict[str, object]], validation["rows"])
        return ImportPreviewResponse(
            preview_id=preview.id,
            expires_at=preview.expires_at,
            summary=ImportSummary.model_validate(summary),
            rows=[ImportRow.model_validate(row) for row in rows],
        )
    finally:
        await file.close()
        temp_path.unlink(missing_ok=True)


@router.post(
    "/{class_group_id}/roster/import-confirm",
    response_model=ConfirmImportResponse,
    operation_id="confirmRosterImport",
)
def confirm_roster_import(
    class_group_id: str,
    payload: ConfirmImportRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    password_changed: Annotated[User, Depends(require_password_changed)],
) -> ConfirmImportResponse:
    ip_address = request.client.host if request.client is not None else "unknown"
    result = confirm_import(
        db,
        teacher=teacher,
        class_group_id=class_group_id,
        preview_id=payload.preview_id,
        duplicate_policy=payload.duplicate_policy,
        ip_address=ip_address,
        request_id=str(request.state.request_id),
    )
    return ConfirmImportResponse.model_validate(result)
