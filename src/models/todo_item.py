"""
Todo item model for document analysis suggestions.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class TodoItem:
    """Represents a suggested action/todo item for document improvement."""

    description_en: str
    description_id: str
    action_type: str  # "edit", "format", "add", "remove", "fix", "improve"
    target: str  # What to modify (e.g., "paragraph_2", "cell_A1", "slide_3")
    suggestion: str  # AI-generated content or fix suggestion
    priority: int  # 1 (highest) to 5 (lowest)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    executed: bool = False
    result: Optional[str] = None  # Result after execution

    def get_description(self, lang: str) -> str:
        """Get description in specified language."""
        if lang == "id":
            return self.description_id
        return self.description_en

    def get_priority_label(self, lang: str) -> str:
        """Get priority label in specified language."""
        labels = {
            1: ("High", "Tinggi"),
            2: ("Medium-High", "Sedang-Tinggi"),
            3: ("Medium", "Sedang"),
            4: ("Low-Medium", "Rendah-Sedang"),
            5: ("Low", "Rendah"),
        }
        en, id_ = labels.get(self.priority, ("Medium", "Sedang"))
        return id_ if lang == "id" else en

    def mark_executed(self, result: Optional[str] = None) -> None:
        """Mark this todo as executed."""
        self.executed = True
        self.result = result

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "description_en": self.description_en,
            "description_id": self.description_id,
            "action_type": self.action_type,
            "target": self.target,
            "suggestion": self.suggestion,
            "priority": self.priority,
            "executed": self.executed,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TodoItem":
        """Create TodoItem from dictionary."""
        item = cls(
            description_en=data.get("description_en", ""),
            description_id=data.get("description_id", ""),
            action_type=data.get("action_type", "edit"),
            target=data.get("target", ""),
            suggestion=data.get("suggestion", ""),
            priority=data.get("priority", 3),
        )
        item.id = data.get("id", item.id)
        item.executed = data.get("executed", False)
        item.result = data.get("result")
        return item
