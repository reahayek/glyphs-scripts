# MenuTitle: Auto Color
# Glyphs 3 script
# Labels glyph.color by how the selected master layer is built:
# - Green: paths only
# - Purple: components only
# - Blue: paths and components

from GlyphsApp import Glyphs

# Glyphs color tag indices (integer palette indices)
# Note: Color appearance can vary by UI theme, but indices are stable.
COLOR_GREEN = 6
COLOR_BLUE = 9  # magenta-like
COLOR_PURPLE = 11  # burgundy-like in many setups


def collectTargetGlyphs(font):
    """
    Always process all glyphs in the font.
    """
    return list(font.glyphs)


def layerForMaster(glyph, master_id):
    """
    Return the glyph layer for the given master ID, or None if missing.
    """
    if glyph is None or not master_id:
        return None
    try:
        return glyph.layers[master_id]
    except Exception:
        return None


def classifyLayer(layer):
    """
    Returns one of: 'green', 'purple', 'blue', or 'empty'
    based on paths/components content.
    """
    if layer is None:
        return "empty"

    has_paths = False
    has_components = False

    try:
        has_paths = len(layer.paths) > 0
    except Exception:
        has_paths = False

    try:
        has_components = len(layer.components) > 0
    except Exception:
        has_components = False

    if has_paths and not has_components:
        return "green"
    if has_components and not has_paths:
        return "purple"
    if has_paths and has_components:
        return "blue"
    return "empty"


def main():
    font = Glyphs.font
    if font is None:
        print("BuildLabel: No font open.")
        return

    master = None
    try:
        master = font.selectedFontMaster
    except Exception:
        master = None

    if master is None:
        print("BuildLabel: No selected master.")
        return

    master_id = master.id
    if not master_id:
        print("BuildLabel: Selected master has no valid ID.")
        return

    glyphs_to_process = collectTargetGlyphs(font)
    if not glyphs_to_process:
        print("BuildLabel: No glyphs to process.")
        return

    count_green = 0
    count_purple = 0
    count_blue = 0
    count_skipped = 0

    for glyph in glyphs_to_process:
        layer = layerForMaster(glyph, master_id)
        if layer is None:
            count_skipped += 1
            continue

        classification = classifyLayer(layer)
        if classification == "empty":
            count_skipped += 1
            continue

        glyph.beginUndo()
        try:
            if classification == "green":
                glyph.color = COLOR_GREEN
                count_green += 1
            elif classification == "purple":
                glyph.color = COLOR_PURPLE
                count_purple += 1
            elif classification == "blue":
                glyph.color = COLOR_BLUE
                count_blue += 1
            else:
                count_skipped += 1
        finally:
            glyph.endUndo()

    print("BuildLabel summary")
    print("  green:", count_green)
    print("  purple:", count_purple)
    print("  blue:", count_blue)
    print("  skipped:", count_skipped)


main()
