# ======================================================================
# ROVER SOFTWARE - WALL FOLLOWER
# ======================================================================
# Package: Wall follower. Version 1.2, built 2026-10-20.
#
# TO GET YOUR ROVER GOING, YOU ONLY NEED TO CHANGE THESE PARTS:
#   SETTINGS           just below: describe your rover and your course
#   YOUR PROGRAM       at the very bottom: choose or write what the rover does
#   on_colour_found()  only for your own colour actions: search the file
#                      for ADD YOUR OWN ACTIONS HERE
# Everything else is the rover software. Read it, play with it and change
# it if you like: that is the best way to understand how it works. Keep a
# copy of a version that works first, so you can always go back.
# The User Manual explains every setting and function.
#
# 1. Copy this whole file into a new Python project in the SPIKE App.
# 2. Change the SETTINGS to match your rover.
# 3. Run setup_check (see YOUR PROGRAM at the bottom) and fix anything it reports.
# 4. Choose your program at the bottom and run it.
# ======================================================================

import motor
import distance_sensor
import color_sensor
import color
import runloop
import math
import time
from hub import port, motion_sensor, button

SOFTWARE_VERSION = "1.2"     # which version of the software this is

# Compass directions, as gyro headings. NORTH is the way the rover faced when
# the program started. Turning left makes the number bigger.
NORTH = 0
NORTH_WEST = 45
WEST = 90
SOUTH_WEST = 135
SOUTH = 180
SOUTH_EAST = -135
EAST = -90
NORTH_EAST = -45


# ======================================================================
# SETTINGS - change these to match your rover and your course
# ======================================================================

# ---- Setup ----
# Which hub port each part is plugged into (port.A to port.F).
LEFT_MOTOR_PORT = port.B
RIGHT_MOTOR_PORT = port.A
DISTANCE_SENSOR_PORT = port.C
COLOUR_SENSOR_PORT = port.D

# Which way each drive motor must spin to move the rover FORWARD: 1 or -1.
# Motors mounted mirror-image on the two sides need opposite numbers.
LEFT_MOTOR_DIRECTION = -1
RIGHT_MOTOR_DIRECTION = 1

WHEEL_DIAMETER_CM = 8.3        # measure across the tyre; setup_check fine-tunes it
WHEEL_GEAR_RATIO = 1           # motor turns for one wheel turn: 1 if the wheel is on the motor,
                               # else teeth on the wheel's gear / teeth on the motor's gear

# Lengths along the rover are measured from its TURNING POINT: the spot
# that stays still when it spins on the spot. With two drive wheels and a
# caster, it is half way between the drive wheels. With four or more wheels
# that cannot swivel, it is somewhere between them - setup_check test 6
# shows how to find it.

# The size of the rover seen from above, in cm. Measure front and back from
# the turning point to the part that sticks out furthest.
ROVER_WIDTH_CM = 15
ROVER_FRONT_CM = 7
ROVER_BACK_CM = 11

# Where the sensors sit along the rover, in cm from the turning point.
# Positive = in front of it, negative = behind it.
DISTANCE_SENSOR_POSITION_CM = 7
# Building tip: a colour sensor IN FRONT is better. To check the floor next to
# a wall, a rover with it in front just drives up and back. With it behind, the
# rover must turn round and reverse blind at every wall - slower and riskier.
COLOUR_SENSOR_POSITION_CM = -10

# Which side of the hub faces up. motion_sensor.TOP means the hub lies flat
# with its light matrix facing up. The others are motion_sensor.BOTTOM,
# FRONT, BACK, LEFT and RIGHT. The gyro needs this to measure turns.
HUB_FACE_UP = motion_sensor.TOP

MAX_RUN_SECONDS = 0            # end the run after this many seconds; 0 = no limit

# ---- Colour sensor ----
COLOURS_TO_FIND = [color.GREEN, color.RED]   # colours the rover reacts to
COLOUR_PAUSE_MS = 5000     # how long to stop on a colour, in ms
REACT_ONCE = True          # True: react to each colour only the first time it is found

# ---- Grid moves ----
COURSE_NORTH_CM = 222   # how far the course reaches from the start in each direction.
COURSE_SOUTH_CM = 0     # The rover never moves outside it. SOUTH is 0 when the start
COURSE_EAST_CM = 24     # is on the edge of the course, so the rover cannot wander
COURSE_WEST_CM = 135    # out through the entrance. These fit the real course
                        # (1.6 m x 2.3 m inside), starting in its bottom-right gap.
CHECK_BY_WALLS = True   # also check the floor next to each wall the rover meets, which its
                        # path through the middle of the squares never reaches. Slower.

# ---- Wall follower ----
KEEP_WALL_ON_RIGHT = True   # True: keep the right hand on the wall. False: the left hand.


