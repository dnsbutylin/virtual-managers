"""Контракты заданий, которые плоскость управления сдаёт ячейке в аренду."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Channel(StrEnum):
    """Канал первого касания.

    Почта, голос, форма и три мессенджера — отдельные каналы.
    Касание создаётся только по тому, который отмечен в записи базы
    и который площадка принимает как первое сообщение.
    """

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    VK = "vk"
    WEBFORM = "webform"
    VOICE = "voice"


def make_idempotency_key(lead_id: UUID, channel: Channel, step: int) -> str:
    """Собирает ключ идемпотентности вида ``{lead_id}:{channel}:{step}``."""
    return f"{lead_id}:{channel.value}:{step}"


def _require_aware(value: datetime) -> datetime:
    """Отклоняет наивный момент времени: у аренды обязан быть часовой пояс."""
    if value.utcoffset() is None:
        raise ValueError("дата и время должны содержать часовой пояс")
    return value


class EmailPayload(BaseModel):
    """Письмо. Следующие каналы добавляются как новые варианты с собственным kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["email"] = "email"
    to_address: str
    subject: Annotated[str, Field(min_length=1)]
    body_text: Annotated[str, Field(min_length=1)]
    in_reply_to: str | None = None
    list_unsubscribe: str | None = None


# Размеченное объединение по kind. Новый канал — ещё один член этого
# объединения; имя поля Task.payload и дискриминатор kind не меняются.
Payload = Annotated[EmailPayload, Field(discriminator="kind")]


class Task(BaseModel):
    """Задание в аренде. Ячейка исполняет его и не меняет состояние лида."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    task_id: UUID
    idempotency_key: str
    lead_id: UUID
    identity_id: UUID
    cell_id: str
    channel: Channel
    step: Annotated[int, Field(ge=0)]
    payload: Payload
    lease_token: UUID
    lease_expires_at: datetime
    not_before: datetime | None = None

    @field_validator("lease_expires_at", "not_before")
    @classmethod
    def _aware_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_aware(value)

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        expected = make_idempotency_key(self.lead_id, self.channel, self.step)
        if self.idempotency_key != expected:
            raise ValueError(
                "idempotency_key должен совпадать с make_idempotency_key(lead_id, channel, step)"
            )
        if self.payload.kind != self.channel.value:
            raise ValueError("payload.kind должен соответствовать channel")
        return self
