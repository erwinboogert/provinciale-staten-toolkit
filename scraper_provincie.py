"""
Scraper voor vergaderstukken van de Provinciale Staten van Nederlandse provincies
Bronnen: Open Raadsinformatie API (osi_-prefix) en Notubiz API

Provinciale Staten zijn het democratisch gekozen bestuursorgaan van een provincie,
verantwoordelijk voor onder meer ruimtelijke ordening, natuur, infrastructuur en
regionaal economisch beleid. Hun vergaderingen zijn openbaar. 8 van de 12 provincies
zijn ontsloten via de ORI API, 1 (Gelderland) via Notubiz, 2 (Zeeland, Noord-Brabant)
via het publieke iBabs-portaal, en alleen Drenthe heeft geen geautomatiseerde bron.

Gebruik:
    python3 scraper_provincie.py zuid-holland           # download vergaderstukken
    python3 scraper_provincie.py zuid-holland --droog   # toon wat er gedownload zou worden
    python3 scraper_provincie.py --lijst                # toon geconfigureerde provincies
    python3 scraper_provincie.py --lijst-ori             # toon alle provincies in ORI

Configuratie: bronnen/provincies.json
Output: ~/Documents/provinciale-staten/provincies/<naam>/

Vereisten: geen externe bibliotheken (alleen standaard Python 3)
"""

import json
import re
import sys

