"""
# Test Script for Ollama Prompts

This script allows rapid testing of different prompt combinations (system, analysis)
with various text files against a specified Ollama model. By default it uses the
application prompts shipped in `aidocsynth/prompts/`.

## Prerequisites
- Python 3.x
- Ollama library installed (`pip install ollama`)

## Usage

The script is run from the command line from the root of the project directory.

### Example 1: Basic test with app prompts and a text file

```bash
python scripts/prompt_tester.py --text path/to/sample.txt
```

### Example 2: Override prompts and specify model

```bash
python scripts/prompt_tester.py \
    --system path/to/custom/system.j2 \
    --analysis path/to/custom/analysis.j2 \
    --text path/to/sample.txt \
    --context path/to/context.json \
    --model llama3.1:8b-instruct-q8_0
```
"""
import argparse
import asyncio
import ollama
import sys
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

# Static text content for testing when no text file is provided
STATIC_TEXT_CONTENT = """This is a sample document for testing the prompt functionality. It contains various types of content that would typically be found in documents that need classification and analysis.

The document discusses different aspects of document processing including:
- Text extraction and formatting
- Content categorization
- Metadata analysis
- Document structure recognition

This sample text is designed to work with the AI classification system to demonstrate how different document types can be processed and categorized automatically."""

# Static parameters for default values
DEFAULT_SYSTEM_PROMPT = "aidocsynth/prompts/system.j2"
DEFAULT_ANALYSIS_PROMPT = "aidocsynth/prompts/analysis.j2"
DEFAULT_MODEL = "qwen3.5:27b-q8_0"

async def run_prompt_test(system_prompt_path: Path | None, analysis_prompt_path: Path | None, text_file_path: Path | None, context_path: Path | None, model: str):
    """
    Runs a test against the Ollama API with the given prompts and text file.
    """
    try:
        # 1. Setup Jinja2 environments
        #    - Package prompts (default): aidocsynth/prompts/system.j2 & analysis.j2
        #    - Filesystem prompts (optional overrides): if paths provided via CLI
        pkg_env = Environment(
            loader=PackageLoader("aidocsynth", "prompts"),
            autoescape=select_autoescape()
        )
        fs_env = Environment(loader=FileSystemLoader(searchpath="."))

        # 2. Load context data from file if provided, else use minimal defaults
        context: dict = {}
        if context_path:
            with context_path.open('r', encoding='utf-8') as f:
                context = json.load(f)

        # Handle multi-line directory structure if it's a list
        if 'directory_structure' in context and isinstance(context.get('directory_structure'), list):
            context['directory_structure'] = '\n'.join(context['directory_structure'])
        
        # 3. Set static text content if no file is provided
        if not text_file_path:
            # Default static text content for testing
            text_content = STATIC_TEXT_CONTENT
        else:
            text_content = text_file_path.read_text(encoding='utf-8')
        context['content'] = text_content

        # 3. Render prompts
        # 3. Render prompts (package defaults, filesystem overrides if provided)
        if system_prompt_path:
            system_template = fs_env.get_template(str(system_prompt_path))
        else:
            system_template = pkg_env.get_template("system.j2")
        if analysis_prompt_path:
            analysis_template = fs_env.get_template(str(analysis_prompt_path))
        else:
            analysis_template = pkg_env.get_template("analysis.j2")

        system_prompt = system_template.render(context)
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
            print(f"--- System Prompt (override): {system_prompt_path.name} ---")
        else:
            print("--- System Prompt: aidocsynth/prompts/system.j2 ---")
        if analysis_prompt_path:
            print(f"--- Analysis Prompt (override): {analysis_prompt_path.name} ---")
        else:
            print("--- Analysis Prompt: aidocsynth/prompts/analysis.j2 ---")
        if text_file_path:
            print(f"--- Text File: {text_file_path.name} ---")
        else:
            print("--- Text Content: Static sample text ---")
        print()

        # 6. Call Ollama API
        response = await client.chat(
            model=model,
            messages=messages,
            stream=False,
            format="json",  # Force JSON output
            options={"temperature": 0.0}  # Use 0.0 for deterministic testing
            think=False
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
        default=DEFAULT_SYSTEM_PROMPT,
        help="Optional path to a custom system prompt file. Defaults to aidocsynth/prompts/system.j2."
    )
    parser.add_argument(
        "--analysis",
        type=Path,
        default=DEFAULT_ANALYSIS_PROMPT,
        help="Optional path to a custom analysis prompt file. Defaults to aidocsynth/prompts/analysis.j2."
    )
    parser.add_argument(
        "--text",
        type=Path,
        required=False,
        help="Path to the example text file to classify. If not provided, uses static sample text."
    )
    parser.add_argument(
        "--context",
        type=Path,
        default=None,
        help="Optional path to a JSON context file (e.g., directory structure)."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
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
