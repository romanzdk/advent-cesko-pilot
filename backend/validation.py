"""Shared offline validation and inert issue rendering. No URL is ever resolved or fetched."""
from datetime import date
import ipaddress
import json
from pathlib import Path
import re
from typing import NoReturn
import unicodedata
from urllib.parse import quote, urlsplit
import uuid

from .errors import APIError

LIMITS = {"title": 100, "town": 100, "venue": 200, "date": 10, "endDate": 10,
          "startTime": 5, "endTime": 5, "price": 200, "sourceURL": 800,
          "description": 1000, "eventId": 200, "errorKind": 20,
          "region": 100, "category": 20, "registration": 500,
          "registrationURL": 800, "audience": 200, "notes": 1000}
EXTENSIONS = {"region", "category", "registration", "registrationURL", "audience", "notes"}
REGIONS = frozenset({"Hlavní město Praha", "Jihočeský kraj", "Jihomoravský kraj", "Karlovarský kraj",
                     "Kraj Vysočina", "Královéhradecký kraj", "Liberecký kraj", "Moravskoslezský kraj",
                     "Olomoucký kraj", "Pardubický kraj", "Plzeňský kraj", "Středočeský kraj",
                     "Ústecký kraj", "Zlínský kraj"})
CATEGORIES = frozenset({"strom", "mikulas", "trhy", "tvoreni", "setkani", "betlem"})
FIELDS = set(LIMITS) | {"mode", "consent", "dateUnknown"}
TRANSPORT = {"requestId", "challenge", "website"}


def invalid(message="Zkontrolujte vyplněná pole a souhlas se zveřejněním.") -> NoReturn:
    raise APIError(400, "validation", message)


def valid_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def load_catalogue(path):
    content = json.loads(Path(path).read_text(encoding="utf-8"))
    events = content["events"]
    if not isinstance(events, list):
        raise ValueError("invalid catalogue")
    result = {entry["id"]: entry for entry in events}
    if len(result) != len(events):
        raise ValueError("duplicate catalogue ID")
    return result


