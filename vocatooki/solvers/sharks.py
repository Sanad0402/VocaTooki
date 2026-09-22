"""SHARKS: steer the raft to the right words with a held drag.

Moved out of Activities/activitiesDemo.py unchanged (2026-09-22); every name is
still reachable as activitiesDemo.<name>.
"""

import math
import time

from alttester import By


# --------------------------------------------------------------- SHARKS -----
_SHARKS_ASM = "Assembly-CSharp"


_SHARKS_RAFT = "Raft(Clone)"


# How fast the raft is sailed. PlayerMovement lerps it 5% of the way to the
# touch point every FixedUpdate, so it always converges on the aim -- what sets
# the speed is how far ahead the aim is put and how often it is moved. A driver
# call costs about 30ms, so the loop below is kept to four of them per tick
# (~7 ticks a second) and the aim is held this far ahead, which comes out near
# the activity's own `moveSpeed` of 3.5 units/s.
#
# Aiming at the target itself instead -- the first version of this -- makes the
# raft bolt across the whole map at once and arrive at a shark long before the
# next tick can steer away, which is how a run ended on one heart out of three.
_SHARKS_LEAD = 2.2


def _sharks_board(altdriver, known=None):
    """Every raft on the water, with the answer key the game keeps on it.

    `Raft` publishes `Word`, `CorrectWord` (is this one of the blanks?),
    `Index` (which blank), `Connected` (already hooked to the player) and
    `drowning` (bitten -- it is under water and will surface somewhere else).

    `known` caches the word and the answer per raft: neither ever changes for a
    raft once it is spawned, and re-reading them between catches is a driver
    call each. That reading is time spent standing still in shark water, so it
    is worth not paying twice -- rafts are destroyed between sentences, and the
    new ones come with new ids, so the cache cannot go stale.
    """
    known = {} if known is None else known
    board = []
    try:
        objects = altdriver.find_objects(By.NAME, _SHARKS_RAFT)
    except Exception:
        return board
    for obj in objects:
        try:
            if obj.id not in known:
                known[obj.id] = (
                    obj.get_component_property("Raft", "Word", _SHARKS_ASM),
                    bool(obj.get_component_property("Raft", "CorrectWord", _SHARKS_ASM)))
            word, correct = known[obj.id]
            board.append({
                "id": obj.id,
                "word": word,
                "correct": correct,
                "connected": bool(obj.get_component_property("Raft", "Connected", _SHARKS_ASM)),
                "drowning": bool(obj.get_component_property("Raft", "drowning", _SHARKS_ASM)),
                "pos": (obj.worldX, obj.worldY),
            })
        except Exception:
            continue
    return board


def _sharks_progress(altdriver):
    """(sentences done, sentences in the level) off the activity's own counter."""
    text = (altdriver.find_object(By.NAME, "ProgressText").get_text() or "").strip()
    done, total = text.split("/")
    return int(done), int(total)


def _sharks_pixels_per_unit(altdriver, height):
    """How many screen pixels one world unit is worth right now.

    The camera is orthographic and PanAndZoom scales it per difficulty, so this
    is read live rather than assumed -- it is what turns a raft's world
    position into the screen point the drag has to aim at.
    """
    camera = altdriver.find_object(By.NAME, "Main Camera")
    size = float(camera.get_component_property(
        "UnityEngine.Camera", "orthographicSize", "UnityEngine.CoreModule"))
    return height / (2.0 * max(size, 0.001))


def _sharks_islands(altdriver):
    """The islands as ellipses in world units: (x, y, radius x, radius y).

    They are solid and they never move once the map is built, so this is read
    once and steered around from then on. `PolygonCollider2D.bounds` is the
    shape the physics actually uses; the ellipse inscribed in it stands in for
    a lumpy coastline well enough to sail past.
    """
    islands = []
    try:
        objects = altdriver.find_objects_which_contain(By.NAME, "Island_")
    except Exception:
        return islands
    for obj in objects:
        try:
            bounds = obj.get_component_property(
                "UnityEngine.PolygonCollider2D", "bounds", "UnityEngine.Physics2DModule")
            centre, extents = bounds["center"], bounds["extents"]
            # 1.15: the coastline fills more of its bounding box than the
            # inscribed ellipse does, and a raft that clips a shore stops dead.
            islands.append((float(centre["x"]), float(centre["y"]),
                            float(extents["x"]) * 1.15, float(extents["y"]) * 1.15))
        except Exception:
            continue
    return islands


