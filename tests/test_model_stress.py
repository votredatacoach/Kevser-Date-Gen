from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kevser_date_gen.config import PROJECT_DIR
from kevser_date_gen.model_stress import ADD_STRESS_SQL, REMOVE_STRESS_SQL
from kevser_date_gen.streaming import generate_bundle


class ModelStressTests(unittest.TestCase):
    def test_bundle_delivers_opt_in_scripts_without_changing_business_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "bundle"
            report = generate_bundle(profile_name="smoke", output=target, progress=lambda _: None)
            sql = target / "sql"
            self.assertEqual((sql / "06_model_stress_optional.sql").read_text(encoding="utf-8-sig"), ADD_STRESS_SQL)
            self.assertEqual((sql / "07_remove_model_stress_optional.sql").read_text(encoding="utf-8-sig"), REMOVE_STRESS_SQL)
            self.assertNotIn("model_stress", (sql / "99_run_all.sql").read_text(encoding="utf-8-sig"))
            self.assertNotIn("ChargeTestModele", (sql / "01_schema.sql").read_text(encoding="utf-8-sig"))
            self.assertNotIn("ChargeTestModele", (target / "csv" / "Activite__Factures.csv").read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(report["all_partition_audits_passed"])
            self.assertTrue(report["company_identity_audit"]["passed"])
            manifest = (target / "manifest.sha256").read_text(encoding="utf-8")
            self.assertIn("sql/06_model_stress_optional.sql", manifest)
            self.assertIn("sql/07_remove_model_stress_optional.sql", manifest)

    def test_ssms_entry_points_match_bundled_scripts(self):
        for name, expected in (
            ("06_model_stress_optional.sql", ADD_STRESS_SQL),
            ("07_remove_model_stress_optional.sql", REMOVE_STRESS_SQL),
        ):
            path = PROJECT_DIR / "schema" / "stress" / name
            self.assertEqual(path.read_text(encoding="utf-8"), expected)
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
