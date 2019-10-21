#!/usr/bin/python3

import argparse
import asyncio
import collections
import itertools
import json
import os
import random
import time
import unicodedata

import http.client
import tornado.web

import scrum

import pprint

Word = collections.namedtuple("Word", ("answer", "chunks", "clue"))

class VennSet:
  VENN_ORDER = {"1": 0,
                "12": 1,
                "2": 2,
                "23": 3,
                "3": 4,
                "13": 5}

  PERMUTATIONS = "012345 234501 450123 054321 432105 210543".split()

  def __init__(self, finalanswer, index, text):
    self.words = [None] * 6
    self.finalanswer = finalanswer
    self.index = index
    self.all_chunks = []

    used = set()

    self.chunk_sortkey = {}

    sort_order = list(range(6))
    random.shuffle(sort_order)

    setmap = {}

    for line in text.split("\n"):
      line = line.strip()
      if not line: continue
      sets, chunks, clue = line.split(None, 2)

      if len(sets) == 1:
        setmap[sets] = str(len(setmap)+1)
        sets = setmap[sets]
      else:
        sets = "".join(sorted([setmap[k] for k in sets]))

      chunks = tuple(chunks.split("-"))
      answer = "".join(chunks)
      so = sort_order.pop()

      for i, c in enumerate(chunks):
        assert c not in used, f"Duplicate chunk {c}"
        used.add(c)
        self.chunk_sortkey[c] = so*100 + i

      self.words[self.VENN_ORDER[sets]] = Word(answer, chunks, clue)
      self.all_chunks.extend(chunks)
    assert len(self.words) == 6
    self.clue_order = self.words[:]
    self.clue_order.sort(key=lambda w: w.clue)
    self.permutations = []

    for p in self.PERMUTATIONS:
      perm = ",".join(self.words[int(p[i])].answer for i in range(6))
      self.permutations.append(perm)
      print(perm)



  def get_chunks(self):
    return self._ChunkSource(self)

  class _ChunkSource:
    def __init__(self, vs):
      self.vs = vs
      self.pending = []

    def __iter__(self): return self

    def __next__(self):
      if not self.pending:
        self.pending = self.vs.all_chunks[:]
        random.shuffle(self.pending)
      return self.pending.pop()

    def recycle(self, chunks):
      temp = list(chunks)
      random.shuffle(temp)
      self.pending.extend(temp)

class Message:
  def __init__(self, serial, message):
    self.serial = serial
    self.timestamp = time.time()
    self.message = message

