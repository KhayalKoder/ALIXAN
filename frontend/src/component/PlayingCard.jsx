// Playing card visual using CSS (face values rendered cleanly).
const SUIT_SYMBOL = { s: "\u2660", h: "\u2665", d: "\u2666", c: "\u2663" };
const SUIT_COLOR = { s: "#0a0a0c", h: "#7a1717", d: "#7a1717", c: "#0a0a0c" };

export function PlayingCard({ card, hidden, small }) {
  if (hidden || !card) {
    return (
      <div
        className={`relative ${small ? "w-9 h-12" : "w-14 h-20"} rounded-sm border border-[#D4AF37]/40 shadow-lg`}
        style={{
          background: "linear-gradient(135deg, #7a1717 0%, #4a0e0e 60%, #2a0808 100%)",
        }}
      >
        <div className="absolute inset-1 border border-[#D4AF37]/30 rounded-sm flex items-center justify-center">
          <div className="text-[#D4AF37] font-serif italic text-xs opacity-60">MR</div>
        </div>
      </div>
    );
  }
  const rank = card[0] === "T" ? "10" : card[0];
  const suit = card[1];
  return (
    <div
      className={`relative ${small ? "w-9 h-12" : "w-14 h-20"} bg-[#FAF7F0] rounded-sm shadow-xl flex flex-col justify-between p-1`}
      style={{ boxShadow: "0 6px 16px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(0,0,0,0.06)" }}
    >
      <div className="flex flex-col items-start leading-none" style={{ color: SUIT_COLOR[suit] }}>
        <div className={small ? "text-xs font-bold" : "text-base font-bold"}>{rank}</div>
        <div className={small ? "text-xs" : "text-sm"}>{SUIT_SYMBOL[suit]}</div>
      </div>
      <div
        className={`self-end leading-none rotate-180`}
        style={{ color: SUIT_COLOR[suit] }}
      >
        <div className={small ? "text-xs font-bold" : "text-sm font-bold"}>{rank}{SUIT_SYMBOL[suit]}</div>
      </div>
    </div>
  );
}
