# Kevser Date Gen

Générateur reproductible de données synthétiques pour le modèle de facturation ADV de Kevser. Le projet produit les **30 tables du modèle source**, un audit automatique et un kit d’import SQL Server utilisable dans SSMS.

Le profil `client`, utilisé par défaut, vise environ **3,2 millions de lignes métier** : plus de dix fois le premier jeu de démonstration (270 438 lignes métier). Il génère 48 000 contrats, 3 600 clients et **96 sociétés** réparties sur 12 partitions. La génération est partitionnée pour ne pas charger tout le dataset en mémoire ; ses volumes et sa durée exacts sont consignés dans `generation-report.json`.

> Le projet embarque un snapshot de **10 000 personnes morales réelles** issues du répertoire Sirene : SIREN, raison sociale, code APE, catégorie juridique et SIRET du siège. Les entrepreneurs individuels et les identités non diffusibles sont exclus. Les personnes, coordonnées, adresses opérationnelles, risques et transactions restent entièrement synthétiques : il ne faut rien en déduire sur les entreprises citées.

## Démarrage en 5 minutes

Prérequis : Windows PowerShell et Python 3.11 ou plus récent.

```powershell
git clone https://github.com/votredatacoach/Kevser-Date-Gen.git
cd Kevser-Date-Gen
.\scripts\bootstrap.ps1
.\scripts\generate.ps1
```

Le résultat se trouve dans `generated/client/` :

- `csv/` : les 30 tables, séparateur `|`, UTF-8 ;
- `sql/` : création, chargement en masse, index et contrôles SQL Server ;
- `generation-report.json` : volumes, durée et résultat des audits ;
- `manifest.sha256` : empreinte de chaque fichier.

## Faire varier la taille

Pour alourdir volontairement le **modèle existant dans SSMS**, sans ajouter de transactions métier, utiliser le [kit de charge Power BI > 1 Go](docs/modele-plus-de-1go.md). Il ajoute une colonne de texte aléatoire sur les factures, par lots, avec cible réglable et script de retrait. Les scripts `06`/`07` sont facultatifs et ne sont jamais exécutés par l'import standard.

```powershell
# Environ la moitié du profil client
.\scripts\generate.ps1 -Scale 0.5 -Output generated\client-50pct

# Deux fois le profil client
.\scripts\generate.ps1 -Scale 2 -Output generated\client-200pct

# Volume exact en partitions (1 partition ≈ 4 000 contrats)
.\scripts\generate.ps1 -Shards 20 -Output generated\client-20-partitions

# Petit jeu rapide pour tester le pipeline
.\scripts\generate.ps1 -Profile smoke -Output generated\smoke
```

`--scale` ajuste le nombre de partitions. `--shards` permet de le fixer exactement. La graine (`-Seed`) garantit une génération reproductible.

| Profil | Partitions par défaut | Sociétés par partition | Contrats visés | Usage |
|---|---:|---:|---:|---|
| `smoke` | 1 petite | 2 | 50 | tests en quelques secondes |
| `demo` | 1 | 8 | 4 000 | démonstration locale |
| `client` | 12 | 8, soit 96 au total | 48 000 | livraison par défaut, ≥ 10× |

Les volumes transactionnels exacts dépendent des durées de contrat, des absences et des heures supplémentaires. Ils sont consignés après chaque exécution.

## Données générées

Le parcours métier principal est cohérent de bout en bout :

```text
clients → établissements → contrats → relevés d’heures → factures → règlements/avoirs
```

Le générateur conserve des motifs réalistes :

