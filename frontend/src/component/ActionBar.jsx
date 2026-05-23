import { useState, useMemo, useEffect } from "react";

export default function ActionBar({ state, onAction, disabled }) {
  const seat = state.your_seat;
  const me = seat != null ? state.seats[seat] : null;
  const isMyTurn = !disabled && seat === state.action_pos && me && !me.folded && !me.all_in;
  const toCall = me ? Math.max(0, state.current_bet - me.bet) : 0;
  const minRaise = state.current_bet + state.min_raise;
  const maxBet = me ? me.bet + me.chips : 0;
  const [raiseAmount, setRaiseAmount] = useState(minRaise);

  useEffect(() => {
    if (isMyTurn) {
      setRaiseAmount(Math.min(maxBet, Math.max(minRaise, state.current_bet + state.tier.bb)));
    }
  }, [isMyTurn, minRaise, maxBet, state.current_bet, state.tier.bb]);

  const canCheck = toCall < 0.001;
  const canRaise = maxBet >= minRaise;

  if (!me) return null;

  return (
    <div className="pointer-events-auto">
      <div className="flex flex-col gap-3 items-center">
        {/* Slider */}
        {isMyTurn && canRaise && (
          <div className="w-full max-w-md flex items-center gap-3 bg-black/70 backdrop-blur border border-white/10 px-4 py-3">
            <button
              onClick={() => setRaiseAmount(Math.max(minRaise, raiseAmount - state.tier.bb))}
              className="text-[#D4AF37] px-2"
              data-testid="raise-dec"
            >−</button>
            <input
              type="range"
              min={minRaise}
              max={maxBet}
              step={state.tier.sb}
              value={Math.min(maxBet, Math.max(minRaise, raiseAmount))}
              onChange={(e) => setRaiseAmount(Number(e.target.value))}
              className="flex-1 accent-[#D4AF37]"
              data-testid="raise-slider"
            />
            <button
              onClick={() => setRaiseAmount(Math.min(maxBet, raiseAmount + state.tier.bb))}
              className="text-[#D4AF37] px-2"
              data-testid="raise-inc"
            >+</button>
            <div className="font-mono text-sm text-[#D4AF37] w-20 text-right" data-testid="raise-amount">
              ${raiseAmount.toFixed(2)}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 md:gap-3">
          <ActionBtn
            label="Fold"
            color="#7A1717"
            disabled={!isMyTurn}
            onClick={() => onAction("fold", 0)}
            testid="action-fold"
          />
          {canCheck ? (
            <ActionBtn
              label="Check"
              color="#4F5359"
              disabled={!isMyTurn}
              onClick={() => onAction("check", 0)}
              testid="action-check"
            />
          ) : (
            <ActionBtn
              label={`Call $${toCall.toFixed(2)}`}
              color="#4F5359"
              disabled={!isMyTurn}
              onClick={() => onAction("call", 0)}
              testid="action-call"
            />
          )}
          {canRaise && (
            <ActionBtn
              label={state.current_bet > 0 ? `Raise to $${raiseAmount.toFixed(2)}` : `Bet $${raiseAmount.toFixed(2)}`}
              color="#D4AF37"
              dark
              disabled={!isMyTurn}
              onClick={() => onAction("raise", raiseAmount)}
              testid="action-raise"
            />
          )}
          {me.chips > 0 && (
            <ActionBtn
              label="All-In"
              color="#D4AF37"
              dark
              disabled={!isMyTurn}
              onClick={() => onAction("raise", maxBet)}
              testid="action-allin"
            />
          )}
        </div>
        {!isMyTurn && (
          <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500" data-testid="waiting-turn">
            {me.folded ? "You folded" : state.action_pos >= 0 ? "Waiting for opponent..." : "Hand starting..."}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionBtn({ label, color, dark, disabled, onClick, testid }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      data-testid={testid}
      className="px-4 md:px-6 py-3 text-xs uppercase tracking-[0.25em] font-sans border transition-all disabled:opacity-30 disabled:cursor-not-allowed hover:brightness-110"
      style={{
        backgroundColor: dark ? color : "rgba(0,0,0,0.6)",
        borderColor: color,
        color: dark ? "#0a0a0c" : "#F4F4F5",
        backdropFilter: "blur(10px)",
      }}
    >
      {label}
    </button>
  );
}
