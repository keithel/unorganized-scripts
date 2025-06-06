import subprocess
import re
import argparse

def run_xrandr():
    """Runs the xrandr command and returns its output."""
    try:
        result = subprocess.run(['xrandr'], capture_output=True, text=True, check=True)
        return result.stdout
    except FileNotFoundError:
        print("Error: xrandr command not found. Make sure Xorg is running and xrandr is installed.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running xrandr: {e}")
        return None

def parse_xrandr_output(xrandr_output):
    """Parses xrandr output to extract monitor information."""
    monitors = []
    primary_display = None

    if not xrandr_output:
        return monitors, primary_display

    lines = xrandr_output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Match connected displays
        match_connected = re.match(r'(\S+) connected (primary )?(\d+x\d+)\+.*', line)
        if match_connected:
            display_id = match_connected.group(1)
            is_primary = bool(match_connected.group(2))
            logical_resolution = match_connected.group(3)

            current_resolution = None
            # Look for the active resolution in the subsequent lines
            j = i + 1
            while j < len(lines) and (lines[j].strip().startswith(' ') or lines[j].strip().startswith('\t')):
                res_match = re.search(r'(\d+x\d+)\s+[\d.]+\*?\+', lines[j]) # Catches 1920x1080 60.00*+ or 3840x2160 29.98*
                if res_match and '*' in lines[j]: # Ensure it's the active one
                    current_resolution = res_match.group(1)
                    break
                j += 1
            
            # If no *+ resolution is found, use the logical resolution as a fallback (e.g., if scaling is involved)
            if not current_resolution:
                current_resolution = logical_resolution

            monitor_info = {
                'id': display_id,
                'name': display_id, # xrandr doesn't always provide a human-readable name, so use ID as name
                'is_primary': is_primary,
                'active_resolution': current_resolution,
                'logical_resolution': logical_resolution # Keep logical resolution for context
            }
            monitors.append(monitor_info)

            if is_primary:
                primary_display = display_id
            i = j # Move pointer to after processing this monitor's details
        else:
            i += 1 # Move to the next line if no match

    return monitors, primary_display

def main():
    parser = argparse.ArgumentParser(description="Query connected Xorg displays and their resolutions.")
    parser.add_argument(
        '-d', '--display',
        help="Specify a display identifier (e.g., DP-2, eDP-1-1) to get its resolution."
    )
    parser.add_argument(
        '-p', '--primary',
        action='store_true',
        help="Print the primary display identifier."
    )
    args = parser.parse_args()

    xrandr_output = run_xrandr()
    if not xrandr_output:
        return

    monitors, primary_display = parse_xrandr_output(xrandr_output)

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
                print(f"  Active Resolution: {monitor['active_resolution']}")
                if monitor['logical_resolution'] != monitor['active_resolution']:
                    print(f"  Logical Resolution (due to scaling): {monitor['logical_resolution']}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not connected.")
        return

    # Default output if no specific arguments are given
    if not monitors:
        print("No connected displays found.")
        return

    print("Connected Displays:")
    for monitor in monitors:
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        print(f"    Name: {monitor['name']}")
        print(f"    Active Resolution: {monitor['active_resolution']}")
        if monitor['logical_resolution'] != monitor['active_resolution']:
            print(f"    Logical Resolution (due to scaling): {monitor['logical_resolution']}")
    
    if primary_display:
        print(f"\nPrimary Display ID: {primary_display}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
