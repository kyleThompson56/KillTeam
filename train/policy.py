# train/policy.py
import torch, torch.nn as nn, torch.nn.functional as F

MAX_ACTIONS = 128

class FlattenObs(nn.Module):
    def forward(self, obs):
        # obs is a dict from KTEnv._obs
        models = torch.tensor(obs["models"]).flatten()
        objs   = torch.tensor(obs["objectives"]).flatten()
        turn   = torch.tensor(obs["turn"]).flatten()
        x = torch.cat([models, objs, turn], dim=0)
        return x.float()

class PolicyNet(nn.Module):
    def __init__(self, obs_dim, hidden=256):
        super().__init__()
        self.pi = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, MAX_ACTIONS)
        )
        self.v = nn.Sequential(
            nn.Linear(obs_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, 1)
        )

    def forward(self, x, mask):
        logits = self.pi(x)
        # mask invalid actions by setting very negative logits
        neg_inf = torch.finfo(logits.dtype).min
        masked = torch.where(mask > 0, logits, torch.full_like(logits, neg_inf))
        value = self.v(x).squeeze(-1)
        return masked, value