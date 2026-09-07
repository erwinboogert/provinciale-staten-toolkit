"""
Scraper voor vergaderstukken van gemeenschappelijke regelingen (GRs)
Bronnen: Open Raadsinformatie API (ORI), Notubiz API direct, of het publieke iBabs-portaal

Gemeenschappelijke regelingen zijn samenwerkingsverbanden tussen gemeenten
(en soms de provincie): omgevingsdiensten, GGD'en, sociale
werkvoorzieningsschappen, jeugdzorgregio's, vervoersautoriteiten en meer.
Ze vergaderen openbaar maar worden nauwelijks journalistiek gevolgd.

Deze catalogus (bronnen/regelingen.json) is opgebouwd per provincie: elke GR
noemt de gemeenten die eraan deelnemen. Welke GRs bij een provincie horen
wordt afgeleid uit de overlap met de gemeentenlijst in bronnen/provincies.json.

De scraper ondersteunt drie bronnen:
  - ORI API: GRs die als gemeente-index in ORI staan (ori_-prefix)
  - Notubiz API direct: elke GR met een notubiz_id in bronnen/regelingen.json
  - iBabs Publieksportaal: elke GR met een ibabs_naam in bronnen/regelingen.json

Gebruik:
    python3 scraper_gr.py <regeling>                 # download vergaderstukken
    python3 scraper_gr.py nieuw-reijerwaard --droog  # droog uitvoeren
    python3 scraper_gr.py nieuw-reijerwaard --jaren 1 # alleen het afgelopen jaar
    python3 scraper_gr.py --lijst                    # toon alle geconfigureerde GRs
    python3 scraper_gr.py --lijst-ori                # toon alle gemeenten in ORI
    python3 scraper_gr.py --provincie zuid-holland   # toon GRs in die provincie
    python3 scraper_gr.py --zoek jeugdhulp           # zoek GR in Notubiz

Opties:
    <regeling>          Naam/slug van de regeling, zoals in --lijst (bijv. nieuw-reijerwaard)
    --droog             Toon wat er gedownload zou worden, download niets echt
    --jaren N           Kijk N jaar terug in plaats van de standaard 2 jaar (mag decimaal, bijv. 0.5)
    --lijst             Toon alle geconfigureerde regelingen en hun brontype
    --lijst-ori         Toon alle gemeente-indices die beschikbaar zijn in de ORI API
    --provincie <naam>  Toon de regelingen waarvan gemeenten in deze provincie liggen
    --zoek <term>       Zoek een organisatie op naam in de Notubiz-catalogus
    --help, -h          Toon deze hulptekst

Configuratie: bronnen/regelingen.json, bronnen/provincies.json
Output: ~/Documents/provinciale-staten/regelingen/<naam>/

Vereisten: geen externe bibliotheken (alleen standaard Python 3)
"""

import json
import re
import sys

