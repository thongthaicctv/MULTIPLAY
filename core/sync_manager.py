from PyQt6.QtCore import QTimer


class SyncManager:

    def __init__(self):

        self.players = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)

    # ===== add player =====
    def add_player(self, p):
        self.players.append(p)

    # ===== clear =====
    def clear(self):
        self.players.clear()

    # ===== start sync =====
    def start(self):
        self.timer.start(100)

    # ===== timeline seek =====
    def set_time(self, value):

        for p in self.players:
            p.set_time(value)

    # ===== realtime sync =====
    def sync(self):

        if not self.players:
            return

        base = self.players[0].get_time()

        for p in self.players[1:]:
            p.set_time(base)