"""Расчёт мощности почтового канала с учётом прогрева ящиков.

DEFAULT_WARMUP — допущение по отраслевой практике, а не норма почтового
провайдера. Лимиты уточняются пилотом: с 1-го дня 5 писем, с 8-го 10,
с 15-го 20, с 22-го 30, с 29-го 40.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True, slots=True)
class WarmupStep:
    """Один порог прогрева: с какого дня возраста действует дневной лимит."""

    from_age_day: int
    daily_limit: int


@dataclass(frozen=True, slots=True)
class WarmupSchedule:
    """Ступенчатый прогрев. Шаги идут по возрастанию, первый начинается с 1-го дня."""

    steps: tuple[WarmupStep, ...]

    def __post_init__(self) -> None:
        if not self.steps or self.steps[0].from_age_day != 1:
            raise ValueError("первый шаг прогрева должен начинаться с 1-го дня")
        previous = self.steps[0].from_age_day
        for step in self.steps[1:]:
            if step.from_age_day <= previous:
                raise ValueError("шаги прогрева должны идти по возрастанию from_age_day")
            previous = step.from_age_day

    def limit_for_age(self, age_day: int) -> int:
        """Дневной лимит для возраста ящика.

        Возраст начинается с 1. Для age_day < 1 возвращается 0. Иначе берётся
        шаг с наибольшим from_age_day, который не превышает age_day.
        """
        if age_day < 1:
            return 0
        limit = 0
        for step in self.steps:
            if step.from_age_day <= age_day:
                limit = step.daily_limit
            else:
                break
        return limit


DEFAULT_WARMUP = WarmupSchedule(
    steps=(
        WarmupStep(from_age_day=1, daily_limit=5),
        WarmupStep(from_age_day=8, daily_limit=10),
        WarmupStep(from_age_day=15, daily_limit=20),
        WarmupStep(from_age_day=22, daily_limit=30),
        WarmupStep(from_age_day=29, daily_limit=40),
    )
)


@dataclass(frozen=True, slots=True)
class MailboxBatch:
    """Партия ящиков, начавших прогрев в день start_day.

    Нумерация дней с 1. Возраст ящика в день d равен d - start_day + 1.
    """

    start_day: int
    mailboxes: int


def daily_capacity(
    batches: Sequence[MailboxBatch],
    schedule: WarmupSchedule,
    day: int,
) -> int:
    """Сколько писем партии могут отправить в указанный день."""
    total = 0
    for batch in batches:
        age = day - batch.start_day + 1
        total += batch.mailboxes * schedule.limit_for_age(age)
    return total


def period_capacity(
    batches: Sequence[MailboxBatch],
    schedule: WarmupSchedule,
    first_day: int,
    last_day: int,
) -> int:
    """Сумма дневной мощности за дни от first_day до last_day включительно."""
    return sum(daily_capacity(batches, schedule, day) for day in range(first_day, last_day + 1))


def steady_month_capacity(
    mailboxes: int,
    daily_limit: int,
    days_in_month: int = 30,
) -> int:
    """Письма за месяц с ящиков, которые уже на дневном лимите.

    Прогрева нет: так считается текущий парк, а не новая партия доменов.
    """
    if mailboxes < 0 or daily_limit < 0 or days_in_month < 1:
        raise ValueError("число ящиков и лимит неотрицательны, в месяце хотя бы один день")
    return mailboxes * daily_limit * days_in_month


def mailboxes_needed(
    target_per_month: int,
    steady_daily_limit: int,
    days_in_month: int = 30,
    reserve: float = 0.2,
) -> tuple[int, int]:
    """Сколько ящиков нужно на месячную цель при установившемся дневном лимите.

    Возвращает (рабочих, всего с резервом). Оба числа округляются вверх:
    рабочих = ceil(target / days / limit), всего = ceil(рабочих * (1 + reserve)).
    """
    workers = ceil(target_per_month / days_in_month / steady_daily_limit)
    total = ceil(workers * (1 + reserve))
    return workers, total


def main() -> None:
    """Печатает сценарии мощности для пилотного набора ящиков."""
    periods = ((1, 30), (31, 60), (61, 90))
    staggered = (
        MailboxBatch(start_day=1, mailboxes=90),
        MailboxBatch(start_day=8, mailboxes=90),
        MailboxBatch(start_day=15, mailboxes=90),
        MailboxBatch(start_day=22, mailboxes=81),
    )
    at_once = (MailboxBatch(start_day=1, mailboxes=351),)
    lines = [
        "Партии: день 1: 90 ящиков, день 8: 90, день 15: 90, день 22: 81",
        "Расписание: прогрев по умолчанию",
    ]
    for first_day, last_day in periods:
        total = period_capacity(staggered, DEFAULT_WARMUP, first_day, last_day)
        lines.append(f"Сумма за дни {first_day}-{last_day}: {total}")
    lines.append("")
    lines.append("Вариант: все 351 ящик в день 1")
    for first_day, last_day in periods:
        total = period_capacity(at_once, DEFAULT_WARMUP, first_day, last_day)
        lines.append(f"Сумма за дни {first_day}-{last_day}: {total}")
    lines.append("")
    lines.append("Потребность в ящиках при лимите 40 писем в день, 30 дней, резерв 0.2")
    for target in (350000, 455000, 591500):
        workers, total = mailboxes_needed(target, 40)
        lines.append(f"Цель {target}: рабочих {workers}, всего {total}")
    lines.append("")
    lines.append("Текущий парк без прогрева, 30 дней")
    for mailboxes in (40, 60):
        for daily_limit in (40, 100):
            total = steady_month_capacity(mailboxes, daily_limit)
            lines.append(f"{mailboxes} ящиков по {daily_limit} в день: {total}")
    lines.append("")
    lines.append("Потребность в ящиках при лимите 100 писем в день, 30 дней, резерв 0.2")
    workers, total = mailboxes_needed(350000, 100)
    lines.append(f"Цель 350000: рабочих {workers}, всего {total}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
