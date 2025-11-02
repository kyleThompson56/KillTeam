# engine/Plastic/TacOps/TacOps.py

def update_martyr_tokens(game):
    """Called whenever a friendly operative is incapacitated. Adds martyr token to contested objective."""
    for obj in game.objectives:
        if obj.distance_to(game.last_incapacitated.position) <= obj.radius:
            if game.last_incapacitated.team == game.current_team():
                obj.martyr_tokens = obj.martyr_tokens if hasattr(obj, 'martyr_tokens') else {}
                obj.martyr_tokens.setdefault(game.last_incapacitated.team, 0)
                obj.martyr_tokens[game.last_incapacitated.team] += 1

def score_martyr(game, team):
    """Called at end of TP (after TP1). Scores VP for removing martyr tokens."""
    if game.tp <= 1:
        return  # No scoring in TP1

    team = game.current_team()
    vp_gained = 0
    for obj in game.objectives:
        if not hasattr(obj, 'martyr_tokens'):
            continue
        tokens = obj.martyr_tokens.get(team, 0)
        if tokens <= 0:
            continue
        # Check if any friendly op is contesting this objective
        for op in game.living_team_ops(team):
            if obj.distance_to(op.position) <= obj.radius:
                # Remove up to 2 tokens
                remove_count = min(2 - vp_gained, tokens)
                if remove_count <= 0:
                    break
                obj.martyr_tokens[team] -= remove_count
                if obj.is_secured_by(team):
                    vp_gained += 2 * remove_count
                else:
                    vp_gained += 1 * remove_count
                break  # Only score once per objective
        if vp_gained >= 2:
            break  # Max 2 VP per TP

    game.vp[team] += vp_gained

def score_track_enemy(game, team):
    """Scores Track Enemy Tac Op at end of TP (after TP1)."""
    if game.tp <= 1:
        return
    tracked_enemies = set()
     # Get all living friendly operatives with Conceal order
    friendly_ops = [op for op in game.living_team_ops(team) if op.order == "Conceal"]
    for friendly in friendly_ops:
        # Must not be in control range of any enemy
        if any(game.board.control_range(friendly, enemy) for enemy in game.living_team_ops(game.other_team())):
            continue

        if friendly.order == "Engage":
            continue

        for enemy in game.living_team_ops(game.other_team()):
            # Must be within 6 inches (152.4mm)
            dx = friendly.position[0] - enemy.position[0]
            dy = friendly.position[1] - enemy.position[1]
            dist_sq = dx * dx + dy * dy
            if dist_sq > 152.4 * 152.4:
                continue

            # Enemy must be a valid target for friendly
            if not game.is_valid_target(friendly, enemy):
                continue

            # Friendly must NOT be a valid target for enemy
            if game.is_valid_target(enemy, friendly):
                continue

            tracked_enemies.add(enemy)
            break  # One tracker per friendly is enough

    # Scoring logic
    count = len(tracked_enemies)
    if count == 0:
        return
    elif count == 1:
        vp = 2 if game.tp == 4 else 1
    else:
        vp = 2

    game.vp[team] += vp
    game._log(f"[TACOP] {team} scores {vp} VP from Track Enemy ({count} tracked)")

def score_dominate(game, team):
    """Scores Dominate Tac Op at end of TP 3 and 4."""
    if game.tp not in (3, 4):
        return

    vp_gained = 0
    for op in game.living_team_ops(team):
        if not hasattr(op, 'dominate_tokens'):
           continue
        tokens = op.dominate_tokens
        if tokens <= 0:
           continue
        remove = min(3 - vp_gained, tokens)
        op.dominate_tokens -= remove
        vp_gained += remove
        if vp_gained >= 3:
            break

    if vp_gained > 0:
        game.vp[team] += vp_gained
        game._log(f"[TACOP] {team} scores {vp_gained} VP from Dominate")

def score_scout_enemy_movement(game, team):
    """Scores Scout Enemy Movement Tac Op at end of TP (after TP1)."""
    if game.tp <= 1:
        return
    vp_gained = 0
    for enemy in game.living_team_ops(game.other_team()):
        if getattr(enemy, 'monitored_by', None) == team:
            # Must still be visible to at least one friendly operative
            for friendly in game.living_team_ops(team):
                if game.board.has_los(friendly, enemy):
                    vp_gained += 1
                    break
        if vp_gained >= 2:
            break

    if vp_gained > 0:
        game.vp[team] += vp_gained
        game._log(f"[TACOP] {team} scores {vp_gained} VP from Scout Enemy Movement")


