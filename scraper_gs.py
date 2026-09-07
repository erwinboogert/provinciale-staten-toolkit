"""
Scraper voor besluiten van Gedeputeerde Staten (GS) van Nederlandse provincies

Gedeputeerde Staten is het dagelijks bestuur van een provincie: het orgaan dat
vergunningen verleent, subsidies toekent, grond aankoopt en contracten sluit.
Provinciale Staten stelt kaders en controleert; GS voert uit. GS-besluiten
krijgen structureel minder aandacht dan PS-vergaderingen, terwijl daar het
feitelijke bestuur gebeurt.

Belangrijk verschil met Provinciale Staten: niet elk GS-besluit is openbaar —
een deel kan (tijdelijk) vertrouwelijk zijn. Deze scraper haalt op wat
openbaar gepubliceerd is en meldt expliciet hoeveel vergaderingen/documenten
dat zijn, zonder te suggereren dat daarmee de volledige besluitvorming
zichtbaar is.

De bron verschilt sterk per provincie. Sommige publiceren GS in dezelfde
vergaderfeed als Provinciale Staten (Notubiz/iBabs/ORI, met een eigen
vergadertype); andere hebben geen vergaderportaal maar een eigen website met
besluitenlijst-PDF's — als eenvoudige index met directe links (backend
"pdf-index") of als los doorzoekbare per-besluit-pagina's (backend
"zuid-holland-website"). Zie het geneste "gs"-veld per provincie in
bronnen/provincies.json, en het "reden"-veld als er nog geen bron bekend is.

Gebruik:
    python3 scraper_gs.py gelderland          # download GS-besluiten
    python3 scraper_gs.py gelderland --droog  # toon wat er gedownload zou worden
    python3 scraper_gs.py --lijst             # toon GS-status per provincie

Configuratie: bronnen/provincies.json (geneste "gs"-sleutel per provincie)
Output: ~/Documents/provinciale-staten/gs/<naam>/

Vereisten: geen externe bibliotheken (alleen standaard Python 3)
"""

import json
import re
import sys

from api import (
    OUTPUT_BASIS, BRONNEN_MAP,
    setup_logging, log, log_samenvatting, parse_jaren_arg,
    haal_en_download_vergaderingen,
    haal_besluiten_zuid_holland, haal_besluiten_pdf_index,
    haal_besluiten_pdf_index_genest, haal_besluiten_fryslan,
    haal_besluiten_utrecht, schrijf_besluiten_utrecht,
    haal_besluiten_zeeland,
    download_vergaderingen_ibabs,
)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATIE
# ══════════════════════════════════════════════════════════════════════════════

STANDAARD_VERGADERTYPEN = {
    "gs-vergadering": True,
    "gs vergadering":  True,
}

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


def _lees_gs_config(naam: str) -> dict:
    """Lees de GS-configuratie voor een provincie (geneste 'gs'-sleutel)."""
    return _lees_provincie_config(naam).get("gs", {})


def laad_vergadertypen(naam: str) -> dict[str, bool]:
    """Laad vergadertypen uit de GS-config of gebruik de standaard."""
    config = _lees_gs_config(naam)
    if "vergadertypen" in config:
        return {vtype: True for vtype in config["vergadertypen"]}
    return dict(STANDAARD_VERGADERTYPEN)


# ── Lijsten ───────────────────────────────────────────────────────────────────

def lijst_provincies():
    """Toon de GS-status per provincie uit provincies.json."""
    pad = BRONNEN_MAP / "provincies.json"
    if not pad.exists():
        print("\nGeen provincies.json gevonden in bronnen/\n")
        return
    config = json.loads(pad.read_text(encoding="utf-8"))
    provincies = {k: v for k, v in config.items() if not k.startswith("_")}
    if not provincies:
        print("\nNog geen provincies geconfigureerd.\n")
        return
    print(f"\nGS-status voor {len(provincies)} provincies:\n")
    for slug, data in sorted(provincies.items()):
        naam = data.get("naam", slug)
        gs = data.get("gs", {})
        if gs.get("notubiz_id"):
            bron = f"notubiz: id {gs['notubiz_id']}"
        elif gs.get("ibabs_naam"):
            bron = f"ibabs: {gs['ibabs_naam']}"
        elif gs.get("ori_index"):
            bron = f"ori: {gs['ori_index']}"
        elif gs.get("backend"):
            bron = f"eigen backend: {gs['backend']}"
        elif gs.get("dataset_url"):
            bron = f"open dataset (nog niet ondersteund): {gs['dataset_url']}"
        else:
            bron = gs.get("reden", "onbekend")
        vlag = "x" if gs.get("geverifieerd") else " "
        print(f"  [{vlag}] {slug:<25} {naam:<30} ({bron})")
    print()


