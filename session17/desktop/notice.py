#!/usr/bin/env python3
"""お知らせのダイアログを出す（第6節で、作業中に割り込むポップアップに使う）。

    notice タイトル 本文

GTK3 で作る。GTK4 のアプリ（zenity 4 など）は、AT-SPI に画面上の位置を正しく返さないため使わない。
"""

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

title, text = sys.argv[1], sys.argv[2]
dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text=title)
dialog.set_title(title)
dialog.format_secondary_text(text)
dialog.set_keep_above(True)
dialog.set_position(Gtk.WindowPosition.CENTER)
dialog.run()