def _sharks_offshore(x, y, islands, clearance):
    """The nearest point to (x, y) that is not on an island."""
    for cx, cy, rx, ry in islands:
        rx, ry = max(rx, 0.1) + clearance, max(ry, 0.1) + clearance
        ax, ay = (x - cx) / rx, (y - cy) / ry
        ashore = math.hypot(ax, ay)
        if ashore >= 1.0:
            continue
        if ashore < 1e-6:
            return (cx + rx, cy)
        return (cx + ax / ashore * rx, cy + ay / ashore * ry)
    return (x, y)


def _sharks_hearts(altdriver):
    """Hearts still on the raft, or None if they cannot be read.

    `currentHeart` is the index of the next one to lose, so a full raft reads
    one less than the number of hearts drawn -- what matters here is that it
    counts down, and that 0 means the next bite ends the attempt.
    """
    try:
        player = altdriver.find_object(By.NAME, "Player")
        return int(player.get_component_property(
            "PlayerMovement", "currentHeart", _SHARKS_ASM)) + 1
    except Exception:
        return None


def _sharks_take_retry(altdriver):
    """Clear the 'try again' popup if it is up. True if one was taken.

    Three bites and the attempt is over: a popup comes up and the game sets
    `Time.timeScale` to 0. Everything then stops -- rafts, sharks and the
    player alike -- which from the steering loop looks exactly like a game
    that has frozen, so it is worth saying plainly: a raft that will not move
    AND a still shark means look for this popup, not for a bug.
    """
    try:
        retry = altdriver.find_object(By.NAME, "RetryButton")
    except Exception:
        return False                    # find only returns active objects: no popup
    print("[INFO] SHARKS: out of hearts — taking the retry")
    retry.tap()
    time.sleep(2.0)
    return True


def _sharks_route(px, py, gx, gy, islands, clearance=1.2):
    """Bend the heading around the first island in the way; a waypoint out.

    Each island is scaled into a unit circle so an ellipse can be handled with
    plain circle maths. If the straight line to the goal cuts that circle, the
    waypoint becomes the point of the circle that line passes closest to,
    pushed out onto the clearance ring -- which is what steering round a
    headland looks like. It is re-run every tick, so the raft hugs the coast
    and heads straight on again the moment the way is clear.
    """
    # Give a wide berth when crossing open water, a narrow one on the run-in.
    # A fixed 1.2 made a raft 2.6 units away unreachable: the player was inside
    # the inflated ring of the island it was passing, which read as "aground",
    # and the steering spent 25s heading out to sea instead of at the word.
    reach = math.hypot(gx - px, gy - py)
    clearance = min(clearance, max(0.3, reach * 0.25))
    AGROUND = 0.25                      # only the real shoreline is aground

    blocking = None
    for cx, cy, rx, ry in islands:
        rx, ry = max(rx, 0.1) + clearance, max(ry, 0.1) + clearance
        ax, ay = (px - cx) / rx, (py - cy) / ry
        bx, by = (gx - cx) / rx, (gy - cy) / ry
        if math.hypot(bx, by) < 1.0:
            continue                    # the raft we want is inside the ring: go straight in
        dx, dy = bx - ax, by - ay
        span = dx * dx + dy * dy
        if span < 1e-6:
            continue
        along = max(0.0, min(1.0, -(ax * dx + ay * dy) / span))
        nx, ny = ax + dx * along, ay + dy * along
        gap = math.hypot(nx, ny)
        if gap >= 1.0:
            continue                    # this island is not in the way
        if math.hypot((px - cx) / (rx - clearance + AGROUND),
                      (py - cy) / (ry - clearance + AGROUND)) < 1.0:
            return _sharks_offshore(px, py, islands, AGROUND)      # on the rocks: straight out
        if blocking is None or along < blocking[0]:
            blocking = (along, cx, cy, rx, ry, nx, ny, gap)

    if blocking is None:
        return (gx, gy)

    _, cx, cy, rx, ry, nx, ny, gap = blocking
    if gap < 1e-3:                      # dead through the middle: pick a side
        nx, ny = -(gy - py), (gx - px)
        gap = math.hypot(nx, ny) or 1.0
    return (cx + nx / gap * rx, cy + ny / gap * ry)


