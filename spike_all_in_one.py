import motor
import distance_sensor
import color_sensor
import color
import runloop
import math
from hub import port, motion_sensor
try:
    import time       # only for RUN_TIME_LIMIT_S
except ImportError:
    time = None

# ============================================================
#CONFIGURATION
# ============================================================
TARGET_HEADING    = 45
MOVE_SPEED        = 400
TURN_SPEED        = 200
TURN_ANGLE        = 90
WALL_THRESHOLD_CM = 15
MOVE_BACKWARD_DURATION_MS= 500
SCAN_PAUSE_MS     = 500
HEADING_TOLERANCE = 20
DEADBAND_CYCLES   = 2

SENSOR_MAX_CM      = 200   # what a -1 reading is worth when ranking
ESCAPE_DURATION_MS = 1500  # longer than a normal step, to clear the obstacle
REVERSE_CLEARANCE_CM = 35  # room needed behind before it is safe to reverse
CLEARANCE_WEIGHT   = 0.6   # how much open space matters when choosing a direction
HEADING_WEIGHT     = 0.4   # how much pointing at TARGET_HEADING matters
SENSOR_POLL_MS     = 50    # how often to check the sensor while driving
APPROACH_STOP_CM   = 10    # bail out of a move at this range; > WALL_THRESHOLD_CM
                           # so there is room to brake before the wall
DRIVE_LOG_MS       = 3000  # how often to log progress while driving
                           # (logging no longer interrupts the drive)

# --- Turning to a room direction ---
TURN_SLOW_SPEED = 100    # motor deg/s for the last TURN_SLOW_DEG of a turn
TURN_SLOW_DEG   = 15     # how far from the target yaw to slow down
TURN_TIMEOUT_MS = 5000   # give up on a turn that takes this long (stalled wheel)

# --- Staircase legs ---
LEG_ROTATIONS    = 1   # leg length in wheel rotations (~18 cm with 56 mm wheels).
                       # Keep it shorter than the red patch (A4 short side is
                       # 21 cm) or the staircase can step right over it.
LEG_STUCK_FACTOR = 3   # a leg taking this many times its expected time is stuck

# --- Staircase navigation ---
# The rover starts square to the room facing "up"; that becomes yaw 0 and
# fixes the four room directions for the whole run: up 0, left 90, down 180,
# right -90. It only ever faces one of these.
GOAL_YAWS       = [0, 90]     # up, left: the directions that lead to the star
DETOUR_YAWS     = [-90, 180]  # right, down: only to get round an obstacle
MAX_TRUSTED_CM  = 180   # no straight path here is over 2 m, so a reading above
                        # this is a missed echo, NOT open space
ROOM_WINDOW_DEG = 15    # radar slices within this of a room direction count for it
MAX_DETOUR_LEGS = 6     # detour legs before sweeping again
MAX_DETOURS     = 3     # failed detours in a row before giving up

# --- Maze exploration (explore) ---
# The floor is mapped as a grid of cells one leg wide, starting at cell (0, 0)
# with +x to the right and +y up. Cells it has not seen count as passable, so
# the shortest route to the nearest unvisited cell always leads somewhere new;
# blocked cells are never forgotten, so it cannot get stuck in a pocket.
RED_NEEDS_GREEN     = True  # True: red only ends the run once green is done; red
                            # seen earlier is remembered and revisited. False: red
                            # always ends the run.
RUN_TIME_LIMIT_S    = 0     # stop exploring after this many seconds; 0 = no limit
WHEEL_DIAMETER_CM   = 5.6   # standard SPIKE wheel; sets the cell size (one leg)
EXPLORE_LEFT_CM     = 220   # map limits, cm from the start. DOWN is 0 because the
EXPLORE_RIGHT_CM    = 220   # start sits on the course edge - without a limit the
EXPLORE_UP_CM       = 220   # rover would wander out through the entrance
EXPLORE_DOWN_CM     = 0
LOOK_MISS_CELLS     = 2     # a missed echo straight ahead still clears this many cells
ROVER_RADIUS_CM     = 8     # half the rover's width: a cell whose centre is closer
                            # than this to a wall can never be stood on
LOOK_SETTLE_MS      = 150   # pause after turning before reading the distance
TOUCH_WALLS         = True  # nose up to each wall met and back, so the colour sensor
                            # covers the strip no cell centre reaches (patches often
                            # sit against walls)

# --- Radar sweep ---
SWEEP_SPEED    = 150   # motor deg/s for the radar spin; slower = finer map
SWEEP_POLL_MS  = 40    # time between samples during the spin
SLICE_DEG      = 10    # angular width of one radar slice (36 slices per spin)

# --- Colour checkpoints ---
# The sensor must be plugged into COLOR_PORT. A and B are the motors, C is the
# distance sensor, so D is the first one free.
COLOR_PORT          = port.D
CHECKPOINT_COLOR    = color.GREEN  # stop once here (payload drop), then carry on
GOAL_COLOR          = color.RED    # the star: the run ends here
CHECKPOINT_PAUSE_MS = 2000         # how long to sit on the checkpoint

# YAW SIGN CONVENTION - measured on this rover, do not guess:
#   turning LEFT  makes yaw INCREASE (more positive)
#   turning RIGHT makes yaw DECREASE (more negative)
# A commanded 90 deg right turn ended at yaw -98.1. Every heading calculation
# below follows this; flipping it silently inverts all steering.

