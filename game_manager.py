"""Game manager: tables, seats, game loop, bots, broadcasts."""
import asyncio
import random
import time
import uuid
from typing import Dict, List, Optional, Set
from fastapi import WebSocket

from poker import new_deck, evaluate_hand

# Stake tiers: (sb, bb, min_buyin, max_buyin)
STAKE_TIERS = [
    {"id": "micro", "name": "Micro", "sb": 0.20, "bb": 0.40, "min_buyin": 8, "max_buyin": 40},
    {"id": "low", "name": "Low", "sb": 1, "bb": 2, "min_buyin": 40, "max_buyin": 200},
    {"id": "mid", "name": "Mid", "sb": 5, "bb": 10, "min_buyin": 200, "max_buyin": 1000},
    {"id": "high", "name": "High", "sb": 25, "bb": 50, "min_buyin": 1000, "max_buyin": 5000},
    {"id": "vip", "name": "VIP", "sb": 100, "bb": 200, "min_buyin": 4000, "max_buyin": 20000},
    {"id": "elite", "name": "Elite", "sb": 250, "bb": 500, "min_buyin": 10000, "max_buyin": 50000},
]

SEATS_PER_TABLE = 5
TURN_TIMEOUT = 30  # seconds


def _table_names():
    return [
        "Monte Carlo", "Macao", "Monaco", "Baden-Baden", "Venezia",
        "Park Hyatt", "Belagio", "Aria", "Borgata", "Wynn",
        "Cosmopolitan", "Caesars",
    ]


class Player:
    def __init__(self, user_id: str, username: str, avatar_id: str, chips: float, is_bot: bool = False):
        self.user_id = user_id
        self.username = username
        self.avatar_id = avatar_id
        self.chips = chips  # at table
        self.is_bot = is_bot
        self.hole_cards: List[str] = []
        self.bet: float = 0  # in current round
        self.total_bet: float = 0  # this hand
        self.folded = False
        self.all_in = False
        self.acted = False  # acted this round
        self.connected = True
        self.ws: Optional[WebSocket] = None

    def public_view(self, show_cards: bool = False):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "avatar_id": self.avatar_id,
            "chips": round(self.chips, 2),
            "is_bot": self.is_bot,
            "bet": round(self.bet, 2),
            "folded": self.folded,
            "all_in": self.all_in,
            "connected": self.connected,
            "has_cards": len(self.hole_cards) > 0,
            "hole_cards": self.hole_cards if show_cards else None,
        }


class Table:
    def __init__(self, table_id: str, name: str, tier: dict):
        self.id = table_id
        self.name = name
        self.tier = tier
        self.seats: List[Optional[Player]] = [None] * SEATS_PER_TABLE
        self.community: List[str] = []
        self.deck: List[str] = []
        self.pot: float = 0
        self.current_bet: float = 0
        self.dealer_pos: int = -1
        self.action_pos: int = -1
        self.stage: str = "waiting"  # waiting, preflop, flop, turn, river, showdown
        self.action_deadline: float = 0
        self.min_raise: float = tier["bb"]
        self.last_aggressor: int = -1
        self.last_winners: List[dict] = []
        self.last_hand_summary: Optional[dict] = None
        self.message_log: List[str] = []
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.hand_id: str = ""

    @property
    def players(self) -> List[Player]:
        return [p for p in self.seats if p is not None]

    @property
    def active_players(self) -> List[Player]:
        return [p for p in self.players if not p.folded]

    def occupied_count(self) -> int:
        return sum(1 for s in self.seats if s is not None)

    def open_seat(self) -> int:
        for i, s in enumerate(self.seats):
            if s is None:
                return i
        return -1

    def find_player(self, user_id: str) -> Optional[int]:
        for i, s in enumerate(self.seats):
            if s and s.user_id == user_id:
                return i
        return None

    def lobby_view(self):
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier,
            "seats_filled": self.occupied_count(),
            "seats_total": SEATS_PER_TABLE,
            "stage": self.stage,
        }

    def state_for(self, user_id: Optional[str]):
        players = []
        for i, p in enumerate(self.seats):
            if p is None:
                players.append(None)
            else:
                players.append({**p.public_view(show_cards=(p.user_id == user_id) or self.stage == "showdown"), "seat": i})
        action_seat = self.action_pos if self.stage in ("preflop", "flop", "turn", "river") else -1
        time_left = max(0, self.action_deadline - time.time()) if action_seat >= 0 else 0
        return {
            "table_id": self.id,
            "name": self.name,
            "tier": self.tier,
            "seats": players,
            "community": self.community,
            "pot": round(self.pot, 2),
            "current_bet": round(self.current_bet, 2),
            "dealer_pos": self.dealer_pos,
            "action_pos": action_seat,
            "stage": self.stage,
            "time_left": round(time_left, 1),
            "min_raise": round(self.min_raise, 2),
            "your_seat": self.find_player(user_id) if user_id else None,
            "last_hand_summary": self.last_hand_summary,
            "messages": self.message_log[-10:],
        }


