"""Moteur de génération, export et audit du dataset de facturation.

Le générateur remplit les 30 tables du DDL transmis par Kevser, mais concentre
la volumétrie sur le flux analytique utile : contrats -> relevés d'heures ->
factures. Les entreprises viennent d'un snapshot Sirene ; le reste est
synthétique et déterministe.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import shutil
import statistics
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from .config import DOCS_DIR, GENERATED_DIR, PROJECT_DIR, SOURCE_DDL, DatasetConfig, VolumeProfile
from .company_reference import company_record, load_company_reference


NAMESPACE = uuid.UUID("51e8f071-1793-4afb-bf2e-bb89afcd6c11")
CREATOR = "GENERATEUR_SYNTHETIQUE_DATACOACH"

LOAD_ORDER = (
    "Referentiel.Communes",
    "Referentiel.CategoriesSocioProfessionnelles",
    "Referentiel.MotifsContrat",
    "Referentiel.MotifsFinContrat",
    "Referentiel.Qualifications",
    "Referentiel.Rubriques",
    "Activite.GroupesClients",
    "Activite.LotsFacturation",
    "Activite.Clients",
    "Activite.Societes",
    "Activite.Etablissements",
    "Activite.Agences",
    "Activite.DossiersAgence",
    "Activite.EtablissementsClient",
    "Activite.DepartementsEtablissementsClients",
    "Activite.EtablissementsClientDossiersAgence",
    "Activite.AxesAnalytiques",
    "Activite.Interimaires",
    "Activite.ParametragesQualification",
    "Activite.PerimetresGroupesClients",
    "Activite.DossierAgenceMatriculeInterimaires",
    "Activite.ContratsModelesPoste",
    "Activite.DonneesContrat",
    "Activite.HorairesEtCouts",
    "Activite.LieuMission",
    "Activite.RelevesHeures",
    "Activite.LignesReleveHeures",
    "Activite.MouvementsReleveHeures",
    "Activite.Factures",
    "Activite.LignesFacture",
)

PK_COLUMNS: dict[str, tuple[str, ...]] = {
    "Activite.Agences": ("Id",),
    "Activite.AxesAnalytiques": ("Id",),
    "Activite.Clients": ("Id",),
    "Activite.ContratsModelesPoste": ("Id",),
    "Activite.DepartementsEtablissementsClients": ("Id",),
    "Activite.DonneesContrat": ("ContratId",),
    "Activite.DossierAgenceMatriculeInterimaires": ("DossierAgenceId",),
    "Activite.DossiersAgence": ("Id",),
    "Activite.Etablissements": ("Id",),
    "Activite.EtablissementsClient": ("Id",),
    "Activite.EtablissementsClientDossiersAgence": ("EtablissementClientId", "DossierAgenceId"),
    "Activite.Factures": ("Id",),
    "Activite.GroupesClients": ("Id",),
    "Activite.HorairesEtCouts": ("ContratId",),
    "Activite.Interimaires": ("Id",),
    "Activite.LieuMission": ("ContratId",),
    "Activite.LignesFacture": ("Id",),
    "Activite.LignesReleveHeures": ("Id",),
    "Activite.LotsFacturation": ("Id",),
    "Activite.MouvementsReleveHeures": ("Id",),
    "Activite.ParametragesQualification": ("ParametrageSpecificitesId", "QualificationCode"),
    "Activite.PerimetresGroupesClients": ("Id",),
    "Activite.RelevesHeures": ("Id", "PartieSemaine"),
    "Activite.Societes": ("Id",),
    "Referentiel.CategoriesSocioProfessionnelles": ("Code",),
    "Referentiel.Communes": ("Id",),
    "Referentiel.MotifsContrat": ("Code",),
    "Referentiel.MotifsFinContrat": ("Code",),
    "Referentiel.Qualifications": ("Code",),
    "Referentiel.Rubriques": ("Id",),
}

# Uniquement les FK effectivement alimentées par le générateur. Les autres
# colonnes du DDL restent NULL et ne peuvent donc pas créer d'orphelin.
FK_CHECKS = (
    ("Activite.Clients", ("CommuneId",), "Referentiel.Communes", ("Id",)),
    ("Activite.Societes", ("CommuneId",), "Referentiel.Communes", ("Id",)),
    ("Activite.Etablissements", ("SocieteId",), "Activite.Societes", ("Id",)),
    ("Activite.Etablissements", ("CommuneId",), "Referentiel.Communes", ("Id",)),
    ("Activite.DossiersAgence", ("AgenceId",), "Activite.Agences", ("Id",)),
    ("Activite.DossiersAgence", ("EtablissementId",), "Activite.Etablissements", ("Id",)),
    ("Activite.EtablissementsClient", ("ClientId",), "Activite.Clients", ("Id",)),
    ("Activite.EtablissementsClient", ("CommuneId",), "Referentiel.Communes", ("Id",)),
    ("Activite.DepartementsEtablissementsClients", ("EtablissementClientId",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.DepartementsEtablissementsClients", ("CommuneId",), "Referentiel.Communes", ("Id",)),
    ("Activite.EtablissementsClientDossiersAgence", ("EtablissementClientId",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.EtablissementsClientDossiersAgence", ("DossierAgenceId",), "Activite.DossiersAgence", ("Id",)),
    ("Activite.AxesAnalytiques", ("EtablissementClientId",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.AxesAnalytiques", ("ClientId",), "Activite.Clients", ("Id",)),
    ("Activite.ParametragesQualification", ("QualificationCode",), "Referentiel.Qualifications", ("Code",)),
    ("Activite.PerimetresGroupesClients", ("GroupeParentId",), "Activite.GroupesClients", ("Id",)),
    ("Activite.PerimetresGroupesClients", ("GroupeClientId",), "Activite.GroupesClients", ("Id",)),
    ("Activite.PerimetresGroupesClients", ("ClientId",), "Activite.Clients", ("Id",)),
    ("Activite.DossierAgenceMatriculeInterimaires", ("DossierAgenceId",), "Activite.DossiersAgence", ("Id",)),
    ("Activite.ContratsModelesPoste", ("AgenceGestionnaireId",), "Activite.Agences", ("Id",)),
    ("Activite.ContratsModelesPoste", ("AgenceOrigineId",), "Activite.Agences", ("Id",)),
    ("Activite.ContratsModelesPoste", ("DepartementEtablissementClientId",), "Activite.DepartementsEtablissementsClients", ("Id",)),
    ("Activite.ContratsModelesPoste", ("ClientIdModelePoste",), "Activite.Clients", ("Id",)),
    ("Activite.ContratsModelesPoste", ("DossierAgenceId",), "Activite.DossiersAgence", ("Id",)),
    ("Activite.ContratsModelesPoste", ("CategorieCode",), "Referentiel.CategoriesSocioProfessionnelles", ("Code",)),
    ("Activite.ContratsModelesPoste", ("InterimaireId",), "Activite.Interimaires", ("Id",)),
    ("Activite.ContratsModelesPoste", ("EtablissementClientId",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.ContratsModelesPoste", ("EtablissementClientIdModelePoste",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.ContratsModelesPoste", ("QualificationCode",), "Referentiel.Qualifications", ("Code",)),
    ("Activite.DonneesContrat", ("ContratId",), "Activite.ContratsModelesPoste", ("Id",)),
    ("Activite.DonneesContrat", ("MotifContratCode",), "Referentiel.MotifsContrat", ("Code",)),
    ("Activite.HorairesEtCouts", ("ContratId",), "Activite.ContratsModelesPoste", ("Id",)),
    ("Activite.HorairesEtCouts", ("AxeAnalytiqueId",), "Activite.AxesAnalytiques", ("Id",)),
    ("Activite.LieuMission", ("ContratId",), "Activite.ContratsModelesPoste", ("Id",)),
    ("Activite.LieuMission", ("CommuneIdLieuMission",), "Referentiel.Communes", ("Id",)),
    ("Activite.RelevesHeures", ("ContratId",), "Activite.ContratsModelesPoste", ("Id",)),
    ("Activite.LignesReleveHeures", ("ReleveHeuresId", "PartieSemaine"), "Activite.RelevesHeures", ("Id", "PartieSemaine")),
    ("Activite.LignesReleveHeures", ("RubriqueId",), "Referentiel.Rubriques", ("Id",)),
    ("Activite.LignesReleveHeures", ("LotFactureId",), "Activite.LotsFacturation", ("Id",)),
    ("Activite.LignesReleveHeures", ("AxeAnalytiqueId",), "Activite.AxesAnalytiques", ("Id",)),
    ("Activite.Factures", ("EtablissementClientId",), "Activite.EtablissementsClient", ("Id",)),
    ("Activite.Factures", ("ClientId",), "Activite.Clients", ("Id",)),
    ("Activite.Factures", ("EtablissementId",), "Activite.Etablissements", ("Id",)),
    ("Activite.Factures", ("DepartementClientId",), "Activite.DepartementsEtablissementsClients", ("Id",)),
    ("Activite.Factures", ("SpecialisationDossierAgenceId",), "Activite.DossiersAgence", ("Id",)),
    ("Activite.Factures", ("AgenceId",), "Activite.Agences", ("Id",)),
    ("Activite.Factures", ("LotId",), "Activite.LotsFacturation", ("Id",)),
    ("Activite.Factures", ("IdParent",), "Activite.Factures", ("Id",)),
    ("Activite.LignesFacture", ("RubriqueId",), "Referentiel.Rubriques", ("Id",)),
    ("Activite.LignesFacture", ("ContratId",), "Activite.ContratsModelesPoste", ("Id",)),
    ("Activite.LignesFacture", ("FactureId",), "Activite.Factures", ("Id",)),
    ("Activite.LignesFacture", ("LigneRhId",), "Activite.LignesReleveHeures", ("Id",)),
)

FIRST_NAMES = (
    "Amel", "Bastien", "Camille", "Dina", "Élodie", "Farid", "Gaëlle", "Hugo",
    "Inès", "Jules", "Kenza", "Léo", "Maya", "Nassim", "Océane", "Paul",
    "Rania", "Samir", "Théo", "Yasmine", "Zoé", "Noé", "Lina", "Mehdi",
)
LAST_NAMES = (
    "Armand", "Bailly", "Caron", "Da Silva", "El Mansouri", "Fabre", "Giraud",
    "Haddad", "Imbert", "Jacob", "Klein", "Leroux", "Moreau", "Nguyen",
    "Olivier", "Perrin", "Renard", "Schmitt", "Traoré", "Vidal",
)
CITIES = (
    "Paris", "Lyon", "Marseille", "Toulouse", "Lille", "Bordeaux", "Nantes",
    "Strasbourg", "Montpellier", "Rennes", "Grenoble", "Rouen", "Dijon",
    "Angers", "Nîmes", "Clermont-Ferrand", "Tours", "Metz", "Besançon",
    "Orléans", "Mulhouse", "Caen", "Nancy", "Poitiers", "Annecy",
)
def stable_uuid(seed: int, entity: str, number: int | str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{seed}|{entity}|{number}"))


def stable_rng(seed: int, label: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{label}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rate(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def random_date(rng: random.Random, start: date, end: date) -> date:
    if end <= start:
        return start
    return start + timedelta(days=rng.randint(0, (end - start).days))


def month_start(value: date) -> date:
    return value.replace(day=1)


def next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)


def month_end(value: date) -> date:
    return next_month(month_start(value)) - timedelta(days=1)


def month_sequence(start: date, end: date) -> list[date]:
    result: list[date] = []
    current = month_start(start)
    while current <= end:
        result.append(current)
        current = next_month(current)
    return result


def audit_columns(created: date) -> dict[str, Any]:
    return {
        "DateCreation": created,
        "DateVersion": created,
        "Createur": CREATOR,
        "Modificateur": CREATOR,
    }


def seasonality_factor(value: date, agency_index: int) -> float:
    monthly = {
        1: 0.94, 2: 0.98, 3: 1.04, 4: 1.07, 5: 1.03, 6: 1.00,
        7: 0.91, 8: 0.82, 9: 1.13, 10: 1.16, 11: 1.08, 12: 0.89,
    }[value.month]
    # Micro-histoire : une agence subit un ralentissement temporaire début 2025.
    if agency_index == 0 and date(2025, 2, 1) <= value <= date(2025, 4, 30):
        monthly *= 0.72
    return monthly


def _split_hours(total: Decimal) -> tuple[Decimal, ...]:
    value = float(total)
    base = [value * 0.20, value * 0.21, value * 0.21, value * 0.20]
    friday = value - sum(base)
    return tuple(money(v) for v in (*base, friday, 0, 0))


def build_dataset(cfg: DatasetConfig, profile: VolumeProfile, *, partition: int = 0) -> dict[str, Any]:
    rng = stable_rng(cfg.seed, f"build-{profile.name}")
    reference_size = len(load_company_reference())
    requested_clients = (partition + 1) * profile.clients
    requested_societes = (partition + 1) * profile.societes
    if requested_clients + requested_societes > reference_size:
        raise ValueError(
            "Le référentiel Sirene embarqué ne permet pas de garantir des identités "
            f"distinctes : {requested_clients} clients + {requested_societes} sociétés "
            f"demandés pour {reference_size} entreprises disponibles."
        )
    created = date(2026, 7, 17)
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in LOAD_ORDER}
    post_load_updates: list[str] = []

    # Référentiels ---------------------------------------------------------
    for i in range(1, profile.communes + 1):
        city = CITIES[(i - 1) % len(CITIES)]
        cp = f"{(i % 95) + 1:02d}{(i * 137) % 1000:03d}"
        tables["Referentiel.Communes"].append({
            "CodeDepartement": cp[:2],
            "LibelleEnMajuscules": city.upper(),
            "CodePostal": cp,
            "Description": city,
            "IsActif": True,
            **audit_columns(created),
            "Id": i,
            "CodeInsee": f"{i:05d}",
            "CodeInseeParent": None,
            "LibelleNormalise": city.upper().replace("-", " "),
            "CodeCollectivite": None,
        })

    categories = (
        ("CAD", "Cadres", 3),
        ("TAM", "Techniciens et agents de maîtrise", 2),
        ("EMP", "Employés", 1),
        ("OUV", "Ouvriers", 1),
        ("LOG", "Logistique", 1),
    )
    for code, description, level in categories:
        tables["Referentiel.CategoriesSocioProfessionnelles"].append({
            "Code": code,
            "Description": description,
            "DureeMaxPeriodeEssai": 5 if level > 1 else 3,
            "MajorationSmic": 5 * level,
            "IsActif": True,
            **audit_columns(created),
            "Niveau": level,
            "IsForfaitJour": code == "CAD",
        })

    qualifications = (
        ("DATA", "Analyste de données", "CAD", 4),
        ("DEV", "Développeur", "CAD", 4),
        ("CHEF", "Chef de projet", "CAD", 5),
        ("TECH", "Technicien de maintenance", "TAM", 3),
        ("ELEC", "Électricien", "TAM", 3),
        ("ASSI", "Assistant administratif", "EMP", 2),
        ("COMPT", "Comptable", "EMP", 3),
        ("VENTE", "Conseiller clientèle", "EMP", 2),
        ("CAR", "Cariste", "LOG", 2),
        ("PREP", "Préparateur de commandes", "LOG", 1),
        ("OPER", "Opérateur de production", "OUV", 1),
        ("SOUDE", "Soudeur", "OUV", 3),
    )
    qualification_meta: dict[str, dict[str, Any]] = {}
    for code, description, category, skill in qualifications:
        qualification_meta[code] = {"category": category, "skill": skill, "description": description}
        tables["Referentiel.Qualifications"].append({
            "Code": code,
            "IsARisque": code in {"ELEC", "CAR", "SOUDE"},
            "CodeGroupeQualification": category,
            "PCS": f"PCS{skill}",
            "ComplementPCSCode": None,
            "Description": description,
            "IsActif": True,
            **audit_columns(created),
            "SecteurDfsCode": None,
            "DetailRisque": "EPI obligatoire" if code in {"ELEC", "CAR", "SOUDE"} else None,
        })

    motifs_contrat = (
        ("ACC", "Accroissement temporaire d'activité"),
        ("REM", "Remplacement d'un salarié"),
        ("SAI", "Emploi saisonnier"),
        ("PRO", "Projet temporaire"),
    )
    for code, description in motifs_contrat:
        tables["Referentiel.MotifsContrat"].append({
            "Code": code, "TypeMotif": 1, "Description": description, "IsActif": True,
            **audit_columns(created), "DureeMin": 1, "DureeMax": 36,
            "DureeMaxLM": 36, "DureeMaxEtranger": 24,
        })

    motifs_fin = (
        ("FIN", "Fin de mission"), ("RUP", "Rupture anticipée"),
        ("EMB", "Embauche par le client"), ("ANN", "Annulation"),
    )
    for code, description in motifs_fin:
        tables["Referentiel.MotifsFinContrat"].append({
            "Code": code, "Description": description, "IsActif": True,
            "CodeLegal": code[:2], **audit_columns(created), "CodeMotifFinContratSante": None,
        })

    rubrics = (
        (1, "HN", "Heures normales", True, False),
        (2, "HS2", "Heures supplémentaires 25 %", True, True),
        (3, "HS5", "Heures supplémentaires 50 %", True, True),
        (4, "PRI", "Prime de mission", False, False),
        (5, "PAN", "Indemnité panier", False, False),
        (6, "REG", "Régularisation", False, False),
    )
    for rubric_id, code, description, is_hour, is_majoration in rubrics:
        tables["Referentiel.Rubriques"].append({
            "Id": rubric_id,
            "IsHeure": is_hour,
            "IsMajoration": is_majoration,
            "IsAutoriseePaie": True,
            "IsAutoriseeFact": True,
            "CategorieCode": "AC",
            "TypeRegleGestion": 1,
            "IsReserveeAdmin": False,
            "IsAutoriseeDansFinancier": True,
            "IsRegul": code == "REGUL",
            "Code": code,
            "Description": description,
            "IsActif": True,
            "IsVisiblePaie": True,
            "IsVisibleFacture": True,
            **audit_columns(created),
            "IsActivite": True,
            "MiseEnCet": False,
        })

    # Lots mensuels -------------------------------------------------------
    lot_id_by_month: dict[tuple[int, int], int] = {}
    for lot_id, month in enumerate(month_sequence(cfg.start_date, cfg.end_date), 1):
        lot_id_by_month[(month.year, month.month)] = lot_id
        tables["Activite.LotsFacturation"].append({
            "Id": lot_id,
            "TypeTraitementFacturation": 1,
            "Description": f"Facturation {month:%Y-%m}",
            "Etat": 2,
            "DateTraitement": month_end(month),
            "DateComptable": month_end(month),
            "DateArrete": month_end(month),
            **audit_columns(created),
            "ModeSelection": 1,
            "DateArreteMois": month_end(month),
            "DateReglementMois": month_end(month) + timedelta(days=30),
            "FrequenceEmission": 1,
            "ModeEnvoiFacture": 1,
        })

    # Groupes clients -----------------------------------------------------
    for i in range(1, profile.groupes_clients + 1):
        tables["Activite.GroupesClients"].append({
            "Description": f"Groupe synthétique {i:02d}",
            **audit_columns(created),
            "DateDebut": cfg.start_date,
            "DateFin": None,
            "PiloteComptePrincipalId": None,
            "PiloteComptePrincipalFonctionCode": "RESP",
            "SegmentCode": ("STRAT", "PME", "ETI")[i % 3],
            "Id": i,
            "TypeGroupeCode": "CLIENT",
        })

    # Clients -------------------------------------------------------------
    client_meta: list[dict[str, Any]] = []
    client_weights: list[float] = []
    for i in range(1, profile.clients + 1):
        company_number = partition * profile.clients + i
        commune = tables["Referentiel.Communes"][(i - 1) % profile.communes]
        tier = rng.choices(("STRAT", "ETI", "PME"), weights=(0.12, 0.33, 0.55), k=1)[0]
        risk = min(0.95, max(0.02, rng.betavariate(2.2, 8.5) + (0.07 if tier == "PME" else 0)))
        weight = rng.paretovariate(1.55) * {"STRAT": 3.2, "ETI": 1.7, "PME": 0.75}[tier]
        client_id = stable_uuid(cfg.seed, "client", i)
        company = company_record(company_number)
        siren = company["siren"]
        company_name = company["raison_sociale"]
        legal_form = company["nature_juridique"]
        ape_code = company["code_ape"]
        client_meta.append({
            "id": client_id, "tier": tier, "risk": risk, "weight": weight,
            "commune": commune, "index": company_number, "siren": siren,
            "name": company_name, "siret_siege": company["siret_siege"],
        })
        client_weights.append(weight)
        tables["Activite.Clients"].append({
            "Id": client_id,
            "Matricule": 100000 + i,
            "SIREN": siren,
            "CodeAPE": ape_code,
            "FormeJuridiqueCode": legal_form,
            "RaisonSociale": company_name,
            "AdresseLigne1": f"{10 + i % 180} rue des Données",
            "AdresseLigne2": None,
            "AdresseLigne3": None,
            "CodePostal": commune["CodePostal"],
            "Ville": commune["Description"],
            "PaysCode": "FR",
            "IndicatifTelephone": "+33",
            "Telephone": None if rng.random() < cfg.missing_contact_rate else f"0100{i % 10_000:04d}",
            "IndicatifFax": None,
            "Fax": None,
            "CentrePayeurCode": f"CP{i % 30:02d}",
            "IsBlocage": risk > 0.82,
            "IsDecompteValide": True,
            "MotifBlocageCode": "IMP" if risk > 0.82 else None,
            **audit_columns(created),
            "IsCpCedex": False,
            "IdAdequat": None,
            "TypeEntrepriseCode": tier,
            "ParametrageFacturationId": None,
            "ParametrageSpecificitesId": None,
            "NoteEllipro": {"STRAT": 5, "ETI": 4, "PME": 3}[tier],
            "IsNoteElliproReadOnly": False,
            "CommentaireSiren": "Identité publique issue du snapshot Sirene du 2026-08-27",
            "CedexId": None,
            "CommuneId": commune["Id"],
            "IsVerificationJourManquantDesactivee": False,
            "StatutDiffusion": 1,
            "EtatAdministratif": 1,
        })

    # Sociétés, établissements, agences et dossiers ----------------------
    societes: list[dict[str, Any]] = []
    for i in range(1, profile.societes + 1):
        company_number = partition * profile.societes + i
        commune = tables["Referentiel.Communes"][(i * 7) % profile.communes]
        company = company_record(company_number, from_end=True)
        siren = company["siren"]
        company_name = company["raison_sociale"]
        legal_form = company["nature_juridique"]
        row = {
            "Id": stable_uuid(cfg.seed, "societe", i),
            "SIREN": siren,
            "RaisonSociale": company_name,
            "Code": f"S{i:02d}",
            "Capital": money(1_000_000 + i * 250_000),
            "CodeTvaCee": f"FR{(12 + 3 * (int(siren) % 97)) % 97:02d}{siren}",
            "Telephone": f"010000{i:04d}",
            "Fax": None,
            "AdresseLigne1": f"{20 + i} avenue du Modèle",
            "CodePostal": commune["CodePostal"],
            "Ville": commune["Description"],
            "PaysCode": "FR",
            "CodeAPE": company["code_ape"],
            **audit_columns(created),
            "FormeJuridiqueCode": legal_form,
            "IndicatifTelephone": "+33",
            "IndicatifFax": None,
            "EtablissementPrincipalId": None,
            "Etat": 1,
            "CommuneId": commune["Id"],
        }
        row["_siret_siege"] = company["siret_siege"]
        row["_code_ape_reference"] = company["code_ape"]
        societes.append(row)
        tables["Activite.Societes"].append(
            {key: value for key, value in row.items() if not key.startswith("_")}
        )

    etablissement_count = max(profile.societes * 2, math.ceil(profile.agences / 2))
    etablissements: list[dict[str, Any]] = []
    for i in range(1, etablissement_count + 1):
        societe = societes[(i - 1) % len(societes)]
        commune = tables["Referentiel.Communes"][(i * 11) % profile.communes]
        is_headquarters = not any(row["SocieteId"] == societe["Id"] for row in etablissements)
        siret = societe["_siret_siege"] if is_headquarters else None
        row = {
            "Id": stable_uuid(cfg.seed, "etablissement", i),
            "RaisonSociale": f"{societe['RaisonSociale']} - {commune['Description']}",
            "SocieteId": societe["Id"],
            "EstAlsaceMoselle": commune["CodeDepartement"] in {"57", "67", "68"},
            "CodeAPE": societe["_code_ape_reference"],
            "Telephone": f"010100{i:04d}",
            "Fax": None,
            "AdresseLigne1": f"{i + 3} boulevard des Analyses",
            "CodePostal": commune["CodePostal"],
            "Ville": commune["Description"],
            "PaysCode": "FR",
            "PseudoSIRET": siret,
            "DateDebutActivite": date(2018 + i % 6, 1, 1),
            "DateFinActivite": None,
            "Code": f"E{i:02d}",
            "NIC": siret[-5:] if siret else None,
            **audit_columns(created),
            "Etat": 1,
            "Nom": None,
            "Prenom": None,
            "MarqueCode": "SYN",
            "Latitude": None,
            "Longitude": None,
            "GeocodeScore": None,
            "CommuneId": commune["Id"],
        }
        etablissements.append(row)
        tables["Activite.Etablissements"].append(row)

    agencies: list[dict[str, Any]] = []
    dossiers: list[dict[str, Any]] = []
    for i in range(1, profile.agences + 1):
        agency_id = stable_uuid(cfg.seed, "agence", i)
        dossier_id = stable_uuid(cfg.seed, "dossier", i)
        city = CITIES[(i * 3) % len(CITIES)]
        agency = {
            "Id": agency_id,
            "Nom": f"Agence {city} {i:02d}",
            "Code": f"A{i:02d}",
            **audit_columns(created),
            "Mail": f"agence{i:02d}@synthese.example.invalid",
            "IndicatifTelephone": "+33",
            "Telephone": f"010200{i:04d}",
            "IndicatifFax": None,
            "Fax": None,
            "DossierAgencePrincipalId": None,
            "IsGeneraliste": i % 4 != 0,
            "IsCertifieCefri": i % 5 == 0,
            "TypeAgence": 1 + i % 3,
            "NbJoursValiditeNssProvisoire": 30,
        }
        dossier = {
            "Id": dossier_id,
            "Code": f"D{i:04d}",
            "Nom": f"Dossier principal {city}",
            "AgenceId": agency_id,
            "EtablissementId": etablissements[(i - 1) % len(etablissements)]["Id"],
            "IsProduction": True,
            **audit_columns(created),
            "IsApporteurAffaires": False,
        }
        agencies.append(agency)
        dossiers.append(dossier)
        tables["Activite.Agences"].append(agency)
        tables["Activite.DossiersAgence"].append(dossier)
        post_load_updates.append(
            f"UPDATE [Activite].[Agences] SET [DossierAgencePrincipalId] = '{dossier_id}' WHERE [Id] = '{agency_id}';"
        )

    for index, societe in enumerate(societes):
        principal = next(row for row in etablissements if row["SocieteId"] == societe["Id"])
        post_load_updates.append(
            f"UPDATE [Activite].[Societes] SET [EtablissementPrincipalId] = '{principal['Id']}' WHERE [Id] = '{societe['Id']}';"
        )

    # Établissements clients, départements, axes --------------------------
    est_client_meta: list[dict[str, Any]] = []
    est_by_client: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dep_by_est: dict[str, dict[str, Any]] = {}
    axis_by_est: dict[str, dict[str, Any]] = {}
    for i in range(1, profile.etablissements_clients + 1):
        client = client_meta[(i - 1) % len(client_meta)]
        commune = tables["Referentiel.Communes"][(i * 13) % profile.communes]
        est_id = stable_uuid(cfg.seed, "etablissement-client", i)
        is_headquarters = not est_by_client[client["id"]]
        siret = client["siret_siege"] if is_headquarters else None
        row = {
            "Id": est_id,
            "CodeNIC": siret[-5:] if siret else None,
            "SIRET": siret,
            "RaisonSociale": f"{client['name']} - site {len(est_by_client[client['id']]) + 1}",
            "AdresseLigne1": f"{15 + i % 200} rue des Indicateurs",
            "CodePostal": commune["CodePostal"],
            "Ville": commune["Description"],
            "PaysCode": "FR",
            "IndicatifTelephone": "+33",
            "Telephone": f"010300{i % 10_000:04d}",
            "IsAdresseSpecifique": True,
            "IsBlocage": False,
            "IsDecompteValide": True,
            "ClientId": client["id"],
            "CentrePayeurCode": f"CP{client['index'] % 30:02d}",
            **audit_columns(created),
            "CommuneId": commune["Id"],
            "StatutDiffusion": 1,
            "EtatAdministratif": 1,
        }
        est_info = {"id": est_id, "client": client, "commune": commune, "row": row}
        est_client_meta.append(est_info)
        est_by_client[client["id"]].append(est_info)
        tables["Activite.EtablissementsClient"].append(row)

        department = {
            "Id": stable_uuid(cfg.seed, "departement-client", i),
            "Libelle": ("Production", "Logistique", "Fonctions support", "Numérique")[i % 4],
            "AdresseLigne1": row["AdresseLigne1"],
            "CodePostal": row["CodePostal"],
            "Ville": row["Ville"],
            "PaysCode": "FR",
            "EtablissementClientId": est_id,
            **audit_columns(created),
            "IsCpCedex": False,
            "CommuneId": commune["Id"],
        }
        dep_by_est[est_id] = department
        tables["Activite.DepartementsEtablissementsClients"].append(department)

        dossier = dossiers[(i - 1) % len(dossiers)]
        tables["Activite.EtablissementsClientDossiersAgence"].append({
            "EtablissementClientId": est_id,
            "DossierAgenceId": dossier["Id"],
            "Matricule": 500000 + i,
            **audit_columns(created),
            "ParametrageFacturationId": None,
            "ParametrageSpecificitesId": None,
            "PublicId": stable_uuid(cfg.seed, "public-etab-client", i),
        })

        axis = {
            "Id": stable_uuid(cfg.seed, "axe", i),
            "Code": f"AXE{i:05d}",
            "FamilleCode": "CENTRECOUT",
            "Valeur": department["Libelle"],
            **audit_columns(created),
            "EtablissementClientId": est_id,
            "ClientId": client["id"],
            "Discriminator": "EtablissementClient",
            "PaysCode": "FR",
            "CodePostal": row["CodePostal"],
            "Ville": row["Ville"],
            "IsActif": True,
        }
        axis_by_est[est_id] = axis
        tables["Activite.AxesAnalytiques"].append(axis)

    # Périmètres groupes clients ----------------------------------------
    for i, client in enumerate(client_meta, 1):
        group_id = 1 + (i - 1) % profile.groupes_clients
        tables["Activite.PerimetresGroupesClients"].append({
            "Id": i,
            "GroupeParentId": group_id,
            "DateDebut": cfg.start_date,
            "DateFin": None,
            **audit_columns(created),
            "ClientId": client["id"],
            "GroupeClientId": group_id,
            "Discriminator": "Client",
        })

    for i, qualification in enumerate(qualifications, 1):
        tables["Activite.ParametragesQualification"].append({
            "ParametrageSpecificitesId": stable_uuid(cfg.seed, "param-qualification", i),
            "QualificationCode": qualification[0],
            "Renommee": qualification[1],
            **audit_columns(created),
            "DetailRisque": "Contrôle EPI" if qualification[0] in {"ELEC", "CAR", "SOUDE"} else None,
        })

    for i, dossier in enumerate(dossiers, 1):
        tables["Activite.DossierAgenceMatriculeInterimaires"].append({
            "DossierAgenceId": dossier["Id"],
            "Matricule": 900000 + i,
            "RowVersion": None,
            **audit_columns(created),
        })

    # Intérimaires --------------------------------------------------------
    interimaires: list[dict[str, Any]] = []
    for i in range(1, profile.interimaires + 1):
        first = FIRST_NAMES[(i * 7) % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 11) % len(LAST_NAMES)]
        city = CITIES[(i * 5) % len(CITIES)]
        # Répartition déterministe : le taux reste stable même dans le profil smoke.
        missing_every = max(1, round(1 / cfg.missing_contact_rate))
        email = None if i == 1 or i % missing_every == 0 else f"candidat{i:07d}@personne.example.invalid"
        row = {
            "Id": stable_uuid(cfg.seed, "interimaire", i),
            "CodeRecruteur": f"REC{i % 25:02d}",
            "Civilite": i % 2,
            "Nom": last.upper(),
            "Prenom": first,
            "IndicatifTelephone": "+33",
            "Telephone": f"0600{i % 1_000_000:06d}",
            "Email": email,
            "PaysNationaliteCode": "FR",
            "Commentaires": "Profil entièrement synthétique",
            "DateDisponibiliteAutre": None,
            "NumeroSecuriteSociale": f"SYNTH-{i:09d}",
            "DateNaissance": date(1962 + i % 44, 1 + i % 12, 1 + i % 27),
            "DepartementNaissanceCode": f"{1 + i % 95:03d}",
            "VilleNaissance": city,
            "PaysNaissanceCode": "FR",
            "Adresse": f"{1 + i % 180} rue Fictive",
            "CodePostal": f"{1 + i % 95:02d}{i % 1000:03d}",
            "Ville": city,
            "PaysCode": "FR",
            "SituationFamilialeCode": ("C", "M", "S")[i % 3],
            "NombrePersonnesACharge": i % 4,
            **audit_columns(created),
            "DateDisponibiliteTheorique": cfg.start_date,
            "TypeDateDisponibilite": 1,
            "NttTransmis": False,
            "FullNameSearch": f"{first} {last}".upper(),
            "SourceRecrutementId": 1 + i % 5,
            "Statut": 1,
            "DateInscription": random_date(rng, date(2019, 1, 1), cfg.end_date),
            "DateDerniereCandidature": random_date(rng, cfg.start_date, cfg.end_date),
        }
        interimaires.append(row)
        tables["Activite.Interimaires"].append(row)

    # Contrats ------------------------------------------------------------
    contract_meta: list[dict[str, Any]] = []
    latest_contract_start = cfg.end_date - timedelta(weeks=profile.min_contract_weeks)
    for i in range(1, profile.contrats + 1):
        client = rng.choices(client_meta, weights=client_weights, k=1)[0]
        establishment = rng.choice(est_by_client[client["id"]])
        agency_index = rng.randrange(len(agencies))
        agency = agencies[agency_index]
        dossier = dossiers[agency_index]
        interim = interimaires[(i * 17 + rng.randrange(len(interimaires))) % len(interimaires)]
        qualification_code = rng.choice(tuple(qualification_meta))
        qual = qualification_meta[qualification_code]
        start = random_date(rng, cfg.start_date, latest_contract_start)
        # Premier lundi à partir de la date tirée, sans sortir de la période.
        start += timedelta(days=(-start.weekday()) % 7)
        duration_weeks = rng.randint(profile.min_contract_weeks, profile.max_contract_weeks)
        end = min(cfg.end_date, start + timedelta(weeks=duration_weeks, days=-1))
        wage = money(11.65 + qual["skill"] * 2.35 + rng.lognormvariate(0, 0.12))
        coefficient = rate(1.48 + qual["skill"] * 0.075 + rng.uniform(-0.06, 0.16))
        bill_rate = money(wage * coefficient)
        contract_id = stable_uuid(cfg.seed, "contrat", i)
        axis = axis_by_est[establishment["id"]]
        department = dep_by_est[establishment["id"]]
        contract = {
            "Id": contract_id,
            "CategorieCode": qual["category"],
            "ProfilPaieCode": f"PP{qual['skill']}",
            "CategorieClientCode": client["tier"],
            "QualificationCode": qualification_code,
            "NiveauQualif": qual["skill"],
            "PositionQualif": 1 + qual["skill"],
            "CoeffQualif": int(100 + qual["skill"] * 25),
            "AutreQualif": None,
            "IsQualifRisque": qualification_code in {"ELEC", "CAR", "SOUDE"},
            "DetailRisque": "EPI obligatoire" if qualification_code in {"ELEC", "CAR", "SOUDE"} else None,
            **audit_columns(created),
            "EtablissementClientId": establishment["id"],
            "InterimaireId": interim["Id"],
            "DossierAgenceId": dossier["Id"],
            "Etat": 2 if end < cfg.end_date else 1,
            "EtatImpression": 1,
            "Numero": 700000 + i,
            "DepartementEtablissementClientId": department["Id"],
            "Libelle": f"Mission {qualification_code} {i:06d}",
            "ClientIdModelePoste": client["id"],
            "EtablissementClientIdModelePoste": establishment["id"],
            "Discriminator": "Contrat",
            "AgenceOrigineId": agency["Id"],
            "TypeDecompteCode": "HEBDO",
            "DatePremiereMiseEnContrat": start,
            "TauxInteressement": rate(0),
            "AgenceGestionnaireId": agency["Id"],
        }
        tables["Activite.ContratsModelesPoste"].append(contract)
        tables["Activite.DonneesContrat"].append({
            "ContratId": contract_id,
            "MotifFinContratCode": "FIN",
            "DateDebut": start,
            "DateFinInitiale": end,
            "DateFin": end,
            "DateFinReelle": end if end < cfg.end_date else None,
            "DateFinPeriodeEssai": min(end, start + timedelta(days=5)),
            "MotifAnnulationContratCode": None,
            "NbJourPeriodeEssai": 5,
            "TypeContratCode": "INTERIM",
            "MotifContratCode": rng.choice(motifs_contrat)[0],
            "TermeCode": "PRECIS",
            "HeureDebut": "08:30",
            "JrTravailleLun": True,
            "JrTravailleMar": True,
            "JrTravailleMer": True,
            "JrTravailleJeu": True,
            "JrTravailleVen": True,
            "JrTravailleSam": False,
            "JrTravailleDim": False,
            **audit_columns(created),
            "DateFinPrevisionnelle": end,
            "MotifFinContratPrevisionnelCode": "FIN",
        })
        tables["Activite.HorairesEtCouts"].append({
            "ContratId": contract_id,
            "HoraireDebut": "08:30",
            "HoraireFin": "17:00",
            "ComplementHoraire": "Pause de 60 minutes",
            "DureeHebdo": money(35),
            "IsDureeHebdoImprimerSurContrat": True,
            "IsTempsPlein": True,
            "SalaireReference": wage,
            "BaseSalaireReference": money(151.67),
            "PrimeReference": None,
            "SalaireRemuneration": wage,
            "BaseSalaireRemuneration": money(151.67),
            "TypeCoefficientCode": "FACT",
            "Coefficient": coefficient,
            "IsCoeffImprimerSurContrat": True,
            "AxeAnalytiqueId": axis["Id"],
            **audit_columns(created),
            "IsPeriodeNonTravailleeRemuneree": False,
            "Descriptif": qual["description"],
            "IsHeuresComplementairesAutorisees": True,
            "UniteSalaire": 1,
            "SalaireAnnuel": money(wage * Decimal("151.67") * 12),
            "NombreJourTravail": money(5),
            "NombreJourRtt": money(0),
            "NombreMois": money(12),
            "ContexteId": 1,
        })
        tables["Activite.LieuMission"].append({
            "ContratId": contract_id,
            "NomOrganisme": establishment["row"]["RaisonSociale"],
            "AdresseLigne1LieuMission": establishment["row"]["AdresseLigne1"],
            "CodePostalLieuMission": establishment["row"]["CodePostal"],
            "VilleLieuMission": establishment["row"]["Ville"],
            "PaysCodeLieuMission": "FR",
            "PersonneDemandee": f"Responsable synthétique {i % 50:02d}",
            "Contact": f"contact{i % 500:03d}@entreprise.example.invalid",
            "MoyenAcces": "Transports en commun",
            "DestinataireEnvoiContrat": "Service RH",
            "AdresseLigne1EnvoiContrat": establishment["row"]["AdresseLigne1"],
            "CodePostalEnvoiContrat": establishment["row"]["CodePostal"],
            "VilleEnvoiContrat": establishment["row"]["Ville"],
            "PaysCodeEnvoiContrat": "FR",
            **audit_columns(created),
            "IsCpCedexLieuMission": False,
            "IsCpCedexEnvoiContrat": False,
            "CommuneIdLieuMission": establishment["commune"]["Id"],
            "CommuneIdEnvoiContrat": establishment["commune"]["Id"],
        })
        contract_meta.append({
            "id": contract_id, "client": client, "establishment": establishment,
            "department": department, "agency": agency, "agency_index": agency_index,
            "dossier": dossier, "axis": axis, "start": start, "end": end,
            "wage": wage, "coefficient": coefficient, "bill_rate": bill_rate,
        })

    # Relevés d'heures et préparation de la facturation ------------------
    invoice_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    releve_counter = 0
    line_rh_counter = 0
    movement_counter = 0
    for contract in contract_meta:
        week = contract["start"]
        while week <= contract["end"]:
            seasonal = seasonality_factor(week, contract["agency_index"])
            absence_probability = 0.025 + (0.07 if week.month in {7, 8, 12} else 0)
            if rng.random() < absence_probability:
                week += timedelta(weeks=1)
                continue
            hours_value = max(18.0, min(45.0, 35.0 * seasonal + rng.gauss(0, 2.4)))
            has_overtime = rng.random() < cfg.overtime_rate * max(0.7, seasonal)
            regular_hours = money(min(hours_value, 35.0))
            overtime_hours = money(max(0.0, hours_value - 35.0) + (rng.uniform(1, 5) if has_overtime else 0))
            releve_counter += 1
            releve_id = stable_uuid(cfg.seed, "releve", releve_counter)
            partie = "1"
            week_end = min(contract["end"], week + timedelta(days=6))
            tables["Activite.RelevesHeures"].append({
                "Id": releve_id,
                "PartieSemaine": partie,
                "ContratId": contract["id"],
                "DateDebut": week,
                "DateFin": week_end,
                **audit_columns(created),
                "PerimetreDelegationId": None,
            })

            all_hours = regular_hours + overtime_hours
            daily = _split_hours(all_hours)
            movement_counter += 1
            tables["Activite.MouvementsReleveHeures"].append({
                "Id": stable_uuid(cfg.seed, "mouvement", movement_counter),
                "ReleveHeuresId": releve_id,
                "PartieSemaine": partie,
                "TypeMouvementId": 1,
                "Lundi": daily[0], "Mardi": daily[1], "Mercredi": daily[2],
                "Jeudi": daily[3], "Vendredi": daily[4], "Samedi": daily[5],
                "Dimanche": daily[6],
                **audit_columns(created),
                "IsRegularisation": False,
            })

            components = [(1, regular_hours, Decimal("1.00"))]
            if overtime_hours > 0:
                components.append((2, overtime_hours, Decimal("1.25")))
            for rubric_id, hours, multiplier in components:
                line_rh_counter += 1
                line_id = stable_uuid(cfg.seed, "ligne-rh", line_rh_counter)
                pay_rate = money(contract["wage"] * multiplier)
                bill_rate = money(contract["bill_rate"] * multiplier)
                base_fact = money(hours * Decimal(str(rng.uniform(0.99, 1.015))))
                amount_pay = money(hours * pay_rate)
                amount_bill = money(base_fact * bill_rate)
                lot_id = lot_id_by_month[(week.year, week.month)]
                tables["Activite.LignesReleveHeures"].append({
                    "Id": line_id,
                    "ReleveHeuresId": releve_id,
                    "PartieSemaine": partie,
                    "RubriqueId": rubric_id,
                    "BasePaie": hours,
                    "BaseFact": base_fact,
                    "TauxPaie": pay_rate,
                    "TauxFact": bill_rate,
                    "MontantPaie": amount_pay,
                    "MontantFact": amount_bill,
                    "Coefficient": contract["coefficient"],
                    "LotPaieId": lot_id,
                    "LotFactureId": lot_id,
                    "AxeAnalytiqueId": contract["axis"]["Id"],
                    **audit_columns(created),
                    "IsRegularisation": False,
                    "IsMontantAuCet": False,
                })
                group_key = (
                    contract["client"]["id"], contract["establishment"]["id"],
                    contract["department"]["Id"], contract["agency"]["Id"],
                    contract["dossier"]["Id"], week.year, week.month,
                )
                invoice_groups[group_key].append({
                    "line_rh_id": line_id,
                    "contract_id": contract["id"],
                    "rubric_id": rubric_id,
                    "base": base_fact,
                    "rate": bill_rate,
                    "amount": amount_bill,
                })
            week += timedelta(weeks=1)

    # Factures et lignes --------------------------------------------------
    establishment_id_by_dossier = {row["Id"]: row["EtablissementId"] for row in dossiers}
    client_by_id = {row["id"]: row for row in client_meta}
    invoice_counter = 0
    invoice_line_counter = 0
    base_invoice_rows: list[dict[str, Any]] = []
    credit_candidates: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for key in sorted(invoice_groups, key=lambda x: (x[5], x[6], x[0], x[3])):
        client_id, est_id, dep_id, agency_id, dossier_id, year, month = key
        group_lines = invoice_groups[key]
        invoice_counter += 1
        invoice_id = stable_uuid(cfg.seed, "facture", invoice_counter)
        edition = month_end(date(year, month, 1))
        net_ht = money(sum((line["amount"] for line in group_lines), Decimal("0")))
        client = client_by_id[client_id]
        recent_factor = 0.07 if edition >= cfg.end_date - timedelta(days=75) else 0
        unpaid_probability = min(0.38, cfg.unpaid_base_rate + client["risk"] * 0.13 + recent_factor)
        is_paid = rng.random() >= unpaid_probability
        if is_paid:
            delay = max(4, int(rng.gammavariate(3.3, 8.0) + client["risk"] * 28))
            payment_date = edition + timedelta(days=delay)
        else:
            payment_date = None
        lot_id = lot_id_by_month[(year, month)]
        invoice = {
            "Id": invoice_id,
            "Numero": 1_000_000 + invoice_counter,
            "DateEdition": edition,
            "DateReglement": payment_date,
            "EtablissementId": establishment_id_by_dossier[dossier_id],
            "ClientId": client_id,
            "EtablissementClientId": est_id,
            "NumeroComplet": f"F{year}{month:02d}{invoice_counter:08d}"[-20:],
            "IdParent": None,
            "HasAvoir": False,
            "IsAvoir": False,
            "IsRefacturation": False,
            "HasRefacturation": False,
            "LotId": lot_id,
            **audit_columns(created),
            "CriteresRupture": "Client|Établissement|Mois",
            "DepartementClientId": dep_id,
            "SpecialisationDossierAgenceId": dossier_id,
            "NetAFacturer": net_ht,
            "AgenceId": agency_id,
            "IsReglee": is_paid,
            "MontantHt": net_ht,
            "AllianceCodeClient": client["tier"],
        }
        base_invoice_rows.append(invoice)
        tables["Activite.Factures"].append(invoice)
        for line in group_lines:
            invoice_line_counter += 1
            ht = line["amount"]
            tva = money(ht * Decimal("0.20"))
            tables["Activite.LignesFacture"].append({
                "Id": invoice_line_counter,
                "FactureId": invoice_id,
                "RubriqueId": line["rubric_id"],
                "ContratId": line["contract_id"],
                "LigneRhId": line["line_rh_id"],
                "Base": line["base"],
                "Taux": line["rate"],
                "MontantTTC": money(ht + tva),
                "MontantHT": ht,
                "TauxTVA": rate(0.20),
                "TVA": tva,
                "Coefficient": rate(line["rate"] / max(Decimal("0.01"), line["rate"] / Decimal("1.75"))),
                **audit_columns(created),
            })
        if rng.random() < cfg.credit_note_rate and group_lines:
            credit_candidates.append((invoice, group_lines))

    # Avoirs liés à une facture existante, avec une ligne négative.
    for original, group_lines in credit_candidates:
        selected = rng.choice(group_lines)
        invoice_counter += 1
        credit_id = stable_uuid(cfg.seed, "facture", invoice_counter)
        credit_ht = -money(selected["amount"] * Decimal(str(rng.uniform(0.25, 1.0))))
        credit_date = min(cfg.end_date + timedelta(days=20), original["DateEdition"] + timedelta(days=rng.randint(7, 45)))
        original["HasAvoir"] = True
        credit = {
            **original,
            "Id": credit_id,
            "Numero": 1_000_000 + invoice_counter,
            "DateEdition": credit_date,
            "DateReglement": credit_date,
            "NumeroComplet": f"A{credit_date:%Y%m}{invoice_counter:08d}"[-20:],
            "IdParent": original["Id"],
            "HasAvoir": False,
            "IsAvoir": True,
            "IsReglee": True,
            "NetAFacturer": credit_ht,
            "MontantHt": credit_ht,
        }
        tables["Activite.Factures"].append(credit)
        invoice_line_counter += 1
        credit_tva = money(credit_ht * Decimal("0.20"))
        tables["Activite.LignesFacture"].append({
            "Id": invoice_line_counter,
            "FactureId": credit_id,
            "RubriqueId": 6,
            "ContratId": selected["contract_id"],
            "LigneRhId": selected["line_rh_id"],
            "Base": money(-selected["base"]),
            "Taux": selected["rate"],
            "MontantTTC": money(credit_ht + credit_tva),
            "MontantHT": credit_ht,
            "TauxTVA": rate(0.20),
            "TVA": credit_tva,
            "Coefficient": rate(1.0),
            **audit_columns(created),
        })

    metadata = {
        "profile": profile.name,
        "seed": cfg.seed,
        "period": {"start": cfg.start_date.isoformat(), "end": cfg.end_date.isoformat()},
        "post_load_updates": post_load_updates,
        "patterns": {
            "temporal": "Creux juillet-août, reprise septembre-octobre, choc agence 1 de février à avril 2025.",
            "segment": "Les clients stratégiques concentrent davantage de missions et de chiffre d'affaires.",
            "correlation": "Montant facturé lié aux heures, au taux métier et aux heures supplémentaires.",
            "event": "Risque client et récence augmentent la probabilité de facture non réglée.",
            "imperfections": "Contacts manquants et libellés clients hétérogènes, sans casser les clés.",
        },
    }
    return {"tables": tables, "metadata": metadata}


def _key(row: dict[str, Any], columns: Iterable[str]) -> tuple[Any, ...]:
    return tuple(row.get(column) for column in columns)


def _ddl_column_types() -> dict[str, dict[str, str]]:
    ddl = SOURCE_DDL.read_text(encoding="utf-8")
    schema: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"CREATE TABLE\s+\[([^]]+)\]\.\[([^]]+)\]\s*\((.*?)\n\);", ddl, re.I | re.S):
        schema_name, table_name, body = match.groups()
        full_name = f"{schema_name}.{table_name}"
        columns: dict[str, str] = {}
        for column_match in re.finditer(r"^\s*\[([^]]+)\]\s+([a-zA-Z0-9]+(?:\s*\([^)]*\))?)", body, re.M):
            column, sql_type = column_match.groups()
            columns[column] = re.sub(r"\s+", "", sql_type).lower()
        schema[full_name] = columns
    return schema


def _ddl_compatibility_errors(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    schema = _ddl_column_types()
    errors: dict[str, Any] = {
        "unknown_columns": 0, "string_too_long": 0,
        "invalid_uuid": 0, "invalid_type": 0, "samples": [],
    }
    def record(kind: str, table: str, column: str, value: Any, sql_type: str | None) -> None:
        errors[kind] += 1
        if len(errors["samples"]) < 20:
            errors["samples"].append({
                "kind": kind, "table": table, "column": column,
                "value": str(value)[:80], "sql_type": sql_type,
            })
    for table, rows in tables.items():
        column_types = schema.get(table, {})
        for row in rows:
            for column, value in row.items():
                sql_type = column_types.get(column)
                if sql_type is None:
                    record("unknown_columns", table, column, value, sql_type)
                    continue
                if value is None:
                    continue
                length_match = re.match(r"(?:n?varchar|n?char)\((\d+)\)", sql_type)
                if length_match and len(str(value)) > int(length_match.group(1)):
                    record("string_too_long", table, column, value, sql_type)
                elif sql_type.startswith("uniqueidentifier"):
                    try:
                        uuid.UUID(str(value))
                    except (ValueError, AttributeError):
                        record("invalid_uuid", table, column, value, sql_type)
                elif sql_type.startswith(("int", "bigint")) and not isinstance(value, int):
                    record("invalid_type", table, column, value, sql_type)
                elif sql_type.startswith("bit") and not isinstance(value, (bool, int)):
                    record("invalid_type", table, column, value, sql_type)
                elif sql_type.startswith(("date", "datetime")) and not isinstance(value, (date, datetime)):
                    record("invalid_type", table, column, value, sql_type)
                elif sql_type.startswith("decimal") and not isinstance(value, (Decimal, int, float)):
                    record("invalid_type", table, column, value, sql_type)
    return errors


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return numerator / denominator if denominator else 0.0


def run_audit(dataset: dict[str, Any], cfg: DatasetConfig, profile: VolumeProfile) -> dict[str, Any]:
    tables = dataset["tables"]
    checks: dict[str, dict[str, Any]] = {}

    ddl_errors = _ddl_compatibility_errors(tables)
    checks["ddl_column_compatibility"] = {
        "passed": all(ddl_errors[key] == 0 for key in ("unknown_columns", "string_too_long", "invalid_uuid", "invalid_type")),
        "details": ddl_errors,
    }

    duplicate_details: dict[str, int] = {}
    for table, columns in PK_COLUMNS.items():
        keys = [_key(row, columns) for row in tables[table]]
        duplicate_details[table] = len(keys) - len(set(keys))
    pk_ok = all(count == 0 for count in duplicate_details.values())
    checks["primary_keys_unique"] = {"passed": pk_ok, "details": duplicate_details}

    orphan_details: dict[str, int] = {}
    for child, child_cols, parent, parent_cols in FK_CHECKS:
        parent_keys = {_key(row, parent_cols) for row in tables[parent]}
        count = 0
        for row in tables[child]:
            value = _key(row, child_cols)
            if any(item is None for item in value):
                continue
            if value not in parent_keys:
                count += 1
        orphan_details[f"{child}({','.join(child_cols)})->{parent}"] = count
    fk_ok = all(count == 0 for count in orphan_details.values())
    checks["populated_foreign_keys"] = {"passed": fk_ok, "details": orphan_details}

    invoice_sums: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in tables["Activite.LignesFacture"]:
        invoice_sums[row["FactureId"]] += row["MontantHT"]
    invoice_errors = sum(
        1 for row in tables["Activite.Factures"]
        if abs(invoice_sums[row["Id"]] - row["NetAFacturer"]) > Decimal("0.02")
    )
    checks["invoice_totals_reconcile"] = {
        "passed": invoice_errors == 0,
        "details": {"mismatches": invoice_errors},
    }

    line_errors = sum(
        1 for row in tables["Activite.LignesReleveHeures"]
        if abs(row["MontantFact"] - money(row["BaseFact"] * row["TauxFact"])) > Decimal("0.02")
    )
    checks["timesheet_amounts_reconcile"] = {
        "passed": line_errors == 0,
        "details": {"mismatches": line_errors},
    }

    contract_dates = {row["ContratId"]: row for row in tables["Activite.DonneesContrat"]}
    invalid_contract_dates = sum(1 for row in contract_dates.values() if row["DateFin"] < row["DateDebut"])
    invalid_payment_dates = sum(
        1 for row in tables["Activite.Factures"]
        if row["DateReglement"] is not None and row["DateReglement"] < row["DateEdition"]
    )
    checks["dates_coherent"] = {
        "passed": invalid_contract_dates == 0 and invalid_payment_dates == 0,
        "details": {
            "invalid_contract_dates": invalid_contract_dates,
            "invalid_payment_dates": invalid_payment_dates,
        },
    }

    positive_lines = [row for row in tables["Activite.LignesFacture"] if row["MontantHT"] > 0]
    hours = [float(row["Base"]) for row in positive_lines]
    amounts = [float(row["MontantHT"]) for row in positive_lines]
    amount_hours_corr = _pearson(hours, amounts)
    checks["hours_revenue_correlation"] = {
        "passed": 0.45 <= amount_hours_corr <= 0.98,
        "details": {"pearson": round(amount_hours_corr, 4), "expected": "0.45..0.98"},
    }

    invoices = [row for row in tables["Activite.Factures"] if not row["IsAvoir"]]
    unpaid_rate = sum(not row["IsReglee"] for row in invoices) / max(1, len(invoices))
    checks["unpaid_rate_plausible"] = {
        "passed": 0.05 <= unpaid_rate <= 0.24,
        "details": {"rate": round(unpaid_rate, 4), "expected": "0.05..0.24"},
    }

    client_revenue: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    invoice_client = {row["Id"]: row["ClientId"] for row in invoices}
    for row in positive_lines:
        client_id = invoice_client.get(row["FactureId"])
        if client_id:
            client_revenue[client_id] += row["MontantHT"]
    ranked = sorted(client_revenue.values(), reverse=True)
    top_count = max(1, math.ceil(len(ranked) * 0.20))
    total_revenue = sum(ranked, Decimal("0"))
    top_share = float(sum(ranked[:top_count], Decimal("0")) / total_revenue) if total_revenue else 0
    checks["client_concentration"] = {
        "passed": 0.42 <= top_share <= 0.92,
        "details": {"top_20_percent_share": round(top_share, 4), "expected": "0.42..0.92"},
    }

    invoice_by_id = {row["Id"]: row for row in tables["Activite.Factures"]}
    regular_hours_by_month: dict[int, list[Decimal]] = defaultdict(list)
    for row in positive_lines:
        if row["RubriqueId"] != 1:
            continue
        invoice = invoice_by_id[row["FactureId"]]
        regular_hours_by_month[invoice["DateEdition"].month].append(row["Base"])
    avg_aug = float(sum(regular_hours_by_month[8], Decimal("0")) / max(1, len(regular_hours_by_month[8])))
    sep_oct_values = regular_hours_by_month[9] + regular_hours_by_month[10]
    avg_sep_oct = float(sum(sep_oct_values, Decimal("0")) / max(1, len(sep_oct_values)))
    rebound_ratio = avg_sep_oct / avg_aug if avg_aug else 0
    checks["autumn_rebound"] = {
        "passed": rebound_ratio >= 1.08,
        "details": {"sep_oct_vs_aug_regular_hours": round(rebound_ratio, 4), "expected_min": 1.08},
    }

    contacts = tables["Activite.Interimaires"]
    missing_email_rate = sum(row["Email"] is None for row in contacts) / max(1, len(contacts))
    checks["documented_missing_contacts"] = {
        "passed": 0.01 <= missing_email_rate <= 0.05,
        "details": {"rate": round(missing_email_rate, 4), "expected": "0.01..0.05"},
    }

    row_counts = {table: len(rows) for table, rows in tables.items()}
    business_rows = sum(
        row_counts[name] for name in (
            "Activite.ContratsModelesPoste", "Activite.RelevesHeures",
            "Activite.LignesReleveHeures", "Activite.MouvementsReleveHeures",
            "Activite.Factures", "Activite.LignesFacture",
        )
    )
    passed = all(item["passed"] for item in checks.values())
    return {
        "passed": passed,
        "profile": profile.name,
        "seed": cfg.seed,
        "row_counts": row_counts,
        "business_rows": business_rows,
        "checks": checks,
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value).replace("|", "/").replace("\r", " ").replace("\n", " ")


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return f"'{value.isoformat()}'"
    escaped = str(value).replace("'", "''")
    return f"N'{escaped}'"


def _sql_name(table: str) -> str:
    schema, name = table.split(".", 1)
    return f"[{schema}].[{name}]"


def _write_csv_tables(tables: dict[str, list[dict[str, Any]]], target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for table in LOAD_ORDER:
        rows = tables[table]
        if not rows:
            continue
        columns = list(rows[0])
        path = target / f"{table.replace('.', '__')}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="|", lineterminator="\n")
            writer.writerow(columns)
            for row in rows:
                writer.writerow([_csv_value(row.get(column)) for column in columns])
        paths.append(str(path))
    return paths


def _write_insert_sql(
    tables: dict[str, list[dict[str, Any]]],
    post_updates: list[str],
    target: Path,
    batch_size: int,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("USE [Adventure];\nGO\nSET NOCOUNT ON;\nSET XACT_ABORT ON;\nBEGIN TRANSACTION;\n\n")
        for table in LOAD_ORDER:
            rows = tables[table]
            if not rows:
                continue
            columns = list(rows[0])
            quoted_columns = ", ".join(f"[{column}]" for column in columns)
            handle.write(f"-- {table}: {len(rows):,} lignes\n")
            for start in range(0, len(rows), batch_size):
                batch = rows[start:start + batch_size]
                handle.write(f"INSERT INTO {_sql_name(table)} ({quoted_columns}) VALUES\n")
                for index, row in enumerate(batch):
                    values = ", ".join(_sql_literal(row.get(column)) for column in columns)
                    suffix = ",\n" if index < len(batch) - 1 else ";\n"
                    handle.write(f"({values}){suffix}")
            handle.write("\n")
        handle.write("-- Fermeture des deux dépendances circulaires du DDL.\n")
        for statement in post_updates:
            handle.write(statement + "\n")
        handle.write("\nCOMMIT TRANSACTION;\nGO\n")


_SQLSERVER_MONEY_COLUMNS = (
        ("Activite", "Factures", "NetAFacturer"), ("Activite", "Factures", "MontantHt"),
        ("Activite", "HorairesEtCouts", "DureeHebdo"), ("Activite", "HorairesEtCouts", "SalaireReference"),
        ("Activite", "HorairesEtCouts", "BaseSalaireReference"), ("Activite", "HorairesEtCouts", "SalaireRemuneration"),
        ("Activite", "HorairesEtCouts", "BaseSalaireRemuneration"), ("Activite", "HorairesEtCouts", "SalaireAnnuel"),
        ("Activite", "LignesFacture", "Base"), ("Activite", "LignesFacture", "Taux"),
        ("Activite", "LignesFacture", "MontantTTC"), ("Activite", "LignesFacture", "MontantHT"),
        ("Activite", "LignesFacture", "TVA"), ("Activite", "LignesReleveHeures", "BasePaie"),
        ("Activite", "LignesReleveHeures", "BaseFact"), ("Activite", "LignesReleveHeures", "TauxPaie"),
        ("Activite", "LignesReleveHeures", "TauxFact"), ("Activite", "LignesReleveHeures", "MontantPaie"),
        ("Activite", "LignesReleveHeures", "MontantFact"),
        ("Activite", "MouvementsReleveHeures", "Lundi"), ("Activite", "MouvementsReleveHeures", "Mardi"),
        ("Activite", "MouvementsReleveHeures", "Mercredi"), ("Activite", "MouvementsReleveHeures", "Jeudi"),
        ("Activite", "MouvementsReleveHeures", "Vendredi"), ("Activite", "MouvementsReleveHeures", "Samedi"),
        ("Activite", "MouvementsReleveHeures", "Dimanche"), ("Activite", "Societes", "Capital"),
)
_SQLSERVER_RATE_COLUMNS = (
        ("Activite", "ContratsModelesPoste", "TauxInteressement"),
        ("Activite", "HorairesEtCouts", "Coefficient"),
        ("Activite", "LignesFacture", "TauxTVA"), ("Activite", "LignesFacture", "Coefficient"),
        ("Activite", "LignesReleveHeures", "Coefficient"),
)


def _sqlserver_column_type(table: str, column: str, ddl_type: str) -> str:
    schema, table_name = table.split(".", 1)
    key = (schema, table_name, column)
    if key in _SQLSERVER_MONEY_COLUMNS:
        return "decimal(18,2)"
    if key in _SQLSERVER_RATE_COLUMNS:
        return "decimal(18,4)"
    return ddl_type


def _schema_corrections_sql() -> str:
    lines = [
        "USE [Adventure];", "GO", "-- Le DDL source utilise DECIMAL sans échelle, donc DECIMAL(18,0).",
        "-- Ces corrections préservent les centimes et les coefficients avant chargement.",
    ]
    for schema, table, column in _SQLSERVER_MONEY_COLUMNS:
        lines.append(f"ALTER TABLE [{schema}].[{table}] ALTER COLUMN [{column}] decimal(18,2) NULL;")
    for schema, table, column in _SQLSERVER_RATE_COLUMNS:
        lines.append(f"ALTER TABLE [{schema}].[{table}] ALTER COLUMN [{column}] decimal(18,4) NULL;")
    lines.extend(["GO", ""])
    return "\n".join(lines)


def _validation_sql() -> str:
    return """USE [Adventure];
