from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kevser_date_gen.config import DEFAULT_SHARDS
from kevser_date_gen.engine import LOAD_ORDER, is_luhn_valid, synthetic_company_identity, synthetic_siren
from kevser_date_gen.sqlserver import _bulk_loader_sql, _create_database_sql, _run_all_sql
from kevser_date_gen.streaming import generate_bundle, resolve_shards


class GenerationTests(unittest.TestCase):
    def test_siren_helpers_match_luhn_and_cover_the_default_client_volume(self) -> None:
        self.assertTrue(is_luhn_valid("732829320"))
        self.assertFalse(is_luhn_valid("732829321"))
        sirens = [synthetic_siren(number) for number in range(1, 3_601)]
        names = [synthetic_company_identity(number)[0] for number in range(1, 3_601)]
        self.assertEqual(len(set(sirens)), 3_600)
        self.assertEqual(len(set(names)), 3_600)

    def test_default_profile_is_larger_than_ten_demo_partitions(self) -> None:
        self.assertGreaterEqual(DEFAULT_SHARDS["client"], 11)
        self.assertEqual(resolve_shards("client", 0.5), 6)
        self.assertEqual(resolve_shards("client", 2), 24)
        self.assertEqual(resolve_shards("client", 1, shards=7), 7)

    def test_smoke_bundle_is_complete_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "smoke"
            report = generate_bundle(profile_name="smoke", output=target, progress=lambda _: None)
            self.assertTrue(report["all_partition_audits_passed"])
            self.assertEqual(len(list((target / "csv").glob("*.csv"))), len(LOAD_ORDER))
            self.assertTrue((target / "sql" / "03_bulk_load.sql").exists())
            schema_sql = (target / "sql" / "01_schema.sql").read_text(encoding="utf-8-sig")
            self.assertTrue(schema_sql.startswith("USE [$(DatabaseName)];"))
            self.assertNotIn(":setvar DatabaseName", schema_sql)
            bulk_sql = (target / "sql" / "03_bulk_load.sql").read_text(encoding="utf-8-sig")
            self.assertNotIn("TRY_CONVERT(timestamp", bulk_sql)
            self.assertNotIn("[Matricule], [RowVersion], [DateCreation]", bulk_sql)
            self.assertIn("TRY_CONVERT(decimal(18,2), NULLIF(REPLACE([NetAFacturer]", bulk_sql)
            self.assertIn("TRY_CONVERT(decimal(18,4), NULLIF(REPLACE([Coefficient]", bulk_sql)
            self.assertTrue((target / "sql" / "99_run_all.sql").exists())
            self.assertTrue((target / "manifest.sha256").exists())
            saved = json.loads((target / "generation-report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["business_rows"], report["business_rows"])

    def test_same_seed_produces_identical_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "a", root / "b"
            generate_bundle(profile_name="smoke", seed=42, output=first, progress=lambda _: None)
            generate_bundle(profile_name="smoke", seed=42, output=second, progress=lambda _: None)
            def digest(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()
            first_files = sorted((first / "csv").glob("*.csv"))
            second_files = sorted((second / "csv").glob("*.csv"))
            self.assertEqual([p.name for p in first_files], [p.name for p in second_files])
            self.assertEqual([digest(p) for p in first_files], [digest(p) for p in second_files])

    def test_partition_offsets_keep_integer_primary_keys_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "two"
            generate_bundle(profile_name="smoke", shards=2, output=target, progress=lambda _: None)
            path = target / "csv" / "Activite__LignesFacture.csv"
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="|"))
            ids = [row["Id"] for row in rows]
            self.assertEqual(len(ids), len(set(ids)))

    def test_company_identities_are_realistic_and_unique_across_partitions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "two"
            report = generate_bundle(profile_name="smoke", shards=2, output=target, progress=lambda _: None)

            def read_table(name: str) -> list[dict[str, str]]:
                path = target / "csv" / f"{name}.csv"
                with path.open(encoding="utf-8", newline="") as handle:
                    return list(csv.DictReader(handle, delimiter="|"))

            clients = read_table("Activite__Clients")
            sirens = [row["SIREN"] for row in clients]
            company_names = [row["RaisonSociale"] for row in clients]
            self.assertEqual(len(sirens), 20)
            self.assertEqual(len(set(sirens)), len(sirens))
            self.assertEqual(len(set(company_names)), len(company_names))
            self.assertTrue(all(len(siren) == 9 and is_luhn_valid(siren) for siren in sirens))

            client_siren_by_id = {row["Id"]: row["SIREN"] for row in clients}
            establishments = read_table("Activite__EtablissementsClient")
            self.assertTrue(all(len(row["SIRET"]) == 14 and is_luhn_valid(row["SIRET"]) for row in establishments))
            self.assertTrue(all(row["SIRET"].startswith(client_siren_by_id[row["ClientId"]]) for row in establishments))

            self.assertTrue(report["company_identity_audit"]["passed"])
            self.assertTrue(
                report["company_identity_audit"]["tables"]["Activite.Clients"]["one_identity_per_row"]
            )

    def test_sql_server_kit_is_safe_for_ssms_and_rowversion(self) -> None:
        create_database = _create_database_sql()
        self.assertIn("IF N'$(RecreateDatabase)' = N'1'", create_database)
        self.assertIn("SET SINGLE_USER WITH ROLLBACK IMMEDIATE", create_database)
        self.assertIn("DROP DATABASE", create_database)
        self.assertIn("QUOTENAME(@DatabaseName)", create_database)
        self.assertNotIn("+ REPLACE('$(DatabaseName)'", create_database)

        bulk_loader = _bulk_loader_sql(
            {
                "Activite.DossierAgenceMatriculeInterimaires": [
                    "DossierAgenceId",
                    "Matricule",
                    "RowVersion",
                    "DateCreation",
                ],
                "Activite.Factures": ["Id", "NetAFacturer"],
                "Activite.LignesFacture": ["Id", "TauxTVA"],
            },
            {
                "Activite.DossierAgenceMatriculeInterimaires": 1,
                "Activite.Factures": 1,
                "Activite.LignesFacture": 1,
            },
            [],
        )
        self.assertIn("[RowVersion] nvarchar(max) NULL", bulk_loader)
        self.assertIn("DROP TABLE IF EXISTS #Stage_DossierAgenceMatriculeInterimaires;", bulk_loader)
        insert = bulk_loader.split(
            "INSERT INTO [Activite].[DossierAgenceMatriculeInterimaires]", 1
        )[1].split("FROM #Stage_DossierAgenceMatriculeInterimaires", 1)[0]
        self.assertNotIn("[RowVersion]", insert)
        self.assertNotIn("TRY_CONVERT(timestamp", insert)
        self.assertIn("TRY_CONVERT(decimal(18,2), NULLIF(REPLACE([NetAFacturer]", bulk_loader)
        self.assertIn("TRY_CONVERT(decimal(18,4), NULLIF(REPLACE([TauxTVA]", bulk_loader)

        run_all = _run_all_sql()
        self.assertIn(":On Error exit", run_all)
        self.assertIn(':setvar RecreateDatabase "0"', run_all)
        self.assertNotIn(":setvar SqlRoot", run_all)
        self.assertIn(":r $(DataRoot)\\sql\\00_create_database.sql", run_all)


if __name__ == "__main__":
    unittest.main()
