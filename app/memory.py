from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from .store import remember, recall

class MemoryStore(ABC):
    @abstractmethod
    def put(self, user_id: str, category: str, key: str, value: Any) -> None: ...
    @abstractmethod
    def get_all(self, user_id: str) -> list[dict[str, Any]]: ...
    @abstractmethod
    def forget(self, user_id: str) -> int: ...

class SQLiteMemoryStore(MemoryStore):
    def put(self, user_id, category, key, value):
        remember(user_id, category, key, value)
    def get_all(self, user_id):
        return recall(user_id)
    def forget(self, user_id):
        from .store import connect
        with connect() as db:
            count=db.execute("SELECT COUNT(*) FROM memory WHERE user_id=?",(user_id,)).fetchone()[0]
            db.execute("DELETE FROM memory WHERE user_id=?",(user_id,))
            return count

memory_store: MemoryStore = SQLiteMemoryStore()