STATE_DRIVE = 0
STATE_AVOID = 1

# Why a continuous drive segment ended.
DRIVE_CONTINUE    = 0   # nothing happened, keep going
DRIVE_OBSTACLE    = 1   # something came within stop_cm
DRIVE_OFF_HEADING = 2   # drifted past the heading tolerance
DRIVE_TIMEOUT     = 3   # ran for the full max_ms without incident
DRIVE_DISTANCE    = 4   # the wheels covered the full max_deg
DRIVE_NAMES = ["continue", "obstacle", "off-heading", "timeout", "distance"]
# Colour is NOT a reason code: a checkpoint pauses in place and resumes the
# manoeuvre in progress, and the goal raises GoalReached, which unwinds every
# loop at once.

_target_heading = 0

# ============================================================
#HEADING / GYRO FUNCTIONS
# ============================================================

def set_heading(heading_degrees):
    global _target_heading
    _target_heading = heading_degrees
    motion_sensor.reset_yaw(0)
    print("set_heading: target=" + str(heading_degrees) + ", yaw reset")

def get_heading():
    return _target_heading

def get_current_yaw():
    yaw = motion_sensor.tilt_angles()[0]
    return yaw / 10

# ============================================================
#MOVEMENT FUNCTIONS
# ============================================================

def wheel_degrees():
    """Degrees the drive wheels have turned since the last reset, either way.

    Averages both wheels so a slight veer does not change the count, and uses
    abs() because the motors are mounted opposed and count in opposite signs.
    """
    return (abs(motor.relative_position(port.A))
            + abs(motor.relative_position(port.B))) / 2


async def drive_until_event(speed, stop_cm, tolerance, max_ms=0, max_deg=0):
    """Drive forward until something needs a decision. Motors stopped on return.

    This is the only forward-drive loop. It replaced a separate move_forward()
    that duplicated the polling and had to be kept in sync by hand.

    tolerance: heading error that ends the segment. Pass 181 - larger than any
               value heading_difference can return - to ignore heading entirely,
               which is what the escape manoeuvre and the deadband both want.
    max_ms:    0 to run until an event; >0 to also stop after that much DRIVING
               time and return DRIVE_TIMEOUT. Colour pauses do not count toward
               it, so a bounded move still covers its full distance.
    max_deg:   0 for no distance limit; >0 to stop once wheel_degrees() reaches
               it and return DRIVE_DISTANCE.

    Returns (reason, distance_cm).
    """
    motor.reset_relative_position(port.A, 0)
    motor.reset_relative_position(port.B, 0)
    motor.run(port.A, abs(speed))
    motor.run(port.B, -abs(speed))

    reason = DRIVE_CONTINUE
    cm = -1
    elapsed = 0      # toward max_ms
    since_log = 0    # toward the heartbeat; reset independently, or the
                     # heartbeat would keep zeroing the duration cap
    while True:
        await runloop.sleep_ms(SENSOR_POLL_MS)
        elapsed += SENSOR_POLL_MS
        since_log += SENSOR_POLL_MS

        cm = read_distance()
        if cm != -1 and cm < stop_cm:
            reason = DRIVE_OBSTACLE
            break

        await handle_color(abs(speed), -abs(speed))

        diff = heading_difference(get_heading(), get_current_yaw())
        if abs(diff) > tolerance:
            reason = DRIVE_OFF_HEADING
            break

        if max_deg > 0 and wheel_degrees() >= max_deg:
            reason = DRIVE_DISTANCE
            break

        if max_ms > 0 and elapsed >= max_ms:
            reason = DRIVE_TIMEOUT
            break

        if since_log >= DRIVE_LOG_MS:
            # Heartbeat only - keep rolling. Stopping the motors just to print
            # a line was making the rover pause every few seconds on a clear
            # path, which looked like a detection but was pure bookkeeping.
            print("  still driving: yaw=" + str(get_current_yaw())
                  + " dist=" + str(cm))
            since_log = 0

    motor.stop(port.A)
    motor.stop(port.B)
    return reason, cm


async def move_backward(duration_ms, speed):
    """Reverse for a fixed time, polling so a colour stop can interrupt it."""
    print("move_backward: speed=" + str(speed) + " duration=" + str(duration_ms) + "ms")
    motor.run(port.A, -abs(speed))
    motor.run(port.B, abs(speed))

    elapsed = 0
    while elapsed < duration_ms:
        await runloop.sleep_ms(SENSOR_POLL_MS)
        elapsed += SENSOR_POLL_MS
        await handle_color(-abs(speed), abs(speed))

    motor.stop(port.A)
    motor.stop(port.B)
    print("move_backward: done")

# ============================================================
#TURNING FUNCTIONS
# ============================================================

async def turn_right(angle, speed):
    if angle <= 0:
        return
    print("turn_right: angle=" + str(angle) + " speed=" + str(speed))
    # Accumulate small per-sample deltas instead of comparing against a fixed
    # start_yaw: tilt_angles() wraps at +/-180, and a raw difference taken
    # across that boundary reads as ~315 deg and ends the turn instantly.
    prev_yaw = motion_sensor.tilt_angles()[0] / 10
    turned = 0
    motor.run(port.A, -abs(speed))
    motor.run(port.B, -abs(speed))
    while turned < angle:
        await runloop.sleep_ms(10)
        if await handle_color(-abs(speed), -abs(speed)):
            # Re-baseline: any yaw wander during the pause is not turning.
            prev_yaw = motion_sensor.tilt_angles()[0] / 10
        now_yaw = motion_sensor.tilt_angles()[0] / 10
        turned += abs(heading_difference(now_yaw, prev_yaw))
        prev_yaw = now_yaw
    motor.stop(port.A)
    motor.stop(port.B)
    print("turn_right: done, turned " + str(turned) + " deg")

