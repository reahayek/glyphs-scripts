#MenuTitle: Round Corners
# -*- coding: utf-8 -*-

"""
Round Corners - GlyphsApp Script
Converts sharp LINE-to-LINE corners into smooth rounded curves.

Usage:
  - Select glyphs in the Font tab, or open a glyph in Edit view
  - Run the script
  - Enter a radius value when prompted
"""

from __future__ import division, print_function, unicode_literals
import math

# ─── CONFIGURATION ───────────────────────────────────────────────────────────

# Ask the user for a radius value (in units)
radius = GetIntFromUser(
    "Round Corners",
    "Enter corner radius (units):",
    value=30,
    minimum=1,
    maximum=500
)

if radius is None:
    print("Script cancelled.")
    import sys; sys.exit()

# Minimum angle (degrees) below which a corner is considered "sharp"
# 180 = perfectly straight line (not a corner), lower = sharper corner
ANGLE_THRESHOLD = 170.0

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def vector_length(p1, p2):
    """Return the distance between two NSPoints."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return math.sqrt(dx * dx + dy * dy)


def lerp_point(p1, p2, t):
    """Linearly interpolate between two NSPoints by factor t."""
    return NSPoint(
        p1.x + (p2.x - p1.x) * t,
        p1.y + (p2.y - p1.y) * t
    )


def angle_between(p_prev, p_corner, p_next):
    """
    Return the interior angle (degrees) at p_corner formed by the
    vectors (p_prev -> p_corner) and (p_corner -> p_next).
    """
    ax = p_corner.x - p_prev.x
    ay = p_corner.y - p_prev.y
    bx = p_next.x - p_corner.x
    by = p_next.y - p_corner.y

    dot   = ax * bx + ay * by
    mag_a = math.sqrt(ax * ax + ay * ay)
    mag_b = math.sqrt(bx * bx + by * by)

    if mag_a == 0 or mag_b == 0:
        return 180.0  # degenerate segment, treat as straight

    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
    return math.degrees(math.acos(cos_angle))


def is_sharp_corner(node):
    """
    Returns True when `node` is a LINE node that sits between two
    straight segments — i.e., a genuine sharp corner.
    """
    if node.type != LINE:
        return False

    path  = node.parent
    nodes = path.nodes
    idx   = list(nodes).index(node)
    count = len(nodes)

    prev_node = nodes[(idx - 1) % count]
    next_node = nodes[(idx + 1) % count]

    # Both neighbours must also be LINE nodes for a straight-to-straight corner
    if prev_node.type not in (LINE, GSLINE) or next_node.type not in (LINE, GSLINE):
        return False

    angle = angle_between(prev_node.position, node.position, next_node.position)
    return angle < ANGLE_THRESHOLD


def round_corner(path, corner_node, r):
    """
    Replace a sharp corner node with a smooth rounded curve.

    Strategy:
      1. Walk r units back along the incoming segment  -> point A
      2. Walk r units forward along the outgoing segment -> point B
      3. Remove the original corner node
      4. Insert A (LINE), a CURVE node at the original corner position,
         and B, then add smooth off-curve handles so the segment curves.

    We use Glyphs' built-in smooth-curve insertion for clean results.
    """
    nodes  = list(path.nodes)
    idx    = nodes.index(corner_node)
    count  = len(nodes)

    prev_node = nodes[(idx - 1) % count]
    next_node = nodes[(idx + 1) % count]

    p_corner = corner_node.position
    p_prev   = prev_node.position
    p_next   = next_node.position

    # Clamp radius to half the shorter segment
    dist_in  = vector_length(p_prev, p_corner)
    dist_out = vector_length(p_corner, p_next)
    safe_r   = min(r, dist_in * 0.49, dist_out * 0.49)

    if safe_r < 1:
        return  # segment too short to round

    t_in  = safe_r / dist_in
    t_out = safe_r / dist_out

    # New on-curve points
    pt_a = lerp_point(p_corner, p_prev,   t_in)   # approaching corner
    pt_b = lerp_point(p_corner, p_next,   t_out)  # leaving corner

    # Off-curve handles (placed at the corner position for a circular-ish arc)
    # Using 0.5523 approximation for a quarter-circle with bezier
    KAPPA = 0.5523
    handle_a = lerp_point(pt_a, p_corner, KAPPA)
    handle_b = lerp_point(pt_b, p_corner, KAPPA)

    # Build replacement nodes
    # Order: ... pt_a (LINE), off_a (OFFCURVE), off_b (OFFCURVE), pt_b (CURVE) ...
    node_a     = GSNode(pt_a,     type=LINE)
    node_off_a = GSNode(handle_a, type=OFFCURVE)
    node_off_b = GSNode(handle_b, type=OFFCURVE)
    node_b     = GSNode(pt_b,     type=CURVE)
    node_b.smooth = True

    # Remove original corner, insert new nodes in its place
    path.removeNodeCheckKeepShape_(corner_node)  # removes node cleanly
    # Re-fetch index after removal
    nodes = list(path.nodes)
    # Find insertion index: right after prev_node's new position
    try:
        insert_after = nodes.index(prev_node) + 1
    except ValueError:
        return  # prev_node was also removed somehow

    for i, new_node in enumerate([node_a, node_off_a, node_off_b, node_b]):
        path.nodes.insert(insert_after + i, new_node)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

font = Glyphs.font
if not font:
    Message("No font open!", "Round Corners")
    import sys; sys.exit()

# Determine target glyphs
doc            = font.currentDocument
selected_glyphs = [layer.parent for layer in font.selectedLayers] if font.selectedLayers else list(font.glyphs)

processed_nodes  = 0
processed_glyphs = 0

for glyph in selected_glyphs:
    layer = glyph.layers[font.selectedFontMaster.id]
    if not layer:
        continue

    corners_in_glyph = 0

    for path in layer.paths:
        # Collect corner nodes BEFORE modifying the path
        corners = [n for n in list(path.nodes) if is_sharp_corner(n)]

        for corner in corners:
            try:
                round_corner(path, corner, radius)
                corners_in_glyph  += 1
                processed_nodes   += 1
            except Exception as e:
                print("  [skip] %s — %s" % (glyph.name, str(e)))

    if corners_in_glyph:
        processed_glyphs += 1
        print("  Rounded %d corner(s) in '%s'" % (corners_in_glyph, glyph.name))

print("\nDone. Rounded %d corner(s) across %d glyph(s) with radius %d." % (
    processed_nodes, processed_glyphs, radius
))
