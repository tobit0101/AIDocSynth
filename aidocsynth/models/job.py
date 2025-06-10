from dataclasses import dataclass
@dataclass
class Job: path: str; status: str = "new"; progress: int = 0; message: str = ""
