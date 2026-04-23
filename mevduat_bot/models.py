from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MevduatSnapshot:
    index_name: str
    index_code: str
    updated_at: str
    current_value: str
    daily_change_percent: str
    currency: str

    def to_message(self) -> str:
        return (
            f"BIST-KYD 1 Aylik Mevduat {self.currency}\n"
            f"Guncel deger: {self.current_value}\n"
            f"Son guncelleme: {self.updated_at}\n"
            f"Degisim (%): {self.daily_change_percent}\n"
            f"Endeks: {self.index_name} ({self.index_code})"
        )
