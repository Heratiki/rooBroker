from typing import Dict, Any, List
from rich.console import Console
from .analysis import analyze_response, improve_prompt
import requests
from .config import CHAT_COMPLETIONS_ENDPOINT

class PromptWizard:
    """A task-aware prompt optimization helper, inspired by PromptWizard (arXiv:2405.18369)."""
    def __init__(self, bench_name: str, model_id: str, console: Console, max_iterations: int = 3):
        self.bench_name = bench_name
        self.model_id = model_id
        self.console = console
        self.max_iterations = max_iterations
        self.history: List[Dict[str, Any]] = []

    def refine(self, prompt: str, response: str, expected: str, analyzer_id: str, improver_id: str) -> str:
        """
        Perform a single iteration of critique and synthesis to improve the prompt.
        Returns a new prompt string.
        """
        # Critique phase
        critique = analyze_response(response, expected, analyzer_id)
        if self.console:
            self.console.print(f"[magenta]PromptWizard Critique for '{self.bench_name}': {critique['analysis']}[/magenta]")
        # Synthesis phase
        new_prompt = improve_prompt({ 'name': self.bench_name }, critique, improver_id)
        if self.console:
            self.console.print(f"[magenta]PromptWizard New Prompt for '{self.bench_name}': {new_prompt}[/magenta]")
        self.history.append({'critique': critique, 'new_prompt': new_prompt})
        return new_prompt
    
    def zero_shot_refine(
        self,
        initial_prompt: str,
        expected: str,
        improver_model: str,
        api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
        timeout: int = 10
    ) -> str:
        """
        Perform a zero-shot prompt improvement based solely on the original prompt and expected output.
        Returns an improved prompt string.
        """
        sys_msg = "You are a prompt engineering assistant. Improve prompts to be clearer, more specific, and lead to correct outputs."
        user_msg = (
            f"Original prompt: {initial_prompt}\n"
            f"Expected output: {expected}\n"
            "Generate an improved version of the above prompt. Return only the improved prompt."
        )
        try:
            payload = {
                "model": improver_model,
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg}
                ],
                "temperature": 0.2,
                "max_tokens": 300
            }
            resp = requests.post(api_endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            return initial_prompt
    
    def iterative_zero_shot_refine(
        self,
        initial_prompt: str,
        expected: str,
        improver_model: str,
        api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
        timeout: int = 10
    ) -> str:
        """
        Perform multiple rounds of zero-shot prompt refinement, iteratively improving
        the prompt up to self.max_iterations or until convergence.
        """
        prompt = initial_prompt
        for i in range(self.max_iterations):
            if self.console:
                self.console.print(f"[magenta]Iterative zero-shot refine iteration {i+1}/{self.max_iterations}[/magenta]")
            new_prompt = self.zero_shot_refine(prompt, expected, improver_model, api_endpoint, timeout)
            if new_prompt == prompt:
                break
            prompt = new_prompt
            self.history.append({'iteration': i+1, 'new_prompt': prompt})
        return prompt
