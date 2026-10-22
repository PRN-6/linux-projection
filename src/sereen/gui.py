"""GUI Application for Sereen.

This module implements the GTK4 desktop interface for discovering
and controlling Epson projectors.
"""

from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi import Gtk, Adw

import threading
from typing import Optional

from .discovery import scan_network, ScanOptions
from .control.factory import open_session
from .models import Projector

class ProjectorRow(Gtk.ListBoxRow):
    """A custom row for the projector list."""
    def __init__(self, projector: Projector):
        super().__init__()
        self.projector = projector

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        label = Gtk.Label(label=projector.display_name)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)

        proto_label = Gtk.Label(label=projector.protocol.value)
        proto_label.add_css_class("caption")

        box.append(label)
        box.append(proto_label)
        self.set_child(box)

class SereenWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Sereen - Epson Projector Control")
        self.set_default_size(900, 600)

        self.current_session = None
        self.current_projector = None

        # Main Layout: Split View
        split_view = Adw.NavigationSplitView()

        # --- Sidebar (Projector List) ---
        sidebar_page = Adw.NavigationPage()
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        header = Adw.HeaderBar()
        scan_btn = Gtk.Button(icon_name="system-search-symbolic", tooltip_text="Scan Network")
        scan_btn.connect("clicked", self.on_scan_clicked)
        header.pack_start(scan_btn)

        self.projector_list = Gtk.ListBox()
        self.projector_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.projector_list.connect("row-selected", self.on_projector_selected)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.projector_list)

        sidebar_box.append(header)
        sidebar_box.append(scrolled)
        sidebar_page.set_child(sidebar_box)

        # --- Content (Control Panel) ---
        content_page = Adw.NavigationPage()
        self.control_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.control_panel.set_valign(Gtk.Align.CENTER)
        self.control_panel.set_halign(Gtk.Align.CENTER)
        self.control_panel.set_margin_all(30)

        # Status Label
        self.status_label = Gtk.Label(label="Select a projector to start")
        self.status_label.add_css_class("title-2")
        self.control_panel.append(self.status_label)

        # Control Grid
        grid = Gtk.Grid(column_spacing=20, row_spacing=20, halign=Gtk.Align.CENTER)

        # Power Buttons
        pwr_on = Gtk.Button(label="Power ON")
        pwr_on.connect("clicked", self.on_power_on)
        pwr_on.add_css_class("suggested-action")

        pwr_off = Gtk.Button(label="Power OFF")
        pwr_off.connect("clicked", self.on_power_off)

        # Input Buttons
        self.input_btn = Gtk.Button(label="Set HDMI 1")
        self.input_btn.connect("clicked", self.on_set_input)

        # Volume
        self.vol_adj = Gtk.Adjustment(value=50, lower=0, upper=100, step_increment=1)
        vol_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.vol_adj)
        vol_scale.set_hexpand(True)
        vol_scale.set_range(0, 100)
        vol_scale.connect("value-changed", self.on_volume_changed)

        # Cast Button
        cast_btn = Gtk.Button(label="Start Screen Cast")
        cast_btn.connect("clicked", self.on_cast_clicked)
        cast_btn.add_css_class("accent")

        grid.attach(pwr_on, 0, 0, 1, 1)
        grid.attach(pwr_off, 1, 0, 1, 1)
        grid.attach(self.input_btn, 0, 1, 2, 1)
        grid.attach(Gtk.Label(label="Volume:"), 0, 2, 1, 1)
        grid.attach(vol_scale, 1, 2, 1, 1)
        grid.attach(cast_btn, 0, 3, 2, 1)

        self.control_panel.append(grid)
        content_page.set_child(self.control_panel)

        split_view.set_sidebar_page(sidebar_page)
        split_view.set_content_page(content_page)

        self.set_content(split_view)

    def on_scan_clicked(self, btn):
        self.status_label.set_text("Scanning network...")

        def run_scan():
            try:
                projectors = scan_network(ScanOptions())
                # UI updates must happen on the main thread
                GLib.idle_add(self.update_list, projectors)
            except Exception as e:
                GLib.idle_add(self.show_error, str(e))

        threading.Thread(target=run_scan, daemon=True).start()

    def update_list(self, projectors):
        self.projector_list.remove_all()
        for p in projectors:
            self.projector_list.append(ProjectorRow(p))
        self.status_label.set_text(f"Found {len(projectors)} projectors")

    def on_projector_selected(self, listbox, row):
        if not row: return
        self.current_projector = row.projector
        self.status_label.set_text(f"Connected to {self.current_projector.display_name}")

        # Attempt to open session in background
        def connect():
            try:
                session = open_session(self.current_projector)
                GLib.idle_add(self.set_session, session)
            except Exception as e:
                GLib.idle_add(self.show_error, str(e))

        threading.Thread(target=connect, daemon=True).start()

    def set_session(self, session):
        self.current_session = session
        self.status_label.set_text(f"Ready: {self.current_projector.display_name}")

    def on_power_on(self, btn):
        if not self.current_session: return
        threading.Thread(target=lambda: self.current_session.power_on(), daemon=True).start()

    def on_power_off(self, btn):
        if not self.current_session: return
        threading.Thread(target=lambda: self.current_session.power_off(), daemon=True).start()

    def on_set_input(self, btn):
        if not self.current_session: return
        threading.Thread(target=lambda: self.current_session.set_input("hdmi1"), daemon=True).start()

    def on_volume_changed(self, scale):
        if not self.current_session: return
        val = int(scale.get_value())
        threading.Thread(target=lambda: self.current_session.set_volume(val), daemon=True).start()

    def on_cast_clicked(self, btn):
        # Integration with GStreamer/Pipewire casting
        self.show_error("Screen casting is initializing. Please ensure GStreamer is installed.")

    def show_error(self, msg):
        dialog = Gtk.AlertDialog(message=msg)
        dialog.show()

from gi.repository import GLib
