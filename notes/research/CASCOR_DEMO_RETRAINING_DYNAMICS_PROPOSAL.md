# Root Cause Proposal: Insufficient Output Retraining and Inter-Cascade Training Dynamics

**Project**: Juniper Canopy (juniper-canopy) — CasCor Demo Mode
**File Under Analysis**: `juniper-canopy/src/demo_mode.py`
**Date**: 2026-03-19
**Author**: Claude Code analysis for Paul Calnon
**Status**: Proposal
**Relates To**: `CASCOR_DEMO_TRAINING_ERROR_PLAN.md` (RC-3, RC-10, Phase 3 plateau)

---

## Root Cause Hypothesis

Training stalls after the first hidden unit because the demo's training dynamics create a **retraining-detection-addition cycle** that never allows the network to settle. Three interacting mechanisms produce the stall:

1. **500 internal retrain steps are invisible to convergence detection**, creating a blind spot where the sliding window sees only the slow post-retrain residual improvement and misinterprets it as convergence.

2. **1 gradient step per visible epoch (~30 epochs between additions) is insufficient** to make meaningful progress with Adam after the optimizer already completed 500 steps of adaptation during retrain.

3. **Rapid cascade addition triggered by false convergence** installs new hidden units before the output layer has learned to use the previous one, compounding weight-column neglect across multiple units.

These three mechanisms form a feedback loop: insufficient inter-cascade training causes apparent convergence, which triggers premature addition, which resets the optimizer and output layer, which makes the next inter-cascade phase even less productive.

---

## Detailed Analysis

### 1. The 500-Step Internal Retrain and Its Interaction with the Outer Loop

**Code location**: `demo_mode.py:235-237` (retrain loop), `demo_mode.py:862-865` (cascade trigger in training loop)

When `add_hidden_unit()` is called at line 865, the method internally executes 500 calls to `train_output_step()` (line 236-237):

```python
# Retrain output with full-batch for 500 steps
for _ in range(500):
    self.train_output_step()
```

These 500 steps occur **inside the lock** at line 864 and are **not recorded** in the loss history. The history is only updated at line 829:

```python
self.network.history["train_loss"].append(loss)
```

This happens once per iteration of the outer `_training_loop()`, at line 817, which calls `_simulate_training_step()` once per epoch. The 500 internal steps are completely invisible to:

- The `network.history["train_loss"]` deque (which feeds convergence detection)
- The `metrics_history` deque (which feeds the dashboard)
- The WebSocket broadcast system (which feeds real-time charts)

**Consequence**: After 500 steps of retrain, the very next `_simulate_training_step()` at line 817 performs one additional step and records the resulting loss. The convergence detector at `_should_add_cascade_unit()` (line 773) then begins filling its 10-epoch window starting from this post-retrain loss. The post-retrain loss is already near a local minimum -- subsequent single steps cannot improve it meaningfully, so the window fills with near-flat values.

### 2. Whether 500 Steps Is Sufficient for Output Retraining

**Code location**: `demo_mode.py:235-237` vs `juniper-cascor/src/cascor_constants/constants_model/constants_model.py:226`

The production CasCor uses **1000 full-batch epochs** (line 226 of constants_model.py: `_PROJECT_MODEL_OUTPUT_EPOCHS = 1000`), confirmed as "the value used with 100% run." The demo uses 500 steps.

**Mathematical analysis of Adam convergence for the new weight column**:

When a hidden unit is installed, the output layer gains one new weight column (for the new hidden feature), initialized to a small random value by `nn.Linear` default. The existing columns carry over from the previous output layer via warm-start (line 228):

```python
self.output_layer.weight[:, :old_layer.in_features] = old_layer.weight
```

The new column must learn a weight that correctly scales the new hidden unit's contribution to the output. With Adam (lr=0.01, betas=(0.9, 0.999)):

- **Effective learning rate during early steps**: Adam's adaptive rate is approximately `lr / sqrt(v_hat + eps)` where `v_hat` is the exponential moving average of squared gradients. For the first ~100 steps, `v_hat` is still warming up (biased toward zero), so bias correction inflates the effective step size.

- **Convergence timeline**: For a 200-sample full-batch problem with MSE loss on a linear output layer (convex), Adam typically converges to within 1% of optimal in ~200-400 steps (empirical observation for similar dimensionality). At 500 steps, the output layer is likely near-converged for the current feature set.

