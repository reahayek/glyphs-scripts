#MenuTitle: Decompose and Remove Anchors
# -*- coding: utf-8 -*-
__doc__ = """
Decomposes all components and deletes all anchors in every layer of every
master, for all selected glyphs (or all glyphs if nothing is selected).
"""

font = Glyphs.font
if not font:
	Glyphs.showMacroWindow()
	print("No font open.")
else:
	targetGlyphs = [layer.parent for layer in font.selectedLayers] if font.selectedLayers else list(font.glyphs)

	decomposedCount = 0
	anchorsRemovedCount = 0

	font.disableUpdateInterface()
	try:
		for glyph in targetGlyphs:
			glyph.beginUndo()
			try:
				for layer in glyph.layers:
					if layer.components:
						layer.decomposeComponents()
						decomposedCount += 1
					anchorsRemovedCount += len(layer.anchors)
					layer.anchors = []
			finally:
				glyph.endUndo()
	finally:
		font.enableUpdateInterface()

	print("Done. Decomposed components in %d layer(s), removed %d anchor(s)." % (decomposedCount, anchorsRemovedCount))
