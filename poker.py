"""Texas Hold'em poker engine: deck, hand eval, game state."""
import random
from typing import List, Tuple, Optional
from collections import Counter

RANKS = "23456789TJQKA"
SUITS = "shdc"  # spades, hearts, diamonds, clubs
RANK_VAL = {r: i for i, r in enumerate(RANKS, start=2)}


def new_deck() -> List[str]:
    deck = [r + s for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


# ----- Hand evaluation -----

def _rank_value(card: str) -> int:
    return RANK_VAL[card[0]]


def _suit(card: str) -> str:
    return card[1]


def _straight_high(values: List[int]) -> int:
    """Return highest card in straight, or 0 if no straight. values: sorted desc unique."""
    vs = sorted(set(values), reverse=True)
    # Wheel: A,2,3,4,5
    if 14 in vs:
        vs_low = vs + [1]
    else:
        vs_low = vs
    run = 1
    for i in range(len(vs_low) - 1):
        if vs_low[i] - 1 == vs_low[i + 1]:
            run += 1
            if run >= 5:
                return vs_low[i - 3]
        else:
            run = 1
    return 0


def evaluate_hand(cards: List[str]) -> Tuple[int, List[int], str]:
    """Evaluate best 5-card hand from up to 7 cards.
    Returns (category, tiebreakers, name). Higher tuple = better hand.
    Categories: 8=SF,7=4K,6=FH,5=Flush,4=Straight,3=3K,2=2P,1=Pair,0=High."""
    values = [_rank_value(c) for c in cards]
    suits = [_suit(c) for c in cards]
    val_count = Counter(values)
    suit_count = Counter(suits)

    # Flush check
    flush_suit = None
    for s, n in suit_count.items():
        if n >= 5:
            flush_suit = s
            break

    # Straight flush
    if flush_suit:
        sf_vals = [_rank_value(c) for c in cards if _suit(c) == flush_suit]
        sf_high = _straight_high(sf_vals)
        if sf_high:
            return (8, [sf_high], "Straight Flush" if sf_high < 14 else "Royal Flush")

    # Four of a kind
    fours = [v for v, n in val_count.items() if n == 4]
    if fours:
        four = max(fours)
        kicker = max(v for v in values if v != four)
        return (7, [four, kicker], "Four of a Kind")

    # Full house
    threes = sorted([v for v, n in val_count.items() if n == 3], reverse=True)
    pairs = sorted([v for v, n in val_count.items() if n == 2], reverse=True)
    if threes and (pairs or len(threes) >= 2):
        three = threes[0]
        pair = threes[1] if len(threes) >= 2 else pairs[0]
        return (6, [three, pair], "Full House")

    # Flush
    if flush_suit:
        flush_vals = sorted([_rank_value(c) for c in cards if _suit(c) == flush_suit], reverse=True)[:5]
        return (5, flush_vals, "Flush")

    # Straight
    high = _straight_high(values)
    if high:
        return (4, [high], "Straight")

    # Three of a kind
    if threes:
        three = threes[0]
        kickers = sorted([v for v in values if v != three], reverse=True)[:2]
        return (3, [three] + kickers, "Three of a Kind")

    # Two pair
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        kicker = max(v for v in values if v != p1 and v != p2)
        return (2, [p1, p2, kicker], "Two Pair")

    # Pair
    if pairs:
        p = pairs[0]
        kickers = sorted([v for v in values if v != p], reverse=True)[:3]
        return (1, [p] + kickers, "Pair")

    # High card
    top5 = sorted(values, reverse=True)[:5]
    return (0, top5, "High Card")


def compare_hands(cards1: List[str], cards2: List[str]) -> int:
    """1 if cards1 wins, -1 if cards2, 0 tie."""
    e1 = evaluate_hand(cards1)
    e2 = evaluate_hand(cards2)
    a = (e1[0], e1[1])
    b = (e2[0], e2[1])
    if a > b:
        return 1
    if a < b:
        return -1
    return 0