async def turn_left(angle, speed):
    if angle <= 0:
        return
    print("turn_left: angle=" + str(angle) + " speed=" + str(speed))
    prev_yaw = motion_sensor.tilt_angles()[0] / 10
    turned = 0
    motor.run(port.A, abs(speed))
    motor.run(port.B, abs(speed))
    while turned < angle:
        await runloop.sleep_ms(10)
        if await handle_color(abs(speed), abs(speed)):
            # Re-baseline: any yaw wander during the pause is not turning.
            prev_yaw = motion_sensor.tilt_angles()[0] / 10
        now_yaw = motion_sensor.tilt_angles()[0] / 10
        turned += abs(heading_difference(now_yaw, prev_yaw))
        prev_yaw = now_yaw
    motor.stop(port.A)
    motor.stop(port.B)
    print("turn_left: done, turned " + str(turned) + " deg")

async def turn_to_yaw(target):
    """Turn the short way to an ABSOLUTE yaw, slowing for the last TURN_SLOW_DEG.

    Steering to an absolute yaw rather than by a relative angle means any
    overshoot gets corrected by the next turn instead of accumulating.
    Left raises yaw (see the convention note at the top), so diff > 0 = left.
    """
    start = get_current_yaw()
    diff = heading_difference(target, start)
    if abs(diff) < 1:
        return
    direction = 1 if diff > 0 else -1    # +1 = left, -1 = right
    # A small correction starts slow - no point lurching at full speed for it.
    speed = TURN_SPEED if abs(diff) > TURN_SLOW_DEG else TURN_SLOW_SPEED
    motor.run(port.A, direction * speed)
    motor.run(port.B, direction * speed)
    elapsed = 0
    while True:
        await runloop.sleep_ms(10)
        elapsed += 10
        await handle_color(direction * speed, direction * speed)
        # Degrees still to go in the direction of travel: <= 0 once reached
        # or passed. The > -90 guard matters for 180 deg turns: a twitch the
        # wrong way at the start wraps 180 to -179.9, which is NOT "passed".
        remaining = heading_difference(target, get_current_yaw()) * direction
        if -90 < remaining <= 0:
            break
        if 0 < remaining < TURN_SLOW_DEG and speed != TURN_SLOW_SPEED:
            speed = TURN_SLOW_SPEED
            motor.run(port.A, direction * speed)
            motor.run(port.B, direction * speed)
        if elapsed >= TURN_TIMEOUT_MS:
            print("turn_to_yaw: WARNING timed out - wheel stalled?")
            break
    motor.stop(port.A)
    motor.stop(port.B)
    print("turn_to_yaw: target=" + str(target) + " from=" + str(start)
          + " stopped=" + str(get_current_yaw()))

# ============================================================
#DISTANCE SENSOR
# ============================================================

def read_distance():
    """Silent distance read in cm, -1 if nothing in range.

    Used by the drive loop, which polls every SENSOR_POLL_MS - printing at
    that rate would flood the console and slow the loop enough to matter.
    """
    dist = distance_sensor.distance(port.C)
    if dist is None or dist < 0:
        return -1
    return dist / 10

def measure_distance():
    """Distance read with logging, for the once-per-decision calls."""
    cm = read_distance()
    if cm == -1:
        print("measure_distance: no reading")
    else:
        print("measure_distance: " + str(cm) + " cm")
    return cm

# ============================================================
#COLOUR SENSOR
# ============================================================

class GoalReached(Exception):
    """Raised from any movement loop when GOAL_COLOR is read. Ends the run."""


# ONE-SHOT: the checkpoint pauses once per run, so driving off the patch and
# back on (or a later patch of the same colour) does not deploy twice. The
# goal has no latch - it ends the run the first time it is seen.
_checkpoint_done = False
_color_warned = False
_red_seen = False   # red was under the sensor before green (RED_NEEDS_GREEN only)


def read_color():
    """Current colour under the sensor, or None if the sensor is missing.

    A missing sensor must not raise mid-drive: an unhandled exception in the
    drive loop would leave the motors running.
    """
    global _color_warned
    try:
        return color_sensor.color(COLOR_PORT)
    except Exception:
        if not _color_warned:
            print("WARNING: no colour sensor on COLOR_PORT - colour stops disabled")
            _color_warned = True
        return None


