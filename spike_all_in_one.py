# ======================================================================
# ROVER SOFTWARE - EVERYTHING (FOR TESTING) - All modules
# ======================================================================
# Package: Everything (for testing). Version 1.2, built 2026-10-20.
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

# ---- Maze explorer ----
HEAD_TOWARDS = None        # which way to search first when explore() gets no near= or towards=.
                           # A heading in degrees: 0 = NORTH, 90 = WEST, 180 = SOUTH, -90 = EAST
                           # (the names NORTH, WEST... work too). 30 = mostly north, a bit west.
                           # None = no preference. Avoid exact diagonals like NORTH_WEST: north and
                           # west then tie, and the rover just keeps going the way it faces.


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

# ---- Maze explorer ----
HEAD_STRENGTH = 1          # how strongly to follow a hint: how many extra steps the rover will drive
                           # to reach a square one step further that way, or one step nearer the spot
NO_ECHO_SQUARES = 2        # when a look gets no echo, count this many squares ahead as open


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
# Colours that must be found in a set ORDER: use explore(find=...) from the
# Maze explorer instead (see the MAZE EXPLORER section). Once your program
# uses it, on_colour_found() no longer runs. A colour only counts when an
# explore(find=...) is looking for it, so driving over RED while looking
# for GREEN does nothing.
#
# The rover also remembers where it first saw each colour - even one it did
# not react to - so the explorer can go straight back to it later.
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
    #    Need to drive, or find colours in a set order? Use explore(find=...)
    #    instead (see the MAZE EXPLORER section): the lines after it in your
    #    program are your actions, and they may drive. This function then
    #    does not run at all.
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
# MAZE EXPLORER
# ======================================================================
# Autonomy option 2. The rover draws a map of the course as it goes, and
# keeps heading for the nearest square it has not searched yet, until it has
# searched everywhere it can reach. It finds patches out in the open that the
# wall follower misses, but it is slower and harder to follow.
#
#   await explore()                   search everywhere; on_colour_found()
#                                     reacts to colours on the way
#   await explore(find=color.GREEN)   search until the colour sensor is on
#                                     GREEN, stop there, and go on with your
#                                     program. Gives True if it found it.
#
# ---- Finding colours in order ----
# In your own program (see YOUR PROGRAM at the bottom), write one
# explore(find=...) for each colour, in the order they must be found. The
# lines after each one are your actions for that colour, and they may drive:
#
#   await explore(find=color.GREEN, near=(-30, 110))
#   await drive_forward(8)          # e.g. get the payload over the patch
#   ...your payload code...
#   await explore(find=color.RED, towards=30)
#
# - Only the colour it is looking for counts: driving over RED while it
#   looks for GREEN does nothing.
# - It keeps its map from one explore() to the next. It does not search the
#   same floor twice, and if it drove over a colour before that colour's
#   turn, it goes straight back there.
# - It keeps track of how far your actions drive it, and starts the next
#   explore() from the middle of the nearest square.
# - If it searches everywhere without finding the colour, it searches
#   everywhere once more, then gives up and gives False.
#
# ---- Telling it where to search first ----
# Both hints are optional. The rover still searches everywhere in the end;
# it just searches there first.
#   near=(-30, 110)   roughly where the colour is: (cm to the RIGHT of the
#                     start, cm AHEAD of it). Use a minus for left, or
#                     behind: (-30, 110) is 30 cm left and 110 cm ahead.
#                     The rover heads there, then searches around it. Use it
#                     when you know roughly where a colour is.
#   towards=30        which way to search, as a heading (see below). The
#                     rover keeps going that way until walls stop it. Use it
#                     when you only know which side a colour is on.
# With neither, it uses the HEAD_TOWARDS setting. Neither hint can see
# walls: a dead end on the way still costs a detour.
#
# Headings are in degrees, measured like the gyro: NORTH is 0 and the number
# grows as you turn LEFT, so WEST is 90, SOUTH is 180 and EAST is -90. Any
# number works, not just the eight named directions - and a number in
# between is often better, because it says which way matters MORE:
#   30           "mostly north, a bit west". North counts for more than
#                west, so the rover heads north wherever it can, and west
#                when north is blocked.
#   NORTH_WEST   (45) north and west count exactly the same, so the rover
#                cannot choose between them. It keeps going whichever way it
#                already faces - which can take it into a dead end that
#                30 would have skipped.
#
# ---- How it works ----
# The map remembers:
#   - which squares the rover has stood on, and which it has searched
#   - which moves between squares are open, and which are blocked by a wall
#   - which squares are "solid": so close to a wall the rover can never stand there
#
# Each time round its main loop, the explorer:
#   1. Plans: picks the unsearched square to head for with a ripple search
#      (next_move) - the nearest one, or with a hint, one that is near and
#      also lies the right way.
#   2. Looks: if it does not know yet whether that first move is open, and
#      has never been in that square, it faces that way and measures. One
#      look maps a whole line of squares.
#   3. Moves one square, or marks the move as blocked if it could not.
#
# If the back of the rover would hit something as it turns to face a new
# way, it turns back and marks that way as blocked from that square. To go
# back to a square right behind it, it reverses instead of turning round.

