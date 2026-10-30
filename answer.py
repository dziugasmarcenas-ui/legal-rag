"""Prompt construction and grounded answering, shared by the HTTP API and MCP.

This lives outside `main.py` because there are now two callers: the demo UI and
the MCP `ask_labour_code` tool. Two copies of a prompt is two products.

The language rules are the accumulated fix list -- each one names a real failure
observed in production, with the wrong form beside the right one. They are not
style advice; deleting a counter-example has already reintroduced the bug once.
"""

import llm


# Written in the target language on purpose -- instructions in the output
# language control the output more reliably than instructions about it.
#
# The Lithuanian rules are not generic "write well" advice. Each one names a
# real failure observed in production, with the wrong form beside the right
# one, because Lithuanian punishes clipped phrasing far harder than English
# does: an English bullet can stop at a noun, a Lithuanian one that opens in
# the dative has to reach its verb or it is simply ungrammatical.
ANSWER_LANGUAGE = {
    "lt": (
        "Atsakyk lietuviškai, aiškiai ir taisyklinga kalba.\n"
        "Kalbos reikalavimai:\n"
        "- Rašyk pilnais sakiniais. Kiekvienas punktas turi būti baigtas "
        "teiginys su veiksmažodžiu. Rašyk „Darbuotojui priklauso 30 darbo "
        "dienų“, o ne „Aukščiau nurodytoms kategorijoms: 30 darbo dienų“.\n"
        "- Nepalik nebaigtų žodžių junginių — visada nurodyk daiktavardį. "
        "Rašyk „pagimdžius du ar daugiau vaikų“, o ne „pagimdžius du ar "
        "daugiau“.\n"
        "- Apibūdindamas asmenis vartok būdvardžius, o ne prieveiksmius. "
        "Rašyk „jaunesni nei 18 metų“, o ne „jauniau nei 18 metų“.\n"
        "- Derink linksnius, giminę ir skaičių visame sakinyje.\n"
        "- Skaičius rašyk skaitmenimis, ne žodžiais: „20 darbo dienų“, "
        "o ne „dvidešimt darbo dienų“.\n"
        "- Nevartok angliškų žodžių ir nepalik jokio teksto anglų kalba.\n"
        "- Nerašyk antraščių su # ženklu.\n"
        "- Jei kelioms darbuotojų kategorijoms taikoma ta pati taisyklė, "
        "išvardyk jas kartu, o ne kartok tą pačią taisyklę kiekvienai atskirai."
    ),
    "en": (
        "Answer in English, clearly and in complete sentences. The articles "
        "are in Lithuanian; translate what they say faithfully and do not add "
        "anything they do not contain. Keep Lithuanian legal terms in brackets "
        "where a precise English equivalent does not exist. Write numbers as "
        "digits, not words. A Seimas draft is not adopted law: say so when you "
        "rely on one. Do not use markdown headings such as # or ##. If the "
        "same rule applies to several categories, list them together rather than "
        "repeating the rule for each one."
    ),
}

REFUSAL = {
    "lt": ("Neturiu pakankamai patikimo pagrindo atsakyti į šį klausimą pagal "
           "Darbo kodeksą. Pasitikslinkite su teisininku ar personalo skyriumi."),
    "en": ("I don't have a confident enough basis in the Labour Code to answer "
           "this. Check with a lawyer or your HR department."),
}


# Citations name the part when the claim rests on one. A reader can check
# "126 straipsnio 2 dalis" in seconds; "126 straipsnis" sends them hunting.
CITATION_CLOSING = {
    "lt": (
        "Pabaigoje nurodyk straipsnį formatu [X straipsnis]. Jei teiginys remiasi "
        "konkrečia straipsnio dalimi, nurodyk ją: [X straipsnio Y dalis]. Kitų "
        "teisės aktų nuostatas cituok tiksliai taip, kaip jos pažymėtos laužtiniuose "
        "skliaustuose, pvz. [Nutarimas Nr. 496, 5 p.]."
    ),
    "en": (
        "End by naming the article as [X straipsnis]. If the claim rests on a "
        "specific part, name it as [X straipsnio Y dalis]. Cite other acts exactly "
        "as labelled in square brackets, e.g. [Nutarimas Nr. 496, 5 p.]."
    ),
}


def _edition_note(edition, lang):
    """A historical answer must say which edition it is answering from."""
    if not edition:
        return ""
    if lang == "en":
        return (
            f"These articles were in force from {edition['valid_from']} to "
            f"{edition['valid_to']}. Answer according to that edition and say so.\n\n"
        )
    return (
        f"Šie straipsniai galiojo nuo {edition['valid_from']} iki "
        f"{edition['valid_to']}. Atsakyk pagal tą redakciją ir tai nurodyk.\n\n"
    )


def build_prompt(question, results, lang="lt", edition=None):
    """Give the model only the retrieved articles, and require a citation.

    The citation format stays "[X straipsnis]" in both languages, because the
    UI parses it back into a link to the source card -- and because the article
    is a Lithuanian one whichever language the prose is in.
    """
    articles = "\n\n".join(
        f"[{r.get('label') or (r['citation'] + ' straipsnis')}] {r['title']}\n{r['text']}"
        for r in results
    )
    return (
        "Tu esi Lietuvos darbo teisės asistentas. Atsakyk į klausimą remdamasis "
        "TIK žemiau pateiktais šaltiniais. Šaltiniai gali būti Darbo kodekso "
        "straipsniai, kiti teisės aktai, institucijų paaiškinimai ar teismų "
        "sprendimai; kiekvienas pažymėtas laužtiniuose skliaustuose. Jei "
        "šaltiniuose atsakymo nėra, pasakyk, kad nežinai. Seimo projektas yra "
        "nepriimtas aktas: jei remiatės projektu, aiškiai pasakyk, kad jis dar "
        "nepriimtas.\n\n"
        f"{_edition_note(edition, lang)}"
        f"Straipsniai:\n{articles}\n\n"
        f"Klausimas: {question}\n\n"
        f"{ANSWER_LANGUAGE[lang]} {CITATION_CLOSING[lang]}"
    )


def generate_answer(question, results, lang="lt"):
    return llm.generate(build_prompt(question, results, lang))


def generate(question, results, lang="lt", edition=None):
    """The grounded answer, or ProviderUnavailable. Callers handle the refusal."""
    return llm.generate(build_prompt(question, results, lang, edition=edition))
