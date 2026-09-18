import motor
import distance_sensor
import runloop
from hub import port, motion_sensor, button

# ============================================================
#CONFIGURATION
# ============================================================
TARGET_HEADING    = 45
MOVE_SPEED        = 400
TURN_SPEED        = 200
TURN_ANGLE        = 90
WALL_THRESHOLD_CM = 15
MOVE_DURATION_MS= 1000
SCAN_PAUSE_MS     = 1000
HEADING_TOLERANCE = 20
DEADBAND_CYCLES   = 2

SENSOR_MAX_CM      = 200   # what a -1 reading is worth when ranking
ESCAPE_DURATION_MS = 1500  # longer than a normal step, to clear the obstacle
CLEARANCE_WEIGHT   = 0.6   # how much open space matters when choosing a direction
HEADING_WEIGHT     = 0.4   # how much pointing at TARGET_HEADING matters
SETTLE_MS          = 3000  # pause after the go button, before zeroing the gyro
SENSOR_POLL_MS     = 50    # how often to check the sensor while driving
APPROACH_STOP_CM   = 20    # bail out of a move at this range; > WALL_THRESHOLD_CM
                           # so there is room to brake before the wall
DRIVE_LOG_MS       = 3000  # how often to log progress while driving
                           # (logging no longer interrupts the drive)

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

_target_heading = 0

# ============================================================
#START GATE
# ============================================================

async def wait_for_start():
    """Hold until the LEFT hub button is tapped, then let the rover settle.

    Must run BEFORE set_heading(), because set_heading() calls reset_yaw(0).
    Zeroing the gyro while the rover is still in your hand makes that hand
    orientation the datum for every heading decision afterwards.
    """
    print("Place the rover on the floor, then press the LEFT hub button.")

    # If the button is already held, wait for it to come up first.
    while button.pressed(button.LEFT):
        await runloop.sleep_ms(50)
    # Wait for the press.
    while not button.pressed(button.LEFT):
        await runloop.sleep_ms(50)
    # Wait for the release, so we don't start while you're still touching it.
    while button.pressed(button.LEFT):
        await runloop.sleep_ms(50)

    print("Starting in " + str(SETTLE_MS) + "ms - hands off")
    await runloop.sleep_ms(SETTLE_MS)


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

async def move_forward(duration_ms, speed, stop_cm=APPROACH_STOP_CM):
    """Drive forward, polling the distance sensor the whole way.

    Returns True if the full duration completed, False if an obstacle came
    within stop_cm and the move was cut short. The old version slept through
    the entire duration, so the rover was blind while moving and would run
    into anything that appeared mid-step.
    """
    print("move_forward: speed=" + str(speed) + " duration=" + str(duration_ms) + "ms")
    motor.run(port.A, abs(speed))
    motor.run(port.B, -abs(speed))

    elapsed = 0
    completed = True
    while elapsed < duration_ms:
        await runloop.sleep_ms(SENSOR_POLL_MS)
        elapsed += SENSOR_POLL_MS
        cm = read_distance()
        if cm != -1 and cm < stop_cm:
            completed = False
            break

    motor.stop(port.A)
    motor.stop(port.B)
    if completed:
        print("move_forward: done")
    else:
        print("move_forward: STOPPED EARLY at " + str(cm) + " cm after " + str(elapsed) + "ms")
    return completed

async def drive_until_event(speed, stop_cm, tolerance):
    """Drive forward continuously until something needs a decision.

    Unlike move_forward, this has no fixed duration - the rover keeps rolling
    while the path is clear and the heading holds, so there is no stop-start
    cadence. Motors are left stopped on return.

    Returns (reason, distance_cm).
    """
    motor.run(port.A, abs(speed))
    motor.run(port.B, -abs(speed))

    reason = DRIVE_CONTINUE
    cm = -1
    elapsed = 0
    while True:
        await runloop.sleep_ms(SENSOR_POLL_MS)
        elapsed += SENSOR_POLL_MS

        cm = read_distance()
        if cm != -1 and cm < stop_cm:
            reason = DRIVE_OBSTACLE
            break

        diff = heading_difference(get_heading(), get_current_yaw())
        if abs(diff) > tolerance:
            reason = DRIVE_OFF_HEADING
            break

        if elapsed >= DRIVE_LOG_MS:
            # Heartbeat only - keep rolling. Stopping the motors just to print
            # a line was making the rover pause every few seconds on a clear
            # path, which looked like a detection but was pure bookkeeping.
            print("  still driving: yaw=" + str(get_current_yaw())
                  + " dist=" + str(cm))
            elapsed = 0

    motor.stop(port.A)
    motor.stop(port.B)
    return reason, cm


async def move_backward(duration_ms, speed):
    print("move_backward: speed=" + str(speed) + " duration=" + str(duration_ms) + "ms")
    motor.run(port.A, -abs(speed))
    motor.run(port.B, abs(speed))
    await runloop.sleep_ms(duration_ms)
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
#MAIN LOOP
# ============================================================

async def main():
    print("=== SPIKE NAV READY ===")
    await wait_for_start()
    print("=== SPIKE NAV START ===")
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

            await move_backward(MOVE_DURATION_MS, MOVE_SPEED)


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
                print("STATE_AVOID: every direction blocked, backing up to rescan")
                await move_backward(MOVE_DURATION_MS, MOVE_SPEED)
                continue

            print("STATE_AVOID: chose " + names[best] + ", "
                  + str(clear[best]) + " cm, score=" + str(best_score))

            # Re-centred, so the offset IS the turn. Positive = more yaw = left.
            turn_needed = offsets[best]
            if turn_needed > 0:
                await turn_left(turn_needed, TURN_SPEED)
            elif turn_needed < 0:
                await turn_right(-turn_needed, TURN_SPEED)
            await runloop.sleep_ms(SCAN_PAUSE_MS)

            if not await move_forward(ESCAPE_DURATION_MS, MOVE_SPEED):
                print("STATE_AVOID: escape route blocked too, rescanning")
                continue

            deadband_counter = DEADBAND_CYCLES
            state = STATE_DRIVE
            print("STATE_AVOID -> STATE_DRIVE")

runloop.run(main())
