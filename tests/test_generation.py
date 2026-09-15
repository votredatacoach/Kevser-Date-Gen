from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kevser_date_gen.company_reference import (
    company_record,
    company_reference_metadata,
    is_luhn_valid,
    load_company_reference,
)
from kevser_date_gen.config import DEFAULT_SHARDS, PROJECT_DIR, PROFILES
from kevser_date_gen.engine import LOAD_ORDER, french_vat_code
from kevser_date_gen.sqlserver import (
    _bulk_loader_sql,
    _create_database_sql,
    _indexes_sql,
    _run_all_sql,
)
from kevser_date_gen.streaming import generate_bundle, resolve_shards


class GenerationTests(unittest.TestCase):
    def test_official_sirene_snapshot_is_dense_unique_and_valid(self) -> None:
        self.assertTrue(is_luhn_valid("732829320"))
        self.assertFalse(is_luhn_valid("732829321"))
        records = load_company_reference()
        sirens = [record["siren"] for record in records]
        names = [record["raison_sociale"].casefold() for record in records]
        self.assertEqual(len(records), 10_000)
        self.assertEqual(len(set(sirens)), len(records))
        self.assertEqual(len(set(names)), len(records))
        self.assertTrue(all(is_luhn_valid(record["siret_siege"]) for record in records))
        self.assertTrue(all(record["nature_juridique"].startswith(("5", "6")) for record in records))
        metadata = company_reference_metadata()
        self.assertEqual(metadata["record_count"], len(records))
        self.assertEqual(metadata["csv_sha256_normalization"], "line-endings-lf")
        self.assertRegex(metadata["snapshot_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(
            [company_record(i)["siren"] for i in range(1, 4)],
            [record["siren"] for record in records[:3]],
        )

    def test_default_profile_is_larger_than_ten_demo_partitions(self) -> None:
        self.assertGreaterEqual(DEFAULT_SHARDS["client"], 11)
        self.assertEqual(resolve_shards("client", 0.5), 6)
        self.assertEqual(resolve_shards("client", 2), 24)
        self.assertEqual(resolve_shards("client", 1, shards=7), 7)

    def test_client_profile_selects_96_diverse_official_societies(self) -> None:
        profile = PROFILES["client"]
        partition_count = DEFAULT_SHARDS["client"]
        society_count = profile.societes * partition_count
        client_count = profile.clients * partition_count
        self.assertEqual(society_count, 96)

        societies = [
            company_record(number, from_end=True, exclude_first=client_count)
            for number in range(1, society_count + 1)
        ]
        clients = [company_record(number) for number in range(1, client_count + 1)]
        society_sirens = {record["siren"] for record in societies}
        client_sirens = {record["siren"] for record in clients}
        area_counts = Counter(record["source_query_area"] for record in societies)

        self.assertEqual(len(society_sirens), society_count)
        self.assertEqual(
            len({record["raison_sociale"].casefold() for record in societies}),
            society_count,
        )
        self.assertTrue(society_sirens.isdisjoint(client_sirens))
        self.assertGreaterEqual(len(area_counts), 20)
        self.assertLessEqual(max(area_counts.values()) / society_count, 0.15)
        self.assertGreaterEqual(len({record["code_ape"] for record in societies}), 40)
        self.assertGreaterEqual(len({record["code_ape"][:2] for record in societies}), 20)
        self.assertGreaterEqual(len({record["nature_juridique"] for record in societies}), 6)
        self.assertGreaterEqual(
            len({record["siren"][:3] for record in societies}) / society_count,
            0.70,
        )
        self.assertTrue(
            all(
                len(record["siren"]) == 9
                and is_luhn_valid(record["siren"])
                and record["raison_sociale"]
                and record["code_ape"]
                and record["nature_juridique"]
                for record in societies
            )
        )

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

            reference = {record["siren"]: record for record in load_company_reference()}
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
            departments = read_table("Activite__DepartementsEtablissementsClients")
            contracts = read_table("Activite__ContratsModelesPoste")
            invoices = read_table("Activite__Factures")

            sirens = [row["SIREN"] for row in clients]
            company_names = [row["RaisonSociale"] for row in clients]
            self.assertEqual(len(sirens), 20)
            self.assertEqual(len(set(sirens)), len(sirens))
            self.assertEqual(len(set(company_names)), len(company_names))
            self.assertTrue(all(len(siren) == 9 and is_luhn_valid(siren) for siren in sirens))
            for row in (*clients, *societies):
                official = reference[row["SIREN"]]
                self.assertEqual(row["RaisonSociale"], official["raison_sociale"])
                self.assertEqual(row["CodeAPE"], official["code_ape"])
                self.assertEqual(row["FormeJuridiqueCode"], official["nature_juridique"])

            self.assertEqual(len(societies), 4)
            self.assertEqual(len({row["SIREN"] for row in societies}), len(societies))
            self.assertTrue(set(sirens).isdisjoint(row["SIREN"] for row in societies))
            self.assertTrue(
                all(row["CodeTvaCee"] == french_vat_code(row["SIREN"]) for row in societies)
            )

            client_siren_by_id = {row["Id"]: row["SIREN"] for row in clients}
            official_client_establishments = [
                row for row in client_establishments if row["SIRET"]
            ]
            synthetic_client_establishments = [
                row for row in client_establishments if not row["SIRET"]
            ]
            self.assertEqual(len(official_client_establishments), len(clients))
            self.assertTrue(
                all(
                    not row["SIRET"] and not row["CodeNIC"]
                    for row in synthetic_client_establishments
                )
            )
            self.assertEqual(
                Counter(row["ClientId"] for row in official_client_establishments),
                Counter({client_id: 1 for client_id in client_siren_by_id}),
            )
            self.assertTrue(
                all(
                    len(row["SIRET"]) == 14 and is_luhn_valid(row["SIRET"])
                    for row in official_client_establishments
                )
            )
            self.assertTrue(
                all(
                    row["SIRET"] == reference[client_siren_by_id[row["ClientId"]]]["siret_siege"]
                    and row["RaisonSociale"]
                    == reference[client_siren_by_id[row["ClientId"]]]["raison_sociale"]
                    and row["SIRET"].startswith(client_siren_by_id[row["ClientId"]])
                    and row["CodeNIC"] == row["SIRET"][-5:]
                    for row in official_client_establishments
                )
            )

            society_by_id = {row["Id"]: row for row in societies}
            official_society_establishments = [
                row for row in establishments if row["PseudoSIRET"]
            ]
            synthetic_society_establishments = [
                row for row in establishments if not row["PseudoSIRET"]
            ]
            self.assertEqual(len(official_society_establishments), len(societies))
            self.assertEqual(
                Counter(row["SocieteId"] for row in official_society_establishments),
                Counter({society_id: 1 for society_id in society_by_id}),
            )
            self.assertTrue(
                all(
                    not row["PseudoSIRET"] and not row["NIC"]
                    for row in synthetic_society_establishments
                )
            )
            for row in establishments:
                parent = society_by_id[row["SocieteId"]]
                self.assertEqual(row["CodeAPE"], parent["CodeAPE"])
                if row["PseudoSIRET"]:
                    official = reference[parent["SIREN"]]
                    self.assertEqual(row["PseudoSIRET"], official["siret_siege"])
                    self.assertEqual(row["RaisonSociale"], official["raison_sociale"])
                    self.assertTrue(row["PseudoSIRET"].startswith(parent["SIREN"]))
                    self.assertTrue(is_luhn_valid(row["PseudoSIRET"]))
                    self.assertEqual(row["NIC"], row["PseudoSIRET"][-5:])

            for rows in (societies, establishments, agencies, dossiers, axes):
                codes = [row["Code"] for row in rows]
                self.assertTrue(all(codes))
                self.assertEqual(len(codes), len(set(codes)))

            agency_by_id = {row["Id"]: row for row in agencies}
            establishment_by_id = {row["Id"]: row for row in establishments}
            dossier_by_id = {row["Id"]: row for row in dossiers}
            self.assertEqual(
                Counter(row["AgenceId"] for row in dossiers),
                Counter({agency_id: 1 for agency_id in agency_by_id}),
            )
            self.assertEqual(
                {
                    establishment_by_id[row["EtablissementId"]]["SocieteId"]
                    for row in dossiers
                },
                set(society_by_id),
            )
            self.assertTrue(
                all(
                    row["AgenceId"] in agency_by_id
                    and row["EtablissementId"] in establishment_by_id
                    for row in dossiers
                )
            )

            client_establishment_by_id = {
                row["Id"]: row for row in client_establishments
            }
            self.assertEqual(
                {
                    row["EtablissementClientId"]
                    for row in client_establishment_dossiers
                },
                set(client_establishment_by_id),
            )
            self.assertTrue(
                all(
                    row["EtablissementClientId"] in client_establishment_by_id
                    and row["DossierAgenceId"] in dossier_by_id
                    for row in client_establishment_dossiers
                )
            )
            client_dossier_pairs = {
                (row["EtablissementClientId"], row["DossierAgenceId"])
                for row in client_establishment_dossiers
            }
            self.assertTrue(
                all(
                    axis["EtablissementClientId"] in client_establishment_by_id
                    and client_establishment_by_id[axis["EtablissementClientId"]]["ClientId"]
                    == axis["ClientId"]
                    for axis in axes
                )
            )
            department_by_id = {row["Id"]: row for row in departments}
            self.assertTrue(
                all(
                    contract["EtablissementClientId"] in client_establishment_by_id
                    and client_establishment_by_id[contract["EtablissementClientId"]]["ClientId"]
                    == contract["ClientIdModelePoste"]
                    and contract["EtablissementClientIdModelePoste"]
                    == contract["EtablissementClientId"]
                    and contract["DossierAgenceId"] in dossier_by_id
                    and (
                        contract["EtablissementClientId"],
                        contract["DossierAgenceId"],
                    )
                    in client_dossier_pairs
                    and dossier_by_id[contract["DossierAgenceId"]]["AgenceId"]
                    == contract["AgenceOrigineId"]
                    == contract["AgenceGestionnaireId"]
                    and contract["DepartementEtablissementClientId"] in department_by_id
                    and department_by_id[contract["DepartementEtablissementClientId"]][
                        "EtablissementClientId"
                    ]
                    == contract["EtablissementClientId"]
                    for contract in contracts
                )
            )
            self.assertTrue(
                all(
                    invoice["EtablissementClientId"] in client_establishment_by_id
                    and client_establishment_by_id[invoice["EtablissementClientId"]]["ClientId"]
                    == invoice["ClientId"]
                    and invoice["SpecialisationDossierAgenceId"] in dossier_by_id
                    and dossier_by_id[invoice["SpecialisationDossierAgenceId"]]["AgenceId"]
                    == invoice["AgenceId"]
                    and dossier_by_id[invoice["SpecialisationDossierAgenceId"]]["EtablissementId"]
                    == invoice["EtablissementId"]
                    and (
                        invoice["EtablissementClientId"],
                        invoice["SpecialisationDossierAgenceId"],
                    )
                    in client_dossier_pairs
                    and invoice["DepartementClientId"] in department_by_id
                    and department_by_id[invoice["DepartementClientId"]][
                        "EtablissementClientId"
                    ]
                    == invoice["EtablissementClientId"]
                    for invoice in invoices
                )
            )

            self.assertTrue(report["company_identity_audit"]["passed"])
            identity_tables = report["company_identity_audit"]["tables"]
            expected_true_fields = {
                "Activite.Clients": (
                    "all_identities_match_official_snapshot",
                    "one_identity_per_row",
                ),
                "Activite.Societes": (
                    "all_identities_match_official_snapshot",
                    "one_identity_per_row",
                    "codes_are_globally_unique",
                    "all_vat_codes_match_siren_derivation",
                ),
                "Activite.EtablissementsClient": (
                    "one_official_headquarters_per_parent",
                    "all_official_sirets_match_parent_and_snapshot",
                    "all_official_headquarter_names_match_parent_and_snapshot",
                    "all_synthetic_sites_leave_siret_and_nic_blank",
                ),
                "Activite.Etablissements": (
                    "codes_are_globally_unique",
                    "one_official_headquarters_per_parent",
                    "all_official_sirets_match_parent_and_snapshot",
                    "all_official_headquarter_names_match_parent_and_snapshot",
                    "all_synthetic_sites_leave_siret_and_nic_blank",
                ),
                "Activite.Agences": ("codes_are_globally_unique",),
                "Activite.DossiersAgence": (
                    "codes_are_globally_unique",
                    "one_dossier_per_agency",
                    "all_agency_establishment_society_links_are_valid",
                    "covers_every_society",
                ),
                "Activite.EtablissementsClientDossiersAgence": (
                    "all_links_are_valid",
                    "covers_every_client_establishment",
                ),
                "Activite.AxesAnalytiques": (
                    "codes_are_globally_unique",
                    "all_client_establishment_paths_are_coherent",
                ),
                "Activite.ContratsModelesPoste": ("all_identity_paths_are_coherent",),
                "Activite.Factures": ("all_identity_paths_are_coherent",),
            }
            for table, fields in expected_true_fields.items():
                for field in fields:
                    self.assertTrue(identity_tables[table][field], f"{table}.{field}")

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
        self.assertIn("IF @@ROWCOUNT <> 1 THROW 51001", bulk_loader)
        self.assertNotIn("IF @@ROWCOUNT = 0", bulk_loader)

        indexes = _indexes_sql()
        self.assertNotIn("WITH CHECK CHECK CONSTRAINT ALL", bulk_loader)
        self.assertIn("IX_LignesFacture_Contrat", indexes)
        self.assertIn("IX_LignesFacture_LigneRh", indexes)
        self.assertIn("IX_MouvementsReleveHeures_Releve", indexes)
        self.assertIn("IX_LignesReleveHeures_AxeAnalytique", indexes)
        self.assertLess(
            indexes.index("IX_LignesFacture_LigneRh"),
            indexes.index("WITH CHECK CHECK CONSTRAINT ALL"),
        )
        self.assertIn("object_id = OBJECT_ID(N'[Activite].[LignesFacture]')", indexes)

        run_all = _run_all_sql()
        self.assertIn(":On Error exit", run_all)
        self.assertIn(':setvar RecreateDatabase "0"', run_all)
        self.assertNotIn(":setvar SqlRoot", run_all)
        self.assertIn(":r $(DataRoot)\\sql\\00_create_database.sql", run_all)

        import_script = (PROJECT_DIR / "scripts" / "import-sqlserver.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("manifest.sha256", import_script)
        self.assertIn("Get-FileHash -Algorithm SHA256", import_script)
        self.assertIn("L'import est annulé avant toute modification SQL", import_script)
        self.assertLess(import_script.index("Get-FileHash"), import_script.index("$Scripts = @("))

    def test_capacity_failure_does_not_remove_an_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "existing"
            target.mkdir()
            sentinel = target / "keep.txt"
            sentinel.write_text("à conserver", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Capacité de génération dépassée"):
                generate_bundle(
                    profile_name="smoke",
                    shards=324,
                    output=target,
                    force=True,
                    progress=lambda _: None,
                )

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "à conserver")


if __name__ == "__main__":
    unittest.main()
