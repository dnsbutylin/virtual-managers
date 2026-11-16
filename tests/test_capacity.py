"""Проверки расчёта мощности. Ожидаемые суммы заданы литералами."""

import pytest

from vm.planning.capacity import (
    DEFAULT_WARMUP,
    MailboxBatch,
    WarmupSchedule,
    WarmupStep,
    daily_capacity,
    mailboxes_needed,
    period_capacity,
    steady_month_capacity,
)

STAGGERED = (
    MailboxBatch(start_day=1, mailboxes=90),
    MailboxBatch(start_day=8, mailboxes=90),
    MailboxBatch(start_day=15, mailboxes=90),
    MailboxBatch(start_day=22, mailboxes=81),
)


def test_one_mailbox_first_thirty_days() -> None:
    # Ручной подсчёт: 7*5 + 7*10 + 7*20 + 7*30 + 2*40 = 535.
    batches = (MailboxBatch(start_day=1, mailboxes=1),)
    assert period_capacity(batches, DEFAULT_WARMUP, 1, 30) == 535


def test_staggered_batches() -> None:
    # Суммы посчитаны вручную по возрасту ящика и ступеням прогрева.
    assert period_capacity(STAGGERED, DEFAULT_WARMUP, 1, 30) == 93105
    assert period_capacity(STAGGERED, DEFAULT_WARMUP, 31, 60) == 372240


def test_all_mailboxes_from_day_one() -> None:
    # 351 * 535 = 187785.
    batches = (MailboxBatch(start_day=1, mailboxes=351),)
    assert period_capacity(batches, DEFAULT_WARMUP, 1, 30) == 187785


def test_mailboxes_needed_for_350000() -> None:
    # ceil(350000 / 30 / 40) = 292, ceil(292 * 1.2) = 351.
    assert mailboxes_needed(350000, 40) == (292, 351)


def test_existing_fleet_has_no_warmup() -> None:
    # 60 * 40 * 30 = 72000. На лимите 100 в день цель 350 тыс. требует 117 рабочих.
    assert steady_month_capacity(60, 40) == 72000
    assert steady_month_capacity(60, 100) == 180000
    assert steady_month_capacity(40, 40) == 48000
    assert mailboxes_needed(350000, 100) == (117, 141)


def test_steady_month_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        steady_month_capacity(-1, 40)
    with pytest.raises(ValueError):
        steady_month_capacity(40, 40, 0)


def test_day_before_batch_start_is_zero() -> None:
    batches = (MailboxBatch(start_day=8, mailboxes=90),)
    assert daily_capacity(batches, DEFAULT_WARMUP, 7) == 0


def test_empty_batches_are_zero() -> None:
    assert daily_capacity((), DEFAULT_WARMUP, 1) == 0
    assert period_capacity((), DEFAULT_WARMUP, 1, 30) == 0


def test_schedule_must_start_on_day_one() -> None:
    with pytest.raises(ValueError):
        WarmupSchedule(steps=(WarmupStep(from_age_day=2, daily_limit=5),))
    with pytest.raises(ValueError):
        WarmupSchedule(steps=())


def test_schedule_must_be_strictly_ascending() -> None:
    with pytest.raises(ValueError):
        WarmupSchedule(
            steps=(
                WarmupStep(from_age_day=1, daily_limit=5),
                WarmupStep(from_age_day=10, daily_limit=20),
                WarmupStep(from_age_day=8, daily_limit=10),
            )
        )
    with pytest.raises(ValueError):
        WarmupSchedule(
            steps=(
                WarmupStep(from_age_day=1, daily_limit=5),
                WarmupStep(from_age_day=1, daily_limit=10),
            )
        )
