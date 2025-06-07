import subprocess
import re
import argparse
import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Tuple, Set

# --- Internal Helper Functions (prefixed with _) ---
def _parse_resolution_string(res_str: str) -> Optional[Tuple[int, int]]:
    """Converts a a 'WxH' resolution string to a (width, height) tuple."""
    if isinstance(res_str, tuple):
        return res_str
    if not isinstance(res_str, str):
        return None
    match = re.match(r'(\d+)x(\d+)', res_str)
    if match:
        try:
            return (int(match.group(1)), int(match.group(2)))
        except ValueError:
            return None
    return None

def _format_resolution_tuple(res_tuple: Optional[Tuple[int, int]]) -> str:
    """Formats a (width, height) tuple back to a 'WxH' string for display."""
    if res_tuple is None or not isinstance(res_tuple, tuple) or len(res_tuple) != 2:
        return "N/A"
    return f"{res_tuple[0]}x{res_tuple[1]}"

def _run_xrandr() -> Optional[str]:
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
        # print(f"Stderr: {e.stderr}")
        return None

def _parse_xrandr_details(xrandr_output: str) -> Tuple[Set[str], Optional[str], Dict[str, Tuple[int, int]], Dict[str, Tuple[int, int]]]:
    """
    Parses xrandr output to get:
    - Set of connected display IDs
    - Primary display ID
    - Dictionary of xrandr-reported resolutions (from the 'connected' line) as tuples
    - Dictionary of xrandr-actual resolutions (from the '*' line) as tuples
    """
    connected_ids = set()
    primary_id = None
    xrandr_reported_resolutions: Dict[str, Tuple[int, int]] = {}
    xrandr_actual_resolutions: Dict[str, Tuple[int, int]] = {}

    if not xrandr_output:
        return connected_ids, primary_id, xrandr_reported_resolutions, xrandr_actual_resolutions

    lines = xrandr_output.splitlines()
    current_display_id = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Example line parsed: "DP-2 connected primary 5120x2880+0+0 (0x31a) normal (normal) 597mm x 336mm"
        match_connected = re.match(r'\s*(\S+)\s+connected(?:\s+primary)?\s+(\d+x\d+)\+.*', line)
        if match_connected:
            current_display_id = match_connected.group(1)
            connected_ids.add(current_display_id)
            xrandr_reported_resolutions[current_display_id] = _parse_resolution_string(match_connected.group(2))

            if "connected primary" in line:
                primary_id = current_display_id

            # Look for the actual (starred) resolution in subsequent lines
            # Example line parsed: "   3840x2160     59.94*+  29.98    25.00    24.00    23.98  "
            j = i + 1
            while j < len(lines):
                sub_line = lines[j]
                if sub_line.startswith(' ') or sub_line.startswith('\t'): # It's a mode line
                    res_match = re.search(r'^\s*(\d+x\d+)(?:(?:\s\+)?\s+\d+\.\d+)*\*', sub_line)
                    if res_match:
                        xrandr_actual_resolutions[current_display_id] = _parse_resolution_string(res_match.group(1))
                        break
                else:
                    break # Not an indented mode line, move to next display or section
                j += 1
            i = j # Move outer loop pointer to avoid re-processing lines
        else:
            i += 1 # Move to next line in outer loop

    return connected_ids, primary_id, xrandr_reported_resolutions, xrandr_actual_resolutions

