#!/usr/bin/env python3

import sys

import pdbuddy
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GObject, GLib


def comms_error_dialog(parent, e):
    dialog = Gtk.MessageDialog(window, 0, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE, "Error communicating with device")
    dialog.format_secondary_text(e.strerror)
    dialog.run()

    dialog.destroy()


class ListRowModel(GObject.GObject):

    def __init__(self, serport):
        GObject.GObject.__init__(self)
        self.serport = serport


class SelectListStore(Gio.ListStore):

    def update_items(self):
        # Get a list of serial ports
        serports = list(pdbuddy.Sink.get_devices())

        # Mark ports to remove or add
        remove_list = []
        list_len = self.get_n_items()
        for i in range(list_len):
            remove = True
            for j in range(len(serports)):
                if serports[j] is not None and self.get_item(i).serport == serports[j]:
                    serports[j] = None
                    remove = False
            if remove:
                remove_list.append(i)

        # Remove the missing ones
        for i in remove_list:
            self.remove(i)

        # Add any new ports
        for port in serports:
            if port is not None:
                self.append(ListRowModel(port))


class SelectList(Gtk.Box):
    __gsignals__ = {
        'row-activated': (GObject.SIGNAL_RUN_FIRST, None,
                      (object,))
    }

    def __init__(self):
        Gtk.Box.__init__(self)

        self._model = None

        self._builder = Gtk.Builder()
        self._builder.add_from_file("data/select-stack.ui")
        self._builder.connect_signals(self)

        sl = self._builder.get_object("select-list")

        # Add separators to the list
        sl.set_header_func(self._update_header_func, None)

        self.pack_start(self._builder.get_object("select-stack"), True, True, 0)
        self.show_all()

    def _update_header_func(self, row, before, data):
        """Add a separator header to all rows but the first one"""
        if before is None:
            row.set_header(None)
            return

        current = row.get_header()
        if current is None:
            current = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
            row.set_header(current)

    def bind_model(self, model, func):
        self._builder.get_object("select-list").bind_model(model, func)
        self._model = model

        self.reload()
        GLib.timeout_add(1000, self.reload)

    def reload(self):
        self._model.update_items()

        # Set the visible child
        stack = self._builder.get_object("select-stack")
        if self._model.get_n_items():
            stack.set_visible_child(self._builder.get_object("select-frame"))
        else:
            stack.set_visible_child(self._builder.get_object("select-none"))

        return True

    def on_select_list_row_activated(self, box, row):
        self.emit("row-activated", row.model.serport)


class SelectListRow(Gtk.ListBoxRow):

    def __init__(self, model):
        Gtk.EventBox.__init__(self)

        self.model = model

        self._builder = Gtk.Builder()
        self._builder.add_from_file("data/select-list-row.ui")
        self._builder.connect_signals(self)

        name = self._builder.get_object("name")
        name.set_text('{} {} {}'.format(self.model.serport.manufacturer,
                                        self.model.serport.product,
                                        self.model.serport.serial_number))

        device = self._builder.get_object("device")
        device.set_text(self.model.serport.device)

        self.add(self._builder.get_object("grid"))
        self.show_all()

    def on_identify_clicked(self, button):
        window = self.get_toplevel()
        try:
            with pdbuddy.Sink(self.model.serport) as pdbs:
                pdbs.identify()
        except OSError as e:
            comms_error_dialog(window, e)
            return