# ======================================================================
# FINE TUNING - the defaults work for most rovers; the User Manual explains each one
# ======================================================================

# ---- Movement ----
DRIVE_SPEED = 400          # wheel speed when driving, degrees per second (max about 1000)
DRIVE_SLOW_SPEED = 150     # wheel speed at the start and end of a drive, so it starts and stops smoothly
DRIVE_SPEED_UP_CM = 4      # speed up gently over this many cm at the start; 0 = full speed at once
DRIVE_SLOW_ZONE_CM = 4     # slow down gently over this many cm at the end
TURN_SPEED = 200           # wheel speed when turning
TURN_SLOW_SPEED = 100      # wheel speed for the end of a turn, so it stops on target
TURN_SLOW_ZONE = 15        # slow down when this many degrees from the target
TURN_ACCURACY = 2          # a turn that ends further off than this many degrees is corrected
TURN_NUDGE_SPEED = 30      # wheel speed for that correction
STEERING = 10              # how strongly to steer back when drifting off course; 0 = off
STUCK_MS = 1000            # no progress for this long while driving or turning = stuck
TICK_MS = 20               # how often to check the sensors while moving, in ms

# ---- Distance sensor ----
MAX_TRUSTED_CM = 200   # readings further than this count as "no echo". The sensor
                       # cannot see further than 2 m. If no straight path in your
                       # course is that long, set this a little below the longest one.
SETTLE_MS = 150        # wait this long after moving before a careful reading

# ---- Grid moves ----
STEP_CM = 12            # size of one grid square, and the length of one step, in cm.
                        # Smaller squares fit through narrower gaps but take longer.
WALL_STOP_CM = 10       # a step stops early if the distance sensor sees a wall this close
WALL_CHECK_GAP_CM = 5   # how close that check brings the front or back of the rover to the wall


# ======================================================================
# SETUP
# ======================================================================
# Everything about how YOUR rover is built: which port each part is plugged
# into, which way the motors face, the wheel size and where the sensors sit.
# Every other module reads these settings, so get them right first.
#
#   setup_check()      run this first on a new rover - it tests each part, one
#                      at a time, and tells you which setting to change if one
#                      is wrong. The LEFT and RIGHT hub buttons move between tests.
#   run_program(...)   starts a program (see YOUR PROGRAM at the bottom)
#   end_run()          finish the whole run straight away, from anywhere

# ---- Talking to the motors and the gyro ----

def set_wheel_speeds(left, right):
    """Spin the drive wheels. Speeds are in degrees per second, + = forward.

    The MOTOR_DIRECTION settings take care of which way each motor faces,
    so the rest of the program can simply say "forward" or "backward".
    """
    motor.run(LEFT_MOTOR_PORT, int(left * LEFT_MOTOR_DIRECTION))
    motor.run(RIGHT_MOTOR_PORT, int(right * RIGHT_MOTOR_DIRECTION))


def stop():
    """Stop both drive wheels."""
    motor.stop(LEFT_MOTOR_PORT)
    motor.stop(RIGHT_MOTOR_PORT)


def reset_wheel_counters():
    """Start counting wheel turns from zero (see wheel_degrees)."""
    motor.reset_relative_position(LEFT_MOTOR_PORT, 0)
    motor.reset_relative_position(RIGHT_MOTOR_PORT, 0)


def wheel_degrees():
    """How far the wheels have turned since reset_wheel_counters(), in degrees.

    It is the average of both wheels, and always positive, whichever way the
    rover went.
    """
    left = abs(motor.relative_position(LEFT_MOTOR_PORT))
    right = abs(motor.relative_position(RIGHT_MOTOR_PORT))
    return (left + right) / 2


def cm_to_wheel_degrees(cm):
    """How many degrees the motors turn to roll the rover cm forward.

    One full turn of a wheel (360 degrees) rolls the rover forward by the
    wheel's circumference, which is pi x the diameter. With gears, the motor
    turns WHEEL_GEAR_RATIO times for each turn of the wheel."""
    return cm / (math.pi * WHEEL_DIAMETER_CM) * 360 * WHEEL_GEAR_RATIO


def wheel_degrees_to_cm(degrees):
    return degrees / WHEEL_GEAR_RATIO / 360 * math.pi * WHEEL_DIAMETER_CM


def gyro_heading():
    """Which way the rover faces right now, in degrees, from the hub's gyro.

    0 is the way it faced when the program started. Turning LEFT makes the
    number bigger and turning RIGHT makes it smaller. It goes from -180 to 180.
    """
    return motion_sensor.tilt_angles()[0] / 10


