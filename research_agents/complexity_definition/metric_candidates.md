# Metric Candidates

## 1. Where Complexity Should Live

### Position-level complexity

Definition target:
- `C_pos(p)`

Question answered:
- “How hard is this turn overall for a human?”

Good for:
- filtering datasets
- selecting positions for review
- estimating whether a model is entering a tactically unstable region

Weakness:
- it hides which candidate move is actually hard to realize

### Move-level complexity

Definition target:
- `C_move(p, m)`

Question answered:
- “If the player chooses move `m` in position `p`, how hard is the resulting task for a human to execute?”

Good for:
- comparing `Stockfish best` vs `human move`
- explaining why humans avoid engine-favored moves
- connecting complexity with realizability

Weakness:
- more expensive to compute than root-only scores

### Line-level complexity

Definition target:
- `C_line(p, l)` for a concrete line `l = (m1, ..., mh)`

Question answered:
- “How narrow, brittle, and unforgiving is this exact continuation?”

Good for:
- explanation
- qualitative review
- debugging false positives from move-level metrics

Weakness:
- too local to be the main training label by itself

## 2. Recommended Main Object

- `Theory judgment`
  - Use `move-level complexity` as the primary definition.
  - Derive position-level summaries from move-level values when needed.
  - Keep line-level complexity as an explanation layer, not the primary scalar.

Reason:
- the motivating problem is specifically about candidate moves that engines like but humans do not trust
- that is naturally a property of `(position, move)`, not of `position` alone

## 3. Candidate Family A: Maia Effective Choice Complexity

Style:
- human candidate breadth
- mostly `position-level`

### Mathematical definition

Let `pi(a | p)` be Maia's root move distribution on legal moves in `p`.

Define the effective number of human-plausible candidates:

`N_eff(p) = exp(- sum_a pi(a | p) log pi(a | p))`

Then define:

`C_MECC_raw(p) = N_eff(p)`

Optional scalar normalization on a reference corpus `D`:

`C_MECC(p) = 100 * F_D(C_MECC_raw(p))`

where `F_D` is the empirical CDF on `D`.

### Required inputs

- Maia root move probabilities

### Computation steps

1. Run Maia on the root position.
2. Read the full root probability distribution.
3. Compute entropy and `N_eff`.
4. Optionally percentile-normalize against a reference set.

### Pros

- very cheap
- already computable from current `raw_policy_snapshots.jsonl`
- no arbitrary weighting
- easy to explain: “how many human-looking options are live?”

### Cons

- measures breadth, not fragility
- can call a quiet position “complex” when many moves are simply similar
- does not see the burden of later forced moves

### Likely failure cases

- slow maneuvering positions with many roughly equal plans
- tactical positions where Maia likes only one natural move, but that move is extremely hard to realize

### Relation to realizability

- `Theory judgment`
  - weak relation
  - it measures root choice breadth, not post-choice convertibility

## 4. Candidate Family B: Engine Stability Complexity

Style:
- engine-best instability across search budgets
- `position-level`, optionally `move-level` after fixing a candidate move

### Mathematical definition

For time budgets `T = {t1, ..., tk}`, let:

- `b_t(p)` = Stockfish best move at budget `t`
- `S_t^K(p)` = top-`K` move set at budget `t`
- `v_t(p)` = best score at budget `t`
- `PV_t(p)` = principal variation at budget `t`

Raw components:

`switch_rate(p) = (1 / (k - 1)) * sum_i I[b_ti != b_t(i+1)]`

`overlap_instability(p) = 1 - (1 / (k - 1)) * sum_i Jaccard(S_ti^K, S_t(i+1)^K)`

`score_drift_raw(p) = max_t v_t - min_t v_t`

`pv_instability(p) = 1 - mean_i prefix_len(PV_ti, PV_t(i+1)) / H`

Scalar form:

`C_ESC(p) = 100 * mean(F_D(score_drift_raw), switch_rate, overlap_instability, pv_instability)`

Equal weights only.

### Required inputs

- Stockfish multi-budget root analysis

### Computation steps

1. Re-analyse the same position at several time budgets.
2. Save top-`K` moves, best score, and PV at each budget.
3. Compute switch, overlap, score drift, and PV prefix instability.
4. Normalize score drift by empirical percentile.
5. Average the four components equally.

### Pros

- independent of Maia
- directly answers “does the engine itself keep changing its mind?”
- existing overnight sweep already supports this style

### Cons

- engine instability is not identical to human difficulty
- expensive if used on every position
- some human-hard positions still have stable engine best moves

### Likely failure cases

- strategically subtle but root-stable positions
- endgames where best move is stable but execution remains technically hard

### Relation to realizability

- `Theory judgment`
  - indirect but useful
  - instability is evidence that a position may be brittle, but realizability is move-specific

## 5. Candidate Family C: Continuation Burden Complexity

Style:
- unique-move burden
- deviation penalty
- opponent refutation pressure
- `move-level`

This is the best match to the repository's actual research question.

### Mathematical definition

Let:

- `p` = root position
- `m` = candidate move
- `r` = root player
- `E(.)` = Stockfish evaluation in `r`'s point of view
- `V0 = E(p, m)`
- `G0 = V0 - E(p)`

Define a viability floor:

`T_viable(p, m) = max(V0 - Delta_drop, E(p) + rho * max(G0, 0), F_abs)`

At any later root-player decision node `n`, let `E*(n)` be the best available evaluation and define the acceptable set:

