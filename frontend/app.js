/* =====================================================================
   app.js  --  Makes the game come alive.

   The story, in 6 steps:
     1. The page asks the Python backend for a NEW GAME.
     2. You click a rod (pick up its top disk) and another rod (put it down).
     3. We send that move to the backend. The backend is the REFEREE:
        illegal moves are refused with a friendly message (red banner).
     4. If the move is legal, the robot arm performs it (animation).
     5. Stuck? The HINT button asks the backend's COACH for the best next
        move and lights up the two rods involved.
     6. When all disks are on rod C, you win stars!
   ===================================================================== */

// If you open index.html by double-clicking, talk to the local server.
const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

// ---------- Drawing sizes (in canvas pixels) ----------
const CANVAS_W = 900;
const BASE_Y = 400;           // the floor line
const BEAM_Y = 34;            // the rail the arm slides on
const DISK_H = 24;            // how tall each disk is
const PEG_X = [150, 450, 750];
const PEG_NAMES = ["A", "B", "C"];
const COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#14b8a6",
                "#0ea5e9", "#6366f1", "#a855f7", "#ec4899", "#78716c"];
const IDLE_HINT_MS = 25000;   // after this long without a move, the Hint button pulses

// ---------- Shortcuts to page elements ----------
const $ = (id) => document.getElementById(id);
const stageCanvas = $("stage");
const ctx = stageCanvas.getContext("2d");

// ---------- Everything we need to remember ----------
const S = {
  n: 3,                 // number of disks
  pegs: [[], [], []],   // the board we DRAW: each rod is a list, bottom disk first
  game: null,           // the latest game info from the backend ("snapshot")
  selected: null,       // rod the player has clicked (0, 1, 2) or null
  hint: null,           // the hint being shown, or null
  locked: false,        // true while waiting for the server or while the arm is moving
  speed: 2,

  // animation of the arm
  queue: [],            // moves the arm must perform
  qIndex: 0,
  phases: [],           // little steps of the current move
  phaseIdx: 0,
  phaseT: 0,
  playing: false,
  onDone: null,
  onFail: null,

  live: null,           // counters shown while the robot solves the puzzle
  startedAt: null,      // when the first move was made (for the clock)
  lastActivity: Date.now(),
  shake: { rod: -1, until: 0 },
  statusText: "Ready",
};

// The robot arm: x,y is where the claw is. claw: 0 = open, 1 = closed.
const arm = { x: PEG_X[0], y: 0, claw: 0, holding: null, grabW: 56 };

// ---------- Small helper functions ----------
const diskWidth = (size) => 56 + (size - 1) * (144 / Math.max(S.n - 1, 1));
const hoverY = () => BASE_Y - (Math.max(S.n, 4) + 2) * DISK_H - 20;
const rodHeight = () => (Math.max(S.n, 4) + 1) * DISK_H + 20;
const ease = (k) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sameBoard = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const poke = () => { S.lastActivity = Date.now(); $("hintBtn").classList.remove("pulse"); };

function setBanner(text, kind = "info") {
  const el = $("banner");
  el.textContent = text;
  el.className = "banner " + kind;
}

function setStatus(text) {
  S.statusText = text;
  $("statStatus").textContent = text;
}

// Best moves are saved in this browser only (it is just a nice extra).
function loadBest(n) {
  try { return JSON.parse(localStorage.getItem("hanoi_best_" + n)); } catch (e) { return null; }
}
function saveBest(n, moves) {
  try {
    const old = loadBest(n);
    if (!old || moves < old) localStorage.setItem("hanoi_best_" + n, JSON.stringify(moves));
  } catch (e) { /* storage not available: no problem */ }
}

// =====================================================================
// 1) TALKING TO THE BACKEND
// =====================================================================
async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    throw new Error("Cannot reach the backend. Is the server running? Start it with:  uvicorn backend.main:app --reload");
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* no JSON body */ }

  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) {          // FastAPI validation errors come as a list
      msg = msg.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    }
    throw new Error(msg || `Server error (${res.status})`);
  }
  return data;
}

const gamePath = (action) => `/api/game/${S.game.game_id}/${action}`;

// =====================================================================
// 2) SHOWING THE GAME INFO ON THE PAGE
// =====================================================================
function renderHistory(list) {
  const ol = $("history");
  ol.innerHTML = "";
  list.forEach((m) => appendHistory(m));
}

