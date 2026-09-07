# Provinciale Staten Toolkit

Een journalistiek onderzoekstool die openbare vergaderstukken van de **Provinciale Staten** van Nederlandse provincies downloadt, plus de **gemeenschappelijke regelingen** (GRs) die binnen elke provincie actief zijn — lokaal, zonder account of API-sleutel.

Dit is een afgeslankte, standalone afsplitsing van de bredere [lokaalbestuur-toolkit](https://github.com/erwinboogert/lokaalbestuur-toolkit) en bevat alleen wat nodig is om Staten- en GR-stukken op te halen: geen gemeenteraad-, waterschap- of veiligheidsregio-scrapers, geen analyse- of zoekindex-tooling.

## Wat wordt gedownload

**Provinciale Staten** (`scraper_provincie.py`) — standaard worden stukken van de **Provinciale Staten**, **Statencommissies** en overige **commissies** opgehaald (dus niet Gedeputeerde Staten, het dagelijks bestuur). 8 van de 12 provincies zijn ontsloten via de Open Raadsinformatie API (ORI), 2 via de Notubiz API, en 1 (Zeeland) via het publieke iBabs-portaal. Alleen Drenthe heeft geen geautomatiseerde bron (eigen verouderd documentsysteem, drenthe.info/dvs/) en moet handmatig worden geraadpleegd.

**Gemeenschappelijke regelingen** (`scraper_gr.py`) — 157 samenwerkingsverbanden tussen gemeenten, verdeeld over alle 12 provincies: omgevingsdiensten, GGD'en, sociale werkvoorzieningsschappen, jeugdzorgregio's, vervoersautoriteiten, afvalinzameling, belastingsamenwerkingen, archieven en meer. Veiligheidsregio's en waterschappen zijn geen onderdeel van deze catalogus (aparte organen met een eigen wettelijk kader). Welke GRs bij een provincie horen wordt bepaald via de deelnemende gemeenten en/of een expliciete provincie-koppeling in `bronnen/regelingen.json`.

**Belangrijk voorbehoud over de GR-catalogus:** de volledige catalogus (166 regelingen bij start, 9 inmiddels verwijderd wegens opheffing/fusie zonder opvolger) is in september 2026 provincie voor provincie handmatig gecontroleerd tegen primaire bronnen (CVDR, organisaties.overheid.nl, organisatiewebsites). 103 van de 157 regelingen zijn **geverifieerd** — bevestigd met een echte, geteste Notubiz- of iBabs-koppeling, of door de vergaderstukkenpagina van de organisatie zelf te lezen. De overige 54 hebben een `reden`-veld dat aangeeft waarom er (nog) geen bevestigd portaal is: geen enkel openbaar portaal vindbaar, stukken alleen verspreid over de iBabs-/Notubiz-sites van individuele deelnemende gemeenten (niet bruikbaar voor deze scraper), geen eigen algemeen bestuur (bedrijfsvoeringsorganisatie/centrumregeling), of een enkel geval waar zelfs het publieke iBabs-portaal zelf de toegang blokkeert. Voor alle niet-geverifieerde regelingen geldt: **bezoek zelf het `website`-veld van de regeling en zoek daar handmatig naar de vergaderstukken** — probeer je het via `scraper_gr.py <naam>` te draaien, dan wijst het script je daar ook expliciet naar. Zie het `_opmerking`-veld in `regelingen.json` voor de volledige uitleg van de `reden`-waarden.

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

Staat een GR niet op `"geverifieerd": true` in `regelingen.json`? Dan heeft `scraper_gr.py` geen automatische bron voor die regeling en stopt hij met een foutmelding die naar het `website`-veld verwijst. Dat is geen bug: bezoek in dat geval die website zelf en zoek daar handmatig naar de vergaderstukken.

## Downloaden én analyseren via een AI

Deze toolkit regelt het downloaden; wat je daarna met de stukken doet, is een
tweede, losstaand proces waarvoor je zelf een AI kiest.

### Downloaden: vraag het in gewone taal

Je hoeft de commando's hierboven niet zelf te onthouden of te typen. Open deze
map met een AI-assistent die bestanden kan lezen en terminal-commando's kan
uitvoeren — zoals [Claude Code](https://claude.ai/code) — en stel je vraag
gewoon in normale taal, bijvoorbeeld:

- "Download de Statenstukken van Zuid-Holland van het afgelopen jaar."
- "Welke gemeenschappelijke regelingen horen bij Gelderland?"
- "Zoek uit of GGD Hart voor Brabant via Notubiz publiceert, en download de
  stukken als dat kan."

De AI vertaalt dit zelf naar de juiste `scraper_provincie.py`- en
`scraper_gr.py`-commando's, controleert de uitvoer, en legt uit wat er
gevonden is. Dat is vooral nuttig bij de GR-catalogus (zie het voorbehoud
hierboven): je kunt de AI eerst een regeling laten verifiëren — bijvoorbeeld
met `--zoek <naam>` en een proefdraai via `--droog` — voordat je hem
daadwerkelijk downloadt.

### Doorzoeken: een tweede, apart proces

Downloaden is niet hetzelfde als doorzoeken. Deze toolkit levert de
vergaderstukken af als PDF's in een mappenstructuur
(`~/Documents/provinciale-staten/...`) en bevat zelf geen zoekindex of
analysefunctie. Voor het daadwerkelijk doorzoeken en analyseren van de inhoud
kies je een AI die met documenten kan werken — dat kan, maar hoeft niet,
dezelfde AI te zijn waarmee je hebt gedownload:

- **Dezelfde terminal-AI (bijv. Claude Code)** — omdat die al toegang heeft
  tot je bestandssysteem, kun je in hetzelfde gesprek doorgaan en vragen
  stellen over de zojuist gedownloade map, bijvoorbeeld: "Wat staat er in de
  laatste vergaderstukken van Omgevingsdienst Utrecht over stikstof?" De AI
  leest de PDF's dan rechtstreeks van schijf, zonder dat je iets hoeft te
  uploaden.
- **NotebookLM (Google)** — upload de gedownloade PDF's (of de hele map) als
  bronnen in een notebook. NotebookLM beantwoordt vragen uitsluitend op basis
  van die documenten en geeft per antwoord een citaat met verwijzing naar de
  bronpagina, wat nuttig is als herleidbaarheid belangrijk is.
- **Claude via de webapp of Cowork (claude.ai)** — upload de PDF's in een
  project of gesprek en stel je vragen daar. Handig als je niet vanaf de
  terminal wilt werken, of als je de analyse wilt delen met anderen binnen
  een team.
- **ChatGPT (OpenAI)** — upload de PDF's rechtstreeks in een gesprek, of, met
  een betaald abonnement, in een "Project" zodat de bestanden voor meerdere
  gesprekken beschikbaar blijven. ChatGPT leest de inhoud binnen dat gesprek,
  maar geeft — anders dan NotebookLM — niet standaard een citaat met
  paginaverwijzing per antwoord; vraag daar expliciet om als herleidbaarheid
  belangrijk is. Bij een groot aantal documenten werkt het prettiger om per
  dossier of onderwerp een apart gesprek of project te openen dan alles in
  één keer te uploaden.

In alle gevallen geldt: hoe specifieker de vraag, hoe bruikbaarder het
antwoord. Concrete voorbeelden, aansluitend bij dossiers die op het moment
van schrijven in deze drie provincies spelen:

- **Groningen** — "Welke argumenten gebruiken Provinciale Staten in hun
  moties tegen de komst van een kerncentrale bij de Eemshaven, en wat is de
  reactie van Gedeputeerde Staten daarop?"
- **Zeeland** — "Welke partijen stemden vóór en tegen de motie tegen
  kerncentrales in de Paulinapolder, en welke alternatieve locaties worden
  in de vergaderstukken genoemd?"
- **Utrecht** — "Wat betekent de vernietiging van het Tracébesluit Ring
  Utrecht (A27/A12) voor de woningbouwplannen in de regio, volgens de meest
  recente Statenstukken?"

Dit soort vragen werkt beter dan "vat dit samen": ze vragen om een concreet
feit, verband of afweging dat in de brontekst te herleiden is.

## Configuratie

De catalogus van provincies staat in `bronnen/provincies.json`: naam, brontype (ORI-index of Notubiz-ID), gemeentenlijst en eventueel afwijkende vergadertypen.

De catalogus van gemeenschappelijke regelingen staat in `bronnen/regelingen.json`: naam, deelnemende gemeenten, provincie(s) en brontype (Notubiz-ID, iBabs-sitename, ORI-index, of een website als er geen geautomatiseerde bron is). Ontbreekt een GR die je zoekt, of wil je een bron bevestigen? Zoek de organisatie op met `--zoek` of vul `regelingen.json` handmatig aan.

Wil je de documenten ergens anders opslaan dan `~/Documents/provinciale-staten/`? Maak een `config.local.json` aan in de projectmap:

```json
{
  "data_map": "/pad/naar/eigen/map"
}
```

### Hoe iBabs-regelingen werken: het publieke portaal, niet de SOAP-API

Regelingen met een `ibabs_naam` worden gescraped via het publieke, ongeauthenticeerde
webportaal op `https://<sitename>.bestuurlijkeinformatie.nl/` — hetzelfde portaal
waar burgers vergaderstukken op inzien. `scraper_gr.py` haalt daar de
vergadercategorieën, de jaaroverzichten per categorie en de documentenlijst per
vergadering van op, en downloadt de PDF's rechtstreeks.

Dit is bewust *niet* de officiële iBabs SOAP-API (Public.svc): die vereist
per-IP whitelisting door iBabs zelf (foutmeldingen als `Invalid site!` of
`IPaddress X has no access to site Y!`), wat in de praktijk voor onafhankelijke
projecten zelden rond te krijgen is. Het publieke portaal heeft die beperking
niet en is bovendien precies de bron die voor *openbare* stukken bedoeld is.

Een enkele organisatie blokkeert ook het publieke portaal zelf (`Geen toegang
tot iBabsOnline!` — zie `reden: "ibabs-portaal-geen-toegang"` in
`regelingen.json`); daar is deze aanpak niet tegen bestand.

## Bron

Vergaderstukken van Provinciale Staten zijn openbare overheidsinformatie. Deze tool haalt ze op via de publieke [Open Raadsinformatie API](https://openraadsinformatie.nl) (Open State Foundation), de publieke Notubiz-API, en het publieke iBabs-portaal (bestuurlijkeinformatie.nl) — dezelfde bronnen die de provincies zelf gebruiken om hun stukken te publiceren.

## Licentie

MIT — zie `LICENSE`.
