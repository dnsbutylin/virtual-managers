"""Проверки контрактов заданий и событий."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from vm.contracts import (
    EVENT_ADAPTER,
    CellHeartbeat,
    Channel,
    EmailPayload,
    IdentityHealth,
    InboundReceived,
    Task,
    TaskFailed,
    TaskSent,
    make_idempotency_key,
)

LEAD_ID = UUID("11111111-1111-1111-1111-111111111111")
IDENTITY_ID = UUID("22222222-2222-2222-2222-222222222222")
TASK_ID = UUID("33333333-3333-3333-3333-333333333333")
LEASE_TOKEN = UUID("44444444-4444-4444-4444-444444444444")
EVENT_ID = UUID("55555555-5555-5555-5555-555555555555")
WHEN = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
LEASE_UNTIL = WHEN + timedelta(minutes=10)


def sample_task() -> Task:
    return Task(
        task_id=TASK_ID,
        idempotency_key=make_idempotency_key(LEAD_ID, Channel.EMAIL, 0),
        lead_id=LEAD_ID,
        identity_id=IDENTITY_ID,
        cell_id="cell-email-1",
        channel=Channel.EMAIL,
        step=0,
        payload=EmailPayload(
            to_address="buyer@example.com",
            subject="Intro",
            body_text="Hello",
            list_unsubscribe="<mailto:unsub@example.com>",
        ),
        lease_token=LEASE_TOKEN,
        lease_expires_at=LEASE_UNTIL,
        not_before=WHEN,
    )


def sample_sent() -> TaskSent:
    return TaskSent(
        event_id=EVENT_ID,
        cell_id="cell-email-1",
        occurred_at=WHEN,
        task_id=TASK_ID,
        idempotency_key=make_idempotency_key(LEAD_ID, Channel.EMAIL, 0),
        lease_token=LEASE_TOKEN,
        identity_id=IDENTITY_ID,
        external_message_id="msg-1",
    )


def sample_inbound() -> InboundReceived:
    return InboundReceived(
        event_id=EVENT_ID,
        cell_id="cell-email-1",
        occurred_at=WHEN,
        identity_id=IDENTITY_ID,
        channel=Channel.EMAIL,
        sender="buyer@example.com",
        text="Reply",
        external_message_id="in-1",
    )


def test_task_json_roundtrip() -> None:
    task = sample_task()
    restored = Task.model_validate_json(task.model_dump_json())
    assert restored == task


def test_naive_datetime_rejected() -> None:
    naive = datetime(2026, 1, 15, 12, 0)
    raw_task = sample_task().model_dump()
    raw_task["lease_expires_at"] = naive
    with pytest.raises(ValidationError):
        Task.model_validate(raw_task)

    raw_not_before = sample_task().model_dump()
    raw_not_before["not_before"] = naive
    with pytest.raises(ValidationError):
        Task.model_validate(raw_not_before)

    raw_event = sample_sent().model_dump()
    raw_event["occurred_at"] = naive
    with pytest.raises(ValidationError):
        TaskSent.model_validate(raw_event)


def test_idempotency_key_must_match() -> None:
    raw = sample_task().model_dump()
    raw["idempotency_key"] = "not-the-canonical-key"
    with pytest.raises(ValidationError):
        Task.model_validate(raw)


def test_extra_field_forbidden() -> None:
    raw_task = json.loads(sample_task().model_dump_json())
    raw_task["lead_state"] = "new"
    with pytest.raises(ValidationError):
        Task.model_validate(raw_task)

    raw_event = json.loads(sample_sent().model_dump_json())
    raw_event["lead_status"] = "won"
    with pytest.raises(ValidationError):
        TaskSent.model_validate(raw_event)


def test_event_adapter_reads_known_types() -> None:
    sent = EVENT_ADAPTER.validate_json(sample_sent().model_dump_json())
    assert isinstance(sent, TaskSent)

    inbound = EVENT_ADAPTER.validate_json(sample_inbound().model_dump_json())
    assert isinstance(inbound, InboundReceived)


def test_event_adapter_rejects_unknown_type() -> None:
    raw = json.loads(sample_sent().model_dump_json())
    raw["type"] = "task.unknown"
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_json(json.dumps(raw))


def test_events_have_no_lead_state_fields() -> None:
    models = (TaskSent, TaskFailed, InboundReceived, IdentityHealth, CellHeartbeat)
    for model in models:
        names = set(model.model_fields)
        assert "lead_state" not in names
        assert "lead_status" not in names


def test_payload_kind_must_match_channel() -> None:
    raw = sample_task().model_dump()
    raw["channel"] = Channel.VOICE
    raw["idempotency_key"] = make_idempotency_key(LEAD_ID, Channel.VOICE, 0)
    with pytest.raises(ValidationError):
        Task.model_validate(raw)


def test_email_subject_and_body_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        EmailPayload(to_address="a@b.c", subject="", body_text="Hello")
    with pytest.raises(ValidationError):
        EmailPayload(to_address="a@b.c", subject="Intro", body_text="")