function appendHistory(m) {
  const ol = $("history");
  const old = ol.querySelector(".latest");
  if (old) old.classList.remove("latest");
  const li = document.createElement("li");
  li.className = "latest";
  li.textContent = `Disk ${m.disk}: ${PEG_NAMES[m.from]} → ${PEG_NAMES[m.to]}`;
  ol.appendChild(li);
  ol.scrollTop = ol.scrollHeight;
}

function updateStats() {
  const g = S.game;
  if (!g) return;
  $("statMoves").textContent = g.moves;
  $("statMin").textContent = g.min_moves;
  $("statLeft").textContent = g.moves_remaining;
  $("statHints").textContent = g.hints_used;
  $("statMistakes").textContent = g.mistakes;
  $("statStatus").textContent = S.statusText;
  updateClock();
}

function updateClock() {
  const g = S.game;
  let seconds = 0;
  if (g && g.solved) seconds = g.elapsed_s;
  else if (S.startedAt) seconds = (Date.now() - S.startedAt) / 1000;
  $("statTime").textContent = seconds.toFixed(1) + " s";
}

function syncButtons() {
  const g = S.game;
  const playing = g && !g.solved;
  $("newBtn").disabled = S.locked;
  $("disks").disabled = S.locked;
  $("restartBtn").disabled = S.locked || !g;
  $("hintBtn").disabled = S.locked || !playing;
  $("undoBtn").disabled = S.locked || !(g && g.can_undo);
  $("solveBtn").disabled = S.locked || !playing;
  document.querySelectorAll(".rodbtns button").forEach((b) => {
    b.disabled = S.locked || !g;
    b.classList.toggle("selected", S.selected === Number(b.dataset.rod));
  });
}

// Take what the backend says and make the page match it.
function applySnapshot(snap, { redrawBoard = true } = {}) {
  S.game = snap;
  S.n = snap.disks;
  if (redrawBoard) {
    S.pegs = snap.pegs.map((p) => p.slice());
    renderHistory(snap.history);
  }
  if (snap.moves === 0) S.startedAt = null;
  setStatus(snap.solved ? (snap.assisted ? "Solved by the robot 🤖" : "Solved! 🎉") : "Your turn");
  updateStats();
  syncButtons();
}

function clearHint() {
  S.hint = null;
  $("hintBox").hidden = true;
}

// =====================================================================
// 3) GAME ACTIONS (each one talks to the backend)
// =====================================================================
async function newGame(n) {
  S.locked = true; syncButtons();
  try {
    const snap = await api("/api/game/new", { method: "POST", body: JSON.stringify({ disks: n }) });
    resetArm(snap.disks);
    S.selected = null; clearHint(); S.startedAt = null;
    applySnapshot(snap);
    $("winOverlay").hidden = true;
    const best = loadBest(snap.disks);
    setBanner(`New game with ${snap.disks} disks. You can win in ${snap.min_moves} moves.` +
              (best ? ` Your best so far: ${best}.` : "") + " Pick a rod to begin!", "info");
  } catch (err) {
    setBanner("⚠️ " + err.message, "error");
    setStatus("Error");
  } finally {
    S.locked = false; syncButtons(); poke();
  }
}

async function restartGame() {
  if (!S.game) return;
  S.locked = true; syncButtons();
  try {
    const snap = await api(gamePath("restart"), { method: "POST" });
    resetArm(snap.disks);
    S.selected = null; clearHint(); S.startedAt = null;
    applySnapshot(snap);
    $("winOverlay").hidden = true;
    setBanner("Restarted. All disks are back on rod A.", "info");
  } catch (err) {
    setBanner("⚠️ " + err.message, "error");
  } finally {
    S.locked = false; syncButtons(); poke();
  }
}

// The player picked a rod (by clicking the picture, a button or a key).
function onRod(r) {
  poke();
  if (S.locked || !S.game || S.game.solved) return;

  if (S.selected === null) {
    if (S.pegs[r].length === 0) {
      setBanner(`Rod ${PEG_NAMES[r]} is empty. Pick a rod that has a disk.`, "error");
      flash(r);
      return;
    }
    S.selected = r;
    const disk = S.pegs[r][S.pegs[r].length - 1];
    setBanner(`You picked disk ${disk} from rod ${PEG_NAMES[r]}. Now choose the rod where it should go.`, "info");
    syncButtons();
    return;
  }

  if (S.selected === r) {                       // clicked the same rod again: put it back
    S.selected = null;
    setBanner("Disk put back. Pick a rod to begin a move.", "info");
    syncButtons();
    return;
  }
  makeMove(S.selected, r);
}

