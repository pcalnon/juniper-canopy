# Root Cause Proposal: Demo Training Stalls After First Hidden Unit Addition

**File under analysis**: `/home/pcalnon/Development/python/Juniper/juniper-canopy/src/demo_mode.py`
**Date**: 2026-03-19
**Author**: Claude Code analysis

---

## Root Cause Hypothesis

Training stalls after the first hidden unit is added because of a **destructive feedback loop between the post-cascade loss inflation and the convergence detection algorithm**, compounded by a **ghost metric effect** where the 500 internal retraining steps are invisible to the convergence detector, causing it to misread the system's true trajectory.

The stall is not a single bug but the interaction of three co-occurring defects:

1. **Loss inflation poisons the history** -- the `self.current_loss * 1.5` inflation at line 871 is overwritten by the real MSE computation on the very next call to `_simulate_training_step()` (line 704), but the *already-appended* history value from the epoch *before* the cascade addition persists, creating a misleading loss plateau in the trailing window.

2. **500 hidden retraining steps are invisible** -- `add_hidden_unit()` runs 500 `train_output_step()` iterations (line 236-237) that dramatically change the output layer weights but produce zero entries in `network.history["train_loss"]`. The convergence detector's 10-epoch sliding window therefore sees the loss from before the 500-step retraining, followed by the loss from after, with no intermediate record of the rapid improvement that occurred.

3. **Convergence detector triggers a cascade cascade** -- the convergence window of 10 epochs, with threshold 0.001, sees a near-flat region (because the 500-step retraining already converged the new architecture internally) and immediately triggers *another* hidden unit addition, which triggers another 500-step retraining, which again produces flat-looking loss, creating a rapid cascade of unit additions until `max_hidden_units` is reached or the training loop exhausts its ability to improve.

---

## Detailed Analysis

### 1. The `current_loss * 1.5` Inflation (Line 871)

```python
# Line 870-872, inside _training_loop after add_hidden_unit():
self.current_loss = min(1.0, self.current_loss * 1.5)
self.target_loss *= 0.8
```

**Flow analysis:**

| Step | Action | `self.current_loss` | In history? |
|------|--------|---------------------|-------------|
| Epoch N | `_simulate_training_step()` returns (loss, acc) | Real MSE (e.g., 0.15) | Yes -- appended at line 829 |
| Epoch N | `_should_add_cascade_unit()` returns True | 0.15 | -- |
| Epoch N | `add_hidden_unit()` runs 500 internal steps | 0.15 (unchanged) | No |
| Epoch N | Loss inflation: `0.15 * 1.5 = 0.225` | 0.225 | No |
| Epoch N+1 | `_simulate_training_step()` computes real MSE | Overwritten to real value (e.g., 0.08) | Yes |

The inflated value 0.225 is written to `self.current_loss` but is **never recorded in history**. It is immediately overwritten by the real MSE at the start of epoch N+1. This means the inflation at line 871 has **no lasting effect on history** and **no effect on convergence detection**.

However, the inflation *does* affect:

- `get_current_state()` (line 1210) -- returns the inflated value to API consumers between epochs
- `pause()` candidate state save (line 1037) -- would snapshot the inflated value if pause happens during this narrow window

**Verdict**: The inflation is a cosmetic artifact, not the primary cause. But it creates a brief misleading signal to the UI.

### 2. The 500 Invisible Retraining Steps (Lines 236-237)

This is the **primary contributor** to the stall.

`add_hidden_unit()` at line 184 calls `train_output_step()` 500 times:

```python
# Lines 236-237 in MockCascorNetwork.add_hidden_unit():
for _ in range(500):
    self.train_output_step()
```

`train_output_step()` (lines 318-350) performs a real Adam gradient update on the output layer but **never appends to `self.history`**. Only the outer training loop at line 829 appends to history:

```python
# Line 829 in _training_loop():
self.network.history["train_loss"].append(loss)
```

**Consequence**: The convergence detector at `_should_add_cascade_unit()` (lines 751-780) examines the last 10 entries in `network.history["train_loss"]`:

```python
# Lines 773-777:
if conv_enabled and len(self.network.history["train_loss"]) >= 10:
    recent = list(self.network.history["train_loss"])[-10:]
    improvement = recent[0] - recent[-1]
    if improvement < conv_threshold:
        return True
```

After the 500-step retraining, the network has already extracted most of the available improvement from the new hidden unit. The first epoch after the cascade produces a loss that is near the *converged floor* of the new architecture. Subsequent epochs show only marginal improvement. The convergence detector's 10-epoch window fills with near-identical values and triggers **another cascade addition** within 10 epochs.

**Mathematical demonstration:**

Suppose before unit addition, the 10-epoch history is:

```text
[0.18, 0.17, 0.165, 0.162, 0.160, 0.158, 0.157, 0.156, 0.155, 0.154]
improvement = 0.18 - 0.154 = 0.026  (> 0.001, so no trigger)
```

The 500-step retraining converges the output layer to approximately its new floor, say 0.082. Post-cascade epochs then look like:

