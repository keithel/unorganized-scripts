import argparse
import random

def create_argparser():
    parser = argparse.ArgumentParser(
        prog = "rand_line",
        description = "Prints a random line from a file")
    parser.add_argument("file",
        metavar = "filename",
        help = "file to print the line from",
        nargs = "?",
        type = argparse.FileType('r'),
        default = "-")
    return parser
    

if __name__ == "__main__":
    parser = create_argparser()
    lines = parser.parse_args().file.readlines()
    selected_lineno = random.randrange(0, len(lines))
    selected_line = lines[selected_lineno]
    print(selected_line)
