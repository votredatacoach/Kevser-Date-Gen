# Test d'un modèle Power BI de plus de 1 Go

L'objectif est de charger volontairement le modèle SQL existant avec une colonne volumineuse, puis de mesurer son import dans Power BI. Il s'agit d'une charge de test, pas d'une optimisation des performances métier.

## Exécuter dans SSMS

1. Ouvrir `schema/stress/06_model_stress_optional.sql` (également livré dans `generated/<profil>/sql/` après génération).
2. Sélectionner la base ADV à tester dans la liste des bases SSMS.
3. Régler `@TargetRandomGiB` si nécessaire : `0.010` pour commencer par un essai court ; `1.500` pour la cible proposée.
4. Exécuter le script. Aucun mode SQLCMD n'est nécessaire. Il ajoute `Activite.Factures.ChargeTestModele`, sans modifier les montants, les clés ou le nombre de lignes. Il refuse une colonne préexistante qui ne porte pas son marqueur.
5. Lire le tableau de contrôle final : factures chargées, longueur minimale/maximale, octets SQL et quantité d'octets aléatoires.

À `1.500`, il faut **107 375 factures** disponibles : 15 000 octets aléatoires par ligne, encodés en 30 000 caractères hexadécimaux. Cela représente environ **3 Gio de texte SQL** et **1,5 Gio d'octets aléatoires**. Le profil client de référence possède 148 087 factures ; le script vérifie le nombre réel de lignes avant toute modification.

Les mises à jour sont faites par lots de 100 factures ; les lignes à traiter sont sélectionnées une seule fois. Une nouvelle exécution conserve les valeurs déjà générées et complète la cible, notamment après interruption. Une cible plus faible ne supprime pas la charge existante. Les valeurs aléatoires ne sont pas reproductibles par graine. Le journal SQL, la base et le rafraîchissement Power BI doivent disposer d'espace suffisant pour cette charge.

## Importer et mesurer dans Power BI

Dans la requête existante des factures, inclure `ChargeTestModele` et lui donner le type **Texte**. Actualiser la navigation/les étapes de sélection des colonnes si elles figent l'ancien schéma. Utiliser le mode **Import** et charger la colonne entière ; DirectQuery ne stocke pas cette charge dans le modèle. Si un filtre réduit le nombre de factures, le test de taille sera réduit dans les mêmes proportions.

La colonne peut être masquée dans le modèle ; elle reste stockée. Ne pas l'ajouter aux tableaux, segments ou calculs métier.

Après l'actualisation, mesurer la taille du modèle et de la colonne avec les métriques VertiPaq. Le volume SQL, le volume CSV et la taille du PBIX ne sont pas des mesures interchangeables. **Le dépassement de 1 Go n'est confirmé qu'après mesure dans Power BI**. La cible initiale de 1,5 Gio aléatoires laisse une marge pour la compression, sans garantir une taille finale exacte. Augmenter la cible et relancer si nécessaire, dans la limite du nombre de factures disponibles.

Un texte répétitif se compresse très bien et serait un mauvais test. Une image binaire ne constitue pas directement une colonne chargeable du modèle. Le texte aléatoire retenu reste sous le plafond pratique d'environ 32 000 caractères de Power BI et possède une forte cardinalité.

Pour publier ensuite un modèle Import supérieur à 1 Go, il faut également un espace de travail avec une licence/capacité adaptée. Ce kit SQL ne change aucune licence ni capacité Power BI.

## Retirer le test

Exécuter `schema/stress/07_remove_model_stress_optional.sql` dans la même base, puis retirer la colonne de la requête Power BI et actualiser. Le script ne retire que la colonne marquée par ce kit. La suppression libère logiquement la charge ; elle ne réduit pas automatiquement les fichiers physiques SQL Server.

## Sources et vérification

- [Types de données Power BI](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types) : plafond pratique du texte.
- [CRYPT_GEN_RANDOM](https://learn.microsoft.com/en-us/sql/t-sql/functions/crypt-gen-random-transact-sql) : génération aléatoire jusqu'à 8 000 octets par appel.
- [Modèles volumineux Power BI](https://learn.microsoft.com/en-us/fabric/enterprise/powerbi/service-premium-large-models) : limites et capacité de publication.

Le dernier appel Kevser identifié est celui du 1er octobre 2026, `[Mentorat Datacoach 10/12] Suivi hebdo`, Fireflies `01M3C3TFVTEJM1WHRB7QYFZY58`. Fireflies renvoie les métadonnées mais aucune transcription ni résumé : aucune décision de cet appel n'a été supposée. Le périmètre de ce kit vient de la clarification donnée par Benjamin dans cette conversation.
