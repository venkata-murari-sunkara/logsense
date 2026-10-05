import logging
import threading
import time

from groq import APIConnectionError, APITimeoutError, Groq, InternalServerError, RateLimitError
from openai import OpenAI
from openai import APIConnectionError as GeminiAPIConnectionError
from openai import APITimeoutError as GeminiAPITimeoutError
from openai import InternalServerError as GeminiInternalServerError
from openai import RateLimitError as GeminiRateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.services.event_descriptions import describe_block

logger = logging.getLogger("logsense.explanation")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Both SDKs default to a long read timeout (Groq: 60s, the openai client
# used for Gemini: 600s/10min) — meant for big batch/streaming jobs, not
# a few-sentence completion that normally finishes in seconds here. A
# connection that genuinely hangs (no response, no error) sits silently
# below our retry logic until that default fires, which is what stalled
# an evaluation run for ~35 minutes with zero error logs. Fail fast
# instead so a hang actually triggers our retry/backoff instead of
# stalling invisibly.
REQUEST_TIMEOUT_SECONDS = 30.0

_client_lock = threading.Lock()
_client: Groq | None = None

_gemini_client_lock = threading.Lock()
_gemini_client: OpenAI | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                settings = get_settings()
                _client = Groq(api_key=settings.groq_api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    return _client


def get_gemini_client() -> OpenAI:
    global _gemini_client
    if _gemini_client is None:
        with _gemini_client_lock:
            if _gemini_client is None:
                settings = get_settings()
                _gemini_client = OpenAI(
                    api_key=settings.gemini_api_key,
                    base_url=GEMINI_BASE_URL,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
    return _gemini_client


# Groq's free tier caps out around 8000 tokens/minute (and a separate
# 200,000 tokens/day cap). Callers (e.g. the evaluation service) may fire
# requests from several worker threads at once, so this throttle is global
# and thread-safe: it enforces a minimum gap between call *starts* across
# every thread — shared across both providers below, since it's really
# about not hammering whichever LLM is currently in use. The lock is
# released before the network call itself, so
# multiple calls can be in flight at once once their spacing has been
# satisfied — that's fine, Groq's client handles concurrent requests without
# issue (verified directly; an earlier theory that concurrent calls hang
# was a red herring — what actually happened was silent retry-then-failure
# against an exhausted daily quota, which is now logged, see below).
_rate_lock = threading.Lock()
_last_call_at = 0.0
MIN_CALL_INTERVAL_SECONDS = 3.0


def _throttle() -> None:
    global _last_call_at
    with _rate_lock:
        now = time.monotonic()
        wait = _last_call_at + MIN_CALL_INTERVAL_SECONDS - now
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _last_call_at = now


def build_prompt(new_block_description: str, evidence: list[dict]) -> str:
    evidence_text = "\n".join(f"- [{e['label']}] {e['description']}" for e in evidence)
    return f"""You are an assistant helping a data center engineer understand a flagged system anomaly.

A new block has been flagged as unusual. Here is what happened to it:
{new_block_description}

Here are similar past incidents from the system's history, for reference:
{evidence_text}

Based only on the information above, write a short, plain-language explanation (2-4 sentences) of what likely went wrong with this new block and why. State clearly whether you believe this block represents a real problem or is likely normal behavior. Be specific about which past incidents support your explanation. Do not make up details that are not present above."""


def build_prompt_ungrounded(new_block_description: str) -> str:
    return f"""You are an assistant helping a data center engineer understand a flagged system anomaly.

A new block has been flagged as unusual. Here is what happened to it:
{new_block_description}

Write a short, plain-language explanation (2-4 sentences) of what likely went wrong with this block and why. State clearly whether you believe this block represents a real problem or is likely normal behavior."""


def build_prompt_recommendation(new_block_description: str, evidence: list[dict], explanation: str) -> str:
    evidence_text = "\n".join(f"- [{e['label']}] {e['description']}" for e in evidence)
    return f"""You are an assistant helping a data center engineer resolve a confirmed system problem.

Here is what happened to the flagged block:
{new_block_description}

Here is the analysis of why this was flagged as a real problem:
{explanation}

Similar past incidents, for reference:
{evidence_text}

Based only on the information above, suggest 2-4 concrete, actionable next steps an engineer should take to investigate or resolve this issue. Write them as a short numbered list in plain language, ordered from most to least urgent. Do not repeat the explanation — focus only on what to do next. Do not invent steps that aren't reasonably supported by the information above."""


@retry(
    retry=retry_if_exception_type(
        (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
    ),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(8),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _complete_groq(messages: list[dict]) -> str:
    _throttle()
    settings = get_settings()
    response = get_client().chat.completions.create(
        model=settings.groq_model_name,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


@retry(
    retry=retry_if_exception_type(
        (
            GeminiRateLimitError,
            GeminiAPIConnectionError,
            GeminiAPITimeoutError,
            GeminiInternalServerError,
        )
    ),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(8),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _complete_gemini(messages: list[dict]) -> str:
    _throttle()
    settings = get_settings()
    response = get_gemini_client().chat.completions.create(
        model=settings.gemini_model_name,
        messages=messages,
        temperature=0.2,
        extra_body={"reasoning_effort": "minimal"},
    )
    return response.choices[0].message.content


def complete_messages(messages: list[dict]) -> str:
    """Routes to the configured provider (LLM_PROVIDER, default "groq").
    When Groq is primary and GEMINI_API_KEY is set, a Groq rate-limit
    error that survives Groq's own retries falls back to Gemini once
    rather than failing the caller outright.
    """
    settings = get_settings()
    if settings.llm_provider == "gemini":
        return _complete_gemini(messages)
    try:
        return _complete_groq(messages)
    except RateLimitError:
        if settings.gemini_api_key:
            logger.warning("Groq rate-limited after retries; falling back to Gemini.")
            return _complete_gemini(messages)
        raise


def _complete(prompt: str) -> str:
    return complete_messages([{"role": "user", "content": prompt}])


def generate_explanation(event_counts: dict, evidence: list[dict]) -> str:
    """Grounded: uses retrieved evidence."""
    description = describe_block(event_counts)
    return _complete(build_prompt(description, evidence))


def generate_explanation_ungrounded(event_counts: dict) -> str:
    """Ungrounded: no retrieved evidence, the model just guesses."""
    description = describe_block(event_counts)
    return _complete(build_prompt_ungrounded(description))


def generate_recommendation(event_counts: dict, evidence: list[dict], explanation: str) -> str:
    """Concrete remediation steps for a confirmed Anomaly verdict."""
    description = describe_block(event_counts)
    return _complete(build_prompt_recommendation(description, evidence, explanation))
