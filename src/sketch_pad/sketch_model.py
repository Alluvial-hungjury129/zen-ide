"""
Sketch Pad data model – ASCII diagram editor.

Re-export shim: imports from sub-modules and re-exports everything
so that existing ``from sketch_pad.sketch_model import X`` continues to work.
"""

# Base types, enums, constants
# Actor, Topic, Database, Cloud
from sketch_pad.sketch_model_actors import (  # noqa: F401
    ACTOR_CHARS,
    ACTOR_HEIGHT,
    ACTOR_WIDTH,
    CLOUD_MIN_HEIGHT,
    CLOUD_MIN_WIDTH,
    DATABASE_DEFAULT_HEIGHT,
    DATABASE_DEFAULT_WIDTH,
    DATABASE_MIN_HEIGHT,
    DATABASE_MIN_WIDTH,
    TOPIC_MIN_HEIGHT,
    TOPIC_MIN_WIDTH,
    ActorShape,
    CloudShape,
    DatabaseShape,
    TopicShape,
)

# Arrow + routing helpers
from sketch_pad.sketch_model_arrow import (  # noqa: F401
    ArrowShape,
    _best_edges_between,
    _clamp_edge_ratio_h,
    _clamp_edge_ratio_v,
    _compute_diagonal_edges,
    _compute_h_edges,
    _compute_v_edges,
    _edges_are_degenerate,
    _mixed_ratios,
    _pick_barely_degenerate,
    _point_in_box,
    _rate_candidate,
    _would_uturn,
)
from sketch_pad.sketch_model_base import (  # noqa: F401
    _CLIPBOARD_XLAT,
    BORDER,
    CORNER_CHARS,
    SNAP_DISTANCE,
    AbstractShape,
    ArrowLineStyle,
    BorderChars,
    ToolMode,
)

# Connection & Board
from sketch_pad.sketch_model_connection import (  # noqa: F401
    Board,
    Connection,
    _render_font_size_texts,
)

# Rectangle
from sketch_pad.sketch_model_rectangle import (  # noqa: F401
    RectangleShape,
    _word_wrap_into,
)