- **However**: 500 steps may be *just barely sufficient* rather than *fully converged*. The final 500 steps of a 1000-step run produce residual improvements of ~0.0001-0.001 per step. These small improvements matter because they set the baseline for convergence detection. If retrain stops at 500 steps while the loss is still dropping at 0.001/step, the next 10 outer epochs of single-step training will show continued improvement and delay the false convergence trigger. If retrain stops only when the loss is truly flat, the post-retrain window immediately looks converged.

**Verdict**: 500 steps is likely sufficient for the output layer to learn to *use* the new hidden unit feature in a basic sense (the new weight reaches approximately the right magnitude). The problem is not that 500 steps is too few for initial learning, but that it is close enough to convergence that the subsequent 1-step-per-epoch training has almost nothing left to improve.

### 3. Inter-Cascade Training: 1 Step/Epoch for ~30 Epochs

**Code location**: `demo_mode.py:817` (single training step), `demo_mode.py:878` (wait interval), `settings.py:124` (`demo_cascade_every = 30`)

Between cascade additions, the training loop executes this per epoch:

1. `_simulate_training_step()` at line 817 -- calls `train_output_step()` **once** (full-batch)
2. Record loss/accuracy in history at lines 829-832
3. Check `_should_add_cascade_unit()` at line 862
4. Wait `update_interval` seconds (default 1.0s) at line 878

**Total inter-cascade computation**: ~10-30 gradient steps (depending on whether convergence triggers early or the fixed schedule fires at epoch 30).

**Why this cannot make meaningful progress**:

After 500 steps of retrain, the Adam optimizer's moment estimates (`m` and `v`) are fully warmed up and adapted to the loss landscape at the retrain minimum. The effective per-parameter learning rate has stabilized at a value appropriate for the small residual gradients near the minimum.

On step 501 (the first outer-loop step), the gradient is essentially the same as on step 500 -- a tiny residual. Adam takes a tiny step. On step 502, another tiny step. After 30 such steps, the total weight change is negligible:

**Estimated weight change over 30 inter-cascade steps**:
- Near the minimum, gradient magnitude is approximately `g ~ 0.001` (residual MSE gradient for a near-converged output layer)
- Adam effective step: `lr * m_hat / (sqrt(v_hat) + eps) ~ 0.01 * 0.001 / (sqrt(0.000001) + 1e-8) ~ 0.01`
- Total change over 30 steps: `~30 * 0.01 = 0.3` in the most optimistic case
- But the adaptive denominator grows, so later steps are even smaller: realistic total change is `~0.05-0.1`

For context, the new hidden unit weight column was trained to a magnitude of approximately 0.5-2.0 during retrain. A post-retrain drift of 0.05-0.1 is noise-level perturbation -- neither harmful nor helpful.

**The core paradox**: If the 500-step retrain was sufficient, then the inter-cascade 30 steps are redundant (the loss is already near-optimal for the current architecture). If the retrain was insufficient, then 30 additional steps are grossly inadequate to complete the job that 500 steps started (it would need hundreds more).

### 4. Convergence Detection False Triggering

**Code location**: `demo_mode.py:751-780`

The convergence detector:

```python
if conv_enabled and len(self.network.history["train_loss"]) >= 10:
    recent = list(self.network.history["train_loss"])[-10:]
    improvement = recent[0] - recent[-1]
    if improvement < conv_threshold:   # conv_threshold = 0.001
        return True
```

**Timeline after hidden unit #1 installation**:

| Time | Event | Loss in History | Notes |
|------|-------|-----------------|-------|
| Epoch N | Cascade trigger fires | history[-1] = L_pre | Pre-retrain loss |
| Epoch N (internal) | 500 retrain steps | (not recorded) | Loss drops by ~0.02-0.05 |
| Epoch N+1 | First post-retrain step | history[-1] = L_post | L_post ~ L_pre - 0.03 |
| Epoch N+2 | Second post-retrain step | history[-1] = L_post - 0.0003 | Tiny improvement |
| ... | ... | ... | ... |
| Epoch N+10 | Convergence window full | window spans N+1..N+10 | Total improvement ~ 0.002 |
| Epoch N+11 | Convergence check | improvement < 0.001? | **May trigger!** |

The critical issue: `improvement = recent[0] - recent[-1]` compares the **first post-retrain epoch** to the **10th post-retrain epoch**. Since the retrain already brought the loss near-optimal, these 10 epochs show minimal improvement. If improvement < 0.001 (the default threshold), another hidden unit is added at epoch N+11.

