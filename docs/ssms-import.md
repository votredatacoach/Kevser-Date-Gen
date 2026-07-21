# Guide d’import SSMS

Les scripts se trouvent dans le dossier `sql/` de chaque génération. Pour un import manuel, ouvrez `99_run_all.sql`, adaptez ses deux variables puis exécutez-le en mode SQLCMD.

## Ordre d’exécution

1. `00_create_database.sql`
2. `01_schema.sql`
3. `02_schema_corrections.sql`
4. `03_bulk_load.sql`
5. `04_indexes.sql`
6. `05_validation.sql`

`99_run_all.sql` définit `DatabaseName` et `DataRoot`, puis appelle les six scripts dans cet ordre. `DataRoot` désigne le dossier qui contient `csv/`. Les scripts numérotés n’imposent aucune valeur par défaut, afin que les paramètres `sqlcmd -v` du script PowerShell ne soient jamais écrasés.

## Permissions de fichiers

`BULK INSERT` lit les CSV depuis le processus SQL Server, pas depuis SSMS. Pour une instance locale, accordez au compte du service SQL Server un droit de lecture sur le dossier. Pour une instance distante, copiez les fichiers sur le serveur ou utilisez un partage UNC autorisé.

## Stratégie de chargement

Les CSV sont d’abord chargés dans des tables temporaires en texte UTF-8, puis convertis vers les types du DDL avec `TRY_CONVERT`. Les contraintes sont suspendues pendant l’import, réactivées avec `WITH CHECK`, puis les index analytiques sont ajoutés.

Si une conversion renvoie `NULL` pour une colonne obligatoire, l’insertion échoue et `sqlcmd -b` retourne un code d’erreur.
