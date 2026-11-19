"""Расчёт мощности почты.

Рабочий план — новые ящики Gmail на дневном лимите с первого дня, без прогрева
и без резерва. Его печатает ``python -m vm.planning.capacity``.

DEFAULT_WARMUP — оценка для доменного теста, если такой тест отдельно одобрят.
Это не норма Gmail и не смета первого месяца: с 1-го дня 5 писем, с 8-го 10,
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

    Прогрева нет. Так считается рабочий план Gmail.
    """
    if mailboxes < 0 or daily_limit < 0 or days_in_month < 1:
        raise ValueError("число ящиков и лимит неотрицательны, в месяце хотя бы один день")
    return mailboxes * daily_limit * days_in_month


def mailboxes_needed(
    target_per_month: int,
    steady_daily_limit: int,
    days_in_month: int = 30,
    reserve: float = 0,
) -> tuple[int, int]:
    """Сколько ящиков нужно на месячную цель при установившемся дневном лимите.

    Возвращает (рабочих, всего с резервом). Оба числа округляются вверх:
    рабочих = ceil(target / days / limit), всего = ceil(рабочих * (1 + reserve)).
    Резерв рабочего плана — 0.
    """
    workers = ceil(target_per_month / days_in_month / steady_daily_limit)
    total = ceil(workers * (1 + reserve))
    return workers, total


def compounded_target(start: int, monthly_growth: float, month: int) -> int:
    """Цель месяца ``month`` при росте каждый месяц. Месяц 1 равен ``start``."""
    if month < 1:
        raise ValueError("месяц начинается с 1")
    return round(start * (1 + monthly_growth) ** (month - 1))


def main() -> None:
    """Печатает ящики рабочего плана: 100 писем в день, без резерва и без прогрева."""
    lines = [
        "Рабочий план: новые ящики Gmail, 100 писем в день, 30 дней, без прогрева и без резерва",
    ]
    for target in (350_000, 455_000, 591_500):
        workers, _total = mailboxes_needed(target, 100, reserve=0)
        lines.append(f"Цель {target}: {workers} ящиков")
    month_12 = compounded_target(350_000, 0.3, 12)
    workers, _total = mailboxes_needed(month_12, 100, reserve=0)
    lines.append(
        f"Месяц 12 при плюс 30% каждый месяц: {month_12} касаний, {workers} ящиков одной почтой"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
