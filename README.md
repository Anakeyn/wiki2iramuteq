# wiki2iramuteq

Constitue des corpus au format [IRaMuTeQ](https://pratinaud.gitpages.huma-num.fr/iramuteq-website/) à partir de Wikipédia, dans n'importe quelle langue. L'outil a été testé pour le français et le breton.

Un corpus peut partir :
- d'une **catégorie** Wikipédia et de ses sous-catégories ;
- de **termes de recherche** ;
- des **articles d'un autre corpus**, dans une autre langue, pour comparer deux Wikipédia.

Le dépôt contient aussi des **corpus prêts à l'emploi** sur les humanités numériques et sur le numérique, dans les Wikipédia française et bretonne.

## Sommaire

1. [Corpus prêts à l'emploi](#1-corpus-prêts-à-lemploi--aucune-commande-nécessaire)
2. [Créer ses propres corpus](#2-créer-ses-propres-corpus)
3. [Refiltrer un corpus](#3-refiltrer-un-corpus--filtrer_corpuspy)
4. [Reproduire les corpus du dépôt](#4-reproduire-les-corpus-du-dépôt)
5. [Options](#5-options)
6. [Licences et citation](#6-licences-et-citation)

## 1. Corpus prêts à l'emploi : aucune commande nécessaire

Ces corpus ont été extraits le 20 octobre 2026. Ils sont prêts à ouvrir dans IRaMuTeQ :

| Corpus | Fichier à ouvrir dans IRaMuTeQ | Articles |
|---|---|---|
| Humanités numériques (fr) | `corpus/hn_fr/wikipedia_fr_humanites_numeriques.txt` | 45 |
| Le numérique (fr) | `corpus/num_fr/wikipedia_fr_numerique_filtre.txt` | 1 232 |
| Le numérique (br) | `corpus/num_br/wikipedia_br_numerique_filtre.txt` | 156 |
| Paires fr/br, version française | `corpus/num_fr_aligne/wikipedia_fr_aligne_sur_br_numerique_filtre.txt` | 135 |
| Paires fr/br, version bretonne | `corpus/num_fr_aligne/wikipedia_br_numerique_filtre_aligne_sur_fr.txt` | 135 |

**Pour récupérer un corpus :** sur GitHub, cliquez sur le fichier, puis sur le bouton de téléchargement (*Download raw file*). Vous pouvez aussi récupérer tout le dépôt avec le bouton vert **Code → Download ZIP**.

**Pour l'ouvrir dans IRaMuTeQ :** *Fichier → Ouvrir un corpus*, encodage **utf-8**, langue **français**. IRaMuTeQ s'installe sur Windows, macOS et Linux ; voir la [page d'installation](https://pratinaud.gitpages.huma-num.fr/iramuteq-website/).

**Corpus bretons :** IRaMuTeQ ne propose pas encore de dictionnaire breton. En attendant, ouvrez-les avec la langue « français » et décochez la lemmatisation dans les paramètres de chaque analyse : les analyses portent alors sur les formes du texte.

Le fichier [`corpus/LISEZMOI.md`](corpus/LISEZMOI.md) décrit pour chaque corpus la méthode de constitution, les variables étoilées, les seuils et les choix manuels. Les fichiers `*_criteres.txt` en gardent la trace.

## 2. Créer ses propres corpus

### Prérequis

Il faut Python 3.8 ou plus récent, sans aucune bibliothèque à installer.

- **Linux, macOS** : Python est déjà présent ; les commandes s'utilisent telles quelles.
- **Windows** : installez Python depuis [python.org](https://www.python.org/downloads/) en cochant *Add Python to PATH*. Dans les commandes, remplacez `python3` par `python`, et écrivez chaque commande **sur une seule ligne**, car le `\` de fin de ligne ne fonctionne pas dans la console Windows.

Téléchargez le dépôt (**Code → Download ZIP**), décompressez-le, puis ouvrez un terminal dans ce dossier.

### Ce que fait `wiki2iramuteq.py`

1. Il sélectionne les articles selon le mode choisi : catégorie, recherche, articles parallèles ou alignement.
2. Il récupère le texte brut de chaque article via l'API officielle de Wikipédia, sans infobox, tableaux ni références.
3. Il supprime les sections annexes (Notes et références, Voir aussi, Liens externes, Bibliographie…), en français et en breton.
4. Il écrit un fichier `.txt` UTF-8 au format IRaMuTeQ, un texte par article, avec ses variables étoilées :
   ```
   **** *art_Logiciel_libre *id_Logiciel_libre *cat_recherche *prof_0 *terme_logiciel_libre *equiv_br_oui *lang_fr
   Texte de l'article…
   ```
5. Il écrit un fichier CSV de métadonnées : titre, URL, révision, nombre de mots, occurrences des termes, article retenu ou non.

**Merci d'indiquer `--contact`** (votre courriel ou site web) : Wikimédia demande que les outils s'identifient. Le script espace ses requêtes et ralentit de lui-même si le serveur le demande (erreur HTTP 429). Comptez quelques minutes pour quelques centaines d'articles.

### Mode « catégorie »

Les articles d'une catégorie et de ses sous-catégories :

```bash
python3 wiki2iramuteq.py --lang fr --categorie "Humanités numériques" --profondeur 2 \
    --contact "votre@courriel" --sortie ./corpus/hn_fr
```

Avec `--depuis`, la catégorie est donnée dans une langue et cherchée dans une autre grâce aux liens interlangues. Par exemple, `--lang en --depuis fr --categorie "Humanités numériques"` cherche son équivalent anglais. Le script s'arrête avec un message si la catégorie n'existe pas dans la langue visée.

### Mode « recherche »

Les articles qui contiennent des termes, par recherche plein texte. Le script ne garde que les articles où les termes apparaissent au moins `--min-occurrences` fois. Il ajoute la variable `*terme_`, qui indique le terme dominant de chaque article.

```bash
python3 wiki2iramuteq.py --lang br --recherche "stlenneg,urzhiataer,kenrouedad,genrouedad" \
    --min-occurrences 2 --nom numerique --contact "votre@courriel" --sortie ./corpus/num_br
```

- **En breton, pensez aux mutations.** La recherche ne les gère pas : il faut donner les variantes (`kenrouedad,genrouedad`).
- **Le comptage se fait en début de mot.** `urzhiataer` compte aussi `urzhiataerioù`.
- **Pour une langue très présente sur Wikipédia**, limitez le volume avec `--plafond`, qui garde les N résultats les plus pertinents par terme.

### Comparer deux Wikipédia : `--marquer`

L'option `--marquer LANGUE` ajoute la variable `*equiv_LANGUE_oui/non` : l'article existe-t-il aussi dans l'autre Wikipédia ? Dans IRaMuTeQ, une classe Reinert composée surtout de `*equiv_fr_non` désigne des sujets propres à la Wikipédia bretonne. Un exemple complet figure dans la [section 4](#4-reproduire-les-corpus-du-dépôt).

### Mode « alignement »

Ce mode part du CSV de métadonnées d'un corpus déjà produit. Il récupère la version des mêmes articles dans une autre langue et produit deux corpus strictement parallèles, avec le même `*id_` dans les deux langues :

```bash
python3 wiki2iramuteq.py --lang fr --aligner ./corpus/num_br/wikipedia_br_numerique_filtre_metadonnees.csv \
    --recherche "informatique,ordinateur,internet,numérique" --contact "votre@courriel" --sortie ./corpus/num_fr_aligne
```

Le dossier de sortie contient :
- `wikipedia_fr_aligne_sur_br_….txt` : les versions françaises ;
- `wikipedia_br_…_aligne_sur_fr.txt` : le corpus d'origine, restreint aux articles qui ont un équivalent.

Ici, `--recherche` est facultatif : il ajoute la variable `*terme_` et le décompte des occurrences, sans rien filtrer.

### Mode « articles parallèles »

Ce mode parcourt une catégorie dans une langue et garde les articles qui existent dans une autre. Il sert quand la catégorie n'existe que dans une langue :

```bash
python3 wiki2iramuteq.py --lang en --paralleles fr --avec-source \
    --categorie "Humanités numériques" --contact "votre@courriel" --sortie ./corpus/hn_en
```

Avec `--avec-source`, le script écrit aussi le sous-corpus dans la langue de départ. Pour le breton et les humanités numériques, ce mode ne trouve aucun article, d'où le choix du mode recherche pour les corpus du dépôt.

## 3. Refiltrer un corpus : `filtrer_corpus.py`

Un nombre minimal d'occurrences pénalise les articles courts. Deux mentions dans 200 mots, c'est le sujet de l'article ; deux mentions dans 5 000 mots, c'est anecdotique. `filtrer_corpus.py` refiltre un corpus déjà téléchargé selon la **densité** des termes (occurrences pour 1 000 mots), puis permet une **révision manuelle** documentée. Il ne retélécharge rien.

```bash
# 1. aperçu : effet de plusieurs seuils et articles les moins denses
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --apercu

# 2. retrouver le titre exact d'un article
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --chercher Atlas

# 3. filtrage avec révision manuelle dans les deux sens
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --min-densite 2 \
    --exclure "Portugal;Shrek" --garder "Treiñ e brezhoneg"
```

Le script produit trois fichiers :
- `…_filtre.txt` : le corpus filtré ;
- `…_filtre_metadonnees.csv` : les métadonnées, utilisables ensuite avec `--aligner` ;
- `…_filtre_criteres.txt` : la trace des seuils, exclusions et conservations appliqués.

## 4. Reproduire les corpus du dépôt

Voici les commandes utilisées le 20 octobre 2026. Wikipédia évoluant, un nouveau tirage donnera des résultats proches, mais pas identiques. Les listes `--exclure` et `--garder` complètes figurent dans les fichiers `*_criteres.txt`.

```bash
# Humanités numériques (fr)
python3 wiki2iramuteq.py --lang fr --categorie "Humanités numériques" --profondeur 2 \
    --contact "votre@courriel" --sortie ./corpus/hn_fr

# Le numérique (br), avec marquage des équivalents français
python3 wiki2iramuteq.py --lang br \
    --recherche "stlenneg,urzhiataer,kenrouedad,genrouedad,niverel,meziant frank,meziantoù frank" \
    --marquer fr --nom numerique --contact "votre@courriel" --sortie ./corpus/num_br
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --min-densite 2 \
    --exclure "…" --garder "…"

# Le numérique (fr), avec marquage des équivalents bretons
python3 wiki2iramuteq.py --lang fr \
    --recherche "informatique,ordinateur,internet,numérique,logiciel libre" \
    --marquer br --plafond 500 --min-occurrences 5 --nom numerique \
    --contact "votre@courriel" --sortie ./corpus/num_fr
python3 filtrer_corpus.py corpus/num_fr/wikipedia_fr_numerique_metadonnees.csv --min-densite 2 \
    --garder "…"

# Paires fr/br
python3 wiki2iramuteq.py --lang fr \
    --aligner ./corpus/num_br/wikipedia_br_numerique_filtre_metadonnees.csv \
    --recherche "informatique,ordinateur,internet,numérique,logiciel libre" \
    --contact "votre@courriel" --sortie ./corpus/num_fr_aligne
```

## 5. Options

### `wiki2iramuteq.py`

| Option | Rôle | Défaut |
|---|---|---|
| `--lang` | Langue du corpus à produire (`fr`, `br`, `en`…) | `fr` |
| `--sortie` | Dossier de sortie, créé s'il n'existe pas | obligatoire |
| `--contact` | Courriel ou site web transmis à Wikimédia (recommandé) | — |
| `--categorie` | Mode catégorie : nom de la catégorie, sans préfixe | — |
| `--profondeur` | Niveaux de sous-catégories parcourus | `2` |
| `--depuis` | Langue dans laquelle `--categorie` est donnée | — |
| `--paralleles` | Mode articles parallèles : langue de départ | — |
| `--avec-source` | Écrit aussi le sous-corpus de la langue de départ | — |
| `--recherche` | Mode recherche : termes séparés par des virgules | — |
| `--min-occurrences` | Occurrences minimales des termes (mode recherche) | `2` |
| `--plafond` | Résultats maximum par terme (mode recherche) | `2000` |
| `--nom` | Nom court du corpus dans les noms de fichiers (mode recherche) | `recherche` |
| `--aligner` | Mode alignement : CSV de métadonnées d'un corpus existant | — |
| `--marquer` | Ajoute `*equiv_LANGUE_oui/non` | — |
| `--min-mots` | Écarte les articles plus courts | `50` |
| `--max-articles` | Limite le nombre d'articles (0 = aucune limite) | `0` |
| `--pause` | Secondes minimum entre deux requêtes | `1` |

### `filtrer_corpus.py`

| Option | Rôle | Défaut |
|---|---|---|
| `--apercu` | Affiche l'effet de plusieurs seuils, sans rien écrire | — |
| `--chercher MOT` | Affiche le titre exact des articles contenant MOT | — |
| `--min-occurrences` | Occurrences minimales | `2` |
| `--min-densite` | Occurrences pour 1 000 mots | `0` |
| `--exclure` | Titres à écarter, séparés par `;` | — |
| `--garder` | Titres à garder malgré les seuils, séparés par `;` | — |

## 6. Licences et citation

- **Code** (`*.py`) : GPL-3.0-or-later, voir le fichier `LICENSE`.
- **Corpus** (dossier `corpus/`) : textes issus de Wikipédia, sous licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr). Les auteurs sont les contributeurs et contributrices de Wikipédia. Chaque fichier `*_metadonnees.csv` donne l'URL et le numéro de révision de chaque article, ce qui permet de retrouver la version utilisée et son historique. Toute réutilisation doit citer la source et rester sous la même licence.

**Pour citer ce travail :** Pierre Rouarch (Anakeyn), *wiki2iramuteq : corpus IRaMuTeQ à partir de Wikipédia*, 2026, https://github.com/Anakeyn/wiki2iramuteq.

Auteur : Pierre Rouarch, Anakeyn.
