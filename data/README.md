# Référentiel Sirene embarqué

`sirene_companies.csv` contient un extrait figé de 10 000 personnes morales françaises réellement enregistrées. Il alimente les identités publiques des entreprises dans le dataset généré, sans introduire de données personnelles.

## Source et périmètre

Source : API Recherche d’Entreprises de la Direction interministérielle du numérique, alimentée notamment par la base Sirene de l’Insee et le Registre national des entreprises.

- API source : <https://recherche-entreprises.api.gouv.fr>
- base Sirene : <https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret>
- licence des données Sirene : Licence Ouverte / Open Licence 2.0
- date d’extraction, nombre de lignes et empreinte canonique du CSV : voir [`sirene_metadata.json`](sirene_metadata.json), vérifié automatiquement à chaque génération ; les fins de ligne sont normalisées en LF pour obtenir le même SHA-256 sous Windows et Linux
- périmètre : unités légales actives et diffusibles au moment de l’extraction, personnes morales privées (catégories juridiques `5xxx` et `6xxx`), catégories PME et ETI, échantillonnées autour de 25 métropoles françaises
- données exclues : dirigeants, élus, entrepreneurs individuels, coordonnées personnelles et adresses détaillées

## Provenance des champs

| Champ généré | Provenance | Portée exacte |
|---|---|---|
| `SIREN` | snapshot officiel | identifiant de l’unité légale |
| `RaisonSociale` | snapshot officiel | dénomination exacte de l’unité légale dans les tables entreprise et sur la ligne de siège officielle ; seuls les sites synthétiques reçoivent un suffixe pédagogique |
| `CodeAPE` | snapshot officiel | activité principale de l’unité légale |
| `FormeJuridiqueCode` | snapshot officiel | catégorie juridique de l’unité légale |
| `SIRET` / `PseudoSIRET` du siège | snapshot officiel | SIRET de l’établissement siège uniquement |
| `CodeTvaCee` | calcul local depuis le SIREN | format français dérivé ; ne prouve ni l’assujettissement, ni l’activation actuelle du numéro auprès de l’administration fiscale |

Les adresses, communes d’affectation, téléphones, agences, personnes et opérations métier sont synthétiques. Sur un établissement synthétique, le code APE recopié depuis sa société parente reste celui de l’unité légale : le projet ne prétend pas connaître l’activité principale propre de ce site.

## Sélection déterministe et diversité

L’ordre renvoyé par l’API peut regrouper des résultats issus d’une même page ou d’une même zone. Pour préserver les jeux déjà utilisés, les clients conservent exactement l’ordre historique du CSV. Les sociétés sont sélectionnées dans le reste du snapshot, après la réserve complète des clients, puis dispersées avec une empreinte SHA-256 stable construite à partir du SIREN.

Les deux populations restent ainsi disjointes, aucune identité n’est recyclée entre partitions et les sociétés ne se concentrent pas sur une seule page géographique. Avec le profil `client` par défaut :

- `Activite.Clients` contient 3 600 identités officielles distinctes ;
- `Activite.Societes` contient 96 identités officielles distinctes, soit 8 par partition ;
- une demande dépassant les 10 000 identités disponibles échoue explicitement au lieu d’inventer ou de réutiliser un SIREN.

## Règle SIRET / NIC

Chaque entreprise reçoit exactement un établissement siège portant le SIRET officiel du snapshot, son NIC et la raison sociale officielle exacte. Les établissements supplémentaires sont des sites pédagogiques synthétiques : leur libellé peut être suffixé et leurs champs SIRET et NIC restent volontairement vides.

Cette règle s’applique aux deux branches du modèle :

- `Activite.EtablissementsClient.SIRET` et `CodeNIC` pour les clients ;
- `Activite.Etablissements.PseudoSIRET` et `NIC` pour les sociétés.

Un champ vide signifie donc « site synthétique sans identifiant officiel connu », et non un identifiant manquant à reconstituer.

## Audit de génération

`generation-report.json` contrôle après concaténation de toutes les partitions :

- la correspondance exacte des SIREN, raisons sociales, codes APE et formes juridiques avec ce snapshot ;
- l’unicité globale et la séparation des identités de clients et de sociétés ;
- la diversité des zones sources, préfixes SIREN, activités et formes juridiques ;
- la dérivation des numéros de TVA ;
- l’unicité et la cohérence des SIRET de siège avec leur SIREN parent ;
- l’absence de SIRET/NIC sur tous les sites synthétiques ;
- la continuité des relations jusqu’aux agences, dossiers, contrats et factures.

La génération échoue si une règle d’identité ou de relation déclarée obligatoire échoue. Sur un profil `client` d’au moins 12 partitions, les seuils de diversité des sociétés deviennent eux aussi bloquants : 96 sociétés, 20 zones, 40 codes APE, 20 divisions APE, 6 formes juridiques, 70 % de préfixes SIREN distincts et 15 % au plus pour la zone la plus représentée.

## Rafraîchir le snapshot

Depuis la racine du dépôt :

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe .\scripts\refresh-sirene-reference.py --count 10000
.\scripts\test.ps1
```

Le rafraîchissement appelle la source distante et peut donc faire évoluer les identités sélectionnées. Il écrit ensemble `sirene_companies.csv` et `sirene_metadata.json` ; le générateur refuse ensuite un CSV dont le nombre de lignes ou l’empreinte canonique ne correspond pas aux métadonnées. Cette empreinte normalise uniquement les fins de ligne en LF afin de rester identique après un checkout Git Windows ou Linux. Après toute mise à jour, contrôlez leur diff, les tests et un rapport de génération complet avant publication.

Le générateur utilise ensuite exclusivement le fichier local : la génération courante reste reproductible et fonctionne hors ligne.
