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


class SelectListRowModel(GObject.GObject):

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
                self.append(SelectListRowModel(port))


def list_box_update_header_func(row, before, data):
    """Add a separator header to all rows but the first one"""
    if before is None:
        row.set_header(None)
        return

    current = row.get_header()
    if current is None:
        current = Gtk.Separator.new(Gtk.Orientation.HORIZONTAL)
        row.set_header(current)


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
        sl.set_header_func(list_box_update_header_func, None)

        self.pack_start(self._builder.get_object("select-stack"), True, True, 0)
        self.show_all()

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


class PDOListRowModel(GObject.GObject):

    def __init__(self, pdo):
        GObject.GObject.__init__(self)
        self.pdo = pdo


class PDOListStore(Gio.ListStore):

    def update_items(self, pdo_list):
        # Clear the list
        self.remove_all()

        # Add everything from the new list
        for pdo in pdo_list:
            self.append(PDOListRowModel(pdo))


class PDOListRow(Gtk.ListBoxRow):
    oc_tooltips = [
        "I<sub>Peak</sub> = I<sub>OC</sub> (default)",
        """Overload Capabilities:
1. I<sub>Peak</sub> = 150% I<sub>OC</sub> for 1 ms @ 5% duty cycle (I<sub>Low</sub> = 97% I<sub>OC</sub> for 19 ms)
2. I<sub>Peak</sub> = 125% I<sub>OC</sub> for 2 ms @ 10% duty cycle (I<sub>Low</sub> = 97% I<sub>OC</sub> for 18 ms)
3. I<sub>Peak</sub> = 110% I<sub>OC</sub> for 10 ms @ 50% duty cycle (I<sub>Low</sub> = 90% I<sub>OC</sub> for 10 ms)""",
        """Overload Capabilities:
1. I<sub>Peak</sub> = 200% I<sub>OC</sub> for 1 ms @ 5% duty cycle (I<sub>Low</sub> = 95% I<sub>OC</sub> for 19 ms)
2. I<sub>Peak</sub> = 150% I<sub>OC</sub> for 2 ms @ 10% duty cycle (I<sub>Low</sub> = 94% I<sub>OC</sub> for 18 ms)
3. I<sub>Peak</sub> = 125% I<sub>OC</sub> for 10 ms @ 50% duty cycle (I<sub>Low</sub> = 75% I<sub>OC</sub> for 10 ms)""",
        """Overload Capabilities:
1. I<sub>Peak</sub> = 200% I<sub>OC</sub> for 1 ms @ 5% duty cycle (I<sub>Low</sub> = 95% I<sub>OC</sub> for 19 ms)
2. I<sub>Peak</sub> = 175% I<sub>OC</sub> for 2 ms @ 10% duty cycle (I<sub>Low</sub> = 92% I<sub>OC</sub> for 18 ms)
3. I<sub>Peak</sub> = 150% I<sub>OC</sub> for 10 ms @ 50% duty cycle (I<sub>Low</sub> = 50% I<sub>OC</sub> for 10 ms)"""
    ]

    def __init__(self, model):
        Gtk.ListBoxRow.__init__(self)
        self.model = model

        self.set_activatable(False)
        self.set_selectable(False)
        self.set_can_focus(False)

        # Make the widgets and populate them with info from the model
        # Main box
        box = Gtk.Box(Gtk.Orientation.HORIZONTAL, 12)
        box.set_homogeneous(True)
        box.set_margin_left(12)
        box.set_margin_right(12)
        box.set_margin_top(6)
        box.set_margin_bottom(6)

        # Type label
        type_label = Gtk.Label(model.pdo.pdo_type.capitalize())
        type_label.set_halign(Gtk.Align.START)
        box.pack_start(type_label, True, True, 0)

        # Voltage label
        if model.pdo.pdo_type != "unknown":
            voltage_label = Gtk.Label("{:g} V".format(model.pdo.v / 1000.0))
            voltage_label.set_halign(Gtk.Align.END)
            box.pack_start(voltage_label, True, True, 0)

        # Right box
        right_box = Gtk.Box(Gtk.Orientation.HORIZONTAL, 6)
        right_box.set_halign(Gtk.Align.END)
        if model.pdo.pdo_type != "unknown":
            # Current label
            current_label = Gtk.Label("{:g} A".format(model.pdo.i / 1000.0))
            current_label.set_halign(Gtk.Align.END)
            right_box.pack_end(current_label, True, False, 0)

            # Over-current image(?)
            if model.pdo.peak_i > 0:
                oc_image = Gtk.Image.new_from_icon_name(
                        "dialog-information-symbolic", Gtk.IconSize.BUTTON)
                oc_image.set_tooltip_markup(
                        PDOListRow.oc_tooltips[model.pdo.peak_i])
                right_box.pack_end(oc_image, True, False, 0)
        else:
            # PDO value
            text_label = Gtk.Label()
            text_label.set_markup("<tt>{}</tt>".format(model.pdo))
            right_box.pack_end(text_label, True, False, 0)

        box.pack_end(right_box, True, True, 0)

        self.add(box)
        self.show_all()


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

        # Add separators to the configuration page lists
        sc_list = self.builder.get_object("sink-config-list")
        sc_list.set_header_func(list_box_update_header_func, None)

        pd_list = self.builder.get_object("power-delivery-list")
        pd_list.set_header_func(list_box_update_header_func, None)

    def on_pdb_window_delete_event(self, *args):
        Gtk.main_quit(*args)

    def on_select_list_row_activated(self, selectlist, serport):
        # Get relevant widgets
        voltage = self.builder.get_object("voltage-combobox")
        current = self.builder.get_object("current-spinbutton")
        giveback = self.builder.get_object("giveback-toggle")
        pd_frame = self.builder.get_object("power-delivery-frame")
        output = self.builder.get_object("output-switch")
        cap_row = self.builder.get_object("source-cap-row")
        cap_warning = self.builder.get_object("source-cap-warning")
        cap_label = self.builder.get_object("short-source-cap-label")
        cap_arrow = self.builder.get_object("source-cap-arrow")

        self.serial_port = serport

        window = self.builder.get_object("pdb-window")
        try:
            with pdbuddy.Sink(self.serial_port) as pdbs:
                try:
                    pdbs.load()
                except KeyError:
                    # If there's no configuration, we don't want to fail.  We
                    # do want to display no configuration though
                    self.cfg = pdbuddy.SinkConfig(
                            status=pdbuddy.SinkStatus.VALID,
                            flags=pdbuddy.SinkFlags.NONE, v=0, i=0)
                else:
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
        elif self.cfg.v == 12000:
            voltage.set_active_id('voltage-twelve')
        elif self.cfg.v == 15000:
            voltage.set_active_id('voltage-fifteen')
        if self.cfg.v == 20000:
            voltage.set_active_id('voltage-twenty')

        current.set_value(self.cfg.i/1000)

        # Set PD frame visibility and output switch state
        try:
            with pdbuddy.Sink(self.serial_port) as pdbs:
                output.set_state(pdbs.output)
        except KeyError:
            pd_frame.set_visible(False)
        else:
            pd_frame.set_visible(True)

            # TODO: do these next things repeatedly
            # Get the Source_Capabilities
            with pdbuddy.Sink(self.serial_port) as pdbs:
                caps = pdbs.get_source_cap()

            # Update the warning icon
            cap_warning.set_visible(not pdbuddy.follows_power_rules(caps))

            # Update the text in the capability label
            if caps:
                cap_label.set_text('{:g} W'.format(pdbuddy.calculate_pdp(caps)))
            else:
                cap_label.set_text('None')

            # Make the row insensitive if there are no capabilities
            cap_row.set_activatable(caps)
            cap_arrow.set_visible(caps)

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

    def on_sink_save_clicked(self, button):
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
        self.cfg_clean = self.cfg

    def _set_save_button_visibility(self):
        """Show the save button if there are new settings to save"""
        # Get relevant widgets
        rev = self.builder.get_object("sink-save-revealer")

        # Set visibility
        rev.set_reveal_child(self.cfg != self.cfg_clean)

    def on_voltage_combobox_changed(self, combo):
        self.cfg = self.cfg._replace(v=int(combo.get_active_text()) * 1000)

        self._set_save_button_visibility()

    def on_current_spinbutton_changed(self, spin):
        self.cfg = self.cfg._replace(i=int(spin.get_value() * 1000))

        self._set_save_button_visibility()

    def on_giveback_toggle_toggled(self, toggle):
        if toggle.get_active():
            self.cfg = self.cfg._replace(flags=self.cfg.flags|pdbuddy.SinkFlags.GIVEBACK)
        else:
            self.cfg = self.cfg._replace(flags=self.cfg.flags&~pdbuddy.SinkFlags.GIVEBACK)

        self._set_save_button_visibility()

    def on_output_switch_state_set(self, switch, state):
        with pdbuddy.Sink(self.serial_port) as pdbs:
            pdbs.output = state

    def on_source_cap_row_activated(self, box, row):
        # Find which row was clicked
        sc_row = self.builder.get_object("source-cap-row")
        if row != sc_row:
            # If it's not the source-cap-row, leave
            return

        # Get the source capabilities
        with pdbuddy.Sink(self.serial_port) as pdbs:
            caps = pdbs.get_source_cap()

        if not caps:
            # If there are no capabilities, don't show a dialog
            return

        # Create the dialog
        window = self.builder.get_object("pdb-window")
        dialog_builder = Gtk.Builder.new_from_file("data/src-cap-dialog.ui")
        dialog = dialog_builder.get_object("src-cap-dialog")
        dialog.set_transient_for(window)

        # Populate PD Power
        d_power = dialog_builder.get_object("power-label")
        d_power.set_text("{:g} W".format(pdbuddy.calculate_pdp(caps)))
        # Warning icon
        cap_warning = dialog_builder.get_object("source-cap-warning")
        cap_warning.set_visible(not pdbuddy.follows_power_rules(caps))

        # Populate Information
        d_info_header = dialog_builder.get_object("info-header")
        d_info = dialog_builder.get_object("info-label")
        # Make the string to display
        info_str = ""
        if caps[0].dual_role_pwr:
            info_str += "Dual-Role Power\n"
        if caps[0].usb_suspend:
            info_str += "USB Suspend Supported\n"
        if caps[0].unconstrained_pwr:
            info_str += "Unconstrained Power\n"
        if caps[0].usb_comms:
            info_str += "USB Communications Capable\n"
        if caps[0].dual_role_data:
            info_str += "Dual-Role Data\n"
        info_str = info_str[:-1]
        # Set the text and label visibility
        d_info.set_text(info_str)
        d_info_header.set_visible(info_str)
        d_info.set_visible(info_str)

        # PDO list
        d_list = dialog_builder.get_object("src-cap-list")
        d_list.set_header_func(list_box_update_header_func, None)

        model = PDOListStore()
        d_list.bind_model(model, PDOListRow)
        model.update_items(caps)

        # Show the dialog
        dialog.run()
        dialog.destroy()


class Application(Gtk.Application):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="com.clayhobbs.pd-buddy-gtk",
                         **kwargs)
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        self.builder = Gtk.Builder.new_from_file("data/pd-buddy-gtk.ui")
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
