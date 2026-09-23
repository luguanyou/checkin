from fastapi.testclient import TestClient

EXPECTED_OPERATION_IDS = {
    "getHealthLive",
    "getHealthReady",
    "login",
    "refreshAccessToken",
    "logout",
    "getCurrentUser",
    "changePassword",
    "listUsers",
    "createTeacher",
    "updateUserStatus",
    "resetUserPassword",
    "listCourses",
    "createCourse",
    "updateCourse",
    "deleteCourse",
    "createClassGroup",
    "updateClassGroup",
    "deleteClassGroup",
    "getClassRoster",
    "previewRosterImport",
    "confirmRosterImport",
    "updateEnrollmentStatus",
    "listAttendanceSessions",
    "createAttendanceSession",
    "getAttendanceSession",
    "updateAttendanceRecord",
    "completeAttendanceSession",
    "exportAttendanceSession",
    "speakText",
    "getScoreBook",
    "setScoreSettings",
    "createScoreItem",
    "updateScoreItem",
    "setScoreRecords",
    "getScoreHistory",
    "exportScores",
}


def test_openapi_contains_all_stable_operation_ids(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    actual = {
        operation["operationId"]
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "patch", "put", "delete"}
    }

    assert actual == EXPECTED_OPERATION_IDS


def test_openapi_declares_bearer_security_and_public_login(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    schemes = schema["components"]["securitySchemes"]

    assert schemes["HTTPBearer"] == {"type": "http", "scheme": "bearer"}
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
    assert schema["paths"]["/api/v1/courses"]["get"]["security"] == [{"HTTPBearer": []}]


def test_openapi_has_uniform_error_schema_and_forbids_extra_request_fields(
    client: TestClient,
) -> None:
    schema = client.get("/openapi.json").json()
    error = schema["components"]["schemas"]["ErrorResponse"]

    assert set(error["required"]) == {"code", "message", "details", "request_id"}
    assert error["additionalProperties"] is False
    request_schemas = {
        name: item
        for name, item in schema["components"]["schemas"].items()
        if name.endswith("Request")
    }
    assert request_schemas
    assert all(item.get("additionalProperties") is False for item in request_schemas.values())
    assert schema["paths"]["/api/v1/courses"]["post"]["responses"]["400"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


def test_openapi_documents_upload_and_binary_exports(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    upload = schema["paths"]["/api/v1/classes/{class_group_id}/roster/import-preview"]["post"]
    export = schema["paths"]["/api/v1/attendance-sessions/{session_id}/export"]["get"]

    assert "multipart/form-data" in upload["requestBody"]["content"]
    content = export["responses"]["200"]["content"]
    assert content["text/csv"]["schema"] == {"type": "string", "format": "binary"}
    assert content["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"][
        "schema"
    ] == {"type": "string", "format": "binary"}
