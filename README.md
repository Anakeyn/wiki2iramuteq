# wiki2iramuteq

Constitue un corpus au format [IRaMuTeQ](https://pratinaud.gitpages.huma-num.fr/iramuteq-website/) à partir d'une catégorie Wikipédia et de ses sous-catégories, dans n'importe quelle langue (testé pour le français et le breton).

## Ce que fait le script

1. Parcourt une catégorie Wikipédia et ses sous-catégories jusqu'à la profondeur choisie, via l'API MediaWiki.
2. Récupère le texte brut de chaque article (extension TextExtracts) : pas d'infobox, de tableaux ni de références.
3. Supprime les sections annexes (Notes et références, Voir aussi, Liens externes, Bibliographie…, et leurs équivalents bretons).
4. Écrit un fichier `.txt` UTF-8 au format IRaMuTeQ, un texte par article :
   ```
   **** *art_Edition_numerique *cat_Humanites_numeriques *prof_0 *lang_fr
   Texte de l'article…
   ```
5. Écrit un fichier CSV de métadonnées (titre, URL, catégorie, profondeur, révision, nombre de mots, retenu ou non).

## Prérequis

Python 3.8 ou plus récent, sans aucune bibliothèque externe.

## Utilisation

```bash
# Corpus français
python3 wiki2iramuteq.py --lang fr --categorie "Humanités numériques" \
    --profondeur 2 --sortie ~/Documents/FouillesdeTextes/iramuteq/hn_fr

# Corpus breton : la catégorie équivalente est trouvée par les liens interlangues
python3 wiki2iramuteq.py --lang br --depuis fr --categorie "Humanités numériques" \
    --profondeur 2 --sortie ~/Documents/FouillesdeTextes/iramuteq/hn_br
```

### Mode « articles parallèles »

Quand la Wikipédia cible n'a pas de catégorie équivalente (c'est le cas en breton pour « Humanités numériques »), le script parcourt la catégorie dans une autre langue et garde les articles qui ont une version dans la langue voulue :

```bash
python3 wiki2iramuteq.py --lang br --paralleles fr --avec-source \
    --categorie "Humanités numériques" --profondeur 2 --sortie ./corpus/hn_br
```

Avec `--avec-source`, il écrit aussi le sous-corpus français limité aux mêmes articles. Une variable commune `*id_` permet d'apparier les textes des deux langues dans IRaMuTeQ.

### Mode « recherche »

Constitue le corpus à partir de termes plutôt que d'une catégorie (recherche plein texte de Wikipédia). Le script garde les articles où les termes apparaissent au moins `--min-occurrences` fois, et ajoute une variable `*terme_` qui indique le terme dominant de chaque article.

```bash
python3 wiki2iramuteq.py --lang br --recherche "stlenneg,urzhiataer,kenrouedad,genrouedad,niverel" \
    --min-occurrences 2 --nom numerique --sortie ./corpus/num_br
```

En breton, pensez aux **mutations** : la recherche ne les gère pas, il faut donner les variantes (`kenrouedad,genrouedad`). Le comptage se fait en début de mot, ce qui inclut les pluriels et dérivés (`urzhiataer` compte aussi `urzhiataerioù`).

### Comparer deux Wikipédia sur un même thème

Ce protocole répond à la question : quels sujets intéressent les contributeurs de chaque langue ? On lance la même recherche dans chaque langue, avec des termes équivalents, et on marque dans chaque corpus les articles qui existent aussi dans l'autre langue :

```bash
python3 wiki2iramuteq.py --lang br --recherche "stlenneg,urzhiataer,kenrouedad,genrouedad,niverel,meziant frank" \
    --marquer fr --nom numerique --sortie ./corpus/num_br
python3 wiki2iramuteq.py --lang fr --recherche "informatique,ordinateur,internet,numérique,logiciel libre" \
    --marquer br --plafond 500 --min-occurrences 5 --nom numerique --sortie ./corpus/num_fr
```

