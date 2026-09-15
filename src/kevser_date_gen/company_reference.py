"""Accès au référentiel embarqué de personnes morales issues de Sirene."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from .config import PROJECT_DIR


REFERENCE_PATH = PROJECT_DIR / "data" / "sirene_companies.csv"
REFERENCE_METADATA_PATH = PROJECT_DIR / "data" / "sirene_metadata.json"


class CompanyReference(TypedDict):
    siren: str
    raison_sociale: str
    nature_juridique: str
    code_ape: str
    categorie_entreprise: str
    siret_siege: str
    statut_diffusion: str
    date_mise_a_jour_insee: str
    source_query_area: str


class CompanyReferenceMetadata(TypedDict):
    snapshot_date: str
    record_count: int
    source_name: str
    source_api: str
    license: str
    csv_sha256: str
    csv_sha256_normalization: str


def _canonical_csv_sha256(path: Path) -> str:
    """Calcule une empreinte stable malgré la conversion Git CRLF/LF."""
    canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical_bytes).hexdigest()


@lru_cache(maxsize=1)
def company_reference_metadata() -> CompanyReferenceMetadata:
    """Charge les métadonnées versionnées qui accompagnent exactement le CSV."""
    if not REFERENCE_METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Métadonnées Sirene absentes : {REFERENCE_METADATA_PATH}. "
            "Rafraîchissez le référentiel avec le script fourni."
        )
    raw = json.loads(REFERENCE_METADATA_PATH.read_text(encoding="utf-8"))
    required = {
        "snapshot_date",
        "record_count",
        "source_name",
        "source_api",
        "license",
        "csv_sha256",
        "csv_sha256_normalization",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError(f"Métadonnées Sirene incomplètes : {', '.join(missing)}")
    date.fromisoformat(str(raw["snapshot_date"]))
    return CompanyReferenceMetadata(
        snapshot_date=str(raw["snapshot_date"]),
        record_count=int(raw["record_count"]),
        source_name=str(raw["source_name"]),
        source_api=str(raw["source_api"]),
        license=str(raw["license"]),
        csv_sha256=str(raw["csv_sha256"]),
        csv_sha256_normalization=str(raw["csv_sha256_normalization"]),
    )


def is_luhn_valid(value: str) -> bool:
    """Valide un identifiant numérique selon l'algorithme de Luhn."""
    if not value.isdigit() or len(value) < 2:
        return False
    total = 0
    parity = len(value) % 2
    for index, character in enumerate(value):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


@lru_cache(maxsize=1)
def load_company_reference() -> tuple[CompanyReference, ...]:
    """Charge et contrôle une seule fois le snapshot officiel embarqué."""
    if not REFERENCE_PATH.exists():
        raise FileNotFoundError(
            f"Référentiel Sirene absent : {REFERENCE_PATH}. "
            "Exécutez scripts/refresh-sirene-reference.py."
        )

    records: list[CompanyReference] = []
    with REFERENCE_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            record: CompanyReference = {
                "siren": row["siren"].strip(),
                "raison_sociale": row["raison_sociale"].strip(),
                "nature_juridique": row["nature_juridique"].strip(),
                "code_ape": row["code_ape"].strip().replace(".", ""),
                "categorie_entreprise": row["categorie_entreprise"].strip(),
                "siret_siege": row["siret_siege"].strip(),
                "statut_diffusion": row["statut_diffusion"].strip(),
                "date_mise_a_jour_insee": row["date_mise_a_jour_insee"].strip(),
                "source_query_area": row["source_query_area"].strip(),
            }
            records.append(record)

    if not records:
        raise ValueError("Le référentiel Sirene embarqué est vide")
    metadata = company_reference_metadata()
    if metadata["csv_sha256_normalization"] != "line-endings-lf":
        raise ValueError("Normalisation SHA-256 Sirene non prise en charge")
    digest = _canonical_csv_sha256(REFERENCE_PATH)
    if metadata["record_count"] != len(records) or metadata["csv_sha256"] != digest:
        raise ValueError(
            "Le CSV Sirene ne correspond pas à sirene_metadata.json "
            "(nombre de lignes ou empreinte SHA-256)."
        )
    sirens = [record["siren"] for record in records]
    names = [record["raison_sociale"].casefold() for record in records]
    invalid = [
        record["siren"]
        for record in records
        if not is_luhn_valid(record["siren"])
        or len(record["siren"]) != 9
        or not is_luhn_valid(record["siret_siege"])
        or len(record["siret_siege"]) != 14
        or not record["siret_siege"].startswith(record["siren"])
        or not record["nature_juridique"].startswith(("5", "6"))
        or record["statut_diffusion"] != "O"
        or not record["raison_sociale"]
    ]
    if invalid:
        raise ValueError(f"Référentiel Sirene invalide pour {len(invalid)} entreprise(s)")
    if len(set(sirens)) != len(records) or len(set(names)) != len(records):
        raise ValueError("Le référentiel Sirene contient des identités dupliquées")

    return tuple(records)


@lru_cache(maxsize=None)
def _dispersed_company_reference(exclude_first: int) -> tuple[CompanyReference, ...]:
    """Disperse un sous-ensemble sans rebrasser les identités clients historiques."""
    records = load_company_reference()
    if exclude_first < 0 or exclude_first >= len(records):
        raise ValueError(
            f"La réserve clients ({exclude_first}) laisse trop peu d'identités Sirene."
        )
    candidates = records[exclude_first:]
    return tuple(
        sorted(
            candidates,
            key=lambda record: hashlib.sha256(
                f"kevser-date-gen-v1|{record['siren']}".encode("utf-8")
            ).digest(),
        )
    )


def company_record(
    number: int,
    *,
    from_end: bool = False,
    exclude_first: int = 0,
) -> CompanyReference:
    """Retourne une identité unique, sans modifier l'ordre historique des clients."""
    records = (
        _dispersed_company_reference(exclude_first)
        if from_end
        else load_company_reference()
    )
    if number < 1 or number > len(records):
        raise ValueError(
            f"La génération demande l'identité d'entreprise n° {number}, "
            f"mais le référentiel Sirene n'en contient que {len(records)}."
        )
    return records[-number] if from_end else records[number - 1]
