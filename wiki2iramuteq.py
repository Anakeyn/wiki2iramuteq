#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wiki2iramuteq — Constitue un corpus IRaMuTeQ à partir d'une catégorie Wikipédia.

Récupère via l'API MediaWiki les articles d'une catégorie (et de ses
sous-catégories jusqu'à une profondeur donnée), en extrait le texte brut,
retire les sections annexes (références, liens externes, voir aussi...)
et écrit un fichier texte au format IRaMuTeQ (une ligne étoilée par article),
ainsi qu'un fichier CSV de métadonnées.

Exemples :
  python3 wiki2iramuteq.py --lang fr --categorie "Humanités numériques" \
      --profondeur 2 --sortie ~/Documents/FouillesdeTextes/iramuteq/hn_fr

  # Wikipédia en breton, catégorie équivalente trouvée par lien interlangue
  python3 wiki2iramuteq.py --lang br --depuis fr --categorie "Humanités numériques" \
      --profondeur 2 --sortie ./corpus/hn_br

  # Mode articles parallèles : articles de la catégorie française ayant une
  # version bretonne, avec le sous-corpus français correspondant
  python3 wiki2iramuteq.py --lang br --paralleles fr --avec-source \
      --categorie "Humanités numériques" --profondeur 2 --sortie ./corpus/hn_br

  # Mode recherche : articles contenant des termes (ici le numérique en breton)
  python3 wiki2iramuteq.py --lang br --recherche "stlenneg,urzhiataer,kenrouedad,genrouedad,niverel" \
      --min-occurrences 2 --nom numerique --sortie ./corpus/num_br

Licence : GPL-3.0-or-later. Textes Wikipédia : CC BY-SA 4.0.
"""

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# Wikimedia exige un User-Agent identifiant l'outil ET un moyen de contact
# (courriel ou site) ; sans cela les requêtes sont vite limitées (HTTP 429).
# Le contact est complété par l'option --contact.
USER_AGENT = "wiki2iramuteq/1.7 (corpus pour IRaMuTeQ ; contact : {contact}) python-urllib"
CONFIG = {"user_agent": USER_AGENT.format(contact="non renseigné"),
          "pause": 1.0, "dernier_appel": 0.0}

# Préfixe de l'espace de noms « Catégorie » selon la langue
PREFIXES_CATEGORIE = {"fr": "Catégorie", "br": "Rummad", "en": "Category"}

# Titres de sections annexes à supprimer (comparaison en minuscules, début de titre)
SECTIONS_ANNEXES = [
    # français
    "notes et références", "notes", "références", "voir aussi",
    "articles connexes", "liens externes", "bibliographie", "sources",
    "annexes", "pour approfondir", "webographie",
    # breton
    "notennoù", "daveennoù", "daveoù", "notennoù ha daveennoù", "gwelet ivez",
    "da welet ivez", "pennadoù kar", "liammoù", "liamm diavaez", "levrlennadur",
    "levrioù", "mammennoù", "stagadennoù", "lec'hiennoù", "lec'hienn",
    "evit gouzout hiroc'h", "evit gouzout muioc'h", "dielloù",
    # anglais
    "references", "see also", "external links", "further reading",
]


# ---------------------------------------------------------------------------
# Accès à l'API
# ---------------------------------------------------------------------------
def api(lang, **params):
    """Appel GET à l'API MediaWiki : requêtes espacées, respect des limites du serveur."""
    params.update({"format": "json", "formatversion": "2", "maxlag": "5"})
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": CONFIG["user_agent"],
                                               "Accept-Encoding": "identity"})
    for essai in range(8):
        # pause minimale entre deux requêtes, quelle que soit la fonction appelante
        ecart = time.monotonic() - CONFIG["dernier_appel"]
        if ecart < CONFIG["pause"]:
            time.sleep(CONFIG["pause"] - ecart)
        CONFIG["dernier_appel"] = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            if "error" in data:
                if data["error"].get("code") == "maxlag":
                    time.sleep(10)
                    continue
                raise RuntimeError(data["error"])
            return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                # le serveur indique souvent combien de secondes attendre
                try:
                    attente = int(e.headers.get("Retry-After", ""))
                except ValueError:
                    attente = 30 * (essai + 1)
                attente = max(attente, 10)
                CONFIG["pause"] = min(CONFIG["pause"] * 2, 5.0)  # on ralentit pour la suite
                print(f"   (Wikipédia demande de ralentir, HTTP {e.code} — pause de {attente} s, "
                      f"puis {CONFIG['pause']:.0f} s entre requêtes)", file=sys.stderr)
                time.sleep(attente)
            else:
                print(f"   (erreur HTTP {e.code} — nouvel essai dans {2 ** essai} s)", file=sys.stderr)
                time.sleep(2 ** essai)
        except (OSError, ValueError) as e:
            attente = 2 ** essai
            print(f"   (erreur réseau : {e} — nouvel essai dans {attente} s)", file=sys.stderr)
            time.sleep(attente)
    raise RuntimeError(f"Échec de l'appel API après plusieurs essais : {url}")


