"""Answer generation -- one seam, two providers.

Retrieval, the gate and the citations are provider-independent; only the prose
changes. Keeping that boundary here is what makes the provider swappable at
all: `main.py` asks for a string and handles one exception type, and a failed
generation is reported as "the model is unavailable", never as "the Labour
Code does not answer this".

Resolution is lazy, at call time, because `main.py` loads `.env` after importing
this module -- reading the environment at import would silently ignore it.
"""

import os

import anthropic
import openai

import config

# Provider history, kept because it is why these defaults exist and not others.
# Claude Haiku rendered "vienas auginantis vaiką" (a SINGLE PARENT raising a
# child) as "auginate vieną vaiką" (you are raising ONE child), which would tell
# a two-parent household it qualifies for the longer leave; Sonnet rendered it
# correctly. Hence the Anthropic fallback defaults to Sonnet, not Haiku.
#
# The OpenAI default is a starting point, not a measured winner. The frozen
# golden set scores retrieval, not Lithuanian prose, so no model can be called
# "best at Lithuanian" from this repository's evidence until a generation
# benchmark exists. See docs/superpowers/plans for that work.
#
# Chosen at call time so `.env` and platform variables both win over the default.
DEFAULTS = {
    "openai": "gpt-6.1-terra",
    "anthropic": "claude-sonnet-5",
}

MODEL_ENV = {
    "openai": "ANSWER_MODEL",
    "anthropic": "ANTHROPIC_ANSWER_MODEL",
}

API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class ProviderUnavailable(RuntimeError):
    """The model API failed. Retrieval is unaffected and its sources still stand."""


def provider():
    """Which provider writes the answer. Default: OpenAI."""
    return os.environ.get("LLM_PROVIDER", "openai").strip().lower()


def model_name(name=None):
    name = (name or provider()).lower()
    if name not in DEFAULTS:
        return name
    return os.environ.get(MODEL_ENV[name], DEFAULTS[name])


def max_tokens():
    return int(os.environ.get("ANSWER_MAX_TOKENS", "1500"))


def generate(prompt, name=None):
    """Return the model's answer text for `prompt`.

    Raises ProviderUnavailable for any provider-side failure, which is the only
    distinction the caller needs: retrieval succeeded, generation did not.
    """
    name = (name or provider()).lower()
    if name == "openai":
        return _openai(prompt)
    if name == "anthropic":
        return _anthropic(prompt)
    raise ValueError(
        f"unknown LLM_PROVIDER {name!r}: expected 'openai' or 'anthropic'"
    )


def _openai(prompt):
    client = openai.OpenAI(api_key=config.require(API_KEY_ENV["openai"]))
    try:
        response = client.responses.create(
            model=model_name("openai"),
            max_output_tokens=max_tokens(),
            input=prompt,
        )
    except openai.APIError as error:
        raise ProviderUnavailable(f"openai: {error}") from error
    return response.output_text


def _anthropic(prompt):
    client = anthropic.Anthropic(api_key=config.require(API_KEY_ENV["anthropic"]))
    try:
        response = client.messages.create(
            model=model_name("anthropic"),
            max_tokens=max_tokens(),
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as error:
        raise ProviderUnavailable(f"anthropic: {error}") from error
    # Join every text block: a thinking block can precede the answer, and
    # indexing content[0] would crash on it.
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )
