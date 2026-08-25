from __future__ import annotations

import json
import time
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class SelectableRouter(Protocol):
    def select(self, message: str) -> Sequence[object]: ...


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


@dataclass(frozen=True, slots=True)
class RoutingCase:
    identifier: str
    message: str
    expected: frozenset[str]


@dataclass(frozen=True, slots=True)
class ContractCase:
    identifier: str
    response: str
    required_any: tuple[str, ...] = ()
    required_all: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoutingEvaluation:
    total: int
    exact_matches: int
    accuracy: float
    macro_f1: float
    latency_p50_ms: float
    latency_p95_ms: float
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContractEvaluation:
    total: int
    passed: int
    pass_rate: float
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvalReport:
    routing: RoutingEvaluation
    contracts: ContractEvaluation

    def write_json(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class OfflineEvaluator:
    """Runs without a model, network, database, UI, or mutable application state."""

    def evaluate_routing(
        self, router: SelectableRouter, cases: Sequence[RoutingCase]
    ) -> RoutingEvaluation:
        failures: list[str] = []
        timings: list[float] = []
        expected_by_label: dict[str, list[bool]] = {}
        predicted_by_label: dict[str, list[bool]] = {}
        exact = 0
        observations: list[tuple[frozenset[str], frozenset[str]]] = []
        for case in cases:
            started = time.perf_counter()
            selected = router.select(case.message)
            timings.append((time.perf_counter() - started) * 1_000)
            predicted = frozenset(str(getattr(item, "name", item)) for item in selected)
            observations.append((case.expected, predicted))
            if predicted == case.expected:
                exact += 1
            else:
                failures.append(
                    f"{case.identifier}: esperado={sorted(case.expected)} obtido={sorted(predicted)}"
                )
        labels = sorted({label for pair in observations for values in pair for label in values})
        for label in labels:
            expected_by_label[label] = [label in expected for expected, _ in observations]
            predicted_by_label[label] = [label in predicted for _, predicted in observations]
        f1_values = []
        for label in labels:
            truth, prediction = expected_by_label[label], predicted_by_label[label]
            true_positive = sum(a and b for a, b in zip(truth, prediction, strict=True))
            false_positive = sum(not a and b for a, b in zip(truth, prediction, strict=True))
            false_negative = sum(a and not b for a, b in zip(truth, prediction, strict=True))
            denominator = 2 * true_positive + false_positive + false_negative
            f1_values.append(2 * true_positive / denominator if denominator else 1.0)
        total = len(cases)
        return RoutingEvaluation(
            total=total,
            exact_matches=exact,
            accuracy=exact / total if total else 1.0,
            macro_f1=sum(f1_values) / len(f1_values) if f1_values else 1.0,
            latency_p50_ms=self._percentile(timings, 0.50),
            latency_p95_ms=self._percentile(timings, 0.95),
            failures=tuple(failures),
        )

    def evaluate_contracts(self, cases: Sequence[ContractCase]) -> ContractEvaluation:
        failures: list[str] = []
        for case in cases:
            response = _normalize(case.response)
            missing_all = [item for item in case.required_all if _normalize(item) not in response]
            has_any = not case.required_any or any(
                _normalize(item) in response for item in case.required_any
            )
            present_forbidden = [item for item in case.forbidden if _normalize(item) in response]
            reasons = []
            if not response.strip():
                reasons.append("resposta vazia")
            if missing_all:
                reasons.append(f"termos obrigatórios ausentes: {missing_all}")
            if not has_any:
                reasons.append("nenhuma alternativa obrigatória presente")
            if present_forbidden:
                reasons.append(f"termos proibidos presentes: {present_forbidden}")
            if reasons:
                failures.append(f"{case.identifier}: {'; '.join(reasons)}")
        total = len(cases)
        passed = total - len(failures)
        return ContractEvaluation(total, passed, passed / total if total else 1.0, tuple(failures))

    @staticmethod
    def _percentile(values: Sequence[float], quantile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        position = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * quantile)))
        return ordered[position]
