#@title Setup
#@about
# Everything about how YOUR rover is built: which port each part is plugged
# into, which way the motors face, the wheel size and where the sensors sit.
# Every other module reads these settings, so get them right first.
#
#   setup_check()      run this first on a new rover - it tests each part, one
#                      at a time, and tells you which setting to change if one
#                      is wrong. The LEFT and RIGHT hub buttons move between tests.
#   run_program(...)   starts a program (see YOUR PROGRAM at the bottom)
#   end_run()          finish the whole run straight away, from anywhere
#@constants
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
#@settings
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
#@only grid
# Building tip: a colour sensor IN FRONT is better. To check the floor next to
# a wall, a rover with it in front just drives up and back. With it behind, the
# rover must turn round and reverse blind at every wall - slower and riskier.
#@end
COLOUR_SENSOR_POSITION_CM = -10

# Which side of the hub faces up. motion_sensor.TOP means the hub lies flat
# with its light matrix facing up. The others are motion_sensor.BOTTOM,
# FRONT, BACK, LEFT and RIGHT. The gyro needs this to measure turns.
HUB_FACE_UP = motion_sensor.TOP

MAX_RUN_SECONDS = 0            # end the run after this many seconds; 0 = no limit
#@code
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
