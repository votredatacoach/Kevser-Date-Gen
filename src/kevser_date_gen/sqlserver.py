"""Génération du kit SQL Server/SSMS à partir du DDL fourni."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import SOURCE_DDL
from .engine import LOAD_ORDER, _ddl_column_types, _schema_corrections_sql, _validation_sql


def _use_variable(text: str) -> str:
    return re.sub(
        r"(?im)^\s*use\s+(?:\[Adventure\]|Adventure)\s*;?\s*$",
        "USE [$(DatabaseName)];",
        text,
    )


def _create_database_sql() -> str:
    return """-- Variable fournie par sqlcmd -v ou par 99_run_all.sql.
USE [master];
GO
IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    DECLARE @DatabaseName sysname = N'$(DatabaseName)';
    DECLARE @CreateDatabaseSql nvarchar(max) = N'CREATE DATABASE ' + QUOTENAME(@DatabaseName);
    EXEC sys.sp_executesql @CreateDatabaseSql;
END;
GO
"""


def _corrected_column_types() -> dict[tuple[str, str], str]:
    pattern = re.compile(
        r"ALTER TABLE \[([^]]+)\]\.\[([^]]+)\] ALTER COLUMN \[([^]]+)\] ([^ ]+) NULL;",
        re.I,
    )
    return {
        (f"{schema}.{table}", column): sql_type.lower()
        for schema, table, column, sql_type in pattern.findall(_schema_corrections_sql())
    }


def _bulk_loader_sql(
    columns: dict[str, list[str]],
    row_counts: dict[str, int],
    post_updates: list[str],
) -> str:
    schema = _ddl_column_types()
    type_overrides = _corrected_column_types()
    lines = [
        "-- Variables fournies par sqlcmd -v ou par 99_run_all.sql.",
        "USE [$(DatabaseName)];",
        "GO",
        "SET NOCOUNT ON;",
        "SET XACT_ABORT ON;",
        "IF EXISTS (SELECT 1 FROM [Activite].[ContratsModelesPoste])",
        "    THROW 51000, 'La base cible contient déjà des données. Utilisez une base vide.', 1;",
        "GO",
        "",
        "-- Les contraintes sont réactivées et vérifiées après le chargement.",
    ]
    for table in LOAD_ORDER:
        if table in columns:
            sch, name = table.split(".", 1)
            lines.append(f"ALTER TABLE [{sch}].[{name}] NOCHECK CONSTRAINT ALL;")
    lines.extend(["GO", ""])

    for table in LOAD_ORDER:
        if table not in columns:
            continue
        sch, name = table.split(".", 1)
        table_columns = columns[table]
        writable_columns = [
            column
            for column in table_columns
            if schema[table][column].strip().lower() not in {"timestamp", "rowversion"}
        ]
        stage = f"#Stage_{name}"
        file_name = f"{table.replace('.', '__')}.csv"
        stage_defs = ",\n    ".join(f"[{column}] nvarchar(max) NULL" for column in table_columns)
        quoted = ", ".join(f"[{column}]" for column in writable_columns)
        conversions = []
        for column in writable_columns:
            sql_type = type_overrides.get((table, column), schema[table][column])
            cleaned = f"NULLIF(REPLACE([{column}], CHAR(13), N''), N'')"
            conversions.append(f"TRY_CONVERT({sql_type}, {cleaned})")
        select_values = ",\n    ".join(conversions)
        lines.extend([
            f"PRINT N'Chargement {table} — {row_counts.get(table, 0):,} lignes';",
            f"CREATE TABLE {stage} (\n    {stage_defs}\n);",
            f"BULK INSERT {stage}",
            f"FROM '$(DataRoot)\\csv\\{file_name}'",
            "WITH (",
            "    FIRSTROW = 2,",
            "    FIELDTERMINATOR = '|',",
            "    ROWTERMINATOR = '0x0a',",
            "    CODEPAGE = '65001',",
            "    TABLOCK,",
            "    BATCHSIZE = 50000",
            ");",
            f"INSERT INTO [{sch}].[{name}] ({quoted})",
            "SELECT",
            f"    {select_values}",
            f"FROM {stage};",
            "IF @@ROWCOUNT = 0 THROW 51001, 'Aucune ligne importée : vérifiez DataRoot.', 1;",
            f"DROP TABLE {stage};",
            "GO",
            "",
        ])

    lines.append("-- Fermeture des deux dépendances circulaires du modèle.")
    lines.extend(post_updates)
    lines.extend(["GO", "", "-- Réactivation avec validation complète des contraintes."])
    for table in reversed(LOAD_ORDER):
        if table in columns:
            sch, name = table.split(".", 1)
            lines.append(f"ALTER TABLE [{sch}].[{name}] WITH CHECK CHECK CONSTRAINT ALL;")
    lines.extend(["GO", "PRINT N'Import terminé et contraintes validées.';", "GO", ""])
    return "\n".join(lines)


def _indexes_sql() -> str:
    return """USE [$(DatabaseName)];
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_RelevesHeures_Contrat_DateDebut')
    CREATE INDEX [IX_RelevesHeures_Contrat_DateDebut]
    ON [Activite].[RelevesHeures] ([ContratId], [DateDebut]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_LignesReleveHeures_Releve')
    CREATE INDEX [IX_LignesReleveHeures_Releve]
    ON [Activite].[LignesReleveHeures] ([ReleveHeuresId], [PartieSemaine]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Factures_Client_DateEdition')
    CREATE INDEX [IX_Factures_Client_DateEdition]
    ON [Activite].[Factures] ([ClientId], [DateEdition])
    INCLUDE ([MontantHt], [IsReglee], [IsAvoir]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_LignesFacture_Facture')
    CREATE INDEX [IX_LignesFacture_Facture]
    ON [Activite].[LignesFacture] ([FactureId])
    INCLUDE ([MontantHT], [Base], [ContratId]);
GO
"""


def _run_all_sql() -> str:
    return """-- Point d'entrée manuel : ouvrir ce fichier dans SSMS en mode SQLCMD.
:setvar DatabaseName "Adventure"
:setvar DataRoot "C:\\Temp\\Kevser-Date-Gen\\generated\\client"
:r .\\00_create_database.sql
:r .\\01_schema.sql
:r .\\02_schema_corrections.sql
:r .\\03_bulk_load.sql
:r .\\04_indexes.sql
:r .\\05_validation.sql
"""


def write_sql_server_kit(
    *,
    target: Path,
    columns: dict[str, list[str]],
    row_counts: dict[str, int],
    post_updates: list[str],
) -> None:
    target.mkdir(parents=True, exist_ok=True)
    ddl = SOURCE_DDL.read_text(encoding="utf-8")
    files: dict[str, str] = {
        "00_create_database.sql": _create_database_sql(),
        "01_schema.sql": _use_variable(ddl),
        "02_schema_corrections.sql": _use_variable(_schema_corrections_sql()),
        "03_bulk_load.sql": _bulk_loader_sql(columns, row_counts, post_updates),
        "04_indexes.sql": _indexes_sql(),
        "05_validation.sql": _use_variable(_validation_sql()),
        "99_run_all.sql": _run_all_sql(),
    }
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8-sig", newline="\n")