def titre_categorie(lang, nom):
    prefixe = PREFIXES_CATEGORIE.get(lang, "Category")
    nom = nom.strip()
    for p in set(PREFIXES_CATEGORIE.values()):
        if nom.startswith(p + ":"):
            nom = nom.split(":", 1)[1]
    return f"{prefixe}:{nom}"


def categorie_equivalente(lang_source, categorie, lang_cible):
    """Retrouve la catégorie équivalente dans une autre langue (liens interlangues)."""
    data = api(lang_source, action="query", prop="langlinks",
               titles=titre_categorie(lang_source, categorie), lllang=lang_cible)
    pages = data["query"]["pages"]
    for p in pages:
        for ll in p.get("langlinks", []):
            return ll["title"]
    return None


def membres(lang, cat, cmtype):
    """Liste les membres (pages de l'espace principal ou sous-catégories) d'une catégorie."""
    resultats, suite = [], {}
    while True:
        params = dict(action="query", list="categorymembers", cmtitle=cat,
                      cmtype=cmtype, cmlimit="500", **suite)
        if cmtype == "page":
            params["cmnamespace"] = "0"
        data = api(lang, **params)
        resultats += data["query"]["categorymembers"]
        if "continue" in data:
            suite = data["continue"]
        else:
            return resultats


def parcourir(lang, cat_racine, profondeur_max):
    """Parcours en largeur des catégories. Renvoie {titre: (catégorie, profondeur)}."""
    articles, vues = {}, {cat_racine}
    file = [(cat_racine, 0)]
    while file:
        cat, prof = file.pop(0)
        print(f"  [{prof}] {cat}")
        for m in membres(lang, cat, "page"):
            articles.setdefault(m["title"], (cat.split(":", 1)[1], prof))
        if prof < profondeur_max:
            for sc in membres(lang, cat, "subcat"):
                if sc["title"] not in vues:
                    vues.add(sc["title"])
                    file.append((sc["title"], prof + 1))
    return articles


def texte_article(lang, titre):
    """Texte brut d'un article (extension TextExtracts), avec titres de sections."""
    data = api(lang, action="query", prop="extracts|info", titles=titre,
               explaintext="1", exsectionformat="wiki", redirects="1")
    page = data["query"]["pages"][0]
    return page.get("extract", "") or "", page.get("lastrevid"), page.get("title", titre)


# ---------------------------------------------------------------------------
# Nettoyage et mise au format IRaMuTeQ
# ---------------------------------------------------------------------------
RE_TITRE = re.compile(r"^(=+)\s*(.*?)\s*\1\s*$")