def _sharks_dodge(bodies, vx, vy, hazards, safe=2.6, horizon=2.0):
    """A steering vector away from everything about to be too close.

    Where a hazard IS matters less than where it is GOING: the blue shark hunts
    the player and the red one crosses the map ten times faster than the grey
    ones, so for each hazard the moment of closest approach is solved from the
    relative velocity, and the push is weighted by how near that miss is and
    how soon it lands.

    `bodies` is every part of the convoy that can set a wrong raft off, not
    just the player: a hooked raft is parented to the player at the offset it
    was caught at and rides there, so it sweeps its own path through the water
    and answers for whatever IT touches. Steering only the player's own hull
    round the hazards is how hearts were still being lost.

    Returns the push, the closest anything is now, the closest thing AHEAD (a
    shark being left behind is no reason to slow down) and the closest anything
    is predicted to come -- a miss of nearly nothing means turn round, not
    swerve.
    """
    push_x = push_y = 0.0
    nearest = ahead = closest_miss = float("inf")
    pace = math.hypot(vx, vy)
    for ox, oy in bodies:
        for hx, hy, hvx, hvy in hazards:
            rx, ry = hx - ox, hy - oy
            gap = math.hypot(rx, ry)
            nearest = min(nearest, gap)
            if pace < 1e-3 or (rx * vx + ry * vy) > 0:
                ahead = min(ahead, gap)     # only what is IN FRONT should slow us
            rvx, rvy = hvx - vx, hvy - vy
            closing = rvx * rvx + rvy * rvy
            when = 0.0
            if closing > 1e-6:
                when = max(0.0, min(horizon, -(rx * rvx + ry * rvy) / closing))
            miss = math.hypot(rx + rvx * when, ry + rvy * when)
            if miss >= safe:
                continue
            if when < 0.7:
                # Only an IMMINENT contact is worth abandoning the word for.
                # At sailing speed 1.5s of prediction is five units of water,
                # and treating that as a near miss put a third of the ticks of
                # a failed sail into evasive steering with nothing within three
                # units of the raft.
                closest_miss = min(closest_miss, miss)
            urgency = (safe - miss) / safe / (1.0 + when)
            push_x -= rx / (gap or 1.0) * urgency * 2.5
            push_y -= ry / (gap or 1.0) * urgency * 2.5
    return push_x, push_y, nearest, ahead, closest_miss


def _sharks_hazards(rafts, enemies, wrong_ids, tracks, now):
    """Sharks and wrong-word rafts as (x, y, vx, vy), velocity measured here.

    The sharks do carry an `AIPath.velocity`, but only some of them -- the red
    one moves its transform directly and the black trap does not move at all --
    so the speed is taken the one way that works for all of them: the change in
    position since the last tick, which costs no extra driver call. A hazard
    that jumps (a shark that has bitten is moved somewhere else) is reported as
    standing still rather than as something crossing the map at fifty units a
    second.
    """
    hazards, fresh = [], {}
    for obj in list(rafts.values()) + list(enemies):
        if obj.name == _SHARKS_RAFT and obj.id not in wrong_ids:
            continue
        x, y = obj.worldX, obj.worldY
        vx = vy = 0.0
        was = tracks.get(obj.id)
        if was is not None:
            elapsed = now - was[2]
            if elapsed > 0.01:
                vx, vy = (x - was[0]) / elapsed, (y - was[1]) / elapsed
                if math.hypot(vx, vy) > 4.0:        # teleported, not swimming
                    vx = vy = 0.0
        fresh[obj.id] = (x, y, now)
        hazards.append((x, y, vx, vy))
    tracks.clear()
    tracks.update(fresh)
    return hazards


