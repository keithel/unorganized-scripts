import os
import re
import argparse
import sys
import displayres
import math

# --- Constants for path detection ---
FALLOUT_NV_APP_ID = "22380"
# Relative path from the 'steamapps' directory to FalloutPrefs.ini for Proton/Wine installs
FALLOUT_NV_INI_RELATIVE_PATH = (f"compatdata/{FALLOUT_NV_APP_ID}/pfx/drive_c/users/steamuser/"
                                "My Documents/My Games/FalloutNV/FalloutPrefs.ini")

def find_steam_root(user_steam_path=None):
    """
    Attempts to locate a valid Steam installation root directory.

    Args:
        user_steam_path (str, optional): A user-provided Steam root directory.
                                         e.g., ~/.local/share/Steam or ~/.steam/steam.

    Returns:
        str or None: The absolute path to the Steam root directory if found and valid, otherwise
        None.
    """
    potential_roots = []

    # Add User-provided path (if specified) first.
    if user_steam_path:
        expanded_path = os.path.expanduser(user_steam_path)
        # If the user gives steamapps directory, get its parent
        if os.path.basename(expanded_path) == "steamapps":
            potential_roots.append(os.path.dirname(expanded_path))
        else:
            potential_roots.append(expanded_path)

    # Next add common default Steam installation paths on Linux
    potential_roots.append(os.path.expanduser("~/.local/share/Steam"))
    potential_roots.append(os.path.expanduser("~/.steam/steam")) # Older Steam path, still common

    for root in potential_roots:
        # Validate this is really a steam directory. If it is, return it.
        if os.path.isdir(os.path.join(root, "steamapps")):
            return root

    # No valid Steam root found
    return None

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

