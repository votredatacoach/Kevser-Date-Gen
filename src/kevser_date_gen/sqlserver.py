"""Génération du kit SQL Server/SSMS à partir du DDL fourni."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import SOURCE_DDL
from .model_stress import ADD_STRESS_SQL, REMOVE_STRESS_SQL
from .engine import (
    LOAD_ORDER,
    _ddl_column_types,
    _schema_corrections_sql,
    _sqlserver_column_type,
    _validation_sql,
)


def _use_variable(text: str) -> str:
    return re.sub(
        r"(?im)^\s*use\s+(?:\[Adventure\]|Adventure)\s*;?\s*$",
        "USE [$(DatabaseName)];",
        text,
    )


def _create_database_sql() -> str:
    return """-- Variables fournies par sqlcmd -v ou par 99_run_all.sql.
-- RecreateDatabase=1 supprime entièrement la base cible avant de la recréer.
USE [master];
GO
DECLARE @DatabaseName sysname = N'$(DatabaseName)';

IF N'$(RecreateDatabase)' = N'1' AND DB_ID(@DatabaseName) IS NOT NULL
BEGIN
    DECLARE @DropDatabaseSql nvarchar(max);
    SET @DropDatabaseSql =
        N'ALTER DATABASE ' + QUOTENAME(@DatabaseName)
        + N' SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE '
        + QUOTENAME(@DatabaseName) + N';';
    EXEC sys.sp_executesql @DropDatabaseSql;
END;

IF DB_ID(@DatabaseName) IS NULL
BEGIN
    DECLARE @CreateDatabaseSql nvarchar(max);
    SET @CreateDatabaseSql = N'CREATE DATABASE ' + QUOTENAME(@DatabaseName);
    EXEC sys.sp_executesql @CreateDatabaseSql;
