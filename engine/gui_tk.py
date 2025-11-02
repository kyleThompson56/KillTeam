# engine/gui_tk.py
import tkinter as tk
from engine.actions import Move, Shoot, End, Fight

MM_TO_PX = 1.5  # 2.0 can make a huge window; tweak to taste

class GuiController:
    def __init__(self, board, scale=MM_TO_PX):
        self.board = board
        self.scale = scale
        self.root = tk.Tk()
        self.root.title("KillTeam (GUI Controller)")
        self.mode = "idle" # team_selection, operative_selection, side_selection, deployment, strategy_ploys, firefight_ploys, target_selection, action_selection, token_removal

        self._selection_callback = None

        # Top frame with buttons/labels
        top = tk.Frame(self.root, bg="#333")
        top.pack(fill=tk.X)
        self.info_lbl = tk.Label(top, text="", fg="white", bg="#333")
        self.info_lbl.pack(side=tk.LEFT, padx=8, pady=4)
        self.end_btn = tk.Button(top, text="End Activation", command=self._on_end)
        self.end_btn.pack(side=tk.RIGHT, padx=8, pady=4)

        # Canvas (main board)
        self.canvas = tk.Canvas(self.root, width=board.width*scale, height=board.height*scale, bg="#222")
        self.canvas.pack()
        self._legal = []
        self._resolve = None  # function to call when user picks an action
        self._pending_end = False
        self.canvas.bind("<Button-1>", self._on_click)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- NEW: Bottom log panel (message box) ---
        bottom = tk.Frame(self.root)
        bottom.pack(fill=tk.BOTH)
        self.log_text = tk.Text(bottom, height=8, bg="#111", fg="#ddd", state="disabled", wrap="word")
        scroll = tk.Scrollbar(bottom, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        # Place on the left and let it expand; scrollbar on the right
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- NEW: Action selection panel ---
        self.action_frame = tk.Frame(self.root, bg="#222")
        self.action_frame.pack(fill=tk.X)
        self.action_buttons = []
        self._selected_action = None  # stores currently selected action label

    # --- public ---
    def draw_board(self, actor=None, legal_actions=None):
        self._draw(actor, legal_actions or [])

    # --- NEW: public log sink for engine ---
    def log(self, msg: str):
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, msg.rstrip() + "\n")
            self.log_text.see(tk.END)  # autoscroll
        finally:
            self.log_text.configure(state="disabled")
        # keep the UI responsive
        self.root.update_idletasks()

    # --- private ---
    def _draw(self, actor, legal_actions):
        c = self.canvas
        c.delete("all")
        # Info label
        if actor is not None:
            self.info_lbl.config(text=f"[{actor.team}] {actor.name} — choose an action")
        else:
            self.info_lbl.config(text="Waiting...")

        # Terrain (walls)
        for t in self.board.terrain:
            if hasattr(t, 'aabb') and getattr(t, 'is_active', True):
                minx,miny,maxx,maxy = t.aabb()
                c.create_rectangle(minx*self.scale, miny*self.scale, maxx*self.scale, maxy*self.scale, fill="#555")
        # Objectives
        for t in self.board.terrain:
            if hasattr(t, 'radius'):
                x,y = t.position
                r = t.radius
                c.create_oval((x-r)*self.scale, (y-r)*self.scale, (x+r)*self.scale, (y+r)*self.scale, outline="#ffa500", width=2)
        # Operatives
        for m in self.board.models:
            x,y = m.position; r = m.radius_mm
            color = "#4caf50" if (actor and m.team == actor.team) else "#e91e63"
            c.create_oval((x-r)*self.scale, (y-r)*self.scale, (x+r)*self.scale, (y+r)*self.scale, fill=color)
            c.create_text(x*self.scale, (y-r-10)*self.scale, text=f"{m.name} HP:{getattr(m,'hp','?')} AP:{getattr(m,'ap','?')}", fill="white")
        # Legal overlays
        self._legal = []
        for a in legal_actions:
            if isinstance(a, Move):
                x,y = a.dest
                id_ = c.create_oval((x-3)*self.scale, (y-3)*self.scale, (x+3)*self.scale, (y+3)*self.scale, fill="#00e5ff")
                self._legal.append((id_, a, (x,y)))
            elif isinstance(a, Shoot):
                target = self.board.models[a.target_id]
                x,y = target.position; r = target.radius_mm
                id_ = c.create_oval((x-r)*self.scale, (y-r)*self.scale, (x+r)*self.scale, (y+r)*self.scale, outline="#ffff00", width=3)
                self._legal.append((id_, a, (x,y)))
        self.root.update_idletasks(); self.root.update()

    def draw_movement_area(self, positions: set[tuple[float, float]]):
        self._legal = []  # Clear previous legal actions
        for x, y in positions:
            id_ = self.canvas.create_rectangle(
                (x - 2) * self.scale, (y - 2) * self.scale,
                (x + 2) * self.scale, (y + 2) * self.scale,
                fill="#00e5ff", outline=""
            )
            self._legal.append((id_, Move((x, y)), (x, y)))

    def set_actions(self, actions: list[str]):
        # Clear old buttons
        for btn in self.action_buttons:
            btn.destroy()
        self.action_buttons.clear()

        for label in actions:
            btn = tk.Button(self.action_frame, text=label, command=lambda l=label: self._on_action_select(l))
            btn.pack(side="left", padx=4, pady=4)
            self.action_buttons.append(btn)

        self._selected_action = None

    def _on_action_select(self, label: str):
        self._selected_action = label
        self.info_lbl.config(text=f"Selected: {label}")

        if self.mode in ["team_selection", "ploy_selection_strategy", "ploy_selection_firefight", "side_selection"]:
            if self._resolve:
                self._resolve(label)
            return

        if self._resolve and self._current_actor and self._current_engine:
            if label in ["Dash", "Reposition", "Charge", "Fallback"]:
                positions = self._current_engine.get_valid_destinations(self._current_actor, label.lower())
                self.draw_board(self._current_actor)
                self.draw_movement_area(positions)
            elif label in ["Shoot", "Fight"]:
                self.draw_board(self._current_actor)  # You can later add target highlights

    def _on_click(self, event):
        x = event.x / self.scale
        y = event.y / self.scale
        if self._resolve and self._selected_action:
            if self._selected_action in ["Dash", "Reposition", "Charge", "Fallback"]:
                self._resolve(Move((x, y), mode=self._selected_action.lower()))
            elif self._selected_action == "Shoot":
                target = self._find_nearest_model(x, y)
                if target:
                    self._resolve(Shoot(target))
            elif self._selected_action == "Fight":
                target = self._find_nearest_model(x, y)
                if target:
                    self._resolve(Fight(target))

    def _on_end(self):
        # End activation via button
        if self._resolve:
            self._resolve(End())

    def _on_close(self):
        # Gracefully end current selection and close window
        try:
            if self._resolve:
                self._resolve(End())
        finally:
            self.root.destroy()

    def select_action(self, game, operative, legal):
        self.mode = "activation"
        self._current_actor = operative
        self._current_engine = game

        legal_actions = game.legal_actions_for(operative)

        labels = []
        for action in legal_actions:
            if isinstance(action, Move):
                labels.append(action.mode.capitalize())
            elif isinstance(action, Shoot):
                labels.append("Shoot")
            elif isinstance(action, Fight):
                labels.append("Fight")
            elif isinstance(action, End):
                labels.append("End")

        seen = set()
        unique_labels = [x for x in labels if not (x in seen or seen.add(x))]
        self.set_actions(unique_labels)
        self.draw_board(operative)

        chosen = None

        def set_choice(a):
            nonlocal chosen; chosen = a

        self._resolve = set_choice

        while chosen is None:
            self.root.update_idletasks()
            self.root.update()

        self._resolve = None
        return chosen

    def _find_nearest_model(self, x, y, max_dist=10.0):
        best = None
        best_dist = float('inf')
        for m in self.board.models:
            mx, my = m.position
            dist = ((mx - x) ** 2 + (my - y) ** 2) ** 0.5
            if dist < best_dist and dist <= max_dist:
                best = m
                best_dist = dist
        return best