class GameManager:
    def __init__(self):
        self.tables: Dict[str, Table] = {}
        self.user_table: Dict[str, str] = {}  # user_id -> table_id
        self.connections: Dict[str, Dict[str, WebSocket]] = {}  # table_id -> {user_id: ws}
        self.db = None
        self._build_tables()

    def _build_tables(self):
        names = _table_names()
        rng = random.Random(42)
        for tier in STAKE_TIERS:
            # 2 tables per tier
            for j in range(2):
                tid = f"{tier['id']}-{j+1}"
                tn = names[rng.randint(0, len(names) - 1)] + f" {j+1}"
                self.tables[tid] = Table(tid, tn, tier)

    def set_db(self, db):
        self.db = db

    def list_tables(self):
        return [t.lobby_view() for t in self.tables.values()]

    def find_open_table(self, tier_id: str) -> Optional[Table]:
        for t in self.tables.values():
            if t.tier["id"] == tier_id and t.open_seat() >= 0:
                return t
        return None

    async def seat_user(self, user: dict, tier_id: str) -> Optional[str]:
        """Seat user at first open table in tier. Returns table_id."""
        # Remove from any existing table
        if user["id"] in self.user_table:
            await self.leave_table(user["id"])
        table = self.find_open_table(tier_id)
        if not table:
            return None
        seat = table.open_seat()
        # Buy in with min buy-in if user has enough chips
        buyin = min(user.get("chips", 0), table.tier["max_buyin"])
        if buyin < table.tier["min_buyin"]:
            return None
        # Deduct chips from user balance
        await self.db.users.update_one({"id": user["id"]}, {"$inc": {"chips": -buyin}})
        table.seats[seat] = Player(user["id"], user["username"], user["avatar_id"], buyin, is_bot=False)
        self.user_table[user["id"]] = table.id
        await self._fill_bots(table)
        await self.broadcast(table)
        if table._task is None or table._task.done():
            table._task = asyncio.create_task(self._game_loop(table))
        return table.id

    async def _fill_bots(self, table: Table):
        """Fill empty seats with bots so game runs immediately."""
        bot_names = ["Alex", "Mila", "Yuri", "Sasha", "Nina", "Igor", "Lana", "Dima", "Vera", "Kai"]
        avatars = ["man1", "man2", "woman1", "woman2", "man3", "woman3"]
        existing = {p.username for p in table.players}
        for i in range(SEATS_PER_TABLE):
            if table.seats[i] is None:
                # Bot buyin: average of min/max
                buyin = (table.tier["min_buyin"] + table.tier["max_buyin"]) / 2
                name = random.choice([n for n in bot_names if n not in existing] or bot_names)
                existing.add(name)
                bot = Player(f"bot-{uuid.uuid4().hex[:8]}", name, random.choice(avatars), buyin, is_bot=True)
                table.seats[i] = bot

    async def leave_table(self, user_id: str):
        table_id = self.user_table.get(user_id)
        if not table_id:
            return
        table = self.tables.get(table_id)
        if not table:
            return
        seat = table.find_player(user_id)
        if seat is not None:
            player = table.seats[seat]
            # Return chips to user balance
            if player and self.db is not None:
                await self.db.users.update_one({"id": user_id}, {"$inc": {"chips": player.chips}})
            table.seats[seat] = None
            # Mark folded if in hand
            if player and not player.folded:
                player.folded = True
        self.user_table.pop(user_id, None)
        if table_id in self.connections:
            self.connections[table_id].pop(user_id, None)
        await self.broadcast(table)

    async def connect(self, table_id: str, user_id: str, ws: WebSocket):
        self.connections.setdefault(table_id, {})[user_id] = ws
        table = self.tables.get(table_id)
        if table:
            seat = table.find_player(user_id)
            if seat is not None and table.seats[seat]:
                table.seats[seat].ws = ws
                table.seats[seat].connected = True
            await self.broadcast(table)

    async def disconnect(self, table_id: str, user_id: str):
        conns = self.connections.get(table_id, {})
        conns.pop(user_id, None)
        table = self.tables.get(table_id)
        if table:
            seat = table.find_player(user_id)
            if seat is not None and table.seats[seat]:
                table.seats[seat].connected = False
                table.seats[seat].ws = None

    async def broadcast(self, table: Table):
        conns = self.connections.get(table.id, {})
        dead = []
        for uid, ws in conns.items():
            try:
                await ws.send_json({"type": "state", "data": table.state_for(uid)})
            except Exception:
                dead.append(uid)
        for uid in dead:
            conns.pop(uid, None)

    async def player_action(self, table: Table, user_id: str, action: str, amount: float = 0):
        async with table._lock:
            seat = table.find_player(user_id)
            if seat is None or seat != table.action_pos:
                return {"error": "Not your turn"}
            player = table.seats[seat]
            if player.folded or player.all_in:
                return {"error": "Cannot act"}
            await self._apply_action(table, seat, action, amount)
            await self._after_action(table)
            return {"ok": True}

    async def _apply_action(self, table: Table, seat: int, action: str, amount: float):
        player = table.seats[seat]
        to_call = table.current_bet - player.bet
        if action == "fold":
            player.folded = True
            table.message_log.append(f"{player.username} folds")
        elif action == "check":
            if to_call > 0.0001:
                # Treat as fold
                player.folded = True
                table.message_log.append(f"{player.username} folds (invalid check)")
            else:
                table.message_log.append(f"{player.username} checks")
        elif action == "call":
            pay = min(to_call, player.chips)
            player.chips -= pay
            player.bet += pay
            player.total_bet += pay
            table.pot += pay
            if player.chips < 0.001:
                player.all_in = True
            table.message_log.append(f"{player.username} calls {pay:.2f}")
        elif action == "raise" or action == "bet":
            # amount is the new total bet target
            target = max(amount, table.current_bet + table.min_raise)
            target = min(target, player.bet + player.chips)
            add = target - player.bet
            if add <= 0:
                # Treat as call/check
                pay = min(to_call, player.chips)
                player.chips -= pay
                player.bet += pay
                player.total_bet += pay
                table.pot += pay
                if player.chips < 0.001:
                    player.all_in = True
                table.message_log.append(f"{player.username} calls {pay:.2f}")
            else:
                player.chips -= add
                player.bet += add
                player.total_bet += add
                table.pot += add
                raise_amt = player.bet - table.current_bet
                if raise_amt >= table.min_raise:
                    table.min_raise = raise_amt
                    table.last_aggressor = seat
                    # Reset acted flags
                    for p in table.players:
                        if p != player and not p.folded and not p.all_in:
                            p.acted = False
                table.current_bet = max(table.current_bet, player.bet)
                if player.chips < 0.001:
                    player.all_in = True
                table.message_log.append(f"{player.username} raises to {player.bet:.2f}")
        player.acted = True

    async def _after_action(self, table: Table):
        # Check if hand should end (only one not folded)
        not_folded = [p for p in table.players if not p.folded]
        if len(not_folded) == 1:
            await self._award_pot(table, [(not_folded[0], "wins uncontested")])
            await self._next_hand(table)
            return
        # Check if all remaining players are all-in or have acted and matched bet
        active_to_act = [p for p in not_folded if not p.all_in]
        all_matched = all(abs(p.bet - table.current_bet) < 0.001 for p in active_to_act)
        all_acted = all(p.acted for p in active_to_act)
        if all_matched and all_acted:
            await self._advance_stage(table)
        else:
            await self._next_actor(table)
        await self.broadcast(table)

    async def _next_actor(self, table: Table):
        n = SEATS_PER_TABLE
        for i in range(1, n + 1):
            pos = (table.action_pos + i) % n
            p = table.seats[pos]
            if p and not p.folded and not p.all_in:
                table.action_pos = pos
                table.action_deadline = time.time() + TURN_TIMEOUT
                return
        table.action_pos = -1

    async def _advance_stage(self, table: Table):
        # Move to next stage
        for p in table.players:
            p.bet = 0
            p.acted = False
        table.current_bet = 0
        table.min_raise = table.tier["bb"]
        if table.stage == "preflop":
            table.stage = "flop"
            table.community.extend([table.deck.pop(), table.deck.pop(), table.deck.pop()])
            table.message_log.append(f"Flop: {' '.join(table.community)}")
        elif table.stage == "flop":
            table.stage = "turn"
            table.community.append(table.deck.pop())
            table.message_log.append(f"Turn: {table.community[-1]}")
        elif table.stage == "turn":
            table.stage = "river"
            table.community.append(table.deck.pop())
            table.message_log.append(f"River: {table.community[-1]}")
        elif table.stage == "river":
            await self._showdown(table)
            await self._next_hand(table)
            return
        # Set action to first active player left of dealer
        table.action_pos = table.dealer_pos
        await self._next_actor(table)
        # If everyone is all-in, skip to showdown rapidly
        active_to_act = [p for p in table.players if not p.folded and not p.all_in]
        if len(active_to_act) <= 1:
            # Reveal remaining community cards
            await self.broadcast(table)
            await asyncio.sleep(1.5)
            while table.stage in ("flop", "turn"):
                if table.stage == "flop":
                    table.stage = "turn"
                    table.community.append(table.deck.pop())
                elif table.stage == "turn":
                    table.stage = "river"
                    table.community.append(table.deck.pop())
                await self.broadcast(table)
                await asyncio.sleep(1.5)
            await self._showdown(table)
            await self._next_hand(table)
            return

    async def _showdown(self, table: Table):
        table.stage = "showdown"
        contenders = [p for p in table.players if not p.folded]
        if not contenders:
            return
        # Evaluate
        best = []
        for p in contenders:
            score = evaluate_hand(p.hole_cards + table.community)
            best.append((p, score))
        best.sort(key=lambda x: (x[1][0], x[1][1]), reverse=True)
        # Find ties at top
        top_score = (best[0][1][0], best[0][1][1])
        winners = [(p, s[2]) for p, s in best if (s[0], s[1]) == top_score]
        await self._award_pot(table, [(w[0], f"wins with {w[1]}") for w in winners])

    async def _award_pot(self, table: Table, winners_msg: list):
        n = len(winners_msg)
        if n == 0:
            return
        share = table.pot / n
        summary_winners = []
        for player, msg in winners_msg:
            player.chips += share
            table.message_log.append(f"{player.username} {msg} ({share:.2f})")
            summary_winners.append({"username": player.username, "msg": msg, "amount": round(share, 2), "user_id": player.user_id})
        table.last_hand_summary = {
            "winners": summary_winners,
            "community": list(table.community),
            "showdown": [{"user_id": p.user_id, "username": p.username, "hole_cards": p.hole_cards}
                         for p in table.players if not p.folded],
            "pot": round(table.pot, 2),
        }
        table.pot = 0

    async def _next_hand(self, table: Table):
        # Persist chips for humans
        if self.db is not None:
            for p in table.players:
                if not p.is_bot:
                    # Update only if change (skip; we always sync chip balance on leave)
                    pass
        # Reset and start next hand if at least 2 players have chips
        await self.broadcast(table)
        await asyncio.sleep(3.0)
        # Remove broke bots and refill
        for i, p in enumerate(table.seats):
            if p and p.is_bot and p.chips < table.tier["bb"]:
                table.seats[i] = None
        await self._fill_bots(table)
        # Reset hand state
        for p in table.players:
            p.hole_cards = []
            p.bet = 0
            p.total_bet = 0
            p.folded = False
            p.all_in = False
            p.acted = False
        table.community = []
        table.pot = 0
        table.current_bet = 0
        table.last_hand_summary = None
        eligible = [i for i, p in enumerate(table.seats) if p and p.chips > 0]
        if len(eligible) < 2:
            table.stage = "waiting"
            table.action_pos = -1
            await self.broadcast(table)
            return
        # Advance dealer
        n = SEATS_PER_TABLE
        for i in range(1, n + 1):
            pos = (table.dealer_pos + i) % n
            if pos in eligible:
                table.dealer_pos = pos
                break
        # Post blinds: SB next to dealer, BB after SB (heads-up: dealer is SB)
        order = []
        for i in range(1, n + 1):
            pos = (table.dealer_pos + i) % n
            if pos in eligible:
                order.append(pos)
        if len(order) < 2:
            return
        if len(eligible) == 2:
            sb_pos = table.dealer_pos
            bb_pos = order[0]
        else:
            sb_pos = order[0]
            bb_pos = order[1]
        table.hand_id = uuid.uuid4().hex[:8]
        table.deck = new_deck()
        table.stage = "preflop"
        table.current_bet = table.tier["bb"]
        table.min_raise = table.tier["bb"]
        # Post SB
        sb_player = table.seats[sb_pos]
        sb_amt = min(table.tier["sb"], sb_player.chips)
        sb_player.chips -= sb_amt
        sb_player.bet = sb_amt
        sb_player.total_bet = sb_amt
        table.pot += sb_amt
        if sb_player.chips < 0.001:
            sb_player.all_in = True
        # Post BB
        bb_player = table.seats[bb_pos]
        bb_amt = min(table.tier["bb"], bb_player.chips)
        bb_player.chips -= bb_amt
        bb_player.bet = bb_amt
        bb_player.total_bet = bb_amt
        table.pot += bb_amt
        if bb_player.chips < 0.001:
            bb_player.all_in = True
        # Deal hole cards
        for _ in range(2):
            for pos in order:
                p = table.seats[pos]
                p.hole_cards.append(table.deck.pop())
        # First to act preflop: after BB
        bb_idx = order.index(bb_pos)
        first_to_act = order[(bb_idx + 1) % len(order)]
        table.action_pos = first_to_act
        table.action_deadline = time.time() + TURN_TIMEOUT
        table.last_aggressor = bb_pos
        table.message_log.append(f"=== New Hand #{table.hand_id} ===")
        table.message_log.append(f"{sb_player.username} posts SB {sb_amt:.2f}")
        table.message_log.append(f"{bb_player.username} posts BB {bb_amt:.2f}")
        await self.broadcast(table)

    async def _game_loop(self, table: Table):
        """Main loop driving turns, bots, timeouts."""
        try:
            # Start first hand if at least 2 players
            await asyncio.sleep(2.0)
            if len([p for p in table.players if p.chips > 0]) >= 2:
                await self._next_hand(table)
            while True:
                await asyncio.sleep(0.5)
                # End loop if no human players
                humans = [p for p in table.players if not p.is_bot]
                if not humans:
                    # Reset table for cleanup
                    table.stage = "waiting"
                    table.action_pos = -1
                    table.seats = [None] * SEATS_PER_TABLE
                    table.community = []
                    table.pot = 0
                    table.last_hand_summary = None
                    return
                if table.stage not in ("preflop", "flop", "turn", "river"):
                    continue
                if table.action_pos < 0:
                    continue
                player = table.seats[table.action_pos]
                if player is None or player.folded or player.all_in:
                    async with table._lock:
                        await self._next_actor(table)
                        await self.broadcast(table)
                    continue
                # Bot action
                if player.is_bot:
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                    if table.action_pos >= 0 and table.seats[table.action_pos] is player:
                        async with table._lock:
                            await self._bot_decide(table, table.action_pos)
                            await self._after_action(table)
                    continue
                # Human timeout
                if time.time() > table.action_deadline:
                    async with table._lock:
                        if table.action_pos >= 0 and table.seats[table.action_pos] is player and not player.folded:
                            to_call = table.current_bet - player.bet
                            action = "check" if to_call < 0.001 else "fold"
                            await self._apply_action(table, table.action_pos, action, 0)
                            await self._after_action(table)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()

    async def _bot_decide(self, table: Table, seat: int):
        player = table.seats[seat]
        to_call = table.current_bet - player.bet
        # Simple bot AI: random with weighting
        r = random.random()
        if to_call < 0.001:
            # Can check
            if r < 0.7:
                await self._apply_action(table, seat, "check", 0)
            else:
                # Bet
                bet_amt = table.tier["bb"] * random.choice([2, 3, 4])
                await self._apply_action(table, seat, "raise", player.bet + bet_amt)
        else:
            # Decide fold / call / raise
            pot_odds = to_call / (table.pot + to_call + 0.0001)
            if r < 0.2 and pot_odds > 0.3:
                await self._apply_action(table, seat, "fold", 0)
            elif r < 0.85:
                await self._apply_action(table, seat, "call", 0)
            else:
                raise_amt = table.current_bet + table.min_raise * random.choice([1, 2])
                await self._apply_action(table, seat, "raise", raise_amt)


# Singleton
manager = GameManager()
