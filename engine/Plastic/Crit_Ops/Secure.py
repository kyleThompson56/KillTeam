from ..Objective import ObjectivePoint

class SecureObjective(ObjectivePoint):
    """
    A Critical Ops objective that requires control and 1 AP spent to secure.
    Scoring happens only if the objective is secured by a team.
    """

    def __init__(self, name, position, radius=45.4):
        super().__init__(name, position, radius)
        self.controlling_team = None
        self.secured_by = None

    def update_control(self, models):
        team_ap = {}
        for model in models:
            if not model.is_alive():
                continue
            if self.distance_to(model.position) > self.radius:
                continue

            ap = getattr(model, "ap", 0)
            if getattr(model, "is_icon_bearer", False):
                ap += 1

            team = model.team
            team_ap[team] = team_ap.get(team, 0) + ap

        self.controlling_team = max(team_ap, key=team_ap.get) if team_ap else None

    def attempt_secure(self, model):
        """
        Model must be within range, alive, and belong to the controlling team.
        Must spend 1 AP to secure.
        """
        if not model.is_alive():
            return False
        if model.team != self.controlling_team:
            return False
        if self.distance_to(model.position) > self.radius:
            return False
        if model.ap < 1:
            return False

        model.ap -= 1
        self.secured_by = model.team
        return True

    def is_secured_by(self, team):
        return self.secured_by == team

    def score_secure_objectives(objectives, team_a, team_b):
        a_secured = sum(1 for obj in objectives if obj.is_secured_by(team_a))
        b_secured = sum(1 for obj in objectives if obj.is_secured_by(team_b))

        score = {team_a: 0, team_b: 0}
        if a_secured >= 1:
            score[team_a] += 1
        if b_secured >= 1:
            score[team_b] += 1

        if a_secured >= 2:
            score[team_a] += 1
        if b_secured >= 2:
            score[team_b] += 1

        return score
