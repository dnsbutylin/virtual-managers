"""Интерфейс ячейки исполнения.

Ячейка берёт задание в аренду, выполняет касание и возвращает факты.
Состояние лида она не меняет: его обновляет только плоскость управления.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from vm.contracts.events import InboundReceived, TaskFailed, TaskSent
from vm.contracts.tasks import Channel, Task


@runtime_checkable
class Cell(Protocol):
    """Контракт ячейки одного канала.

    Обязательные правила:

    1. Без действующей аренды ничего не отправлять.
    2. Отметку «отправлено» писать на диск ячейки до отчёта в плоскость
       управления.
    3. Локальный счётчик дневного лимита обязан переживать перезапуск;
       при нечитаемом счётчике — отказ.
    4. Прямо перед отправкой запросить разрешение у плоскости управления
       (повторная проверка стоп-листа и выключателей).
    5. Состояние лида ячейка не меняет.
    """

    cell_id: str
    channel: Channel

    async def execute(self, task: Task) -> TaskSent | TaskFailed:
        """Выполняет арендованное задание и возвращает факт отправки или сбоя."""
        ...

    async def poll_inbound(self) -> Sequence[InboundReceived]:
        """Возвращает входящие сообщения, полученные ячейкой."""
        ...
