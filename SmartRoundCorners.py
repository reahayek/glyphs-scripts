#MenuTitle: Smart Round Corners
# -*- coding: utf-8 -*-
__doc__ = """
Advanced corner rounding with per-node radius control, angle-aware
adaptive radius, and live preview in the edit view.

Features:
— Live preview: see the rounded result overlaid on your glyph before applying.
— Per-node radius: tag selected nodes with a custom radius stored in
  node.userData["smartRoundRadius"]. Overrides the global radius.
— Angle-aware adaptive radius: obtuse corners get a larger effective
  radius, acute corners get a smaller one. Controlled by the Adaptation
  slider.
— Separate inner/outer radius control.
— Scope: selected nodes, current glyph, or all glyphs in the font.

Requires Vanilla (Window > Plugin Manager > Modules).
"""

import math
import copy
import objc
import traceback
import vanilla
from GlyphsApp import (
	Glyphs, GSLayer, GSPath, GSNode,
	GSLINE, GSCURVE, GSOFFCURVE,
	DRAWFOREGROUND, Message,
)
from AppKit import NSColor, NSBezierPath, NSFont


# ————————————————————————————————————————————————————————————————
# Geometry helpers
# ————————————————————————————————————————————————————————————————

def angle_between(a, b):
	dx = b.x - a.x
	dy = b.y - a.y
	return math.degrees(math.atan2(dy, dx))


def turning_angle(prev_on, corner, next_on):
	a1 = angle_between(corner, prev_on)
	a2 = angle_between(corner, next_on)
	ca = (a2 - a1) % 360
	turn = 180.0 - ca if ca <= 180.0 else ca - 180.0
	return abs(turn)


def pt_distance(a, b):
	return math.hypot(b.x - a.x, b.y - a.y)


def is_corner_node(node):
	if node.type == GSOFFCURVE:
		return False
	if node.smooth:
		return False
	return True


def is_outward_corner(prev_on, node, next_on, path):
	v1x = node.x - prev_on.x
	v1y = node.y - prev_on.y
	v2x = next_on.x - node.x
	v2y = next_on.y - node.y
	cross = v1x * v2y - v1y * v2x
	direction = path.direction
	return (cross * direction) < 0


def get_prev_oncurve(path, index):
	nodes = path.nodes
	n = len(nodes)
	for i in range(1, n):
		idx = (index - i) % n
		if nodes[idx].type != GSOFFCURVE:
			return nodes[idx]
	return None


def get_next_oncurve(path, index):
	nodes = path.nodes
	n = len(nodes)
	for i in range(1, n):
		idx = (index + i) % n
		if nodes[idx].type != GSOFFCURVE:
			return nodes[idx]
	return None


# ————————————————————————————————————————————————————————————————
# Core rounding
# ————————————————————————————————————————————————————————————————

KAPPA = 0.5522847498


def compute_effective_radius(base_radius, corner_node, prev_on, next_on,
                             adaptation):
	node_r = None
	try:
		if corner_node.userData and "smartRoundRadius" in corner_node.userData:
			node_r = float(corner_node.userData["smartRoundRadius"])
	except:
		pass

	r = node_r if node_r is not None else base_radius

	if adaptation > 0 and node_r is None:
		turn = turning_angle(prev_on, corner_node, next_on)
		angle_factor = 1.0 + adaptation * (90.0 - turn) / 90.0
		angle_factor = max(0.15, min(angle_factor, 2.5))
		r *= angle_factor

	d_prev = pt_distance(prev_on, corner_node)
	d_next = pt_distance(corner_node, next_on)
	max_r = min(d_prev, d_next) * 0.49
	r = min(r, max_r)
	r = max(r, 0)
	return r


def round_corner(path, node_index, radius):
	nodes = path.nodes
	node = nodes[node_index]

	prev_on = get_prev_oncurve(path, node_index)
	next_on = get_next_oncurve(path, node_index)
	if prev_on is None or next_on is None:
		return 0
	if radius <= 0.5:
		return 0

	d_prev = pt_distance(prev_on, node)
	d_next = pt_distance(node, next_on)
	if d_prev < 1 or d_next < 1:
		return 0

	t_prev = min(radius / d_prev, 0.49)
	t_next = min(radius / d_next, 0.49)

	asx = node.x + (prev_on.x - node.x) * t_prev
	asy = node.y + (prev_on.y - node.y) * t_prev
	aex = node.x + (next_on.x - node.x) * t_next
	aey = node.y + (next_on.y - node.y) * t_next

	h1x = asx + (node.x - asx) * KAPPA
	h1y = asy + (node.y - asy) * KAPPA
	h2x = aex + (node.x - aex) * KAPPA
	h2y = aey + (node.y - aey) * KAPPA

	n1 = GSNode((asx, asy), GSLINE)
	n2 = GSNode((h1x, h1y), GSOFFCURVE)
	n3 = GSNode((h2x, h2y), GSOFFCURVE)
	n4 = GSNode((aex, aey), GSCURVE)
	n4.smooth = True

	path.removeNodeAtIndex_(node_index)
	for i, nn in enumerate([n1, n2, n3, n4]):
		path.insertNode_atIndex_(nn, node_index + i)

	return 3


