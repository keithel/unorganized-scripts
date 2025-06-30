import argparse
import re
from typing import List, Dict, Optional, Tuple, Set
from pydbus import SessionBus

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

def _get_gnome_display_config() -> Tuple[List[Dict], Optional[str]]:
    """
    Queries GNOME's display configuration via D-Bus and returns monitor information.
    Returns a tuple of (monitors_list, primary_display_id).
    """
    try:
        bus = SessionBus()
        display_config = bus.get('org.gnome.Mutter.DisplayConfig')

        serial, monitors, logical_monitors, properties = display_config.GetCurrentState()

        monitors_from_active_config = []
        primary_display_id = None

        # Process logical monitors (similar to XML parsing logic structure)
        for logical_monitor in logical_monitors:
            x, y, scale, transform, primary, monitors_list, props = logical_monitor

            # Process each monitor in this logical monitor
            for monitor_spec in monitors_list:
                connector, vendor, product, serial_num = monitor_spec

                current_monitor_info = {
                    'id': connector,
                    'is_primary': primary,
                    'actual_display_resolution': None,
                    'logical_resolution': None,
                    'gnome_scale_factor': None,
                }

                if primary:
                    primary_display_id = connector

                # Find the physical monitor details to get current resolution
                for monitor in monitors:
                    monitor_spec_phys, modes, props_phys = monitor
                    connector_phys, vendor_phys, product_phys, serial_phys = monitor_spec_phys

                    if connector_phys == connector:
                        # Find current mode (similar to XML mode parsing)
                        for mode in modes:
                            mode_id, width, height, refresh_rate, preferred_scale, supported_scales, mode_props = mode
                            if mode_props.get('is-current', False):
                                current_monitor_info['actual_display_resolution'] = (width, height)
                                break
                        break

                # Set scale factor (similar to XML scale parsing)
                current_monitor_info['gnome_scale_factor'] = f"{scale:.1f}x"

                # Calculate logical resolution (similar to XML logical resolution calculation)
                if current_monitor_info['actual_display_resolution'] is not None:
                    actual_width, actual_height = current_monitor_info['actual_display_resolution']
                    logical_width = int(actual_width / scale)
                    logical_height = int(actual_height / scale)
                    current_monitor_info['logical_resolution'] = (logical_width, logical_height)

                monitors_from_active_config.append(current_monitor_info)

        return monitors_from_active_config, primary_display_id

    except Exception as e:
        print(f"Error querying GNOME display configuration: {e}")
        return [], None

def get_display_info() -> List[Dict]:
    """
    Retrieves detailed information about currently connected displays,
    using GNOME's D-Bus interface.

    Returns:
        A list of dictionaries, where each dictionary represents a connected monitor
        with the following keys:
        - 'id' (str): The display connector ID (e.g., 'DP-2', 'eDP-1').
        - 'is_primary' (bool): True if this is the primary display.
        - 'actual_display_resolution' (Optional[Tuple[int, int]]): The physical resolution
          reported by GNOME's display config (e.g., (3840, 2160)).
          Will be None if not available.
        - 'logical_resolution' (Optional[Tuple[int, int]]): The logical/rendered resolution
          calculated based on Gnome's UI scale factor (e.g., (2560, 1440)).
          Will be None if not available.
        - 'gnome_scale_factor' (str): Gnome's configured UI scale factor (e.g., '1.2x', '1.5x').

        Returns an empty list if no display information can be retrieved.
    """
    monitors_from_active_config, primary_display_id = _get_gnome_display_config()

    if not monitors_from_active_config:
        return [] # Cannot proceed without display config

    final_monitors_list = []

    # Process monitors from active config
    for gnome_monitor_info in monitors_from_active_config:
        # Set primary status based on GNOME's primary display detection
        gnome_monitor_info['is_primary'] = (gnome_monitor_info['id'] == primary_display_id)
        final_monitors_list.append(gnome_monitor_info)

    final_monitors_list.sort(key=lambda m: m['id'])
    return final_monitors_list

def main():
    parser = argparse.ArgumentParser(description="Query connected displays and their resolutions via GNOME D-Bus.")
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
        '-r', '--raw',
        action='store_true',
        help="Print the displays in raw format - showing the Python structure"
    )
    args = parser.parse_args()

    all_display_info = get_display_info()

    primary_monitor = next((m for m in all_display_info if m['is_primary']), None)
    primary_display_id = primary_monitor['id'] if primary_monitor else None

    if args.primary:
        if primary_display_id:
            print(f"Primary Display: {primary_display_id}")
        else:
            print("No primary display found.")
        return

    if not args.display:
        print("---")
        print("Currently Connected Displays:")
        print("---")
    for monitor in all_display_info:
        found = False
        if monitor['id'] == args.display or not args.display:
            if args.raw:
                print(monitor)
            else:
                status = "(Primary)" if monitor['is_primary'] else ""
                if args.display:
                    print(f"Display: {monitor['id']}")
                else:
                    print(f"ID: {monitor['id']} {status}")
                print(f"  Configured/Actual Resolution: {_format_resolution_tuple(monitor['actual_display_resolution'])}")
                print(f"  Logical/Rendered Resolution (Gnome): {_format_resolution_tuple(monitor['logical_resolution'])}")
                print(f"  Gnome UI Scale Factor: {monitor['gnome_scale_factor']}")
            found = True
        if not args.display:
            print("-" * 20)

        if args.display and found:
            return

    if args.display:
        if not found:
            print(f"Error: Display '{args.display}' not found or not currently connected.")
            print("Note: This script requires GNOME and D-Bus access.")
        return

    if not all_display_info:
        print("No connected displays found.")
        print("Note: This script requires GNOME and D-Bus access.")
        return

    if primary_display_id:
        print(f"\nPrimary Display ID: {primary_display_id}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
