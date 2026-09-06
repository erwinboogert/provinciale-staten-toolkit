"""
Gedeelde API-functies voor de provinciale-staten-toolkit.

Bevat alle herbruikbare logica voor:
  - Open Raadsinformatie (ORI) API
  - Notubiz API
  - iBabs Publieksportaal (HTML-scraping van bestuurlijkeinformatie.nl)
  - Bestandsnamen, downloads en logging
  - Configuratie (config.local.json)
"""

import json
import logging
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path


# ── Configuratie ─────────────────────────────────────────────────────────────

TOOLKIT_MAP = Path(__file__).parent

_config_pad = TOOLKIT_MAP / "config.local.json"
_data_map: Path | None = None
if _config_pad.exists():
    try:
        _cfg = json.loads(_config_pad.read_text(encoding="utf-8"))
        if "data_map" in _cfg:
            _data_map = Path(_cfg["data_map"]).expanduser()
    except Exception:
        pass

DATA_MAP = _data_map  # None als geen config.local.json; anders het geconfigureerde pad
OUTPUT_BASIS = _data_map if _data_map else (Path.home() / "Documents" / "provinciale-staten")
BRONNEN_MAP = TOOLKIT_MAP / "bronnen"


# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging(output_map: Path):
    """Configureer logging naar stdout en een logbestand in output_map/logs/."""
    log_map = output_map / "logs"
    log_map.mkdir(parents=True, exist_ok=True)
    logbestand = log_map / "scraper.log"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logbestand, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M",
        handlers=handlers,
    )


def log(msg):
    logging.info(msg)


# ── Vergaderfilter ───────────────────────────────────────────────────────────

# Sommige organisaties noemen vergaderingen bij hun afkorting in plaats van de
# volledige naam (bijv. "AB-vergadering OPENBAAR" i.p.v. "algemeen bestuur").
# Zonder deze afkortingen als los woord (\b) te herkennen, filtert
# wil_vergadering zulke — verder identieke — vergaderingen stil weg.
_VERGADERTYPE_AFKORTINGEN = {
    "algemeen bestuur": r"\bab\b",
    "dagelijks bestuur": r"\bdb\b",
    "portefeuillehoudersoverleg": r"\bpho\b",
}


def wil_vergadering(naam: str, vergadertypen: dict[str, bool],
                    skip_vervallen: bool = True) -> bool:
    """Controleer of een vergadering gedownload moet worden op basis van type."""
    naam_lower = naam.lower()
    if skip_vervallen and "vervallen" in naam_lower:
        return False
    for sleutel, actief in vergadertypen.items():
        if not actief:
            continue
        if sleutel in naam_lower:
            return True
        afkorting = _VERGADERTYPE_AFKORTINGEN.get(sleutel)
        if afkorting and re.search(afkorting, naam_lower):
            return True
    return False


# ── Bestandsnaam en download ─────────────────────────────────────────────────

def veilige_naam(tekst: str) -> str:
    """Maak een veilige bestandsnaam van een willekeurige tekst."""
    tekst = tekst.lower()
    tekst = re.sub(r"[^\w\s-]", "", tekst)
    tekst = re.sub(r"\s+", "-", tekst.strip())
    tekst = re.sub(r"-+", "-", tekst)
    return tekst[:80]


