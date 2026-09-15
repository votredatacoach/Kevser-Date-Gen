"""Construit un extrait reproductible de personnes morales depuis l'API publique de l'État.

La sortie contient uniquement des identités d'entreprises publiques : aucun
dirigeant, entrepreneur individuel ou autre donnée de personne physique.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://recherche-entreprises.api.gouv.fr/near_point"
SEARCH_AREAS = (
    ("Paris", 48.8566, 2.3522),
    ("Lyon", 45.7640, 4.8357),
    ("Marseille", 43.2965, 5.3698),
    ("Toulouse", 43.6047, 1.4442),
    ("Lille", 50.6292, 3.0573),
    ("Bordeaux", 44.8378, -0.5792),
    ("Nantes", 47.2184, -1.5536),
    ("Strasbourg", 48.5734, 7.7521),
    ("Montpellier", 43.6108, 3.8767),
    ("Rennes", 48.1173, -1.6778),
    ("Grenoble", 45.1885, 5.7245),
    ("Rouen", 49.4432, 1.0993),
    ("Dijon", 47.3220, 5.0415),
    ("Angers", 47.4784, -0.5632),
    ("Nimes", 43.8367, 4.3601),
    ("Clermont-Ferrand", 45.7772, 3.0870),
    ("Tours", 47.3941, 0.6848),
    ("Metz", 49.1193, 6.1757),
    ("Besancon", 47.2378, 6.0241),
    ("Orleans", 47.9030, 1.9093),
    ("Mulhouse", 47.7508, 7.3359),
    ("Caen", 49.1829, -0.3707),
    ("Nancy", 48.6921, 6.1844),
    ("Poitiers", 46.5802, 0.3404),
    ("Annecy", 45.8992, 6.1294),
)
FIELDNAMES = (
    "reference_index",
    "siren",
    "raison_sociale",
    "nature_juridique",
    "code_ape",
    "categorie_entreprise",
    "siret_siege",
    "statut_diffusion",
    "date_mise_a_jour_insee",
    "source_query_area",
)


def canonical_csv_sha256(path: Path) -> str:
    """Calcule une empreinte stable malgré la conversion Git CRLF/LF."""
    canonical_bytes = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical_bytes).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--start-page", type=int, default=80)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "sirene_companies.csv",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        help="Fichier JSON de métadonnées (par défaut à côté du CSV).",
    )
    return parser.parse_args()


def fetch_page(area: tuple[str, float, float], page: int, *, retries: int = 5) -> dict:
    _, latitude, longitude = area
    query = urlencode(
        {
            "lat": latitude,
            "long": longitude,
            "radius": 25,
            "per_page": 25,
            "page": page,
            "minimal": "true",
            "include": "siege",
            "sort_by_size": "false",
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Kevser-Date-Gen reference-refresh"},
    )
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise
            retry_after = error.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else 1.5 * (attempt + 1)
        except URLError:
            if attempt == retries - 1:
                raise
            wait = 1.5 * (attempt + 1)
        time.sleep(wait)
    raise AssertionError("Boucle de nouvelle tentative épuisée")


def normalize(result: dict, area_name: str) -> dict[str, str] | None:
    siren = str(result.get("siren") or "").strip()
    name = " ".join(str(result.get("nom_raison_sociale") or "").split())
    legal_form = str(result.get("nature_juridique") or "").strip()
    ape_code = str(result.get("activite_principale") or "").replace(".", "").strip()
    dissemination = str(result.get("statut_diffusion") or "").strip()
    headquarters = result.get("siege") or {}
    siret = str(headquarters.get("siret") or "").strip()

    # Les catégories 5xxx et 6xxx sont des personnes morales de droit privé.
    if not legal_form.startswith(("5", "6")):
        return None
    if dissemination != "O" or str(result.get("etat_administratif") or "") != "A":
        return None
    if str(result.get("categorie_entreprise") or "") not in {"PME", "ETI"}:
        return None
    if str(headquarters.get("etat_administratif") or "") != "A":
        return None
    if len(siren) != 9 or not siren.isdigit() or len(siret) != 14 or not siret.isdigit():
        return None
    if not name or len(name) > 100 or not ape_code:
        return None
    return {
        "siren": siren,
        "raison_sociale": name,
        "nature_juridique": legal_form,
        "code_ape": ape_code,
        "categorie_entreprise": str(result.get("categorie_entreprise") or ""),
        "siret_siege": siret,
        "statut_diffusion": dissemination,
        "date_mise_a_jour_insee": str(result.get("date_mise_a_jour_insee") or ""),
        "source_query_area": area_name,
    }


def main() -> int:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count doit être supérieur ou égal à 1")

    records: list[dict[str, str]] = []
    seen_sirens: set[str] = set()
    seen_names: set[str] = set()
    exhausted: set[str] = set()
    page = args.start_page

    while len(records) < args.count and len(exhausted) < len(SEARCH_AREAS):
        active_areas = [area for area in SEARCH_AREAS if area[0] not in exhausted]
        with ThreadPoolExecutor(max_workers=5) as executor:
            fetched = [(area, executor.submit(fetch_page, area, page)) for area in active_areas]
        for area, future in fetched:
            area_name = area[0]
            payload = future.result()
            results = payload.get("results") or []
            if not results or page >= int(payload.get("total_pages") or 1):
                exhausted.add(area_name)
            for raw in results:
                record = normalize(raw, area_name)
                if record is None:
                    continue
                normalized_name = record["raison_sociale"].casefold()
                if record["siren"] in seen_sirens or normalized_name in seen_names:
                    continue
                seen_sirens.add(record["siren"])
                seen_names.add(normalized_name)
                record["reference_index"] = str(len(records) + 1)
                records.append(record)
                if len(records) >= args.count:
                    break
            print(f"Page {page:03d} / zone {area_name}: {len(records):,}/{args.count:,}", flush=True)
            if len(records) >= args.count:
                break
        page += 1
        time.sleep(0.2)

    if len(records) < args.count:
        raise RuntimeError(f"Seulement {len(records):,} entreprises admissibles récupérées sur {args.count:,}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    metadata_output = args.metadata_output or args.output.with_name("sirene_metadata.json")
    metadata = {
        "snapshot_date": date.today().isoformat(),
        "record_count": len(records),
        "source_name": "Sirene - API Recherche d'entreprises",
        "source_api": API_URL,
        "license": "Licence Ouverte 2.0",
        "csv_sha256": canonical_csv_sha256(args.output),
        "csv_sha256_normalization": "line-endings-lf",
        "criteria": (
            "Unités légales actives et diffusibles, personnes morales privées 5xxx/6xxx, "
            "catégories PME et ETI, sièges actifs."
        ),
    }
    metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Référentiel écrit : {args.output} ({len(records):,} entreprises)")
    print(f"Métadonnées écrites : {metadata_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
