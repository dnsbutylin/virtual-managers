"""События-факты, которые ячейка сообщает плоскости управления.

Ячейка присылает факты, а не новое состояние лида. Состояние лида меняет
только плоскость управления.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from vm.contracts.tasks import Channel


def _require_aware(value: datetime) -> datetime:
    """Отклоняет наивный момент времени: у факта обязан быть часовой пояс."""
    if value.utcoffset() is None:
        raise ValueError("дата и время должны содержать часовой пояс")
    return value


class FailureReason(StrEnum):
    """Почему попытка выполнения задания не удалась."""

    STOP_LISTED = "stop_listed"
    LIMIT_EXCEEDED = "limit_exceeded"
    AUTH_ERROR = "auth_error"
    REJECTED_BY_PROVIDER = "rejected_by_provider"
    TEMPORARY_ERROR = "temporary_error"
    LEASE_EXPIRED = "lease_expired"
    PERMIT_DENIED = "permit_denied"


class IdentityStatus(StrEnum):
    """Наблюдаемый статус учётной записи канала. Это не статус лида."""

    OK = "ok"
    AUTH_ERROR = "auth_error"
    BOUNCE_SPIKE = "bounce_spike"
    BLOCKED = "blocked"


class _EventBase(BaseModel):
    """Общие поля факта. Снимка состояния лида здесь нет."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    event_id: UUID
    cell_id: str
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def _aware_occurred_at(cls, value: datetime) -> datetime:
        return _require_aware(value)


class TaskSent(_EventBase):
    """Факт: задание отправлено во внешний канал."""

    type: Literal["task.sent"] = "task.sent"
    task_id: UUID
    idempotency_key: str
    lease_token: UUID
    identity_id: UUID
    external_message_id: str | None = None


class TaskFailed(_EventBase):
    """Факт: задание не выполнено."""

    type: Literal["task.failed"] = "task.failed"
    task_id: UUID
    idempotency_key: str
    lease_token: UUID
    identity_id: UUID
    reason: FailureReason
    retryable: bool
    detail: str | None = None


class InboundReceived(_EventBase):
    """Факт: по каналу пришло входящее сообщение."""

    type: Literal["inbound.received"] = "inbound.received"
    identity_id: UUID
    channel: Channel
    sender: str
    text: str
    external_message_id: str
    in_reply_to: str | None = None


class IdentityHealth(_EventBase):
    """Факт: ячейка сообщает наблюдаемый статус учётной записи."""

    type: Literal["identity.health"] = "identity.health"
    identity_id: UUID
    status: IdentityStatus
    detail: str | None = None


class CellHeartbeat(_EventBase):
    """Факт: ячейка жива и сообщает, сколько учётных записей видит."""

    type: Literal["cell.heartbeat"] = "cell.heartbeat"
    software_version: str
    identities_total: Annotated[int, Field(ge=0)]


Event = Annotated[
    TaskSent | TaskFailed | InboundReceived | IdentityHealth | CellHeartbeat,
    Field(discriminator="type"),
]
EVENT_ADAPTER = TypeAdapter(Event)
