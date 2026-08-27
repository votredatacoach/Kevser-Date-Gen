"""Accès au référentiel embarqué de personnes morales issues de Sirene."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from .config import PROJECT_DIR


REFERENCE_PATH = PROJECT_DIR / "data" / "sirene_companies.csv"


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


def company_record(number: int, *, from_end: bool = False) -> CompanyReference:
    """Retourne une identité unique, avec une numérotation commençant à 1."""
    records = load_company_reference()
    if number < 1 or number > len(records):
        raise ValueError(
            f"La génération demande l'identité d'entreprise n° {number}, "
            f"mais le référentiel Sirene n'en contient que {len(records)}."
        )
    return records[-number] if from_end else records[number - 1]
