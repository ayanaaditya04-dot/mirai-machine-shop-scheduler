import hashlib
from pathlib import Path

from src.data_generator import OUTPUT_TABLES, generate_dataset
from src.data_validator import validate_dataset
from src.quality_report import build_report


def _digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in OUTPUT_TABLES:
        digest.update((directory / f"{name}.csv").read_bytes())
    return digest.hexdigest()


def test_generated_dataset_passes_integrity_checks(tmp_path):
    generate_dataset(tmp_path)
    assert validate_dataset(tmp_path) == []


def test_hard_counts_and_routing_sanity(tmp_path):
    generate_dataset(tmp_path)
    assert sum(1 for _ in (tmp_path / "machines.csv").open()) - 1 == 14
    assert sum(1 for line in (tmp_path / "machines.csv").open() if ",GRINDER," in line) == 1
    assert sum(1 for line in (tmp_path / "operator_skills.csv").open() if ",GRINDER," in line) == 3
    report = build_report(tmp_path)
    assert report["orders"]["total"] == 25
    assert 3 <= min(map(int, report["orders"]["operations_per_order"]))
    assert max(map(int, report["orders"]["operations_per_order"])) <= 6
    assert report["grinding"]["workload_hours"] > 0


def test_generation_is_byte_deterministic(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    generate_dataset(first)
    generate_dataset(second)
    assert _digest(first) == _digest(second)
