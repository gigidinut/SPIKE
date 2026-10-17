#@title Movement
#@about
# Drive in straight lines and turn to face any direction. The hub's gyro
# keeps the rover pointing the right way, so a route stays accurate.
#
#   await drive_forward(50)       drive 50 cm forward
#   await drive_backward(20)      back up 20 cm
#   await turn_left(90)           turn 90 degrees left
#   await turn_right(45)          turn 45 degrees right
#   await turn_to(WEST)           face a compass direction
#   cm_driven()                   how far the last drive really went
#   rover_position()              where the rover is: (cm right of the start, cm ahead of it)
#
# NORTH is the way the rover faced when the program started. WEST is 90
# degrees to its left, EAST 90 degrees to its right, SOUTH behind it, and
# NORTH_WEST, NORTH_EAST, SOUTH_WEST, SOUTH_EAST are half way between.
#@tuning
DRIVE_SPEED = 400          # wheel speed when driving, degrees per second (max about 1000)
DRIVE_SLOW_SPEED = 150     # wheel speed for the end of a drive, so it stops on the spot
DRIVE_SLOW_ZONE_CM = 3     # slow down when this many cm from the end
TURN_SPEED = 200           # wheel speed when turning
TURN_SLOW_SPEED = 100      # wheel speed for the end of a turn, so it stops on target
TURN_SLOW_ZONE = 15        # slow down when this many degrees from the target
TURN_ACCURACY = 2          # a turn that ends further off than this many degrees is corrected
TURN_NUDGE_SPEED = 30      # wheel speed for that correction
STEERING = 10              # how strongly to steer back when drifting off course; 0 = off
STUCK_MS = 1000            # no progress for this long while driving or turning = stuck
TICK_MS = 20               # how often to check the sensors while moving, in ms
#@code
def check_movement_settings():
    check_number("DRIVE_SPEED", DRIVE_SPEED, 50, 1000)
    check_number("DRIVE_SLOW_SPEED", DRIVE_SLOW_SPEED, 20, 1000)
    check_number("DRIVE_SLOW_ZONE_CM", DRIVE_SLOW_ZONE_CM, 0, 20)
    check_number("TURN_SPEED", TURN_SPEED, 30, 1000)
    check_number("TURN_SLOW_SPEED", TURN_SLOW_SPEED, 10, 1000)
    check_number("TURN_SLOW_ZONE", TURN_SLOW_ZONE, 0, 90)
    check_number("TURN_ACCURACY", TURN_ACCURACY, 0.5, 10)
    check_number("TURN_NUDGE_SPEED", TURN_NUDGE_SPEED, 10, 300)
    check_number("STEERING", STEERING, 0, 50)
    check_number("STUCK_MS", STUCK_MS, 200, 5000)
    check_number("TICK_MS", TICK_MS, 10, 100)


SETTINGS_CHECKS.append(check_movement_settings)

target_heading = 0     # the direction the rover is meant to be facing
last_drive_cm = 0      # how far the last drive went (see cm_driven)

# Where the rover is (its turning point), in cm from where it started:
# EAST is to the right of the start, NORTH is straight ahead of it. Every
# drive adds the distance it goes, in the direction the gyro says the rover
# faces. Turning on the spot does not move it.
position_east_cm = 0
position_north_cm = 0
driving_way = 0        # while a drive runs: 1 = forward, -1 = backward. 0 = not driving
counted_degrees = 0    # wheel degrees of this drive already added to the position


def update_position():
    """Add the distance driven since the last update to the position."""
    global position_east_cm, position_north_cm, counted_degrees
    if driving_way == 0:
        return
    degrees = wheel_degrees()
    cm = wheel_degrees_to_cm(degrees - counted_degrees) * driving_way
    counted_degrees = degrees
    # Split the distance into how far east and how far north it went. Facing
    # NORTH (0) it is all north; facing WEST (90) it is all east, backwards.
    angle = gyro_heading() * math.pi / 180      # degrees to radians
    position_east_cm -= math.sin(angle) * cm
    position_north_cm += math.cos(angle) * cm


def rover_position():
    """Where the rover is: (cm to the right of the start, cm ahead of the start).
    Negative means left of the start, or behind it. Example: print(rover_position())"""
    return (round(position_east_cm, 1), round(position_north_cm, 1))


