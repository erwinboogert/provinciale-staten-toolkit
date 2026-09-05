# Provinciale Staten Toolkit

Een journalistiek onderzoekstool die openbare vergaderstukken van de **Provinciale Staten** van Nederlandse provincies downloadt, plus de **gemeenschappelijke regelingen** (GRs) die binnen elke provincie actief zijn — lokaal, zonder account of API-sleutel.

Dit is een afgeslankte, standalone afsplitsing van de bredere [lokaalbestuur-toolkit](https://github.com/erwinboogert/lokaalbestuur-toolkit) en bevat alleen wat nodig is om Staten- en GR-stukken op te halen: geen gemeenteraad-, waterschap- of veiligheidsregio-scrapers, geen analyse- of zoekindex-tooling.

## Wat wordt gedownload

**Provinciale Staten** (`scraper_provincie.py`) — standaard worden stukken van de **Provinciale Staten**, **Statencommissies** en overige **commissies** opgehaald (dus niet Gedeputeerde Staten, het dagelijks bestuur). 8 van de 12 provincies zijn ontsloten via de Open Raadsinformatie API (ORI), 2 via de Notubiz API. Drenthe en Zeeland hebben geen geautomatiseerde bron en moeten handmatig worden geraadpleegd.

**Gemeenschappelijke regelingen** (`scraper_gr.py`) — 166 samenwerkingsverbanden tussen gemeenten, verdeeld over alle 12 provincies: omgevingsdiensten, GGD'en, sociale werkvoorzieningsschappen, jeugdzorgregio's, vervoersautoriteiten, afvalinzameling, belastingsamenwerkingen, archieven en meer. Veiligheidsregio's en waterschappen zijn geen onderdeel van deze catalogus (aparte organen met een eigen wettelijk kader). Welke GRs bij een provincie horen wordt bepaald via de deelnemende gemeenten en/of een expliciete provincie-koppeling in `bronnen/regelingen.json`.

**Belangrijk voorbehoud over de GR-catalogus:** 9 regelingen (de oorspronkelijke Rotterdam/Zeeland/Foodvalley-selectie) zijn **geverifieerd** — met een echte, geteste Notubiz-koppeling. De overige ~157 zijn samengesteld via AI-onderzoek op basis van CVDR/overheid.nl-vindplaatsen en organisatiewebsites, **zonder dat de brontekst zelf kon worden ingezien** tijdens dat onderzoek. Namen, deelnemende gemeenten en vooral eventuele bronvermeldingen bij die regelingen zijn dus niet geverifieerd: controleer een regeling voordat je erop vertrouwt, en gebruik `--zoek <naam>` om een Notubiz-ID zelf te bevestigen. Zie het `_opmerking`-veld in `regelingen.json` en het `geverifieerd`-veld per regeling.

## Installatie

```bash
git clone https://github.com/erwinboogert/provinciale-staten-toolkit.git
cd provinciale-staten-toolkit
```

Vereist alleen Python 3.10 of hoger — geen externe bibliotheken.

## Gebruik

**Provinciale Staten:**

```bash
python3 scraper_provincie.py --lijst                # toon geconfigureerde provincies
python3 scraper_provincie.py zuid-holland            # download Statenstukken
python3 scraper_provincie.py zuid-holland --droog    # toon wat er gedownload zou worden
python3 scraper_provincie.py zuid-holland --jaren 1  # alleen het afgelopen jaar
python3 scraper_provincie.py --lijst-ori             # toon alle provincies in de ORI API
```

Na het downloaden van een provincie toont de scraper meteen welke gemeenschappelijke regelingen daar bij horen.

**Gemeenschappelijke regelingen:**

```bash
python3 scraper_gr.py --provincie zuid-holland   # toon GRs die bij deze provincie horen
python3 scraper_gr.py --lijst                    # toon alle geconfigureerde GRs
python3 scraper_gr.py nieuw-reijerwaard          # download vergaderstukken van een GR
python3 scraper_gr.py nieuw-reijerwaard --droog  # toon wat er gedownload zou worden
python3 scraper_gr.py --zoek jeugdhulp           # zoek een GR-organisatie in Notubiz
```

Documenten komen terecht in `~/Documents/provinciale-staten/provincies/<naam>/` en `~/Documents/provinciale-staten/regelingen/<naam>/`.

## Configuratie

De catalogus van provincies staat in `bronnen/provincies.json`: naam, brontype (ORI-index of Notubiz-ID), gemeentenlijst en eventueel afwijkende vergadertypen.

De catalogus van gemeenschappelijke regelingen staat in `bronnen/regelingen.json`: naam, deelnemende gemeenten, provincie(s) en brontype (Notubiz-ID, iBabs-sitename, ORI-index, of een website als er geen geautomatiseerde bron is). Ontbreekt een GR die je zoekt, of wil je een bron bevestigen? Zoek de organisatie op met `--zoek` of vul `regelingen.json` handmatig aan.

Wil je de documenten ergens anders opslaan dan `~/Documents/provinciale-staten/`? Maak een `config.local.json` aan in de projectmap:

```json
{
  "data_map": "/pad/naar/eigen/map"
}
```

## Bron

Vergaderstukken van Provinciale Staten zijn openbare overheidsinformatie. Deze tool haalt ze op via de publieke [Open Raadsinformatie API](https://openraadsinformatie.nl) (Open State Foundation) en de publieke Notubiz-API — dezelfde bronnen die de provincies zelf gebruiken om hun stukken te publiceren.

## Licentie

MIT — zie `LICENSE`.