def _sharks_pick(altdriver, targets, board, player, lane=2.5, detour=5.0):
    """Which answer raft to go for: the cheapest, not simply the nearest.

    A wrong raft or a shark sitting on the straight line to a word is a heart
    waiting to be lost, and the other answer raft is often barely further away
    with clear water in front of it. Anything within `lane` of the line counts
    as being in the way and costs `detour` units of "distance" -- so a clear
    run wins unless the blocked one is a great deal closer.
    """
    px, py = player.worldX, player.worldY
    in_the_way = [raft["pos"] for raft in board if not raft["correct"]]
    try:
        in_the_way += [(obj.worldX, obj.worldY)
                       for obj in altdriver.find_objects_which_contain(By.NAME, "Enemy")]
    except Exception:
        pass

    def cost(raft):
        tx, ty = raft["pos"]
        dx, dy = tx - px, ty - py
        span = dx * dx + dy * dy
        blocked = 0
        for hx, hy in in_the_way:
            along = 0.0 if span < 1e-6 else max(0.0, min(
                1.0, ((hx - px) * dx + (hy - py) * dy) / span))
            if math.hypot(px + dx * along - hx, py + dy * along - hy) < lane:
                blocked += 1
        return math.sqrt(span) + blocked * detour

    while targets:
        choice = min(targets, key=cost)
        try:
            raft = altdriver.find_object(By.ID, str(choice["id"]))
            if bool(raft.get_component_property("Raft", "CorrectWord", _SHARKS_ASM)):
                return choice
        except Exception:
            return choice               # gone or unreadable: let the sail find out
        # The cache said this raft was an answer and the raft says otherwise.
        # Sailing at a wrong word costs a life outright, so never take the
        # cache's word for it at the moment of choosing.
        targets = [raft for raft in targets if raft["id"] != choice["id"]]
    return None


