"""Configuration du générateur Kevser Date Gen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class VolumeProfile:
    name: str
    communes: int
    agences: int
    societes: int
    clients: int
    etablissements_clients: int
    interimaires: int
    contrats: int
    groupes_clients: int
    min_contract_weeks: int
    max_contract_weeks: int


PROFILES: dict[str, VolumeProfile] = {
    "smoke": VolumeProfile("smoke", 12, 2, 2, 10, 14, 35, 50, 2, 2, 6),
    "demo": VolumeProfile("demo", 80, 8, 8, 300, 450, 2_000, 4_000, 12, 4, 22),
    # Le profil client est généré par défaut en 12 partitions de cette taille.
    "client": VolumeProfile("client", 80, 8, 8, 300, 450, 2_000, 4_000, 12, 4, 22),
}

DEFAULT_SHARDS = {"smoke": 1, "demo": 1, "client": 12}


@dataclass(frozen=True)
class DatasetConfig:
    seed: int = 20_260_717
    start_date: date = date(2023, 7, 1)
    end_date: date = date(2026, 6, 30)
    unpaid_base_rate: float = 0.085
    credit_note_rate: float = 0.018
    missing_contact_rate: float = 0.025
    overtime_rate: float = 0.16
    batch_size: int = 500


PROJECT_DIR = Path(__file__).resolve().parents[2]
SOURCE_DDL = PROJECT_DIR / "schema" / "original" / "modele_ADV_script.sql"
GENERATED_DIR = PROJECT_DIR / "generated"
DOCS_DIR = PROJECT_DIR / "docs"
