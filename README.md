# Kevser Date Gen

Générateur reproductible de données synthétiques pour le modèle de facturation ADV de Kevser. Le projet produit les **30 tables du modèle source**, un audit automatique et un kit d’import SQL Server utilisable dans SSMS.

Le profil `client`, utilisé par défaut, vise environ **3,2 millions de lignes métier** : plus de dix fois le premier jeu de démonstration (270 438 lignes métier). La génération est partitionnée pour ne pas charger tout le dataset en mémoire.

Benchmark vérifié avec la graine par défaut : **3 236 579 lignes métier**, **3 434 042 lignes au total**, 48 000 contrats et 820 Mio de CSV, générés en 137 secondes sur la machine de développement. La durée dépend de la machine et du disque.

> Aucune donnée personnelle réelle n’est utilisée. Les noms, coordonnées, entreprises, identifiants et opérations sont entièrement synthétiques.

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

| Profil | Partitions par défaut | Contrats visés | Usage |
|---|---:|---:|---|
| `smoke` | 1 petite | 50 | tests en quelques secondes |
| `demo` | 1 | 4 000 | démonstration locale |
| `client` | 12 | 48 000 | livraison par défaut, ≥ 10× |

Les volumes transactionnels exacts dépendent des durées de contrat, des absences et des heures supplémentaires. Ils sont consignés après chaque exécution.

## Données générées

Le parcours métier principal est cohérent de bout en bout :

```text
clients → établissements → contrats → relevés d’heures → factures → règlements/avoirs
```

Le générateur conserve des motifs réalistes :

- saisonnalité avec creux estival et reprise en septembre-octobre ;
- concentration du chiffre d’affaires sur les clients stratégiques ;
- corrélation entre heures, qualification, taux et montant facturé ;
- absences, heures supplémentaires, factures non réglées et avoirs ;
- quelques contacts manquants et libellés imparfaits, sans casser les clés.

Le DDL transmis par Kevser est conservé sans modification dans [`schema/original/modele_ADV_script.sql`](schema/original/modele_ADV_script.sql). Le kit généré applique séparément les corrections de précision décimale nécessaires.

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

Le compte Windows courant doit pouvoir créer la base et le service SQL Server doit pouvoir lire le dossier CSV. Pour une instance locale, un chemin local absolu est recommandé.

### Import manuel dans SSMS

1. Ouvrez SSMS et activez **Mode SQLCMD** dans le menu **Requête**.
2. Exécutez `sql/00_create_database.sql`.
3. Exécutez `sql/01_schema.sql`, puis `02_schema_corrections.sql`.
4. Dans `03_bulk_load.sql`, adaptez `DatabaseName` et `DataRoot` en haut du fichier.
5. Exécutez `03_bulk_load.sql`, `04_indexes.sql`, puis `05_validation.sql`.

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

Chaque partition doit réussir les contrôles suivants avant d’être écrite :

- conformité des colonnes avec le DDL ;
- unicité des clés primaires ;
- absence d’orphelins sur les clés étrangères alimentées ;
- rapprochement des montants de factures et relevés d’heures ;
- cohérence des dates ;
- plausibilité du taux d’impayés et des contacts manquants ;
- corrélation heures/chiffre d’affaires, concentration client et saisonnalité.

Pour tester le projet :

```powershell
.\scripts\test.ps1
```

## Structure du repository

```text
src/kevser_date_gen/   moteur, orchestration et exports
schema/original/       DDL original fourni par Kevser
profiles/              profils documentés
scripts/               installation, génération et import SQL Server
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

Code publié sous licence MIT. Le schéma métier source reste fourni comme matériel de travail du projet.
