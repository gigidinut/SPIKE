#@title Wall follower
#@about
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
#@settings
KEEP_WALL_ON_RIGHT = True   # True: keep the right hand on the wall. False: the left hand.
#@code
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