END;
GO
"""


def _bulk_loader_sql(
    columns: dict[str, list[str]],
    row_counts: dict[str, int],
    post_updates: list[str],
) -> str:
    schema = _ddl_column_types()
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
        stage = f"#Stage_{name}"
        file_name = f"{table.replace('.', '__')}.csv"
        stage_defs = ",\n    ".join(f"[{column}] nvarchar(max) NULL" for column in table_columns)
        target_columns = [
            column
            for column in table_columns
            if schema[table][column].strip().lower() not in {"timestamp", "rowversion"}
        ]
        quoted = ", ".join(f"[{column}]" for column in target_columns)
        conversions = []
        for column in target_columns:
            sql_type = _sqlserver_column_type(table, column, schema[table][column])
            cleaned = f"NULLIF(REPLACE([{column}], CHAR(13), N''), N'')"
            conversions.append(f"TRY_CONVERT({sql_type}, {cleaned})")
        select_values = ",\n    ".join(conversions)
        expected_rows = row_counts.get(table, 0)
        lines.extend([
            f"PRINT N'Chargement {table} — {expected_rows:,} lignes';",
            f"DROP TABLE IF EXISTS {stage};",
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
            (
                f"IF @@ROWCOUNT <> {expected_rows} THROW 51001, "
                f"'Nombre de lignes inattendu pour {table}.', 1;"
            ),
            f"DROP TABLE {stage};",
            "GO",
            "",
        ])

    lines.append("-- Fermeture des deux dépendances circulaires du modèle.")
    lines.extend(post_updates)
    lines.extend(
        [
            "GO",
            "",
            "-- Les index et la validation complète des contraintes sont exécutés",
            "-- dans 04_indexes.sql, après le chargement massif.",
            "PRINT N'Chargement terminé. Création des index et validation des contraintes à suivre.';",
            "GO",
            "",
        ]
    )
    return "\n".join(lines)


def _indexes_sql() -> str:
    def create_index(
        name: str,
        table: str,
        columns: str,
        *,
        include: str | None = None,
    ) -> str:
        include_clause = f"\n    INCLUDE ({include})" if include else ""
        return (
            "IF NOT EXISTS (SELECT 1 FROM sys.indexes "
            f"WHERE object_id = OBJECT_ID(N'{table}') AND name = N'{name}')\n"
            f"    CREATE INDEX [{name}]\n"
            f"    ON {table} ({columns}){include_clause} WITH (MAXDOP = 1);"
        )

    index_statements = "\n".join(
        (
            create_index(
                "IX_RelevesHeures_Contrat_DateDebut",
                "[Activite].[RelevesHeures]",
                "[ContratId], [DateDebut]",
            ),
            create_index(
                "IX_LignesReleveHeures_Releve",
                "[Activite].[LignesReleveHeures]",
                "[ReleveHeuresId], [PartieSemaine]",
            ),
            create_index(
                "IX_LignesReleveHeures_AxeAnalytique",
                "[Activite].[LignesReleveHeures]",
                "[AxeAnalytiqueId]",
            ),
            create_index(
                "IX_LignesReleveHeures_LotFacture",
                "[Activite].[LignesReleveHeures]",
                "[LotFactureId]",
            ),
            create_index(
                "IX_LignesReleveHeures_Rubrique",
                "[Activite].[LignesReleveHeures]",
                "[RubriqueId]",
            ),
            create_index(
                "IX_MouvementsReleveHeures_Releve",
                "[Activite].[MouvementsReleveHeures]",
                "[ReleveHeuresId], [PartieSemaine]",
            ),
            create_index(
                "IX_Factures_Client_DateEdition",
                "[Activite].[Factures]",
                "[ClientId], [DateEdition]",
                include="[MontantHt], [IsReglee], [IsAvoir]",
            ),
            create_index(
                "IX_LignesFacture_Facture",
                "[Activite].[LignesFacture]",
                "[FactureId]",
                include="[MontantHT], [Base], [ContratId]",
            ),
            create_index(
                "IX_LignesFacture_Contrat",
                "[Activite].[LignesFacture]",
                "[ContratId]",
            ),
            create_index(
                "IX_LignesFacture_LigneRh",
                "[Activite].[LignesFacture]",
                "[LigneRhId]",
            ),
            create_index(
                "IX_LignesFacture_Rubrique",
                "[Activite].[LignesFacture]",
                "[RubriqueId]",
            ),
        )
    )
    constraint_checks = "\n".join(
        f"ALTER TABLE [{schema}].[{table}] WITH CHECK CHECK CONSTRAINT ALL;"
        for schema, table in (name.split(".", 1) for name in reversed(LOAD_ORDER))
    )
    return f"""USE [$(DatabaseName)];
GO
SET NOCOUNT ON;
{index_statements}
GO

-- Les index de jointure existent avant la validation des FK volumineuses.
{constraint_checks}
GO
PRINT N'Index créés et contraintes réactivées avec validation complète.';
GO
"""


def _run_all_sql() -> str:
    return """-- Point d'entrée manuel : ouvrir ce fichier dans SSMS en mode SQLCMD.
:On Error exit
:setvar DatabaseName "Adventure"
:setvar RecreateDatabase "0"
:setvar DataRoot "C:\\Temp\\Kevser-Date-Gen\\generated\\client"
:r $(DataRoot)\\sql\\00_create_database.sql
:r $(DataRoot)\\sql\\01_schema.sql
:r $(DataRoot)\\sql\\02_schema_corrections.sql
:r $(DataRoot)\\sql\\03_bulk_load.sql
:r $(DataRoot)\\sql\\04_indexes.sql
:r $(DataRoot)\\sql\\05_validation.sql
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
        "06_model_stress_optional.sql": ADD_STRESS_SQL,
        "07_remove_model_stress_optional.sql": REMOVE_STRESS_SQL,
        "99_run_all.sql": _run_all_sql(),
    }
    for name, content in files.items():
        (target / name).write_text(content, encoding="utf-8-sig", newline="\n")