def public_url(value):
    if not value or any(unicodedata.category(c)[0] == "C" or c.isspace() for c in value) or "\\" in value:
        invalid("Zdroj musí být veřejná HTTP(S) adresa.")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
            invalid()
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            invalid()
        if "%" in host:
            invalid()
        host = host.encode("idna").decode("ascii").lower()
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            labels = host.rstrip(".").split(".")
            if (len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
                    or labels[-1] in {"localhost", "local", "internal", "lan", "home", "onion", "invalid", "test", "example", "arpa"}
                    or not re.fullmatch(r"[a-z][a-z0-9-]*", labels[-1])
                    or all(re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)", label) for label in labels)):
                invalid("Zdroj musí být veřejná HTTP(S) adresa.")
        else:
            if not ip.is_global or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
                invalid("Zdroj nesmí být soukromá nebo místní adresa.")
    except (ValueError, UnicodeError):
        invalid("Neplatná adresa zdroje.")
    return value


def validate(payload, catalogue):
    if not isinstance(payload, dict) or set(payload) - FIELDS - TRANSPORT:
        invalid()
    mode = payload.get("mode")
    if not isinstance(mode, str) or mode not in {"event", "tip", "error"} or payload.get("consent") is not True:
        invalid()
    unknown = payload.get("dateUnknown", False)
    if type(unknown) is not bool:
        invalid()
    result = {"mode": mode, "consent": True, "dateUnknown": unknown}
    for key, limit in LIMITS.items():
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            invalid()
        if any(unicodedata.category(c)[0] == "C" and not (key in {"description", "registration", "notes"} and c in "\n\t") for c in value):
            invalid()
        result[key] = value.strip()
        if key in {"eventId", "errorKind"} and value != result[key]:
            invalid()
    for key in ("sourceURL", "registrationURL"):
        if result[key]:
            # Validate the original too: urlsplit otherwise silently strips controls.
            public_url(payload[key])
    for key, choices in (("region", REGIONS), ("category", CATEGORIES)):
        if result[key] and payload[key] not in choices:
            invalid()
    if mode != "error" and (result["eventId"] or result["errorKind"]):
        invalid()
    if mode == "error":
        if (result["eventId"] not in catalogue or result["errorKind"] not in {"date", "time", "venue", "cancelled", "other"}
                or not result["description"]):
            invalid("Vyberte existující akci, druh chyby a popište opravu.")
        if unknown or any(result[k] for k in ({"title", "town", "venue", "date", "endDate", "startTime", "endTime", "price"} | EXTENSIONS)):
            invalid()
    if mode == "event":
        if not all(result[k] for k in ("title", "town", "sourceURL")) or (not result["date"] and not unknown):
            invalid("Doplňte název, obec, veřejný zdroj a datum nebo označte neznámé datum.")
    if mode == "tip" and not any(result[k] for k in ("town", "sourceURL", "description")):
        invalid("Tip potřebuje alespoň obec, zdroj nebo popis.")
    if unknown and any(result[k] for k in ("date", "endDate", "startTime", "endTime")):
        invalid()
    start, end = None, None
    for key in ("date", "endDate"):
        if result[key]:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result[key]):
                    invalid()
                parsed_date = date.fromisoformat(result[key])
            except ValueError:
                invalid("Datum není platné.")
            if key == "date":
                start = parsed_date
            else:
                end = parsed_date
    if end and not start:
        invalid()
    if start and (not date(2026, 11, 20) <= start <= date(2026, 12, 24)
                  or (end and not start <= end <= date(2026, 12, 31))):
        invalid("Začátek musí být 20. 11.–24. 12. 2026 a konec nejpozději 31. 12. 2026.")
    for key in ("startTime", "endTime"):
        if result[key] and not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", result[key]):
            invalid("Čas musí mít formát HH:MM.")
    if (result["startTime"] or result["endTime"]) and not start:
        invalid()
    if (result["startTime"] and result["endTime"] and (not end or end == start)
            and result["endTime"] < result["startTime"]):
        invalid()
    # Preserve old canonical bytes/digests: new optional fields have no empty defaults.
    return {key: value for key, value in result.items() if key not in EXTENSIONS or value}


def render_issue(payload, catalogue, request_id):
    """Input stays fenced literal text, including authoritative public catalogue context."""
    if not valid_uuid(request_id):
        invalid()
    clean = validate(payload, catalogue)
    mode = clean["mode"]
    lines = ["Typ: " + mode]
    if mode == "error":
        entry = catalogue[clean["eventId"]]
        lines.append("Kontext existující veřejné akce:")
        for key in ("id", "title", "town", "region", "category", "date", "endDate", "startTime", "endTime",
                    "venue", "price", "registration", "registrationUrl", "audience", "description", "notes",
                    "sourceUrl", "status", "verifiedAt"):
            lines.append(key + ": " + str(entry.get(key, "")))
    for key in LIMITS:
        if clean.get(key):
            lines.append(key + ": " + clean[key])
    if clean["dateUnknown"]:
        lines.append("Datum není známo. Čas nebyl odhadován.")
    text = "\n".join(lines).replace("@", "＠")
    # Prevent user-supplied marker-like HTML from resembling worker identity.
    text = text.replace("<!--", "‹!--").replace("-->", "--›")
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", text)), default=3))
    title = "[Anonymní návrh: " + mode + "] " + (clean["title"] or clean["town"] or clean["eventId"] or "Tip")
    title = title.replace("@", "＠")
    permalink = "\n\nAkce na mapě: https://kamnaadvent.cz/#akce=" + quote(clean["eventId"], safe="") if mode == "error" else ""
    body = ("Anonymní, neověřené podání. Čeká na ruční kontrolu; nejde o automatické zveřejnění v mapě.\n"
            "Odesílatel souhlasil s veřejným zveřejněním na GitHubu.\n\n" + fence + "text\n" + text + "\n" + fence
            + permalink + "\n\n<!-- advent-feedback:" + request_id + " -->")
    return title, body
