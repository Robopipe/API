from abc import abstractmethod
from typing import Protocol, Any


class WebSocket(Protocol):
    @abstractmethod
    async def accept(self): ...

    @abstractmethod
    async def close(self): ...

    @abstractmethod
    async def send(self, data: str | bytes | dict | Any): ...

    @abstractmethod
    async def receive(self) -> str | bytes | Any: ...