def normalise(angle):
    """Bring any angle into the range -180 to 180, so 270 becomes -90."""
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def heading_difference(target, current):
    """How far to turn from current to face target, the short way round.

    Positive = turn left, negative = turn right. From 170 to -170 is
    20 degrees left, not 340 degrees right.
    """
    return normalise(target - current)


# ---- Checking the settings ----
# Before the rover moves, every module checks its own settings, so a typing
# mistake gets a clear message instead of strange driving. Each module adds
# its check to this list.

SETTINGS_CHECKS = []
settings_ok = True


def setting_problem(message):
    global settings_ok
    print("SETTINGS PROBLEM: " + message)
    settings_ok = False


def check_number(name, value, low, high):
    """Complain unless value is a number from low to high."""
    if not isinstance(value, (int, float)) or value < low or value > high:
        setting_problem(name + " is " + str(value) + ", but it should be a number from "
                        + str(low) + " to " + str(high))


def check_true_false(name, value):
    """Complain unless value is True or False."""
    if value is not True and value is not False:
        setting_problem(name + " is " + str(value) + ", but it should be True or False")


def check_setup_settings():
    ports = [port.A, port.B, port.C, port.D, port.E, port.F]
    used = [LEFT_MOTOR_PORT, RIGHT_MOTOR_PORT, DISTANCE_SENSOR_PORT, COLOUR_SENSOR_PORT]
    for value in used:
        if value not in ports:
            setting_problem("every _PORT setting should be port.A to port.F")
    if len(set(used)) < len(used):
        setting_problem("two parts are set to the same port - check the _PORT settings")
    if LEFT_MOTOR_DIRECTION != 1 and LEFT_MOTOR_DIRECTION != -1:
        setting_problem("LEFT_MOTOR_DIRECTION is " + str(LEFT_MOTOR_DIRECTION) + ", but it should be 1 or -1")
    if RIGHT_MOTOR_DIRECTION != 1 and RIGHT_MOTOR_DIRECTION != -1:
        setting_problem("RIGHT_MOTOR_DIRECTION is " + str(RIGHT_MOTOR_DIRECTION) + ", but it should be 1 or -1")
    check_number("WHEEL_DIAMETER_CM", WHEEL_DIAMETER_CM, 2, 20)
    check_number("WHEEL_GEAR_RATIO", WHEEL_GEAR_RATIO, 0.1, 10)
    check_number("ROVER_WIDTH_CM", ROVER_WIDTH_CM, 5, 40)
    check_number("ROVER_FRONT_CM", ROVER_FRONT_CM, 0, 40)
    check_number("ROVER_BACK_CM", ROVER_BACK_CM, 0, 40)
    check_number("DISTANCE_SENSOR_POSITION_CM", DISTANCE_SENSOR_POSITION_CM, -40, 40)
    check_number("COLOUR_SENSOR_POSITION_CM", COLOUR_SENSOR_POSITION_CM, -40, 40)
    check_number("MAX_RUN_SECONDS", MAX_RUN_SECONDS, 0, 3600)


SETTINGS_CHECKS.append(check_setup_settings)


# ---- Starting and finishing a run ----

class RunFinished(Exception):
    """end_run() raises this to stop the program from wherever it is."""


def end_run():
    """Finish the whole run straight away, from anywhere in your program."""
    stop()
    raise RunFinished()


run_started_ms = 0


def check_time_limit():
    """End the run once MAX_RUN_SECONDS have passed. Every movement checks
    this all the time, so the rover stops even in the middle of a move."""
    if MAX_RUN_SECONDS > 0:
        if time.ticks_diff(time.ticks_ms(), run_started_ms) > MAX_RUN_SECONDS * 1000:
            print("Time limit of " + str(MAX_RUN_SECONDS) + " s reached")
            end_run()


async def run_program(program):
    """Run one of the programs, from start to finish.

    The rover must be standing still and facing the way you want to call
    NORTH when this starts: the gyro sets its zero here.
    """
    global run_started_ms
    print("=== ROVER SOFTWARE " + SOFTWARE_VERSION + " ===")
    for check in SETTINGS_CHECKS:
        check()
    if not settings_ok:
        print("Fix the settings above, then run the program again.")
        return
    motion_sensor.set_yaw_face(HUB_FACE_UP)
    motion_sensor.reset_yaw(0)
    run_started_ms = time.ticks_ms()
    try:
        await program()
    except RunFinished:
        pass
    stop()
    print("=== RUN FINISHED ===")


# ---- Colour names, for printing ----
# The SPIKE library spells it "color"; this program uses "colour" in its own names.

COLOUR_NAMES = {
    color.BLACK: "BLACK", color.MAGENTA: "MAGENTA", color.PURPLE: "PURPLE",
    color.BLUE: "BLUE", color.AZURE: "AZURE", color.TURQUOISE: "TURQUOISE",
    color.GREEN: "GREEN", color.YELLOW: "YELLOW", color.ORANGE: "ORANGE",
    color.RED: "RED", color.WHITE: "WHITE",
}


