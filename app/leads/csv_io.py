from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from app.leads.store import LeadStage, LeadStore


@dataclass(frozen=True, slots=True)
class CsvReconciliation:
    source_rows: int = 0
    imported_rows: int = 0
    rejected_rows: int = 0

    @property
    def reconciled(self) -> bool:
        return self.source_rows == self.imported_rows + self.rejected_rows


class LeadCsvService:
    """Importação tolerante e exportação estável do pipeline comercial."""

    HEADERS: ClassVar[tuple[str, ...]] = (
        "empresa", "nicho", "local", "whatsapp", "site", "fonte",
        "score", "etapa", "qualificacao", "proxima_acao",
    )
    ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "empresa": ("empresa", "company", "nome"),
        "nicho": ("nicho", "segmento", "niche"),
        "local": ("local", "cidade", "location"),
        "whatsapp": ("whatsapp", "telefone", "phone"),
        "site": ("site", "website"),
        "fonte": ("fonte", "source", "source_url", "url"),
        "score": ("score", "pontuacao", "pontuação"),
        "etapa": ("etapa", "stage", "status"),
        "qualificacao": ("qualificacao", "qualificação", "qualification"),
        "proxima_acao": ("proxima_acao", "próxima_ação", "next_action"),
    }

    def __init__(self) -> None:
        self.last_reconciliation = CsvReconciliation()

    def import_file(self, store: LeadStore, path: str | Path) -> tuple[int, tuple[str, ...]]:
        imported = 0
        source_rows = 0
        errors: list[str] = []
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError("O CSV não possui cabeçalho.")
            for number, raw in enumerate(reader, start=2):
                source_rows += 1
                if None in raw:
                    errors.append(f"Linha {number}: possui colunas extras")
                    continue
                row = {
                    str(key).strip().casefold(): self._restore_safe(str(value or "").strip())
                    for key, value in raw.items()
                }
                company = self._pick(row, "empresa")
                if not company:
                    errors.append(f"Linha {number}: empresa ausente")
                    continue
                try:
                    score = int(self._pick(row, "score") or 0)
                except ValueError:
                    errors.append(f"Linha {number}: score inválido")
                    continue
                if not 0 <= score <= 100:
                    errors.append(f"Linha {number}: score fora da faixa (0-100)")
                    continue
                stage_value = self._pick(row, "etapa")
                try:
                    stage = LeadStage(stage_value) if stage_value else LeadStage.NEW
                except ValueError:
                    errors.append(f"Linha {number}: etapa inválida ({stage_value})")
                    continue
                identifier = store.upsert(
                    company=company, niche=self._pick(row, "nicho"),
                    location=self._pick(row, "local"), whatsapp=self._pick(row, "whatsapp"),
                    website=self._pick(row, "site"), source_url=self._pick(row, "fonte"),
                    score=score, qualification=self._pick(row, "qualificacao"),
                )
                if stage is not LeadStage.NEW or self._pick(row, "proxima_acao"):
                    store.update(identifier, stage=stage, next_action=self._pick(row, "proxima_acao"))
                imported += 1
        self.last_reconciliation = CsvReconciliation(
            source_rows=source_rows,
            imported_rows=imported,
            rejected_rows=len(errors),
        )
        return imported, tuple(errors)

    def export_file(self, store: LeadStore, path: str | Path, *, leads=None) -> int:
        leads = tuple(leads) if leads is not None else tuple(store.list(limit=100_000))
        with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self.HEADERS)
            writer.writeheader()
            for lead in leads:
                writer.writerow({
                    "empresa": self._safe(lead.company), "nicho": self._safe(lead.niche),
                    "local": self._safe(lead.location), "whatsapp": self._safe(lead.whatsapp),
                    "site": self._safe(lead.website), "fonte": self._safe(lead.source_url),
                    "score": lead.score, "etapa": lead.stage.value,
                    "qualificacao": self._safe(lead.qualification),
                    "proxima_acao": self._safe(lead.next_action),
                })
        return len(leads)

    def _pick(self, row: dict[str, str], field: str) -> str:
        return next((row[name] for name in self.ALIASES[field] if row.get(name)), "")

    @staticmethod
    def _safe(value: str) -> str:
        dangerous = ("=", "+", "-", "@", "\t", "\r")
        return f"'{value}" if value.startswith(dangerous) or value.startswith(
            tuple(f"'{prefix}" for prefix in dangerous)
        ) else value

    @staticmethod
    def _restore_safe(value: str) -> str:
        """Remove apenas o marcador que esta classe adiciona contra fórmulas CSV."""
        dangerous = ("=", "+", "-", "@", "\t", "\r")
        encoded = tuple(f"'{prefix}" for prefix in dangerous) + tuple(
            f"''{prefix}" for prefix in dangerous
        )
        return value[1:] if value.startswith(encoded) else value
