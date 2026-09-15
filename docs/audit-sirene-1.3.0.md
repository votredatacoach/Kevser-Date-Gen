# Audit des identités Sirene — version 1.3.0

Date du contrôle : 15 septembre 2026

Profil : `client`

Graine : `20260717`

Partitions : `12`

## Résultat

Le bundle de release a produit **3 453 181 lignes**, dont **3 236 579 lignes métier**, en 210,84 secondes. Les 12 audits de partition, l’audit global des identités, le plan de génération et tous les seuils de diversité ont réussi. Le manifeste a contrôlé **39 fichiers sans aucun écart SHA-256**.

La version précédente (`origin/main` au commit `54b0d9c`) ne pouvait pas produire de bundle `client` complet : la génération s’arrêtait à la partition 3 sur une raison sociale suffixée qui dépassait la longueur du DDL. Les valeurs « avant » ci-dessous viennent donc du plan, du snapshot et des règles de code de ce commit. Les valeurs « après » viennent du `generation-report.json` du bundle de release `1.3.0`.

## Avant / après

| Table ou indicateur | Version 1.2.0 | Version 1.3.0 | Contrôle |
|---|---:|---:|---|
| `Activite.Clients` — lignes | 3 600 | 3 600 | ordre historique et identités préservés |
| Clients — SIREN / noms distincts | 3 600 / 3 600 | 3 600 / 3 600 | 3 600 correspondances exactes au snapshot |
| Clients — zones / codes APE / divisions / formes | 25 / 430 / 73 / 34 | 25 / 430 / 73 / 34 | stabilité confirmée |
| `Activite.Societes` — lignes | 24 | 96 | 8 par partition |
| Sociétés — SIREN / noms distincts | 24 / 24 | 96 / 96 | 96 correspondances exactes au snapshot |
| Sociétés — codes distincts | 2 | 96 | aucune réinitialisation entre partitions |
| Sociétés — zones sources | 3 | 23 | seuil requis : 20 |
| Sociétés — part de la zone dominante | 41,67 % | 10,42 % | plafond requis : 15 % |
| Sociétés — codes / divisions APE | 20 / 14 | 67 / 37 | seuils requis : 40 / 20 |
| Sociétés — formes juridiques | 5 | 10 | seuil requis : 6 |
| Sociétés — préfixes SIREN distincts | 18 sur 24 | 81 sur 96 | couverture : 84,38 % |
| `Activite.Etablissements` — lignes | 48 | 192 | 2 par société |
| Établissements société — sièges officiels / sites synthétiques | 24 / 24 | 96 / 96 | un siège officiel par société |
| `Activite.Etablissements` — codes distincts | 4 | 192 | tous uniques |
| Établissements client — sièges officiels / sites synthétiques | 3 600 / 1 800 | 3 600 / 1 800 | un siège officiel par client |
| Liens site client–dossier | 5 400 planifiés | 24 323 | tous les rattachements réellement utilisés sont présents |
| `Activite.Agences` — codes / noms distincts | 8 / 8 | 96 / 96 | tous uniques |
| `Activite.DossiersAgence` — codes / noms distincts | 8 / 8 | 96 / 96 | un dossier par agence, 96 sociétés couvertes |
| `Activite.AxesAnalytiques` — codes distincts | 450 | 5 400 | tous uniques |
| `Activite.ContratsModelesPoste` | non contrôlé | 48 000 chemins cohérents | client, site, département, dossier et agence concordent |
| `Activite.Factures` | non contrôlé | 148 087 chemins cohérents | client, site, département, dossier, agence et société concordent |

## Doublons et identifiants absents

- Doublons SIREN inattendus : **0** chez les clients et **0** chez les sociétés.
- Doublons de raison sociale inattendus : **0** dans les deux populations.
- Doublons de SIRET officiel inattendus : **0**.
- Valeurs SIRET/NIC vides attendues : **96** sites société et **1 800** sites client, tous synthétiques.
- Codes dupliqués inattendus : **0** pour les sociétés, établissements, agences, dossiers et axes.
- Les agences sont synthétiques et ne reçoivent aucun SIRET.

## Couverture officielle et limites

L’audit compare exactement le SIREN, la raison sociale, le code APE et la forme juridique au snapshot Sirene embarqué. Pour chaque ligne de siège, il compare aussi le SIRET officiel, le NIC et la raison sociale exacte à l’unité légale parente. Le snapshot est lié à `sirene_metadata.json` par son nombre de lignes et son empreinte SHA-256 canonique, calculée après normalisation des fins de ligne en LF pour rester identique sous Windows et Linux.

Les adresses, villes opérationnelles, téléphones, personnes, risques et transactions restent synthétiques. Il ne faut rien en déduire sur les entreprises réelles citées. Le code APE d’un site synthétique reprend celui de l’unité légale parente ; il ne représente pas un code d’établissement officiel. `CodeTvaCee` suit la formule française dérivée du SIREN et ne prouve pas que le numéro est actif auprès de l’administration fiscale.

## Stabilité du métier synthétique

Une comparaison indépendante du profil `demo`, à seed identique, entre `54b0d9c` et `1.3.0` a montré :

- **22 CSV sur 30 strictement identiques** par SHA-256 et les 30 en-têtes inchangés ;
- clients, intérimaires, contrats, relevés, lignes de relevé, mouvements, lignes de facture, montants, dates et numéros inchangés ;
- 1 488 liens site client–dossier ajoutés, exactement les couples utilisés par les contrats mais absents en `1.2.0` ;
- seules les dimensions d’identité, leurs libellés et les champs de relation nécessaires ont évolué ;
- une seconde génération `1.3.0` identique à la première, soit **0 différence d’empreinte**.

## Exemples contrôlés

| SIREN | Raison sociale | APE | Forme juridique | Zone source |
|---|---|---|---|---|
| `775726433` | FIDAL ET ASSOCIES | `7010Z` | `5699` | Besançon |
| `980384176` | JFA | `4711B` | `5710` | Mulhouse |
| `301918447` | ALFYMA INDUSTRIE | `3320B` | `5710` | Mulhouse |
| `522226356` | TUV SUD FRANCE | `7120B` | `5710` | Metz |
| `341392488` | HELIE | `4722Z` | `5710` | Rouen |
| `331441741` | DMF | `4321A` | `5710` | Rouen |

## Vérifications exécutées

- `python -m unittest discover -s tests -v` : **12 tests réussis** ;
- compilation de `src`, `tests` et `scripts` : réussie ;
- `git diff --check` : aucune erreur ;
- génération `client`, 12 partitions : réussie ;
- audit global relu sur les CSV complets : réussi ;
- validation des 39 empreintes du manifeste : aucun écart ;
- parsing des six scripts SQL Server avec `SET PARSEONLY ON` : réussi ;
- import réel via `scripts/import-sqlserver.ps1` dans la base isolée `Kevser_Audit_130_Release_20260915` sur l’instance locale `Benjamin` : **221,31 secondes** ;
- préflight de l’import : **39 fichiers intègres** avant toute mutation SQL ;
- validation réelle via `scripts/validate-sqlserver.ps1` : **31 contrôles sur 31 à zéro anomalie**, en 4,06 secondes ;
- catalogue SQL après import : **66 clés étrangères actives et fiables**, **11 index de support présents**.

Le contrôle SQL bloque notamment les volumes tronqués, orphelins, écarts de montants, formats et doublons d’identifiants, noms de siège, sites synthétiques, codes métier et chemins complets des axes, relevés, contrats et factures.
