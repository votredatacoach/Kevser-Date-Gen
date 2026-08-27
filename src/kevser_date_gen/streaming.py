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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .company_reference import is_luhn_valid, load_company_reference
from .config import DEFAULT_SHARDS, DatasetConfig, PROFILES
from .engine import LOAD_ORDER, _csv_value, _ddl_column_types, build_dataset, run_audit
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


def _audit_company_identities(csv_root: Path) -> dict[str, Any]:
    """Contrôle les identités d'entreprise après concaténation des partitions."""
    reference = {record["siren"]: record for record in load_company_reference()}
    tables: dict[str, dict[str, Any]] = {}
    for table in ("Activite__Clients", "Activite__Societes"):
        path = csv_root / f"{table}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="|"))
        sirens = [row["SIREN"] for row in rows]
        names = [row["RaisonSociale"].strip() for row in rows]
        official_matches = [
            value in reference
            and reference[value]["raison_sociale"] == name
            for value, name in zip(sirens, names)
        ]
        tables[table.replace("__", ".")] = {
            "rows": len(rows),
            "distinct_sirens": len(set(sirens)),
            "distinct_company_names": len(set(names)),
            "all_sirens_are_nine_digits": all(len(value) == 9 and value.isdigit() for value in sirens),
            "all_sirens_pass_luhn": all(is_luhn_valid(value) for value in sirens),
            "all_identities_match_official_snapshot": all(official_matches),
            "one_identity_per_row": len(set(sirens)) == len(rows) == len(set(names)),
        }
    passed = all(
        item["all_sirens_are_nine_digits"]
        and item["all_sirens_pass_luhn"]
        and item["all_identities_match_official_snapshot"]
        and item["one_identity_per_row"]
        for item in tables.values()
    )
    return {"passed": passed, "tables": tables}


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
            dataset = build_dataset(cfg, profile, partition=shard)
            audit = run_audit(dataset, cfg, profile)
            if not audit["passed"]:
                failed = [name for name, item in audit["checks"].items() if not item["passed"]]
                raise RuntimeError(f"Audit en échec sur la partition {shard + 1}: {', '.join(failed)}")
            writer.append(dataset["tables"], shard)
            post_updates.extend(dataset["metadata"]["post_load_updates"])
            shard_reports.append({
                "partition": shard + 1,
                "seed": shard_seed,
                "business_rows": audit["business_rows"],
                "checks": audit["checks"],
            })
            del dataset, audit
            gc.collect()
            progress(f"Partition {shard + 1}/{shard_count} validée et écrite")
        writer.close()

        company_identity_audit = _audit_company_identities(staging / "csv")
        if not company_identity_audit["passed"]:
            raise RuntimeError("Audit global en échec sur les SIREN ou les raisons sociales")

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
                "name": "Sirene - API Recherche d'entreprises",
                "snapshot_date": "2026-08-27",
                "reference_records": len(load_company_reference()),
                "license": "Licence Ouverte 2.0",
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
