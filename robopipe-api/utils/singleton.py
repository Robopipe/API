from typing import Generic, TypeVar, overload

T = TypeVar("T")


class Singleton(Generic[T]):
    def __init__(self, cls: type[T]) -> type[T]:
        self._cls = cls
        self._instance: T | None = None

    def __call__(self) -> T:
        if self._instance is None:
            self._instance = self._cls()

        return self._instance


class SingletonWrapper(Generic[T]):
    def __init__(self, cls: type[T]):
        self._cls = cls
        self._instance: T | None = None

    def __call__(self) -> T:
        if self._instance is None:
            self._instance = self._cls()

        return self._instance


def Singleton(cls: type[T]) -> type[T]:
    return SingletonWrapper(cls)
