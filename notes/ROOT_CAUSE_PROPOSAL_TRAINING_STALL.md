# Root Cause Proposal: Demo Training Stalls After First Hidden Unit

**Date**: 2026-03-19
**Author**: Claude (Opus 4.6)
**Status**: Proposal
**Severity**: Critical -- training is non-functional after first cascade addition

---

## Executive Summary

The demo's `MockCascorNetwork` and `DemoMode._training_loop()` contain **five fundamental algorithmic mismatches** with the Fahlman & Lebiere (1990) CasCor specification as implemented in `juniper-cascor`. These mismatches were not addressed by previous fix rounds (which corrected activation functions, loss functions, optimizers, correlation normalization, and convergence detection). The mismatches interact to create a training stall that becomes catastrophic after the first hidden unit is installed.

---

## Mismatch 1: Interleaved Single-Step Output Training vs. Phase-Based Convergence Training

### Root Cause Hypothesis

The demo performs **exactly one output gradient step per epoch** inside `_simulate_training_step()`, then evaluates metrics and checks cascade addition criteria. The CasCor algorithm requires the output layer to be trained **to convergence** (hundreds to thousands of steps) as a self-contained phase before any cascade decision is made.

### Evidence from Code

**Demo** (`demo_mode.py` lines 681-713, 816-817):

```python
def _simulate_training_step(self) -> Tuple[float, float]:
    # Perform an actual weight update (full-batch, inline)
    with self._lock:
        self.network.train_output_step()    # <-- ONE step
    # ... compute metrics ...
```

The training loop calls this once per epoch iteration. After that single step, it records the loss, checks convergence, and potentially triggers cascade addition.

**Reference** (`cascade_correlation.py` lines 1141-1145, 1304):

```python
# fit() -- initial output training
train_loss = self.train_output_layer(x_train, y_train, max_epochs)  # max_epochs defaults to 1000

# train_output_layer() -- inner loop
for epoch in range(epochs):   # epochs = 1000 (from _PROJECT_MODEL_OUTPUT_EPOCHS)
    # ... gradient step ...
```

The reference trains the output layer for `_PROJECT_MODEL_OUTPUT_EPOCHS = 1000` full gradient steps before returning. After `fit()` calls `train_output_layer()`, it then enters `grow_network()` which also calls `train_output_layer()` for 1000 steps each time a unit is added.

### Mathematical Impact