def process_layer(layer, base_radius, adaptation, round_inner,
                  inner_radius, only_selected):
	count = 0
	for path in list(layer.paths):
		corners = []
		for i, node in enumerate(path.nodes):
			if not is_corner_node(node):
				continue
			if only_selected and not node.selected:
				continue
			prev_on = get_prev_oncurve(path, i)
			next_on = get_next_oncurve(path, i)
			if prev_on is None or next_on is None:
				continue
			outward = is_outward_corner(prev_on, node, next_on, path)
			if not outward and not round_inner:
				continue
			use_radius = base_radius if outward else inner_radius
			r = compute_effective_radius(
				use_radius, node, prev_on, next_on, adaptation
			)
			if r > 0.5:
				corners.append((i, r))
		for idx, r in reversed(corners):
			round_corner(path, idx, r)
			count += 1
	return count


# ————————————————————————————————————————————————————————————————
# Preview helper
# ————————————————————————————————————————————————————————————————

def make_preview_layer(source_layer, base_radius, adaptation,
                       round_inner, inner_radius, only_selected):
	preview = source_layer.copy()
	process_layer(preview, base_radius, adaptation,
	              round_inner, inner_radius, only_selected)
	return preview


# ————————————————————————————————————————————————————————————————
# Per-node tagging
# ————————————————————————————————————————————————————————————————

def tag_selected_nodes(radius_value):
	font = Glyphs.font
	if not font:
		return 0
	layer = font.selectedLayers[0]
	tagged = 0
	for path in layer.paths:
		for node in path.nodes:
			if node.selected and node.type != GSOFFCURVE:
				node.userData["smartRoundRadius"] = float(radius_value)
				tagged += 1
	return tagged


def clear_tags_selected():
	font = Glyphs.font
	if not font:
		return 0
	layer = font.selectedLayers[0]
	cleared = 0
	for path in layer.paths:
		for node in path.nodes:
			if node.selected and node.type != GSOFFCURVE:
				if node.userData and "smartRoundRadius" in node.userData:
					del node.userData["smartRoundRadius"]
					cleared += 1
	return cleared


# ————————————————————————————————————————————————————————————————
# Vanilla GUI with live preview
# ————————————————————————————————————————————————————————————————

