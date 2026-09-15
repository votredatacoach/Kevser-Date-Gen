# Changelog

## 1.3.0 — 2026-09-15

- profil `client` porté à 96 sociétés officielles distinctes : 8 sociétés dans chacune des 12 partitions ;
- ordre historique des identités clients préservé et sociétés sélectionnées dans un pool distinct, dispersé par empreinte SHA-256 ;
- correspondance contrôlée des SIREN, raisons sociales, codes APE et formes juridiques avec le référentiel officiel embarqué ;
- numéros de TVA français dérivés des SIREN, sans les présenter comme une preuve de statut fiscal actif ;
- SIRET et raison sociale officiels exacts réservés au siège de chaque entreprise, avec SIRET/NIC laissés vides sur les sites synthétiques ;
- codes de sociétés, établissements, agences, dossiers et axes rendus uniques entre partitions, ainsi que les noms des agences et dossiers ;
- audit global étendu aux établissements, agences, dossiers, liaisons et chemins d’identité des contrats et factures ;
- rattachements site client–dossier complétés sans modifier les tirages historiques des personnes, contrats, heures et factures ;
- métadonnées du snapshot liées au CSV par une empreinte SHA-256 canonique, stable après checkout Windows ou Linux, et reprises automatiquement dans les rapports ;
- index de clés étrangères créés avant la revalidation des contraintes volumineuses lors de l’import SQL Server ;
- troncature contrôlée des raisons sociales enrichies pour respecter les longueurs du DDL sur le profil complet ;
- procédure documentée de régénération, contrôle et réimport SQL Server côté Kevser.

## 1.2.0 — 2026-08-27

- référentiel embarqué de 10 000 personnes morales actives et diffusibles issues de Sirene ;
- SIREN, raisons sociales, codes APE, catégories juridiques et SIRET de siège réels ;
- exclusion des entrepreneurs individuels et des identités non diffusibles ;
- audit automatique de correspondance avec le snapshot officiel ;
- personnes, coordonnées, adresses et opérations métier maintenues en données synthétiques.

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
