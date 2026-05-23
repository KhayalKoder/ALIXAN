import { motion } from "framer-motion";
import { avatarUrl } from "../lib/avatars";
import { PlayingCard } from "./PlayingCard";

// Seat positions for a 5-seat oval table (relative percentages within the canvas overlay).
// Seat 0 is at the bottom (the player), then clockwise from there.
export const SEAT_POSITIONS = [
  { left: "50%", top: "68%", anchor: "bottom" },  // 0 - hero
  { left: "10%", top: "55%", anchor: "left" },    // 1
  { left: "22%", top: "20%", anchor: "topleft" }, // 2
  { left: "78%", top: "20%", anchor: "topright" },// 3
  { left: "90%", top: "55%", anchor: "right" },   // 4
];

export default function PlayerSeat({ seatIdx, player, isAction, isDealer, timeLeft, isYou }) {
  const pos = SEAT_POSITIONS[seatIdx];
  if (!player) {
    return (
      <div
        className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
        style={{ left: pos.left, top: pos.top }}
        data-testid={`seat-empty-${seatIdx}`}
      >
        <div className="w-20 h-20 md:w-24 md:h-24 rounded-full border-2 border-dashed border-white/15 flex items-center justify-center bg-black/40">
          <div className="text-[9px] uppercase tracking-[0.3em] text-zinc-500">Open</div>
        </div>
      </div>
    );
  }
  const ringSize = 96; // px
  const circumference = 2 * Math.PI * 44;
  const dashOffset = isAction ? circumference * (1 - timeLeft / 30) : 0;
  const urgent = isAction && timeLeft <= 5;

  return (
    <motion.div
      key={`${seatIdx}-${player.user_id}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
      style={{ left: pos.left, top: pos.top }}
      data-testid={`seat-${seatIdx}`}
    >
      {/* Hole cards above for top seats, below for bottom seats */}
      {(seatIdx === 2 || seatIdx === 3) && player.has_cards && (
        <div className="flex gap-1 mb-1">
          {player.hole_cards
            ? player.hole_cards.map((c, i) => <PlayingCard key={i} card={c} small />)
            : [0, 1].map((i) => <PlayingCard key={i} hidden small />)}
        </div>
      )}

      <div className="relative">
        {/* Timer ring */}
        <svg width={ringSize} height={ringSize} className="absolute inset-0" style={{ transform: "rotate(-90deg)" }}>
          <circle
            cx={ringSize / 2}
            cy={ringSize / 2}
            r={44}
            stroke={isAction ? (urgent ? "#dc2626" : "#D4AF37") : "rgba(255,255,255,0.1)"}
            strokeWidth="3"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            style={{ transition: isAction ? "stroke-dashoffset 1s linear, stroke 0.3s" : "stroke 0.3s" }}
          />
        </svg>
        {/* Avatar */}
        <div
          className={`relative overflow-hidden rounded-full border-2 ${
            isYou ? "border-[#D4AF37]" : isAction ? (urgent ? "border-red-500" : "border-[#D4AF37]") : "border-white/20"
          }`}
          style={{ width: ringSize - 8, height: ringSize - 8, margin: 4 }}
        >
          <img src={avatarUrl(player.avatar_id)} alt={player.username} className="w-full h-full object-cover" />
          {player.folded && (
            <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
              <div className="text-[9px] uppercase tracking-[0.2em] text-zinc-300">Fold</div>
            </div>
          )}
        </div>
        {/* Dealer button */}
        {isDealer && (
          <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-white text-black text-[10px] font-bold flex items-center justify-center border border-black/30">
            D
          </div>
        )}
      </div>

      {/* Name + chips */}
      <div className="mt-1.5 px-2 py-1 bg-black/70 backdrop-blur border border-white/10 text-center min-w-[90px]">
        <div className="text-[11px] font-sans truncate max-w-[100px]">
          {player.username}{player.is_bot && <span className="text-zinc-500 text-[9px] ml-1">·BOT</span>}
        </div>
        <div className="text-[10px] font-mono text-[#D4AF37]">${player.chips.toFixed(2)}</div>
      </div>

      {/* Current bet chip */}
      {player.bet > 0 && (
        <div className="mt-1 px-2 py-0.5 bg-[#D4AF37] text-black text-[10px] font-mono font-bold rounded-full">
          ${player.bet.toFixed(2)}
        </div>
      )}

      {/* Cards for bottom seats (seats 0, 1, 4) */}
      {(seatIdx === 0 || seatIdx === 1 || seatIdx === 4) && player.has_cards && (
        <div className="flex gap-1 mt-1">
          {player.hole_cards
            ? player.hole_cards.map((c, i) => <PlayingCard key={i} card={c} small />)
            : [0, 1].map((i) => <PlayingCard key={i} hidden small />)}
        </div>
      )}
    </motion.div>
  );
}
