#!/usr/bin/env python3
"""Big Tower -- a tower defense game.

Usage:
    python main.py [--fullscreen]

Run from anywhere; assets are resolved relative to this file.
"""
import sys
from pathlib import Path

# make imports work no matter where the game is launched from
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.game import Game  # noqa: E402


def main():
    fullscreen = "--fullscreen" in sys.argv
    game = Game(fullscreen=fullscreen)

    from menus.welcome_screen import Scene
    game.scene = Scene(game)
    game.run()
    pygame_quit()


def pygame_quit():
    import pygame
    pygame.quit()


if __name__ == "__main__":
    main()
