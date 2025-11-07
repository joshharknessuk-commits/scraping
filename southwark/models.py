"""Data models used by the Southwark scraper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class ResultRow:
    reference: str
    address: Optional[str]
    detail_url: str
    summary_text: str


@dataclass(slots=True)
class LicenceRecord:
    reference: str
    address: Optional[str]
    licence_expiry: Optional[str]
    licence_type: Optional[str]
    occupancy: Optional[int]
    detail_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "address": self.address,
            "licence_expiry": self.licence_expiry,
            "licence_type": self.licence_type,
            "occupancy": self.occupancy,
            "detail_url": self.detail_url,
        }