from api import (
    OUTPUT_BASIS, BRONNEN_MAP,
    setup_logging, log, log_samenvatting, parse_jaren_arg,
    alle_indices,
    haal_vergaderingen_ori, download_vergaderingen_ori,
    haal_en_download_vergaderingen,
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATIE
# ══════════════════════════════════════════════════════════════════════════════

STANDAARD_VERGADERTYPEN = {
    "provinciale staten":   True,
    "statencommissie":      True,
    "commissie":            True,
}

MAX_VERGADERINGEN = 50

# ══════════════════════════════════════════════════════════════════════════════


def _lees_provincie_config(naam: str) -> dict:
    """Lees de configuratie voor een provincie uit provincies.json."""
    pad = BRONNEN_MAP / "provincies.json"
    if not pad.exists():
        return {}
    try:
        config = json.loads(pad.read_text(encoding="utf-8"))
        return config.get(naam, {})
    except Exception:
        return {}


def laad_vergadertypen(naam: str) -> dict[str, bool]:
    """Laad vergadertypen uit provincies.json of gebruik standaard."""
    config = _lees_provincie_config(naam)
    if "vergadertypen" in config:
        return {vtype: True for vtype in config["vergadertypen"]}
    return dict(STANDAARD_VERGADERTYPEN)


def find_index_provincie(naam: str) -> str | None:
    """Zoek de meest recente ORI-index (osi_-prefix) voor de provincie."""
    indices = alle_indices()

    config = _lees_provincie_config(naam)
    if "ori_index" in config:
        ori_naam = config["ori_index"]
        prefix = f"osi_{ori_naam}_"
        matches = sorted(i for i in indices if i.startswith(prefix))
        if matches:
            return matches[-1]

    prefix = f"osi_{naam.lower().replace(' ', '_').replace('-', '_')}_"
    matches = sorted(i for i in indices if i.startswith(prefix))
    return matches[-1] if matches else None


# ── Lijsten ───────────────────────────────────────────────────────────────────

def lijst_provincies():
    """Toon geconfigureerde provincies uit provincies.json."""
    pad = BRONNEN_MAP / "provincies.json"
    if not pad.exists():
        print("\nGeen provincies.json gevonden in bronnen/\n")
        return
    config = json.loads(pad.read_text(encoding="utf-8"))
    provincies = {k: v for k, v in config.items() if not k.startswith("_")}
    if not provincies:
        print("\nNog geen provincies geconfigureerd.\n")
        return
    print(f"\n{len(provincies)} provincies:\n")
    for slug, data in sorted(provincies.items()):
        naam = data.get("naam", slug)
        if "ori_index" in data:
            bron = f"ori: osi_{data['ori_index']}"
        elif "notubiz_id" in data:
            bron = f"notubiz: id {data['notubiz_id']}"
        elif "ibabs_naam" in data:
            bron = f"ibabs: {data['ibabs_naam']}"
        else:
            bron = data.get("brontype", "geen")
        print(f"  {slug:<25} {naam:<30} ({bron})")
    print()


def lijst_ori_provincies():
    """Toon beschikbare osi_-indices in de ORI API."""
    indices = alle_indices()
    osi_indices = sorted(i for i in indices if i.startswith("osi_"))

    basisnamen = sorted(set(
        i.replace("osi_", "").rsplit("_", 2)[0]
        for i in osi_indices
    ))

    print()
    print("Beschikbare provincies in de ORI API")
    print("─" * 50)
    print()
    print(f"  {len(basisnamen)} provincies gevonden (osi_-prefix):\n")
    for naam in basisnamen:
        prefix = f"osi_{naam}_"
        recente = sorted(i for i in osi_indices if i.startswith(prefix))
        print(f"  {naam}")
        if recente:
            print(f"    → {recente[-1]}")
    print()


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    vlaggen = {a for a in args if a.startswith("--")}
    droog = "--droog" in vlaggen
    args = [a for a in args if not a.startswith("--")]

    if "--lijst-ori" in vlaggen:
        lijst_ori_provincies()
        return

    if "--lijst" in vlaggen or not args:
        lijst_provincies()
        if not args:
            print(__doc__)
        return

    naam = args[0].lower()
    if not re.match(r'^[a-z0-9][a-z0-9\-\ ]{0,60}$', naam):
        print(f"Ongeldige naam: '{naam}'. Gebruik alleen letters, cijfers en koppeltekens.")
        sys.exit(1)

    vergadertypen = laad_vergadertypen(naam)
    config = _lees_provincie_config(naam)
    output_map = OUTPUT_BASIS / "provincies" / naam
    setup_logging(output_map)

    log("=" * 60)
    log(f"Provincie: {naam}  {'(DROOG)' if droog else ''}")
    log("=" * 60)

    # Brontype bepalen
    brontype = config.get("brontype")
    if brontype == "geen":
        log(f"FOUT: provincie '{naam}' heeft geen geautomatiseerde bron.")
        log("Vergaderstukken moeten handmatig worden opgehaald.")
        sys.exit(1)

    vanaf, terugkijk_dagen = parse_jaren_arg()

    if haal_en_download_vergaderingen(config, vergadertypen, terugkijk_dagen, output_map, droog):
        toon_gerelateerde_regelingen(naam)
        return

    # ORI
    index = find_index_provincie(naam)
    if not index:
        log(f"FOUT: geen ORI-index gevonden voor '{naam}'.")
        log("Gebruik --lijst-ori om beschikbare provincies te ontdekken.")
        sys.exit(1)
    log(f"Bron: ORI-index {index}")

    vergaderingen = haal_vergaderingen_ori(index, vergadertypen, MAX_VERGADERINGEN, vanaf)
    log(f"{len(vergaderingen)} vergaderingen gevonden")

    if not vergaderingen:
        log("Geen vergaderingen gevonden met de geconfigureerde vergadertypen.")
        log(f"Actieve types: {', '.join(k for k, v in vergadertypen.items() if v)}")

    nieuw, overgeslagen, fouten = download_vergaderingen_ori(
        vergaderingen, index, output_map, droog)
    log_samenvatting(nieuw, overgeslagen, fouten, output_map)
    toon_gerelateerde_regelingen(naam)


# ── Gerelateerde regelingen ──────────────────────────────────────────────────

def toon_gerelateerde_regelingen(provincie: str):
    """Toon gemeenschappelijke regelingen waarvan gemeenten in deze provincie liggen."""
    pad = BRONNEN_MAP / "regelingen.json"
    if not pad.exists():
        return
    provincie_config = _lees_provincie_config(provincie)
    gemeenten_provincie = set(provincie_config.get("gemeenten", []))
    if not gemeenten_provincie:
        return

    regelingen = json.loads(pad.read_text(encoding="utf-8"))
    gevonden = [
        (slug, info["naam"])
        for slug, info in regelingen.items()
        if not slug.startswith("_")
        and (gemeenten_provincie & set(info.get("gemeenten", []))
             or provincie in info.get("provincies", []))
    ]
    if not gevonden:
        return

    log("")
    log("  Gemeenschappelijke regelingen in deze provincie")
    log("  " + "─" * 56)
    for slug, naam in sorted(gevonden, key=lambda x: x[1]):
        log(f"    → {naam:<45s} python3 scraper_gr.py {slug}")
    log("  " + "─" * 56)


if __name__ == "__main__":
    main()