async def movement_tick():
    """A short wait inside every movement. While it waits it also keeps the
    rover's position up to date and checks the time limit and the colour
    sensor, so every move reacts to them."""
    await runloop.sleep_ms(TICK_MS)
    update_position()
    check_time_limit()
    await check_colour()


async def drive(cm, speed, stop_at_wall_cm=0):
    """Drive cm in a straight line along target_heading.

    speed above 0 drives forward, below 0 drives backward. If stop_at_wall_cm
    is more than 0, the rover also stops when the distance sensor sees
    something closer than that.

    Returns how the drive ended:
      "done"   it drove the whole way
      "wall"   something came closer than stop_at_wall_cm
      "stuck"  the wheels stopped turning (pushing against something)
    """
    global last_drive_cm, driving_way, counted_degrees
    goal = cm_to_wheel_degrees(abs(cm))
    slow_from = goal - cm_to_wheel_degrees(DRIVE_SLOW_ZONE_CM)
    reset_wheel_counters()
    counted_degrees = 0
    if speed > 0:
        driving_way = 1
    else:
        driving_way = -1
    result = "done"
    progress = 0     # wheel position at the last stuck check
    still_ms = 0     # how long the wheels have hardly moved
    try:
        while wheel_degrees() < goal:
            if stop_at_wall_cm > 0:
                distance = read_distance()
                if distance != -1 and distance < stop_at_wall_cm:
                    result = "wall"
                    break

            # Slow down for the last few cm, or the rover rolls on past the end.
            now_speed = speed
            if wheel_degrees() > slow_from:
                now_speed = DRIVE_SLOW_SPEED
                if speed < 0:
                    now_speed = -DRIVE_SLOW_SPEED

            # Steering: error is how far the rover has drifted. If it has
            # drifted right (error above 0), the right wheel speeds up and the
            # left wheel slows down, which turns it back left - and the other
            # way round. The bigger the drift, the harder it steers.
            error = heading_difference(target_heading, gyro_heading())
            steer = error * STEERING
            limit = abs(now_speed) / 2
            steer = max(-limit, min(limit, steer))
            set_wheel_speeds(now_speed - steer, now_speed + steer)
            await movement_tick()

            # Stuck check: while the motors run, the wheels should keep turning.
            if wheel_degrees() - progress > 10:
                progress = wheel_degrees()
                still_ms = 0
            else:
                still_ms += TICK_MS
                if still_ms >= STUCK_MS:
                    result = "stuck"
                    break
    finally:
        # This part also runs when something cuts the drive short - end_run(),
        # or explore(find=...) finding its colour - so the position stays right.
        stop()
        update_position()
        driving_way = 0
    last_drive_cm = wheel_degrees_to_cm(wheel_degrees())
    print("drive: " + result + " after " + str(round(last_drive_cm, 1)) + " cm")
    return result


async def drive_forward(cm, stop_at_wall_cm=0):
    """Drive forward. Example: await drive_forward(30)

    Add stop_at_wall_cm to stop early if a wall gets that close (this needs
    the Distance sensor module): await drive_forward(80, stop_at_wall_cm=10)
    Returns "done", "wall" or "stuck" - see drive().
    """
    return await drive(cm, DRIVE_SPEED, stop_at_wall_cm)


async def drive_backward(cm):
    """Drive backward. Example: await drive_backward(10)

    There is no sensor at the back, so make sure there is room!
    """
    return await drive(cm, -DRIVE_SPEED)


def cm_driven():
    """How far the last drive really went, in cm. Useful after a drive that
    stopped early, e.g. to reverse exactly that far."""
    return last_drive_cm