def colour_name(colour):
    """The name of a colour, e.g. colour_name(color.GREEN) gives "GREEN"."""
    if colour in COLOUR_NAMES:
        return COLOUR_NAMES[colour]
    return "NONE"


# ---- Setup check: run this first on a new rover ----
# It runs one test at a time and waits for you between tests, using the
# LEFT and RIGHT buttons on the hub (the middle button stops the program).
# Read what to look for in the console in the SPIKE App.

async def wait_for_button():
    """Wait until LEFT or RIGHT is pressed and let go. Returns "left" or "right"."""
    # First make sure no button is still held, so one press only counts once.
    while button.pressed(button.LEFT) or button.pressed(button.RIGHT):
        await runloop.sleep_ms(20)
    while True:
        if button.pressed(button.LEFT):
            choice = "left"
            break
        if button.pressed(button.RIGHT):
            choice = "right"
            break
        await runloop.sleep_ms(20)
    while button.pressed(button.LEFT) or button.pressed(button.RIGHT):
        await runloop.sleep_ms(20)
    return choice


async def right_pressed_within(ms):
    """Wait up to ms milliseconds, but stop early and return True if RIGHT is pressed."""
    waited = 0
    while waited < ms:
        if button.pressed(button.RIGHT):
            return True
        await runloop.sleep_ms(20)
        waited += 20
    return False


def raw_distance_cm():
    """The distance sensor reading in cm: -1 means no echo, None means no sensor found."""
    try:
        mm = distance_sensor.distance(DISTANCE_SENSOR_PORT)
    except Exception:
        return None
    if mm is None or mm < 0:
        return -1
    return mm / 10


async def check_left_wheel():
    print("LEFT WHEEL. Put the rover on the floor, then press RIGHT to start.")
    await wait_for_button()
    set_wheel_speeds(300, 0)
    await runloop.sleep_ms(1000)
    stop()
    print("   Only the LEFT wheel should have turned, rolling FORWARD.")
    print("   The right wheel turned instead? Swap LEFT_MOTOR_PORT and RIGHT_MOTOR_PORT.")
    print("   The left wheel rolled backward? Change LEFT_MOTOR_DIRECTION (1 <-> -1).")


async def check_right_wheel():
    print("RIGHT WHEEL. Press RIGHT to start.")
    await wait_for_button()
    set_wheel_speeds(0, 300)
    await runloop.sleep_ms(1000)
    stop()
    print("   Only the RIGHT wheel should have turned, rolling FORWARD.")
    print("   The right wheel rolled backward? Change RIGHT_MOTOR_DIRECTION (1 <-> -1).")


async def check_gyro():
    print("GYRO. The rover will spin LEFT (anticlockwise, seen from above) for")
    print("   1 second. Press RIGHT to start.")
    await wait_for_button()
    start = gyro_heading()
    set_wheel_speeds(-200, 200)
    await runloop.sleep_ms(1000)
    stop()
    await runloop.sleep_ms(500)
    turned = heading_difference(gyro_heading(), start)
    print("   The gyro measured " + str(round(turned)) + " degrees (+ means left).")
    if turned > 20:
        print("   OK")
    elif turned < -20:
        print("   PROBLEM: the gyro measured a RIGHT turn.")
        print("   If the rover really turned right: swap LEFT_MOTOR_PORT and RIGHT_MOTOR_PORT.")
        print("   If it really turned left: the hub is upside down, so change HUB_FACE_UP.")
    else:
        print("   PROBLEM: the gyro hardly changed. Is the hub on its side? Change HUB_FACE_UP.")


async def check_drive():
    global target_heading
    print("DRIVE 30 CM. Mark the floor beside the middle of a wheel, with at least")
    print("   40 cm of space ahead, then press RIGHT to start.")
    await wait_for_button()
    motion_sensor.reset_yaw(0)     # drive straight ahead from where it points now
    target_heading = 0
    await drive_forward(30)
    print("   Measure how far the middle of the wheel moved. If it was not 30 cm, set")
    print("   WHEEL_DIAMETER_CM = " + str(WHEEL_DIAMETER_CM) + " x (cm it really moved) / 30")