def _parse_active_monitors_xml_config(xml_path: str, connected_xrandr_ids: Set[str]) -> List[Dict]:
    """
    Parses ~/.config/monitors.xml to find the active configuration
    based on currently connected xrandr display IDs, and extracts info.
    """
    monitors_from_active_config = []

    if not os.path.exists(xml_path):
        return monitors_from_active_config

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Iterate through <configuration> elements directly under <monitors>
        for config_element in root.findall('./configuration'):
            config_connectors = set()
            logical_monitors_in_config = []

            # Example structure:
            # <logicalmonitor>
            #   <x>0</x><y>0</y>
            #   <scale>1.5</scale>
            #   <primary>yes</primary>
            #   <monitor>
            #     <monitorspec>
            #       <connector>DP-2</connector>
            #       ...
            #     </monitorspec>
            #     <mode>
            #       <width>3840</width>
            #       <height>2160</height>
            #     </mode>
            #     ...
            #   </monitor>
            # </logicalmonitor>
            for logical_monitor in config_element.findall('./logicalmonitor'):
                current_monitor_info = {
                    'id': None,
                    'is_primary': False,
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
                    current_monitor_info['id'] = connector_element.text
                    config_connectors.add(current_monitor_info['id'])

                mode_element = monitor_element.find('mode')
                if mode_element is not None:
                    width_element = mode_element.find('width')
                    height_element = mode_element.find('height')
                    if width_element is not None and width_element.text and \
                       height_element is not None and height_element.text:
                        try:
                            current_monitor_info['actual_display_resolution'] = (int(width_element.text), int(height_element.text))
                        except ValueError:
                            pass

                scale_element = logical_monitor.find('scale')
                if scale_element is not None and scale_element.text:
                    try:
                        gnome_scale = float(scale_element.text)
                        current_monitor_info['gnome_scale_factor'] = f"{gnome_scale:.1f}x"

                        if current_monitor_info['actual_display_resolution'] is not None:
                            actual_width, actual_height = current_monitor_info['actual_display_resolution']
                            logical_width = int(actual_width * gnome_scale)
                            logical_height = int(actual_height * gnome_scale)
                            current_monitor_info['logical_resolution'] = (logical_width, logical_height)
                    except ValueError:
                        pass

                if current_monitor_info['id']:
                    logical_monitors_in_config.append(current_monitor_info)

            # Check if this configuration matches the currently connected xrandr displays
            if config_connectors == connected_xrandr_ids:
                return logical_monitors_in_config

    except ET.ParseError as e:
        print(f"Error parsing monitors.xml: {e}")
        return []

    return [] # No matching active configuration found in monitors.xml

def _get_xrandr_only_monitor_info(display_id: str, primary_id: Optional[str], xrandr_reported_resolutions: Dict[str, Tuple[int, int]], xrandr_actual_resolutions: Dict[str, Tuple[int, int]]) -> Dict:
    """
    Constructs basic info for a monitor connected via xrandr but not found in active XML config.
    """
    return {
        'id': display_id,
        'is_primary': (display_id == primary_id),
        'actual_display_resolution': xrandr_actual_resolutions.get(display_id, None),
        'logical_resolution': xrandr_reported_resolutions.get(display_id, None),
        'gnome_scale_factor': '1.0x (xrandr detected only)',
        'xrandr_reported_resolution': xrandr_reported_resolutions.get(display_id, None)
    }

def get_display_info() -> List[Dict]:
    """
    Retrieves detailed information about currently connected Xorg displays,
    combining data from ~/.config/monitors.xml and xrandr.

    This function performs the core logic of gathering display information
    without handling command-line arguments or printing output directly.

    Returns:
        A list of dictionaries, where each dictionary represents a connected monitor
        with the following keys:
        - 'id' (str): The display connector ID (e.g., 'DP-2', 'eDP-1').
        - 'is_primary' (bool): True if this is the primary display.
        - 'actual_display_resolution' (Optional[Tuple[int, int]]): The physical resolution
          reported by monitors.xml's <mode> or xrandr's starred resolution (e.g., (3840, 2160)).
          Will be None if not available.
        - 'logical_resolution' (Optional[Tuple[int, int]]): The logical/rendered resolution
          calculated based on Gnome's UI scale factor from monitors.xml (e.g., (2560, 1440)).
          Will be None if not available.
        - 'gnome_scale_factor' (str): Gnome's configured UI scale factor (e.g., '1.2x', '1.5x').
        - 'xrandr_reported_resolution' (Optional[Tuple[int, int]]): The resolution xrandr
          reports on its 'connected' line, which is often its own logical resolution
          (e.g., (1920, 1080)). Will be None if not available.

        For monitors found only by xrandr (not in monitors.xml),
        'gnome_scale_factor' will be '1.0x (xrandr detected only)' and
        'logical_resolution' will be the same as 'xrandr_reported_resolution'.
        Returns an empty list if no display information can be retrieved.
    """
    xrandr_output = _run_xrandr()
    if not xrandr_output:
        return [] # Cannot proceed without xrandr output

    connected_xrandr_ids, primary_display_id, \
    xrandr_reported_resolutions, xrandr_actual_resolutions = _parse_xrandr_details(xrandr_output)

    monitors_xml_path = os.path.expanduser("~/.config/monitors.xml")
    monitors_from_active_config = _parse_active_monitors_xml_config(monitors_xml_path, connected_xrandr_ids)

    final_monitors_list = []

    if monitors_from_active_config:
        for xml_monitor_info in monitors_from_active_config:
            xml_monitor_info['is_primary'] = (xml_monitor_info['id'] == primary_display_id)
            xml_monitor_info['xrandr_reported_resolution'] = xrandr_reported_resolutions.get(xml_monitor_info['id'], None)

            if xml_monitor_info['actual_display_resolution'] is None:
                xml_monitor_info['actual_display_resolution'] = xrandr_actual_resolutions.get(xml_monitor_info['id'], None)

            final_monitors_list.append(xml_monitor_info)

    xml_ids_in_final_list = {m['id'] for m in final_monitors_list}
    for xrandr_id in connected_xrandr_ids:
        if xrandr_id not in xml_ids_in_final_list:
            xrandr_only_info = _get_xrandr_only_monitor_info(xrandr_id, primary_display_id,
                                                            xrandr_reported_resolutions, xrandr_actual_resolutions)
            if xrandr_only_info:
                final_monitors_list.append(xrandr_only_info)

    final_monitors_list.sort(key=lambda m: m['id'])
    return final_monitors_list

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

    all_display_info = get_display_info()

    primary_monitor = next((m for m in all_display_info if m['is_primary']), None)
    primary_display_id = primary_monitor['id'] if primary_monitor else None

    # Handle specific combinations and the new --xrandr-logical-res option
    if args.xrandr_logical_res and args.primary:
        if primary_monitor:
            print(_format_resolution_tuple(primary_monitor['xrandr_reported_resolution']))
        else:
            print("No primary display found.")
        return

    if args.xrandr_logical_res and args.display:
        found = False
        for monitor in all_display_info:
            if monitor['id'] == args.display:
                print(_format_resolution_tuple(monitor['xrandr_reported_resolution']))
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not currently connected.")
        return

    if args.xrandr_logical_res:
        if not all_display_info:
            print("No connected displays found.")
            print("Note: This script is most accurate for Xorg sessions.")
            return

        for monitor in all_display_info:
            print(f"{monitor['id']}: {_format_resolution_tuple(monitor['xrandr_reported_resolution'])}")
        return

    # Standard output logic (if --xrandr-logical-res is NOT used)
    if args.primary:
        if primary_display_id:
            print(f"Primary Display: {primary_display_id}")
        else:
            print("No primary display found.")
        return

    if args.display:
        found = False
        for monitor in all_display_info:
            if monitor['id'] == args.display:
                print(f"Display: {monitor['id']}")
                print(f"  Configured/Actual Resolution: {_format_resolution_tuple(monitor['actual_display_resolution'])}")
                print(f"  Logical/Rendered Resolution (Gnome): {_format_resolution_tuple(monitor['logical_resolution'])}")
                print(f"  Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
                print(f"  XRANDR Reported Resolution: {_format_resolution_tuple(monitor['xrandr_reported_resolution'])}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not currently connected.")
            print("Note: This script is most accurate for Xorg sessions. If you are on Wayland, ~/.config/monitors.xml may not contain active configuration.")
        return

    if not all_display_info:
        print("No connected displays found.")
        print("Note: This script is most accurate for Xorg sessions.")
        return

    print("---")
    print("Currently Connected Displays:")
    print("---")
    for monitor in all_display_info:
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        print(f"    Configured/Actual Resolution: {_format_resolution_tuple(monitor['actual_display_resolution'])}")
        print(f"    Logical/Rendered Resolution (Gnome): {_format_resolution_tuple(monitor['logical_resolution'])}")
        print(f"    Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
        print(f"    XRANDR Reported Resolution: {_format_resolution_tuple(monitor['xrandr_reported_resolution'])}")
        print("-" * 20)

    if primary_display_id:
        print(f"\nPrimary Display ID: {primary_display_id}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