After installing a hidden unit, the output layer has a new column of random weights connecting the new unit to the outputs. The demo gives this new column **one gradient step** before evaluating convergence. One step of Adam with lr=0.01 moves the weight by at most ~0.01 (Adam's effective step is bounded by the learning rate regardless of gradient magnitude). The optimal weight for the new column may be O(1), requiring hundreds of steps to reach.

With 1 step per epoch and a convergence window of 10 epochs, the output layer gets a maximum of 10 gradient updates before the convergence check decides loss is "stalled" and installs another unit -- compounding the problem.

### Predicted Symptoms

- Loss drops initially (pre-cascade, output layer converges slowly over many epochs)
- After first hidden unit: loss partially recovers during the 500-step retrain inside `add_hidden_unit()`, but then stalls because subsequent training is 1-step-per-epoch
- The convergence detector fires prematurely because 10 single-step epochs show minimal improvement
- Cascading failure: units are added too frequently, each with under-trained output weights

### Code Location

- `demo_mode.py:694` -- single `train_output_step()` call
- `demo_mode.py:816-817` -- `_simulate_training_step()` called once per loop iteration
- `cascade_correlation.py:1304` -- reference inner loop `for epoch in range(epochs)` where `epochs=1000`

---

## Mismatch 2: Output Weight Re-initialization Strategy (Warm-Start vs. Random Reset)

### Root Cause Hypothesis

When a new hidden unit is installed, the demo **warm-starts** the output layer by copying old weights and letting `nn.Linear` default-initialize the new column. The reference implementation **randomly re-initializes ALL output weights** then retrains from scratch for 1000 epochs.

### Evidence from Code

**Demo** (`demo_mode.py` lines 223-237):

```python
# Expand output layer to accommodate new hidden unit (warm-start)
old_layer = self.output_layer
new_dim = self.input_size + len(self.hidden_units)
self.output_layer = torch.nn.Linear(new_dim, self.output_size)
with torch.no_grad():
    self.output_layer.weight[:, :old_layer.in_features] = old_layer.weight   # Copy old
    self.output_layer.bias[:] = old_layer.bias                                # Copy old
    # New column initialized by nn.Linear default (small random)
```

**Reference** (`cascade_correlation.py` lines 2822-2836):

```python
# Ensure new weights have requires_grad=True
self.output_weights = torch.randn(new_input_size, self.output_size, requires_grad=True) * 0.1
# Copy old weights
self.output_weights[:input_size_before, :] = old_output_weights
self.output_bias = old_output_bias
```

Both actually copy old weights for the existing columns. However, the critical difference is what happens next: the reference calls `train_output_layer()` for 1000 epochs with a fresh optimizer, while the demo does 500 steps in `add_hidden_unit()` then drops to 1-step-per-epoch. The 500-step retrain in the demo is half of the reference's budget, and this is its only opportunity to substantially train the new output weight column.

### Mathematical Impact

The new column's initial weight is ~N(0, 1/sqrt(fan_in)) from `nn.Linear` default init, which is very small (~0.04 for fan_in=3). After 500 steps, Adam can move this to roughly the right magnitude, but the learning rate of 0.01 with Adam may not converge in 500 steps for a difficult nonlinear problem. The reference uses 1000 epochs -- twice the budget.

More importantly, after those 500 steps, the demo returns to 1-step-per-epoch mode. If the 500-step retrain did not fully converge, the remaining output training is effectively stalled at 1 step per epoch forever.

### Predicted Symptoms

- Post-cascade loss partially drops during the 500-step retrain
- Remaining loss plateau that never resolves because 1-step-per-epoch is too slow
- Each additional unit compounds: the output layer has progressively more under-fit weights

### Code Location

- `demo_mode.py:223-237` -- warm-start expansion + 500-step retrain
- `cascade_correlation.py:2822-2836` -- random re-init + 1000-epoch retrain

---

## Mismatch 3: Cascade Addition Trigger (Loss Stagnation Window vs. Correlation Threshold)

### Root Cause Hypothesis

The demo triggers cascade addition based on **loss stagnation over a 10-epoch sliding window** (plus a fixed-schedule fallback). The CasCor algorithm triggers cascade addition when **(a) the output layer has converged AND (b) the best candidate's correlation exceeds a threshold**. These are fundamentally different criteria.

### Evidence from Code

**Demo** (`demo_mode.py` lines 751-780):

```python
def _should_add_cascade_unit(self) -> bool:
    # ...
    if conv_enabled and len(self.network.history["train_loss"]) >= 10:
        recent = list(self.network.history["train_loss"])[-10:]
        improvement = recent[0] - recent[-1]
        if improvement < conv_threshold:    # conv_threshold = 0.001
            return True
    # Fallback: fixed schedule
    return self.current_epoch > 0 and self.current_epoch % self.cascade_every == 0
```

**Reference** (`cascade_correlation.py` lines 2959-2976):

```python
for epoch in range(max_epochs):
    residual_error = self._calculate_residual_error_safe(x_train, y_train)
    training_results = self._get_training_results(x_train, y_train, residual_error)
    # Check if best candidate meets correlation threshold
    if training_results.best_candidate.get_correlation() < self.correlation_threshold:
        break   # Stop growing -- no useful candidate found
```

The reference's `grow_network()` loop: at each iteration, it computes residual error, trains a full candidate pool, checks if the best candidate exceeds the correlation threshold (0.0005), and only then installs it. Output layer convergence is implicit because `train_output_layer()` ran for 1000 epochs before `grow_network()` was called, and again for 1000 epochs after each unit is added.

### Mathematical Impact

The demo's 10-epoch loss-stagnation window with `threshold=0.001` is far too sensitive when combined with 1-step-per-epoch. A loss improvement of less than 0.001 over 10 single gradient steps is **expected** for any non-trivial loss surface -- this is normal slow convergence, not true stagnation.

The reference never checks "is the output training stalled?" in this way. Instead, it unconditionally trains the output layer to convergence (1000 epochs) and then evaluates whether a *candidate* can provide additional correlation with the residual. If no candidate exceeds the correlation threshold (0.0005), the algorithm terminates -- it does not keep adding units.

### Predicted Symptoms

- After the first unit is installed and the 500-step retrain completes, the loss improves slowly at 1 step/epoch
- Within 10 epochs, the loss stagnation check fires because 10 single steps cannot produce 0.001 improvement
- A second unit is added prematurely, before the first unit's contribution is properly integrated
- The second unit is trained against a stale/incorrect residual (see Mismatch 4)
- This cycle repeats, adding units in rapid succession without any of them being properly utilized

### Code Location

- `demo_mode.py:751-780` -- `_should_add_cascade_unit()`
- `cascade_correlation.py:2973-2976` -- correlation threshold check

---

## Mismatch 4: Residual Error Computed at Wrong Time (Stale Residual)

### Root Cause Hypothesis

The demo computes the residual error **inside** `_train_candidate()` (line 258-260) using the network's current prediction **at the moment the candidate pool is trained**, which occurs inside `add_hidden_unit()`. However, candidate training occurs inside the cascade addition code path, which is triggered AFTER a convergence check that used metrics from the PREVIOUS epoch's single training step. The residual may not reflect the true state of the output layer because:

1. The convergence check uses loss from the last `_simulate_training_step()` call
2. `add_hidden_unit()` is called, which first trains candidates against the current residual
3. Then does 500 steps of output retraining
4. The residual used for candidate training is computed BEFORE those 500 steps

In contrast, the reference computes residual error at the TOP of each `grow_network()` iteration, AFTER the output layer has just been fully retrained.

### Evidence from Code

**Demo** (`demo_mode.py` lines 816-865):

```python
# STEP 1: Single training step
loss, accuracy = self._simulate_training_step()
# STEP 2: Check convergence
if self._should_add_cascade_unit():
    # STEP 3: Inside add_hidden_unit() -> _train_candidate():
    #   residual = (y - current_pred).detach()  # <-- uses prediction BEFORE 500-step retrain
    #   ... train candidates against this residual ...
    # STEP 4: 500-step output retrain
    self.network.add_hidden_unit()
```

**Reference** (`cascade_correlation.py` lines 2959-2998):

```python
for epoch in range(max_epochs):
    # STEP 1: Compute fresh residual (output already converged from last round)
    residual_error = self._calculate_residual_error_safe(x_train, y_train)
    # STEP 2: Train candidates against fresh residual
    training_results = self._get_training_results(x_train, y_train, residual_error)
    # STEP 3: Check correlation threshold
    # STEP 4: Add unit
    self._add_best_candidate(...)
    # STEP 5: Retrain output for 1000 epochs
    train_loss = self._retrain_output_layer(x_train, y_train, self.output_epochs, epoch)
```

### Mathematical Impact

In the demo, the residual used for candidate correlation maximization is `y - f(x)` where `f` is the prediction BEFORE the 500-step retrain. This residual is then **stale** after the retrain -- the output layer has substantially different weights. The installed candidate was optimized to correlate with a residual that no longer exists, making its contribution suboptimal or even detrimental.

More subtly, the candidate's optimal weights depend on the residual distribution. If the residual changes significantly during the 500-step retrain (as it should, if retraining is effective), the installed candidate's frozen weights are pointed in the wrong direction.

### Predicted Symptoms

- First unit: works reasonably because the residual before vs. after the initial output convergence may be directionally similar
- Second unit: trained against stale residual; its contribution is misaligned
- Progressive degradation: each subsequent unit is increasingly misaligned
- Loss plateaus because installed units do not effectively capture the remaining error

### Code Location

- `demo_mode.py:258-260` -- residual computation inside `_train_candidate()`
- `demo_mode.py:236-237` -- 500-step retrain happens AFTER candidate selection
- `cascade_correlation.py:2962` -- fresh residual at top of each `grow_network()` iteration

---

## Mismatch 5: Artificial Loss Manipulation Corrupts the Convergence Signal

### Root Cause Hypothesis

After installing a hidden unit, the demo artificially manipulates `self.current_loss` by multiplying it by 1.5 and reducing `self.target_loss` by 0.8 (lines 871-872). This is a leftover from the original "mock simulation" approach and directly contradicts the real gradient-based training that is now happening.

### Evidence from Code

**Demo** (`demo_mode.py` lines 870-872):

```python
# Reset loss target to simulate retraining
self.current_loss = min(1.0, self.current_loss * 1.5)
self.target_loss *= 0.8
```

Meanwhile, `self.current_loss` is also being set from actual predictions in `_simulate_training_step()` (lines 703-704):

```python
mse = ((predictions - self.network.train_y) ** 2).mean()
self.current_loss = float(mse)
```

These two writes conflict. After `add_hidden_unit()` completes (which includes the 500-step retrain), the loss is artificially inflated to 1.5x. But on the very next epoch, `_simulate_training_step()` overwrites it with the actual MSE. However, the artificially inflated value was already appended to `self.network.history["train_loss"]` on line 829, corrupting the convergence sliding window.

Wait -- actually, the artificial manipulation happens AFTER the metrics append (line 829 happens before the cascade check on line 862). So the sequence is:

1. `_simulate_training_step()` -- computes real loss, stores in `self.current_loss`
2. Append real loss to history (line 829)
3. Check `_should_add_cascade_unit()` -- uses history[-10:]
4. If adding: `add_hidden_unit()` runs, then `self.current_loss *= 1.5`
5. Next epoch: `_simulate_training_step()` overwrites `self.current_loss` with real loss

The artificial inflation happens between epochs and gets overwritten immediately. But `self.target_loss *= 0.8` accumulates across additions and is never used by anything meaningful (it was relevant in the original mock-only implementation). This is not directly harmful but indicates vestigial code from the pre-gradient-based era.

However, there is a subtle issue: `self.current_loss` is read by `get_current_state()` and broadcast via WebSocket. The 1.5x inflation creates a brief spike in reported loss that is not real, potentially confusing monitoring.

### Predicted Symptoms

- Brief loss spike visible in the dashboard after each cascade addition
- `target_loss` decays geometrically with each unit but is never used for training decisions
- Not a primary cause of stalling, but a confusing artifact

### Code Location

- `demo_mode.py:871-872` -- artificial manipulation

---

## Interaction Between Mismatches: The Stall Mechanism

The five mismatches interact as follows to produce the observed stall:

```
Initial state: Output layer training at 1 step/epoch (Mismatch 1)
                          |
                          v
Output loss slowly decreases over ~30 epochs (one gradient step each)
                          |
                          v
Convergence check fires: "loss improved < 0.001 over 10 epochs" (Mismatch 3)
  OR fixed schedule fires at epoch 30
                          |
                          v
add_hidden_unit() called:
  - Candidates trained against CURRENT residual (before 500-step retrain) (Mismatch 4)
  - Best candidate installed
  - Output layer expanded with warm-start (Mismatch 2)
  - 500-step retrain runs -- loss drops partially
                          |
                          v
Back to 1 step/epoch (Mismatch 1)
  - Loss barely changes in 10 epochs
  - Convergence check fires again immediately (Mismatch 3)
                          |
                          v
Second unit added -- trained against STALE residual (Mismatch 4)
  - This unit captures noise, not signal
  - 500-step retrain mostly adjusts old weights, new column under-trained
                          |
                          v
Rapid cascade addition loop:
  - Units added every ~10 epochs
  - Each unit trained against stale residual
  - Output layer never converges because 1 step/epoch is insufficient
  - Network grows without learning --> STALL
```

---

## Proposed Fix

The fix requires restructuring `_training_loop()` and `add_hidden_unit()` to match the CasCor phase-based training sequence:

### Phase 1: Multi-Step Output Training Per Epoch

Replace the single-step-per-epoch approach with a configurable number of output training steps per "epoch" (visual epoch for the dashboard):

```python
OUTPUT_STEPS_PER_EPOCH = 50  # Perform 50 gradient steps per visual epoch

def _simulate_training_step(self) -> Tuple[float, float]:
    with self._lock:
        for _ in range(OUTPUT_STEPS_PER_EPOCH):
            self.network.train_output_step()
    # ... compute metrics ...
```

### Phase 2: Correct Cascade Addition Trigger

Replace loss-stagnation with a two-phase convergence check:

```python
def _should_add_cascade_unit(self) -> bool:
    # 1. Check output convergence (relative improvement over window)
    if len(history) >= WINDOW:
        relative_improvement = (history[-WINDOW] - history[-1]) / (history[-WINDOW] + 1e-8)
        if relative_improvement > MIN_IMPROVEMENT:
            return False  # Output layer is still improving -- keep training it

    # 2. Output has converged. Train candidate pool and check correlation.
    best_correlation = self._evaluate_candidate_pool()
    return best_correlation > CORRELATION_THRESHOLD
```

### Phase 3: Fresh Residual Before Candidate Training

Compute the residual AFTER output training has converged, not before the 500-step retrain:

```python
def add_hidden_unit(self):
    # 1. Output layer is already converged (Phase 1 ensured this)
    # 2. Compute fresh residual NOW
    with torch.no_grad():
        residual = self.train_y - self.forward(self.train_x)
    # 3. Train candidates against fresh residual
    best_unit = self._train_candidate_pool(residual)
    # 4. Install best candidate
    self.hidden_units.append(best_unit)
    # 5. Expand and retrain output for 1000 steps
    self._expand_and_retrain_output(steps=1000)
```

### Phase 4: Remove Artificial Loss Manipulation

Delete lines 871-872. The real MSE from `_simulate_training_step()` is the only source of truth.

### Phase 5: Increase Output Retrain Budget

Change the 500-step retrain to 1000 steps to match the reference's `_PROJECT_MODEL_OUTPUT_EPOCHS = 1000`.

---

## Expected Impact

| Metric | Before Fix | After Fix |
|--------|-----------|-----------|
| Output training steps before first cascade | ~30 (30 epochs x 1 step) | ~1500 (30 epochs x 50 steps) |
| Output training steps after each cascade | 500 + ~10 single steps before next cascade | 1000 in retrain + 50/epoch ongoing |
| Cascade trigger | Loss stagnation (10-epoch window, threshold=0.001) | Correlation threshold (0.0005) after output convergence |
| Residual freshness | Stale (before 500-step retrain) | Fresh (after output convergence) |
| Artificial loss manipulation | Present (1.5x spike) | Removed |
| Expected outcome | Training stalls after first unit | Continuous learning with each unit providing measurable improvement |

---

## Files Requiring Changes

| File | Changes |
|------|---------|
| `/home/pcalnon/Development/python/Juniper/juniper-canopy/src/demo_mode.py` | Restructure `_training_loop()`, `_simulate_training_step()`, `add_hidden_unit()`, `_should_add_cascade_unit()`, `_train_candidate()` |
| `/home/pcalnon/Development/python/Juniper/juniper-canopy/src/canopy_constants.py` | Add constants for `OUTPUT_STEPS_PER_EPOCH`, `CORRELATION_THRESHOLD`, `OUTPUT_RETRAIN_EPOCHS` |

---

## Verification Plan

1. Run the demo and log loss at every epoch; confirm loss decreases monotonically during pure output training phases
2. Confirm that cascade additions are spaced at least 20+ epochs apart (not every 10 epochs)
3. After each cascade addition, confirm loss drops during the retrain phase and continues to decrease afterward
4. Confirm that the demo achieves >90% accuracy on the spiral dataset within 300 epochs (matching the reference implementation's capability)
5. Compare the loss curve shape to a run of `juniper-cascor` on the same spiral dataset
