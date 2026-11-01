/* ------------------------------------------------------------------ *
 *  The rooms you can play in. Each level names the house's rooms (by
 *  the elements file's room names) it uses, any extra rectangles for
 *  spots (the stairs, the front garden), where you start and which way
 *  you face (a point to look at), and how fast it plays.
 * ------------------------------------------------------------------ */

export const LEVELS = [
  { id: "hall", name: "Hall", emoji: "🚪", rooms: ["hall", "cpd (under stairs)"],
    extra: [{ poly: [[3.69, -1.9], [5.48, -1.9], [5.48, -4.36], [3.69, -4.36]], floor: 0, storey: "ground", climb: true }],
    start: [4.3, 0, -0.75], look: [4.3, 1.2, -4], speed: 0.9 },
  { id: "living", name: "Living room", emoji: "🛋️", rooms: ["living", "conservatory (uPVC, polycarbonate roof)"],
    start: [2.95, 0, -1.75], look: [0.6, 0.8, -3.4], speed: 1.0 },
  { id: "kitchen", name: "Kitchen", emoji: "🍳", rooms: ["kitchen"],
    start: [6.05, 0, -1.75], look: [8.0, 1.0, -4.8], speed: 1.05 },
  { id: "upstairs", name: "Upstairs", emoji: "🛏️", rooms: ["hall / landing", "bedroom 1 (front left)", "bedroom 2 (front bay)", "bedroom 3 (rear wing)", "bathroom", "cpd"],
    start: [4.6, 2.6755, -1.75], look: [7.5, 3.6, -1.8], speed: 1.1 },
  { id: "garden", name: "Front garden", emoji: "🌳", rooms: [],
    extra: [{ poly: [[-0.6, 0.15], [9.6, 0.15], [9.6, 9.5], [-0.6, 9.5]], floor: -0.25, storey: "site", outside: true }],
    start: [4.3, -0.25, 7.2], look: [4.3, 1.4, 0], speed: 1.1, far: 11 },
  { id: "house", name: "Whole house", emoji: "🏠", rooms: ["hall", "living", "kitchen", "sitting", "conservatory (uPVC, polycarbonate roof)", "hall / landing", "bedroom 1 (front left)", "bedroom 2 (front bay)", "bedroom 3 (rear wing)", "bathroom"],
    extra: [{ poly: [[3.69, -1.9], [5.48, -1.9], [5.48, -4.36], [3.69, -4.36]], floor: 0, storey: "ground", climb: true }],
    start: [4.3, 0, -0.75], look: [4.3, 1.2, -4], speed: 1.15 },
];

export const DIFFICULTY = {
  easy: { label: "Easy", interval: [1.7, 1.0], life: [6.5, 4.2], max: [3, 5], assist: 1.6 },
  normal: { label: "Normal", interval: [1.4, 0.7], life: [5.2, 3.0], max: [3, 6], assist: 1.3 },
  hard: { label: "Hard", interval: [1.1, 0.45], life: [4.0, 2.2], max: [4, 8], assist: 1.1 },
};

export const POINTS = { balloon: 10, disc: 15, robot: 25, star: 50 };
export const ROUND_SECONDS = 60;
