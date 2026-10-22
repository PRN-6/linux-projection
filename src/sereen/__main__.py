from __future__ import annotations

import sys
from .gui import SereenWindow
from gi.repository import Gtk, Adw

def main():
    # If an argument is passed, we might want to keep the CLI,
    # but for the "App", we launch the GUI.
    app = Adw.Application(application_id="com.sereen.projector",
                          flags=Adw.ApplicationFlags.FLAGS_NONE)

    def on_activate(app):
        win = SereenWindow(application=app)
        win.present()

    app.connect("activate", on_activate)
    app.run(sys.argv[1:])

if __name__ == "__main__":
    main()
