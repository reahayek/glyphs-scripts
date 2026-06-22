#MenuTitle: Insert Glyphs Before or After Each Tab Glyph
# -*- coding: utf-8 -*-
__doc__="""
Insert one or more glyphs (by name) before or after each glyph in the active
Edit tab. If glyphs are selected, only those are affected; otherwise all of
them are. Existing spaces and line breaks are left untouched. Names can be
separated by spaces or slashes.
"""

from GlyphsApp import *
import vanilla


def isGlyphLayer(layer):
	# A line break is a GSControlLayer; a real glyph layer has a glyph parent.
	if isinstance(layer, GSControlLayer):
		return False
	return getattr(layer, "parent", None) is not None


def isSpaceLayer(layer):
	glyph = layer.parent
	return glyph.category == "Separator" or glyph.name == "space"


class InsertGlyphsAroundEachTabGlyph(object):
	def __init__(self):
		self.w = vanilla.FloatingWindow((340, 132), "Insert Around Each Glyph")

		self.w.caption = vanilla.TextBox(
			(15, 14, -15, 17),
			"Glyph names (space- or slash-separated):",
			sizeStyle="small",
		)
		self.w.glyphNames = vanilla.EditText(
			(15, 36, -15, 22),
			"",
			sizeStyle="small",
		)
		self.w.position = vanilla.RadioGroup(
			(15, 68, 170, 20),
			["Before", "After"],
			isVertical=False,
			sizeStyle="small",
		)
		self.w.position.set(1)  # default to After

		self.w.runButton = vanilla.Button(
			(-100, 67, -15, 22),
			"Insert",
			callback=self.insertCallback,
		)
		self.w.setDefaultButton(self.w.runButton)

		self.w.status = vanilla.TextBox(
			(15, 100, -15, 17),
			"",
			sizeStyle="small",
		)

		self.w.open()
		self.w.makeKey()

	def targetIndices(self, tab, allLayers):
		# Returns the set of positions in allLayers to act on.
		# Uses layer-aligned cursor + selected layer objects so suffixed
		# Arabic glyphs (which miscount in textCursor/textRange) stay correct.
		selObjs = list(Glyphs.font.selectedLayers) if Glyphs.font.selectedLayers else []
		hasSelection = (tab.textRange > 0) and (len(selObjs) > 0)
		if not hasSelection:
			return set(range(len(allLayers)))

		k = len(selObjs)
		cursor = tab.layersCursor
		selSet = set(id(layer) for layer in selObjs)

		# The caret sits at one end of the selection; test both ends and verify
		# the window really contains the selected objects.
		for start in (cursor, cursor - k):
			if 0 <= start and start + k <= len(allLayers):
				window = allLayers[start:start + k]
				if set(id(layer) for layer in window) == selSet:
					return set(range(start, start + k))

		# Fallback: act on every position whose layer is one of the selected.
		return set(i for i, layer in enumerate(allLayers) if id(layer) in selSet)

	def insertCallback(self, sender):
		font = Glyphs.font
		if font is None:
			self.w.status.set("Open a font first.")
			return

		tab = font.currentTab
		if tab is None:
			self.w.status.set("No Edit tab is open.")
			return

		# Accept names separated by spaces and/or slashes, e.g. "alef beh" or "/alef/beh".
		names = self.w.glyphNames.get().replace("/", " ").split()
		if not names:
			self.w.status.set("Type at least one glyph name.")
			return

		# Validate first; abort on any unknown name so a typo can't insert a partial set.
		notFound = [n for n in names if font.glyphs[n] is None]
		if notFound:
			self.w.status.set("Not in font: %s" % ", ".join(notFound))
			return

		masterID = font.selectedFontMaster.id
		insertLayers = [font.glyphs[n].layers[masterID] for n in names]
		insertBefore = self.w.position.get() == 0

		allLayers = list(tab.layers)
		targets = self.targetIndices(tab, allLayers)
		hadSelection = len(targets) < len(allLayers)

		newLayers = []
		glyphCount = 0
		for i, layer in enumerate(allLayers):
			wrapThis = (i in targets) and isGlyphLayer(layer) and not isSpaceLayer(layer)
			if wrapThis:
				if insertBefore:
					newLayers.extend(insertLayers)
					newLayers.append(layer)
				else:
					newLayers.append(layer)
					newLayers.extend(insertLayers)
				glyphCount += 1
			else:
				newLayers.append(layer)

		tab.layers = newLayers

		if glyphCount:
			scope = "selected" if hadSelection else "all"
			self.w.status.set(
				"Added %s %i %s glyph%s; spaces and breaks kept."
				% ("before" if insertBefore else "after", glyphCount, scope, "" if glyphCount == 1 else "s")
			)
		else:
			self.w.status.set("No glyphs to act on (only spaces or breaks).")


InsertGlyphsAroundEachTabGlyph()
