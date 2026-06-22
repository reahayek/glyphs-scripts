# MenuTitle: Rename to Standard Glyphs Names
# -*- coding: utf-8 -*-
"""
Renames glyphs in three passes:

PASS 1 — uni-named glyphs (have Unicode via their name):
  uni0628        → ba-ar (or whatever Glyphs.glyphInfoForUnicode returns)
  uni0628.fina   → ba-ar.fina
  uni06440622    → lam-ar_alefMadda-ar  (ligatures)

PASS 2 — non-uni glyphs that have a Unicode value set:
  kasra_01       → looks up glyph.unicode → Glyphs.glyphInfoForUnicode
  veh.fina       → same
  allah, riyal   → same

PASS 3 — no-Unicode component glyphs:
  Uses Glyphs.glyphInfoForName() first.
  Falls back to the manual table below if Glyphs doesn't know the name.
  Anything still unknown is reported for manual review.
"""

import re
from GlyphsApp import *

font = Glyphs.font
if not font:
    print("ERROR: No font open.")
    import sys; sys.exit()

Glyphs.clearLog()
print("=== Rename to Standard Glyphs Names ===\n")


# ─── Manual table for known component glyphs with no Unicode ─────────────────
# Add or adjust entries here as needed.
# Key = current glyph name  |  Value = desired new name

