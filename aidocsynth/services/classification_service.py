import json
import logging
from pathlib import Path
from typing import Any, Dict, List

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

        file_name_string = Path(file_path).name
        metadata_string = json.dumps(metadata, indent=2, ensure_ascii=False)
        content_string = text_content
        directory_structure_json = json.dumps(directory_structure, indent=2, ensure_ascii=False)

        system_prompt = self.system_prompt_template.render()
        user_prompt = self.user_prompt_template.render(
            file_name_string=file_name_string,
            metadata_string=metadata_string,
            content_string=content_string,
            directory_structure_json=directory_structure_json
        )

        self.logger.debug(f"System Prompt:\n{system_prompt}")
        self.logger.debug(f"User Prompt for {file_name_string}:\n{user_prompt}")

        # This part needs to align with how providers handle system/user prompts.
        # Assuming providers will be updated to accept a dict like:
        # { "system_prompt": system_prompt, "user_prompt": user_prompt }
        # Or a messages list: 
        # messages = [
        #     {"role": "system", "content": system_prompt},
        #     {"role": "user", "content": user_prompt}
        # ]
        # For now, let's prepare a dictionary that providers might expect.
        prompt_data = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_content": text_content # Keep if some providers still use it directly
        }

        try:
            classification_data = await self.llm_provider.classify_document(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            self.logger.info(f"Successfully classified {file_name_string}.")
            return classification_data
        except Exception as e:
            self.logger.error(f"Error during document classification for {file_name_string}: {e}", exc_info=True)
            # Fallback or error structure
            return {"error": "Classification failed", "details": str(e)}

# Example usage (for testing, not part of the actual service integration yet):
# async def main():
#     # This is a mock provider for testing purposes.
#     class MockLLMProvider:
#         async def classify_document(self, prompt_data: Dict[str, Any]) -> str:
#             print("MockLLMProvider received prompt_data:", prompt_data.get('user_prompt'))
#             # Simulate LLM returning a JSON string
#             return json.dumps({
#                 "headline": "test_headline",
#                 "label": "test_label",
#                 "context": "This is a test document.",
#                 "yyyymmdd": "20240101",
#                 "document_type": "test_type",
#                 "main_party": "test_party",
#                 "keywords": ["test", "document"],
#                 "targetPath": "Test/Path/Here",
#                 "fileName": "test_headline_20240101_test_label.txt"
#             })

#     provider = MockLLMProvider()
#     service = ClassificationService(llm_provider=provider, prompts_base_path="../../prompts") # Adjust path for local test
    
#     test_content = "This is the main content of the test document."
#     test_file_path = "/path/to/some/test_document.pdf"
#     result = await service.classify_document(test_content, test_file_path)
#     print("Classification Result:", result)

# if __name__ == "__main__":
#     import asyncio
#     # Configure logging for testing
#     logging.basicConfig(level=logging.DEBUG)
#     asyncio.run(main())
