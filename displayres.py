import subprocess
import re
import argparse
import os
import xml.etree.ElementTree as ET

# --- Helper to run xrandr ---
def run_xrandr():
    """Runs the xrandr command and returns its output."""
    try:
        current_env = os.environ.copy()
        current_env['LC_ALL'] = 'C' # Ensure consistent English output

        result = subprocess.run(
            ['xrandr'],
            capture_output=True,
            text=True,
            check=True,
            env=current_env
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: xrandr command not found. Make sure Xorg is running and xrandr is installed.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running xrandr: {e}")
        # print(f"Stderr: {e.stderr}") # Uncomment for more detailed error debugging
        return None

def get_xrandr_connected_displays_and_primary(xrandr_output):
    """
    Parses xrandr output to get a set of connected display IDs
    and the primary display ID.
    """
    connected_ids = set()
    primary_id = None

    if not xrandr_output:
        return connected_ids, primary_id

    lines = xrandr_output.splitlines()
    for line in lines:
        match_connected = re.match(r'\s*(\S+)\s+connected(?:\s+primary)?\s+.*', line)
        if match_connected:
            display_id = match_connected.group(1)
            connected_ids.add(display_id)
            if "connected primary" in line:
                primary_id = display_id
    return connected_ids, primary_id

# --- Function to parse monitors.xml for the ACTIVE configuration ---
def parse_active_monitors_xml_config(xml_path, connected_xrandr_ids):
    """
    Parses ~/.config/monitors.xml to find the active configuration
    based on currently connected xrandr display IDs, and extracts info.
    """
    monitors_from_active_config = []

    if not os.path.exists(xml_path):
        print(f"Warning: '{xml_path}' not found. This script is most accurate for Xorg sessions where Gnome uses this file.")
        return monitors_from_active_config

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Iterate through <configuration> elements directly under <monitors>
        for config_element in root.findall('./configuration'):
            config_connectors = set()
            logical_monitors_in_config = []

            # Collect connectors and monitor info for this configuration
            for logical_monitor in config_element.findall('./logicalmonitor'):
                current_monitor_info = {
                    'id': None,
                    'is_primary': False, # Will be set by xrandr later
                    'actual_display_resolution': None,
                    'logical_resolution': None,
                    'gnome_scale_factor': None
                }

                monitor_element = logical_monitor.find('monitor')
                if monitor_element is None: continue

                monitorspec_element = monitor_element.find('monitorspec')
                if monitorspec_element is None: continue

                connector_element = monitorspec_element.find('connector')
                if connector_element is not None and connector_element.text:
                    # If we encounter a monitor ID that isn't in the connected
                    # IDs, break out of logical_monitor loop, no need to
                    # continue searching.
                    if not connector_element.text in connected_xrandr_ids:
                        break
                    current_monitor_info['id'] = connector_element.text
                    config_connectors.add(current_monitor_info['id'])

                # Get mode (for actual resolution)
                mode_element = monitor_element.find('mode')
                if mode_element is not None:
                    width_element = mode_element.find('width')
                    height_element = mode_element.find('height')
                    if width_element is not None and width_element.text and \
                       height_element is not None and height_element.text:
                        try:
                            width = int(width_element.text)
                            height = int(height_element.text)
                            current_monitor_info['actual_display_resolution'] = f"{width}x{height}"
                        except ValueError:
                            pass

                # Get scaling factor from logical_monitor
                scale_element = logical_monitor.find('scale')
                if scale_element is not None and scale_element.text:
                    try:
                        gnome_scale = float(scale_element.text)
                        current_monitor_info['gnome_scale_factor'] = f"{gnome_scale:.1f}x"

                        # Calculate logical resolution using actual and Gnome scale
                        if current_monitor_info['actual_display_resolution']:
                            actual_width, actual_height = map(int, current_monitor_info['actual_display_resolution'].split('x'))
                            logical_width = int(actual_width * gnome_scale)
                            logical_height = int(actual_height * gnome_scale)
                            current_monitor_info['logical_resolution'] = f"{logical_width}x{logical_height}"
                    except ValueError:
                        pass

                if current_monitor_info['id']:
                    logical_monitors_in_config.append(current_monitor_info)

            # Check if this configuration matches the currently connected xrandr displays
            # A perfect match means all connectors in config are connected AND all connected are in config
            if config_connectors == connected_xrandr_ids:
                return logical_monitors_in_config

    except ET.ParseError as e:
        print(f"Error parsing monitors.xml: {e}")
        return []

    return [] # No matching active configuration found in monitors.xml

# --- Fallback for monitors only detected by xrandr ---
def get_xrandr_only_monitor_info(xrandr_output, display_id, primary_id):
    """
    Parses xrandr output to get basic info for a specific display_id.
    Used for monitors connected but not found in the active monitors.xml config.
    """
    if not xrandr_output:
        return None

    lines = xrandr_output.splitlines()
    for line in lines:
        match_connected = re.match(rf'\s*{re.escape(display_id)}\s+connected(?:\s+primary)?\s+(\d+x\d+)\+.*', line)
        if match_connected:
            logical_resolution_str = match_connected.group(1) # xrandr's current res is the "logical" from its view

            return {
                'id': display_id,
                'is_primary': (display_id == primary_id),
                'actual_display_resolution': logical_resolution_str, # Best guess for actual from xrandr
                'logical_resolution': logical_resolution_str, # Assume 1x scale if not in XML
                'gnome_scale_factor': '1.0x (xrandr detected only)'
            }
    return None

def main():
    parser = argparse.ArgumentParser(description="Query connected Xorg displays and their resolutions.")
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

    # Get connected displays and primary from xrandr
    xrandr_output = run_xrandr()
    if not xrandr_output:
        print("Cannot get display information. Ensure Xorg is running and xrandr is installed.")
        return

    connected_xrandr_ids, primary_display_id = get_xrandr_connected_displays_and_primary(xrandr_output)

    # Parse monitors.xml for the active configuration
    monitors_xml_path = os.path.expanduser("~/.config/monitors.xml")
    monitors_from_active_config = parse_active_monitors_xml_config(monitors_xml_path, connected_xrandr_ids)

    final_monitors_list = []

    # Populate final_monitors_list with data from the active XML configuration
    if monitors_from_active_config:
        for xml_monitor_info in monitors_from_active_config:
            # Mark primary status based on xrandr's determination
            xml_monitor_info['is_primary'] = (xml_monitor_info['id'] == primary_display_id)
            final_monitors_list.append(xml_monitor_info)

    # Add any connected monitors that were NOT found in the active monitors.xml config
    # This handles cases where monitors.xml might not have the *exact* current configuration
    # or if a new monitor is connected that hasn't been saved to XML yet.
    xml_ids_in_final_list = {m['id'] for m in final_monitors_list}
    for xrandr_id in connected_xrandr_ids:
        if xrandr_id not in xml_ids_in_final_list:
            xrandr_only_info = get_xrandr_only_monitor_info(xrandr_output, xrandr_id, primary_display_id)
            if xrandr_only_info:
                final_monitors_list.append(xrandr_only_info)

    # Sort the final list for consistent output
    #final_monitors_list.sort(key=lambda m: m['id'])

    if args.primary:
        if primary_display_id:
            print(f"Primary Display: {primary_display_id}")
        else:
            print("No primary display found.")
        return

    if args.display:
        found = False
        for monitor in final_monitors_list:
            if monitor['id'] == args.display:
                print(f"Display: {monitor['id']}")
                print(f"  Configured/Actual Resolution: {monitor['actual_display_resolution']}")
                print(f"  Logical/Rendered Resolution: {monitor['logical_resolution']}")
                print(f"  Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not currently connected.")
            print("Note: This script assumes you're using Xorg. If you are on Wayland, ~/.config/monitors.xml may not contain active configuration.")
        return

    # Default output if no specific arguments are given
    if not final_monitors_list:
        print("No connected displays found.")
        print("Note: This script assumes you're using Xorg.")
        return

    print("Currently Connected Displays:")
    print()
    for monitor in final_monitors_list:
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        # Name is typically just the ID for monitors.xml, but keeping structure consistent
        print(f"    Configured/Actual Resolution: {monitor['actual_display_resolution']}")
        print(f"    Logical/Rendered Resolution: {monitor['logical_resolution']}")
        print(f"    Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
        print("-" * 20)

    if primary_display_id:
        print(f"\nPrimary Display ID: {primary_display_id}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
