#@title Distance sensor - not installed
#@about
# This file does not include the Distance sensor module, so the rover never
# looks for walls while it drives. read_distance() is here only so the
# Movement module still works.
#@code
def read_distance():
    return -1      # "no echo": the rover never sees a wall