async def handle_color(a_velocity, b_velocity):
    """Read the floor colour and act on it. Returns True if it paused.

    Every movement loop calls this with its own motor velocities, so the
    colours behave the same whether the rover is driving, reversing or
    turning:
      GOAL_COLOR       - stop the motors and raise GoalReached, which unwinds
                         every loop straight back to run_program(). If
                         RED_NEEDS_GREEN and green is not done yet, just note
                         it in _red_seen and carry on.
      CHECKPOINT_COLOR - first time only: stop, wait, then resume with the
                         velocities passed in, so the manoeuvre carries on
                         from where it was interrupted.
    """
    global _checkpoint_done, _red_seen
    c = read_color()
    if c == GOAL_COLOR:
        if _checkpoint_done or not RED_NEEDS_GREEN:
            motor.stop(port.A)
            motor.stop(port.B)
            print("GOAL: red found")
            raise GoalReached()
        if not _red_seen:
            print("RED: seen before green - remembering it, carrying on")
        _red_seen = True
    if c == CHECKPOINT_COLOR and not _checkpoint_done:
        _checkpoint_done = True
        motor.stop(port.A)
        motor.stop(port.B)
        print("CHECKPOINT: green found, pausing " + str(CHECKPOINT_PAUSE_MS) + "ms")
        # Payload deployment goes here once it exists.
        await runloop.sleep_ms(CHECKPOINT_PAUSE_MS)
        print("CHECKPOINT: resuming")
        motor.run(port.A, a_velocity)
        motor.run(port.B, b_velocity)
        return True
    return False


# ============================================================
#NAVIGATION HELPERS
# ============================================================

def heading_difference(target, current):
    diff = target - current
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff

async def align_to_heading(target, tolerance=10):
    current = get_current_yaw()
    diff = heading_difference(target, current)
    print("align_to_heading: target=" + str(target) + " current=" + str(current) + " diff=" + str(diff))
    if abs(diff) <= tolerance:
        print("align_to_heading: within tolerance, skip")
        return
    turn_amount = abs(diff)
    # diff > 0 means the target yaw is HIGHER than current, and yaw rises when
    # turning left. Having these swapped made every correction increase the
    # error instead of reducing it.
    if diff > 0:
        await turn_left(turn_amount, TURN_SPEED)
    else:
        await turn_right(turn_amount, TURN_SPEED)

# ============================================================
#STAIRCASE LEGS
# ============================================================

async def drive_leg(yaw):
    """Square up to a room direction, then drive one leg of LEG_ROTATIONS along it.

    Returns (reason, distance_cm): DRIVE_DISTANCE when the full leg was
    covered, DRIVE_OBSTACLE if something came within APPROACH_STOP_CM, or
    DRIVE_TIMEOUT if the wheels did not get round in time (stuck).
    """
    await turn_to_yaw(yaw)
    leg_deg = LEG_ROTATIONS * 360
    expected_ms = leg_deg * 1000 // MOVE_SPEED
    # tolerance 181 = ignore heading: turn_to_yaw has just squared it up, and
    # a leg is too short to drift far.
    reason, cm = await drive_until_event(MOVE_SPEED, APPROACH_STOP_CM, 181,
                                         expected_ms * LEG_STUCK_FACTOR, leg_deg)
    print("drive_leg: yaw=" + str(yaw) + " " + DRIVE_NAMES[reason]
          + " wheel_deg=" + str(wheel_degrees()) + " dist=" + str(cm))
    return reason, cm

# ============================================================
#RADAR
# ============================================================

