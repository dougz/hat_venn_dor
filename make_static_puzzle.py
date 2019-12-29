#!/usr/bin/python3

def VennSet(mini_answer, ix, big_string):
    frags = []
    clues = []
    center_blanks_l = ["_" for c in mini_answer]
    center_blanks_l[ix-1] = "◯"
    center_blanks_html = "&puncsp;".join(center_blanks_l)
    for line in big_string.splitlines():
        if not "\t" in line: continue
        start, clue = line.strip().split("\t")
        dash_frags = start.split(" ")[-1]
        clues.append(clue)
        frags += dash_frags.split("-")
    clues.sort()
    frags.sort()
    return (center_blanks_html, clues, frags)

venn_sets = [
    VennSet("WOOD", 1, """
    M  PL-AS-TIC	The "Great Pacific Garbage Patch" is mostly comprised of micro-particles of this.
    G  WED-GE	A doorstop is an example of this, one of the six simple machines.
    A  GAR-LA-ND	This one-time Supreme Court nominee shares his last name with a term for a decorative wreath of flowers.
    AG DR-IV-ER	A chauffeur, or a program that allows hardware to communicate with a computer's operating system.
    MG IR-ON	This element, also the name of a household appliance, is one of ten whose name and chemical symbol do not start with the same letter.
    MA STO-NE	14 pounds equals one of these, if you're a Brit.
    """),

    VennSet("MERCURY", 2, """
    C  CH-RY-SL-ER	This company gives its name to an Art Deco-style skyscraper in New York City, at one time the tallest building in the world.
    S  BOW-IE	This knife, primarily used for fighting, was developed by Jim Black in the 1800s and typically features a crossguard and a sheath.
    G  JU-NO	This movie about a pregnant teenager won the Academy Award for Best Original Screenplay in 2007.
    GC SA-TU-RN	This Sega video game console was the 32-bit successor to the Genesis.
    SC BE-NTL-EY	This ultra-luxury car manufacturer is perhaps best known for its logo, which features the letter "B" flanked by a pair of wings.
    GS MA-RS	The 6th largest privately held company in the US, this candy manufacturer counts 3 Musketeers and Milky Way as two of its brands.
    """),

    VennSet("MADISON", 3, """
    G  MA-RY	She had a small farm animal according to one song, and was proud according to another.
    C  ANN-APO-LIS	This seaside city is the home of the US Naval Academy.
    P  HO-OV-ER	Founded in 1908, this company's name has entered common parlance as a synonym for a vacuum cleaner.
    GC HE-LE-NA	The first name of actress Bonham Carter, this word's origin comes from the Greek word for light.
    GP TA-YL-OR	This guitar manufacturer based in El Cajon, California, is the (fittingly) preferred brand of 2014's top selling artist.
    PC JA-CKS-ON	The fictional son of Poseidon, he made his debut in 2005's <i>The Lightning Thief</i>.
    """),

    VennSet("DUCK", 1, """
    T  AN-GEL	In traditional Christianity, it belongs to one of three hierarchical Spheres.
    F  BU-OY	This oddly-spelled piece of maritime equipment has a disputed etymology &mdash; possibly deriving from the Latin boia, or "chain".
    A  CH-AM-EL-EON	In Chinese, this animal's name is <i>biànsèlóng</i>, which literally translates to "changing-color dragon".
    FA OT-TER	This brand of freeze-them-yourself popsicles comes in such electrifying flavors as "Sir Isaac Lime" and "Alexander the Grape".
    TF CL-IPP-ER	You might hear this term for a fast-moving low pressure system the next time you get a manicure.
    TA RA-M	This computer abbreviation is used to describe memory that allows data to be retrieved in near-constant time regardless of where in memory that data lives.
    """),

    VennSet("HERTZ", 2, """
    C  APP-LE	This edible fruit has over 7,500 cultivars, including Jazz, Ambrosia, and Pink Lady.
    H  FL-OUR	A commonly used name for a powder made by grinding a grain such as wheat.
    U  PA-SC-AL	This computer programming language, widely used in the past as a teaching aid, was named for a French philosopher and mathematician.
    CH MER-CK	One of the largest pharmaceutical manufacturers in the world, this company was forced to recall the arthritis medication Vioxx in 2004.
    HU JO-ULE	This English brewer and physicist spent much of his research trying to find the mechanical equivalent of heat.
    UC TES-LA	This eccentric scientist famously feuded with Edison over the best distribution method of electricity.
    """),

    VennSet("JORDAN", 4, """
    C  AN-DOR-RA	This small landlocked country straddles the border between France and Spain.
    B  JA-COB	In the Old Testament, he deceived his blind father and stole his older brother Esau's birthright.
    R  AM-AZ-ON	This retail goods behemoth surpassed Microsoft as the most valuable public company in the world in 2019.
    CR NI-GER	Not to be confused with its neighbor to the south, this West African country contains some of the world's largest uranium deposits.
    CB CH-AD	This term for a small scrap of paper gained widespread public recognition in the aftermath of the 2000 US Presidential election.
    BR CHA-RL-ES	Ten kings of France bore this name, more than any other except for Louis.
    """),
]

HAT_TEMPLATE = """
<div class=onehat>
  <div class=diag>
    <img src="venn.jpg">
    <div class=blanks>BLANKS</div>
  </div>
  <div class=rightin>
  <div class=clues> CLUES </div>
  <div class=frags> FRAGS </div>
  </div>
</div>
"""

PAGE_TEMPLATE = """
  <style>
    .onehat { position: relative; width: 100%; padding: 1em; }
    .onehat .diag { position: absolute; left: 0px; top: 1em; width: 8em; height: 8em; }
    .onehat .diag img { width: 100%; }
    .onehat .diag .blanks { position: absolute; left: 0px; top: 3.5em; width: 100%; text-align: center; }
    .onehat .rightin { position: relative; left: 9em; top: 0px; width: 75%; }
  </style>
  <body id=puzz>
     <div class=fourthwall style="background-color: white; border: 2px dotted blue; padding: 1em;">
     <p>This was a "scrum" puzzle: several people on the team could work on it
        at the same time. There was a timer and the team had to work quickly.

     <p>The following doesn't capture the puzzle's frantic pace, just the raw content:
     </div>

     HATS
  </body>
"""

def main():
  hat_html = ""
  for vs in venn_sets:
      blanks, clues, frags = vs
      clues_html = "\n<ul>\n" + "\n".join(["<li>" + c for c in clues]) + "\n</ul>\n"
      frags_html = " · ".join(frags)
      hat_html += HAT_TEMPLATE.replace("BLANKS", blanks).replace("CLUES", clues_html).replace("FRAGS", frags_html)
  page_html = PAGE_TEMPLATE.replace("HATS", hat_html)
  open("static_puzzle.html", "w").write(page_html)

main()    