async def check_turns():
    global target_heading
    print("TURNING. The rover will turn a quarter turn LEFT, then back again.")
    print("   Press RIGHT to start.")
    await wait_for_button()
    motion_sensor.reset_yaw(0)
    target_heading = 0
    reset_wheel_counters()
    await turn_to(WEST)
    await runloop.sleep_ms(1000)
    # How far the motors turned for that quarter turn - scaled to exactly
    # 90 degrees, as the turn may have stopped a little off.
    turned = abs(gyro_heading())
    if turned > 45:
        quarter = round(wheel_degrees() * 90 / turned)
    else:
        quarter = None
    await turn_to(NORTH)
    print("   Both turns should look like neat quarter turns, and the 'turn:' lines")
    print("   above should stop within " + str(TURN_ACCURACY) + " degrees of the target.")
    print("   Turns wobble or overshoot a lot? Lower TURN_SLOW_SPEED.")
    if quarter is not None:
        print("   A quarter turn took " + str(quarter) + " motor degrees. For the simulator:")
        print("   type that into 'Motor degrees for a quarter turn' on its Rover tab.")


async def check_turning_point():
    global target_heading
    print("TURNING POINT. Put a mark on the floor at the very front of the rover,")
    print("   in the middle. Press RIGHT: the rover turns half a turn.")
    await wait_for_button()
    motion_sensor.reset_yaw(0)
    target_heading = 0
    await turn_to(SOUTH)
    print("   Now mark the front of the rover again, and measure between the marks.")
    print("   The turning point is half that far behind the front, so set")
    print("   ROVER_FRONT_CM to half of it. Measure ROVER_BACK_CM and the SENSOR")
    print("   POSITION settings from that point too.")
    print("   ROVER_FRONT_CM is " + str(ROVER_FRONT_CM) + " now, so the marks should be "
          + str(2 * ROVER_FRONT_CM) + " cm apart.")
    print("   For the simulator: type ROVER_FRONT_CM into 'Turning point, cm behind")
    print("   the front' on its Rover tab.")


