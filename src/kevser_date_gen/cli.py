"""Interface en ligne de commande."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import GENERATED_DIR, PROFILES
from .streaming import generate_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kevser-date-gen",
        description="Génère un dataset ADV synthétique, réaliste et importable dans SQL Server.",
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="client")
    parser.add_argument("--scale", type=float, default=1.0, help="Multiplicateur du profil (défaut : 1.0).")
    parser.add_argument("--shards", type=int, help="Nombre exact de partitions, prioritaire sur --scale.")
    parser.add_argument("--seed", type=int, default=20_260_717)
    parser.add_argument("--output", type=Path, help="Dossier de sortie.")
    parser.add_argument("--sqlite", action="store_true", help="Ajoute une base SQLite portable.")
    parser.add_argument("--force", action="store_true", help="Remplace le dossier de sortie s'il existe.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = args.output or (GENERATED_DIR / args.profile)
    try:
        report = generate_bundle(
            profile_name=args.profile,
            scale=args.scale,
            shards=args.shards,
            seed=args.seed,
            output=output,
            sqlite=args.sqlite,
            force=args.force,
        )
    except (ValueError, FileExistsError, RuntimeError) as error:
        print(f"ERREUR — {error}")
        return 2
    print(json.dumps({
        "output": report["output"],
        "business_rows": report["business_rows"],
        "total_rows": report["total_rows"],
        "elapsed_seconds": report["elapsed_seconds"],
    }, ensure_ascii=False, indent=2))
    return 0
