# -*- coding: utf-8 -*-
# MenuTitle: Kerning proof maker
# App: Glyphs
# GlyphsVersion: 3.0
# Description: Inserts /space between items in the current Edit tab, then prompts for a prefix glyph name and inserts it before every non-space glyph.
# Author: ChatGPT (per user request)

# -*- coding: utf-8 -*-
"""
1) Puts /space between glyphs in the current Edit tab while preserving line breaks.
2) Then inserts a chosen prefix glyph before every non-space glyph.
3) Prompts for the prefix glyph name at runtime.
"""

from GlyphsApp import *
from AppKit import NSAlert, NSTextField, NSMakeRect, NSAlertFirstButtonReturn

# ===== UI prompt =====
def ask_prefix_name(default_value="reh-ar"):
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Prefix glyph name")
    alert.setInformativeText_("Enter the glyph name to insert before each non-space item in the current Edit tab.")
    alert.addButtonWithTitle_("OK")
    alert.addButtonWithTitle_("Cancel")

    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
    field.setStringValue_(default_value)
    alert.setAccessoryView_(field)

    response = alert.runModal()
    if response == NSAlertFirstButtonReturn:
        return field.stringValue().strip()
    return None

def is_space_name(n):
    if not n:
        return False
    nlow = n.lower()
    return nlow.startswith("space") or nlow in {"uni0020"}

# ===== main =====
font = Glyphs.font
tab = font.currentTab if font else None

if not tab:
    Glyphs.showNotification("Space + Prefix", "اول یک Edit Tab باز کن.")
else:
    prefix_name = ask_prefix_name("reh-ar")
    if not prefix_name:
        Glyphs.showNotification("Space + Prefix", "نام گلیف پیشوند وارد نشد.")
    elif prefix_name not in font.glyphs:
        Glyphs.showNotification("Space + Prefix", f"گلیف پیشوند پیدا نشد: {prefix_name}")
    else:
        originalDir = tab.direction
        try:
            if originalDir == RTL:
                tab.direction = LTR  # for /glyph notation

            parts = []
            newLine = True

            for layer in tab.layers:
                if not hasattr(layer, "parent"):
                    parts.append("\n")
                    newLine = True
                    continue

                g = layer.parent
                if not g or not g.name:
                    continue

                if not newLine:
                    parts.append("/space")

                if is_space_name(g.name):
                    parts.append(f"/{g.name}")
                else:
                    parts.append(f"/{prefix_name}/{g.name}")

                newLine = False

            tab.text = "".join(parts)

        finally:
            tab.direction = originalDir

        print("Done.")
