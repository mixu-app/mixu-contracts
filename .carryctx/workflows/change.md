# Workflow: change in mixu-contracts

1. `carryctx task show CTX-XXXX` and read `.carryctx/rules/repo.md` (plus
   `spoiler.md` / `secrets.md` when applicable).
2. `carryctx task start CTX-XXXX`; create a worktree after the first commit
   (`carryctx worktree create CTX-XXXX`).
3. Implement inside the task scope; record `progress note` for findings and
   `progress risk` for anything you decline to fix now.
4. Add or update the test that fails without the change; run `just check` and
   keep the real output for the PR body.
5. Commit on `ctx-XXXX/<type>-<slug>` with `CARRYCTX_TASK` and
   `CARRYCTX_AGENT` exported; push and open a PR.
6. PR body carries `Priority: ... | Area: contracts | Labels: ... |
   Milestone: v0.1.0 | Task: CTX-XXXX`, labels `feat|fix|docs|chore` plus
   `P0|P1|P2` plus `area:contracts`, and `Closes #<issue>`.
7. After review and green CI: merge, `checkpoint`, `task complete`.
