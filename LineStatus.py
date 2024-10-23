from enum import Enum

class LineStatus(Enum):
    """Represents the status of a line in a diff file."""
    ADDED = 0
    DELETED = 1
    UNCHANGED = 2

