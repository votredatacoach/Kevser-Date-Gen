"""Tests de non-regression du script SQL Server de validation post-import."""

from __future__ import annotations

import unittest

from kevser_date_gen.engine import _validation_sql
from kevser_date_gen.sqlserver import _use_variable


class SqlValidationScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sql = _validation_sql()

    def test_sqlserver_kit_rewrites_the_database_name(self) -> None:
        sqlcmd_script = _use_variable(self.sql)

        self.assertIn("USE [$(DatabaseName)];", sqlcmd_script)
        self.assertNotIn("USE [Adventure];", sqlcmd_script)

    def test_identity_checks_are_blocking_and_complete(self) -> None:
        expected_checks = (
            "LignesFacture_Facture_orphelines",
            "Factures_rapprochement_lignes",
            "Clients_SIREN_format",
            "Clients_SIREN_doublons",
            "Societes_SIREN_format",
            "Societes_SIREN_doublons",
            "Societes_Code_vide",
            "Societes_Code_doublons",
            "Agences_Code_vide",
            "Agences_Code_doublons",
            "DossiersAgence_Code_vide",
            "DossiersAgence_Code_doublons",
            "Societes_un_SIRET_reference",
            "Societes_SIRET_structure",
            "Societes_SIRET_doublons",
            "Societes_siege_nom_officiel",
            "Societes_etablissement_principal",
            "Societes_sites_synthetiques_sans_SIRET",
            "Societes_CodeAPE_etablissement",
            "Clients_un_SIRET_reference",
            "Clients_SIRET_structure",
            "Clients_SIRET_doublons",
            "Clients_siege_nom_officiel",
            "Clients_sites_synthetiques_sans_NIC",
            "Agences_dossier_principal",
            "DossiersAgence_lignage_societe",
            "EtablissementsClient_dossier_absent",
            "AxesAnalytiques_lignage_client",
            "LignesReleveHeures_lignage_releve",
            "Contrats_lignage_complet",
            "Factures_lignage_complet",
        )

        for check in expected_checks:
            with self.subTest(check=check):
                self.assertIn(f"N'{check}'", self.sql)

        self.assertEqual(
            len(expected_checks), self.sql.count("INSERT INTO @ControlesIdentite")
        )
        self.assertIn("THROW 51002", self.sql)
        self.assertLess(
            self.sql.index("ORDER BY [Controle]"), self.sql.index("THROW 51002")
        )

    def test_siret_and_business_paths_are_checked_without_fabricating_ids(self) -> None:
        required_fragments = (
            "DATALENGTH(e.[PseudoSIRET]) <> 28",
            "LEFT(e.[PseudoSIRET], 9) <> s.[SIREN]",
            "e.[NIC] <> RIGHT(e.[PseudoSIRET], 5)",
            "e.[Id] <> s.[EtablissementPrincipalId]",
            "DATALENGTH(ec.[SIRET]) <> 28",
            "LEFT(ec.[SIRET], 9) <> c.[SIREN]",
            "ec.[CodeNIC] <> RIGHT(ec.[SIRET], 5)",
            "ISNULL(ec.[RaisonSociale], N'') <> ISNULL(c.[RaisonSociale], N'')",
            "ISNULL(e.[RaisonSociale], N'') <> ISNULL(s.[RaisonSociale], N'')",
            "lien.[EtablissementClientId] = contrat.[EtablissementClientId]",
            "lien.[DossierAgenceId] = contrat.[DossierAgenceId]",
            "COUNT(lf.[MontantHT]) <> COUNT(lf.[Id])",
            "axe.[ClientId] IS NULL",
            "contrat.[EtablissementClientIdModelePoste] IS NULL",
            "contrat.[AgenceOrigineId] IS NULL",
            "contrat.[AgenceGestionnaireId] IS NULL",
            "ec.[ClientId] IS NULL",
            "d.[AgenceId] <> f.[AgenceId]",
            "d.[EtablissementId] <> f.[EtablissementId]",
            "dep.[EtablissementClientId] IS NULL",
            "dep.[EtablissementClientId] <> f.[EtablissementClientId]",
            "lien.[EtablissementClientId] = f.[EtablissementClientId]",
            "lien.[DossierAgenceId] = f.[SpecialisationDossierAgenceId]",
        )

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.sql)

        self.assertNotIn("COUNT_BIG()", self.sql)


if __name__ == "__main__":
    unittest.main()
