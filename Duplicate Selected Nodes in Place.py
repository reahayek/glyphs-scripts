#MenuTitle: Duplicate Selected Nodes in Place
# -*- coding: utf-8 -*-
__doc__="""
Duplicates each selected on-curve node at the exact same coordinates. The copy
is joined to the original by a straight line segment, so no handles are added
between the node and its duplicate. Forward geometry is left untouched. Works
on all currently edited layers.
"""

font = Glyphs.font
duplicatedCount = 0

if font and font.selectedLayers:
	for layer in font.selectedLayers:
		for path in layer.paths:
			# Collect selected on-curve node indexes first, then insert from the
			# highest index down, so insertions never shift indexes still to do.
			selectedIndexes = [
				i for i, node in enumerate(path.nodes)
				if node.selected and node.type != OFFCURVE
			]
			for i in sorted(selectedIndexes, reverse=True):
				original = path.nodes[i]
				newNode = GSNode()
				newNode.position = original.position  # NSPoint value, copied by value
				# Always LINE so the segment between original and duplicate is
				# straight with no handles. smooth is copied so a tangent node
				# (LINE + smooth=True) produces another tangent, and a smooth
				# curve node produces a smooth LINE (tangent-style) duplicate.
				newNode.type = LINE
				newNode.smooth = original.smooth
				path.nodes.insert(i + 1, newNode)
				# Glyphs can flip a freshly inserted node during revalidation;
				# force it back.
				path.nodes[i + 1].type = LINE
				path.nodes[i + 1].smooth = original.smooth
				duplicatedCount += 1

if duplicatedCount:
	print("Duplicated %i node%s in place." % (duplicatedCount, "" if duplicatedCount == 1 else "s"))
else:
	Glyphs.showMacroWindow()
	print("Select at least one on-curve node in a glyph, then run again.")