async function makeMove(src, dst) {
  S.locked = true; syncButtons();
  try {
    // The backend is the referee. Illegal moves throw an error here.
    const res = await api(gamePath("move"), { method: "POST", body: JSON.stringify({ from: src, to: dst }) });
    S.selected = null;
    clearHint();
    if (!S.startedAt) S.startedAt = Date.now();
    setStatus(`Moving disk ${res.move.disk}…`);
    await playMoves([res.move]);                // the robot arm does the move
    finishWithServer(res.game);
    if (res.game.solved) showWin(res.game);
    else setBanner(`Disk ${res.move.disk} moved to rod ${PEG_NAMES[dst]}. ${res.game.moves_remaining} moves are still needed at best.`, "info");
  } catch (err) {
    S.selected = null;
    setBanner("⚠️ " + err.message, "error");   // e.g. "Not allowed! Disk 3 is bigger than disk 1 ..."
    flash(dst);
    if (S.game) await resyncFromServer();
  } finally {
    S.locked = false; syncButtons(); poke();
  }
}

// After the arm finishes, double-check that our drawing equals the backend's board.
function finishWithServer(snap) {
  if (!sameBoard(S.pegs, snap.pegs)) {
    setBanner("⚠️ The board on screen did not match the backend, so it was reloaded.", "error");
    S.pegs = snap.pegs.map((p) => p.slice());
  }
  applySnapshot(snap, { redrawBoard: false });
  renderHistory(snap.history);
}

async function resyncFromServer() {
  try {
    const snap = await api(`/api/game/${S.game.game_id}`);
    resetArm(snap.disks, false);
    applySnapshot(snap);
  } catch (e) { /* the banner already shows the first problem */ }
}

async function onHint() {
  poke();
  if (S.locked || !S.game || S.game.solved) return;
  S.locked = true; syncButtons();
  try {
    const res = await api(gamePath("hint"), { method: "POST" });
    S.selected = null;
    S.hint = res.hint;
    applySnapshot(res.game, { redrawBoard: false });
    $("hintBox").hidden = false;
    $("hintBox").textContent = "💡 " + res.hint.message;
    setBanner(`Hint: move disk ${res.hint.disk} from rod ${res.hint.from_name} to rod ${res.hint.to_name}. ` +
              "The two rods are lit up. Now make the move yourself!", "hint");
  } catch (err) {
    setBanner("⚠️ " + err.message, "error");
  } finally {
    S.locked = false; syncButtons();
  }
}

async function onUndo() {
  poke();
  if (S.locked || !S.game) return;
  S.locked = true; syncButtons();
  try {
    const res = await api(gamePath("undo"), { method: "POST" });
    S.selected = null; clearHint();
    resetArm(res.game.disks, false);
    applySnapshot(res.game);
    setBanner(`Undid the move of disk ${res.undone.disk}. (It still counts as a move you made.)`, "info");
  } catch (err) {
    setBanner("⚠️ " + err.message, "error");
  } finally {
    S.locked = false; syncButtons();
  }
}

// "Robot solves it": the backend finishes the puzzle and the arm shows how.
async function onSolve() {
  poke();
  if (S.locked || !S.game || S.game.solved) return;
  if (!window.confirm("Let the robot finish the puzzle? You will not earn stars for this game.")) return;
  S.locked = true; syncButtons();
  try {
    const res = await api(gamePath("solve"), { method: "POST" });
    S.selected = null; clearHint();
    setBanner(`The robot is finishing the puzzle in ${res.moves.length} moves…`, "info");
    setStatus("Robot at work 🤖");
    S.live = { moves: S.game.moves, left: S.game.moves_remaining };
    try { await playMoves(res.moves); } finally { S.live = null; }
    finishWithServer(res.game);
    setBanner(`The robot solved it. Press New game to try again yourself!`, "success");
  } catch (err) {
    setBanner("⚠️ " + err.message, "error");
    if (S.game) await resyncFromServer();
  } finally {
    S.locked = false; syncButtons();
  }
}