def _sharks_sail_to(altdriver, target_id, wrong_ids, hooked_ids, islands,
                    width, height, timeout=60.0, finger=None):
    """Steer the player's raft onto one raft. True once it is hooked on.

    The raft is DRAGGED, never clicked: `begin_touch` on the player latches
    `PlayerMovement.dragit` (the press has to land on the player's own
    collider) and from then on the raft swims toward whatever world point the
    touch maps to. So the aim is re-sent several times a second instead of
    being one swipe -- both the target and the player are moving, the camera
    follows the player while dragging, and the heading has to keep changing to
    stay out of the sharks' way. A target off the edge of the screen is reached
    by aiming at the screen edge and letting the map scroll.

    Each tick costs four driver calls and nothing else, because the tick rate
    is the steering rate: read the rafts, read the player, read the sharks, and
    send one aim. Everything else -- has it hooked on, is the drag still
    latched -- is only worth a call every few ticks.
    """
    PANIC, STUCK_AFTER, STUCK_WITHIN, ESCAPE_FOR = 1.5, 2.0, 0.6, 1.2
    margin = max(60.0, 0.06 * height)
    ppu = _sharks_pixels_per_unit(altdriver, height)

    tracks = {}
    started = time.time()
    last_pos, anchor, escape_until, escape_dir = None, None, 0.0, (0.0, 0.0)
    escape_turn = 0
    speed, was_head, ticks = (0.0, 0.0), None, 0
    # Why a sail failed is worth knowing without another live investigation:
    # every failure prints how close it got, what was in the way and how much
    # of the time went on escaping or panicking.
    closest, panics, escapes, last = float("inf"), 0, 0, {}
    try:
        while time.time() - started < timeout:
            now = time.time()
            ticks += 1
            # Re-find rather than update_object(): a moving object's cached
            # world position does not refresh, which reads as a frozen game.
            rafts = {obj.id: obj for obj in altdriver.find_objects(By.NAME, _SHARKS_RAFT)}
            target = rafts.get(target_id)
            if target is None:
                # drowned and re-made, or the sentence moved on
                return False, finger
            player = altdriver.find_object(By.NAME, "Player")
            try:
                enemies = altdriver.find_objects_which_contain(By.NAME, "Enemy")
            except Exception:
                enemies = []

            px, py = player.worldX, player.worldY
            psx, psy = player.get_screen_position()
            tx, ty = target.worldX, target.worldY
            reach = math.hypot(tx - px, ty - py)

            if reach < 1.5 or ticks % 5 == 0:
                if bool(target.get_component_property("Raft", "Connected", _SHARKS_ASM)):
                    return True, finger
            if ticks % 15 == 0 and float(altdriver.get_time_scale()) < 0.01:
                # Paused: the retry popup is up. Let go -- the popup has to be
                # clicked -- and let the caller take it.
                if finger is not None:
                    altdriver.end_touch(finger)
                return False, None

            jumped = False
            if last_pos is not None:
                elapsed = max(now - last_pos[2], 0.01)
                jumped = math.hypot(px - last_pos[0], py - last_pos[1]) > 3.0
                speed = (0.0, 0.0) if jumped else ((px - last_pos[0]) / elapsed,
                                                   (py - last_pos[1]) / elapsed)
            last_pos = (px, py, now)
            if jumped:                          # bitten and moved somewhere safe
                tracks.clear()
                anchor, was_head = None, None
            # Stuck is NET displacement, not this tick's step: swerving round a
            # shark barely moves the raft for a tick or two and must not read as
            # aground, or the escape below fires while the raft is sailing fine.
            if anchor is None or math.hypot(px - anchor[0], py - anchor[1]) > STUCK_WITHIN:
                anchor = (px, py, now)

            way_x, way_y = _sharks_route(px, py, tx, ty, islands)
            goal_x, goal_y = way_x - px, way_y - py
            length = math.hypot(goal_x, goal_y) or 1.0
            goal_x, goal_y = goal_x / length, goal_y / length

            hazards = _sharks_hazards(rafts, enemies, wrong_ids, tracks, now)
            bodies = [(px, py)] + [(obj.worldX, obj.worldY)
                                   for rid, obj in rafts.items() if rid in hooked_ids]
            push_x, push_y, nearest, ahead, miss = _sharks_dodge(
                bodies, speed[0], speed[1], hazards)
            closest = min(closest, reach)
            last = {"reach": reach, "near": nearest, "ahead": ahead, "miss": miss}
            if (nearest < PANIC or miss < 0.9) and (push_x or push_y):
                # Slip round it; do not run from it. The blue shark FOLLOWS the
                # player, so a straight retreat just tows it along and the word
                # never comes closer -- measured on a failed sail: 62 of 187
                # ticks spent retreating and the raft finished 21 units away
                # having got within 7.7. Going off at a tangent keeps the same
                # distance from the shark and still makes ground, and the side
                # is picked as the one that heads towards the word.
                panics += 1
                span = math.hypot(push_x, push_y) or 1.0
                away_x, away_y = push_x / span, push_y / span
                slip_x, slip_y = -away_y, away_x
                if slip_x * goal_x + slip_y * goal_y < 0:
                    slip_x, slip_y = away_y, -away_x
                head_x = away_x * 0.6 + slip_x
                head_y = away_y * 0.6 + slip_y
            else:
                # Swerve, do not back off. Taking the push whole turns the raft
                # round, the hazard stops mattering, the raft turns back -- and
                # it rows forward and backward on the spot. Only the part of the
                # push ACROSS the heading is allowed through in full; the part
                # against it can slow the raft down, never reverse it.
                along = push_x * goal_x + push_y * goal_y
                side_x, side_y = push_x - goal_x * along, push_y - goal_y * along
                brake = max(-0.6, min(0.0, along))
                head_x = goal_x * (1.0 + brake) + side_x
                head_y = goal_y * (1.0 + brake) + side_y

            if reach < 1.5:
                # Alongside the raft: creeping the last half unit is not being
                # aground, and treating it as such sends the escape below off
                # in the wrong direction just as the catch is about to happen.
                anchor = (px, py, now)
            if now - anchor[2] > STUCK_AFTER and now > escape_until:
                # Wedged. The islands are lumpy polygons and this only models
                # them as ellipses, so the raft can be hard aground at a spot
                # the model calls open water -- measured: pinned on a shore the
                # ellipse put it 1 unit clear of. So the way out is not derived
                # from the model at all. Try open water if the model does know
                # about it, then sideways, back, and the other side in turn,
                # holding each for over a second: one of the four always frees
                # it, which is exactly how a person unsticks a boat.
                out_x, out_y = _sharks_offshore(px, py, islands, 1.0)
                ways = []
                if (out_x, out_y) != (px, py):
                    ways.append((out_x - px, out_y - py))
                ways += [(-goal_y, goal_x), (-goal_x, -goal_y), (goal_y, -goal_x)]
                escape_dir = ways[escape_turn % len(ways)]
                escape_turn += 1
                escape_until = now + ESCAPE_FOR
                anchor = (px, py, now)
                escapes += 1
                if escape_turn % 3 == 0:
                    # Three ways out and still nothing: suspect the press
                    # rather than the water, and take the drag again from a
                    # clean input state (see the note in `sharks`).
                    try:
                        altdriver.reset_input()
                    except Exception:
                        pass
                    finger = None
            if now < escape_until:
                head_x, head_y = escape_dir

            if was_head is not None:            # damp the turn, do not snap to it
                head_x = head_x * 0.65 + was_head[0] * 0.35
                head_y = head_y * 0.65 + was_head[1] * 0.35
            steer = math.hypot(head_x, head_y) or 1.0
            head_x, head_y = head_x / steer, head_y / steer
            was_head = (head_x, head_y)

            # Aim PAST the raft, never exactly at it. The player closes on the
            # touch point 5% at a time, so an aim sitting on the raft turns the
            # last unit into a crawl -- measured at 0.02 units a tick, still
            # short of the colliders touching, while the sharks close in. That
            # crawl is what drained the hearts on the long approaches.
            lead = min(_SHARKS_LEAD, reach + 0.8)
            if now < escape_until:
                lead = _SHARKS_LEAD     # pulling off a shore is worth the speed
            elif ahead < 4.0:
                # Slow down in traffic. The raft covers most of the gap to the
                # aim between two ticks -- about 1.4 units at full lead -- so a
                # hazard 2 units away can be reached and touched before the next
                # aim goes out. Shortening the lead near anything dangerous
                # gives the steering a tick or two to work, which is also how a
                # person plays it: fast across open water, careful in company.
                lead = min(lead, max(0.9, ahead * 0.7))
            aim_x, aim_y = px + head_x * lead, py + head_y * lead
            if reach > 3.0:
                # Only worth keeping the aim off the rocks on a long leg; near
                # the raft it fights the approach for no gain.
                aim_x, aim_y = _sharks_offshore(aim_x, aim_y, islands, 0.6)

            sx = min(width - margin, max(margin, psx + (aim_x - px) * ppu))
            sy = min(height - margin, max(margin, psy + (aim_y - py) * ppu))

            if finger is None:
                finger = altdriver.begin_touch((psx, psy))
                time.sleep(0.1)
            elif ticks % 12 == 0 and not bool(player.get_component_property(
                    "PlayerMovement", "dragit", _SHARKS_ASM)):
                # The press came off somehow (the game reloaded the map, or the
                # raft was under water when it landed). Take it again.
                altdriver.end_touch(finger)
                finger = altdriver.begin_touch((psx, psy))
                time.sleep(0.1)
            altdriver.move_touch(finger, (int(sx), int(sy)))
    except Exception:
        if finger is not None:
            altdriver.end_touch(finger)
        raise
    print(f"[WARN] SHARKS: gave up {closest:.1f} units short after {ticks} ticks "
          f"— last reach {last.get('reach', 0):.1f}, nearest hazard "
          f"{last.get('near', 0):.1f} ({last.get('ahead', 0):.1f} ahead), "
          f"{panics} panic(s), {escapes} escape(s)")
    return False, finger


