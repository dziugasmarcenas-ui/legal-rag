"""Ingest labour-law acts that are not the Labour Code.

The Code repeatedly delegates: average pay is defined by Government Resolution
No. 496, work-time arrangements too. A connector that cannot read those answers
"what does the Code say" and stops where the user's question actually lives.

This ingests one act at a time from e-TAR, chunks it by its own numbered points,
and writes a separate index. The Labour Code index is untouched, so the frozen
benchmark keeps measuring the same thing.

    python ingest_sources.py            # fetch, parse, embed what is missing
    python ingest_sources.py --refresh  # re-embed unconditionally

Outputs:
    data/sources.json          chunk records with their citation
    embeddings/sources.npy     one row per chunk
    embeddings/sources.json    sidecar: which chunk each row is
"""

import hashlib
import json
import re
import sys

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import voyageai

import config
import ingest_echr
import ingest_committee
import ingest_eu
import ingest_kt
import ingest_explanations
import ingest_sadm
import ingest_sodra
import ingest_seimas
import ingest_seimas_drafts
import refresh_corpus
import vector_store

MODEL = "voyage-3"
BATCH = 64
ROOT = Path(__file__).parent
DATA = ROOT / "data" / "sources.json"
VECTORS = ROOT / "embeddings" / "sources.npy"
SIDECAR = ROOT / "embeddings" / "sources.json"
RAW = ROOT / "data" / "sources_raw"

