#@title Distance sensor
#@about
# Read the distance sensor and use it to stop before walls. Once this module
# is installed, drive_forward() can stop early for a wall too.
#
#   read_distance()                  distance ahead right now, in cm (-1 = no echo)
#   await measure_distance()         a careful reading, standing still
#   await drive_to_wall(10)          drive forward until a wall is 10 cm away
#   await drive_forward(80, stop_at_wall_cm=10)   drive 80 cm, or stop early for a wall
#@settings
MAX_TRUSTED_CM = 180   # readings further than this count as "no echo". In a course
                       # where no straight path is over 2 m, a longer reading means
                       # the sound missed, not that the way is clear.
SETTLE_MS = 150        # wait this long after moving before a careful reading
#@code
def check_distance_settings():
    check_number("MAX_TRUSTED_CM", MAX_TRUSTED_CM, 20, 200)
    check_number("SETTLE_MS", SETTLE_MS, 0, 2000)


SETTINGS_CHECKS.append(check_distance_settings)


def read_distance():
    """Distance to whatever is in front of the sensor, in cm.

    Returns -1 when there is no echo it can trust: nothing in range, or the
    sound bounced away (this happens when the sensor sees a wall at a slant).
    """
    mm = distance_sensor.distance(DISTANCE_SENSOR_PORT)
    if mm is None or mm < 0:
        return -1
    cm = mm / 10
    if cm > MAX_TRUSTED_CM:
        return -1
    return cm


async def measure_distance():
    """A careful distance reading for making a decision.

    Waits for the rover to stop wobbling, takes three readings and returns
    the middle one, so one bad reading cannot fool it. Returns -1 only if
    all three had no echo.
    """
    await runloop.sleep_ms(SETTLE_MS)
    readings = []
    for i in range(3):
        cm = read_distance()
        if cm != -1:
            readings.append(cm)
        await runloop.sleep_ms(30)
    if len(readings) == 0:
        return -1
    readings.sort()
    return readings[len(readings) // 2]


async def drive_to_wall(stop_cm, max_cm=200):
    """Drive forward until something is stop_cm away, or max_cm has been
    driven. Example: await drive_to_wall(10)
    Returns "wall", "done" or "stuck", like drive_forward().
    """
    return await drive_forward(max_cm, stop_at_wall_cm=stop_cm)
