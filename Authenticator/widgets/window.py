# -*- coding: utf-8 -*-
"""
 Copyright © 2016 Bilal Elmoussaoui <bil.elmoussaoui@gmail.com>

 This file is part of Gnome-TwoFactorAuth.

 Gnome-TwoFactorAuth is free software: you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published
 by the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 TwoFactorAuth is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Gnome-TwoFactorAuth. If not, see <http://www.gnu.org/licenses/>.
"""
from gi import require_version
require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, Gdk, GObject, GLib
from Authenticator.widgets.add_account import AddAccount
from Authenticator.widgets.accounts_window import AccountsWindow
from Authenticator.widgets.login_window import LoginWindow
from Authenticator.widgets.no_account_window import NoAccountWindow
from Authenticator.widgets.headerbar import HeaderBar
from Authenticator.widgets.inapp_notification import InAppNotification
from Authenticator.interfaces.observable import Observable
from hashlib import sha256
from gettext import gettext as _
import logging


class Window(Gtk.ApplicationWindow, GObject.GObject):
    __gsignals__ = {
    'changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    'locked': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    'unlocked': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    'view_mode_changed': (GObject.SignalFlags.RUN_LAST, None, (str,))
    }
    counter = 0
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    is_select_mode = False

    def __init__(self, application):
        self.app = application
        self.observable = Observable()
        self.generate_window()
        self.generate_header_bar()
        self.generate_accounts_box()
        self.generate_no_accounts_box()
        self.generate_login_box()
        if self.app.locked:
            self.emit("locked", True)
        else:
            self.emit("unlocked", True)

        GLib.timeout_add_seconds(60, self.refresh_counter)

    def generate_window(self, *args):
        """
            Generate application window (Gtk.Window)
        """
        Gtk.ApplicationWindow.__init__(self, type=Gtk.WindowType.TOPLEVEL,
                                       application=self.app)
        self.move_latest_position()
        self.set_wmclass("org.gnome.Authenticator", "Gnome Authenticator")
        self.set_icon_name("org.gnome.Authenticator")
        self.use_latest_size()
        self.set_resizable(True)
        self.connect("key_press_event", self.on_key_press)
        self.connect("delete-event", lambda x, y: self.app.on_quit())
        self.notification = InAppNotification()
        self.main_box.pack_start(self.notification, False, False, 0)
        self.add(self.main_box)

    def on_key_press(self, app, key_event):
        """
            Keyboard Listener handling
        """
        keyname = Gdk.keyval_name(key_event.keyval).lower()
        if not self.is_locked():

            if not self.no_account_box.is_visible():
                if keyname == "s" or keyname == "escape":
                    if key_event.state == Gdk.ModifierType.CONTROL_MASK or not self.hb.select_button.get_visible():
                        self.toggle_select()
                        return True

            if keyname == "n":
                if key_event.state == Gdk.ModifierType.CONTROL_MASK:
                    self.add_account()
                    return True
            if keyname == "m":
                if key_event.state == Gdk.ModifierType.CONTROL_MASK:
                    self.hb.toggle_view_mode()
                    return True

        return False

    def refresh_counter(self):
        """
            Add a value to the counter each 60 seconds
        """
        if not self.app.locked:
            self.counter += 1
        if self.app.cfg.read("auto-lock", "preferences"):
            if self.counter == self.app.cfg.read("auto-lock-time", "preferences") - 1:
                self.counter = 0
                self.emit("locked", True)
        return True

    def generate_login_box(self):
        """
            Generate login form
        """
        self.login_box = LoginWindow(self.app, self)
        self.observable.register(self.login_box)
        self.hb.lock_button.connect("clicked", lambda x : self.emit("locked", True))
        self.main_box.pack_start(self.login_box, True, False, 0)

    def generate_accounts_box(self):
        self.accounts_box = AccountsWindow(self.app, self)
        self.observable.register(self.accounts_box)
        self.accounts_list = self.accounts_box.get_accounts_list()
        self.accounts_grid = self.accounts_box.get_accounts_grid()
        self.hb.remove_button.connect(
            "clicked", self.accounts_list.remove_selected)
        self.search_bar = self.accounts_box.get_search_bar()
        self.main_box.pack_start(self.accounts_box, True, True, 0)

    def generate_header_bar(self):
        """
            Generate a header bar box
        """
        self.hb = HeaderBar(self.app, self)
        self.observable.register(self.hb)
        # connect signals
        self.hb.cancel_button.connect("clicked", self.toggle_select)
        self.hb.select_button.connect("clicked", self.toggle_select)
        self.hb.add_button.connect("clicked", self.add_account)
        self.set_titlebar(self.hb)

    def add_account(self, *args):
        """
            Create add application window
        """
        add_account = AddAccount(self)
        add_account.show_window()

    def toggle_view_mode(self, is_grid):

        self.accounts_box.set_mode_view(is_grid)

    def toggle_select(self, *args):
        """
            Toggle select mode
        """
        self.is_select_mode = not self.is_select_mode
        self.hb.toggle_select_mode()
        self.accounts_list.toggle_select_mode()
        self.accounts_grid.toggle_select_mode()

    def generate_no_accounts_box(self):
        """
            Generate a box with no accounts message
        """
        self.no_account_box = NoAccountWindow()
        self.observable.register(self.no_account_box)
        self.main_box.pack_start(self.no_account_box, True, False, 0)

    def do_view_mode_changed(self, *args):
        self.observable.update_observers(view_mode=args[0])

    def do_changed(self, *args):
        counter = self.app.db.count()
        self.observable.update_observers(counter=counter)
        self.main_box.show_all()

    def do_locked(self, *args):
        self.app.locked = True
        self.app.refresh_menu()
        self.observable.update_observers(locked=True)

    def do_unlocked(self, *args):
        self.app.locked = False
        self.app.refresh_menu()
        counter = self.app.db.count()
        self.observable.update_observers(unlocked=True, counter=counter)
        self.main_box.show_all()

    def is_locked(self):
        return self.app.locked

    def save_window_state(self):
        """
            Save window position
        """
        pos_x, pos_y = self.get_position()
        size_x, size_y = self.get_size()
        self.app.cfg.update("position-x", pos_x, "preferences")
        self.app.cfg.update("position-y", pos_y, "preferences")
        self.app.cfg.update("size-x", size_x, "preferences")
        self.app.cfg.update("size-y", size_y, "preferences")

    def move_latest_position(self):
        """
            move the application window to the latest position
        """
        x = self.app.cfg.read("position-x", "preferences")
        y = self.app.cfg.read("position-y", "preferences")
        if x != 0 and y != 0:
            self.move(x, y)
        else:
            self.set_position(Gtk.WindowPosition.CENTER)

    def use_latest_size(self):
        x = self.app.cfg.read("size-x", "preferences")
        y = self.app.cfg.read("size-y", "preferences")
        self.resize(x, y)
        self.props.width_request = 500
        self.props.height_request = 650
