#!/usr/bin/env python3

import sys

import serial
import serial.tools.list_ports
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


def pdb_send_message(sp, message):
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

class SelectListRow(Gtk.ListBoxRow):

    def __init__(self, serial_port):
        Gtk.EventBox.__init__(self)

        self.serial_port = serial_port

        self._builder = Gtk.Builder()
        self._builder.add_from_file("data/select-list-row.ui")
        self._builder.connect_signals(self)

        name = self._builder.get_object("name")
        name.set_text(serial_port.description)

        device = self._builder.get_object("device")
        device.set_text(serial_port.device)

        self.add(self._builder.get_object("grid"))
        self.show_all()

    def on_identify_clicked(self, button):
        pdb_send_message(self.serial_port, 'identify')


class Handler:

    def __init__(self, builder):
        self.builder = builder

    def on_pdb_window_realize(self, *args):
        # Get the list
        sl = self.builder.get_object("select-list")
        ss = self.builder.get_object("select-stack")
        sf = self.builder.get_object("select-frame")

        # Search for the serial ports
        for serport in serial.tools.list_ports.grep("1209:0001"):
            # Show the list if we have a serial port
            ss.set_visible_child(sf)
            sl.insert(SelectListRow(serport), -1)

    def on_pdb_window_delete_event(self, *args):
        Gtk.main_quit(*args)

    def on_select_list_row_activated(self, box, row):
        # Get voltage and current widgets
        voltage = self.builder.get_object("voltage-combobox")
        current = self.builder.get_object("current-spinbutton")

        self.serial_port = row.serial_port

        pdb_send_message(self.serial_port, 'load')
        lines = pdb_send_message(self.serial_port, 'get_tmpcfg')

        # Get information
        for line in lines:
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
        hsink.set_subtitle(row.serial_port.device)
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
        combo = self.builder.get_object("voltage-combobox")
        spin = self.builder.get_object("current-spinbutton")
        print("{} V".format(combo.get_active_text()))
        print("{} A".format(spin.get_value()))
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
