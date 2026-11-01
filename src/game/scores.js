/* ------------------------------------------------------------------ *
 *  The high-score board, kept on this device (localStorage), and the
 *  settings (names, room, toy mode, height…). Wrapped so a private
 *  window or blocked storage just means nothing is remembered.
 * ------------------------------------------------------------------ */

const KEY = "house-blaster-scores-v1";
const SETTINGS = "house-blaster-settings-v1";

const read = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (_) { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };

export function allScores() { return read(KEY, []); }

/* add a score; returns its place (1 = best) on that room's board, or 0 if it didn't make the top 10 */
export function addScore(entry) {
  const list = allScores();
  const e = { ...entry, date: new Date().toISOString().slice(0, 10), id: Math.random().toString(36).slice(2) };
  list.push(e);
  const room = list.filter(x => x.room === e.room).sort((a, b) => b.score - a.score);
  const keep = new Set(room.slice(0, 10).map(x => x.id));
  const rest = list.filter(x => x.room !== e.room || keep.has(x.id));
  write(KEY, rest);
  const place = room.findIndex(x => x.id === e.id) + 1;
  return place <= 10 ? place : 0;
}

export function topScores(room, n = 5) {
  return allScores().filter(x => !room || x.room === room).sort((a, b) => b.score - a.score).slice(0, n);
}

export function clearScores() { write(KEY, []); }

export const DEFAULT_SETTINGS = {
  players: ["Player 1", "Player 2"], turns: false, room: "living", toy: false, difficulty: "easy",
  heightOffset: 0, seated: false, hand: "right", aimHelp: true, muted: false,
};
export function loadSettings() { return { ...DEFAULT_SETTINGS, ...read(SETTINGS, {}) }; }
export function saveSettings(s) { write(SETTINGS, s); }
