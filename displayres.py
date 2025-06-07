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
    """Parses xrandr output to extract monitor information"""
    monitors = []
    primary_display = None

    if not xrandr_output:
        return monitors, primary_display

    lines = xrandr_output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Regex captures the display ID, whether display is primary or not, and
        # the logical resolution
        match_connected = re.match(r'\s*(\S+)\s+connected(?:\s+primary)?\s+(\d+x\d+)\+.*', line)
        if match_connected:
            display_id = match_connected.group(1)
            is_primary = "primary" in line.split("connected")[1].split(" ")[1]

            logical_resolution_str = match_connected.group(2)

            actual_display_resolution = None
            j = i + 1
            # Iterate through subsequent lines to find the one with the '*'
            # (which shows active resolution)
            while j < len(lines):
                sub_line = lines[j]

                # Lines that start with whitespace are for the current display
                # we're working with.
                if sub_line.startswith(' ') or sub_line.startswith('\t'):
                    res_match = re.search(r'^\s*(\d+x\d+)(?:(?:\s\+)?\s+\d+\.\d+)*\*', sub_line)

                    if res_match:
                        actual_display_resolution = res_match.group(1) # This is the captured resolution
                        break
                else:
                    # No starting whitespace means next display
                    break
                j += 1

            monitor_info = {
                'id': display_id,
                'name': display_id, # xrandr doesn't always provide a human-readable name, so use ID as name
                'is_primary': is_primary,
                'actual_display_resolution': actual_display_resolution if actual_display_resolution else "N/A",
                'logical_resolution': logical_resolution_str
            }
            monitors.append(monitor_info)

            if is_primary:
                primary_display = display_id
            i = j - 1 # Adjust i to the last line processed for this monitor, so the outer loop increments correctly
                      # This ensures we don't re-process lines already handled by the inner loop
        i += 1 # Move to the next line in the outer loop

    return monitors, primary_display

def main():
    parser = argparse.ArgumentParser(description="Query connected Xorg displays and their resolutions.")
    parser.add_argument(
        '-d', '--display',
        help="Specify a display identifier (e.g., DP-2, eDP-1-1) to get its actual display resolution."
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
    always_show_logical=True

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
                actual_logical_neq=(monitor['logical_resolution'] != monitor['actual_display_resolution'])
                print(f"Display: {monitor['id']}")
                print(f"  Actual Display Resolution: {monitor['actual_display_resolution']}")
                if always_show_logical or actual_logical_neq:
                    print("  Logical/Rendered Resolution: "
                          f"{monitor['logical_resolution']}"
                          f"{' (due to scaling)' if actual_logical_neq else ''}")
                found = True
                break
        if not found:
            print(f"Error: Display '{args.display}' not found or not connected.")
        return

    if not monitors:
        print("No connected displays found.")
        return

    print("---")
    print("Connected Displays:")
    print("---")
    for monitor in monitors:
        actual_logical_neq=(monitor['logical_resolution'] != monitor['actual_display_resolution'])
        status = "(Primary)" if monitor['is_primary'] else ""
        print(f"  ID: {monitor['id']} {status}")
        print(f"    Name: {monitor['name']}")
        print(f"    Actual Display Resolution: {monitor['actual_display_resolution']}")
        if always_show_logical or actual_logical_neq:
            print(f"    Logical/Rendered Resolution: {monitor['logical_resolution']}"
                  f"{' (due to scaling)' if actual_logical_neq else ''}")
        print("-" * 20)

    if primary_display:
        print(f"\nPrimary Display ID: {primary_display}")
    else:
        print("\nNo primary display identified.")

if __name__ == "__main__":
    main()
