# PD Buddy Configuration

PD Buddy Configuration is a GTK+ GUI for configuring PD Buddy Sink devices.

## Dependencies

PD Buddy Configuration is developed with these versions of its dependencies,
but older versions may work.

* GTK+ 3.22
* Python 3.6
* python-gobject 3.22
* pd-buddy-python 0.4.1

## Usage

Plug your PD Buddy Sink(s) into your computer while holding the Setup button.
Start PD Buddy Configuration with:

    $ ./pd-buddy-gtk.py

You will be greeted with a list of connected PD Buddy devices.  If there is
more than one connected, you can identify them by clicking the light bulb
button in each list entry (the selected device's LED will blink rapidly for two
seconds).

Click one of the list items to configure the device.  Select the desired
voltage and current, then click Save.  If you want to configure other devices,
click the Back arrow to return to the list.  After the settings have been
saved, the devices can be safely disconnected at any time.
