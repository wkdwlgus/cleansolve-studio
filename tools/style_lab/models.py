from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


class StyleLabInputError(ValueError):
    """Raised when Style Lab input files or reference contracts are invalid."""


@dataclass(frozen=True)
class ReferenceSample:
    sample_id: str
    tier: Literal["core", "extended"]
    role: str
    filename: str

    def __post_init__(self) -> None:
        if self.tier not in {"core", "extended"}:
            raise StyleLabInputError(f"invalid sample tier: {self.tier}")
        if not self.sample_id.startswith("GT_") or len(self.sample_id) != 6 or not self.sample_id[3:].isdigit():
            raise StyleLabInputError(f"invalid sample id: {self.sample_id}")
        expected_filename = f"{self.sample_id}.png"
        if self.filename != expected_filename:
            raise StyleLabInputError(f"invalid filename for {self.sample_id}: {self.filename}")
        if not self.role.strip():
            raise StyleLabInputError(f"missing role for {self.sample_id}")

    def to_json(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ImageMetric:
    sample_id: str
    path: str
    width: int
    height: int
    aspect_ratio: float
    ink_ratio: float
    dark_ratio: float
    red_ratio: float
    blue_ratio: float

    def to_csv_row(self) -> list[str]:
        return [
            self.sample_id,
            self.path,
            str(self.width),
            str(self.height),
            f"{self.aspect_ratio:.6f}",
            f"{self.ink_ratio:.6f}",
            f"{self.dark_ratio:.6f}",
            f"{self.red_ratio:.6f}",
            f"{self.blue_ratio:.6f}",
        ]
