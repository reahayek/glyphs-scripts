#MenuTitle: Set Medi Fina Init Side Bearings
# -*- coding: utf-8 -*-
__doc__ = """
Sets side bearing metrics keys for .medi, .fina, and .init glyphs:
  .medi — LSB and RSB both linked to behDotless-ar.medi
  .fina — RSB only linked to behDotless-ar.medi
  .init — LSB only linked to behDotless-ar.medi
The reference glyph (behDotless-ar.medi) is always skipped.
Works on selected glyphs, or all glyphs if nothing is selected.
Applies across all masters and syncs spacing immediately.
"""

REFERENCE = "behDotless-ar.medi"
METRICS_KEY = REFERENCE

font = Glyphs.font
if not font:
	Glyphs.showMacroWindow()
	print("No font open.")
else:
	if not font.glyphs[REFERENCE]:
		Glyphs.showMacroWindow()
		print("Reference glyph '%s' not found in font." % REFERENCE)
	else:
		# Collect target glyphs from: font view selection, active edit-view
		# glyph, or all glyphs as a fallback — whichever applies.
		seen = set()
		selectedGlyphs = []

		def _add(g):
			if g and g.id not in seen:
				seen.add(g.id)
				selectedGlyphs.append(g)

		for layer in (font.selectedLayers or []):
			if layer.parent:
				_add(layer.parent)

		tab = font.currentTab
		if tab:
			try:
				activeLayer = tab.activeLayer()
				if activeLayer and activeLayer.parent:
					_add(activeLayer.parent)
			except Exception:
				pass

		if not selectedGlyphs:
			selectedGlyphs = list(font.glyphs)

		mediCount = 0
		finaCount = 0
		initCount = 0

		for glyph in selectedGlyphs:
			name = glyph.name or ""

			if name == REFERENCE:
				continue

			isMedi = name.endswith(".medi")
			isFina = name.endswith(".fina")
			isInit = name.endswith(".init")

			if not isMedi and not isFina and not isInit:
				continue

			glyph.beginUndo()
			try:
				if isMedi:
					glyph.leftMetricsKey  = METRICS_KEY
					glyph.rightMetricsKey = METRICS_KEY
					mediCount += 1
				elif isFina:
					glyph.rightMetricsKey = METRICS_KEY
					finaCount += 1
				elif isInit:
					glyph.leftMetricsKey = METRICS_KEY
					initCount += 1

				# Sync spacing values immediately across all masters
				for layer in glyph.layers:
					layer.syncMetrics()
			finally:
				glyph.endUndo()

		print("Done.")
		print("  .medi glyphs updated: %d (LSB + RSB → %s)" % (mediCount, REFERENCE))
		print("  .fina glyphs updated: %d (RSB → %s)" % (finaCount, REFERENCE))
		print("  .init glyphs updated: %d (LSB → %s)" % (initCount, REFERENCE))
