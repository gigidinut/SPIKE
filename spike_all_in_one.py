import motor
import distance_sensor
import color_sensor
import color
import runloop
from hub import port, motion_sensor

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

# --- Radar sweep ---
SWEEP_SPEED    = 150   # motor deg/s for the radar spin; slower = finer map
SWEEP_POLL_MS  = 40    # time between samples during the spin
SLICE_DEG      = 10    # angular width of one radar slice (36 slices per spin)

# --- Colour stop ---
# The sensor must be plugged into COLOR_PORT. A and B are the motors, C is the
# distance sensor, so D is the first one free.
COLOR_PORT     = port.D
TARGET_COLOR   = color.RED   # drive stops when the floor reads this colour
COLOR_PAUSE_MS = 2000        # how long to sit still before carrying on

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
# Colour is NOT a reason code: every movement loop pauses in place and resumes
# itself, so a colour stop never interrupts the manoeuvre in progress.

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

async def drive_until_event(speed, stop_cm, tolerance, max_ms=0):
    """Drive forward until something needs a decision. Motors stopped on return.

    This is the only forward-drive loop. It replaced a separate move_forward()
    that duplicated the polling and had to be kept in sync by hand.

    tolerance: heading error that ends the segment. Pass 181 - larger than any
               value heading_difference can return - to ignore heading entirely,
               which is what the escape manoeuvre and the deadband both want.
    max_ms:    0 to run until an event; >0 to also stop after that much DRIVING
               time and return DRIVE_TIMEOUT. Colour pauses do not count toward
               it, so a bounded move still covers its full distance.

    Returns (reason, distance_cm).
    """
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

        if color_triggered():
            await color_pause(abs(speed), -abs(speed))

        diff = heading_difference(get_heading(), get_current_yaw())
        if abs(diff) > tolerance:
            reason = DRIVE_OFF_HEADING
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
        if color_triggered():
            await color_pause(-abs(speed), abs(speed))

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
        if color_triggered():
            await color_pause(-abs(speed), -abs(speed))
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
        if color_triggered():
            await color_pause(abs(speed), abs(speed))
            # Re-baseline: any yaw wander during the pause is not turning.
            prev_yaw = motion_sensor.tilt_angles()[0] / 10
        now_yaw = motion_sensor.tilt_angles()[0] / 10
        turned += abs(heading_difference(now_yaw, prev_yaw))
        prev_yaw = now_yaw
    motor.stop(port.A)
    motor.stop(port.B)
    print("turn_left: done, turned " + str(turned) + " deg")

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

# ONE-SHOT latch: TARGET_COLOR fires once per run and never again until
# reset_color_latch() is called explicitly. Nothing re-arms it automatically -
# not driving off the patch, not an avoid manoeuvre, not a later patch of the
# same colour.
_color_found = False
_color_warned = False


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


def color_triggered():
    """True on the FIRST sighting of TARGET_COLOR this run, then never again.

    Once latched it short-circuits before touching the sensor, so the rover
    drives past every later patch of that colour without pausing.
    """
    global _color_found
    if _color_found:
        return False
    c = read_color()
    if c is None:
        return False
    if c == TARGET_COLOR:
        _color_found = True
        return True
    return False


def reset_color_latch():
    """Re-arm the colour stop. The only way the latch ever clears."""
    global _color_found
    _color_found = False
    print("colour latch re-armed")


async def color_pause(a_velocity, b_velocity):
    """Stop, wait COLOR_PAUSE_MS, then resume with the given velocities.

    Every movement loop calls this, so the colour stop behaves identically
    whether the rover is driving, reversing or turning. The caller passes its
    own motor velocities back in, which is what lets the manoeuvre carry on
    from where it was interrupted instead of being abandoned.
    """
    motor.stop(port.A)
    motor.stop(port.B)
    print("COLOUR STOP: target colour found, pausing " + str(COLOR_PAUSE_MS) + "ms")
    await runloop.sleep_ms(COLOR_PAUSE_MS)
    print("COLOUR STOP: resuming")
    motor.run(port.A, a_velocity)
    motor.run(port.B, b_velocity)


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
    motor.run(port.A, SWEEP_SPEED)
    motor.run(port.B, SWEEP_SPEED)
    while turned < 360:
        await runloop.sleep_ms(SWEEP_POLL_MS)
        if color_triggered():
            await color_pause(SWEEP_SPEED, SWEEP_SPEED)
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
#MAIN LOOP
# ============================================================

