"""Orchestration partitionnée et exports du générateur.

Le moteur historique construit une partition cohérente en mémoire. Ce module
enchaîne plusieurs partitions, les contrôle puis les écrit immédiatement sur
disque. La mémoire reste donc bornée, même pour plusieurs millions de lignes.
"""

from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import shutil
import sqlite3
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .company_reference import (
    company_reference_metadata,
    is_luhn_valid,
    load_company_reference,
)
from .config import DEFAULT_SHARDS, DatasetConfig, PROFILES
from .engine import (
    LOAD_ORDER,
    _csv_value,
    _ddl_column_types,
    build_dataset,
    french_vat_code,
    run_audit,
)
from .sqlserver import write_sql_server_kit


SHARED_TABLES = {
    "Referentiel.Communes",
    "Referentiel.CategoriesSocioProfessionnelles",
    "Referentiel.MotifsContrat",
    "Referentiel.MotifsFinContrat",
    "Referentiel.Qualifications",
    "Referentiel.Rubriques",
    "Activite.LotsFacturation",
    "Activite.GroupesClients",
}

BUSINESS_TABLES = (
    "Activite.ContratsModelesPoste",
    "Activite.RelevesHeures",
    "Activite.LignesReleveHeures",
    "Activite.MouvementsReleveHeures",
    "Activite.Factures",
    "Activite.LignesFacture",
)


def resolve_shards(profile: str, scale: float, shards: int | None = None) -> int:
    if scale <= 0:
        raise ValueError("--scale doit être strictement positif")
    if shards is not None:
        if shards < 1:
            raise ValueError("--shards doit être supérieur ou égal à 1")
        return shards
    return max(1, math.ceil(DEFAULT_SHARDS[profile] * scale))


def _validate_generation_capacity(profile_name: str, shard_count: int) -> None:
    """Échoue avant toute écriture si une clé ou le référentiel serait dépassé."""
    profile = PROFILES[profile_name]
    reference_size = len(load_company_reference())
    clients = profile.clients * shard_count
    societies = profile.societes * shard_count
    agencies = profile.agences * shard_count
    establishments = (
        max(profile.societes * 2, math.ceil(profile.agences / 2)) * shard_count
    )
    errors: list[str] = []
    if clients + societies > reference_size:
        errors.append(
            f"{clients} clients + {societies} sociétés > {reference_size} identités Sirene"
        )
    compact_code_maximum = 36**2 - 1
    for label, value in (
        ("sociétés", societies),
        ("agences", agencies),
        ("établissements", establishments),
    ):
        if value > compact_code_maximum:
            errors.append(
                f"{value} {label} > {compact_code_maximum} codes disponibles sur nvarchar(3)"
            )
    if agencies > 9_999:
        errors.append(f"{agencies} dossiers > 9 999 codes disponibles sur nvarchar(5)")
    if errors:
        raise ValueError(
            "Capacité de génération dépassée avant toute écriture : " + "; ".join(errors)
        )


def _transform_row(table: str, row: dict[str, Any], shard: int) -> dict[str, Any]:
    """Évite les collisions sur les clés numériques entre partitions."""
    if shard == 0:
        return row
    result = dict(row)
    offsets: dict[str, tuple[str, int]] = {
        "Activite.PerimetresGroupesClients": ("Id", 1_000_000),
        "Activite.LignesFacture": ("Id", 100_000_000),
        "Activite.Clients": ("Matricule", 1_000_000),
        "Activite.ContratsModelesPoste": ("Numero", 10_000_000),
        "Activite.EtablissementsClientDossiersAgence": ("Matricule", 1_000_000),
        "Activite.DossierAgenceMatriculeInterimaires": ("Matricule", 1_000_000),
        "Activite.Factures": ("Numero", 10_000_000),
    }
    rule = offsets.get(table)
    if rule and result.get(rule[0]) is not None:
        result[rule[0]] = int(result[rule[0]]) + shard * rule[1]
    if table == "Activite.Factures":
        result["NumeroComplet"] = f"S{shard + 1:02d}-{row['NumeroComplet']}"[-20:]
    return result


class CsvBundleWriter:
    def __init__(self, target: Path) -> None:
        self.target = target
        self.target.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, Any] = {}
        self._writers: dict[str, csv.writer] = {}
        self.columns: dict[str, list[str]] = {}
        self.row_counts: dict[str, int] = defaultdict(int)

    def append(self, tables: dict[str, list[dict[str, Any]]], shard: int) -> None:
        for table in LOAD_ORDER:
            if shard > 0 and table in SHARED_TABLES:
                continue
            rows = tables[table]
            if not rows:
                continue
            if table not in self._writers:
                path = self.target / f"{table.replace('.', '__')}.csv"
                handle = path.open("w", encoding="utf-8", newline="")
                columns = list(rows[0])
                writer = csv.writer(handle, delimiter="|", lineterminator="\n")
                writer.writerow(columns)
                self._handles[table] = handle
                self._writers[table] = writer
                self.columns[table] = columns
            columns = self.columns[table]
            writer = self._writers[table]
            for source_row in rows:
                row = _transform_row(table, source_row, shard)
                writer.writerow([_csv_value(row.get(column)) for column in columns])
            self.row_counts[table] += len(rows)

    def close(self) -> None:
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()
        self._writers.clear()


