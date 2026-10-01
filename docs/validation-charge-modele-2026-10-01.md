# Validation du kit de charge — 1er octobre 2026

Base de travail : dépôt `votredatacoach/Kevser-Date-Gen`, branche `main`, commit `3dcbd0399a37d74374bd764e51295ad42b41604e`.

Livrable : ajout facultatif d'une charge texte aux factures existantes dans SSMS, avec cible réglable, reprise après interruption et retrait limité à la colonne du kit.

Contrôles réalisés :

- 14 tests Python réussis, dont génération d'un bundle smoke complet et contrôle de l'inclusion des scripts dans le manifeste.
- Le schéma initial et les CSV métier ne contiennent pas la charge ; le lanceur d'import `99_run_all.sql` ne l'exécute pas.
- Compilation Python réussie ; `git diff --check` réussi.
- Syntaxe des deux scripts SQL et du lot dynamique validée avec `Microsoft.SqlServer.TransactSql.ScriptDom.TSql160Parser`, fourni par SSMS 22.
- L'audit de référence du profil client recense 148 087 factures : la cible proposée nécessite 107 375 lignes. La capacité réelle est vérifiée par le script avant toute écriture.

Limites de preuve : aucun script de charge exécuté sur une instance SQL Server pendant cette tâche, aucun rafraîchissement Power BI, aucune mesure VertiPaq. La syntaxe et l'intégration au générateur sont validées ; le dépassement réel de 1 Go reste à mesurer après exécution dans SSMS et import Power BI. Les validations d'intégrité/cardinalité SQL sont intégrées au script pour cette exécution.
