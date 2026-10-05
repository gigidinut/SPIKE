#@title Maze explorer
#@about
# Autonomy option 2. The rover draws a map of the course as it goes, and
# keeps heading for the nearest square it has not visited yet, until it has
# been everywhere it can reach. It finds patches out in the open that the
# wall follower misses, but it is slower and harder to follow.
#
# The map remembers:
#   - which squares the rover has visited
#   - which moves between squares are open, and which are blocked by a wall
#   - which squares are "solid": so close to a wall the rover can never stand there
#
# Each time round its main loop, the explorer:
#   1. Plans: picks the unvisited square to head for with a ripple search
#      (next_move) - the nearest one, or with HEAD_TOWARDS set, one that is
#      near and also lies in that direction.
#   2. Looks: if it does not know yet whether that first move is open, and
#      has never been in that square, it faces that way and measures. One
#      look maps a whole line of squares.
#   3. Moves one square, or marks the move as blocked if it could not.
#
# If the back of the rover would hit something as it turns to face a new
# way, it turns back and marks that way as blocked from that square. To go
# back to a square right behind it, it reverses instead of turning round.
#
# If you know roughly where to search first, set HEAD_TOWARDS. The rover
# still drives only NORTH, SOUTH, EAST and WEST, one square at a time, and
# still searches everywhere in the end - it just searches that way first.
#
#   await explore()
#@settings
HEAD_TOWARDS = None        # where to search first: NORTH, NORTH_EAST, EAST, SOUTH_EAST, SOUTH,
                           # SOUTH_WEST, WEST, NORTH_WEST, or None for no preference
HEAD_STRENGTH = 1          # how strongly to prefer HEAD_TOWARDS: how many extra steps the rover
                           # will drive to reach a square one step further in that direction
NO_ECHO_SQUARES = 2        # when a look gets no echo, count this many squares ahead as open
#@code
# For each compass direction: how far one square that way goes (east, north).
# The diagonals go 0.7 east or west and 0.7 north or south - together that is
# one square's length, by Pythagoras.
DIRECTION_STEPS = {
    NORTH: (0, 1), NORTH_EAST: (0.7, 0.7), EAST: (1, 0), SOUTH_EAST: (0.7, -0.7),
    SOUTH: (0, -1), SOUTH_WEST: (-0.7, -0.7), WEST: (-1, 0), NORTH_WEST: (-0.7, 0.7),
}
def check_explorer_settings():
    if HEAD_TOWARDS is not None and HEAD_TOWARDS not in DIRECTION_STEPS:
        setting_problem("HEAD_TOWARDS should be NORTH, NORTH_EAST, EAST, SOUTH_EAST, SOUTH, "
                        + "SOUTH_WEST, WEST, NORTH_WEST or None (without quote marks)")
    check_number("HEAD_STRENGTH", HEAD_STRENGTH, 0, 10)
    check_number("NO_ECHO_SQUARES", NO_ECHO_SQUARES, 0, 10)


SETTINGS_CHECKS.append(check_explorer_settings)


class CourseMap:
    """Everything the rover has learnt about the course so far."""
    def __init__(self):
        self.visited = {(0, 0)}       # squares the rover has stood on
        self.solid = set()            # squares the rover can never stand on
        self.open = set()             # (square, direction) moves known to be open
        self.blocked = set()          # (square, direction) moves known to be blocked


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


def next_move(course_map, square, facing):
    """Choose the unvisited square to head for, and the first move towards it.

    This is a "ripple" search (computer scientists call it a breadth-first
    search). Imagine dropping a stone into water on the rover's square. The
    ripple spreads out one square at a time, to every square the rover could
    move to, so it reaches each square by the shortest route. Each square in
    the ripple remembers how many steps away it is, and which way the ripple
    left the rover's square: the first move of that route.

    With HEAD_TOWARDS = None, the first unvisited square the ripple reaches
    wins: it is the nearest one. Otherwise every unvisited square gets a
    score - its number of steps, minus HEAD_STRENGTH for every square it lies
    in the HEAD_TOWARDS direction - and the lowest score wins.

    Returns (first move, target square), or (None, None) when every square it
    can reach has been visited.
    """
    # Try the way the rover already faces first, so it prefers going straight on.
    directions = [facing]
    for direction in [NORTH, WEST, SOUTH, EAST]:
        if direction != facing:
            directions.append(direction)
    if HEAD_TOWARDS is not None:
        towards_east, towards_north = DIRECTION_STEPS[HEAD_TOWARDS]

    best_move = None
    best_square = None
    best_score = 0
    reached = {square}
    ripple = []        # (square, first move, steps) - nearest first
    for direction in directions:
        if can_move(course_map, square, direction):
            ahead = next_square(square, direction)
            reached.add(ahead)
            ripple.append((ahead, direction, 1))

    i = 0
    while i < len(ripple):
        here, first_move, steps = ripple[i]
        i += 1
        if here not in course_map.visited:
            if HEAD_TOWARDS is None:
                return first_move, here
            # How far this square lies in the HEAD_TOWARDS direction, in squares.
            how_far_that_way = here[0] * towards_east + here[1] * towards_north
            score = steps - HEAD_STRENGTH * how_far_that_way
            if best_move is None or score < best_score:
                best_move = first_move
                best_square = here
                best_score = score
        for direction in directions:
            ahead = next_square(here, direction)
            if ahead not in reached and can_move(course_map, here, direction):
                reached.add(ahead)
                ripple.append((ahead, first_move, steps + 1))
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
        # of the wheels, and the distance sensor is already
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


async def explore():
    """Search the whole course, square by square. Start it facing NORTH."""
    print("=== EXPLORER START ===")
    course_map = CourseMap()
    square = (0, 0)
    heading_for = None
    while True:
        # 1. Plan. target_heading is the way the rover faces now.
        direction, target = next_move(course_map, square, target_heading)
        if direction is None:
            print("explore: visited every square it can reach - finished")
            print_map(course_map, square)
            return
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
        else:
            course_map.blocked.add((square, direction))
            course_map.open.discard((square, direction))
