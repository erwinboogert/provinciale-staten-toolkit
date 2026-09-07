# Digitale ontsluiting per provincie: Provinciale Staten, Gedeputeerde Staten en gemeenschappelijke regelingen samengevat

**Peildatum:** 7 september 2026
**Bron:** [`bronnen/provincies.json`](../bronnen/provincies.json) en [`bronnen/regelingen.json`](../bronnen/regelingen.json) in deze repository, plus het eerdere rapport [`gr-transparantie.md`](gr-transparantie.md)
**Scope:** alle 12 Nederlandse provincies, over de drie bestuurslagen die deze toolkit ontsluit: Provinciale Staten (PS), Gedeputeerde Staten (GS) en de gemeenschappelijke regelingen (GR's) die aan elke provincie gekoppeld zijn.

---

## Waarom dit relevant is

De twee eerdere onderzoeksrondes in dit project — het bouwen van `scraper_provincie.py`/`scraper_gs.py` en het verifiëren van de GR-catalogus — leverden allebei losse, orgaan-specifieke bevindingen op. Dit rapport zet ze naast elkaar per provincie, met percentages die onderling vergelijkbaar zijn. Dat maakt in één oogopslag zichtbaar of een provincie structureel goed of slecht digitaal ontsloten is, of dat het per bestuurslaag sterk verschilt — wat op zichzelf ook een bevinding is.

## Methode

Voor elke provincie zijn drie percentages berekend:

- **PS%** — binair: 100% als er een bevestigde, werkende geautomatiseerde bron is voor Provinciale Staten, 0% als niet. Dit is voor 11 van de 12 provincies het geval; alleen Drenthe heeft geen geautomatiseerde bron.
- **GS%** — binair: 100% als GS-besluiten via een bevestigde, werkende bron op te halen zijn, 0% als niet. Dit is voor 11 van de 12 provincies het geval; alleen Overijssel niet (zie hieronder waarom dat een ander soort probleem is dan Drenthe's PS-omissie).
- **GR%** — géén binair getal, maar het percentage van de aan die provincie gekoppelde gemeenschappelijke regelingen waarvoor een werkend vergaderarchief is bevestigd (overgenomen uit [`gr-transparantie.md`](gr-transparantie.md)).
- **Gemiddelde** — het ongewogen gemiddelde van de drie bovenstaande percentages. Dit is een simplificatie (zie de kanttekeningen onderaan) en bedoeld als kompas, niet als exacte maatstaf.

Belangrijk: PS% en GS% meten **of onze scraper een bevestigde bron heeft**, niet rechtstreeks "is dit orgaan transparant". Voor GS geldt bovendien een aanvullende nuance die niet in het percentage zit: "niet automatiseerbaar" is niet hetzelfde als "niet openbaar" (zie de Overijssel-toelichting).

## Overzicht per provincie

| Provincie | PS | GS | GR | Gemiddelde |
|---|---:|---:|---:|---:|
| Zeeland | 100% | 100% | 100% | **100%** |
| Gelderland | 100% | 100% | 90% | **97%** |
| Flevoland | 100% | 100% | 83% | **94%** |
| Fryslân | 100% | 100% | 83% | **94%** |
| Utrecht | 100% | 100% | 64% | **88%** |
| Limburg | 100% | 100% | 58% | **86%** |
| Zuid-Holland | 100% | 100% | 58% | **86%** |
| Noord-Brabant | 100% | 100% | 57% | **86%** |
| Noord-Holland | 100% | 100% | 56% | **85%** |
| Groningen | 100% | 100% | 50% | **83%** |
| **Overijssel** | 100% | **0%** | 71% | **57%** |
| **Drenthe** | **0%** | 100% | 40% | **47%** |

Drenthe en Overijssel vormen samen de staart van de ranglijst — precies de twee provincies waar dit tijdens het bouwen van de scrapers ook al opvielen als lastige gevallen. Maar de aard van hun probleem is fundamenteel verschillend, en dat verdient een aparte toelichting.

## Drenthe (PS: 0%) — een echt ontsluitingsprobleem

Provinciale Staten van Drenthe publiceert vergaderstukken op een eigen, verouderd documentsysteem (`drenthe.info/dvs/`) zonder herkenbaar, geautomatiseerd patroon — niet via ORI, Notubiz of een publiek iBabs-portaal zoals alle andere 11 provincies. Dit is de enige provincie in de hele catalogus waarvoor `scraper_provincie.py` geen bron heeft; vergaderstukken moeten hier letterlijk handmatig worden opgezocht. Dat is een genuine tekortkoming in digitale ontsluiting van het kernorgaan van de provincie, niet alleen een obstakel voor deze toolkit.

Opvallend: Drenthe's **GS** scoort wél 100% — besluitenlijsten staan gewoon als PDF-index op de eigen provinciewebsite. Dezelfde provincie ontsluit haar dagelijks bestuur dus beter dan haar volksvertegenwoordiging, wat een ongebruikelijke volgorde is (doorgaans krijgt PS, als het meest zichtbare orgaan, de meeste aandacht).

## Overijssel (GS: 0%) — geblokkeerd voor bots, niet voor burgers

Overijssel's GS-besluitenlijsten staan volledig openbaar op `overijssel.notubiz.nl` — bevestigd met een echte browser: geen inlog nodig, gewoon doorbladerbaar en leesbaar. Het probleem is uitsluitend dat het hele domein achter een Cloudflare-botdetectie zit, die elk geautomatiseerd verzoek blokkeert (ook directe PDF-links). Deze toolkit omzeilt dat bewust niet, ook niet voor een legitiem journalistiek doel — dus blijft de GS van Overijssel voor déze scraper op 0% staan.

Dat is een wezenlijk ander soort "0%" dan Drenthe's PS-omissie: een burger met een gewone browser kan de Overijsselse GS-besluiten gewoon lezen; het is alleen niet schaalbaar te automatiseren. Het percentage in de tabel maakt dat onderscheid niet zichtbaar — vandaar deze toelichting.

## Kanttekeningen bij de methode

- **PS% en GS% zijn binair, GR% is een gradient.** Het ongewogen gemiddelde van twee alles-of-niets-indicatoren en één percentage is een bewuste vereenvoudiging. Een provincie met 11 van de 12 GR's geverifigeerd en een net ontbrekende PS-bron eindigt in dit model lager dan de nuance eigenlijk rechtvaardigt.
- **Dit meet scraper-dekking, niet per se overheidsgedrag.** Zoals bij het GR-rapport al aangegeven: een 0% of lager percentage betekent dat wíj, binnen een redelijke onderzoeksinspanning, geen bevestigde geautomatiseerde bron konden vinden — niet per se dat de overheid informatie achterhoudt. Overijssel is daar het duidelijkste voorbeeld van.
- **Momentopname.** Portalen migreren, feeds vallen stil zonder foutmelding (zoals eerder gebeurde met Noord-Brabant's Notubiz-koppeling), en Cloudflare-configuraties kunnen wijzigen. Zie het voorgestelde kwartaal-ritme voor herverificatie.
- **GR% is een gewogen gemiddelde over meerdere organisaties, PS%/GS% over precies één bron.** Een provincie met weinig gekoppelde GR's (bijv. Zeeland met 6) laat een enkele misser zwaarder wegen dan een provincie met veel GR's (bijv. Noord-Brabant met 23).
- **Brondata is zelf te verifiëren:** het volledige detail per provincie (backend, indexpagina, laatste verificatiedatum, toelichting) staat in de geneste `gs`-sleutel van [`bronnen/provincies.json`](../bronnen/provincies.json); de GR-cijfers komen rechtstreeks uit [`gr-transparantie.md`](gr-transparantie.md).
