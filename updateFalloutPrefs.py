import os
import re
import argparse
import sys
import displayres

def modify_fallout_prefs(fallout_prefs_path, force_write=False):
    """
    Modifies the FalloutPrefs.ini file with the primary display's
    xrandr_reported_resolution, adjusting for window borders and title bars.

    Args:
        fallout_prefs_path (str): The path to the FalloutPrefs.ini file.
        force_write (bool): If True, changes will be written to the file. Otherwise, a dry run is performed.
    """
    try:
        display_info = displayres.get_display_info()
    except AttributeError:
        print("Error: The 'displayres' module or 'get_display_info' function was not found.", file=sys.stderr)
        print("Please ensure 'displayres.py' is in your PYTHONPATH and contains 'get_display_info()'.", file=sys.stderr)
        return

    primary_display = None
    for display in display_info:
        if display.get('is_primary'):
            primary_display = display
            break

    if not primary_display:
        print("Error: No primary display found.", file=sys.stderr)
        return

    xrandr_reported_width, xrandr_reported_height = primary_display['xrandr_reported_resolution']
    print(f"Primary display xrandr_reported_resolution: {xrandr_reported_width}x{xrandr_reported_height}", file=sys.stderr)

    # Window manager titlebar: 64 pixels
    # Window titlebar: 75 pixels
    # Total effective titlebar height: 64 + 75 = 139 pixels
    TITLEBAR_HEIGHT = 139 # Sum of window manager titlebar (64) + window titlebar (75)
    BORDER_HEIGHT = 2     # Height for bottom window border
    BORDER_WIDTH = 1      # Width for left/right window borders (each)

    adjusted_width = xrandr_reported_width - BORDER_WIDTH*2
    adjusted_height = xrandr_reported_height - TITLEBAR_HEIGHT - BORDER_HEIGHT

    print(f"Adjusted resolution for Fallout New Vegas: {adjusted_width}x{adjusted_height}", file=sys.stderr)

    if not os.path.exists(fallout_prefs_path):
        print(f"Error: FalloutPrefs.ini not found at {fallout_prefs_path}", file=sys.stderr)
        return

    with open(fallout_prefs_path, 'r') as f:
        lines = f.readlines()

    modified_lines = []
    in_display_section = False
    i_size_w_found = False
    i_size_h_found = False

    for i, line in enumerate(lines):
        if re.match(r'\[Display\]', line.strip()):
            in_display_section = True
            modified_lines.append(line)
            continue
        elif re.match(r'\[.*\]', line.strip()) and in_display_section:
            in_display_section = False
            modified_lines.append(line)
            continue

        if in_display_section:
            if re.match(r'iSize W=', line.strip()):
                if not i_size_w_found: # Only modify the first instance if duplicates exist
                    modified_lines.append(f"iSize W={adjusted_width}\n")
                    i_size_w_found = True
                    if not force_write:
                        print(f"DRY RUN: Would change line {i+1}: '{line.strip()}' to 'iSize W={adjusted_width}'", file=sys.stderr)
                else: # Append other instances as-is
                    modified_lines.append(line)
                continue
            elif re.match(r'iSize H=', line.strip()):
                if not i_size_h_found: # Only modify the first instance if duplicates exist
                    modified_lines.append(f"iSize H={adjusted_height}\n")
                    i_size_h_found = True
                    if not force_write:
                        print(f"DRY RUN: Would change line {i+1}: '{line.strip()}' to 'iSize H={adjusted_height}'", file=sys.stderr)
                else: # Append other instances as-is
                    modified_lines.append(line)
                continue
        modified_lines.append(line)

    # If iSize W or iSize H were not found, add them to the [Display] section
    if not i_size_w_found or not i_size_h_found:
        # Find the index of the [Display] section to insert new keys
        display_section_idx = -1
        for i, line in enumerate(modified_lines):
            if re.match(r'\[Display\]', line.strip()):
                display_section_idx = i
                break

        if display_section_idx != -1:
            insertion_point = display_section_idx + 1
            if not i_size_w_found:
                modified_lines.insert(insertion_point, f"iSize W={adjusted_width}\n")
                if not force_write:
                    print(f"DRY RUN: Would insert 'iSize W={adjusted_width}' after [Display] section.", file=sys.stderr)
                insertion_point += 1 # Adjust insertion point for the next potential insert
            if not i_size_h_found:
                modified_lines.insert(insertion_point, f"iSize H={adjusted_height}\n")
                if not force_write:
                    print(f"DRY RUN: Would insert 'iSize H={adjusted_height}' after [Display] section.", file=sys.stderr)
        else:
            print("Warning: [Display] section not found in file. Cannot insert iSize W/H if they don't exist.", file=sys.stderr)

    if not force_write:
        print("\n--- DRY RUN: Proposed File Content ---", file=sys.stderr)
        for line in modified_lines:
            # Print proposed file content to stdout
            print(line.strip())
        print("------------------------------------", file=sys.stderr)
        print("Dry run complete. No changes were written to the file. Use -f or --force to apply changes.", file=sys.stderr)
    else:
        with open(fallout_prefs_path, 'w') as f:
            f.writelines(modified_lines)
        print(f"Successfully modified {fallout_prefs_path}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modify Fallout New Vegas FalloutPrefs.ini with primary display resolution.")
    parser.add_argument("fallout_prefs_path",
                        help="The full path to the FalloutPrefs.ini file.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force write changes to the file. By default, a dry run is performed.")

    args = parser.parse_args()

    # For demonstration purposes, let's create a dummy file if it doesn't exist
    # You should remove this dummy creation in a real scenario
    if not os.path.exists(args.fallout_prefs_path):
        print(f"Creating a dummy FalloutPrefs.ini at: {args.fallout_prefs_path}", file=sys.stderr)
        os.makedirs(os.path.dirname(args.fallout_prefs_path), exist_ok=True)
        with open(args.fallout_prefs_path, 'w') as f:
            f.write("[Display]\n")
            f.write("iSize W=1280\n")
            f.write("iSize H=720\n")
            f.write("bFull Screen=0\n")
            f.write("[General]\n")
            f.write("sLanguage=ENGLISH\n")
            f.write("iPresentInterval=0\n")
            f.write("iPresentInterval=1\n") # Duplicate key example
            f.write("bFull Screen=0\n") # Duplicate key example

    modify_fallout_prefs(args.fallout_prefs_path, force_write=args.force)