# Deliberately a short, hand-picked list: an act earns its place by being cited
# by the Code for something people ask about, not by existing.
ACTS = [
    {
        "id": "76731a705b4711e79198ffdb108a3753",
        "short": "Nutarimas Nr. 496",
        "title": "Dėl Lietuvos Respublikos darbo kodekso įgyvendinimo",
        "authority": "Lietuvos Respublikos Vyriausybė",
        "date": "2017-06-21",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/76731a705b4711e79198ffdb108a3753",
    },
    {
        "id": "3a200a5049eb11e7846ef01bfffb9b64",
        "short": "VDI įsakymas A1-276",
        "title": "Dėl Mokymo ir žinių darbuotojų saugos ir sveikatos srityje reikalavimų",
        "authority": "Valstybinė darbo inspekcija",
        "date": "2017-06-06",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/3a200a5049eb11e7846ef01bfffb9b64",
    },
    {
        "id": "TAR.710F227A96C2",
        "short": "VDI įsakymas A1-502",
        "title": "Dėl Darbuotojų saugos ir sveikatos komitetų bendrųjų nuostatų",
        "authority": "Valstybinė darbo inspekcija",
        "date": "2013-09-09",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.710F227A96C2",
    },
    {
        "id": "TAR.AF1B122D7145",
        "short": "Nutarimas Nr. 1118",
        "title": "Dėl Nelaimingų atsitikimų darbe tyrimo ir apskaitos nuostatų patvirtinimo",
        "authority": "Lietuvos Respublikos Vyriausybė",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.AF1B122D7145",
    },
    {
        "id": "935f0d105cdc11e79198ffdb108a3753",
        "short": "SADM įsakymas A1-344",
        "title": "Dėl Darbo ginčų komisijos nuostatų, darbo reglamento ir atlygio tvarkos",
        "authority": "Socialinės apsaugos ir darbo ministerija",
        "date": "2017-06-29",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/935f0d105cdc11e79198ffdb108a3753",
    },
    {
        "id": "TAR.B2D4448A24C1",
        "short": "SADM ir SAM įsakymas A1-266/V-575",
        "title": "Dėl Įmonių darbuotojų saugos ir sveikatos tarnybų nuostatų",
        "authority": "Socialinės apsaugos ir darbo ministerija, Sveikatos apsaugos ministerija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.B2D4448A24C1",
    },
    {
        "id": "TAR.5B121E9A63FD",
        "short": "SADM ir SAM įsakymas A1-457/V-961",
        "title": "Dėl Profesinės rizikos vertinimo bendrųjų nuostatų patvirtinimo",
        "authority": "Socialinės apsaugos ir darbo ministerija, Sveikatos apsaugos ministerija",
        "date": "2012-10-25",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.5B121E9A63FD",
    },
    {
        "id": "TAR.F69EF012D841",
        "short": "Darboviečių įrengimo bendrieji nuostatai",
        "title": "Darboviečių įrengimo bendrieji nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.F69EF012D841",
    },
    {
        "id": "TAR.FECF8EBD1AFF",
        "short": "Darbo įrenginių naudojimo bendrieji nuostatai",
        "title": "Darbo įrenginių naudojimo bendrieji nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.FECF8EBD1AFF",
    },
    {
        "id": "TAR.63FFB1A69855",
        "short": "Asmeninės apsaugos priemonės",
        "title": "Darbuotojų aprūpinimo asmeninėmis apsaugos priemonėmis nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.63FFB1A69855",
    },
    {
        "id": "TAR.02EABB5CF5CB",
        "short": "Saugos ženklai",
        "title": "Saugos ir sveikatos apsaugos ženklų naudojimo darbovietėse nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.02EABB5CF5CB",
    },
    {
        "id": "TAR.73FAFA28349E",
        "short": "HN 32:2004 videoterminalai",
        "title": "Darbas su videoterminalais. Saugos ir sveikatos reikalavimai",
        "authority": "Sveikatos apsaugos ministerija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.73FAFA28349E",
    },
    {
        "id": "TAR.EE88543E313F",
        "short": "Krovinių tvarkymas rankomis",
        "title": "Darbuotojų saugos ir sveikatos reikalavimai tvarkant krovinius rankomis",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.EE88543E313F",
    },
    {
        "id": "TAR.5ED52629C3C4",
        "short": "Triukšmas",
        "title": "Darbuotojų apsaugos nuo triukšmo keliamos rizikos nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.5ED52629C3C4",
    },
    {
        "id": "TAR.0630DF325F2F",
        "short": "Vibracija",
        "title": "Darbuotojų apsaugos nuo vibracijos keliamos rizikos nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.0630DF325F2F",
    },
    {
        "id": "TAR.313208361D5D",
        "short": "Cheminiai veiksniai",
        "title": "Darbuotojų apsaugos nuo cheminių veiksnių darbe nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.313208361D5D",
    },
    {
        "id": "TAR.4035EFB0B583",
        "short": "Informacija apie saugos būklę",
        "title": "Informacijos apie darbuotojų saugos būklę ir darbo vietų atitiktį teikimo tvarka",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.4035EFB0B583",
    },
    {
        "id": "TAR.A9012F002B6D",
        "short": "DSS paslaugos",
        "title": "Juridinių ir fizinių asmenų, atliekančių darbuotojų saugos ir sveikatos paslaugas, veikla",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.A9012F002B6D",
    },
    {
        "id": "TAR.7AB2F8B44BBF",
        "short": "DSS instrukcijos",
        "title": "Darbuotojų saugos ir sveikatos instrukcijų rengimo ir instruktavimo tvarka",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.7AB2F8B44BBF",
    },
    {
        "id": "TAR.E2B53281464E",
        "short": "Sutrumpintas darbo laikas",
        "title": "Sutrumpinto darbo laiko trukmės nustatymo pagal darbo aplinkos veiksnius kriterijai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.E2B53281464E",
    },
    {
        "id": "TAR.04551A50A76D",
        "short": "Profesinės ligos",
        "title": "Profesinių ligų tyrimo ir apskaitos nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.04551A50A76D",
    },
    {
        "id": "TAR.8012ED3EA143",
        "short": "HN 23:2011 chemikalai",
        "title": "Cheminių medžiagų profesinio poveikio ribiniai dydžiai",
        "authority": "Sveikatos apsaugos ministerija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.8012ED3EA143",
    },
    {
        "id": "TAR.3923E605202A",
        "short": "Statybvietės",
        "title": "Darboviečių įrengimo statybvietėse nuostatai",
        "authority": "Valstybinė darbo inspekcija",
        "date": "",
        "url": "https://www.e-tar.lt/portal/lt/legalAct/TAR.3923E605202A",
    },
]

# Any ID list can be appended without editing this file: the bulk pipeline
# writes data/extra_acts.json and the same download/validity/chunk path runs.
_EXTRA = Path(__file__).parent / "data" / "extra_acts.json"
if _EXTRA.exists():
    for _entry in json.loads(_EXTRA.read_text(encoding="utf-8")):
        if not any(a["id"] == _entry["id"] for a in ACTS):
            ACTS.append({
                "id": _entry["id"],
                "short": _entry.get("short") or _entry["title"][:60],
                "title": _entry["title"],
                "authority": _entry.get("authority", ""),
                "date": _entry.get("date", ""),
                "url": f"https://www.e-tar.lt/portal/lt/legalAct/{_entry['id']}",
            })

