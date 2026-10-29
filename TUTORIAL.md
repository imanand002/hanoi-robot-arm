# 🧸 Build it step by step (explained like you are five)

Go in order. After each step there is a **✅ Check** so you know it works before moving on.
The finished code for every file is in this folder. Type it yourself, or open the file and read along.

---

## Step 0 — The story

Imagine 3 sticks and a pile of pancakes (biggest at the bottom). You must move the whole pile to the last stick.

- Move **one** pancake at a time.
- Only grab the **top** pancake.
- **Never** put a big pancake on a small one.

Our project is a **game** with two parts:

- 🧠 **Backend (Python)** = a clever friend who figures out the moves.
- 🎨 **Frontend (web page)** = a toy robot arm that does the moves.

They talk through a **phone line** called an **API**.

---

## Step 1 — Make a home for the project

1. Make a folder `hanoi-robot-arm`, open it in VS Code.
2. Inside, make folders: `backend`, `frontend`, `tests`, `scripts`, `docs`.
3. Make an empty file `backend/__init__.py` (it tells Python "this folder is a toolbox").
4. Make `requirements.txt` (the shopping list of tools) and run:
   `python -m venv .venv` → activate it → `pip install -r requirements.txt`

✅ Check: `pip list` shows `fastapi` and `uvicorn`.

---

## Step 2 — Teach the brain to solve it (`backend/algorithms.py`)

**Recursive** = "ask a smaller helper". To move 3 pancakes:
1. Ask a helper to move the top 2 out of the way.
2. Move the big one yourself.
3. Ask the helper to put the 2 back on top.

The helper does the same trick with 1 pancake. Once there are 0 pancakes, there's nothing to do, so we stop.

**Iterative** = "follow a dance pattern with a loop". Repeat 2ⁿ−1 times: small disk dance → legal move → legal move → ...

**2ⁿ − 1** = how many moves at minimum. 3 disks → 2×2×2 − 1 = **7**.

Also add a **stopwatch** (`time.perf_counter()`) around the solver.

✅ Check — in the terminal:
```
python -c "from backend.algorithms import solve_recursive; print(len(solve_recursive(3)))"
```
It prints `7`.

---

## Step 3 — Hire a referee (`backend/validator.py`)

The referee replays every move on a pretend board and shouts if:
- the rod is empty,
- the disk is not on top,
- a big disk lands on a small one.

✅ Check:
```
python -c "from backend.validator import validate_solution; from backend.algorithms import solve_iterative; validate_solution(4, solve_iterative(4)); print('referee is happy')"
```

---

## Step 4 — The helper in the middle (`backend/service.py`)

It remembers simulations (start, reset), races both algorithms (compare), and turns problems into friendly messages. No web stuff here, so it is easy to test.

✅ Check: run `pytest -q`. All green means the brain is good.

---

## Step 5 — Open the phone line (`backend/main.py`)

FastAPI lets us write a tiny function and turn it into a web address:

```python
@app.get("/api/health")
def health():
    return {"status": "ok"}
```

Our menu: `start`, `reset`, `compare`, `compare/series`, `validate`.

✅ Check: run `uvicorn backend.main:app --reload`, then open
http://127.0.0.1:8000/api/health → you see `{"status":"ok"}`.
Open http://127.0.0.1:8000/docs → try the buttons there (try disks = 99 to see a friendly error).

---

## Step 6 — Draw the page (`frontend/index.html` + `style.css`)

- `index.html` = the **skeleton**: buttons, dropdowns, a `<canvas>` (a drawing board).
- `style.css` = the **clothes**: colors and spacing.

✅ Check: open http://127.0.0.1:8000 → you see controls and an empty board.

---

## Step 7 — Bring the robot to life (`frontend/app.js`)

Read it in this order:

1. **`api()`** — the phone. Calls the backend; if it's off, shows a red message.
2. **`checkMovesLocally()`** — a second referee in the browser.
3. **`initBoard()`** — puts all disks on rod A.
4. **`draw()`** — paints rods, disks, rail, arm and claw 60 times a second.
5. **`buildPhases()`** — each move is 8 tiny steps:
   `go above → down → grab → up → slide → down → let go → up`.
6. **`advance(dt)`** — moves the animation forward a little each frame. Pause just stops calling it. Speed just makes `dt` bigger.
7. **Buttons** — Start asks the backend, checks the answer, then runs the animation.