function showWin(g) {
  const stars = g.stars || 1;
  $("winStars").innerHTML = [1, 2, 3].map((i) => `<span class="${i <= stars ? "" : "off"}">★</span>`).join("");
  const perfect = g.moves === g.min_moves;
  let text = `You moved all ${g.disks} disks in ${g.moves} moves (best possible: ${g.min_moves}) in ${g.elapsed_s.toFixed(1)} s.` +
             ` Hints used: ${g.hints_used}. Mistakes: ${g.mistakes}.`;
  if (perfect && g.hints_used === 0) text += " Perfect game!";
  else if (perfect) text += " Perfect moves, but hints were used, so you lost a star.";
  const before = loadBest(g.disks);
  saveBest(g.disks, g.moves);
  if (!before || g.moves < before) text += " That is your new best for this level!";
  $("winText").textContent = text;
  $("nextBtn").hidden = g.disks >= 10;
  $("winOverlay").hidden = false;
  setBanner(`Solved with ${"★".repeat(stars)}${"☆".repeat(3 - stars)}!`, "success");
}

// =====================================================================
// 4) THE ROBOT ARM ANIMATION
//    Each move is cut into 8 small steps ("phases"):
//      go above source -> go down -> grab -> go up
//      -> slide across -> go down -> let go -> go up
// =====================================================================
function resetArm(n, resetBoard = true) {
  S.n = n;
  S.queue = []; S.qIndex = 0; S.phases = []; S.phaseIdx = 0; S.phaseT = 0; S.playing = false;
  arm.x = PEG_X[0];
  arm.y = hoverY();
  arm.claw = 0;
  arm.holding = null;
  if (resetBoard) S.pegs = [Array.from({ length: n }, (_, i) => n - i), [], []];
}

// Ask the arm to perform a list of moves. The promise finishes when it is done.
function playMoves(moves) {
  return new Promise((resolve, reject) => {
    S.queue = moves;
    S.qIndex = 0;
    S.phases = [];
    S.phaseIdx = 0;
    S.phaseT = 0;
    S.onDone = resolve;
    S.onFail = reject;
    S.playing = true;
  });
}

function failRun(message) {
  S.playing = false;
  S.queue = [];
  arm.holding = null;
  const fail = S.onFail;
  S.onDone = S.onFail = null;
  if (fail) fail(new Error(message));
}

function finishRun() {
  S.playing = false;
  const done = S.onDone;
  S.onDone = S.onFail = null;
  if (done) done();
}

function buildPhases(m) {
  const from = m.from, to = m.to;
  return [
    { dur: 0.30, to: () => ({ x: PEG_X[from], y: hoverY(), claw: 0 }) },
    {
      dur: 0.25,
      start: () => {
        const src = S.pegs[from];
        if (src.length === 0) return `Rod ${PEG_NAMES[from]} is empty, so there is nothing to pick up.`;
        if (src[src.length - 1] !== m.disk) return `Disk ${m.disk} is not on top of rod ${PEG_NAMES[from]}.`;
        arm.grabW = diskWidth(m.disk);
        return null;
      },
      to: () => ({ y: BASE_Y - S.pegs[from].length * DISK_H }),
    },
    {
      dur: 0.12,
      to: () => ({ claw: 1 }),
      end: () => { arm.holding = S.pegs[from].pop(); },
    },
    { dur: 0.25, to: () => ({ y: hoverY() }) },
    { dur: 0.40, to: () => ({ x: PEG_X[to] }) },
    {
      dur: 0.25,
      start: () => {
        const dst = S.pegs[to];
        if (dst.length && dst[dst.length - 1] < arm.holding) {
          return `Not allowed! Disk ${arm.holding} cannot go on smaller disk ${dst[dst.length - 1]}.`;
        }
        return null;
      },
      to: () => ({ y: BASE_Y - (S.pegs[to].length + 1) * DISK_H }),
    },
    {
      dur: 0.12,
      to: () => ({ claw: 0 }),
      end: () => {
        S.pegs[to].push(arm.holding);
        arm.holding = null;
        S.qIndex++;
        appendHistory(m);
        if (S.live) {                       // robot solving: keep the counters ticking
          $("statMoves").textContent = S.live.moves + S.qIndex;
          $("statLeft").textContent = Math.max(0, S.live.left - S.qIndex);
        }
      },
    },
    { dur: 0.20, to: () => ({ y: hoverY() }) },
  ];
}