async def check_distance_sensor():
    print("DISTANCE SENSOR. Move your hand in front of the sensor and watch the")
    print("   readings. Press RIGHT when you have seen enough.")
    while True:
        cm = raw_distance_cm()
        if cm is None:
            print("   PROBLEM: no distance sensor on DISTANCE_SENSOR_PORT")
            return
        if cm == -1:
            print("   nothing in range")
        else:
            print("   " + str(cm) + " cm")
        if await right_pressed_within(500):
            break
    print("   Now stand the rover facing a wall. Measure from the wall to the TURNING")
    print("   POINT (see the turning point test - not the front of the rover or the")
    print("   sensor) and make that exactly 30 cm. Press RIGHT to measure.")
    await wait_for_button()
    readings = []
    for i in range(5):
        cm = raw_distance_cm()
        if cm is not None and cm != -1:
            readings.append(cm)
        await runloop.sleep_ms(50)
    if len(readings) == 0:
        print("   PROBLEM: no echo from the wall. Is the sensor pointing straight at it?")
        return
    readings.sort()
    cm = readings[len(readings) // 2]
    suggested = round(30 - cm, 1)
    print("   The sensor reads " + str(cm) + " cm, so DISTANCE_SENSOR_POSITION_CM should")
    print("   be about " + str(suggested) + ". It is set to " + str(DISTANCE_SENSOR_POSITION_CM) + ".")
    if abs(suggested - DISTANCE_SENSOR_POSITION_CM) > 3:
        print("   That is quite different. Check the 30 cm went to the turning point,")
        print("   not to the front of the sensor - then press LEFT to try again.")


async def check_colour_sensor():
    print("COLOUR SENSOR. Slide coloured paper under the sensor and watch the")
    print("   readings. Press RIGHT when you have seen enough.")
    while True:
        try:
            seen = color_sensor.color(COLOUR_SENSOR_PORT)
        except Exception:
            print("   PROBLEM: no colour sensor on COLOUR_SENSOR_PORT")
            return
        print("   " + colour_name(seen))
        if await right_pressed_within(500):
            break


async def setup_check():
    """Test each part of the rover, one test at a time.

    Every test waits for you to press RIGHT before it starts. When it has
    finished, press RIGHT to go on to the next test, or LEFT to do the same
    test again - for example to measure twice. A setting you change only
    takes effect when you run the program again.
    """
    checks = [check_left_wheel, check_right_wheel, check_gyro, check_drive,
              check_turns, check_turning_point, check_distance_sensor, check_colour_sensor]
    print("=== SETUP CHECK ===")
    print("Use the LEFT and RIGHT buttons on the hub to go through the tests.")
    number = 0
    while number < len(checks):
        print("")
        print("TEST " + str(number + 1) + " OF " + str(len(checks)) + ":")
        await checks[number]()
        print("   Press RIGHT for the next test, or LEFT to do this one again.")
        if await wait_for_button() == "right":
            number += 1
    print("")
    print("=== SETUP CHECK DONE ===")
    print("Change any settings it suggested, then run it again to make sure.")


# ======================================================================
# MOVEMENT
# ======================================================================
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

def check_movement_settings():
    check_number("DRIVE_SPEED", DRIVE_SPEED, 50, 1000)
    check_number("DRIVE_SLOW_SPEED", DRIVE_SLOW_SPEED, 20, 1000)
    check_number("DRIVE_SPEED_UP_CM", DRIVE_SPEED_UP_CM, 0, 20)
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
    speed_up = cm_to_wheel_degrees(DRIVE_SPEED_UP_CM)
    slow_zone = cm_to_wheel_degrees(DRIVE_SLOW_ZONE_CM)
    top = abs(speed)
    low = min(top, DRIVE_SLOW_SPEED)
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

            # Speed up gently at the start and slow down gently at the end,
            # so the rover does not lurch, and stops on the spot instead of
            # rolling on past the end. The speed goes in a straight line
            # from low to top over the first DRIVE_SPEED_UP_CM, and back
            # down to low over the last DRIVE_SLOW_ZONE_CM.
            done = wheel_degrees()
            now_speed = top
            if done < speed_up:
                now_speed = low + (top - low) * done / speed_up
            if goal - done < slow_zone:
                now_speed = min(now_speed, low + (top - low) * (goal - done) / slow_zone)
            if speed < 0:
                now_speed = -now_speed

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


# ======================================================================
# DISTANCE SENSOR
# ======================================================================
# Read the distance sensor and use it to stop before walls. Once this module
# is installed, drive_forward() can stop early for a wall too.
#
#   read_distance()                  distance ahead right now, in cm (-1 = no echo)
#   await measure_distance()         a careful reading, standing still
#   await drive_to_wall(10)          drive forward until a wall is 10 cm away
#   await drive_forward(80, stop_at_wall_cm=10)   drive 80 cm, or stop early for a wall

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


# ======================================================================
# COLOUR SENSOR
# ======================================================================
# Watches the floor while the rover moves. When the sensor arrives on one of
# the colours in COLOURS_TO_FIND, the rover stops and on_colour_found() runs.
# Afterwards the move it was making carries on. This happens during every
# drive and turn, including the autonomous searches, without you calling
# anything.
#
#   on_colour_found(colour)   what to do on a colour - WRITE YOUR OWN ACTIONS HERE
#   read_colour()             the colour under the sensor right now
#   found_colours             a list of the colours found so far

def check_colour_settings():
    if not isinstance(COLOURS_TO_FIND, list):
        setting_problem("COLOURS_TO_FIND should be a list in square brackets, like [color.GREEN, color.RED]")
    check_number("COLOUR_PAUSE_MS", COLOUR_PAUSE_MS, 0, 60000)
    check_true_false("REACT_ONCE", REACT_ONCE)


SETTINGS_CHECKS.append(check_colour_settings)

class ColourReached(Exception):
    """explore(find=...) uses this to stop whatever the rover is doing the
    moment the colour sensor arrives on the colour it is looking for."""


found_colours = []         # colours found so far, in the order they were found
colour_spots = {}          # where each colour was first seen: colour -> (cm east, cm north)
looking_for = None         # set by explore(find=...): the one colour that counts right now
react_to_colours = True    # explore(find=...) sets this to False: on_colour_found() is then off
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


def colour_sensor_position():
    """Where the colour sensor is over the floor right now, in cm from the
    start: (cm east, cm north). It sits COLOUR_SENSOR_POSITION_CM in front of
    the turning point - behind it if that number is negative."""
    angle = gyro_heading() * math.pi / 180      # degrees to radians
    east = position_east_cm - math.sin(angle) * COLOUR_SENSOR_POSITION_CM
    north = position_north_cm + math.cos(angle) * COLOUR_SENSOR_POSITION_CM
    return (east, north)


async def check_colour():
    """Every movement calls this many times a second. It reacts only at the
    moment the sensor ARRIVES on a colour, so sitting on a patch counts once."""
    global last_colour
    colour = read_colour()
    just_arrived = colour != last_colour
    last_colour = colour
    if not just_arrived or colour is None:
        return
    if colour not in colour_spots:
        colour_spots[colour] = colour_sensor_position()
    if looking_for is not None:
        # explore(find=...) is running, and only its colour counts.
        if colour == looking_for:
            stop()
            print("COLOUR: found " + colour_name(colour))
            if colour not in found_colours:
                found_colours.append(colour)
            raise ColourReached()
        return
    if not react_to_colours or colour not in COLOURS_TO_FIND:
        return
    if REACT_ONCE and colour in found_colours:
        return
    if colour not in found_colours:
        found_colours.append(colour)
    stop()
    await on_colour_found(colour)


# ======================================================================
# GRID MOVES
# ======================================================================
# Used by both autonomy modules. They think of the floor as a grid of
# squares, STEP_CM wide. The rover starts in the middle of square (0, 0),
# facing NORTH. The first number counts squares to the EAST (right of the
# start), the second counts squares to the NORTH (ahead of the start).
#
#   next_square(square, direction)   the square next door in that direction
#   inside_course(square)            False for squares outside the COURSE_ limits
#   await step(direction)            try to move one square: "done", "blocked" or "no room"
#   await check_by_wall(direction)   sweep the colour sensor up to the wall ahead

def check_grid_settings():
    check_number("STEP_CM", STEP_CM, 5, 50)
    check_number("WALL_STOP_CM", WALL_STOP_CM, 5, 50)
    check_number("COURSE_NORTH_CM", COURSE_NORTH_CM, 0, 1000)
    check_number("COURSE_SOUTH_CM", COURSE_SOUTH_CM, 0, 1000)
    check_number("COURSE_EAST_CM", COURSE_EAST_CM, 0, 1000)
    check_number("COURSE_WEST_CM", COURSE_WEST_CM, 0, 1000)
    check_true_false("CHECK_BY_WALLS", CHECK_BY_WALLS)
    check_number("WALL_CHECK_GAP_CM", WALL_CHECK_GAP_CM, 2, 30)


SETTINGS_CHECKS.append(check_grid_settings)

# How one step in each direction changes the square: (east, north).
MOVES = {NORTH: (0, 1), WEST: (-1, 0), SOUTH: (0, -1), EAST: (1, 0)}
DIRECTION_NAMES = {NORTH: "NORTH", WEST: "WEST", SOUTH: "SOUTH", EAST: "EAST"}


def next_square(square, direction):
    """The square next to square in direction, e.g. next_square((0, 0), NORTH) is (0, 1)."""
    move = MOVES[direction]
    return (square[0] + move[0], square[1] + move[1])


def inside_course(square):
    """True if the middle of square is inside the COURSE_ limits."""
    east_cm = square[0] * STEP_CM
    north_cm = square[1] * STEP_CM
    if east_cm > COURSE_EAST_CM or east_cm < -COURSE_WEST_CM:
        return False
    if north_cm > COURSE_NORTH_CM or north_cm < -COURSE_SOUTH_CM:
        return False
    return True


async def step(direction, been_there=False):
    """Move one square in direction.

    Set been_there to True when the rover has stood in that square before.
    It then knows there is room, so:
      - it does not stop for walls (a wall just beyond that square could
        otherwise stop it short - it still notices if it gets stuck)
      - if the square is straight behind it, it reverses into it instead of
        turning round, which needs no room to turn

    Returns how it went:
      "done"     it reached the next square
      "blocked"  something was in the way, so it came back to where it started
      "no room"  there was not enough room to turn to face that way
    """
    name = DIRECTION_NAMES[direction]
    behind = normalise(target_heading + 180)
    if been_there and direction == behind:
        await drive_backward(STEP_CM)
        print("step: " + name + " done (reversed)")
        return "done"
    if not await turn_to(direction):
        print("step: " + name + " - no room to turn that way")
        return "no room"
    stop_cm = WALL_STOP_CM
    if been_there:
        stop_cm = 0
    result = await drive_forward(STEP_CM, stop_at_wall_cm=stop_cm)
    if result == "done":
        print("step: " + name + " done")
        return "done"
    print("step: " + name + " blocked (" + result + "), going back")
    await drive_backward(cm_driven())
    return "blocked"


async def check_by_wall(direction):
    """Sweep the colour sensor over the strip of floor next to the wall ahead.

    The rover's path runs through the middle of the squares, so it never
    crosses the strip of floor between the last square and a wall. A patch
    could be there as much as anywhere else, so this brings the colour
    sensor into that strip and back:
      - colour sensor at the front: drive towards the wall, then back
      - colour sensor at the back: turn round and reverse towards it, then back
    Either way, the rover stops WALL_CHECK_GAP_CM short of the wall. Nothing
    happens if CHECK_BY_WALLS is False, there is no wall close ahead, or
    there is no room to turn round.
    """
    if not CHECK_BY_WALLS:
        return
    if not await turn_to(direction):
        return
    distance = await measure_distance()
    if distance == -1 or distance > STEP_CM + WALL_STOP_CM:
        return       # no wall close ahead
    # How far the wall is from the turning point. distance is measured
    # from the distance sensor, which sits in front of it.
    wall_cm = distance + DISTANCE_SENSOR_POSITION_CM
    if COLOUR_SENSOR_POSITION_CM >= 0:
        # Drive forward until the front of the rover is WALL_CHECK_GAP_CM
        # from the wall. Parts sticking out in front of the distance sensor
        # count too.
        stop_cm = WALL_CHECK_GAP_CM + ROVER_FRONT_CM - DISTANCE_SENSOR_POSITION_CM
        move = distance - stop_cm
        if move < 3:
            return   # already close enough
        print("wall check: driving up to the wall")
        await drive_forward(move, stop_at_wall_cm=stop_cm)
        await drive_backward(cm_driven())
    else:
        # Turn round, then reverse until the back of the rover is
        # WALL_CHECK_GAP_CM from the wall. The reverse is blind - there is
        # no sensor at the back - so it goes by the distance measured now.
        move = wall_cm - ROVER_BACK_CM - WALL_CHECK_GAP_CM
        if move < 3:
            return   # already close enough
        if not await turn_to(direction + 180):
            return   # no room to turn round here
        # Reverse slowly: if the reading was a little out, the rover only
        # touches the wall gently, and its stuck check stops it.
        print("wall check: reversing up to the wall")
        await drive(move, -DRIVE_SLOW_SPEED)
        await drive_forward(cm_driven())


# ======================================================================
# WALL FOLLOWER
# ======================================================================
# Autonomy option 1. The rover keeps one hand on a wall and follows it, the
# way you could find your way round a maze in the dark. It needs no map, so
# it is simple and easy to predict.
#
# How it works, one grid square at a time:
#   1. Drive straight on until there is a wall ahead.
#   2. Turn so that wall is on the hand side.
#   3. At every square, try these in order: turn towards the hand, straight
#      on, turn away from the hand, go back. Take the first one that works.
#   4. Stop when it is about to make its very first move again: it has
#      been all the way round. (It also stops if it finds itself going round
#      the same loop again and again.)
#
# It remembers every square it tried to drive into and could not, and
# treats those squares as wall from then on. (When there is only no room
# to turn that way, it simply tries the next way.) Real walls do not line up
# with the grid, so a square can look blocked from one side and open from
# another. Remembering keeps the rover's hand on the wall instead of
# letting it wander off in circles.
#
# It only visits squares along the walls it follows. A patch in the middle
# of a big open space, or next to a wall that is not joined to the others,
# can be missed. Choose the hand that suits your course!
#
#   await follow_wall()

def check_wall_follower_settings():
    check_true_false("KEEP_WALL_ON_RIGHT", KEEP_WALL_ON_RIGHT)


SETTINGS_CHECKS.append(check_wall_follower_settings)


async def follow_wall():
    print("=== WALL FOLLOWER START ===")
    if KEEP_WALL_ON_RIGHT:
        hand = -90          # a right turn
    else:
        hand = 90           # a left turn
    square = (0, 0)
    facing = NORTH
    visited = {square}      # squares the rover has stood on
    walls = set()           # squares it tried to drive into and could not
    first_move = None       # (square, direction) of its first move along the wall
    times_made = {}         # how many times it has made each (square, direction) move

    # 1. Drive straight on until there is a wall ahead.
    while True:
        ahead = next_square(square, facing)
        if not inside_course(ahead):
            break
        if await step(facing) != "done":
            walls.add(ahead)
            await check_by_wall(facing)
            break
        square = ahead
        visited.add(square)

    # 2. Turn away from the hand, so the wall ahead ends up on the hand side.
    facing = normalise(facing - hand)

    # 3. Follow the wall.
    while True:
        moved = False
        for turn in [hand, 0, -hand, 180]:
            direction = normalise(facing + turn)
            ahead = next_square(square, direction)
            if ahead in walls or not inside_course(ahead):
                continue
            # 4. Back to the first move? Then it has been all the way round.
            move = (square, direction)
            if move == first_move:
                print("follow: back to its first move - all the way round, finished")
                return
            if times_made.get(move, 0) >= 2:
                print("follow: going round the same loop again - finished")
                return
            result = await step(direction, ahead in visited)
            if result == "done":
                if first_move is None:
                    first_move = move
                times_made[move] = times_made.get(move, 0) + 1
                square = ahead
                visited.add(square)
                facing = direction
                moved = True
                break
            if result == "blocked" and ahead not in visited:
                walls.add(ahead)
                await check_by_wall(direction)    # a new bit of wall: look for a patch by it
            # "no room": not enough room to turn that way here - try the next way
        if not moved:
            print("follow: no way out of square " + str(square))
            return


# ======================================================================
# YOUR PROGRAM
# ======================================================================

async def my_program():
    # Write your own route here. This example drives a 30 cm square.
    for side in range(4):
        await drive_forward(30)
        await turn_left(90)
    # Another example: drive until a wall is 10 cm away, then turn to face WEST.
    # await drive_to_wall(10)
    # await turn_to(WEST)


# Choose what runs: exactly ONE of these lines must have no # in front.
# Run setup_check first on a new rover.
# runloop.run(run_program(my_program))
# runloop.run(run_program(setup_check))
runloop.run(run_program(follow_wall))