**This means the network gets only 10-11 outer epochs between additions**, not the 30 that the fixed schedule would provide. The convergence detector short-circuits the fixed schedule fallback.

**Important nuance**: The convergence detector checks `improvement = recent[0] - recent[-1]`. This is the **total improvement over the window**, not the per-epoch rate. With loss near 0.24 (post-retrain for a spiral problem), an improvement of 0.001 over 10 epochs corresponds to a 0.4% relative improvement. This is actually a reasonable convergence criterion for the *current architecture* -- the problem is that the architecture just changed (new hidden unit added) and the output layer hasn't had enough inter-cascade steps to exploit the change.

### 5. Cumulative Effect: The Rapid-Addition Cascade

The feedback loop creates an accelerating cycle of diminishing returns:

**Cycle for hidden unit #1**:
1. Output training converges at ~0.24 MSE over 30 initial epochs
2. Convergence detected; unit #1 installed; 500 retrain steps internally
3. Loss drops to ~0.22 (retrain finds a better configuration using the new feature)
4. 10 outer epochs produce ~0.001 total improvement (0.22 -> 0.219)
5. Convergence detected again; unit #2 installed

**Cycle for hidden unit #2**:
1. 500 retrain steps internally; loss drops from 0.219 to ~0.217
2. But unit #2's contribution is marginal because unit #1's weight was not fully optimized
3. 10 outer epochs produce ~0.0005 total improvement
4. Convergence detected; unit #3 installed

**Cycle for hidden unit #N**:
- Each successive unit contributes less because the output layer has accumulated N weight columns that were never given enough post-retrain optimization to reach their full potential
- The new unit's candidate was trained against a residual that still contains unexploited information from the previous units (whose weights are suboptimal)
- The retrain attempts to jointly optimize all N+2 columns (input_size + N hidden) in 500 steps, but the optimization surface grows more complex with each added dimension
- The 500 steps become increasingly insufficient as dimensionality grows

**Predicted loss trajectory**:

```
Epoch:  0    10   20   30   31   41   42   52   53   ...
Loss:   0.50 0.35 0.27 0.24 0.22 0.219 0.217 0.216 0.215 ...
                       ^Unit1     ^Unit2      ^Unit3
                       (500 internal steps each, invisible)
```

The visible loss curve shows: 0.50, 0.35, 0.27, 0.24, 0.22, 0.219, 0.217, 0.216, 0.215...

From epoch 31 onward, the loss decreases by ~0.001 per cascade event, creating the visual appearance of a plateau. Each hidden unit provides a smaller marginal benefit because the previous units were never fully utilized.

---

## Predicted Symptoms

Based on the analysis above, the following observable behaviors are predicted:

1. **Loss curve shows a staircase-without-stairs pattern**: After the initial drop (epochs 0-30), the loss decreases in tiny jumps every ~10-12 epochs (when convergence triggers a new unit), but the jumps are invisible at chart scale (~0.001-0.002 each)

2. **Accuracy plateaus at 55-60%**: This corresponds to a network that learned the bulk structure of the spiral (first hidden unit) but cannot refine the boundary because subsequent units' weights are under-trained

3. **Hidden unit output weights decay in magnitude with index**: The N-th hidden unit's output weight is smaller than the (N-1)-th because each retrain starts from scratch (fresh Adam) and has the same 500 steps to optimize an increasingly complex weight vector

4. **Decision boundary shows one major curve, then stops evolving**: The first hidden unit creates a visible nonlinear boundary. Subsequent units add imperceptible refinements

5. **Candidate correlation decreases with unit count**: Later candidates train against residuals that still contain useful signal from under-exploited earlier units, but the correlation computation (now Pearson-normalized) returns lower values because the residual has less variance (it was partially reduced by the retrain, even if not fully)

6. **Disabling convergence detection (`convergence_enabled=False`) partially helps**: With only the fixed 30-epoch schedule, each unit gets 30 outer steps instead of ~10, providing ~3x more inter-cascade training. This does not solve the fundamental problem but makes the staircase steps slightly larger.

---

## Specific Code Locations