// Move the animation forward by dt seconds.
function advance(dt) {
  let left = dt;
  while (left > 0 && S.playing) {
    if (S.phases.length === 0 || S.phaseIdx >= S.phases.length) {
      if (S.qIndex >= S.queue.length) { finishRun(); return; }   // nothing left to do
      S.phases = buildPhases(S.queue[S.qIndex]);
      S.phaseIdx = 0;
      S.phaseT = 0;
    }
    const p = S.phases[S.phaseIdx];

    if (!p.started) {                       // first time we touch this step
      p.started = true;
      if (p.start) {
        const problem = p.start();
        if (problem) { failRun(problem); return; }
      }
      p.from = { x: arm.x, y: arm.y, claw: arm.claw };
      p.target = { ...p.from, ...p.to() };
    }

    const use = Math.min(p.dur - S.phaseT, left);
    S.phaseT += use;
    left -= use;

    const k = ease(Math.min(S.phaseT / p.dur, 1));
    for (const key of ["x", "y", "claw"]) {
      arm[key] = p.from[key] + (p.target[key] - p.from[key]) * k;
    }

    if (S.phaseT >= p.dur - 1e-9) {          // step finished
      if (p.end) p.end();
      S.phaseIdx++;
      S.phaseT = 0;
    }
  }
}

// =====================================================================
// 5) DRAWING
// =====================================================================
function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawDisk(cx, topY, size, glow) {
  const w = diskWidth(size);
  const color = COLORS[(size - 1) % COLORS.length];
  roundRect(cx - w / 2, topY + 1, w, DISK_H - 2, 7);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.lineWidth = glow ? 4 : 2;
  ctx.strokeStyle = glow || "rgba(0,0,0,0.35)";
  ctx.stroke();
  ctx.fillStyle = "#fff";
  ctx.font = "bold 13px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(size), cx, topY + DISK_H / 2 + 1);
}

function drawColumn(rod, fill, stroke, dashed) {
  const top = BEAM_Y + 24, h = BASE_Y - top;
  roundRect(PEG_X[rod] - 98, top, 196, h, 14);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke) {
    ctx.setLineDash(dashed ? [10, 7] : []);
    ctx.lineWidth = 3;
    ctx.strokeStyle = stroke;
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function draw() {
  const now = performance.now();
  const pulse = 0.5 + 0.5 * Math.sin(now / 230);
  ctx.clearRect(0, 0, CANVAS_W, stageCanvas.height);

  // background
  const bg = ctx.createLinearGradient(0, 0, 0, stageCanvas.height);
  bg.addColorStop(0, "#eef2ff");
  bg.addColorStop(1, "#f8fafc");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, CANVAS_W, stageCanvas.height);

  // lit-up columns: hint (green), selected (blue), mistake flash (red)
  if (S.hint) {
    drawColumn(S.hint.from, `rgba(34,197,94,${0.12 + 0.12 * pulse})`, "#16a34a", false);
    drawColumn(S.hint.to, `rgba(34,197,94,${0.06 + 0.1 * pulse})`, "#16a34a", true);
  }
  if (S.selected !== null) drawColumn(S.selected, "rgba(79,70,229,0.12)", "#4f46e5", false);
  if (S.shake.rod >= 0 && now < S.shake.until) drawColumn(S.shake.rod, "rgba(239,68,68,0.22)", "#dc2626", false);

  // floor
  roundRect(40, BASE_Y, 820, 16, 6);
  ctx.fillStyle = "#475569";
  ctx.fill();

  // rods + labels
  const rh = rodHeight();
  PEG_X.forEach((x, i) => {
    roundRect(x - 5, BASE_Y - rh, 10, rh, 4);
    ctx.fillStyle = "#94a3b8";
    ctx.fill();
    ctx.fillStyle = "#334155";
    ctx.font = "bold 18px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(PEG_NAMES[i], x, BASE_Y + 38);
  });

  // disks resting on rods (the top disk of the picked rod is lifted a little)
  S.pegs.forEach((stack, p) => {
    stack.forEach((size, i) => {
      const isTop = i === stack.length - 1;
      const lifted = isTop && S.selected === p && !S.playing;
      const hinted = isTop && S.hint && S.hint.from === p && !S.playing;
      const y = BASE_Y - (i + 1) * DISK_H - (lifted ? 22 : 0);
      drawDisk(PEG_X[p], y, size, lifted ? "#4f46e5" : hinted ? "#16a34a" : null);
    });
  });

  // top rail
  roundRect(40, BEAM_Y - 8, 820, 16, 6);
  ctx.fillStyle = "#334155";
  ctx.fill();

  // carriage (the box that slides on the rail)
  roundRect(arm.x - 30, BEAM_Y - 15, 60, 30, 8);
  ctx.fillStyle = "#4f46e5";
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.beginPath();
  ctx.arc(arm.x, BEAM_Y, 5, 0, Math.PI * 2);
  ctx.fill();

  // arm (the long vertical rod)
  ctx.fillStyle = "#64748b";
  ctx.fillRect(arm.x - 4, BEAM_Y + 12, 8, Math.max(0, arm.y - 16 - (BEAM_Y + 12)));

  // disk being carried (drawn before the fingers so it looks gripped)
  if (arm.holding) drawDisk(arm.x, arm.y, arm.holding);

  // claw: a hand and two fingers
  const open = arm.grabW / 2 + 26;
  const closed = arm.grabW / 2 + 3;
  const gap = open + (closed - open) * arm.claw;
  ctx.fillStyle = "#1e293b";
  roundRect(arm.x - gap - 6, arm.y - 16, gap * 2 + 12, 12, 4);
  ctx.fill();
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(arm.x - gap - 6, arm.y - 8, 6, DISK_H - 2);   // left finger
  ctx.fillRect(arm.x + gap, arm.y - 8, 6, DISK_H - 2);       // right finger

  // hint arrow label above the target rod
  if (S.hint && !S.playing) {
    ctx.fillStyle = "#15803d";
    ctx.font = "bold 16px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(`💡 ${PEG_NAMES[S.hint.from]} → ${PEG_NAMES[S.hint.to]}`, PEG_X[S.hint.to], BEAM_Y + 52);
  }
}