# ── Hoofdprogramma ────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    vlaggen = {a for a in args if a.startswith("--")}
    droog = "--droog" in vlaggen
    args = [a for a in args if not a.startswith("--")]

    if "--lijst" in vlaggen or not args:
        lijst_provincies()
        if not args:
            print(__doc__)
        return

    naam = args[0].lower()
    if not re.match(r'^[a-z0-9][a-z0-9\-\ ]{0,60}$', naam):
        print(f"Ongeldige naam: '{naam}'. Gebruik alleen letters, cijfers en koppeltekens.")
        sys.exit(1)

    provincie_config = _lees_provincie_config(naam)
    if not provincie_config:
        print(f"Onbekende provincie: '{naam}'. Gebruik --lijst voor de geconfigureerde provincies.")
        sys.exit(1)

    gs_config = provincie_config.get("gs", {})
    heeft_bron = any(gs_config.get(v) for v in ("notubiz_id", "ibabs_naam", "ori_index"))
    backend = gs_config.get("backend")
    if not heeft_bron and backend not in (
            "zuid-holland-website", "pdf-index", "pdf-index-genest",
            "fryslan-website", "utrecht-tekst", "zeeland-website"):
        reden = gs_config.get("reden", "nog-niet-onderzocht")
        print(f"FOUT: van GS van '{naam}' is geen geautomatiseerde bron bekend (reden: {reden}).")
        if gs_config.get("dataset_url"):
            print(f"Besluiten staan wel als open dataset online: {gs_config['dataset_url']}")
            print("(deze scraper ondersteunt dat brontype nog niet — zie bronnen/provincies.json)")
        sys.exit(1)

    output_map = OUTPUT_BASIS / "gs" / naam
    setup_logging(output_map)

    log("=" * 60)
    log(f"GS: {naam}  {'(DROOG)' if droog else ''}")
    log("=" * 60)
    log("Let op: niet elk GS-besluit is openbaar. Onderstaande aantallen zijn")
    log("wat via deze bron publiek gevonden is, niet noodzakelijk de volledige")
    log("besluitvorming.")

    _, terugkijk_dagen = parse_jaren_arg()

    if backend == "zuid-holland-website":
        log("Bron: eigen website Provincie Zuid-Holland (geen vergaderportaal)")
        log("Let op: traag — geen bulk-API, één verzoek per besluit voor de bijlagen.")
        besluiten = haal_besluiten_zuid_holland(terugkijk_dagen=terugkijk_dagen)
        log(f"{len(besluiten)} besluiten gevonden")
        if not besluiten:
            log("Geen besluiten gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = download_vergaderingen_ibabs(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    if backend == "pdf-index":
        log(f"Bron: eigen website (besluitenlijst-PDF-index) — {gs_config.get('index_url', '')}")
        besluiten = haal_besluiten_pdf_index(
            gs_config["index_url"], terugkijk_dagen=terugkijk_dagen,
            pagina_param=gs_config.get("pagina_param"))
        log(f"{len(besluiten)} besluiten gevonden")
        if not besluiten:
            log("Geen besluiten gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = download_vergaderingen_ibabs(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    if backend == "pdf-index-genest":
        log(f"Bron: eigen website (jaar->maand-index met besluitenlijst-PDF's) — {gs_config.get('index_url', '')}")
        besluiten = haal_besluiten_pdf_index_genest(
            gs_config["index_url"], terugkijk_dagen=terugkijk_dagen)
        log(f"{len(besluiten)} besluiten gevonden")
        if not besluiten:
            log("Geen besluiten gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = download_vergaderingen_ibabs(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    if backend == "fryslan-website":
        log("Bron: eigen website Provincie Fryslân (één pagina per jaar, geen vergaderportaal)")
        besluiten = haal_besluiten_fryslan(terugkijk_dagen=terugkijk_dagen)
        log(f"{len(besluiten)} besluiten gevonden")
        if not besluiten:
            log("Geen besluiten gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = download_vergaderingen_ibabs(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    if backend == "utrecht-tekst":
        log("Bron: eigen iBabs-portaal Provincie Utrecht (platte tekst per agendapunt, geen PDF's)")
        besluiten = haal_besluiten_utrecht(terugkijk_dagen=terugkijk_dagen)
        log(f"{len(besluiten)} vergaderingen gevonden")
        if not besluiten:
            log("Geen vergaderingen gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = schrijf_besluiten_utrecht(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    if backend == "zeeland-website":
        log("Bron: eigen website Provincie Zeeland (Woo-index, geen vergaderportaal)")
        besluiten = haal_besluiten_zeeland(terugkijk_dagen=terugkijk_dagen)
        log(f"{len(besluiten)} besluiten gevonden")
        if not besluiten:
            log("Geen besluiten gevonden in dit tijdvenster.")
        nieuw, overgeslagen, fouten = download_vergaderingen_ibabs(besluiten, output_map, droog)
        log_samenvatting(nieuw, overgeslagen, fouten, output_map)
        return

    vergadertypen = laad_vergadertypen(naam)
    if haal_en_download_vergaderingen(gs_config, vergadertypen, terugkijk_dagen, output_map, droog):
        return

    # Nog geen provincie bekend waar GS via ORI loopt (alleen Notubiz/iBabs
    # tot nu toe) — als dat ooit nodig blijkt, hier op dezelfde manier
    # toevoegen als in scraper_provincie.py/scraper_gr.py.
    log(f"FOUT: geen bruikbare bron gevonden voor GS van '{naam}'.")
    sys.exit(1)


if __name__ == "__main__":
    main()