def check_explorer_settings():
    if HEAD_TOWARDS is not None and (not isinstance(HEAD_TOWARDS, (int, float))
                                     or HEAD_TOWARDS < -360 or HEAD_TOWARDS > 360):
        setting_problem("HEAD_TOWARDS should be a heading in degrees from -360 to 360, "
                        + "such as 30 or NORTH (without quote marks), or None")
    check_number("HEAD_STRENGTH", HEAD_STRENGTH, 0, 10)
    check_number("NO_ECHO_SQUARES", NO_ECHO_SQUARES, 0, 10)


SETTINGS_CHECKS.append(check_explorer_settings)


class CourseMap:
    """Everything the rover has learnt about the course so far."""
    def __init__(self):
        self.visited = {(0, 0)}       # squares the rover has stood on
        self.searched = {(0, 0)}      # squares it has searched, so it need not search them again
        self.solid = set()            # squares the rover can never stand on
        self.open = set()             # (square, direction) moves known to be open
        self.blocked = set()          # (square, direction) moves known to be blocked


# The explorer keeps these from one explore() to the next.
course_map = CourseMap()
rover_square = (0, 0)       # the square the rover was in at the start of its last move
square_position = (0, 0)    # its position (see Movement) when it stood in the middle of that square


def can_move(course_map, square, direction):
    """Could the rover move from square in direction, as far as the map knows?

    Moves it has never tried count as possible: that is what sends the rover
    off to look at new places.
    """
    ahead = next_square(square, direction)
    if not inside_course(ahead):
        return False
    if ahead in course_map.solid:
        return False
    if (square, direction) in course_map.blocked:
        return False
    return True


def course_squares():
    """How many squares the course has."""
    wide = COURSE_WEST_CM // STEP_CM + COURSE_EAST_CM // STEP_CM + 1
    deep = COURSE_SOUTH_CM // STEP_CM + COURSE_NORTH_CM // STEP_CM + 1
    return wide * deep


def square_number(square):
    """Number the course's squares 0, 1, 2 ... row by row, from the
    south-west corner. square must be inside the course."""
    wide = COURSE_WEST_CM // STEP_CM + COURSE_EAST_CM // STEP_CM + 1
    east = square[0] + COURSE_WEST_CM // STEP_CM
    north = square[1] + COURSE_SOUTH_CM // STEP_CM
    return north * wide + east


