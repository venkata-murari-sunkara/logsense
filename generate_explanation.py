"""
Step 4: Explanation Generation
Takes a newly flagged block plus the similar past incidents retrieved
in Step 3, and asks Groq (openai/gpt-oss-120b) to write a plain-language
explanation of the likely root cause, grounded in that evidence.

Also includes an "ungrounded" version (no retrieved evidence) so we can
compare the two in the accuracy evaluation step.
"""
import os
from dotenv import load_dotenv
from groq import Groq

from event_descriptions import describe_block
from retrieve_similar_incidents import get_similar_incidents

import streamlit as st
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
MODEL = "openai/gpt-oss-120b"


def build_prompt(new_block_description: str, evidence: list) -> str:
    evidence_text = "\n".join(
        f"- [{e['label']}] {e['description']}" for e in evidence
    )
    prompt = f"""You are an assistant helping a data center engineer understand a flagged system anomaly.

A new block has been flagged as unusual. Here is what happened to it:
{new_block_description}

Here are similar past incidents from the system's history, for reference:
{evidence_text}

Based only on the information above, write a short, plain-language explanation (2-4 sentences) of what likely went wrong with this new block and why. State clearly whether you believe this block represents a real problem or is likely normal behavior. Be specific about which past incidents support your explanation. Do not make up details that are not present above."""
    return prompt


def build_prompt_ungrounded(new_block_description: str) -> str:
    """No retrieved evidence at all — the AI has to explain based only
    on the block's own description, guessing without reference examples."""
    prompt = f"""You are an assistant helping a data center engineer understand a flagged system anomaly.

A new block has been flagged as unusual. Here is what happened to it:
{new_block_description}

Write a short, plain-language explanation (2-4 sentences) of what likely went wrong with this block and why. State clearly whether you believe this block represents a real problem or is likely normal behavior."""
    return prompt


def generate_explanation(event_counts: dict, top_k: int = 3) -> str:
    """Grounded: uses RAG retrieval for evidence."""
    new_block_description = describe_block(event_counts)
    evidence = get_similar_incidents(event_counts, top_k=top_k)
    prompt = build_prompt(new_block_description, evidence)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content


def generate_explanation_ungrounded(event_counts: dict) -> str:
    """Ungrounded: no retrieved evidence, the AI just guesses."""
    new_block_description = describe_block(event_counts)
    prompt = build_prompt_ungrounded(new_block_description)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    test_event_counts = {"E5": 1, "E7": 2, "E14": 1}

    print("=== Grounded (RAG) Explanation ===")
    print(generate_explanation(test_event_counts))

    print("\n=== Ungrounded Explanation ===")
    print(generate_explanation_ungrounded(test_event_counts))