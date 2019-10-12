#!/usr/bin/python3

import argparse
import asyncio
import collections
import json
import os
import time
import unicodedata

import http.client
import tornado.web

import scrum

Word = collections.namedtuple("Word", ("answer", "chunks", "clue"))

class VennSet:
  def __init__(self, finalanswer, index, text):
    self.words = []
    self.finalanswer = finalanswer
    self.index = index

    for line in text.split("\n"):
      line = line.strip()
      if not line: continue
      chunks, clue = line.split(None, 1)

      chunks = tuple(chunks.split("-"))
      answer = "".join(chunks)

      self.words.append(Word(answer, chunks, clue))
    assert len(self.words) == 6



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
    self.running = False
    self.cond = asyncio.Condition()

    self.current_word = None
    self.solved = set()
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
    self.widq.append((wid, now))

    count = self.wids[wid] = self.wids.get(wid, 0) + 1
    if count == 1:
      # a new wid has been issued
      async with self.cond:
        self.cond.notify_all()

    if len(self.widq) > 1000:
      await self.purge(now)

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
    for vs in self.venn_sets:
      # clue phase
      for w in vs.words:
        self.current_word = w
        d = {"method": "show_clue", "html": w.clue}
        await self.team.send_messages([d], sticky=1)

        async with self.cond:
          while w not in self.solved:
            await self.cond.wait()

        break  # skip words

      # venn phase
      while True:
        wids = list(self.wids.keys())
        print(f"wid set: {wids}")

        async with self.cond:
          await self.cond.wait()

  async def send_chat(self, text):
    d = {"method": "add_chat", "text": text}
    await self.team.send_messages([d])

  async def try_answer(self, answer):
    async with self.cond:
      print(answer, self.current_word.answer)
      if (self.current_word not in self.solved and
          answer == self.current_word.answer):
        self.solved.add(self.current_word)
        self.cond.notify_all()


class HatVennDorApp(scrum.ScrumApp):
  WAIT_TIMEOUT = 5
  WAIT_SMEAR = 1

  async def on_wait(self, team, session, wid):
    gs = GameState.get_for_team(team)

    if not gs.running:
      gs.running = True
      self.add_callback(gs.run_game)

    await gs.on_wait(session, wid)


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
    MA-RY       She had a small farm animal according to one song, and was proud according to another.
    ANN-APO-LIS This seaside city is the home of the US Naval Academy.
    HO-OV-ER    Founded in 1908, this company's name has entered common parlance as a synonym for a vacuum cleaner.
    HE-LE-NA    The first name of actress Bonham Carter, this word's origin comes from the Greek word for light.
    TA-YL-OR    This guitar manufacturer based in El Cajon, California, is the (fittingly) preferred brand of 2014's top selling artist.
    JA-CKS-ON   The fictional son of Poseidon, he made his debut in 2005's <i>The Lightning Thief</i>.
    """),
    )

  GameState.set_globals(options, venn_sets)

  loop = asyncio.get_event_loop()
  loop.create_task(GameState.purger())

  handlers = [
    (r"/hatsubmit", SubmitHandler),
    (r"/hatopen", OpenHandler),
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