`A(n ; p, m) = { a : E(n, a) >= max(E*(n) - delta_local, T_viable(p, m)) }`

Now define raw burden features over all root-player nodes `N_r` and opponent-response nodes `N_o` inside a shallow continuation tree:

`f_width = mean_{n in N_r} 1 / max(1, |A(n)|)`

`f_unique = mean_{n in N_r} I[|A(n)| <= 2]`

`f_refute = mean_{o in N_o} I[ next root-player node has |A| = 0 ]`

`f_drop = median_{n in N_r} (E*(n) - E_bad(n))_+`

where `E_bad(n)` is the best move below the acceptable cutoff, if one exists, else `E*(n)`.

`f_streak = longest consecutive narrow streak / max possible streak`

Scalar form:

`z_j = F_D(f_j)`

`C_CBC(p, m) = 100 * mean(z_width, z_unique, z_refute, z_drop, z_streak)`

Equal weights only. `F_D` is an empirical CDF fitted on a calibration corpus.

### Required inputs

- Stockfish root analysis
- Stockfish continuation analysis to horizon `H`
- candidate move list
- optional Maia root probabilities for comparison, not for the core definition

### Computation steps

1. Select root candidates worth evaluating.
2. For each candidate move, build a shallow tree with strong opponent replies and root-player follow-ups.
3. At each root-player node, compute the acceptable set `A(n ; p, m)`.
4. Extract `f_width`, `f_unique`, `f_refute`, `f_drop`, `f_streak`.
5. Convert each raw feature to a reference percentile.
6. Average the normalized features equally.

### Pros

- directly aligned with “humans may not dare play this”
- decomposable into human-readable reasons
- close to the current repository's `realizability` pipeline, so implementation cost is moderate
- works naturally at `move-level`

### Cons

- needs more engine calls than root-only metrics
- still depends on a definition of “acceptable”
- centipawn thresholds need calibration, not hand-picking

### Likely failure cases

- fortress / tablebase-like positions where cp evaluation is misleading
- sacrificial attacks with mate-or-bust evaluation cliffs
- positions where the true difficulty is long-horizon rather than 4-ply local burden

### Relation to realizability

- `Theory judgment`
  - this is the closest family to realizability
  - if `m` gains an advantage, then `high C_CBC(p, m)` usually means `low realizability(p, m)`
  - but it is still broader than realizability because it remains meaningful even when `G0 <= 0`, and because it is used as a complexity lens rather than a “can convert advantage” label only

## 6. Candidate Family D: Human-Engine Conflict Complexity

Style:
- Maia vs Stockfish disagreement
- “engine strongly recommends, human policy refuses”
- `position-level` or `engine-best move-level`

### Mathematical definition

Let `b = argmax_a E(p, a)` be Stockfish's best move.

Define:

`g_prob(p) = - log max(pi(b | p), epsilon)`

`g_margin(p) = E(p, b) - E(p, second_best)`

Scalar form:

`C_HECC(p) = 100 * mean(F_D(g_prob), F_D(g_margin))`

Interpretation:
- high when Stockfish strongly prefers a move and Maia assigns that move low probability

### Required inputs

- Stockfish root analysis
- Maia root probabilities

### Computation steps

1. Find Stockfish root best move and second-best score.
2. Read Maia probability of the Stockfish best move.
3. Transform low human-likeness and high engine margin into two normalized components.
4. Average equally.

### Pros

- cheap once both root analyses exist
- tightly connected to the motivating phenomenon
- already partly validated by existing repository reports

### Cons

- depends on Maia quality and calibration
- can confuse “Maia blind spot” with “intrinsic human difficulty”
- sees disagreement, not necessarily follow-up burden

### Likely failure cases

- opening novelty or distribution shift against Maia
- style mismatches between Maia training cohort and target human population

### Relation to realizability

- `Theory judgment`
  - often correlated, but not identical
  - a move can be Maia-unlikely for stylistic reasons even if it is easy to realize once played

## 7. Comparison Summary

| Family | Primary object | Best use | Cost | Main blind spot |
|---|---|---|---:|---|
| `MECC` | position | cheap root filtering | low | misses continuation burden |
| `ESC` | position | engine-instability probe | medium/high | stable engine move can still be hard for humans |
| `CBC` | move | main human-realization metric | medium/high | needs acceptable-set calibration |
| `HECC` | position or engine-best move | human-engine divergence scan | low/medium | depends on Maia calibration |

## 8. What Existing Code Already Supports

- `Code-validated result`
  - `src/complexity/simple_metric.py` already implements a root-only branching score.
  - `src/analysis/time_budget_sweep.py` already supports the `ESC` family.
  - `src/analysis/realizability.py` already supports a bootstrap version of `CBC`, but its current scalar score uses arbitrary manual weights and should not be treated as the final recommended scalar.

## 9. Recommended Direction

- `Theory judgment`
  - Main definition: `CBC` at `move-level`
  - Position-level derived views:
    - `C_pos_best(p) = C_CBC(p, m_sf_best)`
    - `C_pos_frontier(p) = mean_{m in K(p)} C_CBC(p, m)`
  - Auxiliary diagnostics:
    - `ESC` as engine-only corroboration
    - `HECC` as human-engine conflict corroboration
- `Unverified hypothesis`
  - `CBC` should outperform the current simple root score for explaining human avoidance of engine-best moves.
