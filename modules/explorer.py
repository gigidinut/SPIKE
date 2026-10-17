#@title Maze explorer
#@about
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
#@settings
HEAD_TOWARDS = None        # which way to search first when explore() gets no near= or towards=.
                           # A heading in degrees: 0 = NORTH, 90 = WEST, 180 = SOUTH, -90 = EAST
                           # (the names NORTH, WEST... work too). 30 = mostly north, a bit west.
                           # None = no preference. Avoid exact diagonals like NORTH_WEST: north and
                           # west then tie, and the rover just keeps going the way it faces.
HEAD_STRENGTH = 1          # how strongly to follow a hint: how many extra steps the rover will drive
                           # to reach a square one step further that way, or one step nearer the spot
NO_ECHO_SQUARES = 2        # when a look gets no echo, count this many squares ahead as open
#@code
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
    if find is not None and not colour_module_installed:
        print("explore: find needs the Colour sensor module, which is not installed")
        return False

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
