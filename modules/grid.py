#@title Grid moves
#@about
# Used by both autonomy modules. They think of the floor as a grid of
# squares, STEP_CM wide. The rover starts in the middle of square (0, 0),
# facing NORTH. The first number counts squares to the EAST (right of the
# start), the second counts squares to the NORTH (ahead of the start).
#
#   next_square(square, direction)   the square next door in that direction
#   inside_course(square)            False for squares outside the COURSE_ limits
#   await step(direction)            try to move one square: "done", "blocked" or "no room"
#   await check_by_wall(direction)   sweep the colour sensor up to the wall ahead
#@settings
COURSE_NORTH_CM = 222   # how far the course reaches from the start in each direction.
COURSE_SOUTH_CM = 0     # The rover never moves outside it. SOUTH is 0 when the start
COURSE_EAST_CM = 24     # is on the edge of the course, so the rover cannot wander
COURSE_WEST_CM = 135    # out through the entrance. These fit the real course
                        # (1.6 m x 2.3 m inside), starting in its bottom-right gap.
CHECK_BY_WALLS = True   # also check the floor next to each wall the rover meets, which its
                        # path through the middle of the squares never reaches. Slower.
#@tuning
STEP_CM = 12            # size of one grid square, and the length of one step, in cm.
                        # Smaller squares fit through narrower gaps but take longer.
WALL_STOP_CM = 10       # a step stops early if the distance sensor sees a wall this close
WALL_CHECK_GAP_CM = 5   # how close that check brings the front or back of the rover to the wall
#@code
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