MANUAL_TABLE = {
    # ── Dot components ───────────────────────────────────────────────────────
    "onedot.above":                 "_oneDotAbove",
    "onedot.below":                 "_oneDotBelow",
    "twodots.above":                "_twoDotAbove",
    "twodots.below":                "_twoDotBelow",
    "twodots.small.above":          "_twoDotSmall.above",
    "twodots.small.below":          "_twoDotSmall.below",
    "twodots.vert.above":           "_twoDotVert.above",
    "twodots.vert.below":           "_twoDotVert.below",
    "twodots.vert.small.above":     "_twoDotVertSmall.above",
    "twodots.vert.small.below":     "_twoDotVertSmall.below",
    "twodots.vert_alt1.below":      "_twoDotVert.below.alt1",
    "twodots_alt1.above":           "_twoDotAbove.alt1",
    "twodots_alt1.below":           "_twoDotBelow.alt1",
    "threedots.above":              "_threeDotAbove",
    "threedots.below":              "_threeDotBelow",
    "threedots.small.above":        "_threeDotSmall.above",
    "threedots.small.below":        "_threeDotSmall.below",
    "threedots.horz.below":         "_threeDotHorz.below",
    "threedots.horz_alt1.below":    "_threeDotHorz.below.alt1",
    "threedots.rev.above":          "_threeDotRev.above",
    "threedots.rev.below":          "_threeDotRev.below",
    "threedots.rev_alt1.below":     "_threeDotRev.below.alt1",
    "threedots.rev_alt2.below":     "_threeDotRev.below.alt2",
    "threedots_alt1.above":         "_threeDotAbove.alt1",
    "threedots_alt1.below":         "_threeDotBelow.alt1",
    "threedots_alt2.above":         "_threeDotAbove.alt2",
    "threedots_alt2.below":         "_threeDotBelow.alt2",
    "fourdots.above":               "_fourDotAbove",
    "fourdots.below":               "_fourDotBelow",
    # ── Small marks / special shapes ─────────────────────────────────────────
    "smallv.arabic":                "_smallVAbove-ar",
    "circumflex.arabic":            "_circumflex-ar",
    # ── Utility / drawing helpers ─────────────────────────────────────────────
    "diagonal":                     "_diagonal",
    "diagonal2":                    "_diagonal2",
    # ── Named alternates without Unicode ─────────────────────────────────────
    "wasla":                        "wasla-ar",
    "hamza_medial":                 "hamzaMedial-ar",
    "wavyhamza_above":              "wavyHamza.above-ar",
    "wavyhamza_below":              "wavyHamza.below-ar",
    "alef_alt.fina":                "alef-ar.fina.alt",
    "alef_alt.isol":                "alef-ar.alt",
    "beh_dotless_alt.init":         "behDotless-ar.init.alt",
    "beh_dotless_alt.medi":         "behDotless-ar.medi.alt",
    "feh_dotless.isol":             "fehDotless-ar.alt",
    "hah_alt.fina":                 "hah-ar.fina.alt",
    "hah_alt.isol":                 "hah-ar.alt",
    "heh_ae.fina":                  "hehGoal-ar.fina.alt",
    # ── Non-standard naming ───────────────────────────────────────────────────
    "Ghunna_above":                 "ghunna-ar",
    "nonmarkingreturn":             "nonmarkingreturn",  # keep
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Arabic mark components that form camelCase ligature names (not consonant ligatures).
# e.g. hamzaabove_damma-ar → hamzaaboveDamma-ar
# Consonant ligatures like lam_alef-ar keep their underscore.
ARABIC_MARK_PREFIXES = {
    "hamzaabove", "hamzabelow", "shadda", "superscriptalef",
    "maddaabove", "smallhighseen", "smallhighroundedzero",
    "smallhighquranicyaseen", "smallhighuninhabited",
}


def to_camelcase_mark(name):
    """
    Convert Arabic mark-combination names from underscore to camelCase.
      'hamzaabove_damma-ar'    →  'hamzaaboveDamma-ar'
      'hamzabelow_kasratan-ar' →  'hamzabelowKasratan-ar'
    Only applies when the first component is a known Arabic mark prefix.
    Preserves language suffix (-ar) and form suffix (.fina etc.).
    Returns None if the pattern doesn't apply.
    """
    m = re.match(r'^([A-Za-z]+)_([a-z][A-Za-z]*)(-[a-z]+)?(\..*)?$', name)
    if not m:
        return None
    p1, p2, lang, suf = m.groups()
    if p1.lower() not in ARABIC_MARK_PREFIXES:
        return None
    lang = lang or ""
    suf  = suf  or ""
    return p1 + p2[0].upper() + p2[1:] + lang + suf


def standard_name_for_unicode_str(hex4):
    """Return Glyphs standard name for a 4-digit hex string, or None."""
    info = Glyphs.glyphInfoForUnicode(hex4.upper())
    if info and info.name:
        return info.name
    return None


def build_name_from_uni_string(uni_str_raw):
    """
    Given a raw name like 'uni0628' or 'uni06440622', return
    the Glyphs standard name, or None if it can't be resolved.
    """
    m = re.match(r'^(uni[0-9A-Fa-f]+)((?:\.[A-Za-z0-9_]+)*)$', uni_str_raw)
    if not m:
        return None
    hex_digits = m.group(1)[3:]
    suffix     = m.group(2)

    if not re.match(r'^[0-9A-Fa-f]+$', hex_digits):
        return None
    if len(hex_digits) % 4 != 0:
        return None

    chunks = [hex_digits[i:i+4] for i in range(0, len(hex_digits), 4)]
    parts  = []
    for chunk in chunks:
        n = standard_name_for_unicode_str(chunk)
        parts.append(n if n else "uni" + chunk.upper())

    return "_".join(parts) + suffix


def standard_name_for_glyph_unicode(glyph):
    """
    Given a glyph object, use its primary unicode value to look up
    the Glyphs standard name.  Returns None if no unicode or no match.
    Handles both int and hex-string unicode values (Glyphs 3 returns strings).
    """
    unis = glyph.unicodes          # list of int or hex string depending on Glyphs version
    if not unis:
        return None
    u = unis[0]
    if isinstance(u, int):
        hex4 = format(u, "04X")
    else:
        hex4 = str(u).upper().zfill(4)
    return standard_name_for_unicode_str(hex4)


# ─── Build rename map ─────────────────────────────────────────────────────────

rename_map   = {}    # old_name → new_name
current_names = set(g.name for g in font.glyphs)

for glyph in font.glyphs:
    old = glyph.name
    new = None

    # ── PASS 1: uni-named glyphs ─────────────────────────────────────────────
    if re.match(r'^uni[0-9A-Fa-f]', old):
        new = build_name_from_uni_string(old)

    # ── PASS 2: non-uni glyphs that have a Unicode value ─────────────────────
    elif glyph.unicodes:
        candidate = standard_name_for_glyph_unicode(glyph)
        if candidate and candidate != old:
            new = candidate

    # ── PASS 3: no Unicode — try Glyphs DB, then manual table ────────────────
    else:
        # Strip suffix for Glyphs DB lookup
        base = old.split(".")[0] if "." in old else old
        info = Glyphs.glyphInfoForName(base)
        db_match = None
        if info and info.name and info.name != base:
            # Guard: reject if DB result belongs to a different script than the glyph.
            # e.g. "alef_alt" matches a Hebrew glyph — wrong for an Arabic font.
            info_script  = getattr(info, "script", None) or ""
            glyph_script = getattr(glyph, "script", None) or ""
            if glyph_script and info_script and glyph_script != info_script:
                pass   # script mismatch — ignore DB result
            else:
                suffix   = old[len(base):]
                db_match = info.name + suffix
        if db_match and db_match != old:
            new = db_match
        elif old in MANUAL_TABLE and MANUAL_TABLE[old] != old:
            new = MANUAL_TABLE[old]

    # ── camelCase fixup: mark+mark combinations use camelCase, not underscore ──
    # Applies to whatever name Passes 1-3 produced, AND to existing names
    # already in the font that weren't caught above (e.g. hamzabelow_kasratan-ar).
    check = new if new else old
    if "_" in check:
        cc = to_camelcase_mark(check)
        if cc and cc != old:
            new = cc

    if new and new != old:
        rename_map[old] = new

# ─── Conflict check ───────────────────────────────────────────────────────────

conflicts = {}
for old, new in list(rename_map.items()):
    if new in current_names and new not in rename_map:
        conflicts[old] = new
        del rename_map[old]

# ─── Report ───────────────────────────────────────────────────────────────────

print(f"Renames planned: {len(rename_map)}")
if conflicts:
    print(f"Skipped (name conflict): {len(conflicts)}")

print()
for old, new in sorted(rename_map.items()):
    print(f"  {old}  →  {new}")

if conflicts:
    print("\n--- SKIPPED (conflict — target name already exists) ---")
    for old, new in sorted(conflicts.items()):
        print(f"  {old}  →  {new}")

# ─── Identify unmapped no-Unicode glyphs ─────────────────────────────────────
# Only flag glyphs that are NOT already correctly named per the Glyphs DB.
# Glyphs like `ain-ar.fina` are already correct — skip them silently.

unmapped = []
for glyph in font.glyphs:
    if not glyph.unicodes and not re.match(r'^uni[0-9A-Fa-f]', glyph.name):
        if glyph.name not in rename_map and glyph.name not in MANUAL_TABLE:
            # Check if the current name is already the Glyphs standard name
            base   = glyph.name.split(".")[0] if "." in glyph.name else glyph.name
            suffix = glyph.name[len(base):]
            info   = Glyphs.glyphInfoForName(base)
            if info and info.name and (info.name + suffix) == glyph.name:
                continue   # already correctly named — skip
            unmapped.append(glyph.name)

if unmapped:
    print(f"\n--- UNMAPPED (no Unicode, not in manual table — review manually) ---")
    for n in sorted(unmapped):
        print(f"  {n}")

# ─── Apply renames ────────────────────────────────────────────────────────────

font.disableUpdateInterface()

# Sort: base glyphs first (no form suffix), then form variants
def sort_key(item):
    old, new = item
    has_suffix = "." in new.split("-ar")[-1] or (
        new.count(".") > 0 and not new.endswith("-ar"))
    return (1 if has_suffix else 0, old)

applied = 0
errors  = []

for old, new in sorted(rename_map.items(), key=sort_key):
    g = font.glyphs[old]
    if not g:
        errors.append(f"  NOT FOUND: {old}")
        continue
    try:
        g.name = new
        applied += 1
    except Exception as e:
        errors.append(f"  ERROR {old} → {new}: {e}")

font.enableUpdateInterface()

# ─── Summary ──────────────────────────────────────────────────────────────────

print(f"\n✅ Applied: {applied} renames")
if errors:
    print(f"\n⚠️  Errors ({len(errors)}):")
    for e in errors: print(e)
if conflicts:
    print(f"\n⚠️  {len(conflicts)} skipped (conflicts) — review manually")
if unmapped:
    print(f"\n⚠️  {len(unmapped)} unmapped no-Unicode glyphs — see list above")

print("\nDone. Save the font to apply.")
