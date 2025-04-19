"""
Analysis of model responses and prompt improvement.
"""
from typing import Dict, Any
import requests

from lmstudio_config import CHAT_COMPLETIONS_ENDPOINT


def analyze_response(
    response: str,
    expected: str,
    analyzer_model: str,
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    timeout: int = 10
) -> Dict[str, Any]:
    """Analyze a model's response using another model to suggest improvements."""
    analysis_prompt = f"""Analyze this model response and suggest improvements:

    Original Task Expected: {expected}
    Model Response: {response}

    Analyze:
    1. What's missing or incorrect?
    2. How could the prompt be improved?
    3. Rate accuracy (0-100%)
    """
    try:
        payload: Dict[str, Any] = {
            "model": analyzer_model,
            "messages": [
                {"role": "system", "content": "You are an AI response analyst. Analyze model outputs and suggest improvements."},
                {"role": "user", "content": analysis_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        resp = requests.post(api_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        analysis = resp.json()["choices"][0]["message"]["content"]
        return {"analysis": analysis, "original_response": response, "expected": expected}
    except Exception as e:
        return {"analysis": f"Analysis failed: {e}", "original_response": response, "expected": expected}


def improve_prompt(
    benchmark: Dict[str, Any],
    analysis: Dict[str, Any],
    improver_model: str,
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    timeout: int = 10
) -> str:
    """Generate an improved prompt based on analysis."""
    improvement_prompt = (
        f"Original prompt: {benchmark['prompt']}\n"
        f"Expected output: {benchmark['expected']}\n"
        f"Previous response: {analysis['original_response']}\n"
        f"Analysis: {analysis['analysis']}\n\n"
        "Generate an improved version of the original prompt that will lead to better results."
        " Focus on clarity, specificity, and guiding the model to the expected format."
        " Return only the improved prompt, no explanations."
    )
    try:
        payload: Dict[str, Any] = {
            "model": improver_model,
            "messages": [
                {"role": "system", "content": "You are a prompt engineer. Improve prompts to get better results."},
                {"role": "user", "content": improvement_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        resp = requests.post(api_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return benchmark["prompt"]