POINT = re.compile(r"^(\d+)\.\s")
SUBPOINT = re.compile(r"^(\d+\.\d+)\.?\s")
SECTION = re.compile(r"^[IVXLC]+ SKYRIUS\b")
ANNOTATION = re.compile(r"^(Papunkčio|Punkto|Straipsnio|Priedo|Skirsnio).*pakeitim")
CITATION = re.compile(r"^Nr\. [IVX]+-\d+, \d{4}-\d{2}-\d{2}")
MAX_CHARS = 1500


def clean(text):
    lines = []
    raw = text.splitlines()

    # The act carries a numbered list of the amendments made to it, exactly the
    # way the Code carries its annex. It is not part of the act and must not be
    # retrievable as if it were.
    for index, line in enumerate(raw):
        if line.strip() == "Lietuvos Respublikos Vyriausybė, Nutarimas":
            raw = raw[: max(0, index - 1)]
            break

    for line in raw:
        line = line.strip()
        if not line:
            continue
        if CITATION.match(line) or ANNOTATION.match(line):
            continue
        if line.startswith("Suvestinė redakcija") or line.startswith("Nutarimas paskelbtas"):
            continue
        lines.append(line)
    return lines


def chunks(lines, act):
    """Group the act's own numbered points into retrieval-sized chunks.

    The document's structure is authoritative: a top-level point opens a chunk,
    its sub-points follow, and an annex or chapter heading becomes the context
    recorded with the chunk. Nothing is split mid-sentence.
    """
    out = []
    annex = ""
    chapter = ""
    current = None

    def flush():
        nonlocal current
        if current and current["parts"]:
            out.append(current)
        current = None

    for line in lines:
        if line.isupper() and len(line) > 18:
            flush()
            annex = line
            chapter = ""
            continue
        if SECTION.match(line):
            flush()
            chapter = line
            continue

        match = POINT.match(line)
        if match:
            flush()
            current = {
                "source": act["short"],
                "act_id": act["id"],
                "act_title": act["title"],
                "authority": act["authority"],
                "act_date": act["date"],
                "url": act["url"],
                "annex": annex,
                "chapter": chapter,
                "ref": match.group(1),
                "parts": [line],
            }
            continue

        if current is None:
            # Preamble and the enacting clause: their own chunk.
            current = {
                "source": act["short"], "act_id": act["id"],
                "act_title": act["title"], "authority": act["authority"],
                "act_date": act["date"], "url": act["url"],
                "annex": annex, "chapter": chapter, "ref": "",
                "parts": [line],
            }
            continue

        if sum(len(p) for p in current["parts"]) + len(line) > MAX_CHARS:
            # A long provision is split, not orphaned: the continuation keeps
            # the point number, because two chunks of "5 p." are still "5 p.".
            ref = current["ref"]
            flush()
            current = {
                "source": act["short"], "act_id": act["id"],
                "act_title": act["title"], "authority": act["authority"],
                "act_date": act["date"], "url": act["url"],
                "annex": annex, "chapter": chapter, "ref": ref,
                "parts": [line],
            }
            continue

        current["parts"].append(line)

    flush()

    if not out:
        # Orders and regulations sometimes carry no numbering at all. Do not
        # drop them: group paragraphs into readable chunks instead.
        buffer = []
        for line in lines:
            buffer.append(line)
            if sum(len(x) for x in buffer) >= 1100:
                out.append({
                    "source": act["short"], "act_id": act["id"],
                    "act_title": act["title"], "authority": act["authority"],
                    "act_date": act["date"], "url": act["url"],
                    "annex": "", "chapter": "", "ref": "",
                    "parts": buffer,
                })
                buffer = []
        if buffer:
            out.append({
                "source": act["short"], "act_id": act["id"],
                "act_title": act["title"], "authority": act["authority"],
                "act_date": act["date"], "url": act["url"],
                "annex": "", "chapter": "", "ref": "",
                "parts": buffer,
            })

    records = []
    for index, chunk in enumerate(out, start=1):
        heading = " · ".join(x for x in (chunk["annex"], chunk["chapter"]) if x)
        reference = f"{chunk['ref']} p." if chunk["ref"] else "įžanga"
        records.append({
            # The whole id, not its first eight characters: TAIS.403977 and
            # TAIS.403469 both truncate to "TAIS.403", which silently collapsed
            # 54 chunks into their neighbours when the store keyed on id.
            "id": f"{act['id']}-{index}",
            "source": chunk["source"],
            "act_id": act["id"],
            "act_title": chunk["act_title"],
            "authority": chunk["authority"],
            "act_date": chunk["act_date"],
            "url": chunk["url"],
            "annex": chunk["annex"],
            "chapter": chunk["chapter"],
            "ref": chunk["ref"],
            "citation": f"{chunk['source']}, {reference}",
            "title": (heading + " — " if heading else "") + chunk["parts"][0][:110],
            "text": "\n".join(chunk["parts"]),
        })
    return records


