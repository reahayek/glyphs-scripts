#MenuTitle: Put Spaces Between Arabic Glyphs
# -*- coding: utf-8 -*-
__doc__="""
Goes through all selected glyphs and slaps each of their nodes around a bit.
"""

from GlyphsApp import *

tab = Glyphs.font.currentTab
if not tab:
    Glyphs.showNotification("Insert Spaces", "Open an Edit Tab first.")
else:
    originalDir = tab.direction
    if originalDir == RTL:   # temporarily switch to LTR so /glyph notation works
        tab.direction = LTR

    parts, newLine = [], True
    for layer in tab.layers:
        if not hasattr(layer, "parent"):  # line break
            parts.append("\n")
            newLine = True
            continue
        if not newLine:
            parts.append("/space")
        parts.append("/" + layer.parent.name)
        newLine = False

    tab.text = "".join(parts)
    tab.direction = originalDir