def nettoyer(texte):
    """Supprime les sections annexes et les titres, normalise les espaces."""
    lignes_gardees, niveau_coupe = [], None
    for ligne in texte.splitlines():
        m = RE_TITRE.match(ligne)
        if m:
            niveau, intitule = len(m.group(1)), m.group(2).lower().strip()
            if niveau_coupe is not None and niveau <= niveau_coupe:
                niveau_coupe = None
            if niveau_coupe is None and any(intitule.startswith(s) for s in SECTIONS_ANNEXES):
                niveau_coupe = niveau
            continue  # on ne garde pas les titres de sections eux-mêmes
        if niveau_coupe is None:
            lignes_gardees.append(ligne)
    texte = "\n".join(lignes_gardees)
    texte = texte.replace("*", " ")            # « * » est réservé par IRaMuTeQ
    texte = texte.replace("\u00a0", " ").replace("\u202f", " ")
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n\s*\n+", "\n", texte)  # pas de lignes vides
    return texte.strip()


def modalite(s, longueur=60):
    """Transforme une chaîne en modalité de variable IRaMuTeQ (ASCII, sans espace)."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return (s or "inconnu")[:longueur]


def equivalents(lang_source, titres, lang_cible):
    """Pour une liste de titres (lang_source), renvoie {titre: titre_dans_lang_cible}.
    Interroge les liens interlangues par lots de 50 titres."""
    resultat = {}
    for i in range(0, len(titres), 50):
        lot = titres[i:i + 50]
        suite = {}
        while True:
            data = api(lang_source, action="query", prop="langlinks", lllang=lang_cible,
                       lllimit="max", titles="|".join(lot), redirects="1", **suite)
            q = data.get("query", {})
            # titres normalisés ou redirigés : on remonte au titre d'origine
            origine = {t: t for t in lot}
            for cle in ("normalized", "redirects"):
                for n in q.get(cle, []):
                    for t, o in list(origine.items()):
                        if t == n["from"]:
                            origine[n["to"]] = o
            for page in q.get("pages", []):
                for ll in page.get("langlinks", []):
                    resultat[origine.get(page["title"], page["title"])] = ll["title"]
            if "continue" in data:
                suite = data["continue"]
            else:
                break
    return resultat


def rechercher(lang, termes, plafond=2000):
    """Recherche plein texte (espace principal). Renvoie {titre: [termes trouvés]}."""
    trouves = {}
    for terme in termes:
        requete = f'"{terme}"' if " " in terme else terme
        n, suite = 0, {}
        while n < plafond:
            data = api(lang, action="query", list="search", srsearch=requete,
                       srnamespace="0", srlimit="500", srwhat="text", srinfo="totalhits",
                       srprop="", **suite)
            q = data.get("query", {})
            for r in q.get("search", []):
                trouves.setdefault(r["title"], []).append(terme)
                n += 1
            if "continue" in data:
                suite = data["continue"]
            else:
                break
        total = q.get("searchinfo", {}).get("totalhits", n)
        print(f"  « {terme} » : {total} articles ({n} récupérés)")
    return trouves


def compter(texte, termes):
    """Occurrences de chaque terme (début de mot, insensible à la casse)."""
    return {t: len(re.findall(r"(?<!\w)" + re.escape(t), texte, flags=re.IGNORECASE))
            for t in termes}


def marquer_equivalents(lang, entrees, lang_autre):
    """Ajoute à chaque entrée la variable *equiv_<lang_autre>_oui/non."""
    print(f"Recherche des équivalents en « {lang_autre} »…")
    corresp = equivalents(lang, [e["titre"] for e in entrees], lang_autre)
    for e in entrees:
        e["extra"] = e.get("extra", "") + \
            f" *equiv_{lang_autre}_{'oui' if e['titre'] in corresp else 'non'}"
    print(f"{len(corresp)} articles sur {len(entrees)} existent aussi en « {lang_autre} ».")


def ecrire_corpus(lang, entrees, base, sortie, min_mots, filtre=None, termes=None, min_occ=0):
    """Écrit le corpus IRaMuTeQ et son CSV de métadonnées.
    entrees : liste de dict {id, titre, categorie, prof}. Renvoie l'ensemble des id retenus."""
    f_corpus = sortie / f"{base}.txt"
    f_meta = sortie / f"{base}_metadonnees.csv"
    retenus, titres_ecrits = set(), set()
    with open(f_corpus, "w", encoding="utf-8") as fc, \
         open(f_meta, "w", encoding="utf-8", newline="") as fm:
        meta = csv.writer(fm)
        meta.writerow(["id", "titre", "url", "categorie", "profondeur", "revision", "mots",
                       "occurrences", "retenu"])
        for i, e in enumerate(entrees, 1):
            brut, revid, titre_reel = texte_article(lang, e["titre"])
            if titre_reel in titres_ecrits:  # redirection vers un article déjà écrit
                print(f"  {i:4}/{len(entrees)} = [{lang}] {e['titre']} → {titre_reel} (doublon écarté)")
                continue
            texte = nettoyer(brut)
            nb_mots = len(texte.split())
            retenu = (e["id"] in filtre) if filtre is not None else nb_mots >= min_mots
            variable_terme, occ = "", ""
            if termes:
                comptes = compter(texte, termes)
                occ = sum(comptes.values())
                retenu = retenu and occ >= min_occ
                dominant = max(comptes, key=comptes.get)
                variable_terme = f" *terme_{modalite(dominant, 30)}"
            url = f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(titre_reel.replace(" ", "_"))
            meta.writerow([e["id"], titre_reel, url, e["categorie"], e["prof"], revid, nb_mots,
                           occ, int(retenu)])
            print(f"  {i:4}/{len(entrees)} {'✓' if retenu else '–'} [{lang}] {titre_reel} ({nb_mots} mots{f', {occ} occ.' if termes else ''})")
            if retenu:
                titres_ecrits.add(titre_reel)
                fc.write(f"**** *art_{modalite(titre_reel)} *id_{e['id']} "
                         f"*cat_{modalite(e['categorie'], 40)} *prof_{e['prof']}{variable_terme}{e.get('extra', '')} "
                         f"*lang_{lang}\n"
                         f"{texte}\n\n")
                retenus.add(e["id"])
    print(f"\n{len(retenus)} articles écrits dans {f_corpus}")
    print(f"Métadonnées : {f_meta}")
    return retenus


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", default="fr", help="langue du corpus à produire (fr, br...)")
    ap.add_argument("--categorie", help="nom de la catégorie (sans préfixe)")
    ap.add_argument("--recherche", metavar="TERMES",
                    help="mode recherche : termes séparés par des virgules, variantes comprises "
                         "(ex. \"stlenneg,urzhiataer,kenrouedad,genrouedad\")")
    ap.add_argument("--aligner", metavar="CSV",
                    help="mode alignement : à partir du CSV de métadonnées d'un corpus déjà produit, "
                         "récupère la version en --lang des articles retenus (mêmes *id_)")
    ap.add_argument("--plafond", type=int, default=2000,
                    help="(mode recherche) nombre maximal de résultats par terme, les plus "
                         "pertinents d'abord (défaut 2000)")
    ap.add_argument("--marquer", metavar="LANGUE",
                    help="ajoute la variable *equiv_LANGUE_oui/non : l'article existe-t-il "
                         "aussi dans cette langue ?")
    ap.add_argument("--min-occurrences", type=int, default=2,
                    help="(mode recherche) occurrences minimales des termes dans l'article (défaut 2)")
    ap.add_argument("--nom", default="",
                    help="(mode recherche) nom court du corpus pour les fichiers (défaut : recherche)")
    ap.add_argument("--depuis", help="langue dans laquelle --categorie est donnée ; "
                                     "la catégorie équivalente en --lang est alors recherchée")
    ap.add_argument("--paralleles", metavar="LANGUE_SOURCE",
                    help="mode articles parallèles : parcourt la catégorie dans LANGUE_SOURCE "
                         "et garde les articles qui existent aussi en --lang")
    ap.add_argument("--avec-source", action="store_true",
                    help="(mode parallèle) écrit aussi le sous-corpus dans la langue source, "
                         "limité aux mêmes articles, pour comparaison")
    ap.add_argument("--profondeur", type=int, default=2, help="profondeur des sous-catégories (défaut 2)")
    ap.add_argument("--min-mots", type=int, default=50, help="ignorer les articles plus courts (défaut 50)")
    ap.add_argument("--max-articles", type=int, default=0, help="limite (0 = pas de limite)")
    ap.add_argument("--sortie", required=True, help="dossier de sortie")
    ap.add_argument("--contact", default="",
                    help="courriel ou site web transmis à Wikimédia dans le User-Agent "
                         "(recommandé par Wikimédia pour éviter les blocages)")
    ap.add_argument("--pause", type=float, default=1.0,
                    help="secondes minimum entre deux requêtes (défaut 1)")
    args = ap.parse_args()

    if args.contact:
        CONFIG["user_agent"] = USER_AGENT.format(contact=args.contact)
    else:
        print("Conseil : indiquez --contact (courriel ou site) pour être identifié par Wikimédia.")
    CONFIG["pause"] = max(args.pause, 0.5)

    sortie = Path(args.sortie).expanduser()
    sortie.mkdir(parents=True, exist_ok=True)

    if not (args.categorie or args.recherche or args.aligner):
        ap.error("indiquez --categorie, --recherche ou --aligner")

    # ----- Mode alignement --------------------------------------------------
    if args.aligner:
        with open(Path(args.aligner).expanduser(), encoding="utf-8") as f:
            lignes = [l for l in csv.DictReader(f) if l.get("retenu") == "1"]
        if not lignes:
            sys.exit("Aucun article retenu dans ce CSV.")
        src = urllib.parse.urlparse(lignes[0]["url"]).netloc.split(".")[0]
        print(f"{len(lignes)} articles retenus en « {src} ». Recherche des versions en « {args.lang} »…")
        corresp = equivalents(src, [l["titre"] for l in lignes], args.lang)
        print(f"{len(corresp)} ont une version en « {args.lang} » "
              f"({len(lignes) - len(corresp)} sans équivalent).")
        entrees, deja = [], set()
        for l in lignes:
            cible = corresp.get(l["titre"])
            if cible and cible not in deja:
                deja.add(cible)
                entrees.append(dict(id=l["id"], titre=cible, categorie=l["categorie"],
                                    prof=l["profondeur"]))
        if len(entrees) < len(corresp):
            print(f"({len(corresp) - len(entrees)} doublon(s) écarté(s) : plusieurs articles "
                  f"pointent vers le même article en « {args.lang} »)")
        base = Path(args.aligner).name.replace("_metadonnees.csv", "")
        base = base.replace(f"wikipedia_{src}_", f"wikipedia_{args.lang}_aligne_sur_{src}_", 1)
        termes = [t.strip() for t in args.recherche.split(",")] if args.recherche else None
        ids = ecrire_corpus(args.lang, entrees, base, sortie, 0, termes=termes, min_occ=0)
        # corpus source restreint aux mêmes articles, pour une comparaison stricte
        f_src = Path(args.aligner).expanduser().with_name(
            Path(args.aligner).name.replace("_metadonnees.csv", ".txt"))
        if f_src.exists():
            blocs = re.split(r"(?m)^(?=\*\*\*\* )", f_src.read_text(encoding="utf-8"))
            garder = [b for b in blocs
                      if (m := re.search(r"\*id_(\S+)", b.split("\n", 1)[0])) and m.group(1) in ids]
            f_out = sortie / f_src.name.replace(".txt", f"_aligne_sur_{args.lang}.txt")
            f_out.write_text("".join(garder), encoding="utf-8")
            print(f"Corpus « {src} » restreint aux mêmes {len(garder)} articles : {f_out}")
        print(f"Source : Wikipédia ({args.lang}), CC BY-SA 4.0, extraction du {date.today():%d/%m/%Y}.")
        return

    # ----- Mode recherche ---------------------------------------------------
    if args.recherche:
        termes = [t.strip() for t in args.recherche.split(",") if t.strip()]
        print(f"Recherche sur {args.lang}.wikipedia.org : {', '.join(termes)}")
        trouves = rechercher(args.lang, termes, plafond=args.plafond)
        print(f"{len(trouves)} articles distincts contiennent au moins un terme.")
        titres = sorted(trouves, key=lambda t: (-len(set(trouves[t])), t))
        if args.max_articles:
            titres = titres[: args.max_articles]
        entrees = [dict(id=modalite(t, 50), titre=t, categorie="recherche", prof=0) for t in titres]
        if args.marquer:
            marquer_equivalents(args.lang, entrees, args.marquer)
        nom = modalite(args.nom or "recherche").lower()
        ecrire_corpus(args.lang, entrees, f"wikipedia_{args.lang}_{nom}", sortie,
                      args.min_mots, termes=termes, min_occ=args.min_occurrences)
        print(f"Source : Wikipédia ({args.lang}), CC BY-SA 4.0, extraction du {date.today():%d/%m/%Y}.")
        return

    # ----- Mode articles parallèles -----------------------------------------
    if args.paralleles and args.paralleles != args.lang:
        src = args.paralleles
        cat = titre_categorie(src, args.categorie)
        print(f"Parcours de {cat} (profondeur {args.profondeur}) sur {src}.wikipedia.org")
        articles = parcourir(src, cat, args.profondeur)
        print(f"{len(articles)} articles en « {src} ». Recherche des versions en « {args.lang} »…")
        corresp = equivalents(src, sorted(articles), args.lang)
        print(f"{len(corresp)} articles ont une version en « {args.lang} ».")
        if not corresp:
            sys.exit("Aucun article parallèle : essayez une profondeur plus grande ou une autre catégorie.")
        titres = sorted(corresp)
        if args.max_articles:
            titres = titres[: args.max_articles]
        entrees_cible, entrees_src = [], []
        for t in titres:
            categorie, prof = articles[t]
            ident = modalite(t, 50)
            entrees_cible.append(dict(id=ident, titre=corresp[t], categorie=categorie, prof=prof))
            entrees_src.append(dict(id=ident, titre=t, categorie=categorie, prof=prof))
        nom = modalite(cat.split(":", 1)[1]).lower()
        retenus = ecrire_corpus(args.lang, entrees_cible,
                                f"wikipedia_{args.lang}_paralleles_{nom}", sortie, args.min_mots)
        if args.avec_source and retenus:
            print(f"\nSous-corpus « {src} » limité aux mêmes articles :")
            ecrire_corpus(src, entrees_src, f"wikipedia_{src}_paralleles_{nom}",
                          sortie, args.min_mots, filtre=retenus)
        print(f"Source : Wikipédia, CC BY-SA 4.0, extraction du {date.today():%d/%m/%Y}.")
        return

    # ----- Mode catégorie (normal) ------------------------------------------
    if args.depuis and args.depuis != args.lang:
        cat = categorie_equivalente(args.depuis, args.categorie, args.lang)
        if not cat:
            sys.exit(f"Pas de catégorie équivalente en « {args.lang} » pour « {args.categorie} » "
                     f"({args.depuis}). Indiquez-la avec --categorie, ou utilisez "
                     f"--paralleles {args.depuis}.")
        print(f"Catégorie équivalente en {args.lang} : {cat}")
    else:
        cat = titre_categorie(args.lang, args.categorie)

    print(f"Parcours de {cat} (profondeur {args.profondeur}) sur {args.lang}.wikipedia.org")
    articles = parcourir(args.lang, cat, args.profondeur)
    print(f"{len(articles)} articles trouvés.")
    titres = sorted(articles)
    if args.max_articles:
        titres = titres[: args.max_articles]
    entrees = [dict(id=modalite(t, 50), titre=t, categorie=articles[t][0], prof=articles[t][1])
               for t in titres]
    if args.marquer:
        marquer_equivalents(args.lang, entrees, args.marquer)
    ecrire_corpus(args.lang, entrees, f"wikipedia_{args.lang}_{modalite(cat.split(':', 1)[1]).lower()}",
                  sortie, args.min_mots)
    print(f"Source : Wikipédia ({args.lang}), CC BY-SA 4.0, extraction du {date.today():%d/%m/%Y}.")


if __name__ == "__main__":
    main()
