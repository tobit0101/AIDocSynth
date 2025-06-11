# This file ensures that all provider modules are imported, which is necessary
# for them to register themselves via the @register decorator.

from . import dummy_provider
from . import ollama_provider
from . import openai_provider
from . import azure_provider

from .base import get_provider
