from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kevser_date_gen.config import DEFAULT_SHARDS
from kevser_date_gen.engine import LOAD_ORDER
from kevser_date_gen.streaming import generate_bundle, resolve_shards


class GenerationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
