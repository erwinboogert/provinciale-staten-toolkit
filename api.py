"""
Gedeelde API-functies voor de provinciale-staten-toolkit.

Bevat alle herbruikbare logica voor:
  - Open Raadsinformatie (ORI) API
  - Notubiz API
  - iBabs SOAP API
  - Bestandsnamen, downloads en logging
  - Configuratie (config.local.json)
"""

import json
import logging
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
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


# ── iBabs SOAP API ───────────────────────────────────────────────────────────

IBABS_ENDPOINT = "https://wcf.ibabs.eu/api/Public.svc"
IBABS_NS = "http://tempuri.org/"
IBABS_BASE_NS = "http://schemas.datacontract.org/2004/07/iBabsWCFObjects.Base"


class IbabsFout(Exception):
    """De iBabs SOAP API gaf een Status=ERR terug (bijv. ongeldige sitename of IP-blokkade).

    Een "Invalid site!" of "IPaddress X has no access to site Y!"-melding
    betekent meestal dat dit IP-adres nog niet is whitelist bij iBabs — dit
    geldt ook voor overduidelijk juiste sitenamen. Zie het README
    ("Bekende beperking: iBabs vereist IP-whitelisting") voor hoe je dat
    aanvraagt bij support@ibabs.eu.
    """


def ibabs_soap(methode: str, body_xml: str) -> ET.Element:
    """Doe een SOAP-verzoek naar de iBabs API en geef het root-element terug.

    De iBabs API antwoordt met HTTP 200 zelfs bij een fout (ongeldige sitename,
    IP niet toegestaan, etc.) — de fout zit in <Status>ERR</Status> /
    <Message> binnen de body. Zonder expliciete check hierop lijkt zo'n fout
    identiek aan "geen resultaten gevonden". Deze functie zet die fout om in
    een IbabsFout zodat aanroepers hem niet per ongeluk als lege lijst lezen.
    """
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:tns="http://tempuri.org/">'
        "<soap:Body>"
        f"<tns:{methode}>"
        f"{body_xml}"
        f"</tns:{methode}>"
        "</soap:Body>"
        "</soap:Envelope>"
    )
    req = urllib.request.Request(
        IBABS_ENDPOINT,
        data=envelope.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"http://tempuri.org/IPublic/{methode}"',
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())

    status = root.find(f".//{{{IBABS_BASE_NS}}}Status")
    if status is not None and (status.text or "").strip().upper() == "ERR":
        bericht = root.find(f".//{{{IBABS_BASE_NS}}}Message")
        raise IbabsFout((bericht.text or "onbekende fout").strip() if bericht is not None else "onbekende fout")

    return root


def ibabs_tekst(el: ET.Element, tag: str) -> str:
    """Haal tekst op van een child-element in de iBabs-namespace."""
    child = el.find(f"{{{IBABS_NS}}}{tag}")
    return (child.text or "").strip() if child is not None else ""


def haal_vergadertypen_ibabs(sitename: str) -> dict[str, str]:
    """Geeft {id: naam} voor alle vergadertypen van een iBabs-organisatie."""
    body = f"<tns:Sitename>{sitename}</tns:Sitename>"
    try:
        root = ibabs_soap("GetMeetingtypes", body)
        result = {}
        for mt in root.iter(f"{{{IBABS_NS}}}iBabsMeetingtype"):
            mt_id = ibabs_tekst(mt, "Id")
            mt_naam = ibabs_tekst(mt, "Name")
            if mt_id:
                result[mt_id] = mt_naam
        return result
    except IbabsFout as e:
        log(f"  ! iBabs-fout bij GetMeetingtypes voor '{sitename}': {e}")
        return {}
    except Exception as e:
        log(f"  ! GetMeetingtypes mislukt: {e}")
        return {}


def haal_vergaderingen_ibabs(sitename: str, vergadertypen: dict[str, bool],
                              terugkijk_dagen: int = 730) -> list[dict]:
    """Haal vergaderingen + documenten op via de iBabs SOAP API.

    Geeft [{id, naam, datum, documenten: [{naam, url}]}].
    """
    date_from = (datetime.now() - timedelta(days=terugkijk_dagen)).strftime("%Y-%m-%dT00:00:00")
    date_to = datetime.now().strftime("%Y-%m-%dT23:59:59")

    vergadertypen_map = haal_vergadertypen_ibabs(sitename)

    body = (
        f"<tns:Sitename>{sitename}</tns:Sitename>"
        f"<tns:StartDate>{date_from}</tns:StartDate>"
        f"<tns:EndDate>{date_to}</tns:EndDate>"
        "<tns:MetaDataOnly>false</tns:MetaDataOnly>"
    )
    try:
        root = ibabs_soap("GetMeetingsByDateRange", body)
    except IbabsFout as e:
        log(f"  ! iBabs-fout bij GetMeetingsByDateRange voor '{sitename}': {e}")
        return []

    vergaderingen = []
    for meeting in root.iter(f"{{{IBABS_NS}}}iBabsMeeting"):
        mt_id = ibabs_tekst(meeting, "MeetingtypeId")
        mt_naam = vergadertypen_map.get(mt_id, mt_id)

        if not wil_vergadering(mt_naam, vergadertypen):
            continue

        meeting_id = ibabs_tekst(meeting, "Id")
        datum_raw = ibabs_tekst(meeting, "MeetingDate")
        datum = datum_raw[:10] if datum_raw else ""

        documenten = []
        for doc in meeting.iter(f"{{{IBABS_NS}}}iBabsDocument"):
            confidential = ibabs_tekst(doc, "Confidential")
            if confidential == "true":
                continue
            url = ibabs_tekst(doc, "PublicDownloadURL")
            if not url:
                continue
            bestandsnaam = ibabs_tekst(doc, "FileName") or ibabs_tekst(doc, "DisplayName")
            if not bestandsnaam:
                bestandsnaam = f"document-{ibabs_tekst(doc, 'Id')}.pdf"
            if not bestandsnaam.lower().endswith(".pdf"):
                bestandsnaam += ".pdf"
            documenten.append({"naam": bestandsnaam, "url": url})

        vergaderingen.append({
            "id": meeting_id,
            "naam": mt_naam,
            "datum": datum,
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
