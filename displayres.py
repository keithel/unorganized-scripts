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

def parse_xrandr_details(xrandr_output):
    """
    Parses xrandr output to get:
    - Set of connected display IDs
    - Primary display ID
    - Dictionary of xrandr-reported resolutions (from the 'connected' line)
    - Dictionary of xrandr-actual resolutions (from the '*' line)
    """
    connected_ids = set()
    primary_id = None
    xrandr_reported_resolutions = {} # Resolution from the 'connected' line
    xrandr_actual_resolutions = {} # Resolution with the '*'

    if not xrandr_output:
        return connected_ids, primary_id, xrandr_reported_resolutions, xrandr_actual_resolutions

    lines = xrandr_output.splitlines()
    current_display_id = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match connected displays (e.g., DP-2 connected primary 5120x2880+0+0)
        match_connected = re.match(r'\s*(\S+)\s+connected(?:\s+primary)?\s+(\d+x\d+)\+.*', line)
        if match_connected:
            current_display_id = match_connected.group(1)
            connected_ids.add(current_display_id)
            xrandr_reported_resolutions[current_display_id] = match_connected.group(2) # Resolution from the 'connected' line

            if "connected primary" in line:
                primary_id = current_display_id

            # Look for the actual (starred) resolution in subsequent lines
            j = i + 1
            while j < len(lines):
                sub_line = lines[j]
                if sub_line.startswith(' ') or sub_line.startswith('\t'): # It's a mode line
                    res_match = re.search(r'^\s*(\d+x\d+)(?:(?:\s\+)?\s+\d+\.\d+)*\*', sub_line)
                    if res_match:
                        xrandr_actual_resolutions[current_display_id] = res_match.group(1)
                        break # Found the actual resolution for this monitor
                else:
                    # Not indented, means we've moved to the next display or a new section
                    break
                j += 1
            i = j # Move outer loop pointer to avoid re-processing lines
        else:
            i += 1 # Move to next line in outer loop

    return connected_ids, primary_id, xrandr_reported_resolutions, xrandr_actual_resolutions

# --- Function to parse monitors.xml for the ACTIVE configuration ---
def parse_active_monitors_xml_config(xml_path, connected_xrandr_ids):
    """
    Parses ~/.config/monitors.xml to find the active configuration
    based on currently connected xrandr display IDs, and extracts info.
    """
    monitors_from_active_config = []

    if not os.path.exists(xml_path):
        # print(f"Warning: '{xml_path}' not found. This script is most accurate for Xorg sessions where Gnome uses this file.")
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
                    'actual_display_resolution': None, # From XML's <mode>
                    'logical_resolution': None,        # Calculated using XML's <scale>
                    'gnome_scale_factor': None         # From XML's <scale>
                }

                monitor_element = logical_monitor.find('monitor')
                if monitor_element is None: continue

                monitorspec_element = monitor_element.find('monitorspec')
                if monitorspec_element is None: continue

                connector_element = monitorspec_element.find('connector')
                if connector_element is not None and connector_element.text:
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
            if config_connectors == connected_xrandr_ids:
                return logical_monitors_in_config # Found the active configuration!

    except ET.ParseError as e:
        print(f"Error parsing monitors.xml: {e}")
        return []

    return [] # No matching active configuration found in monitors.xml