| Location | Description | Role in the Bug |
|----------|-------------|-----------------|
| `demo_mode.py:235-237` | 500-step retrain loop in `add_hidden_unit()` | Creates 500 invisible training steps |
| `demo_mode.py:232-233` | Fresh Adam optimizer creation | Resets optimizer state, removing inter-cascade adaptation |
| `demo_mode.py:694` | `self.network.train_output_step()` in `_simulate_training_step()` | Only 1 gradient step per visible epoch |
| `demo_mode.py:829` | `self.network.history["train_loss"].append(loss)` | Records only 1 loss per outer epoch (misses 500 retrain steps) |
| `demo_mode.py:773-776` | Convergence detection: 10-epoch sliding window | Window fills with near-flat post-retrain loss |
| `demo_mode.py:780` | Fixed schedule fallback: `cascade_every` (default 30) | Overridden by convergence trigger at ~epoch 10 |
| `demo_mode.py:862-865` | Cascade trigger check and add_hidden_unit call | Fires too frequently due to false convergence |
| `demo_mode.py:870-871` | Artificial loss inflation: `self.current_loss * 1.5` | Cosmetic; overwritten by real MSE at next step |
| `canopy_constants.py:58` | `DEFAULT_CONVERGENCE_THRESHOLD = 0.001` | Threshold too tight for post-retrain residual |
| `settings.py:124` | `demo_cascade_every = 30` | Fallback interval (never reached if convergence fires first) |
| `cascor constants_model.py:226` | `_PROJECT_MODEL_OUTPUT_EPOCHS = 1000` | Production reference: 2x the demo's retrain budget |

---

## Proposed Fix

### Primary Fix: Record retrain progress and widen the convergence window

**Rationale**: The root issue is that 500 steps of retrain are invisible to convergence detection, creating an information asymmetry. The fix should either (a) make the retrain visible, or (b) adjust detection to account for the blind spot.

#### A. Inject retrain loss samples into the history

Modify `add_hidden_unit()` to periodically record loss during the 500-step retrain:

```python
def add_hidden_unit(self):
    # ... (candidate training unchanged) ...

    self.hidden_units.append(best_unit)

    # Expand output layer (unchanged)
    old_layer = self.output_layer
    new_dim = self.input_size + len(self.hidden_units)
    self.output_layer = torch.nn.Linear(new_dim, self.output_size)
    with torch.no_grad():
        self.output_layer.weight[:, :old_layer.in_features] = old_layer.weight
        self.output_layer.bias[:] = old_layer.bias

    # Fresh optimizer (unchanged)
    self.output_optimizer = torch.optim.Adam(
        self.output_layer.parameters(), lr=self.learning_rate
    )

    # Retrain with periodic loss recording
    retrain_steps = 1000  # Match production CasCor
    sample_interval = 50  # Record every 50 steps
    for step in range(retrain_steps):
        self.train_output_step()
        if (step + 1) % sample_interval == 0:
            with torch.no_grad():
                predictions = self.forward(self.train_x)
                loss = float(((predictions - self.train_y) ** 2).mean())
                self.history["train_loss"].append(loss)
```

This makes the retrain's convergence trajectory visible to the sliding window. The window will see the loss dropping during retrain and will not trigger false convergence until retrain itself has converged.

**Impact on convergence detection**: With 1000 steps and sampling every 50, the retrain adds 20 loss samples. The 10-epoch window will span the tail end of retrain (where improvement is genuinely slow) rather than the immediate post-retrain region. This correctly identifies that the *retrained* output layer has converged, which is the legitimate signal to add a new unit.

#### B. Increase retrain steps to match production

Change from 500 to 1000 steps to match the production CasCor's `_PROJECT_MODEL_OUTPUT_EPOCHS = 1000`:

```python
retrain_steps = 1000  # Was 500; match production CasCor
```

This gives the output layer 2x more training to learn the new hidden unit's weight, and more importantly, ensures the retrain fully converges before returning to the outer loop.

#### C. Increase inter-cascade training to 5 steps per epoch

Modify `_simulate_training_step()` to perform multiple gradient steps per outer epoch:

```python
def _simulate_training_step(self) -> Tuple[float, float]:
    # Perform multiple weight updates per outer epoch
    steps_per_epoch = 5
    with self._lock:
        for _ in range(steps_per_epoch):
            self.network.train_output_step()

    # Compute metrics (unchanged)
    ...
```

This gives the inter-cascade phase 150 gradient steps (30 epochs x 5 steps) instead of 30, providing meaningful optimization budget between cascade additions.

#### D. Widen the convergence window

