#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filtrer_corpus — Refiltre un corpus produit par wiki2iramuteq, sans rien retélécharger.

Critères, appliqués aux colonnes « mots » et « occurrences » du CSV de métadonnées :
  --min-occurrences N : au moins N occurrences des termes de recherche ;
  --min-densite D     : au moins D occurrences pour 1 000 mots.
Un article est gardé s'il satisfait les deux critères.

Options --exclure / --garder : titres écartés ou gardés à la main (séparés par « ; »),
--chercher MOT : retrouve le titre exact d'un article.

Écrit <base>_filtre.txt, <base>_filtre_metadonnees.csv et <base>_filtre_criteres.txt
(trace des critères appliqués) à côté des originaux.
Le nouveau CSV peut ensuite servir à --aligner dans wiki2iramuteq.py.

Exemples :
  # aperçu de l'effet de plusieurs seuils, sans rien écrire
  python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv --apercu

  # filtrage effectif
  python3 filtrer_corpus.py corpus/num_br/wikipedia_br_numerique_metadonnees.csv \
      --min-occurrences 2 --min-densite 5

Licence : GPL-3.0-or-later.
"""
import argparse
import csv
import re
import sys
from pathlib import Path


def densite(ligne):
    mots = int(ligne["mots"] or 0)
    occ = int(ligne["occurrences"] or 0)
    return 1000 * occ / mots if mots else 0.0


def garde(ligne, min_occ, min_dens):
    return (ligne["retenu"] == "1" and int(ligne["occurrences"] or 0) >= min_occ
            and densite(ligne) >= min_dens)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="fichier *_metadonnees.csv produit par wiki2iramuteq")
    ap.add_argument("--min-occurrences", type=int, default=2)
    ap.add_argument("--min-densite", type=float, default=0.0,
                    help="occurrences pour 1 000 mots (défaut 0)")
    ap.add_argument("--exclure", default="",
                    help="titres à écarter à la main, séparés par des points-virgules "
                         "(ex. \"Portugal;Matematik\")")
    ap.add_argument("--garder", default="",
                    help="titres à garder malgré les seuils, séparés par des points-virgules")
    ap.add_argument("--chercher", metavar="MOT",
                    help="affiche les titres exacts contenant MOT (pour remplir --exclure / --garder)")
    ap.add_argument("--apercu", action="store_true",
                    help="affiche l'effet de plusieurs seuils sans rien écrire")
    args = ap.parse_args()

    f_csv = Path(args.csv).expanduser()
    with open(f_csv, encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    if not lignes or "occurrences" not in lignes[0]:
        sys.exit("Ce CSV n'a pas de colonne « occurrences » : il faut un corpus produit "
                 "avec --recherche (ou --aligner avec --recherche).")
    retenus = [l for l in lignes if l["retenu"] == "1"]

    if args.chercher:
        for l in retenus:
            if args.chercher.lower() in l["titre"].lower():
                print(f'"{l["titre"]}"  ({l["occurrences"]} occ. / {l["mots"]} mots, '
                      f'{densite(l):.1f} ‰)')
        return

    if args.apercu:
        print(f"{len(retenus)} articles retenus actuellement.\n")
        print("occ. min | densité min (‰ mots) → articles gardés")
        for occ in (2, 3, 4):
            ligne = "   ".join(f"{d:>3} → {sum(garde(l, occ, d) for l in lignes):>4}"
                               for d in (0, 2, 5, 10))
            print(f"   {occ}     | {ligne}")
        print("\nArticles les moins denses (candidats à l'exclusion) :")
        for l in sorted(retenus, key=densite)[:15]:
            print(f"   {densite(l):6.1f} ‰  {l['occurrences']:>3} occ. / {l['mots']:>6} mots  {l['titre']}")
        return

    exclus = {t.strip().lower() for t in args.exclure.split(";") if t.strip()}
    forces = {t.strip().lower() for t in args.garder.split(";") if t.strip()}
    connus = {l["titre"].lower() for l in retenus}
    for nom, ens in (("exclure", exclus), ("garder", forces)):
        if ens - connus:
            print(f"Attention, titres à {nom} introuvables : " + " ; ".join(sorted(ens - connus))
                  + "  (utilisez --chercher MOT pour trouver le titre exact)")
    ids = {l["id"] for l in retenus
           if l["titre"].lower() not in exclus
           and (l["titre"].lower() in forces or garde(l, args.min_occurrences, args.min_densite))}
    ecartes = [l["titre"] for l in retenus if l["id"] not in ids]

    f_txt = f_csv.with_name(f_csv.name.replace("_metadonnees.csv", ".txt"))
    if not f_txt.exists():
        sys.exit(f"Corpus introuvable : {f_txt}")
    blocs = re.split(r"(?m)^(?=\*\*\*\* )", f_txt.read_text(encoding="utf-8"))
    gardes = [b for b in blocs
              if (m := re.search(r"\*id_(\S+)", b.split("\n", 1)[0])) and m.group(1) in ids]

    base = f_txt.stem + "_filtre"
    (f_txt.parent / f"{base}.txt").write_text("".join(gardes), encoding="utf-8")
    with open(f_txt.parent / f"{base}_metadonnees.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        for l in lignes:
            w.writerow({**l, "retenu": "1" if l["id"] in ids else "0"})

    print(f"{len(gardes)} articles gardés sur {len(retenus)} "
          f"(occurrences ≥ {args.min_occurrences}, densité ≥ {args.min_densite} ‰"
          f"{f', {len(exclus)} exclusion(s) manuelle(s)' if exclus else ''}"
          f"{f', {len(forces)} conservation(s) forcée(s)' if forces else ''}).")
    # trace des critères, pour la documentation de la méthode
    (f_txt.parent / f"{base}_criteres.txt").write_text(
        f"Source : {f_csv.name}\nOccurrences minimales : {args.min_occurrences}\n"
        f"Densité minimale : {args.min_densite} ‰\n"
        f"Exclusions manuelles : {args.exclure or 'aucune'}\n"
        f"Conservations forcées : {args.garder or 'aucune'}\n"
        f"Articles gardés : {len(gardes)} sur {len(retenus)}\n", encoding="utf-8")
    print(f"Corpus : {f_txt.parent / (base + '.txt')}")
    if ecartes:
        print(f"Écartés ({len(ecartes)}) : " + " ; ".join(ecartes))


if __name__ == "__main__":
    main()
