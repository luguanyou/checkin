from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Response, UploadFile
from pydantic import AwareDatetime, ConfigDict, Field, HttpUrl, ValidationError
from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from attendance_api.db import get_db
from attendance_api.errors import ApiError
from attendance_api.models import ClassGroup, Course, TeachingContent, TeachingPublication, User
from attendance_api.modules.auth.dependencies import require_password_changed, require_teacher
from attendance_api.modules.courses.service import get_owned_class_group
from attendance_api.modules.portal.router import no_cache, require_student
from attendance_api.modules.portal.service import get_enrolled_class
from attendance_api.schemas.common import ApiModel

router = APIRouter(
    prefix="/api/v1",
    tags=["teaching-content"],
    dependencies=[Depends(require_password_changed), Depends(no_cache)],
)
DB = Annotated[Session, Depends(get_db)]
Teacher = Annotated[User, Depends(require_teacher)]
Student = Annotated[User, Depends(require_student)]
MAX_ATTACHMENT = 10 * 1024 * 1024


class ContentInput(ApiModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Literal["MATERIAL", "ASSIGNMENT"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10000)
    chapter: str | None = Field(default=None, max_length=120)
    category: Literal["CLASSROOM", "SELF_STUDY"] | None = None
    url: HttpUrl | None = None
    due_at: AwareDatetime | None = None
    submission_method: str | None = Field(default=None, max_length=500)
    resource_id: str | None = Field(default=None, max_length=36)
    class_ids: list[Annotated[str, Field(min_length=1, max_length=36)]] = Field(min_length=1)
    remove_attachment: bool = False


class ContentView(ApiModel):
    id: str
    kind: str
    title: str
    description: str
    chapter: str | None
    category: str | None
    url: str | None
    due_at: datetime | None
    submission_method: str | None
    resource_id: str | None
    attachment_name: str | None


class TeacherContentView(ContentView):
    class_ids: list[str]


class StudentContentList(ApiModel):
    items: list[ContentView]


class PublicationClass(ApiModel):
    id: str
    name: str
    status: str


class TeacherContentList(ApiModel):
    course_name: str
    classes: list[PublicationClass]
    items: list[TeacherContentView]


def invalid(message: str) -> ApiError:
    return ApiError(400, "INVALID_REQUEST", message)


def missing() -> ApiError:
    return ApiError(404, "RESOURCE_NOT_FOUND", "教学内容不存在或未向本班发布")


def published_in(class_id: str) -> Select[tuple[str]]:
    return select(TeachingPublication.content_id).where(TeachingPublication.class_id == class_id)


def published_content(db: Session, class_id: str) -> list[TeachingContent]:
    return list(
        db.scalars(
            select(TeachingContent)
            .where(TeachingContent.id.in_(published_in(class_id)))
            .order_by(
                TeachingContent.due_at,
                TeachingContent.chapter,
                TeachingContent.title,
                TeachingContent.id,
            )
        )
    )


def find_item(db: Session, class_id: str, item_id: str, *, lock: bool = False) -> TeachingContent:
    query = (
        select(TeachingContent)
        .join(TeachingPublication, TeachingPublication.content_id == TeachingContent.id)
        .where(TeachingContent.id == item_id, TeachingPublication.class_id == class_id)
    )
    item = db.scalar(query.with_for_update() if lock else query)
    if item is None:
        raise missing()
    return item


def teacher_scope(
    db: Session, teacher: User, class_id: str, *, write: bool = False
) -> tuple[ClassGroup, Course]:
    group, course = get_owned_class_group(db, teacher_id=teacher.id, class_group_id=class_id)
    if write:
        locked_course = db.get(Course, course.id, populate_existing=True, with_for_update=True)
        locked_group = db.get(ClassGroup, group.id, populate_existing=True, with_for_update=True)
        if locked_course is None or locked_group is None:
            raise ApiError(404, "RESOURCE_NOT_FOUND", "班级不存在")
        group, course = locked_group, locked_course
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        raise ApiError(409, "RESOURCE_STATE_CONFLICT", "班级或课程已归档")
    return group, course


def locked_scope_ids(db: Session, item_id: str) -> list[str]:
    return list(
        db.scalars(
            select(TeachingPublication.class_id)
            .where(TeachingPublication.content_id == item_id)
            .order_by(TeachingPublication.class_id)
            .with_for_update()
        )
    )


def student_view(item: TeachingContent, visible_ids: set[str]) -> ContentView:
    return ContentView.model_validate(item).model_copy(
        update={
            "resource_id": item.resource_id if item.resource_id in visible_ids else None,
            "due_at": item.due_at.replace(tzinfo=UTC) if item.due_at else None,
        }
    )


def teacher_view(item: TeachingContent, class_ids: list[str]) -> TeacherContentView:
    data = student_view(item, {item.resource_id} if item.resource_id else set())
    return TeacherContentView(**data.model_dump(), class_ids=class_ids)


def save_item(
    db: Session,
    group: ClassGroup,
    payload: str,
    file: UploadFile | None,
    item: TeachingContent | None = None,
) -> TeacherContentView:
    try:
        data = ContentInput.model_validate_json(payload)
    except ValidationError as exc:
        raise invalid("请检查标题、链接、截止时间和发布班级") from exc
    url = str(data.url) if data.url else None
    if url and len(url) > 2048:
        raise invalid("链接最大为 2048 个字符")

    # Lock the target classes while validating and changing their publications.
    classes = {
        target.id: target.status
        for target in db.scalars(
            select(ClassGroup)
            .where(ClassGroup.course_id == group.course_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    previous = set(locked_scope_ids(db, item.id)) if item else set()
    selected = set(data.class_ids)
    if any(
        key not in classes or (classes[key] != "ACTIVE" and key not in previous) for key in selected
    ):
        raise invalid("只能发布到本课程的有效班级")
    if item and item.kind != data.kind:
        raise invalid("发布后无法切换内容类型")
    if file and data.remove_attachment:
        raise invalid("请选择保留、替换或移除附件")

    if data.kind == "MATERIAL":
        if not data.category or data.due_at or data.submission_method or data.resource_id:
            raise invalid("请选择资料类型，作业字段仅用于作业")
        if not (
            data.description
            or data.url
            or file
            or (item and item.attachment_name and not data.remove_attachment)
        ):
            raise invalid("请填写学习说明、添加链接或上传附件")
    else:
        if selected != {group.id}:
            raise invalid("作业须发布到当前班级")
        if not (data.description and data.due_at and data.submission_method):
            raise invalid("请填写作业要求、截止时间和提交方式")
        if data.category or data.chapter:
            raise invalid("资料分类和章节仅用于课程资料")
        if data.resource_id and not db.scalar(
            select(TeachingContent.id)
            .join(TeachingPublication, TeachingPublication.content_id == TeachingContent.id)
            .where(
                TeachingContent.id == data.resource_id,
                TeachingContent.kind == "MATERIAL",
                TeachingPublication.class_id == group.id,
            )
            .with_for_update()
        ):
            raise invalid("请选择已发布给当前班级的资料")

    if item is None:
        item = TeachingContent(course_id=group.course_id, kind=data.kind)
        db.add(item)
    item.title = data.title
    item.description = data.description
    item.chapter = data.chapter or None
    item.category = data.category
    item.url = url
    item.due_at = data.due_at.astimezone(UTC).replace(tzinfo=None) if data.due_at else None
    item.submission_method = data.submission_method or None
    item.resource_id = data.resource_id or None
    if file:
        filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(char for char in filename if char.isprintable()).strip()
        if not filename or len(filename) > 255:
            raise invalid("附件文件名无效")
        content = file.file.read(MAX_ATTACHMENT + 1)
        if len(content) > MAX_ATTACHMENT:
            raise ApiError(413, "FILE_TOO_LARGE", "附件最大为 10 MB")
        if not content:
            raise invalid("附件不能为空")
        item.attachment_name = filename
        item.attachment = content
    elif data.remove_attachment:
        item.attachment_name = None
        item.attachment = None

    db.flush()
    removed = previous - selected
    if removed:
        db.execute(
            delete(TeachingPublication).where(
                TeachingPublication.content_id == item.id, TeachingPublication.class_id.in_(removed)
            )
        )
    db.add_all(
        TeachingPublication(content_id=item.id, class_id=class_id)
        for class_id in selected - previous
    )
    result = teacher_view(item, sorted(selected))
    db.commit()
    return result


@router.get("/classes/{class_id}/teaching-content", operation_id="listTeachingContent")
def list_content(class_id: str, db: DB, teacher: Teacher) -> TeacherContentList:
    _, course = teacher_scope(db, teacher, class_id)
    groups = db.scalars(
        select(ClassGroup).where(ClassGroup.course_id == course.id).order_by(ClassGroup.name)
    )
    items = published_content(db, class_id)
    scopes: dict[str, list[str]] = {item.id: [] for item in items}
    for item_id, target in db.execute(
        select(TeachingPublication.content_id, TeachingPublication.class_id)
        .where(TeachingPublication.content_id.in_(scopes))
        .order_by(TeachingPublication.class_id)
    ):
        scopes[item_id].append(target)
    return TeacherContentList(
        course_name=course.name,
        classes=[PublicationClass.model_validate(group) for group in groups],
        items=[teacher_view(item, scopes[item.id]) for item in items],
    )


@router.post(
    "/classes/{class_id}/teaching-content", status_code=201, operation_id="publishTeachingContent"
)
def create_content(
    class_id: str,
    db: DB,
    teacher: Teacher,
    payload: Annotated[str, Form()],
    file: UploadFile | None = None,
) -> TeacherContentView:
    group, _ = teacher_scope(db, teacher, class_id, write=True)
    return save_item(db, group, payload, file)


@router.put("/classes/{class_id}/teaching-content/{item_id}", operation_id="updateTeachingContent")
def update_content(
    class_id: str,
    item_id: str,
    db: DB,
    teacher: Teacher,
    payload: Annotated[str, Form()],
    file: UploadFile | None = None,
) -> TeacherContentView:
    group, _ = teacher_scope(db, teacher, class_id, write=True)
    return save_item(db, group, payload, file, find_item(db, class_id, item_id, lock=True))


@router.delete(
    "/classes/{class_id}/teaching-content/{item_id}",
    status_code=204,
    operation_id="withdrawTeachingContent",
)
def withdraw_content(class_id: str, item_id: str, db: DB, teacher: Teacher) -> None:
    teacher_scope(db, teacher, class_id, write=True)
    item = find_item(db, class_id, item_id, lock=True)
    db.delete(item)
    db.commit()


@router.get(
    "/student/classes/{class_id}/teaching-content", operation_id="listStudentTeachingContent"
)
def student_content(class_id: str, db: DB, student: Student) -> StudentContentList:
    _, group, course = get_enrolled_class(db, user=student, class_id=class_id)
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        return StudentContentList(items=[])
    items = published_content(db, class_id)
    visible_ids = {item.id for item in items}
    return StudentContentList(items=[student_view(item, visible_ids) for item in items])


def download(item: TeachingContent) -> Response:
    if not item.attachment_name or item.attachment is None:
        raise missing()
    filename = quote(item.attachment_name, safe="")
    return Response(
        item.attachment,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/classes/{class_id}/teaching-content/{item_id}/attachment",
    operation_id="downloadTeachingAttachment",
)
def teacher_attachment(class_id: str, item_id: str, db: DB, teacher: Teacher) -> Response:
    teacher_scope(db, teacher, class_id)
    return download(find_item(db, class_id, item_id))


@router.get(
    "/student/classes/{class_id}/teaching-content/{item_id}/attachment",
    operation_id="downloadStudentTeachingAttachment",
)
def student_attachment(class_id: str, item_id: str, db: DB, student: Student) -> Response:
    _, group, course = get_enrolled_class(db, user=student, class_id=class_id)
    if group.status != "ACTIVE" or course.status != "ACTIVE":
        raise missing()
    return download(find_item(db, class_id, item_id))
