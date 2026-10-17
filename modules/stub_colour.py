#@title Colour sensor - not installed
#@about
# This file does not include the Colour sensor module, so the rover ignores
# colours while it moves. check_colour() and the names below are here only so
# the Movement module and the Maze explorer still work.
#@code
class ColourReached(Exception):
    pass


colour_module_installed = False
colour_spots = {}
looking_for = None
react_to_colours = True


async def check_colour():
    pass