def download(url: str, bestemming: Path) -> int:
    """Download een bestand en geef de grootte in bytes terug."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    bestemming.write_bytes(data)
    return len(data)


# ── ORI API (Open Raadsinformatie) ───────────────────────────────────────────

API_BASE = "https://api.openraadsinformatie.nl/v1/elastic"


def api_search(index: str, query: dict) -> list:
    """Voer een Elasticsearch-zoekopdracht uit op een ORI-index."""
    url = f"{API_BASE}/{index}/_search"
    data = json.dumps(query).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("hits", {}).get("hits", [])


def alle_indices() -> list[str]:
    """Haal alle beschikbare ORI-indices op."""
    req = urllib.request.Request(
        f"{API_BASE}/_cat/indices?h=index&format=json",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return [row["index"] for row in json.loads(r.read())]


def haal_vergaderingen_ori(index: str, vergadertypen: dict[str, bool],
                           max_vergaderingen: int = 50,
                           vanaf: str | None = None) -> list[dict]:
    """Haal vergaderingen op uit een ORI-index. Geeft [{id, naam, datum}]."""
    if vanaf:
        query = {
            "bool": {
                "must": [
                    {"term": {"@type": "Meeting"}},
                    {"range": {"start_date": {"gte": vanaf + "T00:00:00Z"}}},
                ]
            }
        }
        size = 200
    else:
        query = {"term": {"@type": "Meeting"}}
        size = max_vergaderingen

    hits = api_search(index, {
        "query": query,
        "sort": [{"start_date": {"order": "desc"}}],
        "size": size,
        "_source": ["name", "start_date"],
    })
    return [
        {
            "id": h["_id"],
            "naam": h["_source"].get("name", ""),
            "datum": h["_source"].get("start_date", "")[:10],
        }
        for h in hits
        if wil_vergadering(h["_source"].get("name", ""), vergadertypen)
    ]


def haal_documenten_ori(index: str, vergadering_id: str) -> list[dict]:
    """Haal documenten op voor een ORI-vergadering. Geeft [{naam, url}]."""
    agenda_hits = api_search(index, {
        "query": {"term": {"parent": vergadering_id}},
        "size": 100,
        "_source": ["attachment"],
    })
    attachment_ids = []
    meeting_hits = api_search(index, {"query": {"ids": {"values": [vergadering_id]}}, "_source": ["attachment"]})
    if meeting_hits:
        val = meeting_hits[0]["_source"].get("attachment", [])
        attachment_ids.extend(val if isinstance(val, list) else [val])

    for hit in agenda_hits:
        val = hit["_source"].get("attachment", []); attachment_ids.extend(val if isinstance(val, list) else [val])
    if not attachment_ids:
        return []

    media_hits = api_search(index, {
        "query": {"ids": {"values": attachment_ids}},
        "size": 500,
        "_source": ["name", "url", "@type"],
    })
    return [
        {"naam": h["_source"].get("name", "").strip(), "url": h["_source"].get("url", "")}
        for h in media_hits
        if h["_source"].get("@type") == "MediaObject"
        and h["_source"].get("url")
        and h["_source"].get("name", "").strip()
    ]


# ── Notubiz API ──────────────────────────────────────────────────────────────

NOTUBIZ_API = "https://api.notubiz.nl"
NOTUBIZ_VERSION = "1.17.0"


def notubiz_verzoek(endpoint: str) -> dict:
    """Doe een GET-verzoek naar de Notubiz API en geef het JSON-resultaat terug."""
    sep = "&" if "?" in endpoint else "?"
    url = f"{NOTUBIZ_API}/{endpoint}{sep}format=json&version={NOTUBIZ_VERSION}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def haal_vergaderingen_notubiz(org_id: int, vergadertypen: dict[str, bool] | None = None,
                                terugkijk_dagen: int = 730) -> list[dict]:
    """Haal vergaderingen op via de Notubiz API. Geeft [{id, naam, datum}].

    Als vergadertypen None is, worden alle vergaderingen meegenomen.
    """
    date_to = datetime.now().strftime("%Y-%m-%d 23:59:59")
    date_from = (datetime.now() - timedelta(days=terugkijk_dagen)).strftime("%Y-%m-%d 00:00:00")

    vergaderingen = []
    page = 1
    while True:
        data = notubiz_verzoek(
            f"events?organisation_id={org_id}"
            f"&date_from={date_from.replace(' ', '+')}"
            f"&date_to={date_to.replace(' ', '+')}"
            f"&page={page}"
        )
        for event in data.get("events", []):
            if event.get("permission_group") != "public":
                continue
            if event.get("canceled") or event.get("inactive"):
                continue

            datum = ""
            for planning in event.get("plannings", []):
                datum = planning.get("start_date", "")[:10]
                if datum:
                    break
            if not datum:
                datum = event.get("creation_date", "")[:10]

            naam = ""
            for attr in event.get("attributes", []):
                naam = attr.get("value", "").strip()
                if naam:
                    break
            if not naam:
                naam = f"vergadering-{event['id']}"

            if vergadertypen is not None and not wil_vergadering(naam, vergadertypen):
                continue

            vergaderingen.append({
                "id": str(event["id"]),
                "naam": naam,
                "datum": datum,
            })

        if not data.get("pagination", {}).get("has_more_pages"):
            break
        page += 1

    return vergaderingen


def haal_documenten_notubiz(meeting_id: str) -> list[dict]:
    """Haal documenten op voor een Notubiz-vergadering. Geeft [{naam, url}]."""
    data = notubiz_verzoek(f"events/meetings/{meeting_id}")
    meeting = data.get("meeting", {})
    documenten = []

    def verwerk_doc(doc: dict):
        if doc.get("confidential"):
            return
        url = doc.get("url", "")
        if not url:
            return
        bestandsnaam = ""
        for versie in doc.get("versions", []):
            if versie.get("mime_type") == "application/pdf":
                bestandsnaam = versie.get("file_name", "")
                break
        if not bestandsnaam:
            bestandsnaam = doc.get("title", f"document-{doc.get('id', '')}")
            if not bestandsnaam.lower().endswith(".pdf"):
                bestandsnaam += ".pdf"
        documenten.append({"naam": bestandsnaam, "url": url})

    for doc in meeting.get("documents", []):
        verwerk_doc(doc)
    for item in meeting.get("agenda_items", []):
        for doc in item.get("documents", []):
            verwerk_doc(doc)

    return documenten


# ── iBabs Publieksportaal (HTML) ─────────────────────────────────────────────
#
# iBabs biedt naast de SOAP-API (Public.svc, vereist per-IP whitelisting door
# iBabs zelf) ook een publiek, ongeauthenticeerd webportaal op
# https://<sitename>.bestuurlijkeinformatie.nl/ — hetzelfde portaal waar
# burgers vergaderstukken op inzien. Dat portaal is een gewone server-side
# gerenderde site zonder inlog, dus we scrapen die HTML direct in plaats van
# de SOAP-API aan te roepen: geen whitelisting nodig, en het is bovendien
# precies de bron die voor *openbare* stukken bedoeld is.

IBABS_PORTAAL = "https://{sitename}.bestuurlijkeinformatie.nl"

_DUTCH_MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}


def _ibabs_get(sitename: str, pad: str) -> str:
    """Haal een pagina op van het publieke iBabs-portaal van een organisatie."""
    url = f"{IBABS_PORTAAL.format(sitename=sitename)}{pad}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def haal_categorieen_ibabs(sitename: str) -> dict[str, str]:
    """Geeft {agendatypeId: naam} van alle vergadercategorieën op het portaal."""
    html = _ibabs_get(sitename, "/Calendar")
    return dict(re.findall(r'href="/Calendar/OpenCategory/(\d+)"[^>]*>([^<]+)</a>', html))


def haal_vergaderingen_ibabs(sitename: str, vergadertypen: dict[str, bool],
                              terugkijk_dagen: int = 730) -> list[dict]:
    """Haal vergaderingen + documenten op via het publieke iBabs-portaal.

    Geeft [{id, naam, datum, documenten: [{naam, url}]}].
    """
    try:
        categorieen = haal_categorieen_ibabs(sitename)
    except Exception as e:
        log(f"  ! iBabs-portaal onbereikbaar voor '{sitename}': {e}")
        return []

    relevante_categorieen = {
        cat_id: naam.strip() for cat_id, naam in categorieen.items()
        if wil_vergadering(naam, vergadertypen)
    }
    if not relevante_categorieen:
        return []

    vandaag = datetime.now()
    vroegste = vandaag - timedelta(days=terugkijk_dagen)

    vergaderingen = []
    for cat_id, cat_naam in relevante_categorieen.items():
        for jaar in range(vroegste.year, vandaag.year + 1):
            try:
                jaar_html = _ibabs_get(
                    sitename, f"/Agenda/RetrieveAgendasForYear?agendatypeId={cat_id}&year={jaar}")
            except Exception as e:
                log(f"  ! iBabs-fout bij ophalen {jaar} voor '{sitename}': {e}")
                continue

            for guid, dag, maand, jaartal in re.findall(
                r'href="/Agenda/Index/([0-9a-f-]{36})"[^>]*>\s*'
                r'<div class="agenda-link-title">\w+ (\d{1,2}) ([a-zA-Zéï]+) '
                r'<span class="sr-only">(\d{4})</span></div>',
                jaar_html,
            ):
                maand_nr = _DUTCH_MAANDEN.get(maand.lower())
                if not maand_nr:
                    continue
                try:
                    datum_obj = datetime(int(jaartal), maand_nr, int(dag))
                except ValueError:
                    continue
                if not (vroegste <= datum_obj <= vandaag):
                    continue

                try:
                    detail_html = _ibabs_get(sitename, f"/Agenda/Index/{guid}")
                except Exception as e:
                    log(f"  ! iBabs-fout bij ophalen vergadering {guid} voor '{sitename}': {e}")
                    continue

                documenten = []
                for doc_id, ruwe_naam in re.findall(
                    rf'href="/Agenda/Document/{re.escape(guid)}\?documentId='
                    r'([0-9a-f-]{36})[^"]*"[^>]*>(?:\s*<span[^>]*></span>)?\s*(.*?)\s*<span class="badge',
                    detail_html, re.DOTALL,
                ):
                    naam = " ".join(re.sub(r"<[^>]+>", "", ruwe_naam).split())
                    if not naam:
                        naam = f"document-{doc_id}"
                    if not naam.lower().endswith(".pdf"):
                        naam += ".pdf"
                    url = (f"{IBABS_PORTAAL.format(sitename=sitename)}"
                           f"/Document/LoadAgendaDocument/{doc_id}?agendaId={guid}")
                    documenten.append({"naam": naam, "url": url})

                vergaderingen.append({
                    "id": guid,
                    "naam": cat_naam,
                    "datum": datum_obj.strftime("%Y-%m-%d"),
                    "documenten": documenten,
                })

    return vergaderingen


# ── Download-lus (gedeeld patroon) ──────────────────────────────────────────

def download_vergaderingen_ori(vergaderingen: list[dict], index: str,
                                output_map: Path, droog: bool = False) -> tuple[int, int, int]:
    """Download documenten voor ORI-vergaderingen. Geeft (nieuw, overgeslagen, fouten)."""
    totaal_nieuw = totaal_overgeslagen = totaal_fout = 0

    for verg in vergaderingen:
        docs = haal_documenten_ori(index, verg["id"])
        if not docs:
            continue

        doelmap = output_map / veilige_naam(verg["naam"]) / verg["datum"]
        nieuwe_docs = [d for d in docs
                       if not (doelmap / (veilige_naam(d["naam"]) + ".pdf")).exists()]

        if not nieuwe_docs:
            totaal_overgeslagen += len(docs)
            continue

        log(f"\n  {verg['naam']} ({verg['datum']}) — {len(nieuwe_docs)} nieuw van {len(docs)}")

        if not droog:
            doelmap.mkdir(parents=True, exist_ok=True)

        for doc in docs:
            bestandsnaam = veilige_naam(doc["naam"]) + ".pdf"
            bestemming = doelmap / bestandsnaam

            if bestemming.exists():
                totaal_overgeslagen += 1
                continue

            if droog:
                log(f"    [DROOG] {bestandsnaam}")
                totaal_nieuw += 1
                continue

            try:
                grootte = download(doc["url"], bestemming)
                log(f"    + {bestandsnaam} ({grootte / 1024:.0f} KB)")
                totaal_nieuw += 1
            except Exception as e:
                log(f"    ! FOUT: {bestandsnaam} — {e}")
                totaal_fout += 1

    return totaal_nieuw, totaal_overgeslagen, totaal_fout


def download_vergaderingen_notubiz(vergaderingen: list[dict],
                                    output_map: Path, droog: bool = False) -> tuple[int, int, int]:
    """Download documenten voor Notubiz-vergaderingen. Geeft (nieuw, overgeslagen, fouten)."""
    totaal_nieuw = totaal_overgeslagen = totaal_fout = 0

    for verg in vergaderingen:
        docs = haal_documenten_notubiz(verg["id"])
        if not docs:
            continue

        doelmap = output_map / veilige_naam(verg["naam"]) / verg["datum"]
        nieuwe_docs = [d for d in docs if not (doelmap / d["naam"]).exists()]

        if not nieuwe_docs:
            totaal_overgeslagen += len(docs)
            continue

        log(f"\n  {verg['naam']} ({verg['datum']}) — {len(nieuwe_docs)} nieuw van {len(docs)}")

        if not droog:
            doelmap.mkdir(parents=True, exist_ok=True)

        for doc in docs:
            bestemming = doelmap / doc["naam"]
            if bestemming.exists():
                totaal_overgeslagen += 1
                continue
            if droog:
                log(f"    [DROOG] {doc['naam']}")
                totaal_nieuw += 1
                continue
            try:
                grootte = download(doc["url"], bestemming)
                log(f"    + {doc['naam']} ({grootte / 1024:.0f} KB)")
                totaal_nieuw += 1
            except Exception as e:
                log(f"    ! FOUT: {doc['naam']} — {e}")
                totaal_fout += 1

    return totaal_nieuw, totaal_overgeslagen, totaal_fout


def download_vergaderingen_ibabs(vergaderingen: list[dict],
                                  output_map: Path, droog: bool = False) -> tuple[int, int, int]:
    """Download documenten voor iBabs-vergaderingen. Geeft (nieuw, overgeslagen, fouten)."""
    totaal_nieuw = totaal_overgeslagen = totaal_fout = 0

    for verg in vergaderingen:
        docs = verg["documenten"]
        if not docs:
            continue

        doelmap = output_map / veilige_naam(verg["naam"]) / verg["datum"]
        nieuwe_docs = [d for d in docs
                       if not (doelmap / (veilige_naam(d["naam"]) + ".pdf")).exists()]

        if not nieuwe_docs:
            totaal_overgeslagen += len(docs)
            continue

        log(f"\n  {verg['naam']} ({verg['datum']}) — {len(nieuwe_docs)} nieuw van {len(docs)}")

        if not droog:
            doelmap.mkdir(parents=True, exist_ok=True)

        for doc in docs:
            bestandsnaam = veilige_naam(doc["naam"]) + ".pdf"
            bestemming = doelmap / bestandsnaam

            if bestemming.exists():
                totaal_overgeslagen += 1
                continue

            if droog:
                log(f"    [DROOG] {bestandsnaam}")
                totaal_nieuw += 1
                continue

            try:
                grootte = download(doc["url"], bestemming)
                log(f"    + {bestandsnaam} ({grootte / 1024:.0f} KB)")
                totaal_nieuw += 1
            except Exception as e:
                log(f"    ! FOUT: {bestandsnaam} — {e}")
                totaal_fout += 1

    return totaal_nieuw, totaal_overgeslagen, totaal_fout


def parse_jaren_arg(standaard_dagen: int = 730) -> tuple[str | None, int]:
    """Lees --jaren N uit sys.argv. Geeft (vanaf_datum, terugkijk_dagen).

    vanaf_datum: ISO-datumstring voor ORI-queries (of None als niet opgegeven).
    terugkijk_dagen: aantal dagen terug, bruikbaar voor Notubiz.
    Standaard: standaard_dagen (default 730 = 2 jaar).
    """
    argv = sys.argv[1:]
    if "--jaren" not in argv:
        return None, standaard_dagen

    idx = argv.index("--jaren")
    if idx + 1 >= len(argv):
        return None, standaard_dagen

    try:
        jaren = float(argv[idx + 1])
        dagen = int(jaren * 365)
        vanaf = (datetime.now() - timedelta(days=dagen)).strftime("%Y-%m-%d")
        return vanaf, dagen
    except ValueError:
        return None, standaard_dagen


def log_samenvatting(nieuw: int, overgeslagen: int, fouten: int, output_map: Path):
    """Print een standaard-samenvatting na het downloaden."""
    log("")
    log("─" * 60)
    log(f"Nieuw gedownload : {nieuw}")
    log(f"Al aanwezig      : {overgeslagen}")
    log(f"Fouten           : {fouten}")
    log(f"Opgeslagen in    : {output_map}")
    log("─" * 60)
