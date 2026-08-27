# Changelog

## 1.1.0 — 2026-08-27

- SIREN numériques à neuf chiffres avec clé Luhn valide ;
- raisons sociales synthétiques plausibles et uniques entre partitions ;
- SIRET des établissements cohérents avec le SIREN de leur entreprise ;
- audit global des identités d’entreprise dans le rapport de génération.

## 1.0.0 — 2026-07-20

- générateur des 30 tables du modèle ADV ;
- profil `client` par défaut supérieur à dix fois le prototype ;
- génération partitionnée et reproductible ;
- exports CSV et SQLite optionnel ;
- kit SQL Server/SSMS avec `BULK INSERT` ;
- audits métier, manifeste SHA-256, tests et CI.