class Handler:

    def __init__(self, builder):
        self.builder = builder
        self.serial_port = None
        self.voltage = None
        self.current = None
        self.giveback = None
        self.selectlist = None

    def on_pdb_window_realize(self, *args):
        # Get the list
        sb = self.builder.get_object("select-box")
        self.selectlist = SelectList()
        sb.pack_start(self.selectlist, True, True, 0)

        liststore = SelectListStore()

        self.selectlist.bind_model(liststore, SelectListRow)

        self.selectlist.connect("row-activated", self.on_select_list_row_activated)

    def on_pdb_window_delete_event(self, *args):
        Gtk.main_quit(*args)

    def on_select_list_row_activated(self, selectlist, serport):
        # Get voltage and current widgets
        voltage = self.builder.get_object("voltage-combobox")
        current = self.builder.get_object("current-spinbutton")
        giveback = self.builder.get_object("giveback-toggle")

        self.serial_port = serport

        window = self.builder.get_object("pdb-window")
        try:
            with pdbuddy.Sink(self.serial_port) as pdbs:
                try:
                    pdbs.load()
                except KeyError:
                    # If there's no configuration, we don't want to fail
                    pass
                self.cfg = pdbs.get_tmpcfg()
        except OSError as e:
            comms_error_dialog(window, e)
            return

        self._store_device_settings()
        self._set_save_button_visibility()

        # Set giveback button state
        giveback.set_active(bool(self.cfg.flags & pdbuddy.SinkFlags.GIVEBACK))

        # Get voltage and current from device and load them into the GUI
        if self.cfg.v == 5000:
            voltage.set_active_id('voltage-five')
        elif self.cfg.v == 9000:
            voltage.set_active_id('voltage-nine')
        elif self.cfg.v == 15000:
            voltage.set_active_id('voltage-fifteen')
        if self.cfg.v == 20000:
            voltage.set_active_id('voltage-twenty')

        current.set_value(self.cfg.i/1000)

        # Show the Sink page
        hst = self.builder.get_object("header-stack")
        hsink = self.builder.get_object("header-sink")
        hsink.set_title('{} {} {}'.format(serport.manufacturer,
                                          serport.product,
                                          serport.serial_number))
        hsink.set_subtitle(serport.device)
        hst.set_visible_child(hsink)

        st = self.builder.get_object("stack")
        sink = self.builder.get_object("sink")
        st.set_visible_child(sink)

        # Ping the Sink repeatedly
        GLib.timeout_add(1000, self._ping)

    def _ping(self):
        """Ping the device we're configuring, showing to the list on failure"""
        if self.serial_port is None:
            self.selectlist.reload()
            self.on_header_sink_back_clicked(None)
            return False
        try:
            with pdbuddy.Sink(self.serial_port) as pdbs:
                pdbs.send_command("")
            return True
        except:
            self.selectlist.reload()
            self.on_header_sink_back_clicked(None)
            return False

    def on_header_sink_back_clicked(self, data):
        self.serial_port = None

        # Show the Select page
        hst = self.builder.get_object("header-stack")
        hselect = self.builder.get_object("header-select")
        hst.set_visible_child(hselect)

        st = self.builder.get_object("stack")
        select = self.builder.get_object("select")
        st.set_visible_child(select)

    def on_header_sink_save_clicked(self, button):
        window = self.builder.get_object("pdb-window")
        try:
            with pdbuddy.Sink(self.serial_port) as pdbs:
                pdbs.set_tmpcfg(self.cfg)
                pdbs.write()

            self._store_device_settings()
            self._set_save_button_visibility()
        except OSError as e:
            comms_error_dialog(window, e)
            self.on_header_sink_back_clicked(None)

    def _store_device_settings(self):
        """Store the settings that were loaded from the device"""
        self.cfg_clean = pdbuddy.SinkConfig(
                status=self.cfg.status,
                flags=self.cfg.flags,
                v=self.cfg.v,
                i=self.cfg.i)

    def _set_save_button_visibility(self):
        """Show the save button if there are new settings to save"""
        # Get relevant widgets
        rev = self.builder.get_object("header-sink-save-revealer")

        # Set visibility
        rev.set_reveal_child(self.cfg != self.cfg_clean)

    def on_voltage_combobox_changed(self, combo):
        self.cfg.v = int(combo.get_active_text()) * 1000

        self._set_save_button_visibility()

    def on_current_spinbutton_changed(self, spin):
        self.cfg.i = int(spin.get_value() * 1000)

        self._set_save_button_visibility()

    def on_giveback_toggle_toggled(self, toggle):
        if toggle.get_active():
            self.cfg.flags |= pdbuddy.SinkFlags.GIVEBACK
        else:
            self.cfg.flags &= ~pdbuddy.SinkFlags.GIVEBACK

        self._set_save_button_visibility()


class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="com.clayhobbs.pd-buddy-gtk",
                         **kwargs)
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.builder = Gtk.Builder()
        self.builder.add_from_file("data/pd-buddy-gtk.ui")
        self.builder.connect_signals(Handler(self.builder))

    def do_activate(self):
        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = self.builder.get_object("pdb-window")
            self.add_window(self.window)
            self.window.set_wmclass("PD Buddy Configuration",
                                    "PD Buddy Configuration")

        self.window.present()


def run():
    app = Application()
    app.run(sys.argv)

if __name__ == "__main__":
    run()