- saisonnalité avec creux estival et reprise en septembre-octobre ;
- concentration du chiffre d’affaires sur les clients stratégiques ;
- une raison sociale et un SIREN officiels, uniques par client, y compris après concaténation des partitions ;
- 96 sociétés distinctes dans le profil `client`, sélectionnées de façon déterministe et dispersée dans le snapshot officiel ;
- le code APE et la forme juridique officiels de chaque unité légale ;
- un numéro de TVA au format français calculé depuis le SIREN, sans affirmer que l’entreprise possède un statut fiscal actif ;
- le SIRET et la raison sociale officiels exacts du siège pour le premier établissement de chaque entreprise ;
- aucun faux SIRET ni NIC pour les sites supplémentaires synthétiques : les champs restent vides ;
- corrélation entre heures, qualification, taux et montant facturé ;
- absences, heures supplémentaires, factures non réglées et avoirs ;
- quelques contacts manquants et libellés imparfaits, sans casser les clés.

Le DDL transmis par Kevser est conservé sans modification dans [`schema/original/modele_ADV_script.sql`](schema/original/modele_ADV_script.sql). Le kit généré applique séparément les corrections de précision décimale nécessaires.

Le snapshot officiel, sa provenance, sa licence et ses critères de filtrage sont documentés dans [`data/README.md`](data/README.md). Il peut être régénéré avec `scripts/refresh-sirene-reference.py`. Si une volumétrie demande plus d’identités uniques que le référentiel n’en contient, la génération échoue explicitement au lieu de recycler ou d’inventer des entreprises.

## Régénérer et réimporter les données chez Kevser

Les commandes suivantes partent d’un clone existant et produisent un dossier distinct pour la version 1.3.0 :

```powershell
cd C:\chemin\vers\Kevser-Date-Gen
git switch main
git pull --ff-only origin main
.\scripts\bootstrap.ps1
.\scripts\test.ps1
.\scripts\generate.ps1 `
  -Profile client `
  -Seed 20260717 `
  -Output .\generated\client-1.3.0
```

Si `generated\client-1.3.0` existe déjà et doit réellement être remplacé, relancez uniquement la dernière commande avec `-Force`. Cette option supprime le dossier de sortie ciblé, pas la base SQL Server.

Avant l’import, contrôlez le rapport généré :

```powershell
$report = Get-Content .\generated\client-1.3.0\generation-report.json -Raw |
  ConvertFrom-Json

$report.version
$report.partitions
$report.company_identity_audit.passed
$report.company_identity_audit.tables.'Activite.Societes' |
  Select-Object rows, distinct_sirens, distinct_company_names,
    distinct_ape_codes, distinct_legal_forms, distinct_source_query_areas,
    all_identities_match_official_snapshot, all_vat_codes_match_siren_derivation
```

Les trois premières valeurs attendues sont `1.3.0`, `12` et `True`. Le tableau des sociétés doit indiquer `96` lignes, `96` SIREN distincts et `96` raisons sociales distinctes.

Pour tester le jeu sans toucher à la base actuellement utilisée, importez-le d’abord dans une nouvelle base :

```powershell
.\scripts\import-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure_130" `
  -DataRoot "$PWD\generated\client-1.3.0"

.\scripts\validate-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure_130" `
  -DataRoot "$PWD\generated\client-1.3.0"
```

Adaptez le nom de l’instance dans `-Server` si nécessaire. Une fois la validation terminée, faites pointer l’environnement applicatif vers `Adventure_130`, ou sauvegardez la base courante puis utilisez l’option `-Recreate` décrite ci-dessous pour la remplacer.

Pour conserver le nom de base `Adventure`, la réimportation complète s’effectue ainsi après sauvegarde :

```powershell
.\scripts\import-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure" `
  -DataRoot "$PWD\generated\client-1.3.0" `
  -Recreate

.\scripts\validate-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure" `
  -DataRoot "$PWD\generated\client-1.3.0"
```

Ne remplacez pas uniquement `Activite.Societes` : les entreprises, établissements, agences, dossiers et factures sont générés et audités comme un ensemble relié.

Dans SSMS, ces requêtes confirment que le nouveau jeu est bien chargé :

```sql
SELECT
    'Clients' AS Population,
    COUNT(*) AS NombreEntreprises,
    COUNT(DISTINCT SIREN) AS SirenDistincts,
    COUNT(DISTINCT RaisonSociale) AS RaisonsSocialesDistinctes