def next_move(course_map, square, facing, towards=None, near=None):
    """Choose the unsearched square to head for, and the first move towards it.

    This is a "ripple" search (computer scientists call it a breadth-first
    search). Imagine dropping a stone into water on the rover's square. The
    ripple spreads out one square at a time, to every square the rover could
    move to, so it reaches each square by the shortest route. Each square in
    the ripple remembers how many steps away it is, and which way the ripple
    left the rover's square: the first move of that route.

    With no hint (towards and near both None), the first unsearched square
    the ripple reaches wins: it is the nearest one. With a hint, every
    unsearched square gets a score, and the lowest score wins:
      near     its number of steps, plus HEAD_STRENGTH for every square it is
               away from the spot (here near is in squares, not cm)
      towards  its number of steps, minus HEAD_STRENGTH for every square it
               lies that way
    If both are given, near wins. If two squares score exactly the same, the
    one the ripple reached first wins, and the ripple starts with the way the
    rover already faces.

    Returns (first move, target square), or (None, None) when every square it
    can reach has been searched.
    """
    # Try the way the rover already faces first, so it prefers going straight on.
    directions = [facing]
    for direction in [NORTH, WEST, SOUTH, EAST]:
        if direction != facing:
            directions.append(direction)
    if towards is not None:
        # How far one square NORTH, and one square EAST, takes the rover in the
        # towards direction, in hundredths of a square. The cos and sin work
        # it out: NORTH (0) gives 100 and 0, WEST (90) gives 0 and -100, 30
        # gives 87 and -50, NORTH_WEST (45) gives 71 and -71. Rounding to
        # whole numbers means squares that are equally far that way score
        # exactly the same, instead of differing by a tiny rounding error.
        angle = towards * math.pi / 180      # degrees to radians
        towards_north = round(100 * math.cos(angle))
        towards_east = round(-100 * math.sin(angle))

    best_move = None
    best_square = None
    best_score = 0
    # Which squares the ripple has reached: one byte for every square of the
    # course, 1 once reached. The hub has little memory, so the ripple only
    # keeps the ring of squares it is spreading from, not every square so far.
    reached = bytearray(course_squares())
    if inside_course(square):
        reached[square_number(square)] = 1
    ring = []          # (square, first move) for each square in the ring
    for direction in directions:
        if can_move(course_map, square, direction):
            ahead = next_square(square, direction)
            reached[square_number(ahead)] = 1
            ring.append((ahead, direction))

    steps = 1          # how many steps from the rover the ring is
    while len(ring) > 0:
        if near is not None and best_move is not None and steps > best_score:
            # With near, no square scores less than its number of steps, so
            # nothing further out can beat the best one now.
            break
        next_ring = []
        for here, first_move in ring:
            if here not in course_map.searched:
                if towards is None and near is None:
                    return first_move, here
                if near is not None:
                    # How far this square is from the spot, in squares (Pythagoras).
                    # Rounded to hundredths, so squares that are equally far from
                    # it score exactly the same.
                    east_gap = here[0] - near[0]
                    north_gap = here[1] - near[1]
                    away = round(100 * math.sqrt(east_gap * east_gap + north_gap * north_gap)) / 100
                    score = steps + HEAD_STRENGTH * away
                else:
                    # How far this square lies in the towards direction, in squares.
                    how_far_that_way = (here[0] * towards_east + here[1] * towards_north) / 100
                    score = steps - HEAD_STRENGTH * how_far_that_way
                if best_move is None or score < best_score:
                    best_move = first_move
                    best_square = here
                    best_score = score
            for direction in directions:
                if can_move(course_map, here, direction):
                    ahead = next_square(here, direction)
                    if not reached[square_number(ahead)]:
                        reached[square_number(ahead)] = 1
                        next_ring.append((ahead, first_move))
        ring = next_ring
        steps = steps + 1
    return best_move, best_square