class GameState:
  BY_TEAM = {}

  @classmethod
  async def purger(cls):
    while True:
      for t in cls.BY_TEAM.values():
        await t.purge(time.time())
      await asyncio.sleep(2.0)

  @classmethod
  def set_globals(cls, options, venn_sets):
    cls.options = options
    cls.venn_sets = venn_sets

  @classmethod
  def get_for_team(cls, team):
    if team not in cls.BY_TEAM:
      cls.BY_TEAM[team] = cls(team)
    return cls.BY_TEAM[team]

  def __init__(self, team):
    self.team = team
    self.sessions = set()
    self.wid_sessions = {}
    self.running = False
    self.cond = asyncio.Condition()

    self.current_word = None
    self.solved = set()
    self.venn_centers = set()
    self.widq = collections.deque()
    self.wids = {}

    if self.options.min_players is not None:
      self.min_size = self.options.min_players
    else:
      self.min_size = (team.size + 1) // 2
      if self.min_size > 20:
        self.min_size = 20

  async def on_wait(self, session, wid):
    now = time.time()
    wid = f"w{wid}"
    self.widq.append((wid, now))

    count = self.wids[wid] = self.wids.get(wid, 0) + 1
    if count == 1:
      # a new wid has been issued
      async with self.cond:
        self.cond.notify_all()

    if len(self.widq) > 1000:
      await self.purge(now)

    self.wid_sessions[wid] = session

    async with self.cond:
      if session not in self.sessions:
        self.sessions.add(session)
        self.cond.notify_all()

  async def purge(self, now):
    expire = now - HatVennDorApp.WAIT_TIMEOUT * 2
    notify = False
    while self.widq and self.widq[0][1] < expire:
      x = self.widq.popleft()
      if self.wids[x[0]] > 1:
        self.wids[x[0]] -= 1
      else:
        del self.wids[x[0]]
        notify = True
    if notify:
      async with self.cond:
        self.cond.notify_all()

  async def run_game(self):
    for vs in itertools.cycle(self.venn_sets):
      self.current_vs = vs

      # clue phase
      self.phase = "clue"
      for w in vs.clue_order:
        self.current_word = w
        d = {"method": "show_clue", "clue": w.clue}
        await self.team.send_messages([d], sticky=1)

        async with self.cond:
          while w not in self.solved:
            await self.cond.wait()

        d = {"method": "show_answer", "answer": w.answer}
        await self.team.send_messages([d], sticky=1)
        await asyncio.sleep(1.5)

      print(f"chunks {len(vs.all_chunks)} players {len(self.wids)}")
      chunks_per_user = max((len(vs.all_chunks)+1) // len(self.wids), 3)
      chunks_per_user = min(chunks_per_user, len(vs.all_chunks))
      self.assignment = {}
      get_chunks = vs.get_chunks()

      # venn phase
      self.targets = [[] for i in range(6)]
      self.success = False

      while not self.success:
        to_delete = set()
        for wid in self.assignment:
          if wid not in self.wids:
            to_delete.add(wid)
        if to_delete:
          for wid in to_delete:
            get_chunks.recycle(self.assignment.pop(wid).keys())
          # Remove any chunks a purged wid had in the targets.
          for i in range(len(self.targets)):
            self.targets[i] = [x for x in self.targets[i] if x[1] not in to_delete]

        for wid in self.wids:
          if wid not in self.assignment:
            d = self.assignment[wid] = {}
            while len(d) < chunks_per_user:
              c = next(get_chunks)
              if c not in d:
                d[c] = None

        d = {"method": "venn_state",
             "chunks": dict((k, list(v.keys())) for (k, v) in self.assignment.items()),
             "targets": self.targets}
        await self.team.send_messages([d], sticky=1)

        async with self.cond:
          await self.cond.wait()

      self.phase = "final"
      d = {"method": "venn_complete",
           "targets": ["".join(i[0] for i in t) for t in self.targets]}
      await self.team.send_messages([d], sticky=1)

      async with self.cond:
        while vs.finalanswer not in self.venn_centers:
          await self.cond.wait()

      d = {"method": "center_complete",
           "targets": ["".join(i[0] for i in t) for t in self.targets],
           "answer": f"{vs.finalanswer} [{vs.index}]"}
      await self.team.send_messages([d], sticky=1)

      await asyncio.sleep(3.0)

  async def send_chat(self, text):
    d = {"method": "add_chat", "text": text}
    await self.team.send_messages([d])

  async def try_answer(self, answer):
    async with self.cond:
      if self.phase == "clue":
        if (self.current_word not in self.solved and
            answer == self.current_word.answer):
          self.solved.add(self.current_word)
          self.cond.notify_all()
      elif self.phase == "final":
        if (self.current_vs.finalanswer not in self.venn_centers and
            answer == self.current_vs.finalanswer):
          self.venn_centers.add(self.current_vs.finalanswer)
          self.cond.notify_all()

  async def place_chunk(self, session, wid, chunk, target):
    if self.wid_sessions.get(wid) != session:
      print(f"bad wid {wid} for session")
      return

    d = self.assignment.get(wid)
    if not d: return
    if chunk not in d:
      print(f"  wid {wid} doesn't have {chunk}")
      return

    old_target = d[chunk]
    if old_target is not None:
      self.targets[old_target].remove((chunk, wid))
    d[chunk] = target
    if target is not None:
      self.targets[target].append((chunk, wid))
      self.targets[target].sort(key=lambda c: self.current_vs.chunk_sortkey[c[0]])

    self.check_targets()

    async with self.cond:
      self.cond.notify_all()

  def check_targets(self):
    current = []
    for t in self.targets:
      a = "".join(i[0] for i in t)
      if not a: return
      current.append(a)
    current = ",".join(current)

    print(f"current set: {current}")
    if current in self.current_vs.permutations:
      self.success = True


class HatVennDorApp(scrum.ScrumApp):
  WAIT_TIMEOUT = 5
  WAIT_SMEAR = 1

  async def on_wait(self, team, session, wid):
    gs = GameState.get_for_team(team)

    if not gs.running:
      gs.running = True
      self.add_callback(gs.run_game)

    await gs.on_wait(session, wid)


class PlaceHandler(tornado.web.RequestHandler):
  async def get(self, chunk, wid, target):
    scrum_app = self.application.settings["scrum_app"]
    team, session = await scrum_app.check_cookie(self)
    gs = GameState.get_for_team(team)
    if target == "bank":
      target = None
    else:
      target = int(target, 10)
    await gs.place_chunk(session, wid, chunk, target)
    self.set_status(http.client.NO_CONTENT.value)


class SubmitHandler(tornado.web.RequestHandler):
  def prepare(self):
    self.args = json.loads(self.request.body)

  @staticmethod
  def canonicalize_answer(text):
    text = unicodedata.normalize("NFD", text.upper())
    out = []
    for k in text:
      cat = unicodedata.category(k)
      # Letters only.
      if cat[:1] == "L":
        out.append(k)
    return "".join(out)

  async def post(self):
    scrum_app = self.application.settings["scrum_app"]
    team, session = await scrum_app.check_cookie(self)
    gs = GameState.get_for_team(team)

    submission = self.args["answer"]
    answer = self.canonicalize_answer(submission)
    who = self.args["who"].strip()
    if not who: who = "anonymous"
    print(f"{team}: {who} submitted {answer}")

    await gs.send_chat(f"{who} guessed \"{submission}\"")
    await gs.try_answer(answer)

    self.set_status(http.client.NO_CONTENT.value)


class OpenHandler(tornado.web.RequestHandler):
  async def get(self):
    scrum_app = self.application.settings["scrum_app"]
    team, session = await scrum_app.check_cookie(self)
    gs = GameState.get_for_team(team)
    await gs.request_open()
    self.set_status(http.client.NO_CONTENT.value)


class DebugHandler(tornado.web.RequestHandler):
  def get(self, fn):
    if fn.endswith(".css"):
      self.set_header("Content-Type", "text/css")
    elif fn.endswith(".js"):
      self.set_header("Content-Type", "application/javascript")
    with open(fn) as f:
      self.write(f.read())


def make_app(options):
  venn_sets = (
    VennSet("MADISON", 3, """
    G  MA-RY       She had a small farm animal according to one song, and was proud according to another.
    C  ANN-APO-LIS This seaside city is the home of the US Naval Academy.
    P  HO-OV-ER    Founded in 1908, this company's name has entered common parlance as a synonym for a vacuum cleaner.
    GC HE-LE-NA    The first name of actress Bonham Carter, this word's origin comes from the Greek word for light.
    GP TA-YL-OR    This guitar manufacturer based in El Cajon, California, is the (fittingly) preferred brand of 2014's top selling artist.
    PC JA-CKS-ON   The fictional son of Poseidon, he made his debut in 2005's <i>The Lightning Thief</i>.
    """),

    VennSet("HERTZ", 2, """
    C  APP-LE	This edible fruit has over 7,500 cultivars, including Jazz, Ambrosia, and Pink Lady.
    H  FL-OUR	A commonly used name for a powder made by grinding a grain such as wheat.
    U  PA-SC-AL	This computer programming language, widely used in the past as a teaching aid, was named for a French philosopher and mathematician.
    CH MER-CK	One of the largest pharmaceutical manufactuerers in the world, this company was forced to recall the arthritis medication Vioxx in 2004.
    HU JO-ULE	This English brewer and physicist spent much of his research trying to find the mechanical equivalent of heat.
    UC TES-LA	This eccentric scientist famously feuded with Edison over the best distribution method of electricity.
    """),

    VennSet("DUCK", 1, """
    T  AN-GEL	In traditional Christianity, it belongs to one of three hierarchical Spheres.
    F  BU-OY	This oddly-spelled piece of maritime equipment has a disputed etymology &mdash; possibly deriving from the Latin boia, or "chain".
    A  CH-AM-EL-EON	In Chinese, this animal's name is <i>biànsèlóng</i>, which literally translates to "changing-color dragon".
    FA OT-TER	This brand of freeze-them-yourself popsicles comes in such electrifying flavors as "Sir Isaac Lime" and "Alexander the Grape".
    TF CL-IPP-ER	You might hear this term for a fast-moving low pressure system the next time you get a manicure.
    TA RA-M	This computer abbreviation is used to describe memory that allows data to retrieved in near-constant time regardless of where in memory that data lives.
    """),

    VennSet("JORDAN", 4, """
    C  AN-DOR-RA	This small landlocked country straddles the border between France and Spain.
    B  JA-COB	In the Old Testament, he deceived his blind father and stole his older brother Esau's birthright.
    R  AM-AZ-ON	This retail goods behemoth surpassed Microsoft as the most valuable public company in the world in 2019.
    CR NI-GER	Not to be confused with its neighbor to the south, this West African country contains some of the world's largest uranium deposits.
    CB CH-AD	This term for a small scrap of paper gained widespread public recognition in the aftermath of the 2000 US Presidential election.
    BR CHA-RL-ES	Ten kings of France bore this name, more than any other except for Louis.
    """),

    VennSet("MERCURY", 2, """
    C  CH-RY-SL-ER	This company gives its name to an Art Deco-style skyscraper in New York City, at one time the tallest building in the world.
    S  BOW-IE	This knife, primarily used for fighting, was developed by Jim Black in the 1800s and typically features a crossguard and a sheath.
    G  JU-NO	This movie about a pregnant teenager won the Academy Award for Best Original Screenplay in 2007.
    GC SA-TU-RN	This Sega video game console was the 32-bit successor to the Genesis.
    SC BE-NTL-EY	This ultra-luxury car manufacturer is perhaps best known for its logo, which features the letter "B" flanked by a pair of wings.
    GS MA-RS	The 6th largest privately held company in the US, this candy manufacturer counts 3 Musketeers and Milky Way as two of its brands.
    """),

    VennSet("WOOD", 1, """
    M  PL-AS-TIC	The "Great Pacific Garbage Patch" is mostly comprised of micro-particles of this.
    G  WED-GE	A doorstop is an example of this, one of the six simple machines.
    A  GAR-LA-ND	This one-time Supreme Court nominee shares his last name with a term for a decorative wreath of flowers.
    AG DR-IV-ER	A chauffeur, or a program that allows hardware to communicate with a computer's operating system.
    MG IR-ON	This element, also the name of a household appliance, is one of ten whose name and chemical symbol do not start with the same letter.
    MA STO-NE	14 pounds equals one of these, if you're a Brit.
    """),


  )


  GameState.set_globals(options, venn_sets)

  loop = asyncio.get_event_loop()
  loop.create_task(GameState.purger())

  handlers = [
    (r"/hatsubmit", SubmitHandler),
    (r"/hatopen", OpenHandler),
    (r"/hatplace/([A-Z]+)/(w\d+)/(bank|\d+)", PlaceHandler),
  ]
  if options.debug:
    handlers.append((r"/hatdebug/(\S+)", DebugHandler))
  return handlers


def main():
  parser = argparse.ArgumentParser(description="Run the hat venn-dor puzzle.")
  parser.add_argument("--debug", action="store_true",
                      help="Run in debug mode.")
  parser.add_argument("--assets_json", default=None,
                      help="JSON file for image assets")
  parser.add_argument("-c", "--cookie_secret",
                      default="snellen2020",
                      help="Secret used to create session cookies.")
  parser.add_argument("--socket_path", default="/tmp/hatvenndor",
                      help="Socket for requests from frontend.")
  parser.add_argument("--wait_url", default="hatwait",
                      help="Path for wait requests from frontend.")
  parser.add_argument("--main_server_port", type=int, default=2020,
                      help="Port to use for requests to main server.")
  parser.add_argument("--min_players", type=int, default=None,
                      help="Number of players needed to start game.")

  options = parser.parse_args()

  # assert options.assets_json
  # with open(options.assets_json) as f:
  #   options.assets = json.load(f)

  app = HatVennDorApp(options, make_app(options))
  app.start()


if __name__ == "__main__":
  main()

