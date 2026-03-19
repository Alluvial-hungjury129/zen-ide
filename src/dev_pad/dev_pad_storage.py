"""
Dev Pad storage for persisting activity history.

GUI-agnostic module for storing and querying Dev Pad activities.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

# Storage location
DEV_PAD_DIR = Path.home() / ".zen_ide"
DEV_PAD_FILE = DEV_PAD_DIR / "dev_pad.json"
NOTES_DIR = DEV_PAD_DIR / "notes"


def _relative_date_label(d: date) -> str:
    """Return a human-friendly relative label for a date."""
    today = date.today()
    delta = (today - d).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 7:
        return f"{delta} days ago"
    if delta < 14:
        return "Last week"
    return d.strftime("%a %d %b")  # e.g., "Fri 23 Jan"


@dataclass
class DevPadActivity:
    """Represents a single activity entry in the Dev Pad."""

    id: str  # Unique ID for the activity
    timestamp: str  # ISO format timestamp
    activity_type: str  # "file_edit", "ai_chat", "git_checkout", "search", etc.
    title: str  # Short display title
    description: str  # Longer description
    link_type: Optional[str] = None  # "file", "ai_chat", "repo", etc.
    link_target: Optional[str] = None  # Path, chat ID, URL, etc.
    metadata: dict = field(default_factory=dict)  # Additional data

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DevPadActivity":
        return cls(**data)


class DevPadStorage:
    """Manages persistence and querying of Dev Pad activities."""

    _instance = None

    def __init__(self):
        self._activities: list[DevPadActivity] = []
        self._max_activities = 500  # Limit history size
        self._listeners: list[Callable] = []  # Callbacks when activities change
        self._loaded = False  # Lazy loading flag

    @classmethod
    def get_instance(cls) -> "DevPadStorage":
        if cls._instance is None:
            cls._instance = DevPadStorage()
        return cls._instance

    def _ensure_loaded(self):
        """Ensure activities are loaded (lazy loading)."""
        if self._loaded:
            return
        self._loaded = True
        self._load()

    def _load(self):
        """Load activities from disk."""
        try:
            if DEV_PAD_FILE.exists():
                with open(DEV_PAD_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._activities = [DevPadActivity.from_dict(a) for a in data.get("activities", [])]
        except Exception:
            self._activities = []

    def _save(self):
        """Save activities to disk."""
        try:
            DEV_PAD_DIR.mkdir(parents=True, exist_ok=True)
            data = {"activities": [a.to_dict() for a in self._activities]}
            with open(DEV_PAD_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def add_activity(
        self,
        activity_type: str,
        title: str,
        description: str,
        link_type: Optional[str] = None,
        link_target: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DevPadActivity:
        """Add a new activity to the Dev Pad."""
        self._ensure_loaded()
        activity = DevPadActivity(
            id=f"{datetime.now().timestamp()}_{len(self._activities)}",
            timestamp=datetime.now().isoformat(),
            activity_type=activity_type,
            title=title,
            description=description,
            link_type=link_type,
            link_target=link_target,
            metadata=metadata or {},
        )
        self._activities.insert(0, activity)  # Most recent first

        # Trim to max size
        if len(self._activities) > self._max_activities:
            self._activities = self._activities[: self._max_activities]

        self._save()
        self._notify_listeners()
        return activity

    def update_or_add_activity(
        self,
        activity_type: str,
        title: str,
        description: str,
        link_type: Optional[str] = None,
        link_target: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DevPadActivity:
        """Update existing activity timestamp if found, otherwise add new.

        Matches by link_type and link_target to avoid duplicate entries.
        """
        self._ensure_loaded()
        if link_type and link_target:
            # Look for existing activity with same link
            for i, activity in enumerate(self._activities):
                if activity.link_type == link_type and activity.link_target == link_target:
                    # Found existing - update timestamp, content and move to top
                    activity.timestamp = datetime.now().isoformat()
                    activity.title = title
                    activity.description = description
                    if metadata is not None:
                        activity.metadata = metadata
                    self._activities.pop(i)
                    self._activities.insert(0, activity)
                    self._save()
                    self._notify_listeners()
                    return activity

        # No existing activity found, add new
        return self.add_activity(
            activity_type=activity_type,
            title=title,
            description=description,
            link_type=link_type,
            link_target=link_target,
            metadata=metadata,
        )

    def get_activities_grouped_by_date(
        self, limit: int = 50, filter_query: str = "", type_filter: set[str] | None = None
    ) -> dict[str, list[DevPadActivity]]:
        """Get activities grouped by date, optionally filtered by search query and type."""
        self._ensure_loaded()
        query_lower = filter_query.lower().strip()
        grouped: dict[str, list[DevPadActivity]] = {}
        count = 0

        for activity in self._activities:
            if count >= limit:
                break

            # Apply type filter if provided
            if type_filter is not None and activity.activity_type not in type_filter:
                continue

            # Apply search filter if query is provided
            if query_lower:
                if not (
                    query_lower in activity.title.lower()
                    or query_lower in activity.description.lower()
                    or query_lower in activity.activity_type.lower()
                ):
                    continue

            try:
                dt = datetime.fromisoformat(activity.timestamp)
                date_key = _relative_date_label(dt.date())
            except Exception:
                date_key = "Unknown"

            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(activity)
            count += 1

        return grouped

    def delete_activity(self, activity_id: str):
        """Delete a specific activity."""
        self._ensure_loaded()
        self._activities = [a for a in self._activities if a.id != activity_id]
        self._save()
        self._notify_listeners()

    def clear_all(self, type_filter: set[str] | None = None, filter_query: str = ""):
        """Clear activities. If type_filter or filter_query is provided, only clear matching activities."""
        self._ensure_loaded()
        if type_filter is None and not filter_query:
            # Clear everything
            self._activities = []
        else:
            # Clear only matching activities
            query_lower = filter_query.lower().strip()
            self._activities = [a for a in self._activities if not self._matches_filter(a, type_filter, query_lower)]
        self._save()
        self._notify_listeners()

    def _matches_filter(self, activity: DevPadActivity, type_filter: set[str] | None, query_lower: str) -> bool:
        """Check if an activity matches the given filter criteria."""
        # Check type filter
        if type_filter is not None and activity.activity_type not in type_filter:
            return False
        # Check search query
        if query_lower:
            searchable = f"{activity.title} {activity.description or ''}".lower()
            if query_lower not in searchable:
                return False
        return True

    def update_activity(self, activity_id: str, **kwargs):
        """Update an existing activity."""
        for activity in self._activities:
            if activity.id == activity_id:
                for key, value in kwargs.items():
                    if hasattr(activity, key):
                        setattr(activity, key, value)
                self._save()
                self._notify_listeners()
                return

    def add_listener(self, callback: Callable):
        """Add a callback to be notified when activities change."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        """Remove a callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self):
        """Notify all listeners of changes."""
        for callback in self._listeners:
            try:
                callback()
            except Exception:
                pass


def get_dev_pad_storage() -> DevPadStorage:
    """Get the singleton Dev Pad storage instance."""
    return DevPadStorage.get_instance()
