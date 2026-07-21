# Guide d’import SSMS

Les scripts se trouvent dans le dossier `sql/` de chaque génération.

## Ordre d’exécution

1. `00_create_database.sql`
2. `01_schema.sql`
3. `02_schema_corrections.sql`
4. `03_bulk_load.sql`
5. `04_indexes.sql`
6. `05_validation.sql`

Activez le mode SQLCMD dans SSMS. Modifiez les variables `DatabaseName` et `DataRoot` au début des scripts. `DataRoot` désigne le dossier qui contient `csv/`.

## Permissions de fichiers

`BULK INSERT` lit les CSV depuis le processus SQL Server, pas depuis SSMS. Pour une instance locale, accordez au compte du service SQL Server un droit de lecture sur le dossier. Pour une instance distante, copiez les fichiers sur le serveur ou utilisez un partage UNC autorisé.

## Stratégie de chargement

Les CSV sont d’abord chargés dans des tables temporaires en texte UTF-8, puis convertis vers les types du DDL avec `TRY_CONVERT`. Les contraintes sont suspendues pendant l’import, réactivées avec `WITH CHECK`, puis les index analytiques sont ajoutés.

Si une conversion renvoie `NULL` pour une colonne obligatoire, l’insertion échoue et `sqlcmd -b` retourne un code d’erreur.