Change the window from 10 to 25 epochs, and adjust the threshold:

```python
# In _should_add_cascade_unit():
window_size = 25  # Was 10; need more epochs to distinguish noise from plateau
if conv_enabled and len(self.network.history["train_loss"]) >= window_size:
    recent = list(self.network.history["train_loss"])[-window_size:]
    improvement = recent[0] - recent[-1]
    relative_improvement = improvement / (abs(recent[0]) + 1e-8)
    if relative_improvement < conv_threshold:  # Use relative, not absolute
        return True
```

Using **relative improvement** (rather than absolute) prevents the threshold from being effectively tighter at low loss values. At loss=0.24, an absolute threshold of 0.001 corresponds to 0.4% improvement -- which is actually reasonable. But at loss=0.50 (before any units), 0.001 is only 0.2%. A relative threshold of 0.5% (0.005) applies uniformly.

### Summary of Proposed Changes

| Change | Location | Effect |
|--------|----------|--------|
| Record retrain loss in history | `add_hidden_unit()` | Makes retrain visible to convergence detection |
| Increase retrain to 1000 steps | `add_hidden_unit()` | Matches production CasCor; ensures full convergence |
| 5 steps per outer epoch | `_simulate_training_step()` | 5x more inter-cascade optimization |
| 25-epoch window + relative threshold | `_should_add_cascade_unit()` | Prevents false convergence triggering |

---

## Expected Impact

### With All Four Changes Applied

1. **Loss trajectory improvement**: Each hidden unit will produce a visible loss reduction of ~0.01-0.03 (instead of ~0.001), because:
   - The 1000-step retrain fully converges the output weights for all hidden units (not just near-convergence)
   - The 5-step inter-cascade training provides 150 steps of continued optimization
   - The wider convergence window gives the network 25 epochs to demonstrate improvement before adding another unit

2. **Accuracy improvement**: Expected final accuracy of 70-80% (up from 55-60%) with 5-7 hidden units on the spiral problem, because each hidden unit's output weight is properly optimized

3. **Visible decision boundary evolution**: Each hidden unit addition should produce a visible change in the decision boundary on the dashboard, rather than imperceptible refinements

4. **Slower cascade addition rate**: Hidden units will be added approximately every 25-40 epochs instead of every 10-12 epochs, giving each unit time to contribute

5. **Dashboard chart interpretability**: The loss curve will show a clear staircase pattern with visible steps (retrain drops sampled into history), followed by gradual inter-cascade improvement, followed by the next cascade event

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| Retrain loss samples inflate history length | `deque(maxlen=1000)` already limits history; 20 samples per retrain is manageable |
| Longer retrain blocks the training thread | 1000 steps at ~0.1ms each = ~100ms total; acceptable for 1s epoch interval |
| 5 steps/epoch changes the effective training rate | This is the intended effect; loss curve will show smoother improvement |
| Wider window delays initial cascade addition | First addition moves from epoch ~10 to epoch ~25-30; this is actually closer to the correct CasCor behavior |

---

## Appendix: Comparison with Production CasCor Training Loop

| Aspect | Demo (Current) | Production CasCor | Demo (Proposed) |
|--------|----------------|-------------------|-----------------|
| Output retrain after unit install | 500 full-batch steps | 1000 full-batch epochs | 1000 full-batch steps |
| Retrain loss recorded in history | No | Yes (final loss) | Yes (every 50 steps) |
| Optimizer after retrain | Fresh Adam | Fresh optimizer | Fresh Adam (unchanged) |
| Inter-cascade training | 1 step/epoch, ~10-30 epochs | N/A (grow_network is outer loop) | 5 steps/epoch, ~25-40 epochs |
| Convergence detection | 10-epoch window, abs threshold 0.001 | Correlation threshold on candidates | 25-epoch window, relative threshold 0.005 |
| Cascade trigger | Convergence OR fixed schedule (30) | Correlation threshold met | Convergence OR fixed schedule (30) |

**Key architectural difference**: In production CasCor, the outer loop is `grow_network()` which alternates between candidate training and output retraining. There is no "inter-cascade output training" -- the output is retrained for the full `output_epochs` count after each unit, and the next iteration immediately begins candidate training. The demo's outer loop adds a third phase (inter-cascade single-step training) that does not exist in the algorithm specification. The proposed fix does not eliminate this third phase but makes it productive enough to avoid false convergence triggers.
