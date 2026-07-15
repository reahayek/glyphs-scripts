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

FORM_SUFFIXES = ('.init', '.medi', '.fina', '.isol')

# Persists last-used values across runs within the same Glyphs session.
if not hasattr(Glyphs, '_insertGlyphsState'):
	Glyphs._insertGlyphsState = {'names': '', 'position': 1}


def isGlyphLayer(layer):
	if isinstance(layer, GSControlLayer):
		return False
	return getattr(layer, "parent", None) is not None


def isSpaceLayer(layer):
	glyph = layer.parent
	return glyph.category == "Separator" or glyph.name == "space"


def hasFormSuffix(name):
	return any(name.endswith(s) for s in FORM_SUFFIXES)


def joinsOnLeft(name):
	"""Glyph connects on its LEFT side in RTL display (.init or .medi)."""
	return name.endswith('.init') or name.endswith('.medi')


def joinsOnRight(name):
	"""Glyph connects on its RIGHT side in RTL display (.fina or .medi)."""
	return name.endswith('.medi') or name.endswith('.fina')


def remapLayer(font, masterID, glyphName, connectsFromRight, connectsToLeft):
	"""Return the layer for the correct contextual form, or None if unchanged."""
	base = glyphName
	for s in FORM_SUFFIXES:
		if glyphName.endswith(s):
			base = glyphName[:-len(s)]
			break
	if connectsFromRight and connectsToLeft:
		suffix = '.medi'
	elif connectsFromRight:
		suffix = '.fina'
	elif connectsToLeft:
		suffix = '.init'
	else:
		suffix = '.isol'
	candidate = base + suffix
	if candidate == glyphName:
		return None
	if font.glyphs[candidate]:
		return font.glyphs[candidate].layers[masterID]
	return None


class InsertGlyphsAroundEachTabGlyph(object):
	def __init__(self):
		state = Glyphs._insertGlyphsState
		self.w = vanilla.FloatingWindow((340, 132), "Insert Around Each Glyph")

		self.w.caption = vanilla.TextBox(
			(15, 14, -15, 17),
			"Glyph names (space- or slash-separated):",
			sizeStyle="small",
		)
		self.w.glyphNames = vanilla.EditText(
			(15, 36, -15, 22),
			state['names'],
			sizeStyle="small",
		)
		self.w.position = vanilla.RadioGroup(
			(15, 68, 170, 20),
			["Before", "After"],
			isVertical=False,
			sizeStyle="small",
		)
		self.w.position.set(state['position'])

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
		rawInput = self.w.glyphNames.get()
		names = rawInput.replace("/", " ").split()
		if not names:
			self.w.status.set("Type at least one glyph name.")
			return

		# Save state for next run.
		Glyphs._insertGlyphsState['names'] = rawInput
		Glyphs._insertGlyphsState['position'] = self.w.position.get()

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

		# Step 1: build the new layer list with insertions, tracking which
		# layers are original (eligible for form remapping) vs inserted.
		newLayers = []
		origFlags = []
		glyphCount = 0

		for i, layer in enumerate(allLayers):
			wrapThis = (i in targets) and isGlyphLayer(layer) and not isSpaceLayer(layer)
			if wrapThis:
				if insertBefore:
					for il in insertLayers:
						newLayers.append(il)
						origFlags.append(False)
					newLayers.append(layer)
					origFlags.append(True)
				else:
					newLayers.append(layer)
					origFlags.append(True)
					for il in insertLayers:
						newLayers.append(il)
						origFlags.append(False)
				glyphCount += 1
			else:
				newLayers.append(layer)
				origFlags.append(True)

		# Step 2: remap original glyphs that have form suffixes based on their
		# actual neighbors in the new sequence. Lower array index = more to
		# the RIGHT in RTL display, so:
		#   right neighbor = lower index  → does it join on its LEFT?
		#   left  neighbor = higher index → does it join on its RIGHT?
		def findNeighborName(seq, start, direction):
			"""Walk in direction (+1 or -1) and return first joining glyph name,
			or None if a line-break or space is hit first."""
			k = start + direction
			while 0 <= k < len(seq):
				lyr = seq[k]
				if not isGlyphLayer(lyr):
					return None  # line break: chain broken
				if isSpaceLayer(lyr):
					return None  # space: chain broken
				name = lyr.parent.name
				if hasFormSuffix(name):
					return name
				return None  # non-form glyph: chain broken
			return None

		finalLayers = []
		for j, (layer, isOrig) in enumerate(zip(newLayers, origFlags)):
			if not isOrig or not isGlyphLayer(layer) or isSpaceLayer(layer):
				finalLayers.append(layer)
				continue
			name = layer.parent.name
			if not hasFormSuffix(name):
				finalLayers.append(layer)
				continue
			rightName = findNeighborName(newLayers, j, -1)  # lower index = right
			leftName  = findNeighborName(newLayers, j, +1)  # higher index = left
			connectsFromRight = joinsOnLeft(rightName)  if rightName else False
			connectsToLeft    = joinsOnRight(leftName)  if leftName  else False
			remapped = remapLayer(font, masterID, name, connectsFromRight, connectsToLeft)
			finalLayers.append(remapped if remapped else layer)

		tab.layers = finalLayers

		if glyphCount:
			scope = "selected" if hadSelection else "all"
			self.w.status.set(
				"Added %s %i %s glyph%s; spaces and breaks kept."
				% ("before" if insertBefore else "after", glyphCount, scope, "" if glyphCount == 1 else "s")
			)
		else:
			self.w.status.set("No glyphs to act on (only spaces or breaks).")


InsertGlyphsAroundEachTabGlyph()
