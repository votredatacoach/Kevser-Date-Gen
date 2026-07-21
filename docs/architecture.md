# Architecture et garanties

## Pourquoi des partitions ?

Le premier prototype conservait toutes les tables dans des listes Python. À dix fois le volume, la mémoire aurait pu atteindre plusieurs gigaoctets. Kevser Date Gen construit une partition cohérente, l’audite, l’écrit en CSV puis libère sa mémoire avant la suivante.

Chaque partition utilise une graine dérivée de la graine principale. Les UUID sont donc disjoints. Les rares clés numériques propres aux transactions reçoivent un espace d’identifiants réservé à leur partition. Les petits référentiels communs ne sont écrits qu’une fois.

## Reproductibilité

À paramètres identiques (`profile`, `scale` ou `shards`, `seed`), les CSV sont identiques octet par octet. `manifest.sha256` permet de vérifier une livraison après copie.

Les fichiers de rapport contiennent une date de génération et une durée : ils ne font pas partie de la garantie d’identité octet par octet.

## Limites volontaires

- Les coordonnées utilisent des domaines `.invalid` et des identifiants explicitement synthétiques.
- SQLite offre une représentation portable, mais pas toutes les contraintes SQL Server.
- Le modèle reproduit des comportements plausibles pour la formation et les tests ; ce n’est pas un modèle statistique d’une entreprise réelle.
- Le chargement SQL Server vise une base vide et ne réalise aucune suppression automatique.
