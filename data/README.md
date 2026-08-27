# Référentiel Sirene embarqué

`sirene_companies.csv` contient un extrait figé d’entreprises françaises réellement enregistrées. Il sert uniquement à alimenter les identités publiques des personnes morales dans le dataset généré.

Source : API Recherche d’Entreprises de la Direction interministérielle du numérique, alimentée notamment par la base Sirene de l’Insee et le Registre national des entreprises.

- source officielle : <https://recherche-entreprises.api.gouv.fr>
- base Sirene : <https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret>
- licence des données Sirene : Licence Ouverte / Open Licence 2.0
- date d’extraction : 2026-08-27
- périmètre : unités légales actives et diffusibles, personnes morales privées (catégories juridiques `5xxx` et `6xxx`), catégories PME et ETI, échantillonnées autour de 25 métropoles françaises
- données conservées : SIREN, raison sociale, catégorie juridique, code APE, catégorie d’entreprise, SIRET du siège et date de mise à jour Insee
- données exclues : dirigeants, élus, entrepreneurs individuels, coordonnées personnelles et adresses détaillées

Pour rafraîchir l’extrait :

```powershell
python .\scripts\refresh-sirene-reference.py --count 10000
```

Le générateur utilise ce fichier local afin de rester déterministe et utilisable hors ligne. Les autres données métier du projet restent synthétiques.