FROM Activite.Clients
UNION ALL
SELECT
    'Societes',
    COUNT(*) AS NombreSocietes,
    COUNT(DISTINCT SIREN) AS SirenDistincts,
    COUNT(DISTINCT RaisonSociale) AS RaisonsSocialesDistinctes
FROM Activite.Societes;

SELECT
    COUNT(*) AS NombreEtablissements,
    SUM(CASE WHEN NULLIF(LTRIM(RTRIM(PseudoSIRET)), '') IS NOT NULL THEN 1 ELSE 0 END)
        AS SiegesAvecSiretOfficiel,
    SUM(CASE WHEN NULLIF(LTRIM(RTRIM(PseudoSIRET)), '') IS NULL THEN 1 ELSE 0 END)
        AS SitesSynthetiquesSansSiret
FROM Activite.Etablissements;

SELECT
    COUNT(*) AS NombreEtablissementsClients,
    SUM(CASE WHEN NULLIF(LTRIM(RTRIM(SIRET)), '') IS NOT NULL THEN 1 ELSE 0 END)
        AS SiegesAvecSiretOfficiel,
    SUM(CASE WHEN NULLIF(LTRIM(RTRIM(SIRET)), '') IS NULL THEN 1 ELSE 0 END)
        AS SitesSynthetiquesSansSiret
FROM Activite.EtablissementsClient;
```

Avec le profil `client` par défaut, les résultats attendus sont `3 600 / 3 600 / 3 600` pour les clients, `96 / 96 / 96` pour les sociétés, `192 / 96 / 96` pour les établissements des sociétés et `5 400 / 3 600 / 1 800` pour les établissements clients.

## Import dans SQL Server / SSMS

### Import automatisé

Installez les outils en ligne de commande SQL Server (`sqlcmd`), puis lancez :

```powershell
.\scripts\import-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure" `
  -DataRoot "$PWD\generated\client"

.\scripts\validate-sqlserver.ps1 -Server ".\SQLEXPRESS" -Database "Adventure"
```

Pour remplacer volontairement une base existante, sauvegardez-la d’abord, puis ajoutez `-Recreate`. Cette option force la déconnexion des sessions, supprime entièrement la base cible, puis la recrée avant l’import :

```powershell
.\scripts\import-sqlserver.ps1 `
  -Server ".\SQLEXPRESS" `
  -Database "Adventure" `
  -DataRoot "$PWD\generated\client" `
  -Recreate
```

Le compte Windows courant doit pouvoir créer la base et le service SQL Server doit pouvoir lire le dossier CSV. Pour une instance locale, un chemin local absolu est recommandé.

Le lanceur PowerShell est le parcours recommandé : avant de contacter SQL Server, il vérifie l’intégrité de chaque fichier avec `manifest.sha256`, puis chaque chargement exige le nombre exact de lignes annoncé par le bundle.

### Import manuel dans SSMS

1. Ouvrez `sql/99_run_all.sql` dans SSMS et activez **Mode SQLCMD** dans le menu **Requête**.
2. Adaptez `DatabaseName`, `RecreateDatabase` et `DataRoot` en haut du fichier. `RecreateDatabase "1"` supprime entièrement une base cible existante ; conservez `"0"` pour le mode non destructif.
3. Exécutez le script : il appelle dans l’ordre la création, le schéma, le chargement, les index et les validations.

Les six scripts numérotés peuvent également être lancés séparément en leur fournissant les variables SQLCMD. `99_run_all.sql` est le parcours manuel recommandé dans SSMS ; il vérifie les volumes exacts et les contrôles SQL, mais la vérification cryptographique préalable du manifeste reste propre au lanceur PowerShell.

Le chargement utilise `BULK INSERT`, des lots de 50 000 lignes et une réactivation contrôlée des contraintes. Il refuse une base qui contient déjà des contrats afin d’éviter un doublonnage accidentel.

## Autres formats

Les CSV sont le format principal : faciles à versionner, inspecter et charger dans SQL Server, PostgreSQL, DuckDB, Fabric ou Power BI.

Pour ajouter une base SQLite portable :

```powershell
.\scripts\generate.ps1 -Profile demo -SQLite -Output generated\demo-sqlite
```

SQLite sert à l’exploration locale. Pour respecter les types et relations du modèle ADV, SQL Server et le kit SSMS restent la référence.

## Utilisation directe en Python

```powershell
.\.venv\Scripts\python.exe -m kevser_date_gen `
  --profile client `
  --scale 1.25 `
  --seed 20260717 `
  --output generated\client-125pct
