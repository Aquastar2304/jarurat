from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..config import Settings
from ..http_client import PoliteSession
from ..models import Lead


class LeadSource(ABC):
    """Contract every data source implements."""

    name: str = "base"

    def __init__(self, session: PoliteSession, settings: Settings):
        self.session = session
        self.settings = settings

    @abstractmethod
    def fetch(self, limit: int) -> Iterator[Lead]:
        """Yield up to ``limit`` raw (uncleaned) leads."""
