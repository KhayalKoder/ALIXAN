// Avatar mapping. Uses generated luxury avatars from design guidelines + procedural fallbacks.
const AVATAR_BASE = "https://api.dicebear.com/9.x/personas/svg";

export const AVATARS = [
  { id: "man1", name: "Lord Ashford", url: `${AVATAR_BASE}?seed=Lord%20Ashford&backgroundColor=1c1c22` },
  { id: "man2", name: "Vincenzo", url: `${AVATAR_BASE}?seed=Vincenzo&backgroundColor=2a1a1a` },
  { id: "man3", name: "Kazimir", url: `${AVATAR_BASE}?seed=Kazimir&backgroundColor=1a1a2a` },
  { id: "woman1", name: "Vivienne", url: `${AVATAR_BASE}?seed=Vivienne&backgroundColor=2a1a2a` },
  { id: "woman2", name: "Anastasia", url: `${AVATAR_BASE}?seed=Anastasia&backgroundColor=1a2a2a` },
  { id: "woman3", name: "Isolde", url: `${AVATAR_BASE}?seed=Isolde&backgroundColor=2a2a1a` },
];

export function avatarUrl(id) {
  return (AVATARS.find((a) => a.id === id) || AVATARS[0]).url;
}

export function avatarName(id) {
  return (AVATARS.find((a) => a.id === id) || AVATARS[0]).name;
}