function flash(rod) {
  S.shake = { rod, until: performance.now() + 700 };
}

// =====================================================================
// 6) THE LOOP THAT RUNS ~60 TIMES PER SECOND
// =====================================================================
let lastTime = performance.now();
function frame(now) {
  const realDt = Math.min((now - lastTime) / 1000, 0.1);
  lastTime = now;
  if (S.playing) advance(realDt * S.speed);
  draw();
  requestAnimationFrame(frame);
}

// A clock that ticks, and a gentle nudge when you have been idle for a while.
setInterval(() => {
  if (S.game && !S.game.solved && S.startedAt) updateClock();
  const g = S.game;
  if (g && !g.solved && !S.locked && !S.hint && Date.now() - S.lastActivity > IDLE_HINT_MS) {
    $("hintBtn").classList.add("pulse");
  }
}, 250);

// =====================================================================
// 7) THE ALGORITHM LAB (compare recursive vs iterative)
// =====================================================================
async function onCompare() {
  const n = parseInt($("disks").value, 10);
  const box = $("compareResult");
  box.textContent = "Racing the algorithms…";
  try {
    const d = await api("/api/compare", { method: "POST", body: JSON.stringify({ disks: n, repeats: 5 }) });
    const r = d.results.recursive, i = d.results.iterative;
    const win = (name) => (d.faster === name ? ' class="winner"' : "");
    box.innerHTML = `
      <table>
        <tr><th>${n} disks</th><th>Recursive</th><th>Iterative</th></tr>
        <tr><td>Moves</td><td>${r.total_moves}</td><td>${i.total_moves}</td></tr>
        <tr><td>Time (ms)</td><td${win("recursive")}>${r.execution_time_ms.toFixed(4)}</td><td${win("iterative")}>${i.execution_time_ms.toFixed(4)}</td></tr>
        <tr><td>Minimum reached (2ⁿ − 1 = ${d.min_moves})</td><td>${r.is_minimum ? "✔" : "✘"}</td><td>${i.is_minimum ? "✔" : "✘"}</td></tr>
      </table>
      <p>Both produce the same moves: <b>${d.same_moves ? "yes ✔" : "no ✘"}</b>. Faster this time: <b>${esc(d.faster)}</b> (best of ${d.repeats} tries).</p>`;
  } catch (err) {
    box.innerHTML = `<div class="banner error">⚠️ ${esc(err.message)}</div>`;
  }
}

async function onChart() {
  const canvas = $("chart");
  try {
    const d = await api("/api/compare/series?max_disks=14&repeats=3");
    canvas.hidden = false;
    drawChart(canvas, d.points);
  } catch (err) {
    $("compareResult").innerHTML = `<div class="banner error">⚠️ ${esc(err.message)}</div>`;
  }
}