def download(act):
    # Documents that exist only in e-seimas (not in e-TAR) are exported through
    # the browser bridge and read from disk.
    local = ROOT / "data" / "acts_raw" / f"act-{act['id']}.docx"
    if local.exists() and local.stat().st_size > 1000:
        return local.read_bytes()

    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"{act['id']}.docx"
    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_bytes()
    page = refresh_corpus.fetch(f"https://www.e-tar.lt/portal/lt/legalAct/{act['id']}/asr")
    if b"actualedition" not in page:
        page = refresh_corpus.fetch(f"https://www.e-tar.lt/portal/lt/legalAct/{act['id']}")
    html_text = page.decode("utf-8", "replace")
    match = re.search(rf"actualedition/{re.escape(act['id'])}/([A-Za-z0-9]+)/", html_text)
    if match:
        url = (
            f"https://www.e-tar.lt/rs/actualedition/{act['id']}/"
            f"{match.group(1)}/format/MSO2010_DOCX/"
        )
    else:
        # Acts that were never consolidated (a single published order) expose the
        # DOCX directly instead of through an edition token.
        direct = re.search(r'/rs/legalact/[^"\'\s]*MSO2010_DOCX[^"\'\s]*', html_text)
        if not direct:
            raise RuntimeError(f"no edition token or DOCX link for {act['short']}")
        url = "https://www.e-tar.lt" + direct.group(0)
    blob = refresh_corpus.fetch(url)
    cache.write_bytes(blob)
    return blob


MONTHS = {"sausio": 1, "vasario": 2, "kovo": 3, "balandžio": 4, "gegužės": 5,
          "birželio": 6, "liepos": 7, "rugpjūčio": 8, "rugsėjo": 9, "spalio": 10,
          "lapkričio": 11, "gruodžio": 12}