```

Options :

```text
--profile {client,demo,smoke}
--scale N
--shards N
--seed N
--output DOSSIER
--sqlite
--force
```

`--force` supprime uniquement le dossier de sortie explicitement ciblé avant de le régénérer.

## Contrôles qualité

Chaque partition doit réussir ses contrôles structurels et métier avant d’être écrite. Après concaténation, un audit global contrôle l’ensemble des partitions :

- conformité des colonnes avec le DDL ;
- unicité des clés primaires ;
- absence d’orphelins sur les clés étrangères alimentées ;
- rapprochement des montants de factures et relevés d’heures ;
- cohérence des dates ;
- plausibilité du taux d’impayés et des contacts manquants ;
- format, clé de contrôle, unicité globale et correspondance exacte au snapshot Sirene des SIREN, raisons sociales, codes APE et formes juridiques ;
- séparation des identités entre clients et sociétés, diversité des zones sources et des préfixes SIREN ;
- dérivation cohérente du numéro de TVA depuis le SIREN, sans validation du statut fiscal actif ;
- un seul SIRET de siège officiel par entreprise et aucun SIRET/NIC inventé sur les sites synthétiques ;
- unicité globale des codes de sociétés, établissements, agences, dossiers et axes, ainsi que des noms d’agences et de dossiers ;
- cohérence des relations société–établissement–agence–dossier et client–établissement–contrat–facture ;
- corrélation heures/chiffre d’affaires, concentration client et saisonnalité.

Pour tester le projet :

```powershell
.\scripts\test.ps1
```

Le détail chiffré avant/après, les doublons attendus et inattendus ainsi que les preuves d’import sont regroupés dans [`docs/audit-sirene-1.3.0.md`](docs/audit-sirene-1.3.0.md).

## Structure du repository

```text
src/kevser_date_gen/   moteur, orchestration et exports
schema/original/       DDL original fourni par Kevser
profiles/              profils documentés
scripts/               installation, génération et import SQL Server
data/                  snapshot Sirene et documentation de provenance
tests/                 tests rapides et reproductibles
docs/                  modèle, exploitation et dépannage
generated/             sorties locales ignorées par Git
```

## Dépannage

- **PowerShell bloque les scripts** : lancez temporairement `Set-ExecutionPolicy -Scope Process Bypass` dans la console courante.
- **`python` est introuvable** : installez Python 3.11+ et cochez l’ajout au `PATH`.
- **`sqlcmd` est introuvable** : installez les Microsoft SQL Server command-line utilities.
- **`BULK INSERT` refuse le fichier** : donnez au service SQL Server un droit de lecture sur `DataRoot`, et utilisez un chemin absolu accessible depuis la machine SQL Server.
- **Le dossier de sortie existe** : choisissez un autre `-Output` ou ajoutez `-Force` en connaissance de cause.
- **La base contient déjà des données** : utilisez une nouvelle base ; le projet ne supprime jamais une base existante automatiquement.

## Licence

Code publié sous licence MIT. Le snapshot Sirene est réutilisé sous Licence Ouverte 2.0. Le schéma métier source reste fourni comme matériel de travail du projet.
