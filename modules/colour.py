#@title Colour sensor
#@about
# Watches the floor while the rover moves. When the sensor arrives on one of
# the colours in COLOURS_TO_FIND, the rover stops and on_colour_found() runs.
# Afterwards the move it was making carries on. This happens during every
# drive and turn, including the autonomous searches, without you calling
# anything.
#
#   on_colour_found(colour)   what to do on a colour - WRITE YOUR OWN ACTIONS HERE
#   read_colour()             the colour under the sensor right now
#   found_colours             a list of the colours found so far
#@settings
COLOURS_TO_FIND = [color.GREEN, color.RED]   # colours the rover reacts to
COLOUR_PAUSE_MS = 5000     # how long to stop on a colour, in ms
REACT_ONCE = True          # True: react to each colour only the first time it is found
#@code
def check_colour_settings():
    if not isinstance(COLOURS_TO_FIND, list):
        setting_problem("COLOURS_TO_FIND should be a list in square brackets, like [color.GREEN, color.RED]")
    check_number("COLOUR_PAUSE_MS", COLOUR_PAUSE_MS, 0, 60000)
    check_true_false("REACT_ONCE", REACT_ONCE)


SETTINGS_CHECKS.append(check_colour_settings)

found_colours = []         # colours found so far, in the order they were found
last_colour = None         # what the sensor saw last time
sensor_missing = False


async def on_colour_found(colour):
    # ======================================================================
    #
    #    ADD YOUR OWN ACTIONS HERE
    #
    #    This runs when the rover drives onto a colour from COLOURS_TO_FIND.
    #    The wheels have already stopped. For now it just waits for
    #    COLOUR_PAUSE_MS (5 seconds).
    #
    #    Ideas:
    #        if colour == color.GREEN:
    #            ... drop the payload with a third motor ...
    #        if colour == color.RED:
    #            end_run()          # finish the run here
    #        if len(found_colours) == len(COLOURS_TO_FIND):
    #            end_run()          # finish once every colour has been found
    #
    #    Do NOT drive the rover from here. When this function ends, the move
    #    that was interrupted carries on, and the autonomy modules still
    #    think the rover is where it stopped. Other motors, the lights and
    #    sounds are fine.
    #
    # ======================================================================
    print("COLOUR: found " + colour_name(colour) + ", pausing "
          + str(COLOUR_PAUSE_MS // 1000) + " s")
    await runloop.sleep_ms(COLOUR_PAUSE_MS)
    print("COLOUR: carrying on")


def read_colour():
    """The colour under the sensor right now, e.g. color.GREEN.

    Returns None if there is no colour sensor on COLOUR_SENSOR_PORT. It
    warns once instead of crashing, because a crash in the middle of a
    drive would leave the motors running.
    """
    global sensor_missing
    try:
        return color_sensor.color(COLOUR_SENSOR_PORT)
    except Exception:
        if not sensor_missing:
            print("WARNING: no colour sensor on COLOUR_SENSOR_PORT - colours are ignored")
            sensor_missing = True
        return None


async def check_colour():
    """Every movement calls this many times a second. It reacts only at the
    moment the sensor ARRIVES on a colour, so sitting on a patch counts once."""
    global last_colour
    colour = read_colour()
    just_arrived = colour != last_colour
    last_colour = colour
    if not just_arrived or colour not in COLOURS_TO_FIND:
        return
    if REACT_ONCE and colour in found_colours:
        return
    if colour not in found_colours:
        found_colours.append(colour)
    stop()
    await on_colour_found(colour)