# --- Fallback for monitors only detected by xrandr ---
def get_xrandr_only_monitor_info(display_id, primary_id, xrandr_reported_resolutions, xrandr_actual_resolutions):
    """
    Constructs basic info for a monitor connected via xrandr but not found in active XML config.
    """
    return {
        'id': display_id,
        'is_primary': (display_id == primary_id),
        'actual_display_resolution': xrandr_actual_resolutions.get(display_id, "N/A"), # Best guess for actual
        'logical_resolution': xrandr_reported_resolutions.get(display_id, "N/A"), # xrandr's connected resolution as logical
        'gnome_scale_factor': '1.0x (xrandr detected only)',
        'xrandr_reported_resolution': xrandr_reported_resolutions.get(display_id, "N/A") # The requested xrandr reported res
    }

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
    parser.add_argument(
        '--xrandr-logical-res',
        action='store_true',
        help="Show only the xrandr logical resolution for each display. If -d is also specified, only print it for that display."
    )
    args = parser.parse_args()

    # Step 1: Get comprehensive xrandr details (connected status, primary, and reported resolutions)
    xrandr_output = run_xrandr()
    if not xrandr_output:
        print("Cannot get display information. Ensure Xorg is running and xrandr is installed.")
        return

    connected_xrandr_ids, primary_display_id, \
    xrandr_reported_resolutions, xrandr_actual_resolutions = parse_xrandr_details(xrandr_output)

    # Step 2: Parse monitors.xml for the ACTIVE configuration
    monitors_xml_path = os.path.expanduser("~/.config/monitors.xml")
    monitors_from_active_config = parse_active_monitors_xml_config(monitors_xml_path, connected_xrandr_ids)

    final_monitors_list = []

    # Step 3: Combine data: Prioritize monitors.xml data for connected displays
    if monitors_from_active_config:
        for xml_monitor_info in monitors_from_active_config:
            # Mark primary status based on xrandr's determination
            xml_monitor_info['is_primary'] = (xml_monitor_info['id'] == primary_display_id)
            # Add xrandr's reported resolution
            xml_monitor_info['xrandr_reported_resolution'] = xrandr_reported_resolutions.get(xml_monitor_info['id'], "N/A")
            # If actual_display_resolution from XML is N/A, try to use xrandr_actual_resolutions
            if xml_monitor_info['actual_display_resolution'] is None or xml_monitor_info['actual_display_resolution'] == "N/A":
                xml_monitor_info['actual_display_resolution'] = xrandr_actual_resolutions.get(xml_monitor_info['id'], "N/A")
            final_monitors_list.append(xml_monitor_info)

    # Step 4: Add any connected monitors that were NOT found in the active monitors.xml config
    xml_ids_in_final_list = {m['id'] for m in final_monitors_list}
    for xrandr_id in connected_xrandr_ids:
        if xrandr_id not in xml_ids_in_final_list:
            # Get basic info from xrandr for this connected-only monitor
            xrandr_only_info = get_xrandr_only_monitor_info(xrandr_id, primary_display_id,
                                                            xrandr_reported_resolutions, xrandr_actual_resolutions)
            if xrandr_only_info:
                final_monitors_list.append(xrandr_only_info)

    # Sort the final list for consistent output
    final_monitors_list.sort(key=lambda m: m['id'])

    # --- Handle new --xrandr-logical-res option ---
    if args.xrandr_logical_res:
        if args.display:
            # If -d is also specified, print only for that display
            found = False
            for monitor in final_monitors_list:
                if monitor['id'] == args.display:
                    print(monitor['xrandr_reported_resolution'])
                    found = True
                    break
            if not found:
                print(f"Error: Display '{args.display}' not found or not currently connected.")
            return # Exit after printing

        else:
            # Print xrandr logical resolution for all connected displays
            for monitor in final_monitors_list:
                print(f"{monitor['id']}: {monitor['xrandr_reported_resolution']}")
            return # Exit after printing

    # --- Standard output logic (if --xrandr-logical-res is NOT used) ---
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
                print(f"  Logical/Rendered Resolution (Gnome): {monitor['logical_resolution']}")
                print(f"  Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
                print(f"  XRANDR Reported Resolution: {monitor['xrandr_reported_resolution']}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not currently connected.")
            print("Note: This script is most accurate for Xorg sessions. If you are on Wayland, ~/.config/monitors.xml may not contain active configuration.")
        return

    # Default output if no specific arguments are given
    if not final_monitors_list:
        print("No connected displays found.")
        print("Note: This script is most accurate for Xorg sessions.")
        return

    print("---")
    print("Currently Connected Displays:")
    print("---")
    for monitor in final_monitors_list:
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        print(f"    Configured/Actual Resolution: {monitor['actual_display_resolution']}")
        print(f"    Logical/Rendered Resolution (Gnome): {monitor['logical_resolution']}")
        print(f"    Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
        print(f"    XRANDR Reported Resolution: {monitor['xrandr_reported_resolution']}")
        print("-" * 20) # Separator for individual monitors

    if primary_display_id:
        print(f"\nPrimary Display ID: {primary_display_id}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
