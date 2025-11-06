"""Dataclasses shared across council scrapers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class LicenceRecord:
    council: str
    reference: str
    address: Optional[str]
    occupancy: Optional[int]
    licence_expiry: Optional[str]
    licence_type: Optional[str]
    detail_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "council": self.council,
            "reference": self.reference,
            "address": self.address,
            "occupancy": self.occupancy,
            "licence_expiry": self.licence_expiry,
            "licence_type": self.licence_type,
            "detail_url": self.detail_url,
        }


@dataclass(slots=True)
class ResultRow:
    reference: str
    address: Optional[str]
    detail_url: str
    summary_text: str
