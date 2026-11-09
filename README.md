# Screener BRVM

Outil gratuit de sélection des 48 actions cotées à la BRVM, inspiré de Finviz : filtres descriptifs, fondamentaux et techniques, score composite (valeur, qualité, dividende, momentum), fiches graphiques par titre et carte du marché. La page se met à jour seule chaque soir de séance.

## Mise en ligne en 6 étapes (environ 15 minutes, sans programmation)

1. **Créer un compte GitHub** gratuit sur https://github.com/signup (si vous n'en avez pas).
2. **Créer le dépôt** : bouton « + » en haut à droite, puis « New repository ». Nom : `screener-brvm`. Cocher **Public**. Cliquer « Create repository ».
3. **Déposer les fichiers** : sur la page du dépôt, lien « uploading an existing file ». Glisser le contenu du dossier décompressé : `index.html`, `README.md`, les dossiers `archive` et `scripts`. Cliquer « Commit changes ».
4. **Ajouter la mise à jour automatique** (le dossier `.github` est souvent masqué par l'ordinateur, on le crée donc à la main) : « Add file », puis « Create new file ». Dans le nom, taper exactement `.github/workflows/maj-quotidienne.yml`, puis coller le contenu du fichier du même nom fourni dans le dossier. Cliquer « Commit changes ».
5. **Autoriser la publication** : « Settings », puis « Actions », puis « General ». Sous « Workflow permissions », choisir **Read and write permissions** et enregistrer.
6. **Mettre la page en ligne** : « Settings », puis « Pages ». Sous « Branch », choisir `main` et `/ (root)`, puis « Save ».

Après une à deux minutes, le screener est en ligne à l'adresse :
`https://VOTRE-NOM-GITHUB.github.io/screener-brvm/`

## Vérifier la mise à jour automatique

Onglet **Actions**, puis « Mise à jour quotidienne », puis **Run workflow**. Une coche verte indique que tout fonctionne. Ensuite, la mise à jour tourne seule du lundi au vendredi à 22h30 (heure de Londres en hiver, 23h30 en été). Les soirs sans nouvelle séance (jours fériés), rien n'est publié.

## Personnaliser

- **Nom affiché** : dans `index.html`, modifier le texte entre `<title>` et `</title>`, et celui entre `<h1>` et `</h1>`.
- **Composition des indices BRVM 30 et Prestige** : listes `B30` et `PRES` en haut du script de `index.html`, à actualiser à chaque révision trimestrielle de la BRVM.
- **Nouvelle introduction en bourse** : ajouter le ticker dans la liste `TICKERS` de `scripts/build_brvm.py` et une ligne dans `META` de `index.html`.

## Données et avertissement

Les données proviennent du dépôt ouvert BRVMetrics (https://github.com/harzat/brvm-data-public), qui agrège la BRVM, SikaFinance et RicheBourse. Ses conditions réservent l'usage gratuit à l'analyse personnelle, la formation et la vérification ; pour un usage commercial, se rapprocher des sources. Les cours sont ajustés des divisions d'actions, pas des dividendes. Les fondamentaux portent sur le dernier exercice publié.

Cet outil aide à présélectionner des titres. Il ne constitue pas un conseil en investissement : recoupez toujours les chiffres sur le Bulletin Officiel de la Cote avant de passer un ordre.