✅ Check: press **Start** with 3 disks → 7 moves, ends with "Solved! 🎉".

---

## Step 8 — Race them! (Compare + graph)

- **Compare** button → `/api/compare` → a table of times.
- **Draw speed chart** → `/api/compare/series` → a line graph.
- `python scripts/benchmark.py` → saves `docs/performance.png`.

---

## Step 9 — Try to break it (that's how you learn)

- Stop the server and press Start → red "Cannot reach the backend".
- In `/docs`, send disks = 0 → friendly error.
- Change `algorithms.py` on purpose to make a bad move → the referee catches it.

---

# 🎮 PART 2 — Turn it into a GAME (with hints!)

Same project, same folders. Now a **person** plays and the computer is the **referee** (checks rules) and the **coach** (gives hints).

## Step 10 — The coach (`backend/hints.py`)

The player might wander off the textbook plan, so we cannot just replay a stored list. Instead the coach looks at the board **right now** and thinks:

1. Find the **biggest disk that is not on rod C yet** (call it k).
2. To move k to C, all smaller disks must first hop onto the **third rod** (not where k is, not C).
3. So the best next move is the first move of "get the smaller disks out of the way". If they are already there, move disk k.

That is the whole trick: `next_move(pegs)`. Another function, `moves_remaining(pegs)`, counts how many moves are still needed at best.

✅ Check:
```
python -c "from backend.hints import next_move; print(next_move([[3,2,1],[],[]]))"
```
It prints `{'disk': 1, 'from': 0, 'to': 2}`.

## Step 11 — A one-move referee (`check_move` in `backend/validator.py`)

Before, we checked a whole list. A game needs to check **one** move and explain why not: empty rod, same rod twice, or big-on-small.

✅ Check: `python -c "from backend.validator import check_move; print(check_move([[3,2],[1],[]], 0, 1))"` prints the "Not allowed!" message.

## Step 12 — One game (`backend/game.py`)

A `Game` remembers the rods, moves made, hints used, mistakes, undos and the clock. Its jobs: `apply_move`, `undo`, `hint`, `solve_for_player`, `restart`, `stars`.

Stars: **3** = fewest moves possible and no hints · **2** = close (≤ 1.5× the best) or perfect but hints used · **1** = solved.

## Step 13 — New phone numbers (API) in `service.py` and `main.py`

| Phone number | What it does |
|---|---|
| `POST /api/game/new` | start a game |
| `POST /api/game/{id}/move` | try a move (illegal → red message) |
| `POST /api/game/{id}/hint` | ask the coach |
| `POST /api/game/{id}/undo` | take the last move back |
| `POST /api/game/{id}/restart` | start over |
| `POST /api/game/{id}/solve` | robot finishes it (no stars) |
| `GET /api/game/{id}` | look at the game now |

✅ Check: open http://127.0.0.1:8000/docs, try `POST /api/game/new`, copy the `game_id`, then try `hint`.

## Step 14 — Make the page playable (`frontend/`)

- Click a rod = **pick up** its top disk (it lifts and glows). Click another rod = **put it down**. Keys `1 2 3` work too.
- The page sends the move to the backend. **Red banner** if it is illegal. If legal, the **robot arm** does the move (same 8-step animation as before).
- **💡 Hint** → the coach answers → the two rods glow green and a sentence explains why.
- If you do nothing for 25 seconds, the Hint button gently pulses.
- Win → pop-up with stars. Your best score per level is saved in your browser.

✅ Check: press Start a New game, make one wrong move on purpose (you should see the red message), press Hint, follow it.

## Step 15 — Prove the coach is right (`tests/test_game.py`)

We do not just *hope* hints are best. The test explores **every possible position** (3ⁿ of them) with a brute-force search and checks that the hint always moves one step closer to the shortest finish.

✅ Check: `pytest -q` → all green.

---

## Mini glossary

| Word | Five-year-old meaning |
|---|---|
| API | A phone line between two programs |
| Endpoint | One phone number on that line |
| JSON | The language the two programs speak |
| Recursion | A job that asks a smaller copy of itself for help |
| Iteration | A job done with a loop |
| Canvas | A drawing board in the web page |
| Frame | One picture of the animation (60 per second) |
| Hint | The coach's best next move from where you are now |
| BFS | A brute-force search that tries every position, used to prove the hints are best |
