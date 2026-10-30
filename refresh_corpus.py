"""Pull the current consolidated Labour Code from e-TAR and show what changed.

    python refresh_corpus.py           # fetch, compare, write nothing
    python refresh_corpus.py --write   # replace data/darbo_kodeksas_raw.txt

Why this exists: the corpus is a *consolidated edition*, not a URL. e-TAR rolls
the edition forward on a date boundary (the loaded one runs 2026-06-07 to
2026-10-31), and a RAG system that keeps serving the old text after that date is
answering about superseded law with a confident citation. This script makes the
refresh one command instead of a manual copy-paste, and makes it verifiable:
it prints the edition window and the paragraphs that actually changed, so a
refresh is never "trust me, I re-downloaded it".

How it works: the portal page for the act carries a token for the current
edition; the same token serves a DOCX of the full text. Both are public, no
login. No HTML scraping of the article body, no PDF layout guessing.

The comparison normalises whitespace (including the non-breaking spaces e-TAR
uses for alignment) because a whitespace-only difference is not a legal change
and must not trigger a re-embed.
"""

import html
import re
import ssl
import sys
import urllib.request
import zipfile

from io import BytesIO
from pathlib import Path

# The framework Python on macOS ships without a CA bundle, so the system store
# cannot verify e-TAR's certificate. certifi is already a transitive dependency
# of the SDKs; use it when present and fall back to the system store otherwise.
try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

ACT_ID = "f6d686707e7011e6b969d7ae07280e89"
PORTAL = f"https://www.e-tar.lt/portal/lt/legalAct/{ACT_ID}/asr"
RAW = Path(__file__).parent / "data" / "darbo_kodeksas_raw.txt"

USER_AGENT = "legal-rag corpus refresh (https://github.com/dziugasmarcenas-ui/legal-rag)"

# A paragraph's visible text is an ordered mixture of runs, tabs and line
# breaks. Pulling only <w:t> drops the tab between "Prezidentė" and the name and
# glues words together, so walk the inline elements in document order.
INLINE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|<w:(tab|br|cr)\b[^>]*/>", re.S)
PARAGRAPH = re.compile(r"<w:p\b.*?</w:p>", re.S)
ARTICLE = re.compile(r"^(\d+)(?:-(\d+))? straipsnis\.", re.M)
WINDOW = re.compile(r"Suvestinė redakcija nuo (\d{4}-\d{2}-\d{2}) iki (\d{4}-\d{2}-\d{2})")


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()


def edition_token(page):
    """The path segment that identifies the current edition on the portal."""
    match = re.search(rf"actualedition/{ACT_ID}/([^/\"']+)/", page.decode("utf-8", "replace"))
    if not match:
        sys.exit(
            "could not find the edition token on the portal page.\n"
            "The page layout probably changed -- check "
            f"{PORTAL} and the token regex in this file."
        )
    return match.group(1)


def download_docx(token):
    url = f"https://www.e-tar.lt/rs/actualedition/{ACT_ID}/{token}/format/MSO2010_DOCX/"
    blob = fetch(url)
    if not blob.startswith(b"PK"):
        sys.exit(f"e-TAR did not return a DOCX ({len(blob)} bytes). Refusing to write a broken corpus.")
    return blob


def docx_text(blob):
    """Plain text of the document, one paragraph per line, tabs and breaks as spaces."""
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    lines = []
    for paragraph in PARAGRAPH.findall(xml):
        parts = []
        for match in INLINE.finditer(paragraph):
            text, break_tag = match.group(1), match.group(2)
            parts.append(html.unescape(text) if text is not None else " ")
        line = re.sub(r"[ \t\r\n\f\v]+", " ", "".join(parts)).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def edition_window(text):
    match = WINDOW.search(text)
    if not match:
        sys.exit("no 'Suvestinė redakcija nuo ... iki ...' header -- wrong document?")
    return match.group(1), match.group(2)


def article_ids(text):
    """Article identifiers in document order, for a cheap structural check."""
    return [match.group(0).split()[0] for match in ARTICLE.finditer(text)]


def normalise(text):
    """Whitespace-insensitive form, used only for comparing and for the diff."""
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def changed_lines(old, new):
    """(index, old, new) for lines that differ, aligned on the shorter prefix.

    Insertions and deletions shift every later line, so this reports the first
    divergent index and lets the reader look at the printed context rather than
    pretending to be a real diff engine.
    """
    a, b = normalise(old), normalise(new)
    return [(i, x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y], len(a), len(b)


def main(argv):
    write = "--write" in argv

    print(f"portal: {PORTAL}")
    page = fetch(PORTAL)
    token = edition_token(page)
    print(f"edition token: {token}")

    text = docx_text(download_docx(token))
    start, end = edition_window(text)
    ids = article_ids(text)
    print(f"edition: {start} .. {end}")
    print(f"article headings: {len(ids)}  paragraphs: {len(normalise(text))}")

    if not RAW.exists():
        print(f"no existing corpus at {RAW.relative_to(Path.cwd()) if RAW.is_relative_to(Path.cwd()) else RAW}")
        current = ""
    else:
        current = RAW.read_text(encoding="utf-8")

    diffs, old_count, new_count = changed_lines(current, text)
    print(f"existing paragraphs: {old_count}  new: {new_count}")

    if not diffs and old_count == new_count:
        print("no substantive change -- the edition on e-TAR is the one already loaded.")
        return 0

    print(f"\n{len(diffs)} changed paragraph(s):")
    for index, before, after in diffs[:10]:
        print(f"\n--- paragraph {index}")
        print(f"  old: {before[:300]}")
        print(f"  new: {after[:300]}")
    if len(diffs) > 10:
        print(f"\n... and {len(diffs) - 10} more")

    old_start = edition_window(current)[0] if WINDOW.search(current) else "unknown"
    if old_start == start and diffs:
        print("\nWARNING: same edition window but different text -- e-TAR edited the edition in place.")
        print("Re-check the golden set labels before trusting any measurement.")

    if not write:
        print("\ndry run; re-run with --write to replace the corpus.")
        return 0

    RAW.write_text(text, encoding="utf-8")
    print(f"\nwrote {RAW}")
    print("next: python parse_corpus.py && python check_corpus.py && python embed_corpus.py")
    print("then re-verify golden-set labels and re-run eval/run_eval.py --refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