async def spin(heading, speed, way):
    """Spin on the spot until the rover faces heading.

    way is 1 to turn left or -1 to turn right - even if that is the long way
    round. It slows down to TURN_SLOW_SPEED for the last TURN_SLOW_ZONE
    degrees. Returns True when it gets there, or False if it got stuck - for
    example when the back of the rover hits a wall as it swings round.
    turn_to() uses this; you will normally want turn_to() instead.
    """
    to_turn = heading_difference(heading, gyro_heading()) * way
    if to_turn < 0:
        to_turn += 360           # the long way round
    turned = 0                   # degrees turned so far, in the direction of way
    last_heading = gyro_heading()
    checked = 0                  # degrees turned at the last stuck check
    still_ms = 0                 # how long it has hardly turned
    while turned < to_turn:
        now_speed = speed
        if to_turn - turned < TURN_SLOW_ZONE:
            now_speed = min(speed, TURN_SLOW_SPEED)
        # Left turn: left wheel backward, right wheel forward.
        set_wheel_speeds(-way * now_speed, way * now_speed)
        await movement_tick()
        now = gyro_heading()
        turned += heading_difference(now, last_heading) * way
        last_heading = now
        # Stuck check: while the rover turns, the gyro should keep changing.
        if turned - checked > 2:
            checked = turned
            still_ms = 0
        else:
            still_ms += TICK_MS
            if still_ms >= STUCK_MS:
                stop()
                return False
    stop()
    return True


async def face(heading, way):
    """Spin to face heading (way: 1 = left, -1 = right), then nudge it until it
    is within TURN_ACCURACY degrees. Returns False if it got stuck on the way."""
    if not await spin(heading, TURN_SPEED, way):
        return False
    # The rover rolls on a little after the motors stop. If it ends up more
    # than TURN_ACCURACY degrees out, nudge it back slowly (up to 3 tries).
    for attempt in range(3):
        await runloop.sleep_ms(100)
        error = heading_difference(heading, gyro_heading())
        if abs(error) <= TURN_ACCURACY:
            return True
        if error > 0:
            nudge_way = 1
        else:
            nudge_way = -1
        if not await spin(heading, TURN_NUDGE_SPEED, nudge_way):
            return False
    return True


async def turn_to(direction):
    """Turn on the spot to face a direction.

    direction is a gyro heading: NORTH, WEST, NORTH_WEST and so on, or any
    angle. Example: await turn_to(WEST)

    It turns the short way round. If the rover gets stuck - there is not
    enough room for its back to swing round - it swings back to where it
    started and tries the long way round instead. If that gets stuck too,
    it shuffles sideways a little (see shuffle) and tries once more.
    Returns True when the rover faces the new way, or False if nothing
    worked (it is then facing the way it was before).
    """
    global target_heading
    before = target_heading
    target_heading = normalise(direction)
    if abs(heading_difference(target_heading, gyro_heading())) <= TURN_ACCURACY:
        return True
    if heading_difference(target_heading, gyro_heading()) > 0:
        short_way = 1        # left
    else:
        short_way = -1       # right
    for way in [short_way, -short_way]:
        if await face(target_heading, way):
            print("turn: to " + str(target_heading) + ", stopped at " + str(gyro_heading()))
            return True
        # Stuck: swing back the way it came, to where it started.
        print("turn: no room to turn that way round - swinging back")
        await face(before, -way)
    # Turning short_way, the back of the rover swings the other way, so that
    # is where the wall is. Shuffle away from it, then try once more.
    target_heading = before
    if await shuffle(short_way):
        target_heading = normalise(direction)
        if await face(target_heading, short_way):
            print("turn: to " + str(target_heading) + ", stopped at " + str(gyro_heading()))
            return True
        await face(before, -short_way)
        target_heading = before
    print("turn: no room to turn to " + str(normalise(direction)) + " here")
    return False


async def shuffle(way):
    """Move the rover a few cm sideways without turning far, like parallel
    parking: angle it 25 degrees to one side (way: 1 = left, -1 = right),
    drive forward 10 cm, straighten up and reverse the same distance. That
    moves it about 4 cm to that side. Returns False if there was no room
    even for that.
    """
    global target_heading
    heading = target_heading
    print("turn: shuffling sideways to make room")
    target_heading = normalise(heading + way * 25)
    if not await face(target_heading, way):
        target_heading = heading
        await face(heading, -way)
        return False
    await drive_forward(10, stop_at_wall_cm=8)
    moved = cm_driven()
    target_heading = heading
    await face(heading, -way)
    await drive_backward(moved)
    return True


async def turn_left(degrees=90):
    """Turn left by degrees (up to 180). Example: await turn_left(90)
    Returns True, or False if there was no room to turn (see turn_to)."""
    return await turn_to(target_heading + degrees)


async def turn_right(degrees=90):
    """Turn right by degrees (up to 180). Example: await turn_right(90)
    Returns True, or False if there was no room to turn (see turn_to)."""
    return await turn_to(target_heading - degrees)