def modify_fallout_prefs(fallout_prefs_path, force_write=False, show_changes=False):
    """
    Modifies the FalloutPrefs.ini file with the primary display's
    xrandr_reported_resolution, adjusting for window borders and title bars.

    Args:
        fallout_prefs_path (str): The path to the FalloutPrefs.ini file.
        force_write (bool): If True, changes will be written to the file without confirmation.
        show_changes (bool): If True, the proposed file content will be printed to stdout.
    """

    logfile=sys.stderr if show_changes else sys.stdout
    try:
        display_info = displayres.get_display_info()
    except AttributeError:
        print("Error: The 'displayres' module or 'get_display_info' function was not found.",
              file=sys.stderr)
        print("Please ensure 'displayres.py' is in your PYTHONPATH and contains "
              "'get_display_info()'.", file=sys.stderr)
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
    scalefactor_match=re.match(r'^\d+\.\d+', primary_display['gnome_scale_factor'])
    scalefactor = float(scalefactor_match.group(0))
    print(f"Primary display xrandr_reported_resolution: "
          "{xrandr_reported_width}x{xrandr_reported_height}", file=logfile)
    print(f"scalefactor: {scalefactor}", file=logfile)

    # Window manager titlebar: 64 pixels
    # Window titlebar: 75 pixels
    # Total effective titlebar height: 64 + 75 = 139 pixels
    # This is for scalefactor > 1
    TITLEBAR_HEIGHT = 139.0/2 # Sum of window manager titlebar (64) + window titlebar (75)
    BORDER_HEIGHT = 2.0/2     # Height for bottom window border
    BORDER_WIDTH = 1.0/2      # Width for left/right window borders (each)

    adjusted_width = int(round(xrandr_reported_width - (BORDER_WIDTH*2)*math.ceil(scalefactor)))
    adjusted_height = int(round(xrandr_reported_height - (TITLEBAR_HEIGHT + BORDER_HEIGHT) *
                                math.ceil(scalefactor)))

    print(f"Adjusted resolution for Fallout New Vegas: {adjusted_width}x{adjusted_height}",
          file=logfile)

    if not os.path.exists(fallout_prefs_path):
        print(f"Error: FalloutPrefs.ini not found at {fallout_prefs_path}", file=sys.stderr)
        return

    with open(fallout_prefs_path, 'r') as f:
        lines = f.readlines()

    modified_lines = []
    in_display_section = False
    i_size_w_found = False
    i_size_h_found = False
    dirty = False # Indicates if any changes are made in memory
    changes_summary = [] # List to store "before -> after" change descriptions

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
                if not i_size_w_found:
                    current_val = int(line.strip().split('=')[1])
                    if current_val != adjusted_width:
                        modified_lines.append(f"iSize W={adjusted_width}\n")
                        dirty = True
                        changes_summary.append(f"iSize W: {current_val} -> {adjusted_width}")
                        if show_changes:
                            print(f"Proposed: Change line {i+1}: '{line.strip()}' to "
                                  "'iSize W={adjusted_width}'", file=logfile)
                    else:
                        modified_lines.append(line)
                else:
                    modified_lines.append(line)
                i_size_w_found = True
                continue
            elif re.match(r'iSize H=', line.strip()):
                if not i_size_h_found:
                    current_val = int(line.strip().split('=')[1])
                    if current_val != adjusted_height:
                        modified_lines.append(f"iSize H={adjusted_height}\n")
                        dirty = True
                        changes_summary.append(f"iSize H: {current_val} -> {adjusted_height}")
                        if show_changes:
                            print(f"Proposed: Change line {i+1}: '{line.strip()}' to "
                                  "'iSize H={adjusted_height}'", file=logfile)
                    else:
                        modified_lines.append(line)
                else:
                    modified_lines.append(line)
                i_size_h_found = True
                continue
        modified_lines.append(line)

    # Check if iSize W or iSize H were found in the [Display] section
    if not i_size_h_found or not i_size_w_found:
        missing_sec_str=""
        if not i_size_w_found:
            missing_sec_str="'iSize W' "
        if not i_size_h_found:
            missing_sec_str+=f"{'and ' if len(missing_sec_str)>0 else ''}'iSize H' "
        print(f"Error: FalloutPrefs.ini appears to be corrupted. Missing {missing_sec_str}in the "
              "[Display] section.", file=sys.stderr)
        print("Please verify your FalloutPrefs.ini file or try generating a fresh one by launching "
              "the game.", file=sys.stderr)
        sys.exit(1) # Exit with an error code

    if not dirty and not show_changes:
        print("No changes are needed for FalloutPrefs.ini. Resolutions are already set correctly.",
              file=logfile)
        return

    if show_changes:
        print("\n--- Proposed File Content ---", file=sys.stderr)
        for line in modified_lines:
            print(line.strip())
        print("-----------------------------", file=sys.stderr)
        if not dirty:
            print("No actual changes to apply. Displaying proposed content only.", file=sys.stderr)
            return

    if dirty: # Only prompt for confirmation if changes were actually detected
        print("\nChanges to be applied:", file=logfile)
        for change in changes_summary:
            print(f"- {change}", file=logfile)

        if not force_write:
            logfile.write("Apply these changes to FalloutPrefs.ini? (y/N): ")
            logfile.flush()
            confirmation = input().strip().lower()
            if confirmation != 'y':
                print("Changes not applied. Exiting.", file=sys.stderr)
                return
    else: # This block is reached if show_changes was False and dirty was False
        print("No changes to apply. Exiting.", file=sys.stderr)
        return

    with open(fallout_prefs_path, 'w') as f:
        f.writelines(modified_lines)
    print(f"Successfully modified {fallout_prefs_path}", file=logfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False,
                                     description="Modify Fallout New Vegas FalloutPrefs.ini to fit "
                                     "the game to your primary display in windowed mode.")
    parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    parser.add_argument("fallout_prefs_path", nargs='?',
                        help="The full path to the FalloutPrefs.ini file. If not provided, script "
                        "will attempt to locate it automatically.")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force write changes to the file without prompting for confirmation.")
    parser.add_argument("-s", "--steam-path",
                        help="Specify the root directory of your Steam installation "
                        "(e.g., ~/.local/share/Steam). This is used for auto-detecting "
                        "FalloutPrefs.ini if its path isn't given directly.")
    parser.add_argument("--show-changes", action="store_true",
                        help="Print the proposed changes to the FalloutPrefs.ini file.")

    args = parser.parse_args()

    logfile=sys.stderr if args.show_changes else sys.stdout

    # Print detected Steam installation path when the app starts
    _detected_steam_root_at_startup = find_steam_root(args.steam_path)
    if _detected_steam_root_at_startup:
        print(f"Steam installation detected at: {_detected_steam_root_at_startup}", file=logfile)
    else:
        print("Info: No Steam installation found in common locations. Please ensure Steam is installed or specify its path.", file=sys.stderr)
    print("", file=logfile)

    if args.help:
        parser.print_help()
        sys.exit(0)

    actual_fallout_prefs_path = None

    # Determine the FalloutPrefs.ini path
    if args.fallout_prefs_path:
        actual_fallout_prefs_path = os.path.expanduser(args.fallout_prefs_path)
        if not os.path.exists(actual_fallout_prefs_path):
            print(f"Error: Specified FalloutPrefs.ini not found at '{actual_fallout_prefs_path}'. Exiting.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Attempting to auto-detect FalloutPrefs.ini path...", file=logfile)
        actual_fallout_prefs_path = find_fallout_prefs_path(args.steam_path)
        if not actual_fallout_prefs_path:
            print("Error: Could not auto-detect FalloutPrefs.ini path.", file=sys.stderr)
            print("Please ensure Steam is installed, Fallout New Vegas is installed via Proton/Wine,", file=sys.stderr)
            print("and either provide the full path using the positional argument or specify your Steam root directory with --steam-path.", file=sys.stderr)
            sys.exit(1)

    # Modify the fallout prefs file. Confirmation will be requested unless force
    # is provided.
    print(f"Using FalloutPrefs.ini at: {actual_fallout_prefs_path}", file=logfile)
    modify_fallout_prefs(actual_fallout_prefs_path, force_write=args.force, show_changes=args.show_changes)
