"""
# Test Script for Ollama Prompts

This script allows for rapid testing of different prompt combinations (system, analysis)
with various text files against a specified Ollama model.

## Prerequisites
- Python 3.x
- Ollama library installed (`pip install ollama`)

## Usage

The script is run from the command line from the root of the project directory.

### Example 1: Basic test with analysis prompt and text file

```bash
python tests/test_prompt.py
```

### Example 2: Full test with system prompt, analysis prompt, text file, and specific model

```bash
python tests/test_prompt.py \\
    --system tests/prompts/system.j2 \\
    --analysis tests/prompts/analysis.j2 \\
    --text tests/prompts/document.txt \\
    --context tests/prompts/context.json \\
    --model llama3.1:8b-instruct-q8_0
```
"""
import argparse
import asyncio
import ollama
import sys
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

async def run_prompt_test(system_prompt_path: Path, analysis_prompt_path: Path, text_file_path: Path, context_path: Path, model: str):
    """
    Runs a test against the Ollama API with the given prompts and text file.
    """
    try:
        # 1. Setup Jinja2 environment
        env = Environment(loader=FileSystemLoader(searchpath="."))

        # 2. Load context data from files
        with context_path.open('r', encoding='utf-8') as f:
            context = json.load(f)

        # Handle multi-line directory structure if it's a list
        if 'directory_structure' in context and isinstance(context.get('directory_structure'), list):
            context['directory_structure'] = '\n'.join(context['directory_structure'])
        
        text_content = text_file_path.read_text(encoding='utf-8')
        context['content'] = text_content

        # 3. Render prompts
        system_prompt = ""
        if system_prompt_path:
            system_template = env.get_template(str(system_prompt_path))
            system_prompt = system_template.render(context)
        
        analysis_template = env.get_template(str(analysis_prompt_path))
        analysis_prompt = analysis_template.render(context)

        # 3. Setup Ollama client
        client = ollama.AsyncClient()

        # 5. Prepare messages for the chat API
        messages = [
            {
                'role': 'system',
                'content': system_prompt,
            },
            {
                'role': 'user',
                'content': analysis_prompt,
            }
        ]
        
        print(f"--- Running test with model: {model} ---")
        if system_prompt_path:
            print(f"--- System Prompt: {system_prompt_path.name} ---")
        print(f"--- Analysis Prompt: {analysis_prompt_path.name} ---")
        print(f"--- Text File: {text_file_path.name} ---\n")

        # 6. Call Ollama API
        response = await client.chat(
            model=model,
            messages=messages,
            stream=False,
            format="json",  # Force JSON output
            options={"temperature": 0.0}  # Use 0.0 for deterministic testing
        )

        print("\n--- Parsed JSON Response ---")
        try:
            # Attempt to parse the JSON string
            parsed_json = json.loads(response['message']['content'])
            # Pretty-print the parsed JSON
            print(json.dumps(parsed_json, indent=2, ensure_ascii=False))
        except json.JSONDecodeError as e:
            print(f"Error: Failed to decode JSON from LLM response.", file=sys.stderr)
            print(f"JSONDecodeError: {e}", file=sys.stderr)
        print("--- End of Response ---\n")

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

async def main():
    """
    Main function to parse arguments and run the test.
    """
    parser = argparse.ArgumentParser(description="Run a prompt test against Ollama.")
    parser.add_argument(
        "--system",
        type=Path,
        default="tests/prompts/system.j2",
        help="Path to the system prompt file (default: tests/prompts/system.j2)."
    )
    parser.add_argument(
        "--analysis",
        type=Path,
        default="tests/prompts/analysis.j2",
        help="Path to the analysis prompt file (default: tests/prompts/analysis.j2)."
    )
    parser.add_argument(
        "--text",
        type=Path,
        default="tests/prompts/document.txt",
        help="Path to the example text file (default: tests/prompts/document.txt)."
    )
    parser.add_argument(
        "--context",
        type=Path,
        default="tests/prompts/context.json",
        help="Path to the context data JSON file (default: tests/prompts/context.json)."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.1:8b-instruct-q8_0",
        help="The Ollama model to use for the test (default: llama3.1:8b-instruct-q8_0)."
    )

    args = parser.parse_args()

    await run_prompt_test(
        system_prompt_path=args.system,
        analysis_prompt_path=args.analysis,
        text_file_path=args.text,
        context_path=args.context,
        model=args.model
    )

if __name__ == "__main__":
    # Make sure ollama library is installed: pip install ollama
    asyncio.run(main())