function drawChart(canvas, points) {
  const c = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const L = 70, R = 20, T = 30, B = 50;
  c.clearRect(0, 0, W, H);
  c.fillStyle = "#fff";
  c.fillRect(0, 0, W, H);

  const maxY = Math.max(...points.map((p) => Math.max(p.recursive_ms, p.iterative_ms))) * 1.1 || 1;
  const xAt = (i) => L + (i / (points.length - 1)) * (W - L - R);
  const yAt = (v) => H - B - (v / maxY) * (H - T - B);

  c.font = "12px system-ui, sans-serif";
  c.fillStyle = "#475569";
  c.strokeStyle = "#e5e7eb";
  c.lineWidth = 1;
  c.textAlign = "right";
  c.textBaseline = "middle";
  for (let t = 0; t <= 5; t++) {            // horizontal grid + y labels
    const v = (maxY * t) / 5, y = yAt(v);
    c.beginPath(); c.moveTo(L, y); c.lineTo(W - R, y); c.stroke();
    c.fillText(v < 1 ? v.toFixed(3) : v.toFixed(1), L - 8, y);
  }
  c.textAlign = "center";
  c.textBaseline = "top";
  points.forEach((p, i) => c.fillText(String(p.disks), xAt(i), H - B + 8));
  c.fillText("number of disks", (L + W - R) / 2, H - 22);
  c.save();
  c.translate(18, (T + H - B) / 2);
  c.rotate(-Math.PI / 2);
  c.fillText("time (ms)", 0, 0);
  c.restore();

  const line = (key, color) => {
    c.strokeStyle = color; c.fillStyle = color; c.lineWidth = 3;
    c.beginPath();
    points.forEach((p, i) => (i ? c.lineTo(xAt(i), yAt(p[key])) : c.moveTo(xAt(i), yAt(p[key]))));
    c.stroke();
    points.forEach((p, i) => { c.beginPath(); c.arc(xAt(i), yAt(p[key]), 4, 0, Math.PI * 2); c.fill(); });
  };
  line("recursive_ms", "#4f46e5");
  line("iterative_ms", "#ea580c");

  c.textAlign = "left"; c.textBaseline = "middle";
  c.fillStyle = "#4f46e5"; c.fillRect(L + 10, 12, 18, 4); c.fillText("Recursive", L + 34, 14);
  c.fillStyle = "#ea580c"; c.fillRect(L + 120, 12, 18, 4); c.fillText("Iterative", L + 144, 14);
}

// =====================================================================
// 8) WIRE EVERYTHING UP
// =====================================================================
$("newBtn").addEventListener("click", () => newGame(parseInt($("disks").value, 10)));
$("restartBtn").addEventListener("click", restartGame);
$("hintBtn").addEventListener("click", onHint);
$("undoBtn").addEventListener("click", onUndo);
$("solveBtn").addEventListener("click", onSolve);
$("compareBtn").addEventListener("click", onCompare);
$("chartBtn").addEventListener("click", onChart);

document.querySelectorAll(".rodbtns button").forEach((b) =>
  b.addEventListener("click", () => onRod(Number(b.dataset.rod))));

// Click on the picture: the closest rod is the one you meant.
stageCanvas.addEventListener("click", (e) => {
  const rect = stageCanvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) * CANVAS_W) / rect.width;
  const rod = PEG_X.reduce((best, px, i) => (Math.abs(px - x) < Math.abs(PEG_X[best] - x) ? i : best), 0);
  onRod(rod);
});

// Keyboard: 1 2 3 (or a b c) pick a rod, h = hint, u = undo
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "select" || tag === "input") return;
  const k = e.key.toLowerCase();
  if (["1", "2", "3"].includes(k)) onRod(Number(k) - 1);
  else if (["a", "b", "c"].includes(k)) onRod("abc".indexOf(k));
  else if (k === "h") onHint();
  else if (k === "u") onUndo();
});

$("speed").addEventListener("input", (e) => {
  S.speed = parseFloat(e.target.value);
  $("speedLabel").textContent = S.speed + "x";
});

$("againBtn").addEventListener("click", () => newGame(S.n));
$("nextBtn").addEventListener("click", () => {
  const next = Math.min(10, S.n + 1);
  $("disks").value = String(next);
  newGame(next);
});
$("closeBtn").addEventListener("click", () => { $("winOverlay").hidden = true; });

// Start up: draw an empty board, then ask the backend for the first game.
resetArm(3);
syncButtons();
requestAnimationFrame(frame);
newGame(3);
