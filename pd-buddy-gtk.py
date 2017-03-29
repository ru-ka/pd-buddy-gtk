#!/usr/bin/env python3

import sys

import serial
import serial.tools.list_ports
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GObject, GLib


def pdb_send_message(sp, message):
    """Send a message over the serial port and return the response"""
    # Open the serial port
    # FIXME handle exceptions
    sp = serial.Serial(sp.device, baudrate=115200, timeout=0.01)

    sp.write(bytes(message, 'utf-8') + b'\r\n')
    sp.flush()
    answer = sp.readlines()

    sp.close()

    # Remove the echoed command and prompt
    answer = answer[1:-1]
    return answer


class ListRowModel(GObject.GObject):

    def __init__(self, serport):
        GObject.GObject.__init__(self)
        self.serport = serport


class SelectListStore(Gio.ListStore):

    def update_items(self):
        # Get a list of serial ports
        serports = list(serial.tools.list_ports.grep("1209:0001"))

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

        self._reload()
        GLib.timeout_add(1000, self._reload)

    def _reload(self):
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
        name.set_text(self.model.serport.description)

        device = self._builder.get_object("device")
        device.set_text(self.model.serport.device)

        self.add(self._builder.get_object("grid"))
        self.show_all()

    def on_identify_clicked(self, button):
        pdb_send_message(self.model.serport, 'identify')


class Handler:

    def __init__(self, builder):
        self.builder = builder

    def on_pdb_window_realize(self, *args):
        # Get the list
        sb = self.builder.get_object("select-box")
        sl = SelectList()
        sb.pack_start(sl, True, True, 0)

        liststore = SelectListStore()

        sl.bind_model(liststore, SelectListRow)

        sl.connect("row-activated", self.on_select_list_row_activated)

    def on_pdb_window_delete_event(self, *args):
        Gtk.main_quit(*args)

    def on_select_list_row_activated(self, selectlist, serport):
        # Get voltage and current widgets
        voltage = self.builder.get_object("voltage-combobox")
        current = self.builder.get_object("current-spinbutton")

        self.serial_port = serport

        pdb_send_message(self.serial_port, 'load')
        tmpcfg = pdb_send_message(self.serial_port, 'get_tmpcfg')

        # Get information
        for line in tmpcfg:
            if line.startswith(b'v:'):
                v = line.split()[1]
                if v == b'5.00':
                    voltage.set_active_id('voltage-five')
                elif v == b'9.00':
                    voltage.set_active_id('voltage-nine')
                elif v == b'15.00':
                    voltage.set_active_id('voltage-fifteen')
                if v == b'20.00':
                    voltage.set_active_id('voltage-twenty')
            elif line.startswith(b'i:'):
                i = float(line.split()[1])
                current.set_value(i)

        # Hide the Save button
        rev = self.builder.get_object("header-sink-save-revealer")
        rev.set_reveal_child(False)

        # Show the Sink page
        hst = self.builder.get_object("header-stack")
        hsink = self.builder.get_object("header-sink")
        hsink.set_subtitle(serport.device)
        hst.set_visible_child(hsink)

        st = self.builder.get_object("stack")
        sink = self.builder.get_object("sink")
        st.set_visible_child(sink)

    def on_header_sink_back_clicked(self, data):
        # Show the Select page
        hst = self.builder.get_object("header-stack")
        hselect = self.builder.get_object("header-select")
        hst.set_visible_child(hselect)

        st = self.builder.get_object("stack")
        select = self.builder.get_object("select")
        st.set_visible_child(select)

    def on_header_sink_save_clicked(self, button):
        rev = self.builder.get_object("header-sink-save-revealer")
        rev.set_reveal_child(False)

        pdb_send_message(self.serial_port, 'write')

    def on_voltage_combobox_changed(self, combo):
        rev = self.builder.get_object("header-sink-save-revealer")
        rev.set_reveal_child(True)

        pdb_send_message(self.serial_port,
                         'set_v {}'.format(int(combo.get_active_text())*1000))

    def on_current_spinbutton_changed(self, spin):
        rev = self.builder.get_object("header-sink-save-revealer")
        rev.set_reveal_child(True)

        pdb_send_message(self.serial_port,
                         'set_i {}'.format(int(spin.get_value()*1000)))

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

if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)