class SmartRoundCornersDialog:

	def __init__(self):
		self.preview_active = False
		self.preview_layer = None

		y = 10
		sp = 28
		ww = 330
		wh = 480

		self.w = vanilla.FloatingWindow(
			(ww, wh), "Smart Round Corners",
			minSize=(ww, wh), maxSize=(ww, wh + 80),
		)

		# ── Preview toggle ──────────────────────────────────
		self.w.previewCheck = vanilla.CheckBox(
			(15, y, -15, 20), "Preview",
			sizeStyle="small", value=False,
			callback=self.togglePreview,
		)
		y += sp + 2

		# ── Outer radius ────────────────────────────────────
		self.w.labelRadius = vanilla.TextBox(
			(15, y, 100, 17), "Outer radius:", sizeStyle="small"
		)
		self.w.radiusSlider = vanilla.Slider(
			(120, y - 2, 150, 20),
			minValue=0, maxValue=200, value=30,
			continuous=True, callback=self.sliderChanged,
			sizeStyle="small",
		)
		self.w.radiusField = vanilla.EditText(
			(276, y - 2, 44, 20), "30", sizeStyle="small",
			callback=self.fieldChanged,
		)
		y += sp + 4

		# ── Inner radius ────────────────────────────────────
		self.w.roundInner = vanilla.CheckBox(
			(15, y, 160, 17), "Round inner corners",
			sizeStyle="small", value=False,
			callback=self.toggleInner,
		)
		y += sp - 4
		self.w.labelInner = vanilla.TextBox(
			(15, y, 100, 17), "Inner radius:", sizeStyle="small"
		)
		self.w.innerSlider = vanilla.Slider(
			(120, y - 2, 150, 20),
			minValue=0, maxValue=200, value=20,
			continuous=True, callback=self.innerSliderChanged,
			sizeStyle="small",
		)
		self.w.innerField = vanilla.EditText(
			(276, y - 2, 44, 20), "20", sizeStyle="small",
			callback=self.innerFieldChanged,
		)
		y += sp + 8

		# ── Adaptation ──────────────────────────────────────
		self.w.labelAdapt = vanilla.TextBox(
			(15, y, -10, 34),
			"Angle adaptation (0 = uniform, 1 = strong):",
			sizeStyle="small",
		)
		y += 20
		self.w.adaptSlider = vanilla.Slider(
			(15, y - 2, 250, 20),
			minValue=0, maxValue=1.0, value=0.4,
			continuous=True, callback=self.adaptSliderChanged,
			sizeStyle="small",
		)
		self.w.adaptField = vanilla.EditText(
			(276, y - 2, 44, 20), "0.40", sizeStyle="small",
			callback=self.adaptFieldChanged,
		)
		y += sp + 10

		# ── Divider ─────────────────────────────────────────
		self.w.div1 = vanilla.HorizontalLine((15, y, -15, 1))
		y += 12

		# ── Scope ───────────────────────────────────────────
		self.w.labelScope = vanilla.TextBox(
			(15, y, 200, 17), "Apply to:", sizeStyle="small"
		)
		y += 20
		self.w.scope = vanilla.RadioGroup(
			(15, y, -15, 60),
			["Selected nodes only",
			 "Current glyph (all corners)",
			 "All glyphs in font"],
			sizeStyle="small",
		)
		self.w.scope.set(0)
		y += 68

		# ── Divider ─────────────────────────────────────────
		self.w.div2 = vanilla.HorizontalLine((15, y, -15, 1))
		y += 12

		# ── Per-node tag ────────────────────────────────────
		self.w.labelTag = vanilla.TextBox(
			(15, y, -10, 17),
			"Per-node radius override:", sizeStyle="small"
		)
		y += 22
		self.w.tagField = vanilla.EditText(
			(15, y, 55, 20), "50", sizeStyle="small"
		)
		self.w.tagButton = vanilla.Button(
			(76, y, 108, 20), "Tag selected",
			sizeStyle="small", callback=self.tagNodes,
		)
		self.w.clearTagButton = vanilla.Button(
			(190, y, 108, 20), "Clear tags",
			sizeStyle="small", callback=self.clearTags,
		)
		y += sp + 14

		# ── Action buttons ──────────────────────────────────
		self.w.applyButton = vanilla.Button(
			(15, -42, 145, 26), "Apply rounding",
			callback=self.applyRounding,
		)
		self.w.closeButton = vanilla.Button(
			(170, -42, 145, 26), "Close",
			callback=self.closeWindow,
		)

		# initial state
		self.toggleInner(None)

		# Clean up callback when window closes
		self.w.bind("close", self.onClose)
		self.w.open()
		self.w.center()

	# ────────────────────────────────────────────────────────
	# Preview drawing callback
	# ────────────────────────────────────────────────────────

	def drawPreview(self, layer, info):
		try:
			if not self.preview_active:
				return
			if self.preview_layer is None:
				return

			bp = self.preview_layer.bezierPath
			if bp is None:
				return

			# Translucent teal fill
			NSColor.colorWithCalibratedRed_green_blue_alpha_(
				0.0, 0.75, 0.72, 0.28
			).set()
			bp.fill()

			# Darker outline
			NSColor.colorWithCalibratedRed_green_blue_alpha_(
				0.0, 0.55, 0.52, 0.7
			).set()
			bp.setLineWidth_(1.0)
			bp.stroke()

		except:
			print(traceback.format_exc())

	# ────────────────────────────────────────────────────────
	# Refresh preview from current slider values
	# ────────────────────────────────────────────────────────

	def refreshPreview(self):
		if not self.preview_active:
			self.preview_layer = None
			return
		font = Glyphs.font
		if not font or not font.selectedLayers:
			self.preview_layer = None
			return

		source = font.selectedLayers[0]
		base_r = self.w.radiusSlider.get()
		adapt = self.w.adaptSlider.get()
		do_inner = self.w.roundInner.get()
		inner_r = self.w.innerSlider.get() if do_inner else 0
		scope = self.w.scope.get()
		only_sel = (scope == 0)

		try:
			self.preview_layer = make_preview_layer(
				source, base_r, adapt, do_inner, inner_r, only_sel
			)
		except:
			print(traceback.format_exc())
			self.preview_layer = None

		Glyphs.redraw()

	# ────────────────────────────────────────────────────────
	# Toggle preview on / off
	# ────────────────────────────────────────────────────────

	def togglePreview(self, sender):
		if sender.get():
			self.preview_active = True
			Glyphs.addCallback(self.drawPreview, DRAWFOREGROUND)
			self.refreshPreview()
		else:
			self.preview_active = False
			self.preview_layer = None
			try:
				Glyphs.removeCallback(self.drawPreview)
			except:
				pass
			Glyphs.redraw()

	# ────────────────────────────────────────────────────────
	# Slider / field sync  (all trigger preview refresh)
	# ────────────────────────────────────────────────────────

	def sliderChanged(self, sender):
		self.w.radiusField.set("%g" % round(sender.get(), 1))
		self.refreshPreview()

	def fieldChanged(self, sender):
		try:
			v = float(sender.get())
			self.w.radiusSlider.set(v)
			self.refreshPreview()
		except:
			pass

	def innerSliderChanged(self, sender):
		self.w.innerField.set("%g" % round(sender.get(), 1))
		self.refreshPreview()

	def innerFieldChanged(self, sender):
		try:
			v = float(sender.get())
			self.w.innerSlider.set(v)
			self.refreshPreview()
		except:
			pass

	def adaptSliderChanged(self, sender):
		self.w.adaptField.set("%.2f" % sender.get())
		self.refreshPreview()

	def adaptFieldChanged(self, sender):
		try:
			v = float(sender.get())
			self.w.adaptSlider.set(v)
			self.refreshPreview()
		except:
			pass

	def toggleInner(self, sender):
		enabled = bool(self.w.roundInner.get())
		self.w.innerSlider.enable(enabled)
		self.w.innerField.enable(enabled)
		self.refreshPreview()

	# ────────────────────────────────────────────────────────
	# Per-node tagging
	# ────────────────────────────────────────────────────────

	def tagNodes(self, sender):
		try:
			val = float(self.w.tagField.get())
		except:
			Message("Invalid number", "Enter a valid radius number.")
			return
		n = tag_selected_nodes(val)
		Glyphs.showNotification(
			"Smart Round Corners",
			"Tagged %d node%s with radius %g." % (n, "" if n == 1 else "s", val)
		)
		self.refreshPreview()

	def clearTags(self, sender):
		n = clear_tags_selected()
		Glyphs.showNotification(
			"Smart Round Corners",
			"Cleared tags from %d node%s." % (n, "" if n == 1 else "s")
		)
		self.refreshPreview()

	# ────────────────────────────────────────────────────────
	# Apply rounding (destructive — writes to actual layer)
	# ────────────────────────────────────────────────────────

	def applyRounding(self, sender):
		font = Glyphs.font
		if not font:
			Message("No font open", "Please open a font first.")
			return

		base_r = self.w.radiusSlider.get()
		do_inner = self.w.roundInner.get()
		inner_r = self.w.innerSlider.get() if do_inner else 0
		adapt = self.w.adaptSlider.get()
		scope = self.w.scope.get()
		total = 0

		try:
			if scope == 0:
				layer = font.selectedLayers[0]
				layer.parent.beginUndo()
				total = process_layer(
					layer, base_r, adapt, do_inner, inner_r,
					only_selected=True,
				)
				layer.parent.endUndo()

			elif scope == 1:
				layer = font.selectedLayers[0]
				layer.parent.beginUndo()
				total = process_layer(
					layer, base_r, adapt, do_inner, inner_r,
					only_selected=False,
				)
				layer.parent.endUndo()

			elif scope == 2:
				font.disableUpdateInterface()
				for glyph in font.glyphs:
					mid = font.selectedFontMaster.id
					layer = glyph.layers[mid]
					if layer is None:
						continue
					glyph.beginUndo()
					total += process_layer(
						layer, base_r, adapt, do_inner, inner_r,
						only_selected=False,
					)
					glyph.endUndo()
				font.enableUpdateInterface()

		except Exception as e:
			print("Smart Round Corners error:\n%s" % traceback.format_exc())
			Message("Error", "Something went wrong:\n%s" % str(e))
			return

		# Turn off preview after applying
		self.w.previewCheck.set(False)
		self.togglePreview(self.w.previewCheck)

		Glyphs.showNotification(
			"Smart Round Corners",
			"Rounded %d corner%s." % (total, "" if total == 1 else "s")
		)

	# ────────────────────────────────────────────────────────
	# Cleanup
	# ────────────────────────────────────────────────────────

	def closeWindow(self, sender):
		self.w.close()

	def onClose(self, sender):
		self.preview_active = False
		self.preview_layer = None
		try:
			Glyphs.removeCallback(self.drawPreview)
		except:
			pass
		Glyphs.redraw()


# ————————————————————————————————————————————————————————————————
# Run
# ————————————————————————————————————————————————————————————————
SmartRoundCornersDialog()
