"""Tiny deterministic/local games used by Mary Arcade without model calls."""
from __future__ import annotations
import random

class MaryArcade:
    GAMES=(
        {"key":"coin","label":"Coin Flip","description":"Quick local coin flip."},
        {"key":"number","label":"Guess 1–10","description":"Mary picks a number locally."},
        {"key":"prompt","label":"Story Spark","description":"A small creative prompt from a local deck."},
    )
    PROMPTS=(
        "A door appears somewhere it absolutely should not exist.",
        "Two characters remember the same event differently.",
        "A harmless object becomes important for the wrong reason.",
        "Someone tells the truth and nobody believes them.",
        "A quiet scene reveals more than the action scene before it.",
    )
    def __init__(self, seed=None): self.random=random.Random(seed); self._number=None
    def games(self): return list(self.GAMES)
    def play(self,key:str,payload:str=""):
        key=str(key).strip().lower()
        if key=="coin": return {"game":key,"result":self.random.choice(["Heads","Tails"])}
        if key=="number":
            if self._number is None: self._number=self.random.randint(1,10); return {"game":key,"state":"started","message":"I picked a number from 1 to 10."}
            try: guess=int(payload)
            except ValueError: return {"game":key,"state":"playing","message":"Give me a number from 1 to 10."}
            if guess==self._number: self._number=None; return {"game":key,"state":"won","message":"You got it."}
            return {"game":key,"state":"playing","message":"Too low." if guess<self._number else "Too high."}
        if key=="prompt": return {"game":key,"result":self.random.choice(self.PROMPTS)}
        raise ValueError(f"Unknown arcade game: {key}")
