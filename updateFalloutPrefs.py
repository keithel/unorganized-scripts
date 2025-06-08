import os
import re
import argparse
import sys
import displayres

# --- Constants for path detection ---
FALLOUT_NV_APP_ID = "22380"
# Relative path from the 'steamapps' directory to FalloutPrefs.ini for Proton/Wine installs
FALLOUT_NV_INI_RELATIVE_PATH = f"compatdata/{FALLOUT_NV_APP_ID}/pfx/drive_c/users/steamuser/My Documents/My Games/FalloutNV/FalloutPrefs.ini"

def find_steam_root(user_steam_path=None):
    """
    Attempts to locate a valid Steam installation root directory.

    Args:
        user_steam_path (str, optional): A user-provided Steam root directory.
                                         e.g., ~/.local/share/Steam or ~/.steam/steam.

    Returns:
        str or None: The absolute path to the Steam root directory if found and valid, otherwise None.
    """
    potential_roots = []

    # 1. User-provided path (if specified)
    if user_steam_path:
        expanded_path = os.path.expanduser(user_steam_path)
        # If the user gives steamapps directory, get its parent
        if os.path.basename(expanded_path) == "steamapps":
            potential_roots.append(os.path.dirname(expanded_path))
        else:
            potential_roots.append(expanded_path)

    # 2. Common default Steam installation paths on Linux
    default_roots = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam/steam"), # Older Steam path, still common
    ]

    for root in default_roots:
        if root not in potential_roots: # Avoid checking duplicates
            potential_roots.append(root)

    for root in potential_roots:
        # Check if the 'steamapps' directory exists within the root
        if os.path.isdir(os.path.join(root, "steamapps")):
            return root # Found a valid Steam root

    return None # No valid Steam root found

def find_fallout_prefs_path(user_steam_path=None):
    """
    Attempts to locate the FalloutPrefs.ini file based on a detected Steam installation path.

    Args:
        user_steam_path (str, optional): A user-provided Steam root directory.

    Returns:
        str or None: The full path to FalloutPrefs.ini if found, otherwise None.
    """
    steam_root = find_steam_root(user_steam_path)
    if steam_root:
        steamapps_path = os.path.join(steam_root, "steamapps")
        full_ini_path = os.path.join(steamapps_path, FALLOUT_NV_INI_RELATIVE_PATH)
        if os.path.exists(full_ini_path):
            return full_ini_path

    return None # Path not found

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
    if not i_size_h_found or not i_size_w_found:
        # Find the index of the [Display] section to insert new keys
        display_section_idx = -1
        for i, line in enumerate(modified_lines):
            if re.match(r'\[Display\]', line.strip()):
                display_section_idx = i
                break

        if display_section_idx != -1:
            # Insert H first, then W, to ensure W is before H if both are added
            # This is a minor stylistic choice, but can matter for some INI parsers
            insertion_point = display_section_idx + 1
            if not i_size_h_found:
                modified_lines.insert(insertion_point, f"iSize H={adjusted_height}\n")
                if not force_write:
                    print(f"DRY RUN: Would insert 'iSize H={adjusted_height}' after [Display] section.", file=sys.stderr)
                insertion_point += 1 # Adjust insertion point for the next potential insert
            if not i_size_w_found:
                modified_lines.insert(insertion_point, f"iSize W={adjusted_width}\n")
                if not force_write:
                    print(f"DRY RUN: Would insert 'iSize W={adjusted_width}' after [Display] section.", file=sys.stderr)
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
    parser = argparse.ArgumentParser(add_help=False, description="Modify Fallout New Vegas FalloutPrefs.ini to fit the game to your primary display in windowed mode.")
    parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    # Make the positional argument optional by adding nargs='?'
    parser.add_argument("fallout_prefs_path", nargs='?',
                        help="The full path to the FalloutPrefs.ini file. If not provided, script will attempt to locate it automatically.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force write changes to the file. By default, a dry run is performed.")
    # New argument for Steam path
    parser.add_argument("-s", "--steam-path",
                        help="Specify the root directory of your Steam installation (e.g., ~/.local/share/Steam). "
                             "This is used for auto-detecting FalloutPrefs.ini if its path isn't given directly.")

    args = parser.parse_args()

    # --- Print detected Steam installation path when the app starts ---
    _detected_steam_root_at_startup = find_steam_root(args.steam_path)
    if _detected_steam_root_at_startup:
        print(f"Steam installation detected at: {_detected_steam_root_at_startup}", file=sys.stderr)
    else:
        print("Info: No Steam installation found in common locations. Please ensure Steam is installed or specify its path.", file=sys.stderr)
    print("", file=sys.stderr)

    if args.help:
        parser.print_help()
        sys.exit(0)

    actual_fallout_prefs_path = None

    # Determine the FalloutPrefs.ini path
    if args.fallout_prefs_path:
        actual_fallout_prefs_path = os.path.expanduser(args.fallout_prefs_path)
        if not os.path.exists(actual_fallout_prefs_path):
            print(f"Error: Specified FalloutPrefs.ini not found at '{actual_fallout_prefs_path}'. Exiting.", file=sys.stderr)
            sys.exit(1) # Exit with failure if explicit path doesn't exist
    else:
        print("Attempting to auto-detect FalloutPrefs.ini path...", file=sys.stderr)
        actual_fallout_prefs_path = find_fallout_prefs_path(args.steam_path)
        if not actual_fallout_prefs_path:
            print("Error: Could not auto-detect FalloutPrefs.ini path.", file=sys.stderr)
            print("Please ensure Steam is installed, Fallout New Vegas is installed via Proton/Wine,", file=sys.stderr)
            print("and either provide the full path using the positional argument or specify your Steam root directory with --steam-path.", file=sys.stderr)
            sys.exit(1) # Exit with failure

    print(f"Using FalloutPrefs.ini at: {actual_fallout_prefs_path}", file=sys.stderr)
    modify_fallout_prefs(actual_fallout_prefs_path, force_write=args.force)
