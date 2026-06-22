# MenuTitle: Open Arabic Init & Non-Connecting (No .fina/.medi) Letters
# -*- coding: utf-8 -*-
from GlyphsApp import Glyphs

font = Glyphs.font
if not font:
    raise RuntimeError("No font open.")

def is_target_arabic_letter(g):
    if not g:
        return False
    # Arabic script only
    if (g.script or "") != "arabic":
        return False
    # Keep only letters (exclude marks, numbers, punctuation, etc.)
    if (g.category or "") != "Letter":
        return False
    # Exclude final and medial forms
    n = g.name or ""
    if ".fina" in n or ".medi" in n:
        return False
    return True

targets = [g for g in font.glyphs if is_target_arabic_letter(g)]

if not targets:
    Glyphs.showNotification("Arabic Filter", "No matching glyphs found.")
else:
    tab_string = " ".join("/" + g.name for g in targets)
    font.newTab(tab_string)