GO

-- Volumes des tables analytiques principales
SELECT 'ContratsModelesPoste' AS TableName, COUNT_BIG(*) AS NbLignes FROM [Activite].[ContratsModelesPoste]
UNION ALL SELECT 'RelevesHeures', COUNT_BIG(*) FROM [Activite].[RelevesHeures]
UNION ALL SELECT 'LignesReleveHeures', COUNT_BIG(*) FROM [Activite].[LignesReleveHeures]
UNION ALL SELECT 'Factures', COUNT_BIG(*) FROM [Activite].[Factures]
UNION ALL SELECT 'LignesFacture', COUNT_BIG(*) FROM [Activite].[LignesFacture];

-- Aucune ligne de facture orpheline
SELECT COUNT_BIG(*) AS LignesFactureOrphelines
FROM [Activite].[LignesFacture] lf
LEFT JOIN [Activite].[Factures] f ON f.Id = lf.FactureId
WHERE f.Id IS NULL;

-- Réconciliation facture / lignes (doit retourner 0 ligne)
SELECT f.Id, f.NumeroComplet, f.NetAFacturer, SUM(lf.MontantHT) AS SommeLignes
FROM [Activite].[Factures] f
JOIN [Activite].[LignesFacture] lf ON lf.FactureId = f.Id
GROUP BY f.Id, f.NumeroComplet, f.NetAFacturer
HAVING ABS(f.NetAFacturer - SUM(lf.MontantHT)) > 0.02;

