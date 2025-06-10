from pydantic import BaseModel, Field
from typing import Optional

class ProviderSettings(BaseModel):
    provider_name: str = "default"
    api_key: Optional[str] = None

class AppSettings(BaseModel):
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    # Weitere Einstellungen können hier später hinzugefügt werden.
