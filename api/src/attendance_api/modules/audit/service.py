from sqlalchemy.orm import Session

from attendance_api.models import AuditLog


def append_audit(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before_value: dict[str, object] | None,
    after_value: dict[str, object] | None,
    reason: str | None,
    ip_address: str,
    request_id: str,
    client_mutation_id: str | None = None,
) -> AuditLog:
    audit = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_value=before_value,
        after_value=after_value,
        reason=reason,
        ip_address=ip_address[:45],
        request_id=request_id[:64],
        client_mutation_id=client_mutation_id,
    )
    db.add(audit)
    db.flush()
    return audit
