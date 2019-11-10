#!/usr/bin/python3

import argparse
import os
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
options = parser.parse_args()

with zipfile.ZipFile("hat_venn_dor.zip", mode="w") as z:
  with z.open("puzzle.html", "w") as f_out:
    with open("hat_venn_dor.html", "rb") as f_in:

      html = f_in.read()

      if options.debug:
        head = ('<link rel=stylesheet href="/hatdebug/hat_venn_dor.css" />'
                '<script src="/closure/goog/base.js"></script>'
                '<script src="/hatdebug/hat_venn_dor.js"></script>')
      else:
        head = ('<link rel=stylesheet href="hat_venn_dor.css" />'
                '<script src="hat_venn_dor-compiled.js"></script>')

      html = html.replace(b"@HEAD@", head.encode("utf-8"))

      f_out.write(html)

  with z.open("solution.html", "w") as f_out:
    with open("solution.html", "rb") as f_in:
      f_out.write(f_in.read())

  for count in range(1, 6+1):
    z.write(f"solution/{count}.svg")

  with z.open("metadata.yaml", "w") as f_out:
    with open("metadata.yaml", "rb") as f_in:
      f_out.write(f_in.read())

  with z.open("endcard.png", "w") as f_out:
    with open("endcard.png", "rb") as f_in:
      f_out.write(f_in.read())

  if not options.debug:
    with z.open("hat_venn_dor.css", "w") as f_out:
      with open("hat_venn_dor.css", "rb") as f_in:
        f_out.write(f_in.read())

    with z.open("hat_venn_dor-compiled.js", "w") as f_out:
      with open("hat_venn_dor-compiled.js", "rb") as f_in:
        f_out.write(f_in.read())