```text
[0.082, 0.081, 0.0808, 0.0805, 0.0803, 0.0801, 0.0800, 0.0799, 0.0798, 0.0797]
improvement = 0.082 - 0.0797 = 0.0023  (barely > 0.001)
```

By epoch 12-15 post-cascade:

```text
improvement = 0.0801 - 0.0795 = 0.0006  (< 0.001, TRIGGERS another cascade)
```

The system adds a second hidden unit, which again runs 500 invisible retraining steps, and the pattern repeats. Each successive hidden unit provides diminishing returns, so the convergence window gets tighter, and cascades fire faster.

### 3. `target_loss` Is Dead Code

`self.target_loss` is:

- Initialized to 0.1 (line 391)
- Multiplied by 0.8 after each cascade (line 872)
- Reset to 0.1 on full reset (line 982)
- **Never read** in any conditional, comparison, or output

It is pure dead code. It has no effect on training behavior, convergence detection, or UI display. It appears to be a vestige of an earlier design where training would stop when `current_loss < target_loss`.

### 4. Synthetic Validation Metrics Mask True State

```python
# Line 820-821:
val_loss = loss * 1.1 + np.random.randn() * 0.01
val_accuracy = accuracy * 0.95 + np.random.randn() * 0.01
```

The validation loss is derived from the training loss with a fixed 10% inflation plus Gaussian noise (mean 0, std 0.01). This creates several problems:

- **No overfitting signal**: Real validation loss diverges from training loss when the model overfits. Here, `val_loss` is permanently coupled to `train_loss` with a constant ratio, so the UI can never show the characteristic overfitting pattern (train loss dropping while val loss rises).

- **False smoothness**: The noise term `np.random.randn() * 0.01` has std=0.01 regardless of the loss scale. When loss is 0.08, a perturbation of 0.01 is 12.5% -- quite noisy. When loss is 0.5, it is only 2% -- deceptively smooth. This inverts the expected signal-to-noise relationship.

- **Negative validation loss possible**: When `loss` is small (e.g., 0.02), `val_loss = 0.02 * 1.1 + np.random.randn() * 0.01 = 0.022 + noise`. With ~2.3% probability, `np.random.randn()` returns a value below -2.2, producing a negative validation loss. MSE loss cannot be negative, so this would display physically impossible values.

- **Masking the stall**: Because `val_loss` tracks `train_loss` mechanically, a user watching the dashboard cannot tell from validation metrics whether the model is genuinely improving or merely rearranging parameters. The synthetic val_loss will look "healthy" (slightly above train_loss, gently noisy) even when the model is stalled.

### 5. `output_layer.eval()` / `.train()` Toggle (Lines 699-701)

```python
# Lines 699-701 in _simulate_training_step():
self.network.output_layer.eval()
predictions = self.network.forward(self.network.train_x)
self.network.output_layer.train()
```

`nn.Linear` has **no mode-dependent behavior**. Unlike `nn.Dropout` or `nn.BatchNorm`, `nn.Linear` computes identical outputs in both `train()` and `eval()` modes. The `.eval()` / `.train()` toggle is a no-op here.

However, this is a **latent defect**: if anyone adds `nn.Dropout` or `nn.BatchNorm` to the mock network in the future, the `eval()` call would become semantically meaningful, and the current code structure of wrapping only `output_layer` (not the full network) in eval mode would miss hidden units containing such layers.

**Verdict**: No effect on current behavior. No contribution to the stall.

### 6. `is_candidate_phase` and `_simulate_candidate_pool()` (Lines 806-814)

```python
# Lines 806-814:
is_candidate_phase = self.current_epoch > 0 and self.current_epoch % 5 == 0
if is_candidate_phase:
    self.state_machine.set_phase(TrainingPhase.CANDIDATE)
    self._simulate_candidate_pool()
else:
    self.state_machine.set_phase(TrainingPhase.OUTPUT)
    if self.candidate_pool:
        self.candidate_pool.update_pool(status="Inactive")
        self.candidate_pool.clear()
```

Every 5th epoch is marked as a "candidate phase." However, `_simulate_candidate_pool()` (lines 715-749) only generates **synthetic candidate data** with random correlations (`np.random.uniform(0.4, 0.9)`) and pushes it to the `CandidatePool` for UI display. It does **not** affect training: the actual gradient step (`_simulate_training_step()`) executes regardless of `is_candidate_phase` (line 817 runs unconditionally).

The candidate pool simulation is cosmetic -- it populates the candidate pool panel in the dashboard. It has no effect on the training loop, convergence detection, or cascade decisions.

**But there is a subtle timing interaction**: When `is_candidate_phase` is True AND `_should_add_cascade_unit()` is also True (both can fire on the same epoch if `current_epoch % 5 == 0` aligns with the cascade schedule), the FSM phase is set to CANDIDATE, then a real hidden unit is added. This adds a hidden unit while the FSM reports being in "candidate" phase -- a state inconsistency that could confuse the UI but does not cause the stall.

### 7. History Records Manipulated vs. True Values