async def look(course_map, square, direction):
    """Measure the distance in direction (the rover must already face that
    way) and write what it means on the map.

    Every square the rover could drive into before the wall stop kicks in is
    marked open. A wall is only marked when it is in the very next square:
    further away the sensor's beam is wide enough to catch things off to the
    side, so that decision waits until the rover is close.

    Returns (how many squares ahead are free, the distance in cm or -1).
    """
    distance = await measure_distance()
    if distance == -1:
        free = NO_ECHO_SQUARES
    else:
        free = max(0, int((distance - WALL_STOP_CM) // STEP_CM))

    here = square
    for i in range(free):
        if not inside_course(next_square(here, direction)):
            break
        course_map.open.add((here, direction))
        course_map.blocked.discard((here, direction))
        here = next_square(here, direction)

    if free == 0 and distance != -1:
        course_map.blocked.add((square, direction))
        course_map.open.discard((square, direction))
        # Is the wall so close that the rover could never stand in the next
        # square, even sideways? The middle of that square is STEP_CM ahead
        # of the turning point, and the distance sensor is already
        # DISTANCE_SENSOR_POSITION_CM ahead.
        ahead = next_square(square, direction)
        wall_from_middle = distance - (STEP_CM - DISTANCE_SENSOR_POSITION_CM)
        if wall_from_middle < ROVER_WIDTH_CM / 2 and ahead not in course_map.visited:
            course_map.solid.add(ahead)

    print("look: " + DIRECTION_NAMES[direction] + " from " + str(square) + ", "
          + str(distance) + " cm, " + str(free) + " squares free")
    return free, distance


def print_map(course_map, square):
    """Print the map with NORTH at the top.
    R = rover, o = visited, . = seen to be open, # = solid, blank = unknown."""
    seen_open = set()
    for (from_square, direction) in course_map.open:
        seen_open.add(next_square(from_square, direction))
    squares = course_map.visited | course_map.solid | seen_open
    easts = [s[0] for s in squares]
    norths = [s[1] for s in squares]
    for north in range(max(norths), min(norths) - 1, -1):
        row = ""
        for east in range(min(easts), max(easts) + 1):
            here = (east, north)
            if here == square:
                row += "R"
            elif here in course_map.visited:
                row += "o"
            elif here in course_map.solid:
                row += "#"
            elif here in seen_open:
                row += "."
            else:
                row += " "
        print("map |" + row + "|")


def nearest_direction(heading):
    """NORTH, WEST, SOUTH or EAST - whichever is closest to heading."""
    best = NORTH
    for direction in [WEST, SOUTH, EAST]:
        if abs(heading_difference(direction, heading)) < abs(heading_difference(best, heading)):
            best = direction
    return best


async def back_to_a_square():
    """Drive to the middle of the nearest square, and return that square.

    Between one explore() and the next, your program may have driven the
    rover somewhere - and explore(find=...) stops part way through a move,
    the moment it finds its colour. The rover's position (see Movement)
    says how far it has gone since it last stood in the middle of
    rover_square, so this works out which square it is nearest now.
    """
    moved_east = position_east_cm - square_position[0]
    moved_north = position_north_cm - square_position[1]
    east_cm = rover_square[0] * STEP_CM + moved_east      # where it is now, in cm on the grid
    north_cm = rover_square[1] * STEP_CM + moved_north
    square = (round(east_cm / STEP_CM), round(north_cm / STEP_CM))
    to_east = square[0] * STEP_CM - east_cm               # from there to the middle of square
    to_north = square[1] * STEP_CM - north_cm
    distance = math.sqrt(to_east * to_east + to_north * to_north)
    if distance > 2:
        # Split the way to the middle into "along the way the rover faces"
        # and "sideways". Usually it is all along: the rover stopped part way
        # through a step, or your program drove straight on or back.
        angle = target_heading * math.pi / 180      # degrees to radians
        along = -math.sin(angle) * to_east + math.cos(angle) * to_north
        sideways = math.cos(angle) * to_east + math.sin(angle) * to_north
        if abs(sideways) > 3:
            # Too far to the side: turn to face the middle, then drive straight there.
            heading = round(math.atan2(-to_east, to_north) * 180 / math.pi)
            if await turn_to(heading):
                along = distance
        print("explore: driving " + str(round(along, 1)) + " cm to the middle of square "
              + str(square))
        if along > 0:
            await drive_forward(along, stop_at_wall_cm=WALL_STOP_CM)
        else:
            await drive_backward(-along)
    course_map.visited.add(square)
    course_map.searched.add(square)
    return square


async def explore(find=None, near=None, towards=None):
    """Search the course, square by square. Start the run facing NORTH.

    find     a colour, like color.GREEN: stop the moment the colour sensor is
             on it, and give True. Gives False if it searched everywhere it
             can reach, twice, without finding it. Without find, it searches
             everywhere, and on_colour_found() reacts to colours on the way.
    near     (cm right of the start, cm ahead of it): search around there first
    towards  a heading in degrees: search that way first
    With neither near nor towards, it uses the HEAD_TOWARDS setting.
    """
    global rover_square, square_position, looking_for, react_to_colours
    if find is not None and find not in COLOUR_NAMES:
        print("explore: find should be a colour, like find=color.GREEN")
        end_run()
    if near is not None and (not isinstance(near, (tuple, list)) or len(near) != 2):
        print("explore: near should be two numbers in brackets, like near=(-30, 110)")
        end_run()
    if towards is not None and not isinstance(towards, (int, float)):
        print("explore: towards should be a heading in degrees, like towards=30 or towards=NORTH")
        end_run()
    print("=== EXPLORER START ===")

    if near is None and towards is None:
        towards = HEAD_TOWARDS
    if near is not None:
        near = (near[0] / STEP_CM, near[1] / STEP_CM)      # from cm to squares
    if find is not None:
        print("explore: looking for " + colour_name(find))
        react_to_colours = False      # from now on, a colour only counts when it is looked for
        if find in colour_spots:
            # It drove over this colour earlier, before its turn. Head for
            # that spot, and forget that the squares round it were searched,
            # so that the rover drives over it again.
            spot = colour_spots[find]
            near = (spot[0] / STEP_CM, spot[1] / STEP_CM)
            middle = (round(near[0]), round(near[1]))
            course_map.searched.discard(middle)
            for direction in [NORTH, WEST, SOUTH, EAST]:
                course_map.searched.discard(next_square(middle, direction))
            print("explore: saw " + colour_name(find) + " earlier, near square "
                  + str(middle) + " - going back there")

    looking_for = find
    searched_again = False
    heading_for = None
    try:
        square = await back_to_a_square()
        while True:
            # The rover is in the middle of square now. Remember that, in case
            # finding the colour stops it part way through the next move.
            rover_square = square
            square_position = (position_east_cm, position_north_cm)

            # 1. Plan, starting from the way the rover faces now.
            facing = nearest_direction(target_heading)
            direction, target = next_move(course_map, square, facing, towards, near)
            if direction is None:
                if find is None:
                    print("explore: searched every square it can reach - finished")
                    print_map(course_map, square)
                    return False
                if searched_again:
                    print("explore: " + colour_name(find) + " not found anywhere it can reach")
                    return False
                print("explore: " + colour_name(find) + " not found - searching everywhere once more")
                course_map.searched = {square}
                searched_again = True
                continue
            if target != heading_for:
                print("explore: heading for square " + str(target))
                heading_for = target

            # 2. Look first - unless this move is already known to be open, or
            # leads to a square the rover has stood in before (so there is room).
            ahead = next_square(square, direction)
            been_there = ahead in course_map.visited
            if (square, direction) not in course_map.open and not been_there:
                if not await turn_to(direction):
                    # No room to swing round to face that way from here.
                    course_map.blocked.add((square, direction))
                    continue
                free, distance = await look(course_map, square, direction)
                if free == 0:
                    # A wall right ahead: check next to it for a patch. This
                    # happens once per wall, as look() has now marked the move
                    # blocked, so the rover will not look this way again.
                    await check_by_wall(direction)
                    continue       # the map has changed, so plan again

            # 3. Move one square. If it could not - something in the way, or no
            # room to turn - that move is marked blocked and it plans again.
            if await step(direction, been_there) == "done":
                course_map.open.add((square, direction))
                square = ahead
                course_map.visited.add(square)
                course_map.searched.add(square)
            else:
                course_map.blocked.add((square, direction))
                course_map.open.discard((square, direction))
    except ColourReached:
        print("explore: on " + colour_name(find) + " at " + str(rover_position())
              + " - back to your program")
        return True
    finally:
        looking_for = None


# ======================================================================
# YOUR PROGRAM
# ======================================================================

async def my_program():
    # 1. Find GREEN - in the middle, about 28 cm left of the start and 112 cm
    #    ahead - and stand on it for 5 seconds.
    if not await explore(find=color.GREEN, near=(0, 110)):
        return     # no GREEN anywhere it can reach: RED would not count, so stop here
    await runloop.sleep_ms(5000)

    # 2. Find RED - top-left corner, about 125 cm left and 183 cm ahead - and
    #    stop on it. The run ends there.
    await explore(find=color.BLUE, near=(-65, 220))


# Choose what runs: exactly ONE of these lines must have no # in front.
# Run setup_check first on a new rover.
runloop.run(run_program(my_program))
# runloop.run(run_program(setup_check))
# runloop.run(run_program(follow_wall))
# runloop.run(run_program(explore))
