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
import refresh_corpus

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
]

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

    records = []
    for index, chunk in enumerate(out, start=1):
        heading = " · ".join(x for x in (chunk["annex"], chunk["chapter"]) if x)
        reference = f"{chunk['ref']} p." if chunk["ref"] else "įžanga"
        records.append({
            "id": f"{act['id'][:8]}-{index}",
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
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"{act['id']}.docx"
    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_bytes()
    page = refresh_corpus.fetch(f"https://www.e-tar.lt/portal/lt/legalAct/{act['id']}/asr")
    match = re.search(rf"actualedition/{act['id']}/([A-Za-z0-9]+)/", page.decode("utf-8", "replace"))
    if not match:
        sys.exit(f"no edition token for {act['short']}")
    blob = refresh_corpus.fetch(
        f"https://www.e-tar.lt/rs/actualedition/{act['id']}/{match.group(1)}/format/MSO2010_DOCX/"
    )
    cache.write_bytes(blob)
    return blob


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
        text = refresh_corpus.docx_text(download(act))
        act_chunks = chunks(clean(text), act)
        print(f"{act['short']}: {len(act_chunks)} chunks")
        records.extend(act_chunks)

    DATA.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    texts = [embedding_input(r) for r in records]
    expected = fingerprint(texts)

    if VECTORS.exists() and SIDECAR.exists() and "--refresh" not in (argv or sys.argv[1:]):
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


if __name__ == "__main__":
    raise SystemExit(main())
