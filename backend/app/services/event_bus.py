"""Simple async pub/sub event bus for broadcasting events to WebSocket clients."""
import asyncio

from app.models.events import WSEvent


class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers = [q for q in self._subscribers if q is not queue]

    async def publish(self, event: WSEvent):
        for queue in self._subscribers:
            await queue.put(event)


event_bus = EventBus()