async def radar_sweep():
    """Spin 360 deg left once, sampling distance against measured yaw.

    Returns (start_yaw, slices). slices[i] is the closest distance seen
    between i*SLICE_DEG and (i+1)*SLICE_DEG LEFT of start_yaw, so its centre
    is at yaw start_yaw + i*SLICE_DEG + SLICE_DEG/2. None means no sample
    landed in that slice - the spin was too fast for the sensor.

    Each sample is tagged with the yaw the gyro actually measured, so turn
    overshoot cannot mislabel a reading the way it does in the 5-point scan.
    """
    slices = [None] * (360 // SLICE_DEG)
    start_yaw = prev = get_current_yaw()
    turned = 0
    samples = 0
    print("radar_sweep: start_yaw=" + str(start_yaw))
    speed = SWEEP_SPEED
    motor.run(port.A, speed)
    motor.run(port.B, speed)
    while turned < 360:
        await runloop.sleep_ms(SWEEP_POLL_MS)
        # Same end-of-turn slow-down as turn_to_yaw: momentum after stopping
        # at full sweep speed carried it well past 360.
        if 360 - turned < TURN_SLOW_DEG and speed != TURN_SLOW_SPEED:
            speed = TURN_SLOW_SPEED
            motor.run(port.A, speed)
            motor.run(port.B, speed)
        if await handle_color(speed, speed):
            # Re-baseline: any yaw wander during the pause is not turning.
            prev = get_current_yaw()
        now = get_current_yaw()
        turned += abs(heading_difference(now, prev))
        prev = now

        # -1 means nothing in range. Mapping it to SENSOR_MAX_CM BEFORE taking
        # the min means any real echo in the slice beats a missed one.
        cm = read_distance()
        if cm == -1:
            cm = SENSOR_MAX_CM
        i = int(turned // SLICE_DEG) % len(slices)
        if slices[i] is None or cm < slices[i]:
            slices[i] = cm
        samples += 1
    motor.stop(port.A)
    motor.stop(port.B)
    print("radar_sweep: done, " + str(samples) + " samples over "
          + str(turned) + " deg")
    return start_yaw, slices


def room_clearance(start_yaw, slices, yaw):
    """Clearance in cm along an absolute room direction, from a radar map.

    Takes the closest reading among the slices whose centre is within
    ROOM_WINDOW_DEG of yaw - the flat dip a square-on wall makes. Returns
    None if every one of them was over MAX_TRUSTED_CM: in this room that is a
    missed echo, not open space.
    """
    best = None
    for i in range(len(slices)):
        centre = start_yaw + i * SLICE_DEG + SLICE_DEG / 2
        if abs(heading_difference(centre, yaw)) > ROOM_WINDOW_DEG:
            continue
        cm = slices[i]
        if cm is None or cm > MAX_TRUSTED_CM:
            continue
        if best is None or cm < best:
            best = cm
    return best

# ============================================================
#AVOID MANOEUVRE
# ============================================================

async def reverse_if_clear():
    """Look behind, come back to the same heading, and reverse only if there is room.

    The rover has no rear sensor, so the only way to find out is to turn
    around and look. Reversing blind was an assumption that a wall behind
    would quietly falsify.
    """
    heading_before = get_current_yaw()
    print("reverse_if_clear: turning to check clearance behind")
    await turn_left(180, TURN_SPEED)
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    behind = measure_distance()

    # Return by absolute heading rather than a second blind 180: turns
    # overshoot 6-8 deg each, and align_to_heading goes the short way
    # to a measured target instead of compounding that error.
    print("reverse_if_clear: turning back to " + str(heading_before))
    await align_to_heading(heading_before)
    await runloop.sleep_ms(SCAN_PAUSE_MS)

    # -1 means nothing in range, which is the CLEAREST case.
    if behind == -1 or behind >= REVERSE_CLEARANCE_CM:
        print("reverse_if_clear: " + str(behind) + " cm behind, reversing")
        await move_backward(MOVE_BACKWARD_DURATION_MS, MOVE_SPEED)
    else:
        print("reverse_if_clear: only " + str(behind)
              + " cm behind, skipping reverse")


async def choose_escape_direction():
    """Scan five directions, re-centre, and pick the best way out.

    Returns the turn to make from the re-centred heading, in YAW space
    (positive = left, see the convention note at the top): one of
    90, 45, 0, -45, -90. Returns None if every direction is blocked.
    """
    # Measure 5 distances to choose direction
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    dist_forward = measure_distance()

    await turn_left(45, TURN_SPEED)
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    dist_left_45 = measure_distance()

    await turn_left(45, TURN_SPEED)
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    dist_left_90 = measure_distance()

    await turn_right(135, TURN_SPEED)
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    dist_right_45 = measure_distance()

    await turn_right(45, TURN_SPEED)
    await runloop.sleep_ms(SCAN_PAUSE_MS)
    dist_right_90 = measure_distance()

    # Re-center rover
    await turn_left(90, TURN_SPEED)

    # --- Score each direction: clearance gates, heading tips ---
    # -1 means "nothing in range" = the CLEAREST case, so it must map
    # to a large number, not rank last.
    readings = [dist_left_90, dist_left_45, dist_forward,
                dist_right_45, dist_right_90]
    # Offsets are in YAW space, so left is POSITIVE (see convention
    # note at the top). These are added straight to scan_yaw below.
    offsets  = [90, 45, 0, -45, -90]
    names    = ["left90", "left45", "forward", "right45", "right90"]
    clear    = [SENSOR_MAX_CM if d == -1 else d for d in readings]

    # Normalise against the best reading actually available, so the
    # clearance term keeps its full 0..1 range even in tight spaces.
    max_clear = clear[0]
    for c in clear:
        if c > max_clear:
            max_clear = c
    if max_clear <= 0:
        max_clear = 1

    scan_yaw = get_current_yaw()   # re-centred: offsets are relative to this
    best = -1
    best_score = -1.0
    for i in range(len(clear)):
        if clear[i] < WALL_THRESHOLD_CM:
            continue               # blocked - not a candidate at all
        heading_here = scan_yaw + offsets[i]
        goal_error = abs(heading_difference(get_heading(), heading_here))
        open_score = clear[i] / max_clear
        aim_score = 1.0 - (goal_error / 180.0)
        score = CLEARANCE_WEIGHT * open_score + HEADING_WEIGHT * aim_score
        print("  " + names[i] + " (yaw" + str(offsets[i]) + "): clear="
              + str(clear[i]) + " err=" + str(goal_error)
              + " score=" + str(score))
        if score > best_score:
            best_score = score
            best = i

    if best == -1:
        return None

    print("choose_escape_direction: chose " + names[best] + ", "
          + str(clear[best]) + " cm, score=" + str(best_score))
    return offsets[best]

# ============================================================
#STAIRCASE NAVIGATION
# ============================================================

async def detour():
    """Both goal directions are blocked: sweep, take the clearer DETOUR_YAWS
    direction, and step along it, trying the goal direction beside it after
    every leg.

    Returns the goal yaw that got the rover moving again, or None if this
    detour found no way round.
    """
    start_yaw, slices = await radar_sweep()
    away = None
    best = -1
    for yaw in DETOUR_YAWS:
        cm = room_clearance(start_yaw, slices, yaw)
        print("detour: yaw=" + str(yaw) + " clear=" + str(cm))
        # A missed echo is not open space here, but it is not a wall either:
        # rank it as barely clear, so any measured clearance beats it.
        rank = WALL_THRESHOLD_CM if cm is None else cm
        if rank >= WALL_THRESHOLD_CM and rank > best:
            best = rank
            away = yaw
    if away is None:
        print("detour: no clear way")
        return None

    # The goal direction at right angles to `away` is the one that opens up
    # as the rover steps along the obstacle (away right -> try up; away
    # down -> try left).
    beside = GOAL_YAWS[0]
    if abs(heading_difference(GOAL_YAWS[0], away)) != 90:
        beside = GOAL_YAWS[1]
    for _ in range(MAX_DETOUR_LEGS):
        away_reason, _ = await drive_leg(away)
        reason, _ = await drive_leg(beside)
        if reason == DRIVE_DISTANCE:
            return beside
        if away_reason != DRIVE_DISTANCE:
            break      # the detour is blocked too - sweep again from here
    return None

# ============================================================
#MAIN LOOP
# ============================================================

async def main():
    """Staircase to the star: alternate legs along GOAL_YAWS until red ends it.

    A blocked leg is retried along the other goal direction straight away,
    then the blocked one is tried again - so the rover steps along an obstacle
    until the way opens up. Only when BOTH goal directions are blocked does it
    sweep and detour.
    """
    print("=== SPIKE NAV START ===")
    motion_sensor.reset_yaw(0)   # rover must start square to the room, facing up
    nxt = 0       # index into GOAL_YAWS of the next leg to try
    failed = 0    # detours in a row that found no way round

    while True:
        reason, _ = await drive_leg(GOAL_YAWS[nxt])
        if reason == DRIVE_DISTANCE:
            nxt = 1 - nxt
            continue

        # Blocked: take the other goal direction now. nxt stays put, so the
        # blocked direction is tried again straight after.
        reason, _ = await drive_leg(GOAL_YAWS[1 - nxt])
        if reason == DRIVE_DISTANCE:
            continue

        print("main: both goal directions blocked")
        got = await detour()
        if got is None:
            failed += 1
            if failed >= MAX_DETOURS:
                print("main: no way round after " + str(failed) + " detours - stopping")
                return
            continue
        failed = 0
        nxt = 1 - GOAL_YAWS.index(got)

# ============================================================
#MAZE EXPLORATION
# ============================================================

CELL_CM = LEG_ROTATIONS * math.pi * WHEEL_DIAMETER_CM   # one leg = one cell
# Room direction -> one-cell step in grid coordinates (+x right, +y up).
# Left raises yaw, so yaw 90 is -x.
STEP = {0: (0, 1), 90: (-1, 0), 180: (0, -1), -90: (1, 0)}


class Maze:
    """What the rover has learnt about the course, in cells.

    Blocking is stored per EDGE - (cell, yaw) meaning "cannot drive out of
    this cell in that direction" - because it depends on the side you come
    from: a cell that is too close to a wall to drive into from the left can
    still be fine to enter from below. A cell is only marked solid when a
    wall is so close to its centre that the rover's body could never stand
    there.
    """
    def __init__(self):
        self.visited = {(0, 0)}
        self.solid = set()
        self.open = set()       # (cell, yaw) known to be drivable
        self.closed = set()     # (cell, yaw) known to be blocked
        self.touched = set()    # (cell, yaw) walls already nosed up to


def neighbour(c, yaw):
    return (c[0] + STEP[yaw][0], c[1] + STEP[yaw][1])


def in_bounds(c):
    return (-EXPLORE_LEFT_CM <= c[0] * CELL_CM <= EXPLORE_RIGHT_CM
            and -EXPLORE_DOWN_CM <= c[1] * CELL_CM <= EXPLORE_UP_CM)


def can_move(maze, c, yaw):
    n = neighbour(c, yaw)
    return in_bounds(n) and n not in maze.solid and (c, yaw) not in maze.closed


def plan_step(maze, pos, heading, target):
    """First move (a room yaw) of the shortest route from pos to a goal cell.

    The goal is target if given, otherwise the nearest cell not visited yet.
    Edges and cells it has not seen count as passable - that is what sends
    the rover to look at them. The current heading is tried first, so ties go
    to driving straight on. Returns None if no goal cell can be reached.
    """
    order = [heading] + [y for y in STEP if y != heading]
    seen = {pos}
    queue = []
    for yaw in order:
        if can_move(maze, pos, yaw):
            n = neighbour(pos, yaw)
            seen.add(n)
            queue.append((n, yaw))
    i = 0
    while i < len(queue):
        c, first = queue[i]
        i += 1
        is_goal = (c == target) if target is not None else (c not in maze.visited)
        if is_goal:
            return first
        for yaw in order:
            n = neighbour(c, yaw)
            if n not in seen and can_move(maze, c, yaw):
                seen.add(n)
                queue.append((n, first))
    return None


async def steady_distance():
    """Median of 3 readings once the rover has settled; -1 only if all miss."""
    await runloop.sleep_ms(LOOK_SETTLE_MS)
    vals = []
    for _ in range(3):
        cm = read_distance()
        if cm != -1:
            vals.append(cm)
        await runloop.sleep_ms(30)
    if not vals:
        return -1
    vals.sort()
    return vals[len(vals) // 2]


async def look(maze, pos, yaw):
    """Face a room direction and record what the distance sensor sees.

    Every cell the rover could drive into without the obstacle stop firing
    gets a known-open edge. Blocking is only recorded when the wall is in the
    very next cell: further out the beam is wide enough to pick up things
    beside the line, so that call waits until the rover is close.
    Returns (free cells straight ahead, reading in cm or -1).
    """
    await turn_to_yaw(yaw)
    d = await steady_distance()
    if d == -1 or d > MAX_TRUSTED_CM:
        n_free = LOOK_MISS_CELLS
    else:
        n_free = max(0, int((d - APPROACH_STOP_CM) // CELL_CM))
    c = pos
    for _ in range(n_free):
        if not in_bounds(neighbour(c, yaw)):
            break
        maze.open.add((c, yaw))
        maze.closed.discard((c, yaw))
        c = neighbour(c, yaw)
    if n_free == 0 and 0 <= d <= MAX_TRUSTED_CM:
        maze.closed.add((pos, yaw))
        maze.open.discard((pos, yaw))
        n = neighbour(pos, yaw)
        if d < CELL_CM + ROVER_RADIUS_CM and n not in maze.visited:
            maze.solid.add(n)
    print("look: at " + str(pos) + " yaw=" + str(yaw) + " dist=" + str(d)
          + " free=" + str(n_free))
    return n_free, d


async def back_up(deg):
    """Reverse until the wheels have turned deg degrees - undoes a partial leg."""
    if deg <= 0:
        return
    motor.reset_relative_position(port.A, 0)
    motor.reset_relative_position(port.B, 0)
    motor.run(port.A, -MOVE_SPEED)
    motor.run(port.B, MOVE_SPEED)
    limit = deg * 1000 // MOVE_SPEED * LEG_STUCK_FACTOR + 500
    elapsed = 0
    while wheel_degrees() < deg and elapsed < limit:
        await runloop.sleep_ms(SENSOR_POLL_MS)
        elapsed += SENSOR_POLL_MS
        await handle_color(-MOVE_SPEED, MOVE_SPEED)
    motor.stop(port.A)
    motor.stop(port.B)


async def touch_wall(maze, pos, yaw, gap_cm):
    """Nose up to the wall ahead and back, once per cell and direction.

    The rover only stops at cell centres, which leaves a strip in front of
    each wall the colour sensor never crosses - and the patches often sit
    right against a wall.
    """
    if not TOUCH_WALLS or (pos, yaw) in maze.touched or gap_cm < 3:
        return
    maze.touched.add((pos, yaw))
    leg_deg = LEG_ROTATIONS * 360
    await drive_until_event(MOVE_SPEED, APPROACH_STOP_CM, 181,
                            leg_deg * 1000 // MOVE_SPEED * LEG_STUCK_FACTOR, leg_deg)
    await back_up(wheel_degrees())


def print_map(maze, pos):
    """Map rows top to bottom: R rover, o visited, . seen open, # solid, blank unknown."""
    seen_open = set(neighbour(c, y) for c, y in maze.open)
    cells = maze.visited | maze.solid | seen_open
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    for y in range(max(ys), min(ys) - 1, -1):
        row = ""
        for x in range(min(xs), max(xs) + 1):
            c = (x, y)
            if c == pos:
                row += "R"
            elif c in maze.visited:
                row += "o"
            elif c in maze.solid:
                row += "#"
            elif c in seen_open:
                row += "."
            else:
                row += " "
        print("map |" + row + "|")


def take_red(cell, yaw, how):
    """Consume the red flag after a move: (start cell, yaw, kind of move) if
    red went under the sensor during it, else None. Clearing it after every
    move keeps a later sighting from being pinned on the wrong move."""
    global _red_seen
    if not _red_seen:
        return None
    _red_seen = False
    print("explore: red seen during a " + how + " from " + str(cell))
    return (cell, yaw, how)


async def explore():
    """Maze search: keep driving to the nearest cell not visited yet until
    green and then red are found.

    The rover must start square to the course, facing up, on its bottom edge
    (see EXPLORE_DOWN_CM). Before driving along an edge it has not seen,
    it looks, which also maps a line of cells. A leg that stops early is
    backed out and that edge marked blocked.

    Red seen before green (RED_NEEDS_GREEN) is remembered as the move that
    crossed it. Once green is done the rover drives back and repeats that
    move - going back to the cell alone is not enough when red was only
    reached by nosing up to a wall.
    """
    print("=== EXPLORE START === cell=" + str(int(CELL_CM * 10) / 10) + "cm")
    motion_sensor.reset_yaw(0)
    start_ms = time.ticks_ms() if time else 0
    if RUN_TIME_LIMIT_S and not time:
        print("WARNING: no time module - RUN_TIME_LIMIT_S is ignored")
    maze = Maze()
    pos = (0, 0)
    heading = 0
    red_spot = None      # (cell, yaw, how) of the move that crossed red

    while True:
        if (RUN_TIME_LIMIT_S and time
                and time.ticks_diff(time.ticks_ms(), start_ms) > RUN_TIME_LIMIT_S * 1000):
            print("explore: time limit reached - stopping")
            print_map(maze, pos)
            return

        target = None
        forced = None
        if _checkpoint_done and red_spot is not None:
            cell, ryaw, how = red_spot
            if pos != cell:
                target = cell                # head back to where red was crossed
            else:
                print("explore: back where red was seen - repeating the " + how)
                red_spot = None              # if this fails too, search the rest
                if how == "spin":
                    await radar_sweep()      # colour is read all the way round
                    continue
                if how == "touch":
                    maze.touched.discard((pos, ryaw))
                    n_free, d = await look(maze, pos, ryaw)
                    heading = ryaw
                    if n_free == 0:
                        await touch_wall(maze, pos, ryaw, d - APPROACH_STOP_CM)
                        continue
                forced = ryaw                # "leg": drive the same leg again

        yaw = forced if forced is not None else plan_step(maze, pos, heading, target)
        if yaw is None:
            print("explore: every reachable cell visited - "
                  + ("red" if _checkpoint_done else "green") + " not found")
            print_map(maze, pos)
            return

        if (pos, yaw) not in maze.open:
            n_free, d = await look(maze, pos, yaw)
            heading = yaw
            spot = take_red(pos, yaw, "spin")
            red_spot = red_spot or spot
            if n_free == 0:
                await touch_wall(maze, pos, yaw, d - APPROACH_STOP_CM)
                spot = take_red(pos, yaw, "touch")
                red_spot = red_spot or spot
                continue                 # the map changed - plan again

        start = pos
        reason, _ = await drive_leg(yaw)
        heading = yaw
        nxt = neighbour(pos, yaw)
        if reason == DRIVE_DISTANCE:
            maze.open.add((pos, yaw))
            pos = nxt
            maze.visited.add(pos)
            spot = take_red(start, yaw, "leg")
        else:
            await back_up(wheel_degrees())
            maze.closed.add((pos, yaw))
            maze.open.discard((pos, yaw))
            print("explore: cannot drive " + str(pos) + " -> " + str(nxt)
                  + " (" + DRIVE_NAMES[reason] + "), backed out")
            spot = take_red(start, yaw, "touch")
        red_spot = red_spot or spot

# ============================================================
#BENCH TESTS
# ============================================================

async def test_radar():
    """Bench test for radar_sweep(): spin, print the map, wait, repeat.

    Prints 4 lines of 90 deg each, in sweep order, as whole cm per slice.
    The label is the slice-centre angle range relative to where the rover
    faced when the sweep started, in yaw space: + is left, - is right,
    +/-180 is behind. 200 means no echo anywhere in that slice; -- means
    no sample landed in it.

    Kept this short because the SPIKE App console only copies part of a long
    printout and drops the line breaks - the [range] label on each line keeps
    it readable even when the lines run together.
    """
    def centre(i):
        angle = i * SLICE_DEG + SLICE_DEG // 2
        if angle > 180:
            angle -= 360
        return angle

    print("=== RADAR TEST ===")
    motion_sensor.reset_yaw(0)   # so the [room] line's "up" is where it faced at start
    per_line = 90 // SLICE_DEG
    while True:
        start_yaw, slices = await radar_sweep()
        for first in range(0, len(slices), per_line):
            values = []
            for cm in slices[first:first + per_line]:
                values.append("--" if cm is None else str(int(cm + 0.5)))
            print("[" + str(centre(first)) + ".." + str(centre(first + per_line - 1))
                  + "] " + " ".join(values))
        # What the navigation sees: clearance along each room direction,
        # ? = only missed echoes there.
        room = []
        for name, yaw in [("up", 0), ("left", 90), ("down", 180), ("right", -90)]:
            cm = room_clearance(start_yaw, slices, yaw)
            room.append(name + "=" + ("?" if cm is None else str(int(cm + 0.5))))
        print("[room] " + " ".join(room))
        await runloop.sleep_ms(1000)   # let it settle before measuring the overshoot
        print("radar: ended " + str(heading_difference(get_current_yaw(), start_yaw))
              + " deg past a full turn; next sweep in 4s")
        await runloop.sleep_ms(4000)

async def test_turns():
    """Bench test for turn_to_yaw(): left, right and 180 deg turns, forever.

    One line per turn once it has settled. err is where it ended relative to
    the target: + means it stopped LEFT of the target, - means RIGHT. So on a
    left turn + is overshoot; on a right turn - is overshoot.
    """
    print("=== TURN TEST ===")
    motion_sensor.reset_yaw(0)
    while True:
        # 0->90 left, 90->0 right, 0->-90 right, -90->0 left, then two 180s
        for target in [90, 0, -90, 0, 180, 0]:
            await turn_to_yaw(target)
            await runloop.sleep_ms(1000)   # let it settle before measuring
            yaw = get_current_yaw()
            print("[turn " + str(target) + "] settled=" + str(yaw)
                  + " err=" + str(heading_difference(yaw, target)))
        print("turn test: next round in 3s")
        await runloop.sleep_ms(3000)

async def test_legs():
    """Bench test for drive_leg(): drive a square - up, left, down, right.

    It should end roughly where it started. One drive_leg line per leg says
    why the leg ended (distance = full leg, obstacle, timeout = stuck) and how
    far the wheels actually turned.
    """
    print("=== LEG TEST ===")
    motion_sensor.reset_yaw(0)
    while True:
        for yaw in [0, 90, 180, -90]:
            await drive_leg(yaw)
            await runloop.sleep_ms(500)
        await turn_to_yaw(0)
        print("leg test: square done, next in 5s")
        await runloop.sleep_ms(5000)

# ============================================================
#ENTRY POINT
# ============================================================

async def run_program(program):
    """Run program until GOAL_COLOR ends it.

    GoalReached is raised from inside whatever loop saw red, with the motors
    already stopped, so catching it here is all it takes to end the run.
    """
    try:
        await program()
    except GoalReached:
        print("=== RUN COMPLETE: goal reached ===")

# Run exactly ONE of these. explore is the maze search, main the old staircase;
# the rest are bench tests.
runloop.run(run_program(explore))
# runloop.run(run_program(main))
# runloop.run(run_program(test_radar))
# runloop.run(run_program(test_turns))
# runloop.run(run_program(test_legs))
