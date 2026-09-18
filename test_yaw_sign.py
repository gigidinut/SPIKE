"""Determine which way yaw moves when the rover turns.

Run this on the hub as its own program. It turns right 90 degrees, then left
90 degrees, printing yaw at every stage.

WHAT TO LOOK FOR
----------------
After the RIGHT turn, does yaw go UP (0 -> +90) or DOWN (0 -> -90)?

  yaw goes UP   -> right is positive. align_to_heading in spike_all_in_one.py
                   is correct as written, and the bug is elsewhere.
  yaw goes DOWN -> right is negative. align_to_heading has its turns
                   backwards, and the scan offsets need flipping too.
"""
import motor
import runloop
from hub import port, motion_sensor

TURN_SPEED = 200


def yaw():
    return motion_sensor.tilt_angles()[0] / 10


def heading_difference(target, current):
    diff = target - current
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff


async def turn(angle, a_sign, b_sign, label):
    print(label + ": starting at yaw=" + str(yaw()))
    prev = yaw()
    turned = 0
    motor.run(port.A, a_sign * TURN_SPEED)
    motor.run(port.B, b_sign * TURN_SPEED)
    while turned < angle:
        await runloop.sleep_ms(10)
        now = yaw()
        turned += abs(heading_difference(now, prev))
        prev = now
    motor.stop(port.A)
    motor.stop(port.B)
    await runloop.sleep_ms(1000)      # let it settle before reading
    print(label + ": ended at yaw=" + str(yaw()))


async def main():
    motion_sensor.reset_yaw(0)
    await runloop.sleep_ms(1000)
    print("=== YAW SIGN TEST ===")
    print("start yaw=" + str(yaw()) + " (should be ~0)")

    # Same motor signs as turn_right() in spike_all_in_one.py
    await turn(90, -1, -1, "RIGHT turn (A-, B-)")

    await runloop.sleep_ms(2000)

    # Same motor signs as turn_left() in spike_all_in_one.py
    await turn(90, 1, 1, "LEFT turn (A+, B+)")

    print("=== DONE ===")
    print("If RIGHT ended near +90, right is POSITIVE yaw.")
    print("If RIGHT ended near -90, right is NEGATIVE yaw.")


runloop.run(main())