Dans IRaMuTeQ, croisez les classes (méthode Reinert) avec la variable `*equiv_` : une classe composée surtout de `*equiv_fr_non` désigne des sujets propres à la Wikipédia bretonne.

### Refiltrer un corpus par densité : `filtrer_corpus.py`

Un nombre minimal d'occurrences pénalise les articles courts. Deux mentions dans 200 mots, c'est le sujet de l'article ; deux mentions dans 5 000 mots, c'est anecdotique. `filtrer_corpus.py` refiltre un corpus déjà téléchargé selon la densité des termes (occurrences pour 1 000 mots) :

```bash
# aperçu de plusieurs seuils et liste des articles les moins denses
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --apercu
# filtrage : produit wikipedia_br_numerique_filtre.txt et son CSV
python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --min-densite 5
```

Le CSV filtré peut ensuite servir à `--aligner`.

### Mode « alignement »

Ce mode part d'un corpus déjà produit, via son CSV de métadonnées. Il récupère dans une autre langue les articles retenus et produit deux corpus strictement parallèles, avec les mêmes sujets et le même `*id_` dans les deux langues :

```bash
python3 wiki2iramuteq.py --lang fr --aligner ./corpus/num_br/wikipedia_br_numerique_metadonnees.csv \
    --recherche "informatique,ordinateur,internet,numérique,logiciel libre" --sortie ./corpus/num_fr_aligne
```

Le dossier de sortie contient :
- `wikipedia_fr_aligne_sur_br_numerique.txt` : les versions françaises ;
- `wikipedia_br_numerique_aligne_sur_fr.txt` : le corpus breton restreint aux articles qui ont un équivalent français.

`--recherche` est facultatif ici : il ajoute seulement la variable `*terme_` et le décompte des occurrences, sans rien filtrer.

| Option | Rôle | Défaut |
|---|---|---|
| `--lang` | Wikipédia interrogée (`fr`, `br`, `en`…) | `fr` |
| `--categorie` | Nom de la catégorie, sans préfixe | (ou `--recherche`) |
| `--recherche` | Termes séparés par des virgules (mode recherche) | — |
| `--aligner` | CSV de métadonnées d'un corpus existant (mode alignement) | — |
| `--plafond` | (mode recherche) résultats maximum par terme, les plus pertinents d'abord | `2000` |
| `--marquer` | Ajoute la variable `*equiv_LANGUE_oui/non` (l'article existe-t-il dans cette autre langue ?) | — |
| `--min-occurrences` | (mode recherche) occurrences minimales des termes | `2` |
| `--nom` | (mode recherche) nom court du corpus dans les noms de fichiers | `recherche` |
| `--depuis` | Langue dans laquelle la catégorie est donnée (recherche de l'équivalent) | — |
| `--paralleles` | Langue source pour le mode articles parallèles | — |
| `--avec-source` | (mode parallèle) écrit aussi le sous-corpus de la langue source | — |
| `--profondeur` | Niveaux de sous-catégories parcourus | `2` |
| `--min-mots` | Écarte les articles plus courts | `50` |
| `--max-articles` | Limite le nombre d'articles (0 = aucune) | `0` |
| `--sortie` | Dossier de sortie | obligatoire |
| `--contact` | Courriel ou site web, transmis à Wikimédia dans l'en-tête User-Agent (recommandé) | — |
| `--pause` | Secondes minimum entre deux requêtes | `1` |

Le script respecte les limites de l'API Wikimédia. En cas de réponse HTTP 429 (trop de requêtes), il attend le délai indiqué par le serveur, puis ralentit pour la suite. Un corpus de quelques centaines d'articles prend donc quelques minutes.

## Dans IRaMuTeQ

*Fichier → Ouvrir un corpus*, choisir le fichier `.txt`, encodage **utf-8**, langue **français** (ou la langue bretonne une fois installée).

## Licences

- Code : GPL-3.0-or-later.
- Textes extraits : Wikipédia, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.fr). Le CSV de métadonnées conserve l'URL et la révision de chaque article pour l'attribution.

Auteur : Pierre Rouarch — Anakeyn.
