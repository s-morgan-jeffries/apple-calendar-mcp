#!/usr/bin/env python3
"""Run blind agent evals against any OpenAI-compatible API.

Sends each scenario prompt (with tool descriptions as context) to a model
and saves responses for scoring.

Usage:
    # Single model:
    python run_eval.py --model meta-llama/llama-3.3-70b-instruct

    # Multiple models in parallel:
    python run_eval.py --model meta-llama/llama-3.3-70b-instruct qwen/qwen-2.5-72b-instruct

    # Specific scenarios:
    python run_eval.py --model meta-llama/llama-3.3-70b-instruct --scenarios 1,2,3

Requires OPENROUTER_API_KEY in environment or .env file at project root.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

from scenarios import SCENARIOS

SCRIPT_DIR = Path(__file__).parent
TOOL_DESCRIPTIONS_PATH = SCRIPT_DIR / "tool_descriptions.md"

SYSTEM_PROMPT = """You are a blind eval agent. You have access ONLY to the tool descriptions below. \
You have NO access to any codebase, documentation, or external knowledge. \
Based solely on the tool descriptions, plan your response to the user's request.

List the exact tool calls you would make, in order, with all parameters. Explain your reasoning briefly.

## Tool Descriptions

{tool_descriptions}"""


def get_api_key() -> str:
    """Get API key from environment or .env file."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        env_path = SCRIPT_DIR.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    return api_key


def run_scenario(client: OpenAI, model: str, scenario: dict, tool_descriptions: str) -> dict:
    """Run a single scenario and return the result."""
    system = SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": scenario["prompt"]},
        ],
        temperature=0,
        max_tokens=2048,
    )

    content = response.choices[0].message.content
    usage = response.usage

    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "category": scenario["category"],
        "prompt": scenario["prompt"],
        "response": content,
        "scoring_notes": scenario["scoring_notes"],
        "safety_critical": scenario["safety_critical"],
        "model": model,
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
    }


def run_model(client: OpenAI, model: str, scenarios: list, tool_descriptions: str, output_dir: Path) -> dict:
    """Run all scenarios for a single model. Returns summary dict."""
    model_short = model.split("/")[-1]
    results = []
    total_input = 0
    total_output = 0

    for i, scenario in enumerate(scenarios, 1):
        print(f"  [{model_short}] [{i}/{len(scenarios)}] {scenario['name']}...", end=" ", flush=True)
        try:
            result = run_scenario(client, model, scenario, tool_descriptions)
            results.append(result)
            if result["input_tokens"]:
                total_input += result["input_tokens"]
                total_output += result["output_tokens"]
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "id": scenario["id"],
                "name": scenario["name"],
                "error": str(e),
            })

    # Save results
    model_slug = model.replace("/", "_")
    output_path = output_dir / f"raw_{model_slug}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    return {
        "model": model,
        "output_path": str(output_path),
        "scenarios": len(scenarios),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
    }


def main():
    parser = argparse.ArgumentParser(description="Run blind agent evals via OpenRouter")
    parser.add_argument("--model", nargs="+",
                        default=["meta-llama/llama-3.3-70b-instruct"],
                        help="Model ID(s) — multiple models run in parallel")
    parser.add_argument("--scenarios", default=None,
                        help="Comma-separated scenario IDs (default: all)")
    parser.add_argument("--output", default=str(SCRIPT_DIR / "results"),
                        help="Output directory")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found.")
        print("Set it as an environment variable or in .env at the project root.")
        sys.exit(1)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    tool_descriptions = TOOL_DESCRIPTIONS_PATH.read_text()

    scenarios = SCENARIOS
    if args.scenarios:
        ids = {int(x) for x in args.scenarios.split(",")}
        scenarios = [s for s in SCENARIOS if s["id"] in ids]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    models = args.model

    print(f"Models: {', '.join(models)}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Output: {args.output}")
    if len(models) > 1:
        print(f"Running {len(models)} models in parallel")
    print()

    if len(models) == 1:
        summary = run_model(client, models[0], scenarios, tool_descriptions, output_dir)
        print(f"\nResults saved to {summary['output_path']}")
        print(f"Total tokens: {summary['total_tokens']}")
    else:
        summaries = []
        with ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(run_model, client, model, scenarios, tool_descriptions, output_dir): model
                for model in models
            }
            for future in as_completed(futures):
                model = futures[future]
                try:
                    summary = future.result()
                    summaries.append(summary)
                except Exception as e:
                    print(f"\n{model} FAILED: {e}")

        print(f"\n{'='*60}")
        print("Summary:")
        for s in sorted(summaries, key=lambda x: x["model"]):
            print(f"  {s['model']}: {s['scenarios']} scenarios, {s['total_tokens']} tokens -> {s['output_path']}")


if __name__ == "__main__":
    main()