def _sqlite_type(sql_type: str) -> str:
    if sql_type.startswith(("int", "bigint", "bit")):
        return "INTEGER"
    if sql_type.startswith("decimal"):
        return "NUMERIC"
    if sql_type.startswith("varbinary"):
        return "BLOB"
    return "TEXT"


def export_sqlite(csv_dir: Path, target: Path, columns: dict[str, list[str]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = _ddl_column_types()
    connection = sqlite3.connect(target)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=OFF")
        for table in LOAD_ORDER:
            if table not in columns:
                continue
            sqlite_table = table.replace(".", "__")
            column_defs = ", ".join(
                f'"{column}" {_sqlite_type(schema[table][column])}' for column in columns[table]
            )
            connection.execute(f'CREATE TABLE "{sqlite_table}" ({column_defs})')
            placeholders = ",".join("?" for _ in columns[table])
            csv_path = csv_dir / f"{sqlite_table}.csv"
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle, delimiter="|")
                next(reader)
                batch: list[list[str | None]] = []
                for row in reader:
                    batch.append([value if value != "" else None for value in row])
                    if len(batch) >= 10_000:
                        connection.executemany(
                            f'INSERT INTO "{sqlite_table}" VALUES ({placeholders})', batch
                        )
                        batch.clear()
                if batch:
                    connection.executemany(
                        f'INSERT INTO "{sqlite_table}" VALUES ({placeholders})', batch
                    )
            connection.commit()
    finally:
        connection.close()


def _hash_files(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "manifest.sha256":
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def _write_manifest(root: Path) -> dict[str, str]:
    hashes = _hash_files(root)
    text = "".join(f"{digest}  {path}\n" for path, digest in hashes.items())
    (root / "manifest.sha256").write_text(text, encoding="utf-8", newline="\n")
    return hashes


def _partition_identity_metrics(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Résume les identités d'une partition avant leur écriture sur disque."""

    def values(table: str, column: str) -> list[str]:
        return [str(row.get(column) or "").strip() for row in tables[table]]

    clients = tables["Activite.Clients"]
    societies = tables["Activite.Societes"]
    establishments = tables["Activite.Etablissements"]
    client_establishments = tables["Activite.EtablissementsClient"]
    return {
        "Activite.Clients": {
            "rows": len(clients),
            "distinct_sirens": len(set(values("Activite.Clients", "SIREN"))),
            "siren_examples": values("Activite.Clients", "SIREN")[:3],
        },
        "Activite.Societes": {
            "rows": len(societies),
            "distinct_sirens": len(set(values("Activite.Societes", "SIREN"))),
            "distinct_codes": len(set(values("Activite.Societes", "Code"))),
            "siren_examples": values("Activite.Societes", "SIREN")[:3],
            "codes": values("Activite.Societes", "Code"),
        },
        "Activite.Etablissements": {
            "rows": len(establishments),
            "official_siret_rows": sum(
                bool(value) for value in values("Activite.Etablissements", "PseudoSIRET")
            ),
            "synthetic_rows_without_siret": sum(
                not value for value in values("Activite.Etablissements", "PseudoSIRET")
            ),
            "distinct_codes": len(set(values("Activite.Etablissements", "Code"))),
        },
        "Activite.EtablissementsClient": {
            "rows": len(client_establishments),
            "official_siret_rows": sum(
                bool(value) for value in values("Activite.EtablissementsClient", "SIRET")
            ),
            "synthetic_rows_without_siret": sum(
                not value for value in values("Activite.EtablissementsClient", "SIRET")
            ),
        },
        "Activite.Agences": {
            "rows": len(tables["Activite.Agences"]),
            "distinct_codes": len(set(values("Activite.Agences", "Code"))),
            "codes": values("Activite.Agences", "Code"),
        },
        "Activite.DossiersAgence": {
            "rows": len(tables["Activite.DossiersAgence"]),
            "distinct_codes": len(set(values("Activite.DossiersAgence", "Code"))),
            "codes": values("Activite.DossiersAgence", "Code"),
        },
        "Activite.AxesAnalytiques": {
            "rows": len(tables["Activite.AxesAnalytiques"]),
            "distinct_codes": len(set(values("Activite.AxesAnalytiques", "Code"))),
        },
    }


def _audit_company_identities(
    csv_root: Path,
    *,
    profile_name: str,
    shard_count: int,
) -> dict[str, Any]:
    """Contrôle les identités légales et leurs relations après concaténation."""
    reference = {record["siren"]: record for record in load_company_reference()}
    tables: dict[str, dict[str, Any]] = {}

    def read_table(table: str) -> list[dict[str, str]]:
        path = csv_root / f"{table}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="|"))

    def iter_table(table: str):
        path = csv_root / f"{table}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle, delimiter="|")

    def identity_summary(rows: list[dict[str, str]], *, with_codes: bool = False) -> dict[str, Any]:
        sirens = [row["SIREN"] for row in rows]
        names = [row["RaisonSociale"].strip() for row in rows]
        matched_references = [reference.get(value) for value in sirens]
        official_matches = []
        for row, record in zip(rows, matched_references):
            official_matches.append(
                record is not None
                and record["raison_sociale"] == row["RaisonSociale"].strip()
                and record["code_ape"] == row["CodeAPE"].replace(".", "").strip()
                and record["nature_juridique"] == row["FormeJuridiqueCode"].strip()
            )
        valid_references = [record for record in matched_references if record is not None]
        area_counts = Counter(record["source_query_area"] for record in valid_references)
        duplicate_sirens = sorted(value for value, count in Counter(sirens).items() if count > 1)
        duplicate_names = sorted(value for value, count in Counter(names).items() if count > 1)
        distinct_prefixes = len({value[:3] for value in sirens})
        summary: dict[str, Any] = {
            "rows": len(rows),
            "distinct_sirens": len(set(sirens)),
            "distinct_company_names": len(set(names)),
            "duplicate_sirens": duplicate_sirens[:20],
            "duplicate_company_names": duplicate_names[:20],
            "distinct_siren_prefixes_3": distinct_prefixes,
            "siren_prefix_3_coverage_ratio": (
                round(distinct_prefixes / len(rows), 4) if rows else 0
            ),
            "distinct_ape_codes": len({record["code_ape"] for record in valid_references}),
            "distinct_ape_divisions": len({record["code_ape"][:2] for record in valid_references}),
            "distinct_legal_forms": len({record["nature_juridique"] for record in valid_references}),
            "distinct_company_categories": len(
                {record["categorie_entreprise"] for record in valid_references}
            ),
            "distinct_source_query_areas": len(area_counts),
            "source_query_area_counts": dict(sorted(area_counts.items())),
            "maximum_source_query_area_share": (
                round(max(area_counts.values()) / len(rows), 4) if rows and area_counts else 0
            ),
            "official_snapshot_matches": sum(official_matches),
            "official_snapshot_coverage_ratio": (
                round(sum(official_matches) / len(rows), 4) if rows else 0
            ),
            "all_sirens_are_nine_digits": all(len(value) == 9 and value.isdigit() for value in sirens),
            "all_sirens_pass_luhn": all(is_luhn_valid(value) for value in sirens),
            "all_identities_match_official_snapshot": all(official_matches),
            "all_company_names_are_populated": all(names),
            "sirens_are_globally_unique": not duplicate_sirens,
            "company_names_are_globally_unique": not duplicate_names,
            "one_identity_per_row": len(set(sirens)) == len(rows) == len(set(names)),
            "examples": [
                {
                    "siren": row["SIREN"],
                    "raison_sociale": row["RaisonSociale"].strip(),
                    "code_ape": row["CodeAPE"].replace(".", "").strip(),
                    "forme_juridique": row["FormeJuridiqueCode"].strip(),
                    "source_query_area": reference[row["SIREN"]]["source_query_area"],
                }
                for row in rows[:8]
                if row["SIREN"] in reference
            ],
        }
        if with_codes:
            codes = [row["Code"].strip() for row in rows]
            summary.update(
                {
                    "distinct_codes": len(set(codes)),
                    "all_codes_are_populated": all(codes),
                    "codes_are_globally_unique": len(set(codes)) == len(rows),
                    "all_vat_codes_match_siren_derivation": all(
                        row["CodeTvaCee"].strip() == french_vat_code(row["SIREN"])
                        for row in rows
                    ),
                    "vat_identifier_provenance": (
                        "Format français dérivé du SIREN ; activité fiscale non affirmée."
                    ),
                }
            )
        return summary

    clients = read_table("Activite__Clients")
    societies = read_table("Activite__Societes")
    client_establishments = read_table("Activite__EtablissementsClient")
    establishments = read_table("Activite__Etablissements")
    agencies = read_table("Activite__Agences")
    dossiers = read_table("Activite__DossiersAgence")
    client_establishment_dossiers = read_table(
        "Activite__EtablissementsClientDossiersAgence"
    )
    axes = read_table("Activite__AxesAnalytiques")

    tables["Activite.Clients"] = identity_summary(clients)
    tables["Activite.Societes"] = identity_summary(societies, with_codes=True)

    client_by_id = {row["Id"]: row for row in clients}
    society_by_id = {row["Id"]: row for row in societies}
    official_client_sites = [row for row in client_establishments if row["SIRET"].strip()]
    synthetic_client_sites = [row for row in client_establishments if not row["SIRET"].strip()]
    official_client_sites_by_parent = Counter(row["ClientId"] for row in official_client_sites)
    client_site_siret_checks = []
    client_site_name_checks = []
    for row in official_client_sites:
        parent = client_by_id.get(row["ClientId"])
        record = reference.get(parent["SIREN"]) if parent else None
        siret = row["SIRET"].strip()
        client_site_siret_checks.append(
            record is not None
            and siret == record["siret_siege"]
            and len(siret) == 14
            and is_luhn_valid(siret)
            and siret.startswith(parent["SIREN"])
            and row["CodeNIC"].strip() == siret[-5:]
        )
        client_site_name_checks.append(
            record is not None
            and row["RaisonSociale"].strip() == record["raison_sociale"]
            and row["RaisonSociale"].strip() == parent["RaisonSociale"].strip()
        )
    tables["Activite.EtablissementsClient"] = {
        "rows": len(client_establishments),
        "parent_clients": len(client_by_id),
        "official_headquarters_rows": len(official_client_sites),
        "synthetic_site_rows_without_siret": len(synthetic_client_sites),
        "distinct_official_sirets": len({row["SIRET"] for row in official_client_sites}),
        "one_official_headquarters_per_parent": (
            set(official_client_sites_by_parent) == set(client_by_id)
            and all(count == 1 for count in official_client_sites_by_parent.values())
        ),
        "all_official_sirets_match_parent_and_snapshot": all(
            client_site_siret_checks
        ),
        "all_official_headquarter_names_match_parent_and_snapshot": all(
            client_site_name_checks
        ),
        "all_sites_link_to_a_known_parent": all(
            row["ClientId"] in client_by_id for row in client_establishments
        ),
        "all_synthetic_sites_leave_siret_and_nic_blank": all(
            not row["SIRET"].strip() and not row["CodeNIC"].strip()
            for row in synthetic_client_sites
        ),
        "identifier_policy": (
            "SIRET officiel du siège uniquement ; SIRET et NIC vides pour les sites synthétiques."
        ),
    }

    establishment_by_id = {row["Id"]: row for row in establishments}
    official_society_sites = [row for row in establishments if row["PseudoSIRET"].strip()]
    synthetic_society_sites = [row for row in establishments if not row["PseudoSIRET"].strip()]
    official_society_sites_by_parent = Counter(row["SocieteId"] for row in official_society_sites)
    official_society_site_siret_checks = []
    official_society_site_name_checks = []
    for row in official_society_sites:
        parent = society_by_id.get(row["SocieteId"])
        record = reference.get(parent["SIREN"]) if parent else None
        siret = row["PseudoSIRET"].strip()
        official_society_site_siret_checks.append(
            record is not None
            and siret == record["siret_siege"]
            and len(siret) == 14
            and is_luhn_valid(siret)
            and siret.startswith(parent["SIREN"])
            and row["NIC"].strip() == siret[-5:]
        )
        official_society_site_name_checks.append(
            record is not None
            and row["RaisonSociale"].strip() == record["raison_sociale"]
            and row["RaisonSociale"].strip() == parent["RaisonSociale"].strip()
        )
    establishment_codes = [row["Code"].strip() for row in establishments]
    tables["Activite.Etablissements"] = {
        "rows": len(establishments),
        "parent_societies": len(society_by_id),
        "official_headquarters_rows": len(official_society_sites),
        "synthetic_site_rows_without_siret": len(synthetic_society_sites),
        "distinct_official_sirets": len({row["PseudoSIRET"] for row in official_society_sites}),
        "distinct_codes": len(set(establishment_codes)),
        "all_codes_are_populated": all(establishment_codes),
        "codes_are_globally_unique": len(set(establishment_codes)) == len(establishments),
        "all_sites_link_to_a_known_parent": all(
            row["SocieteId"] in society_by_id for row in establishments
        ),
        "all_site_ape_codes_match_the_parent": all(
            row["SocieteId"] in society_by_id
            and row["CodeAPE"].replace(".", "").strip()
            == society_by_id[row["SocieteId"]]["CodeAPE"].replace(".", "").strip()
            for row in establishments
        ),
        "one_official_headquarters_per_parent": (
            set(official_society_sites_by_parent) == set(society_by_id)
            and all(count == 1 for count in official_society_sites_by_parent.values())
        ),
        "all_official_sirets_match_parent_and_snapshot": all(
            official_society_site_siret_checks
        ),
        "all_official_headquarter_names_match_parent_and_snapshot": all(
            official_society_site_name_checks
        ),
        "all_synthetic_sites_leave_siret_and_nic_blank": all(
            not row["PseudoSIRET"].strip() and not row["NIC"].strip()
            for row in synthetic_society_sites
        ),
        "ape_provenance": (
            "Code APE officiel de l'unité légale parente ; le snapshot ne prétend pas fournir "
            "l'APE propre du site synthétique."
        ),
        "identifier_policy": (
            "PseudoSIRET renseigné avec le SIRET officiel du siège uniquement ; vide sur le site synthétique."
        ),
    }

    agency_codes = [row["Code"].strip() for row in agencies]
    agency_names = [row["Nom"].strip() for row in agencies]
    tables["Activite.Agences"] = {
        "rows": len(agencies),
        "distinct_codes": len(set(agency_codes)),
        "distinct_names": len(set(agency_names)),
        "all_codes_are_populated": all(agency_codes),
        "all_names_are_populated": all(agency_names),
        "codes_are_globally_unique": len(set(agency_codes)) == len(agencies),
        "names_are_globally_unique": len(set(agency_names)) == len(agencies),
        "identity_policy": "Agences entièrement synthétiques ; aucun SIRET ne leur est attribué.",
    }

    agency_by_id = {row["Id"]: row for row in agencies}
    dossier_by_id = {row["Id"]: row for row in dossiers}
    dossier_codes = [row["Code"].strip() for row in dossiers]
    dossier_names = [row["Nom"].strip() for row in dossiers]
    reached_societies = {
        establishment_by_id[row["EtablissementId"]]["SocieteId"]
        for row in dossiers
        if row["EtablissementId"] in establishment_by_id
    }
    tables["Activite.DossiersAgence"] = {
        "rows": len(dossiers),
        "distinct_codes": len(set(dossier_codes)),
        "distinct_names": len(set(dossier_names)),
        "all_codes_are_populated": all(dossier_codes),
        "all_names_are_populated": all(dossier_names),
        "codes_are_globally_unique": len(set(dossier_codes)) == len(dossiers),
        "names_are_globally_unique": len(set(dossier_names)) == len(dossiers),
        "one_dossier_per_agency": (
            len(dossiers) == len(agencies)
            and set(row["AgenceId"] for row in dossiers) == set(agency_by_id)
            and all(
                count == 1
                for count in Counter(row["AgenceId"] for row in dossiers).values()
            )
        ),
        "all_agency_establishment_society_links_are_valid": all(
            row["AgenceId"] in agency_by_id
            and row["EtablissementId"] in establishment_by_id
            and establishment_by_id[row["EtablissementId"]]["SocieteId"] in society_by_id
            for row in dossiers
        ),
        "distinct_societies_reached": len(reached_societies),
        "covers_every_society": reached_societies == set(society_by_id),
    }

    client_establishment_by_id = {row["Id"]: row for row in client_establishments}
    tables["Activite.EtablissementsClientDossiersAgence"] = {
        "rows": len(client_establishment_dossiers),
        "distinct_client_establishments": len(
            {row["EtablissementClientId"] for row in client_establishment_dossiers}
        ),
        "distinct_dossiers": len({row["DossierAgenceId"] for row in client_establishment_dossiers}),
        "all_links_are_valid": all(
            row["EtablissementClientId"] in client_establishment_by_id
            and row["DossierAgenceId"] in dossier_by_id
            for row in client_establishment_dossiers
        ),
        "covers_every_client_establishment": (
            {row["EtablissementClientId"] for row in client_establishment_dossiers}
            == set(client_establishment_by_id)
        ),
    }

    axis_codes = [row["Code"].strip() for row in axes]
    tables["Activite.AxesAnalytiques"] = {
        "rows": len(axes),
        "distinct_codes": len(set(axis_codes)),
        "all_codes_are_populated": all(axis_codes),
        "codes_are_globally_unique": len(set(axis_codes)) == len(axes),
        "all_client_establishment_paths_are_coherent": all(
            row["EtablissementClientId"] in client_establishment_by_id
            and client_establishment_by_id[row["EtablissementClientId"]]["ClientId"]
            == row["ClientId"]
            for row in axes
        ),
    }

    departments = read_table("Activite__DepartementsEtablissementsClients")
    department_by_id = {row["Id"]: row for row in departments}
    client_dossier_pairs = {
        (row["EtablissementClientId"], row["DossierAgenceId"])
        for row in client_establishment_dossiers
    }

    contract_count = 0
    incoherent_contract_examples: list[str] = []
    for row in iter_table("Activite__ContratsModelesPoste"):
        contract_count += 1
        client_site = client_establishment_by_id.get(row["EtablissementClientId"])
        dossier = dossier_by_id.get(row["DossierAgenceId"])
        department = department_by_id.get(row["DepartementEtablissementClientId"])
        coherent = (
            client_site is not None
            and client_site["ClientId"] == row["ClientIdModelePoste"]
            and row["EtablissementClientIdModelePoste"] == row["EtablissementClientId"]
            and dossier is not None
            and row["AgenceOrigineId"] == dossier["AgenceId"]
            and row["AgenceGestionnaireId"] == dossier["AgenceId"]
            and (row["EtablissementClientId"], row["DossierAgenceId"])
            in client_dossier_pairs
            and department is not None
            and department["EtablissementClientId"] == row["EtablissementClientId"]
        )
        if not coherent and len(incoherent_contract_examples) < 5:
            incoherent_contract_examples.append(row["Id"])
    tables["Activite.ContratsModelesPoste"] = {
        "rows": contract_count,
        "all_identity_paths_are_coherent": not incoherent_contract_examples,
        "incoherent_examples": incoherent_contract_examples,
    }

    invoice_count = 0
    incoherent_invoice_examples: list[str] = []
    for row in iter_table("Activite__Factures"):
        invoice_count += 1
        client_site = client_establishment_by_id.get(row["EtablissementClientId"])
        dossier = dossier_by_id.get(row["SpecialisationDossierAgenceId"])
        department = department_by_id.get(row["DepartementClientId"])
        coherent = (
            client_site is not None
            and client_site["ClientId"] == row["ClientId"]
            and dossier is not None
            and dossier["AgenceId"] == row["AgenceId"]
            and dossier["EtablissementId"] == row["EtablissementId"]
            and (
                row["EtablissementClientId"],
                row["SpecialisationDossierAgenceId"],
            )
            in client_dossier_pairs
            and department is not None
            and department["EtablissementClientId"] == row["EtablissementClientId"]
        )
        if not coherent and len(incoherent_invoice_examples) < 5:
            incoherent_invoice_examples.append(row["Id"])
    tables["Activite.Factures"] = {
        "rows": invoice_count,
        "all_identity_paths_are_coherent": not incoherent_invoice_examples,
        "incoherent_examples": incoherent_invoice_examples,
    }

    client_sirens = {row["SIREN"] for row in clients}
    society_sirens = {row["SIREN"] for row in societies}
    client_sirets = {row["SIRET"].strip() for row in official_client_sites}
    society_sirets = {row["PseudoSIRET"].strip() for row in official_society_sites}

    profile = PROFILES[profile_name]
    expected_rows = {
        "Activite.Clients": profile.clients * shard_count,
        "Activite.Societes": profile.societes * shard_count,
        "Activite.Agences": profile.agences * shard_count,
        "Activite.DossiersAgence": profile.agences * shard_count,
        "Activite.Etablissements": (
            max(profile.societes * 2, math.ceil(profile.agences / 2)) * shard_count
        ),
        "Activite.EtablissementsClient": profile.etablissements_clients * shard_count,
        "Activite.EtablissementsClientDossiersAgence": (
            profile.etablissements_clients * shard_count
        ),
        "Activite.AxesAnalytiques": profile.etablissements_clients * shard_count,
        "Activite.ContratsModelesPoste": profile.contrats * shard_count,
    }
    generation_plan_matches = all(
        (
            tables[table]["rows"] >= expected
            if table == "Activite.EtablissementsClientDossiersAgence"
            else tables[table]["rows"] == expected
        )
        for table, expected in expected_rows.items()
    )

    society_summary = tables["Activite.Societes"]
    diversity_applies = profile_name == "client" and shard_count >= DEFAULT_SHARDS["client"]
    diversity_checks = {
        "at_least_96_societies": society_summary["rows"] >= 96,
        "at_least_20_source_areas": society_summary["distinct_source_query_areas"] >= 20,
        "at_least_40_ape_codes": society_summary["distinct_ape_codes"] >= 40,
        "at_least_20_ape_divisions": society_summary["distinct_ape_divisions"] >= 20,
        "at_least_6_legal_forms": society_summary["distinct_legal_forms"] >= 6,
        "siren_prefix_coverage_at_least_70_percent": (
            society_summary["siren_prefix_3_coverage_ratio"] >= 0.70
        ),
        "maximum_source_area_share_at_most_15_percent": (
            society_summary["maximum_source_query_area_share"] <= 0.15
        ),
    }
    diversity_requirements = {
        "applied": diversity_applies,
        "scope": "profil client sur au moins 12 partitions",
        "checks": diversity_checks,
        "passed": not diversity_applies or all(diversity_checks.values()),
    }

    expected_true_fields = (
        ("Activite.Clients", "all_sirens_are_nine_digits"),
        ("Activite.Clients", "all_sirens_pass_luhn"),
        ("Activite.Clients", "all_identities_match_official_snapshot"),
        ("Activite.Clients", "all_company_names_are_populated"),
        ("Activite.Clients", "sirens_are_globally_unique"),
        ("Activite.Clients", "one_identity_per_row"),
        ("Activite.Societes", "all_sirens_are_nine_digits"),
        ("Activite.Societes", "all_sirens_pass_luhn"),
        ("Activite.Societes", "all_identities_match_official_snapshot"),
        ("Activite.Societes", "all_company_names_are_populated"),
        ("Activite.Societes", "sirens_are_globally_unique"),
        ("Activite.Societes", "one_identity_per_row"),
        ("Activite.Societes", "all_codes_are_populated"),
        ("Activite.Societes", "codes_are_globally_unique"),
        ("Activite.Societes", "all_vat_codes_match_siren_derivation"),
        ("Activite.EtablissementsClient", "all_sites_link_to_a_known_parent"),
        ("Activite.EtablissementsClient", "one_official_headquarters_per_parent"),
        ("Activite.EtablissementsClient", "all_official_sirets_match_parent_and_snapshot"),
        (
            "Activite.EtablissementsClient",
            "all_official_headquarter_names_match_parent_and_snapshot",
        ),
        ("Activite.EtablissementsClient", "all_synthetic_sites_leave_siret_and_nic_blank"),
        ("Activite.Etablissements", "all_codes_are_populated"),
        ("Activite.Etablissements", "codes_are_globally_unique"),
        ("Activite.Etablissements", "all_sites_link_to_a_known_parent"),
        ("Activite.Etablissements", "all_site_ape_codes_match_the_parent"),
        ("Activite.Etablissements", "one_official_headquarters_per_parent"),
        ("Activite.Etablissements", "all_official_sirets_match_parent_and_snapshot"),
        (
            "Activite.Etablissements",
            "all_official_headquarter_names_match_parent_and_snapshot",
        ),
        ("Activite.Etablissements", "all_synthetic_sites_leave_siret_and_nic_blank"),
        ("Activite.Agences", "all_codes_are_populated"),
        ("Activite.Agences", "all_names_are_populated"),
        ("Activite.Agences", "codes_are_globally_unique"),
        ("Activite.Agences", "names_are_globally_unique"),
        ("Activite.DossiersAgence", "all_codes_are_populated"),
        ("Activite.DossiersAgence", "all_names_are_populated"),
        ("Activite.DossiersAgence", "codes_are_globally_unique"),
        ("Activite.DossiersAgence", "names_are_globally_unique"),
        ("Activite.DossiersAgence", "one_dossier_per_agency"),
        ("Activite.DossiersAgence", "all_agency_establishment_society_links_are_valid"),
        ("Activite.DossiersAgence", "covers_every_society"),
        ("Activite.EtablissementsClientDossiersAgence", "all_links_are_valid"),
        ("Activite.EtablissementsClientDossiersAgence", "covers_every_client_establishment"),
        ("Activite.AxesAnalytiques", "all_codes_are_populated"),
        ("Activite.AxesAnalytiques", "codes_are_globally_unique"),
        ("Activite.AxesAnalytiques", "all_client_establishment_paths_are_coherent"),
        ("Activite.ContratsModelesPoste", "all_identity_paths_are_coherent"),
        ("Activite.Factures", "all_identity_paths_are_coherent"),
    )
    client_society_sirens_disjoint = client_sirens.isdisjoint(society_sirens)
    client_society_sirets_disjoint = client_sirets.isdisjoint(society_sirets)
    passed = (
        generation_plan_matches
        and diversity_requirements["passed"]
        and client_society_sirens_disjoint
        and client_society_sirets_disjoint
        and all(tables[table][field] for table, field in expected_true_fields)
    )
    return {
        "passed": passed,
        "generation_plan": {
            "profile": profile_name,
            "partitions": shard_count,
            "expected_rows": expected_rows,
            "row_rule_notes": {
                "Activite.EtablissementsClientDossiersAgence": (
                    "minimum attendu ; des rattachements supplémentaires conservent les "
                    "affectations historiques des contrats"
                )
            },
            "row_counts_match": generation_plan_matches,
        },
        "diversity_requirements": diversity_requirements,
        "client_and_society_sirens_are_disjoint": client_society_sirens_disjoint,
        "client_and_society_sirets_are_disjoint": client_society_sirets_disjoint,
        "tables": tables,
    }


def generate_bundle(
    *,
    profile_name: str = "client",
    scale: float = 1.0,
    shards: int | None = None,
    seed: int = 20_260_717,
    output: Path,
    sqlite: bool = False,
    force: bool = False,
    progress: Callable[[str], None] = print,
) -> dict[str, Any]:
    if profile_name not in PROFILES:
        raise ValueError(f"Profil inconnu : {profile_name}")
    shard_count = resolve_shards(profile_name, scale, shards)
    _validate_generation_capacity(profile_name, shard_count)
    output = output.resolve()
    if output.exists():
        if not force:
            raise FileExistsError(f"Le dossier existe déjà : {output}. Utilisez --force pour le remplacer.")
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.staging-{uuid.uuid4().hex[:8]}"
    staging.mkdir(parents=True)
    started = time.perf_counter()
    writer = CsvBundleWriter(staging / "csv")
    shard_reports: list[dict[str, Any]] = []
    post_updates: list[str] = []
    profile = PROFILES[profile_name]

    try:
        for shard in range(shard_count):
            shard_seed = seed + shard * 1_000_003
            cfg = DatasetConfig(seed=shard_seed)
            progress(f"Partition {shard + 1}/{shard_count} — seed {shard_seed}")
            dataset = build_dataset(
                cfg,
                profile,
                partition=shard,
                reserved_client_identities=profile.clients * shard_count,
            )
            audit = run_audit(dataset, cfg, profile)
            if not audit["passed"]:
                failed = [name for name, item in audit["checks"].items() if not item["passed"]]
                raise RuntimeError(f"Audit en échec sur la partition {shard + 1}: {', '.join(failed)}")
            identity_metrics = _partition_identity_metrics(dataset["tables"])
            writer.append(dataset["tables"], shard)
            post_updates.extend(dataset["metadata"]["post_load_updates"])
            shard_reports.append({
                "partition": shard + 1,
                "seed": shard_seed,
                "business_rows": audit["business_rows"],
                "checks": audit["checks"],
                "identity_metrics": identity_metrics,
            })
            del dataset, audit
            gc.collect()
            progress(f"Partition {shard + 1}/{shard_count} validée et écrite")
        writer.close()

        company_identity_audit = _audit_company_identities(
            staging / "csv",
            profile_name=profile_name,
            shard_count=shard_count,
        )
        if not company_identity_audit["passed"]:
            raise RuntimeError("Audit global en échec sur les identités légales ou leurs relations")

        business_rows = sum(writer.row_counts.get(name, 0) for name in BUSINESS_TABLES)
        baseline_10x = 2_704_380
        minimum_check = profile_name != "client" or scale != 1.0 or shards is not None or business_rows >= baseline_10x
        if not minimum_check:
            raise RuntimeError(
                f"Le profil client par défaut produit {business_rows:,} lignes métier, "
                f"sous le minimum contractuel de {baseline_10x:,}."
            )

        write_sql_server_kit(
            target=staging / "sql",
            columns=writer.columns,
            row_counts=dict(writer.row_counts),
            post_updates=post_updates,
        )
        if sqlite:
            progress("Création de la base SQLite portable")
            export_sqlite(staging / "csv", staging / "sqlite" / "KevserDateGen.db", writer.columns)

        csv_bytes = sum(path.stat().st_size for path in (staging / "csv").glob("*.csv"))
        elapsed = round(time.perf_counter() - started, 2)
        reference_metadata = company_reference_metadata()
        report = {
            "generator": "Kevser-Date-Gen",
            "version": __version__,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "profile": profile_name,
            "scale": scale,
            "partitions": shard_count,
            "base_seed": seed,
            "period": {"start": "2023-07-01", "end": "2026-06-30"},
            "row_counts": dict(writer.row_counts),
            "business_rows": business_rows,
            "total_rows": sum(writer.row_counts.values()),
            "csv_bytes": csv_bytes,
            "elapsed_seconds": elapsed,
            "default_minimum_10x_passed": minimum_check,
            "all_partition_audits_passed": True,
            "company_identity_audit": company_identity_audit,
            "company_identity_source": {
                "name": reference_metadata["source_name"],
                "source_api": reference_metadata["source_api"],
                "snapshot_date": reference_metadata["snapshot_date"],
                "reference_records": len(load_company_reference()),
                "csv_sha256": reference_metadata["csv_sha256"],
                "license": reference_metadata["license"],
            },
            "partition_reports": shard_reports,
            "privacy": (
                "Les identités publiques des personnes morales viennent du snapshot Sirene embarqué. "
                "Les personnes, coordonnées opérationnelles, adresses et transactions restent synthétiques."
            ),
        }
        (staging / "generation-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (staging / "README.txt").write_text(
            "Dataset généré par Kevser-Date-Gen.\n"
            "ATTENTION : les identités légales sont réelles, mais les adresses, "
            "personnes, risques, activités financières et transactions sont fictifs. "
            "N'en déduisez rien sur les entreprises citées.\n"
            "Consultez generation-report.json, manifest.sha256 et le dossier sql/.\n",
            encoding="utf-8",
        )
        _write_manifest(staging)
        staging.rename(output)
        report["output"] = str(output)
        progress(
            f"Terminé : {report['business_rows']:,} lignes métier, "
            f"{report['total_rows']:,} lignes au total, {csv_bytes / 1024**2:.1f} Mo de CSV"
        )
        return report
    except Exception:
        writer.close()
        if staging.exists():
            shutil.rmtree(staging)
        raise