The loss value recorded in history at line 829:

```python
self.network.history["train_loss"].append(loss)
```

...uses the `loss` variable returned from `_simulate_training_step()`, which is the **real MSE** computed at line 703-704:

```python
mse = ((predictions - self.network.train_y) ** 2).mean()
self.current_loss = float(mse)
```

This is the true network performance metric. The history does NOT record the inflated `current_loss * 1.5` value because:

1. The `loss` local variable is captured from `_simulate_training_step()` return at line 817
2. The inflation at line 871 modifies `self.current_loss` but NOT the local `loss` variable
3. History append at line 829 uses the local `loss` (which was set before the cascade addition code runs)

**However**, there is still a disconnect: the `loss` appended to history is the loss **before** the cascade's 500-step retraining. The network has already substantially changed by the time the next epoch runs, but the recorded loss does not reflect the post-retraining state. This means the history shows:

```text
[..., loss_before_cascade, loss_after_500_steps_of_next_architecture, ...]
```

The jump between consecutive history entries can be large (either up or down), creating an artificial discontinuity that confuses convergence detection.

---

## Predicted Symptoms

1. **Rapid cascade additions**: After the first hidden unit, additional units are added every 10-15 epochs instead of the expected 30 (the `cascade_every` fallback), because convergence detection fires prematurely.

2. **Loss plateau appearance**: The dashboard shows a loss curve that flattens within 10-15 epochs after each cascade addition, giving the appearance of stalling, because the 500-step retraining already extracted the available improvement.

3. **Hidden unit count climbs quickly**: The network reaches `max_hidden_units` (20) much sooner than the 600 epochs (20 units * 30 epochs/unit) that the fixed-schedule fallback would require.

4. **Final loss is not significantly better**: Despite adding many hidden units, final loss is not dramatically lower than the 1-2 hidden unit level, because each unit is installed at a point where the convergence detector has already declared the previous architecture exhausted.

5. **Validation loss tracks training loss perfectly**: No overfitting signal is ever visible, regardless of model complexity, making it impossible to diagnose whether the stall is due to underfitting or overfitting.

---

## Proposed Fix

### Fix 1: Record loss after the 500-step retraining (Primary fix)

After `add_hidden_unit()` completes, immediately compute and record the post-retraining loss. This gives the convergence detector accurate data about the new architecture's starting point.

```python
# In _training_loop(), after the add_hidden_unit() block (after line 875):
# Recompute metrics after cascade retraining so convergence detector
# sees the true post-retraining baseline, not the pre-cascade loss.
loss, accuracy = self._simulate_training_step()
with self._lock:
    self.network.history["train_loss"].append(loss)
    self.network.history["train_accuracy"].append(accuracy)
    val_loss = loss * 1.1 + np.random.randn() * 0.01
    val_accuracy = accuracy * 0.95 + np.random.randn() * 0.01
    self.network.history["val_loss"].append(val_loss)
    self.network.history["val_accuracy"].append(val_accuracy)
```

### Fix 2: Add a convergence cooldown after cascade additions

Prevent the convergence detector from firing for N epochs after a cascade addition, giving the new architecture time to demonstrate its improvement trajectory.

```python
# Add to DemoMode.__init__():
self._cascade_cooldown_remaining = 0

# In _should_add_cascade_unit():
if self._cascade_cooldown_remaining > 0:
    self._cascade_cooldown_remaining -= 1
    return False

# In _training_loop(), after add_hidden_unit():
self._cascade_cooldown_remaining = 15  # Cooldown for 15 epochs
```

### Fix 3: Remove the dead `current_loss * 1.5` inflation and `target_loss`

```python
# Remove lines 871-872 entirely:
# self.current_loss = min(1.0, self.current_loss * 1.5)  # DELETE
# self.target_loss *= 0.8                                 # DELETE

# Remove target_loss from __init__ (line 391) and _reset_state_and_history (line 982)
```

### Fix 4: Fix synthetic validation metrics

```python
# Replace line 820-821 with scale-aware noise and non-negative clamping:
val_loss = max(0.0, loss * (1.1 + np.random.randn() * 0.02))
val_accuracy = min(1.0, max(0.0, accuracy * 0.95 + np.random.randn() * 0.005))
```

---

## Expected Impact

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| Epochs between cascade additions | 10-15 (premature convergence detection) | 30+ (convergence detector sees real improvement trajectory) |
| Time to reach `max_hidden_units` | ~150-200 epochs | ~500-600 epochs |
| Final loss at 20 hidden units | Similar to 3-4 unit level (rapid cascade exhausts easy gains) | Progressively lower with each unit |
| Loss curve appearance | Flat plateaus with discontinuities | Smooth exponential decay segments between cascades |
| Validation metric realism | Mechanically coupled, can go negative | Scale-appropriate noise, always non-negative |

The primary fix (recording post-retraining loss) combined with the convergence cooldown will break the positive feedback loop that causes premature cascade triggering. The convergence detector will see the true improvement trajectory of each architecture, allowing each hidden unit to contribute meaningful capacity before the next is added.
