# alpasim-jepa

JEPA-style driving planners for the **AlpaSim E2E Closed-Loop Challenge 2026**, evaluated as a
separate thread from the main entry in `../alpasim` (Alpamayo 1.5; PAI rank 2/58, nuPlan rank
19/71 on 2026-09-29).

**Rule (Aman, 2026-09-29):** `../alpasim`, `../jepa-nureasoning` and `../nureasoning` are
read-only from here. Everything borrowed is listed in [BORROWED.md](BORROWED.md).

**Aim:** find out whether a released JEPA planner beats the current nuPlan-track driver in
closed loop, and whether a JEPA component helps on PAI. Evidence and decisions live in
[LEDGER.md](LEDGER.md).

## Layout
- `src/`: our code: the WA-JEPA / Drive-JEPA policy adapters for the AlpaSim egodriver API.
- `notes/`: design notes.
- `cluster/`: job scripts. Where GPU work runs is still to be agreed with Aman.