async def main():
    print("=== SPIKE NAV START ===")
    reset_color_latch()
    set_heading(TARGET_HEADING)

    # reset_yaw(0) means the rover starts at yaw 0 while the target is
    # TARGET_HEADING, so it begins life off-target by exactly that much.
    # Point it the right way before the first drive segment.
    print("aligning to target heading before first move")
    await align_to_heading(get_heading())
    await runloop.sleep_ms(SCAN_PAUSE_MS)

    state = STATE_DRIVE
    deadband_counter = 0

    while True:
        if state == STATE_DRIVE:
            # The deadband suppresses heading correction for a segment or two
            # after an avoid, so the rover commits to its escape instead of
            # immediately steering back toward the obstacle it just dodged.
            if deadband_counter > 0:
                deadband_counter -= 1
                tolerance = 181     # larger than any possible error: ignore heading
                print("STATE_DRIVE: driving (deadband, " + str(deadband_counter) + " left)")
            else:
                tolerance = HEADING_TOLERANCE
                print("STATE_DRIVE: driving (yaw=" + str(get_current_yaw())
                      + " target=" + str(get_heading()) + ")")

            reason, cm = await drive_until_event(MOVE_SPEED, APPROACH_STOP_CM, tolerance)

            # drive_until_event now only returns on a real event, so every
            # stop below has a cause printed against it.
            if reason == DRIVE_OBSTACLE:
                print("STATE_DRIVE -> STATE_AVOID (obstacle at " + str(cm) + " cm)")
                state = STATE_AVOID
            elif reason == DRIVE_OFF_HEADING:
                print("STATE_DRIVE: off heading, correcting")
                await align_to_heading(get_heading())

        elif state == STATE_AVOID:
            print("STATE_AVOID")

            await runloop.sleep_ms(1000)

            await reverse_if_clear()

            turn_needed = await choose_escape_direction()
            if turn_needed is None:
                print("STATE_AVOID: every direction blocked, backing up to rescan")
                await move_backward(MOVE_BACKWARD_DURATION_MS, MOVE_SPEED)
                continue

            # Re-centred, so the offset IS the turn. Positive = more yaw = left.
            if turn_needed > 0:
                await turn_left(turn_needed, TURN_SPEED)
            elif turn_needed < 0:
                await turn_right(-turn_needed, TURN_SPEED)
            await runloop.sleep_ms(SCAN_PAUSE_MS)

            # tolerance 181 = ignore heading: the whole point of the escape is
            # to go somewhere other than the target heading for a moment.
            reason, cm = await drive_until_event(MOVE_SPEED, APPROACH_STOP_CM,
                                                 181, ESCAPE_DURATION_MS)
            if reason == DRIVE_OBSTACLE:
                print("STATE_AVOID: escape route blocked too (" + str(cm)
                      + " cm), rescanning")
                continue

            deadband_counter = DEADBAND_CYCLES
            state = STATE_DRIVE
            print("STATE_AVOID -> STATE_DRIVE")

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
    per_line = 90 // SLICE_DEG
    while True:
        _, slices = await radar_sweep()   # radar_sweep logs start_yaw itself
        for first in range(0, len(slices), per_line):
            values = []
            for cm in slices[first:first + per_line]:
                values.append("--" if cm is None else str(int(cm + 0.5)))
            print("[" + str(centre(first)) + ".." + str(centre(first + per_line - 1))
                  + "] " + " ".join(values))
        print("radar: next sweep in 5s")
        await runloop.sleep_ms(5000)

# Bench test - swap these two lines back to run the full navigation.
# runloop.run(main())
runloop.run(test_radar())
