from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Job:
    path: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: datetime = field(default_factory=datetime.now)
    status: str = "new"              # new | extracting | ocr | llm | writing | done | error
    progress: int = 0
    message: str = ""
    result: str = ""