-- Factures impayées et délais de règlement
SELECT
    CAST(100.0 * AVG(CASE WHEN IsReglee = 0 AND IsAvoir = 0 THEN 1.0 ELSE 0.0 END) AS decimal(6,2)) AS TauxImpayesPct,
    AVG(CASE WHEN DateReglement IS NOT NULL THEN DATEDIFF(day, DateEdition, DateReglement) * 1.0 END) AS DelaiMoyenJours
FROM [Activite].[Factures];
GO
"""


def _parse_ddl_dictionary(tables: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    ddl = SOURCE_DDL.read_text(encoding="utf-8")
    output: list[dict[str, Any]] = []
    for match in re.finditer(r"CREATE TABLE\s+\[([^]]+)\]\.\[([^]]+)\]\s*\((.*?)\n\);", ddl, re.I | re.S):
        schema, table_name, body = match.groups()
        full_name = f"{schema}.{table_name}"
        populated = set(tables.get(full_name, [{}])[0]) if tables.get(full_name) else set()
        for column_match in re.finditer(r"^\s*\[([^]]+)\]\s+([^,\r\n]+)", body, re.M):
            column, sql_type = column_match.groups()
            if column.upper().startswith("CONSTRAINT"):
                continue
            output.append({
                "Schema": schema,
                "Table": table_name,
                "Colonne": column,
                "Type_SQL_source": sql_type.strip(),
                "Alimentee_V1": "Oui" if column in populated else "Non",
                "Description": "Champ du schéma opérationnel transmis par Kevser.",
            })
    return output


def _write_audit_markdown(audit: dict[str, Any], target: Path) -> None:
    lines = [
        "# Rapport d'audit du dataset synthétique", "",
        f"- Profil : `{audit['profile']}`",
        f"- Seed : `{audit['seed']}`",
        f"- Lignes métier principales : **{audit['business_rows']:,}**",
        f"- Statut global : **{'RÉUSSI' if audit['passed'] else 'ÉCHEC'}**", "",
        "## Contrôles", "",
        "| Contrôle | Statut | Détails |", "|---|---:|---|",
    ]
    for name, result in audit["checks"].items():
        details = json.dumps(result["details"], ensure_ascii=False, default=str)
        lines.append(f"| `{name}` | {'✅' if result['passed'] else '❌'} | `{details}` |")
    lines.extend(["", "## Volumes", "", "| Table | Lignes |", "|---|---:|"])
    for table, count in audit["row_counts"].items():
        lines.append(f"| `{table}` | {count:,} |")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_dataset(
    dataset: dict[str, Any],
    audit: dict[str, Any],
    cfg: DatasetConfig,
    profile: VolumeProfile,
    formats: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    root = Path(output_dir).resolve() if output_dir else GENERATED_DIR / profile.name
    csv_dir = root / "csv"
    sql_dir = root / "sql"
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Any] = {"root": str(root)}
    if formats in {"csv", "both"}:
        outputs["csv"] = _write_csv_tables(dataset["tables"], csv_dir)
    if formats in {"sql", "both"}:
        schema_target = sql_dir / "00_schema_source.sql"
        shutil.copyfile(SOURCE_DDL, schema_target)
        corrections_target = sql_dir / "01_schema_corrections.sql"
        corrections_target.write_text(_schema_corrections_sql(), encoding="utf-8")
        data_target = sql_dir / "02_insert_data.sql"
        _write_insert_sql(
            dataset["tables"], dataset["metadata"]["post_load_updates"],
            data_target, cfg.batch_size,
        )
        validation_target = sql_dir / "03_validation_queries.sql"
        validation_target.write_text(_validation_sql(), encoding="utf-8")
        outputs["sql"] = [str(schema_target), str(corrections_target), str(data_target), str(validation_target)]

    dictionary = _parse_ddl_dictionary(dataset["tables"])
    dictionary_path = docs_dir / "data_dictionary.csv"
    with dictionary_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dictionary[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(dictionary)

    audit_json = docs_dir / "audit_report.json"
    audit_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    audit_md = docs_dir / "audit_report.md"
    _write_audit_markdown(audit, audit_md)
    truth_path = docs_dir / "instructor_truth.json"
    truth_path.write_text(json.dumps(dataset["metadata"]["patterns"], ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_path = docs_dir / "metadata.json"
    metadata_path.write_text(json.dumps(dataset["metadata"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    model_path = docs_dir / "model_view.md"
    model_path.write_text("""# Vue analytique recommandée

```mermaid
flowchart LR
    A[Agences] --> C[Contrats]
    CL[Clients] --> C
    I[Intérimaires] --> C
    Q[Qualifications] --> C
    C --> RH[Relevés d'heures]
    RH --> LRH[Lignes de relevé]
    LRH --> LF[Lignes de facture]
    F[Factures] --> LF
    R[Rubriques] --> LRH
    R --> LF
```

Grains principaux : un contrat, un relevé par semaine de mission, une ligne par
rubrique d'heures et une facture par client/établissement/agence/mois.
""", encoding="utf-8")

    outputs["docs"] = [str(dictionary_path), str(audit_json), str(audit_md), str(truth_path), str(metadata_path), str(model_path)]
    report = root / "generation_report.json"
    report.write_text(json.dumps({"audit": audit, "outputs": outputs}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    outputs["generation_report"] = str(report)
    return outputs
