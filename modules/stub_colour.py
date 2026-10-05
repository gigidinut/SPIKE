#@title Colour sensor - not installed
#@about
# This file does not include the Colour sensor module, so the rover ignores
# colours while it moves. check_colour() is here only so the Movement module
# still works.
#@code
async def check_colour():
    pass
