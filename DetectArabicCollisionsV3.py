# MenuTitle: Detect Arabic Collisions v3

from vanilla import FloatingWindow, PopUpButton, Button, TextBox
from Foundation import NSAutoreleasePool

font = Glyphs.font
if not font:
	Message("No font open.", title="Detect Arabic Collisions v3")
elif not font.masters:
	Message("No masters found.", title="Detect Arabic Collisions v3")
else:
	masterNames = [m.name for m in font.masters]

	def getJoiningType(glyph):
		"""Determine joining type from available contextual forms."""
		name = glyph.name
		baseName = name.split(".")[0] if "." in name else name
		hasInit = font.glyphs[baseName + ".init"] is not None
		hasFina = font.glyphs[baseName + ".fina"] is not None
		if hasInit and hasFina:
			return "D"
		elif hasFina and not hasInit:
			return "R"
		else:
			return "U"

	def getContextualPairs(gA, gB):
		"""Return ONLY non-connected pair forms where collision is unintentional.
		Connected forms overlap by design at join points — skip those."""
		baseA = gA.name.split(".")[0] if "." in gA.name else gA.name
		baseB = gB.name.split(".")[0] if "." in gB.name else gB.name
		joinA = getJoiningType(gA)
		joinB = getJoiningType(gB)

		pairs = []

		# A=.isol + B=.isol (both standalone)
		pairs.append((gA.name, gB.name))

		# A=.fina + B=.isol (A ends a group, B standalone)
		if joinA in ("D", "R"):
			finaA = font.glyphs[baseA + ".fina"]
			if finaA:
				pairs.append((finaA.name, gB.name))

		# A=.isol + B=.init (A standalone, B starts new group)
		if joinB == "D":
			initB = font.glyphs[baseB + ".init"]
			if initB:
				pairs.append((gA.name, initB.name))

		# A=.fina + B=.init (A ends group, B starts new group)
		if joinA in ("D", "R") and joinB == "D":
			finaA = font.glyphs[baseA + ".fina"]
			initB = font.glyphs[baseB + ".init"]
			if finaA and initB:
				pairs.append((finaA.name, initB.name))

		# Deduplicate
		seen = set()
		unique = []
		for p in pairs:
			if p not in seen:
				seen.add(p)
				unique.append(p)
		return unique

	def getKernRTL(mkRTL, gA, gB):
		"""Get RTL kerning from raw dict using ObjC objectForKey_.
		RTL keys: first glyph (rightmost) uses @MMK_R_ + leftKerningGroup,
		second glyph (leftmost) uses @MMK_L_ + rightKerningGroup."""
		if mkRTL is None:
			return 0.0

		leftKeys = [gA.name, gA.id]
		if gA.leftKerningGroup:
			leftKeys.append("@MMK_R_" + gA.leftKerningGroup)
		rightKeys = [gB.name, gB.id]
		if gB.rightKerningGroup:
			rightKeys.append("@MMK_L_" + gB.rightKerningGroup)

		for lk in leftKeys:
			try:
				subDict = mkRTL.objectForKey_(lk)
			except:
				subDict = None
			if subDict is None:
				continue
			for rk in rightKeys:
				try:
					val = subDict.objectForKey_(rk)
				except:
					val = None
				if val is not None:
					try:
						return float(val)
					except:
						pass
		return 0.0

	def getKernForPair(masterId, mkRTL, gA, gB):
		"""Try kerningForPair with GSRTL first, fallback to raw dict."""
		# Method 1: kerningForPair with GSRTL direction
		try:
			v = font.kerningForPair(masterId, gA.name, gB.name, GSRTL)
			if v is not None and abs(v) < 9000:
				return float(v)
		except:
			pass

		# Method 2: raw dict lookup
		return getKernRTL(mkRTL, gA, gB)

	# Collect base Arabic letter glyphs
	arabic_glyphs = []
	seen = set()
	for glyph in font.glyphs:
		if not glyph.export:
			continue
		if glyph.name in seen:
			continue
		if glyph.script != "arabic":
			continue
		if glyph.category != "Letter":
			continue
		name = glyph.name
		if ".init" in name or ".medi" in name or ".fina" in name:
			continue
		seen.add(name)
		arabic_glyphs.append(glyph)

	if not arabic_glyphs:
		Message("No Arabic letter glyphs found.")
	else:
		totalGlyphs = len(arabic_glyphs)

		class CollisionDetector:
			def __init__(self):
				self.w = FloatingWindow((350, 130),
					"Arabic Collisions v3 — %d base glyphs" % totalGlyphs)
				self.w.masterLabel = TextBox((15, 12, 80, 20), "Master:")
				self.w.masterPop = PopUpButton((95, 10, -15, 25), masterNames)
				self.w.info = TextBox((15, 45, -15, 20),
					"Shaped pairs + RTL kerning + removeOverlap",
					sizeStyle="small")
				self.w.runBtn = Button((15, 80, -15, 30),
					"Run Detection", callback=self.run)
				self.w.open()

			def run(self, sender):
				sender.enable(False)
				Glyphs.clearLog()
				Glyphs.showMacroWindow()

				masterIdx = self.w.masterPop.get()
				master = font.masters[masterIdx]
				masterId = master.id
				print("Master: %s" % master.name)

				# RTL kerning dict
				mkRTL = None
				try:
					mkRTL = font.kerningRTL.get(masterId)
				except:
					try:
						rtlDict = font.pyobjc_instanceMethods.kerningRTL()
						if rtlDict:
							mkRTL = rtlDict.objectForKey_(masterId)
					except:
						pass
				print("  RTL kerning: %s" % ("found" if mkRTL else "none"))

				# Debug: verify kerning works
				rehG = font.glyphs["reh-ar"]
				if rehG:
					testKern = getKernForPair(masterId, mkRTL, rehG, rehG)
					print("  DEBUG: reh-ar + reh-ar kern = %s" % testKern)

				# Phase 1: pre-clean ALL Arabic glyph forms
				self.w.info.set("Preparing glyphs...")
				print("Phase 1: pre-cleaning all Arabic glyph forms...")

				pool = NSAutoreleasePool.alloc().init()
				cleanCache = {}
				for g in font.glyphs:
					if not g.export:
						continue
					if g.script != "arabic":
						continue
					layer = g.layers[masterId]
					if layer is None:
						continue
					bp = layer.completeBezierPath
					if bp is None or bp.isEmpty():
						continue
					clean = layer.copyDecomposedLayer()
					clean.removeOverlap()
					w = float(layer.width)
					r = bp.bounds()
					bounds = (r.origin.x, r.origin.y,
					          r.origin.x + r.size.width,
					          r.origin.y + r.size.height)
					cleanCache[g.name] = (clean, w, bounds)
				del pool
				print("  Cleaned %d glyph forms" % len(cleanCache))

				# Phase 2: generate non-connected contextual pairs
				self.w.info.set("Generating contextual pairs...")
				print("Phase 2: generating non-connected contextual pairs...")

				allPairs = []
				for gA in arabic_glyphs:
					for gB in arabic_glyphs:
						ctxPairs = getContextualPairs(gA, gB)
						for formA, formB in ctxPairs:
							if formA in cleanCache and formB in cleanCache:
								allPairs.append((formA, formB))

				# Deduplicate
				seenForms = set()
				uniquePairs = []
				for formA, formB in allPairs:
					key = (formA, formB)
					if key not in seenForms:
						seenForms.add(key)
						uniquePairs.append((formA, formB))

				print("  %d unique non-connected pairs" % len(uniquePairs))

				# Phase 3: collision check with RTL kerning + removeOverlap
				self.w.info.set("Checking %d pairs..." % len(uniquePairs))
				print("Phase 3: checking collisions...")

				collisions = []
				checked = 0

				for formA, formB in uniquePairs:
					pool = NSAutoreleasePool.alloc().init()
					checked += 1

					cleanA, wA, boundsA = cleanCache[formA]
					cleanB, wB, boundsB = cleanCache[formB]

					# RTL kerning using correct API
					gA = font.glyphs[formA]
					gB = font.glyphs[formB]
					kern = getKernForPair(masterId, mkRTL, gA, gB)

					# RTL: B at x=0, A at x = wB + kern
					dx = wB + kern

					# Bbox pre-filter (>20 units overlap in both axes)
					aLeft = boundsA[0] + dx
					aRight = boundsA[2] + dx
					overlapX = min(aRight, boundsB[2]) - max(aLeft, boundsB[0])
					if overlapX <= 20:
						del pool
						continue
					overlapY = min(boundsA[3], boundsB[3]) - max(boundsA[1], boundsB[1])
					if overlapY <= 20:
						del pool
						continue

					# removeOverlap collision check
					tempLayer = GSLayer()
					for path in cleanB.paths:
						tempLayer.shapes.append(path.copy())
					for path in cleanA.paths:
						pc = path.copy()
						pc.applyTransform((1, 0, 0, 1, dx, 0))
						tempLayer.shapes.append(pc)

					nodesBefore = sum(len(p.nodes) for p in tempLayer.paths)
					tempLayer.removeOverlap()
					nodesAfter = sum(len(p.nodes) for p in tempLayer.paths)

					if nodesAfter != nodesBefore:
						collisions.append((formA, formB, kern))

					del pool

					if checked % 200 == 0:
						print("  checked %d / %d, %d collisions" % (
							checked, len(uniquePairs), len(collisions)))

				print("=" * 40)
				print("Done! %d collisions found" % len(collisions))

				if not collisions:
					self.w.info.set("No collisions found.")
					sender.enable(True)
					Message("No collisions for master '%s'." % master.name,
						title="Detect Arabic Collisions v3")
					return

				# Open tabs
				sp = "/space"
				chunk_size = 600
				chunks = []
				current = []
				for formA, formB, kv in collisions:
					current.append(sp + "/" + formA + "/" + formB + sp)
					if len(current) >= chunk_size:
						chunks.append("".join(current))
						current = []
				if current:
					chunks.append("".join(current))

				for chunk_text in chunks:
					font.newTab(chunk_text)

				self.w.info.set("Done! %d collisions in %d tab(s)" % (
					len(collisions), len(chunks)))
				sender.enable(True)
				print("Opened %d tab(s)" % len(chunks))

				print("")
				for formA, formB, kv in collisions[:30]:
					print("  %s + %s (kern=%d)" % (formA, formB, int(kv)))

		CollisionDetector()
