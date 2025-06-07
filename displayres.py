import subprocess
import re
import argparse
import os
import xml.etree.ElementTree as ET

# --- Helper to run xrandr (still useful as a fallback or for comparison) ---
def run_xrandr():
    """Runs the xrandr command and returns its output."""
    try:
        result = subprocess.run(['xrandr'], capture_output=True, text=True, check=True)
        return result.stdout
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError:
        return None

# --- New function to parse monitors.xml ---
def parse_monitors_xml(xml_path):
    """Parses ~/.config/monitors.xml to extract monitor information."""
    monitors = []

    if not os.path.exists(xml_path):
        print(f"Warning: '{xml_path}' not found. This script is most accurate for Xorg sessions where Gnome uses this file.")
        print("Falling back to xrandr for basic connected display info (may not include Gnome scaling).")
        return parse_xrandr_fallback(run_xrandr()), None # Fallback to xrandr for basic info

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Iterate through <logicalmonitor> elements
        for logical_monitor in root.findall('.//logicalmonitor'):
            monitor_info = {
                'id': None,
                'name': None,
                'is_primary': False,
                'actual_display_resolution': None, # Resolution configured for display
                'logical_resolution': None,        # Resolution after Gnome scaling
                'gnome_scale_factor': None         # Gnome's scaling value
            }

            monitor_element = logical_monitor.find('monitor')
            monitorspec_element = monitor_element.find('monitorspec')
            connector_element = monitorspec_element.find('connector')
            if connector_element is not None:
                monitor_info['id'] = connector_element.text # e.g., 'DP-2'

            # Get geometry (used for actual resolution)
            mode = monitor_element.find('mode')
            width = mode.find('width').text
            height = mode.find('height').text
            if width and height:
                monitor_info['actual_display_resolution'] = f"{width}x{height}"

            # Get scaling factor
            scale_element = logical_monitor.find('scale')
            if scale_element is not None and scale_element.text:
                try:
                    gnome_scale = float(scale_element.text)
                    monitor_info['gnome_scale_factor'] = f"{gnome_scale:.1f}x"
                    
                    # Calculate logical resolution from actual and gnome scale
                    if width and height:
                        logical_width = int(int(width) * gnome_scale)
                        logical_height = int(int(height) * gnome_scale)
                        monitor_info['logical_resolution'] = f"{logical_width}x{logical_height}"
                except ValueError:
                    pass # Handle cases where scale is not a valid float

            # If we have an ID, add to list
            if monitor_info['id']:
                monitors.append(monitor_info)

    except ET.ParseError as e:
        print(f"Error parsing monitors.xml: {e}")
        print("Falling back to xrandr for basic connected display info.")
        return parse_xrandr_fallback(run_xrandr()), None # Fallback to xrandr if XML is malformed

    return monitors

# --- Fallback to xrandr for basic info if monitors.xml is not available or malformed ---
def parse_xrandr_fallback(xrandr_output):
    """Parses xrandr output as a fallback for basic connected monitor info."""
    monitors = []
    if not xrandr_output:
        return monitors

    lines = xrandr_output.splitlines()
    for line in lines:
        match_connected = re.match(r'\s*(\S+)\s+connected(?:\s+primary)?\s+(\d+x\d+)\+.*', line)
        if match_connected:
            display_id = match_connected.group(1)
            is_primary = "primary" in line.split("connected")[1]
            logical_resolution_str = match_connected.group(2)

            monitor_info = {
                'id': display_id,
                'name': display_id,
                'is_primary': is_primary,
                'actual_display_resolution': logical_resolution_str, # In fallback, xrandr's logical is the "best guess" actual
                'logical_resolution': logical_resolution_str,        # In fallback, assume 1x scale if not explicitly found
                'gnome_scale_factor': 'N/A (using xrandr fallback)'
            }
            monitors.append(monitor_info)
    return monitors


def main():
    parser = argparse.ArgumentParser(description="Query connected Xorg displays and their resolutions via ~/.config/monitors.xml.")
    parser.add_argument(
        '-d', '--display',
        help="Specify a display identifier (e.g., DP-2, eDP-1-1) to get its resolution and scaling info."
    )
    parser.add_argument(
        '-p', '--primary',
        action='store_true',
        help="Print the primary display identifier."
    )
    args = parser.parse_args()

    monitors_xml_path = os.path.expanduser("~/.config/monitors.xml")
    monitors = parse_monitors_xml(monitors_xml_path)
    primary_display = None

    # Get primary from xrandr.
    xrandr_output_for_primary = run_xrandr()
    if xrandr_output_for_primary:
        xrandr_lines = xrandr_output_for_primary.splitlines()
        for line in xrandr_lines:
            if "connected primary" in line:
                match = re.match(r'\s*(\S+)\s+connected\s+primary.*', line)
                if match:
                    primary_display = match.group(1)
                    # Update the monitor in the list if found
                    for mon in monitors:
                        if mon['id'] == primary_display:
                            mon['is_primary'] = True
                            break
                    break

    if args.primary:
        if primary_display:
            print(f"Primary Display: {primary_display}")
        else:
            print("No primary display found.")
        return

    if args.display:
        found = False
        for monitor in monitors:
            if monitor['id'] == args.display:
                print(f"Display: {monitor['id']}")
                print(f"  Actual Display Resolution: {monitor['actual_display_resolution']}")
                print(f"  Logical/Rendered Resolution: {monitor['logical_resolution']}")
                print(f"  Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not configured in '{monitors_xml_path}'.")
            print("Note: If you are on a Wayland session, this file may not contain active configuration.")
        return

    # Default output if no specific arguments are given
    if not monitors:
        print(f"No connected displays found or '{monitors_xml_path}' could not be parsed.")
        print("Note: This script is most accurate for Xorg sessions.")
        return

    print("---")
    print("Connected Displays (from ~/.config/monitors.xml):")
    print("---")
    for monitor in monitors:
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        print(f"    Name: {monitor['name']}") # Name from XML is usually just the ID/connector
        print(f"    Configured/Actual Resolution: {monitor['actual_display_resolution']}")
        print(f"    Logical/Rendered Resolution: {monitor['logical_resolution']}")
        print(f"    Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
        print("-" * 20) # Separator for individual monitors

    if primary_display:
        print(f"\nPrimary Display ID: {primary_display}")
    else:
        print("\nNo primary display identified from monitors.xml.")

if __name__ == "__main__":
    main()