def sharks(altdriver, raft_timeout=25.0, sentence_timeout=45.0, max_retries=3):
    """SHARKS: sail the player's raft into the rafts carrying the right words.

    The sentence at the top of the screen has blanks in it and every raft
    floats one word. Which words fill the blanks is not guessed -- each raft's
    own `Raft.CorrectWord` says so -- and neither is how many, since a sentence
    is done when the activity's `ProgressText` ticks over. Touching a right
    raft hooks it behind the player, touching a wrong one or a shark costs a
    life, so what is left is a steering problem: see `_sharks_sail_to`.
    """
    print("[INFO] SHARKS: starting")
    # Clear any press left over from an earlier run. A held touch that was
    # never ended -- a killed test, a crashed solver -- leaves the input mock
    # stuck: the game still reports `dragit` true but `Input.mousePosition`
    # freezes at whatever it last saw, so the raft answers no steering at all
    # and every word looks unreachable. It cost most of an afternoon to find.
    try:
        altdriver.reset_input()
    except Exception as reset_error:
        print(f"[WARN] SHARKS: could not reset the input first: {reset_error}")
    width, height = (float(value) for value in altdriver.get_application_screensize())
    islands = _sharks_islands(altdriver)
    done, total = _sharks_progress(altdriver)
    print(f"[INFO] SHARKS: {total} sentence(s) to complete, "
          f"{len(islands)} island(s) to sail around")
    if done >= total:
        # An activity always opens on 0/total. Finding it already finished means
        # this is the leftover board of a previous run, and sailing nowhere for
        # nought seconds would report a pass for a solve that never happened.
        raise AssertionError(
            f"SHARKS: opened on {done}/{total} — this board is already finished, "
            f"so nothing here was solved")

    # The drag is taken ONCE and held for the whole activity. Letting go
    # between catches left the raft sitting still for the second it takes to
    # re-read the board, and a still raft is what the sharks are for.
    collected, missed, retries, empty_since = 0, 0, 0, None
    known, finger = {}, None
    try:
        while done < total:
            if _sharks_take_retry(altdriver):
                retries += 1
                finger = None                       # the popup took the press with it
                if retries > max_retries:
                    raise AssertionError(
                        f"SHARKS: lost the hearts {retries} times by {done}/{total} — "
                        f"the sharks are winning, not the solver")
                done, total = _sharks_progress(altdriver)
                empty_since = None
                continue

            board = _sharks_board(altdriver, known)
            wrong_ids = {raft["id"] for raft in board if not raft["correct"]}
            targets = [raft for raft in board
                       if raft["correct"] and not raft["connected"] and not raft["drowning"]]

            if not targets:
                # Between sentences the rafts are destroyed and re-made, and a
                # bitten raft is under water for a couple of seconds. Both look the
                # same from here, so wait and re-read -- but if the activity itself
                # has gone (the hard timer runs out, or the lives do) say THAT,
                # instead of waiting out a timeout for rafts that will never come.
                #
                # The clock starts when the water goes EMPTY. Timing it from the
                # last sentence instead failed a run that was solving perfectly
                # well: three rafts took 47s to hook and the very first empty read
                # after them was already "stuck for 45s".
                if altdriver.get_current_scene() != "Sharks":
                    raise AssertionError(
                        f"SHARKS: the activity closed itself at {done}/{total} — "
                        f"out of time or out of lives")
                empty_since = empty_since or time.time()
                if time.time() - empty_since > sentence_timeout:
                    raise AssertionError(
                        f"SHARKS: stuck at {done}/{total} — no answer raft on the water "
                        f"for {sentence_timeout:.0f}s")
                time.sleep(1.0)
                was, (done, total) = done, _sharks_progress(altdriver)
                if done != was:
                    # The counter ticks over a second AFTER the last raft is
                    # hooked, so this is usually where a finished sentence is seen.
                    hearts = _sharks_hearts(altdriver)
                    print(f"[INFO] SHARKS: sentence {done}/{total} completed"
                          + (f", {hearts} heart(s) left" if hearts is not None else ""))
                continue
            empty_since = None

            player = altdriver.find_object(By.NAME, "Player")
            hooked_ids = {raft["id"] for raft in board if raft["connected"]}
            target = _sharks_pick(altdriver, targets, board, player)
            if target is None:
                known.clear()           # the cache disagreed with the game: re-read it
                continue
            started = time.time()
            print(f"[INFO] SHARKS: sailing for '{target['word']}' "
                  f"({len(targets)} answer raft(s) left in this sentence)")
            hooked, finger = _sharks_sail_to(
                altdriver, target["id"], wrong_ids, hooked_ids, islands,
                width, height, raft_timeout, finger)
            if hooked:
                collected += 1
                print(f"[INFO] SHARKS: hooked '{target['word']}' in {time.time() - started:.0f}s")
            else:
                missed += 1
                print(f"[WARN] SHARKS: lost '{target['word']}' after "
                      f"{time.time() - started:.0f}s — picking again")

            was = done
            done, total = _sharks_progress(altdriver)
            if done != was:
                hearts = _sharks_hearts(altdriver)
                print(f"[INFO] SHARKS: sentence {done}/{total} completed"
                      + (f", {hearts} heart(s) left" if hearts is not None else ""))
    finally:
        if finger is not None:
            altdriver.end_touch(finger)

    print(f"SHARKS RESULT: {done}/{total} sentences completed, {collected} answer "
          f"raft(s) hooked ({missed} re-picked, {retries} attempt(s) lost to the "
          f"sharks). Sailed with a held drag on the player's own raft; the timer "
          f"and the score screen are not asserted.")