def adoption_date(text):
    """The act's own adoption date, read from its header rather than guessed."""
    match = re.search(r"(\d{4}) m\. (\w+) (\d{1,2}) d\.", text[:3000])
    if not match or match.group(2) not in MONTHS:
        return ""
    year, month, day = int(match.group(1)), MONTHS[match.group(2)], int(match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


# Acts whose e-seimas page says "NEGALIOJA", with the date it stopped applying.
# The DOCX export of a repealed act still contains the old text and no marker, so
# the text alone cannot tell; this list is the recorded page status.
REPEALED_FILE = ROOT / "data" / "repealed_ids.json"
REPEALED = (
    json.loads(REPEALED_FILE.read_text(encoding="utf-8"))
    if REPEALED_FILE.exists()
    else {}
)


def validity(act, text):
    """Refuse to ingest repealed acts. A dead regulation is worse than none."""
    if act["id"] in REPEALED:
        return None
    window = refresh_corpus.WINDOW.search(text)
    if not window:
        # A single published order has no consolidated-edition header. Its
        # adoption date is the best available start; the repeals marker is the
        # guard against ingesting a dead act.
        if "netenka galios" in text[:300]:
            return None
        adopted = adoption_date(text)
        return (adopted, refresh_corpus.OPEN_ENDED) if adopted else None
    head = text[:300]
    if "netenka galios" in head:
        return None
    return window.group(1), window.group(2) or refresh_corpus.OPEN_ENDED


def embedding_input(record):
    return record["title"] + "\n" + record["text"]


def fingerprint(texts):
    digest = hashlib.sha256()
    digest.update(MODEL.encode())
    for text in texts:
        digest.update(text.encode())
    return digest.hexdigest()


def main(argv=None):
    records = []
    for act in ACTS:
        try:
            text = refresh_corpus.docx_text(download(act))
        except Exception as error:
            print(f"{act['short']}: SKIPPED -- {error}")
            continue
        window = validity(act, text)
        if window is None:
            print(f"{act['short']}: SKIPPED -- not in force (no consolidated edition or repealed)")
            continue
        if not act.get("date"):
            act["date"] = adoption_date(text)
        act_chunks = chunks(clean(text), act)
        for chunk in act_chunks:
            chunk["valid_from"], chunk["valid_to"] = window
        print(f"{act['short']}: {len(act_chunks)} chunks  ({window[0]} .. {window[1]})")
        records.extend(act_chunks)

    explanations = ingest_explanations.records()
    print(f"VDI paaiškinimai: {len(explanations)} chunks")
    records.extend(explanations)

    sadm = ingest_sadm.records()
    print(f"SADM paaiškinimai: {len(sadm)} chunks")
    records.extend(sadm)

    sodra = ingest_sodra.records()
    print(f"Sodra paaiškinimai: {len(sodra)} chunks")
    records.extend(sodra)

    transcripts = ingest_seimas.records()
    print(f"Seimo stenogramos: {len(transcripts)} chunks")
    records.extend(transcripts)

    drafts = ingest_seimas_drafts.records()
    print(f"Seimo projektai: {len(drafts)} chunks")
    records.extend(drafts)

    committee = ingest_committee.records()
    print(f"Seimo komiteto išvados: {len(committee)} chunks")
    records.extend(committee)

    eu = ingest_eu.records()
    print(f"EU directives: {len(eu)} chunks")
    records.extend(eu)

    echr = ingest_echr.records()
    print(f"ECHR judgments: {len(echr)} chunks")
    records.extend(echr)

    kt = ingest_kt.records()
    print(f"KT nutarimai: {len(kt)} chunks")
    records.extend(kt)

    # The store's primary key is the chunk id: a generator that emits the same
    # id twice would silently lose a chunk, so uniqueness is enforced here for
    # every source, not only the one that collided.
    records, repaired = vector_store.unique_ids(records)
    if repaired:
        print(f"repaired {repaired} duplicate chunk ids")

    DATA.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    texts = [embedding_input(r) for r in records]
    expected = fingerprint(texts)
    refresh = "--refresh" in (argv or sys.argv[1:])

    store = vector_store.load() if vector_store.exists() else None
    if store is None:
        # No store yet: keep the legacy all-or-nothing path so a checkout can
        # still rebuild the artifacts before the migration runs.
        if VECTORS.exists() and SIDECAR.exists() and not refresh:
            if json.loads(SIDECAR.read_text())["fingerprint"] == expected:
                print("source index already current -- no API call made")
                return 0

        client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))
        vectors = []
        for i in range(0, len(texts), BATCH):
            result = client.embed(texts[i:i + BATCH], model=MODEL, input_type="document")
            vectors.extend(result.embeddings)
            print(f"  embedded {min(i + BATCH, len(texts))}/{len(texts)}")

        matrix = np.array(vectors, dtype=np.float32)
        np.save(VECTORS, matrix)
        SIDECAR.write_text(json.dumps({
            "model": MODEL, "count": int(matrix.shape[0]),
            "fingerprint": expected, "embedded_at": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")
        print(f"saved {matrix.shape} to {VECTORS}")
        return 0

    # Incremental: a chunk whose title+text is unchanged keeps its vector, so a
    # re-ingest after adding acts embeds only the new ones.
    cache = {} if refresh else store.vectors_by_hash()
    digests = [vector_store.content_hash(r) for r in records]
    vectors = [cache.get(digest) for digest in digests]
    missing = [i for i, vector in enumerate(vectors) if vector is None]

    if missing:
        client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))
        for i in range(0, len(missing), BATCH):
            batch = missing[i:i + BATCH]
            result = client.embed(
                [texts[j] for j in batch], model=MODEL, input_type="document"
            )
            for j, embedding in zip(batch, result.embeddings):
                vectors[j] = np.asarray(embedding, dtype=np.float32)
            print(f"  embedded {min(i + BATCH, len(missing))}/{len(missing)} new chunks")

    matrix = np.array(vectors, dtype=np.float32)
    added, updated, unchanged = store.put_many(records, matrix, model=MODEL)
    store.set_meta("fingerprint", expected)
    removed = store.delete_missing([r["id"] for r in records])
    store.close()

    # The NPY pair stays in step as the reviewable artifact; the store is what
    # the service reads.
    np.save(VECTORS, matrix)
    SIDECAR.write_text(json.dumps({
        "model": MODEL, "count": int(matrix.shape[0]),
        "fingerprint": expected, "embedded_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    print(
        f"store: +{added} ~{updated} ={unchanged}, removed {removed}; "
        f"embedded {len(missing)} of {len(records)} chunks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