from api import (
    OUTPUT_BASIS, BRONNEN_MAP,
    setup_logging, log, log_samenvatting, parse_jaren_arg,
    alle_indices,
    notubiz_verzoek,
    download_vergaderingen_ori,
    haal_vergaderingen_ori,
    haal_en_download_vergaderingen,
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATIE
# ══════════════════════════════════════════════════════════════════════════════

STANDAARD_VERGADERTYPEN = {
    "algemeen bestuur":           True,
    "dagelijks bestuur":          True,
    "portefeuillehoudersoverleg": True,
}

MAX_VERGADERINGEN = 50

# ══════════════════════════════════════════════════════════════════════════════


def find_index_gr(naam: str) -> str | None:
    """Zoek de meest recente ORI-index voor de opgegeven GR.

    Probeert eerst de ori_index uit regelingen.json. Valt daarna terug
    op directe naammatching.
    """
    indices = alle_indices()

    config = _lees_regeling_config(naam)
    if "ori_index" in config:
        ori_naam = config["ori_index"]
        prefix = f"ori_{ori_naam.lower().replace(' ', '_').replace('-', '_')}_"
        matches = sorted(i for i in indices if i.startswith(prefix))
        if matches:
            return matches[-1]

    prefix = f"ori_{naam.lower().replace(' ', '_').replace('-', '_')}_"
    matches = sorted(i for i in indices if i.startswith(prefix))
    return matches[-1] if matches else None


def _lees_regeling_config(naam: str) -> dict:
    """Lees de configuratie voor een GR uit regelingen.json."""
    pad = BRONNEN_MAP / "regelingen.json"
    if not pad.exists():
        return {}
    try:
        config = json.loads(pad.read_text(encoding="utf-8"))
        return config.get(naam, {})
    except Exception:
        return {}


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
    """Laad vergadertypen uit regelingen.json of gebruik standaard."""
    config = _lees_regeling_config(naam)
    if "vergadertypen" in config:
        return {vtype: True for vtype in config["vergadertypen"]}
    return dict(STANDAARD_VERGADERTYPEN)


# ── Lijsten ───────────────────────────────────────────────────────────────────

def lijst_regelingen():
    """Toon geconfigureerde GRs uit regelingen.json."""
    pad = BRONNEN_MAP / "regelingen.json"
    if not pad.exists():
        print("\nGeen regelingen.json gevonden in bronnen/\n")
        return
    config = json.loads(pad.read_text(encoding="utf-8"))
    regelingen = {k: v for k, v in config.items() if not k.startswith("_")}
    if not regelingen:
        print("\nNog geen regelingen geconfigureerd.")
        print("Gebruik '--lijst-ori' om te zien welke GRs beschikbaar zijn in ORI,")
        print("of '--zoek <naam>' om een Notubiz-organisatie op te zoeken.\n")
        return
    print(f"\n{len(regelingen)} geconfigureerde regelingen:\n")
    for slug, data in sorted(regelingen.items()):
        naam = data.get("naam", slug)
        if data.get("notubiz_id"):
            bron = f"notubiz:{data['notubiz_id']}"
        elif data.get("ibabs_naam"):
            bron = f"ibabs:{data['ibabs_naam']}"
        elif data.get("ori_index"):
            bron = f"ori:{data['ori_index']}"
        elif data.get("website"):
            bron = f"handmatig: {data['website']}"
        else:
            bron = "onbekend"
        print(f"  {slug:<32} {naam:<50} ({bron})")
    print()


def lijst_regelingen_provincie(provincie: str):
    """Toon GRs waarvan gemeenten in de opgegeven provincie liggen."""
    provincie_config = _lees_provincie_config(provincie)
    if not provincie_config:
        print(f"\nOnbekende provincie: '{provincie}'. Gebruik scraper_provincie.py --lijst voor de lijst.\n")
        return
    gemeenten_provincie = set(provincie_config.get("gemeenten", []))

    pad = BRONNEN_MAP / "regelingen.json"
    if not pad.exists():
        print("\nGeen regelingen.json gevonden in bronnen/\n")
        return
    config = json.loads(pad.read_text(encoding="utf-8"))
    regelingen = {k: v for k, v in config.items() if not k.startswith("_")}

    gevonden = {
        slug: data for slug, data in regelingen.items()
        if gemeenten_provincie & set(data.get("gemeenten", []))
        or provincie in data.get("provincies", [])
    }

    naam_provincie = provincie_config.get("naam", provincie)
    if not gevonden:
        print(f"\nGeen gemeenschappelijke regelingen gevonden voor {naam_provincie}.\n")
        return

    print(f"\n{len(gevonden)} gemeenschappelijke regelingen met gemeenten in {naam_provincie}:\n")
    for slug, data in sorted(gevonden.items(), key=lambda x: x[1].get("naam", x[0])):
        naam = data.get("naam", slug)
        if data.get("notubiz_id"):
            bron = f"notubiz:{data['notubiz_id']}"
        elif data.get("ibabs_naam"):
            bron = f"ibabs:{data['ibabs_naam']}"
        elif data.get("ori_index"):
            bron = f"ori:{data['ori_index']}"
        elif data.get("website"):
            bron = f"handmatig: {data['website']}"
        else:
            bron = "onbekend"
        print(f"  {slug:<32} {naam:<50} ({bron})")
    print()


def lijst_ori_gr():
    """Toon beschikbare ORI-indices."""
    indices = alle_indices()

    ori = sorted(set(
        i.replace("ori_", "").rsplit("_", 2)[0].replace("_", "-")
        for i in indices if i.startswith("ori_")
    ))

    print()
    print("Beschikbare gemeente-indices in de ORI API")
    print("─" * 50)
    print()
    print(f"  {len(ori)} gemeenten gevonden (ori_-prefix)")
    print()
    print("  Gemeenschappelijke regelingen zijn momenteel NIET")
    print("  opgenomen in de ORI API. Zoek de stukken van jouw GR")
    print("  op de eigen website of via Notubiz (--zoek <naam>).")
    print()
    print("  Als jouw GR wél in ORI staat (bijv. als gemeente geregistreerd),")
    print("  zoek de naam dan in onderstaande lijst en gebruik die als ori_index")
    print("  in bronnen/regelingen.json.")
    print()
    print(f"  Alle {len(ori)} gemeenten in ORI:\n")
    for naam in ori:
        print(f"    {naam}")
    print()


def zoek_notubiz_organisaties(zoekterm: str) -> list[dict]:
    """Zoek GR-organisaties in de Notubiz-catalogus op naam."""
    data = notubiz_verzoek("organisations")
    orgs = data.get("organisations", {}).get("organisation", [])
    term = zoekterm.lower()
    return [
        {
            "id": int(o.get("@attributes", {}).get("id", 0) or o.get("id", 0)),
            "naam": o.get("name", "").strip(),
        }
        for o in orgs
        if term in o.get("name", "").lower()
    ]


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    args = sys.argv[1:]
    vlaggen = {a for a in args if a.startswith("--")}
    droog = "--droog" in vlaggen
    args = [a for a in args if not a.startswith("--")]

    if "--lijst-ori" in vlaggen:
        lijst_ori_gr()
        return

    if "--provincie" in vlaggen:
        if not args:
            print("\nGebruik: python3 scraper_gr.py --provincie <naam>\n")
            sys.exit(1)
        lijst_regelingen_provincie(args[0].lower())
        return

    if "--lijst" in vlaggen or not args:
        lijst_regelingen()
        if not args:
            print(__doc__)
        return

    if "--zoek" in vlaggen:
        if not args:
            print("\nGebruik: python3 scraper_gr.py --zoek <zoekterm>\n")
            sys.exit(1)
        zoekterm = " ".join(args)
        resultaten = zoek_notubiz_organisaties(zoekterm)
        if not resultaten:
            print(f"\nGeen Notubiz-organisaties gevonden voor '{zoekterm}'.\n")
        else:
            print(f"\n{len(resultaten)} organisaties gevonden voor '{zoekterm}':\n")
            for r in resultaten:
                print(f"  {r['id']:<8} {r['naam']}")
            print()
            print("Voeg toe aan bronnen/regelingen.json met notubiz_id.\n")
        return

    naam = args[0].lower()
    if not re.match(r'^[a-z0-9][a-z0-9\-\ ]{0,60}$', naam):
        print(f"Ongeldige naam: '{naam}'. Gebruik alleen letters, cijfers en koppeltekens.")
        sys.exit(1)

    vergadertypen = laad_vergadertypen(naam)
    config = _lees_regeling_config(naam)
    if not config:
        print(f"Onbekende regeling: '{naam}'. Gebruik --lijst voor de geconfigureerde regelingen.")
        sys.exit(1)
    if not any(config.get(v) for v in ("notubiz_id", "ibabs_naam", "ori_index")):
        print(f"FOUT: van '{naam}' is geen geautomatiseerde bron bekend.")
        if config.get("website"):
            print(f"Vergaderstukken moeten handmatig worden opgehaald via: {config['website']}")
        sys.exit(1)

    output_map = OUTPUT_BASIS / "regelingen" / naam
    setup_logging(output_map)

    log("=" * 60)
    log(f"GR: {naam}  {'(DROOG)' if droog else ''}")
    log("=" * 60)

    vanaf, terugkijk_dagen = parse_jaren_arg()

    if haal_en_download_vergaderingen(config, vergadertypen, terugkijk_dagen, output_map, droog):
        return

    index = find_index_gr(naam)
    if not index:
        log(f"FOUT: geen ORI-index, notubiz_id of ibabs_naam gevonden voor '{naam}'.")
        log("Gebruik --lijst-ori om beschikbare GRs in ORI te ontdekken.")
        log("Gebruik --zoek <naam> om een Notubiz-organisatie op te zoeken.")
        sys.exit(1)
    log(f"Bron: ORI API (index={index})")

    vergaderingen = haal_vergaderingen_ori(index, vergadertypen, MAX_VERGADERINGEN, vanaf)
    log(f"{len(vergaderingen)} vergaderingen gevonden")

    if not vergaderingen:
        log("Geen vergaderingen gevonden met de geconfigureerde vergadertypen.")
        log(f"Actieve types: {', '.join(k for k, v in vergadertypen.items() if v)}")

    nieuw, overgeslagen, fouten = download_vergaderingen_ori(
        vergaderingen, index, output_map, droog)
    log_samenvatting(nieuw, overgeslagen, fouten, output_map)


if __name__ == "__main__":
    main()
