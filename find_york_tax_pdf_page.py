"""
Tool for parsing Town of York Maine giant PDF files of property tax bills.
Will return the tax bill of the owner whose last name matches the search query.
"""
import argparse
from pathlib import Path
import sys
from typing import IO, Optional, Union, BinaryIO
from io import BufferedWriter
from pypdf import PdfReader, PageObject, PdfWriter

def bill_last_name(pdf_page: PageObject) -> str: # pylint: disable=redefined-outer-name
    """
    Given a PDF page that is expected to be a Town of York Property Tax bill,
    returns the last name (or first whitespace separated portion of name) on the
    bill.
    """
    # 5th line contains the name, but it is tainted with a prefix of "acreage"
    # like so: 'acreagealdrich paul j/sally a' or 'acreagekyzivat mary k hrs of'
    # The [7:] is to strip off 'acreage'.
    # The remainder is to just return the last name.
    return pdf_page.extract_text().splitlines()[4][7:].split(' ')[0].lower()

def find_page(pdf_file: IO, query: str) -> Optional[PageObject]: # pylint: disable=redefined-outer-name
    """
    Finds the Town of York, Maine real estate tax bill PDF page, and returns it.
    """
    pdf = PdfReader(pdf_file)
    num_pages = len(pdf.pages)
    cur_begin = 0
    cur_mid = round(num_pages / 2)
    cur_end = num_pages

    cur_last_name = bill_last_name(pdf.pages[cur_mid])
    while (not query in cur_last_name) and cur_begin != cur_end:
        if query > cur_last_name:
            cur_begin = cur_mid+1
        else:
            cur_end = cur_mid-1
        cur_mid = round((cur_end-cur_begin) / 2) + cur_begin
        cur_last_name = bill_last_name(pdf.pages[cur_mid])

    if cur_begin == cur_end:
        return None

    return pdf.pages[cur_mid]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", metavar="FILENAME", type=Path,
        help="Path to PDF file holding all of York, Maine's property "
        "tax bills.")
    parser.add_argument("search", metavar="SEARCH_QUERY", type=str,
        help="A search query used to find the desired property tax bill "
        "page.")
    parser.add_argument("-o", "--output", metavar="output-path", type=Path,
        default=None,
        help="Output PDF file.")
    args = parser.parse_args()
    pdf_path = args.file
    search_query = args.search.lower()

    if not pdf_path.exists():
        print(f"{pdf_path} doesn't exist. aborting.")
        sys.exit(1)

    with open(pdf_path, "rb") as pdf_file:
        pdf_page = find_page(pdf_file, search_query)
        if not pdf_page:
            print(f"No page found that matches '{search_query}'", file=sys.stderr)
            sys.exit(1)

        out_file: Union[BinaryIO, BufferedWriter] = sys.stdout.buffer
        if args.output:
            with open(args.output, "wb") as out_file:
                writer = PdfWriter()
                writer.add_page(pdf_page)
                writer.write(out_file)
                writer.close()
                print(f"Success, wrote matching tax bill PDF to {args.output}")
        else:
            print(f"Matched page split lines: {pdf_page.extract_text().splitlines()}")
            print("To save the matched page to a new PDF file, pass --output=<path to output PDF>")
