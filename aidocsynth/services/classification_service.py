import json
import logging
from pathlib import Path
from typing import Any, Dict, List
import time

from jinja2 import Environment, PackageLoader, select_autoescape

class ClassificationService:
    def __init__(self, llm_provider: Any):
        self.logger = logging.getLogger(__name__)
        self.llm_provider = llm_provider
        self.jinja_env = Environment(
            loader=PackageLoader("aidocsynth", "prompts"),
            autoescape=select_autoescape()
        )
        self.system_prompt_template = self.jinja_env.get_template("system.j2")
        self.user_prompt_template = self.jinja_env.get_template("analysis.j2")
        # Maximum number of retries if the LLM returns an invalid response
        self.max_retries: int = 3

    async def classify_document(
        self, 
        text_content: str, 
        file_path: str, 
        metadata: Dict[str, Any] = None, # Placeholder for now
        directory_structure: List[str] = None # Placeholder for now
    ) -> Dict[str, Any]:
        """
        Classifies the document using the configured LLM provider and prompts.

        Args:
            text_content: The extracted text content of the document.
            file_path: The original path of the document file.
            metadata: Extracted metadata from the document (placeholder).
            directory_structure: A list of existing directories (placeholder).

        Returns:
            A dictionary containing the structured classification data from the LLM.
        """
        if metadata is None:
            metadata = {}
        if directory_structure is None:
            directory_structure = []

        target_filename_string = Path(file_path).name
        metadata_string = json.dumps(metadata, indent=2, ensure_ascii=False)
        content_string = text_content
        directory_structure_json = json.dumps(directory_structure, indent=2, ensure_ascii=False)

        system_prompt = self.system_prompt_template.render()
        user_prompt = self.user_prompt_template.render(
            target_filename_string=target_filename_string,
            metadata_string=metadata_string,
            content_string=content_string,
            directory_structure_json=directory_structure_json
        )

        self.logger.debug(f"System Prompt:\n{system_prompt}")
        self.logger.debug(f"User Prompt for {target_filename_string}:\n{user_prompt}")

        # Start overall timer to measure processing duration
        overall_start = time.perf_counter()

        # Retry loop – ensures we get at least a JSON object that contains
        # the mandatory keys: "target_filename" and "target_directory".
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                raw_response = await self.llm_provider.classify_document(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt
                )

                # The provider may already return a dict or a JSON string. Try both.
                if isinstance(raw_response, dict):
                    classification_data = raw_response
                else:
                    classification_data = json.loads(str(raw_response))

                # Validate minimal schema
                if not (
                    isinstance(classification_data, dict)
                    and "target_filename" in classification_data
                    and "target_directory" in classification_data
                ):
                    raise ValueError(
                        "Invalid classification result – missing required keys 'target_filename' and/or 'target_directory'."
                    )

                # Success – log and return (include timing)
                overall_duration = time.perf_counter() - overall_start
                self.logger.info(
                    f"Successfully classified {target_filename_string} on attempt {attempt} in {overall_duration:.2f}s."
                )
                return classification_data

            except (json.JSONDecodeError, ValueError) as e:
                # Response content error – potentially recoverable
                last_error = e
                self.logger.warning(
                    f"Attempt {attempt} for {target_filename_string} returned an invalid response: {e}"
                )
            except Exception as e:
                # Other, potentially transient error (network, provider error, etc.)
                last_error = e
                self.logger.warning(
                    f"Attempt {attempt} for {target_filename_string} failed with error: {e}",
                    exc_info=True,
                )

        # All retries exhausted – return fallback structure
        overall_duration = time.perf_counter() - overall_start

        error_message = (
            f"Classification failed after {self.max_retries} attempts: {last_error}"
            if last_error
            else "Classification failed for unknown reasons."
        )
        self.logger.error(f"{error_message} (took {overall_duration:.2f}s)")
        return {"error": "Classification failed", "details": str(last_error)}
