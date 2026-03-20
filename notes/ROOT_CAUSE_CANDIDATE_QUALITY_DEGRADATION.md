# Root Cause Proposal: Candidate Unit Quality Degradation Across Successive Hidden Unit Additions

**Date**: 2026-03-19
**Author**: Claude Code analysis
**Status**: Proposal
**Severity**: High -- explains the primary training stall after the first hidden unit

---

## Root Cause Hypothesis

Demo training stalls after the first hidden unit because the candidate training budget (8 candidates x 200 steps, no early stopping) is **sufficient to find a good first feature** but **systematically insufficient for subsequent features**, where the residual error has more complex spatial structure, the input dimensionality grows, and the gradient signal through the Pearson correlation objective becomes weaker. Five reinforcing sub-causes produce this degradation:

1. **Candidate pool too small to cover the search space** as input dimensionality grows
2. **200 fixed steps are not enough** for later candidates to converge, and there is no convergence check to detect this
3. **Pearson correlation gradients degrade** as residual magnitude shrinks, despite theoretical scale-invariance
4. **Weight initialization scale is a poor match** for the growing input dimension
5. **A subtle numerical difference** in the correlation computation between the demo and the CasCor reference changes gradient flow

---

## 1. Pool Size: 8 Candidates vs. 50 in CasCor Reference

### Code Locations

- Demo: `demo_mode.py` line 199 -- `pool_size = 8`
- CasCor reference: `constants_candidates.py` line 214 -- `_PROJECT_MODEL_CANDIDATE_POOL_SIZE = 50`

### Analysis

CasCor trains **50 candidates** in parallel and selects the best. The demo trains **8 sequentially**. The candidate pool serves as a random-restart mechanism: each candidate starts from a different random initialization and may converge to a different local optimum on the correlation surface. The probability that at least one candidate finds a high-correlation feature is:

```
P(at_least_one_good) = 1 - (1 - p)^N
```

where `p` is the per-candidate probability of finding a feature with correlation above some usefulness threshold, and `N` is the pool size. For the first hidden unit, the residual error is large and structured (the raw classification error), so `p` is high and even `N=8` works. For subsequent units:

- The residual is smaller and has more complex spatial patterns (the "leftovers" after the easy features are captured).
- `p` drops significantly -- perhaps from 0.5 to 0.1.
- With `N=8`: `P = 1 - 0.9^8 = 0.57` (a coin flip).
- With `N=50`: `P = 1 - 0.9^50 = 0.995` (near certainty).

### Predicted Symptom

Second and third hidden units will have **lower best-candidate correlations** than the first, not because good features don't exist, but because the pool doesn't explore enough initializations to find them.

---

## 2. Fixed 200 Steps with No Convergence Check

### Code Locations

- Demo: `demo_mode.py` line 210 -- `self._train_candidate(unit, steps=200, lr=0.01)`
- Demo: `demo_mode.py` lines 272-294 -- training loop with no early stopping or convergence detection
- CasCor reference: `constants_candidates.py` line 135 -- `_PROJECT_MODEL_CANDIDATE_EPOCHS = 600`
- CasCor reference: `candidate_unit.py` lines 656-719 -- training loop **with** early stopping (patience=30)

### Analysis

The CasCor reference uses **600 epochs with early stopping (patience=30)**. This means it runs up to 600 steps but will terminate earlier if correlation plateaus for 30 consecutive epochs -- an adaptive budget. The demo uses a **hard-coded 200 steps with no convergence check at all**.

For the first hidden unit (2 inputs, `tanh` candidate), 200 Adam steps at lr=0.01 is often sufficient because:
- The input dimension is small (2 features).
- The residual is large and has clear directional structure.
- Adam's adaptive learning rate finds the gradient quickly.

For the second hidden unit (3 inputs: 2 original + 1 hidden output), the problem is harder:
- The input dimension has grown.
- The residual landscape is more complex (the "easy" correlations were already captured).
- The correlation surface may have shallow gradients and require more steps to navigate.

At 200 steps, the candidate may still be on a rising trajectory when training terminates. Without any convergence check, there is no way to know whether the correlation is still improving or has actually plateaued.

**Mathematical estimate of convergence speed**: For Adam with lr=0.01 on a Pearson objective through a `tanh` nonlinearity, the effective gradient magnitude scales as:

```
||grad_corr|| ~ (1/N) * ||d_tanh/dz|| * ||x|| * ||e_centered|| / (std_v * std_e)
```

As hidden units are added: `||e_centered||` decreases (smaller residual), `||x||` grows (more input dimensions to navigate), and the `tanh` derivative may saturate more easily if pre-activations are pushed to larger magnitudes. The net effect is **slower convergence that demands more steps**, precisely the opposite of what the fixed 200-step budget provides.

### Predicted Symptom

Logging the correlation at step 200 for the 2nd and 3rd candidates would show values **still monotonically increasing** -- the training was cut off before convergence.

---

## 3. Pearson Correlation Gradient Degradation Despite Normalization

### Code Locations

- Demo correlation computation: `demo_mode.py` lines 279-285
- CasCor reference correlation: `candidate_unit.py` lines 1033-1087
- CasCor reference gradient computation: `candidate_unit.py` lines 1150-1184

### Analysis

The Pearson correlation coefficient is theoretically **scale-invariant**: multiplying the residual by any constant `c > 0` does not change the correlation value. This is correct for the *forward* computation. However, the **gradient of the correlation with respect to the candidate weights** is *not* scale-invariant in practice due to how it flows through the `tanh` activation.

The full gradient chain is:

```
d(corr)/d(weights) = d(corr)/d(v) * d(v)/d(z) * d(z)/d(weights)
```

where:
- `v = tanh(z)`, `z = x @ weights + bias`
- `d(corr)/d(v)` involves the mean-centered error `e_centered`

Expanding `d(corr)/d(v)` for the Pearson formula:

```
d(corr)/d(v_i) = (1/denom) * [e_centered_i - corr * v_centered_i * (sum(e_centered^2) / sum(v_centered^2))]
                  * sign(corr)
```

The critical term is `e_centered_i`. After the first hidden unit is installed and the output retrained, `||e_centered||` shrinks -- say from magnitude ~0.5 to ~0.1. While the *ratio* `corr = cov / (std_v * std_e)` remains properly normalized, the **individual gradient components** `e_centered_i` that drive the weight updates are 5x smaller. This means:

1. The raw gradient `d(corr)/d(v)` has smaller components.
2. Adam's adaptive step size partially compensates via its second-moment estimate, but only after several steps of accumulation.
3. In the early steps (where Adam's moment estimates are still warming up due to bias correction), the effective update magnitude is significantly smaller for later hidden units.

Additionally, the demo computes correlation via autograd through `(-correlation).backward()` (line 293), which propagates through the full Pearson formula including the `sqrt` in the denominator. When `sum(e_centered^2)` is small, the `sqrt` produces very small denominator terms, and the quotient rule creates **numerically noisy gradients** near zero.

### The Demo vs. CasCor Reference Difference

The demo (`demo_mode.py` lines 279-285):
```python
v_centered = v - v.mean()
e_centered = residual - residual.mean(dim=0)
cov = (v_centered.unsqueeze(1) * e_centered).sum(dim=0)
std_v = torch.sqrt((v_centered**2).sum() + 1e-8)
std_e = torch.sqrt((e_centered**2).sum(dim=0) + 1e-8)
correlation = (cov / (std_v * std_e)).abs().sum()
```

The CasCor reference (`candidate_unit.py` lines 1053-1079):
```python
numerator = torch.sum(norm_output * norm_error)
sum_output_sq = torch.sum(norm_output**2)
sum_error_sq = torch.sum(norm_error**2)
denominator = torch.sqrt(sum_output_sq * sum_error_sq + 1e-8)
correlation_raw = numerator_val / denominator_val
correlation = np.abs(correlation_raw)
```

**Key difference**: The CasCor reference computes the denominator as `sqrt(sum_out^2 * sum_err^2 + eps)`, applying epsilon *inside* the product before the square root. The demo computes it as `sqrt(sum_out^2 + eps) * sqrt(sum_err^2 + eps)`, applying epsilon to each factor separately. These are mathematically different:

```
sqrt(A * B + eps)  !=  sqrt(A + eps) * sqrt(B + eps)
```

When `A` and `B` are both large (first hidden unit, large residual), the difference is negligible. When `B` (`sum_err^2`) is small (later hidden units, small residual), the demo's formulation `sqrt(B + eps)` floors at `sqrt(eps) = 1e-4`, while the CasCor reference's `sqrt(A * B + eps)` can produce a larger denominator (since `A * B` may still be above `eps`). This means the demo's correlation values for later units are **slightly inflated** compared to the reference, and more critically, the **gradient through the separate-sqrt formulation differs**.

Additionally, the CasCor reference detaches the correlation to a Python float (`numerator_val / denominator_val` using `.item()`) and uses `np.abs()` -- the correlation value itself does *not* carry autograd history. The gradient computation happens in a separate `_update_weights_and_bias` method that recomputes the correlation from scratch with `requires_grad=True` parameters (lines 1123-1184). This **recomputation pattern** ensures clean gradient graphs each epoch.

The demo, by contrast, computes correlation once in the forward pass and calls `.backward()` on it directly, accumulating autograd history across the entire 200-step loop. While `optimizer.zero_grad()` clears the parameter gradients, the intermediate tensors in the computation graph are recreated each step (so this is not a graph-accumulation bug), but the single-pass approach means any numerical issues in the correlation computation directly pollute the gradient.

### Predicted Symptom

Gradient norms for candidate weight updates will be **5-10x smaller** for the second hidden unit compared to the first, even though the theoretical correlation signal may be equally strong. Training will appear to make very slow progress.

---

## 4. Weight Initialization Scale vs. Growing Input Dimension

### Code Locations

- Demo: `demo_mode.py` line 203 -- `"weights": torch.randn(input_dim) * 0.1`
- CasCor reference: `candidate_unit.py` line 336 -- `self.weights = torch.randn(self.input_size) * self.random_value_scale` (where `random_value_scale = 0.1`)

### Analysis

Both implementations use `randn * 0.1`. For the first hidden unit, `input_dim = 2`, so the pre-activation is:

```
z = x @ w + b,  where w ~ N(0, 0.01),  x in [-1, 1]
```

Expected magnitude: `E[|z|] ~ sqrt(input_dim) * 0.1 = sqrt(2) * 0.1 = 0.14`. This lands in the near-linear region of `tanh`, producing healthy gradients (tanh'(0.14) ~ 0.98).

For the second hidden unit, `input_dim = 3` (2 original + 1 hidden output). The hidden output is itself a `tanh` value in [-1, 1]. Expected `|z| ~ sqrt(3) * 0.1 = 0.17`. Still reasonable.

For the third hidden unit, `input_dim = 4`, `|z| ~ 0.2`. And so on.

The issue is not catastrophic but **compounds with the other problems**: the fixed `0.1` scale means that as `input_dim` grows, the variance of the pre-activation `z` grows as `0.01 * input_dim`. For the CasCor reference running the spiral problem (which can grow to 10+ hidden units), this means `Var[z] = 0.01 * 12 = 0.12`, so `|z| ~ 0.35`, pushing slightly further into `tanh` non-linearity.

A more principled initialization would scale as `1 / sqrt(input_dim)` (Xavier/Glorot initialization for `tanh`), which for `input_dim = 2` gives `0.71` -- much larger than `0.1`. The current `0.1` initialization is **too conservative**, producing near-zero pre-activations that make the candidate unit behave almost linearly in early training steps. This is a **double-edged sword**: it prevents saturation but also means the candidate can't initially express the nonlinear features that later hidden units need.

For the first hidden unit, the correlation surface is so strongly structured that even a nearly-linear candidate finds a good direction within 200 steps. For later units, the candidate needs to discover a **nonlinear combination** of inputs (that's the whole point of `tanh`), but the conservative initialization starts it in a near-linear regime where the gradient doesn't differentiate between linear and nonlinear solutions.

### Predicted Symptom

Later candidates will tend to converge to **near-linear features** (small weights, operating in the linear regime of `tanh`), which are redundant with the linear output layer. These features provide minimal new information and produce low correlation with the residual.

---

## 5. Exact Correlation Computation Comparison

### Demo Implementation (`demo_mode.py` lines 279-285)

```python
# Multi-output aware: residual shape is (batch, num_outputs)
v_centered = v - v.mean()                                    # Shape: (batch,)
e_centered = residual - residual.mean(dim=0)                  # Shape: (batch, num_outputs)
cov = (v_centered.unsqueeze(1) * e_centered).sum(dim=0)       # Shape: (num_outputs,)
std_v = torch.sqrt((v_centered**2).sum() + 1e-8)              # Scalar
std_e = torch.sqrt((e_centered**2).sum(dim=0) + 1e-8)         # Shape: (num_outputs,)
correlation = (cov / (std_v * std_e)).abs().sum()              # Scalar: sum of abs correlations
```

### CasCor Reference (`candidate_unit.py` lines 1033-1087)

```python
# Single-output path (after slicing in _multi_output_correlation):
output_flat = output.flatten()
residual_error_flat = residual_error.flatten()
output_mean = torch.mean(output_flat)
error_mean = torch.mean(residual_error_flat)
norm_output = output_flat - output_mean
norm_error = residual_error_flat - error_mean
numerator = torch.sum(norm_output * norm_error)
sum_output_sq = torch.sum(norm_output**2)
sum_error_sq = torch.sum(norm_error**2)
denominator = torch.sqrt(sum_output_sq * sum_error_sq + 1e-8)
correlation_raw = numerator.item() / denominator.item()     # <-- detached to Python float
correlation = np.abs(correlation_raw)                        # <-- no autograd
```

### Critical Differences

| Aspect                    | Demo                                                                   | CasCor Reference                                                                             |
|---------------------------|------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| **Epsilon placement**     | `sqrt(A + eps) * sqrt(B + eps)`                                        | `sqrt(A * B + eps)`                                                                          |
| **Gradient flow**         | Correlation has autograd history; `.backward()` directly               | Correlation detached to float; gradients recomputed separately in `_update_weights_and_bias` |
| **Multi-output handling** | Vectorized: computes all outputs simultaneously, sums abs correlations | Iterative: loops through outputs in `_multi_output_correlation`, selects best                |
| **Optimizer**             | Adam (with momentum, adaptive lr)                                      | Manual SGD (`weights -= lr * grad`)                                                          |
| **Objective**             | `(-correlation).backward()` (gradient of sum-of-abs-correlations)      | `-torch.abs(correlation).backward()` on recomputed single-output correlation                 |

The **most impactful difference** is the optimizer choice.
The CasCor reference uses **manual SGD** (`weights -= lr * grad`, line 1198), while the demo uses **Adam**.
Adam's exponential moving averages of first and second moments (beta1=0.9, beta2=0.999) introduce momentum that persists across steps.
For the first hidden unit, this accelerates convergence.
For subsequent hidden units, the **stale momentum from the first 50-100 steps** (when the gradient was pointing in the wrong direction, before the optimizer found the right feature) can actually **slow convergence** by biasing the effective gradient toward an outdated direction.

More concretely: Adam's second-moment estimate `v_t = beta2 * v_{t-1} + (1-beta2) * grad^2` scales the learning rate inversely with historical gradient magnitude.
If early steps had very small gradients (due to the conservative initialization + small residual), Adam's `v_t` will be small, producing **large effective step sizes** that can overshoot.
Conversely, if early steps happened to have large gradients, `v_t` will be large, producing **tiny effective step sizes** that prevent the candidate from escaping a poor local optimum.
Manual SGD avoids both pathologies.

---

## Proposed Fix

### Phase 1: Match CasCor Reference Parameters (Low Risk)

```python
# demo_mode.py, add_hidden_unit method

# Change pool_size from 8 to at least 16 (compromise between 8 and 50 for demo speed)
pool_size = 16  # was 8; CasCor reference uses 50

# Change training steps from 200 to 400 with convergence check
correlation = self._train_candidate(unit, steps=400, lr=0.01)  # was steps=200
```

### Phase 2: Add Early Stopping to Candidate Training (Medium Risk)

```python
# demo_mode.py, _train_candidate method

best_correlation = 0.0
patience_counter = 0
patience_limit = 30  # match CasCor reference

for step in range(steps):
    # ... existing training code ...

    abs_corr = float(correlation.detach())
    if abs_corr > best_correlation + 1e-6:
        best_correlation = abs_corr
        patience_counter = 0
        # Save best weights
        best_weights = weights.detach().clone()
        best_bias = bias.detach().clone()
    else:
        patience_counter += 1
        if patience_counter >= patience_limit:
            break

# Restore best weights
unit["weights"] = best_weights
unit["bias"] = best_bias
```

### Phase 3: Fix Epsilon Placement to Match Reference (Low Risk)

```python
# demo_mode.py, _train_candidate method, lines 283-285

# Before (separate epsilon):
# std_v = torch.sqrt((v_centered**2).sum() + 1e-8)
# std_e = torch.sqrt((e_centered**2).sum(dim=0) + 1e-8)
# correlation = (cov / (std_v * std_e)).abs().sum()

# After (joint epsilon, matching CasCor reference):
sum_v_sq = (v_centered**2).sum()
sum_e_sq = (e_centered**2).sum(dim=0)
denom = torch.sqrt(sum_v_sq * sum_e_sq + 1e-8)
correlation = (cov / denom).abs().sum()
```

### Phase 4: Dimension-Aware Initialization (Medium Risk)

```python
# demo_mode.py, add_hidden_unit method, line 203

# Xavier-style initialization scaled for tanh
init_std = 1.0 / math.sqrt(input_dim)  # was 0.1 fixed
unit = {
    "id": hidden_id,
    "weights": torch.randn(input_dim) * init_std,
    "bias": torch.zeros(1),  # zero-init bias (standard practice)
    "activation_fn": torch.tanh,
}
```

### Phase 5 (Optional): Switch to Manual SGD (Higher Risk, Higher Fidelity)

Replace Adam with manual SGD to match the CasCor reference exactly. This removes the momentum/adaptive-rate pathologies but may slow first-unit convergence slightly.

---

## Expected Impact

| Fix | Expected Effect | Confidence |
|-----|----------------|------------|
| Pool size 8 -> 16+ | 2nd/3rd hidden units find better features; correlation scores for installed units increase by 20-50% | High |
| Steps 200 -> 400 + early stopping | Candidates allowed to converge; no wasted computation when they converge early | High |
| Epsilon placement fix | Marginal improvement in gradient quality for small residuals; prevents potential NaN edge cases | Medium |
| Xavier initialization | Later candidates start in a regime where `tanh` nonlinearity is useful, not redundant with linear output | Medium |
| Switch to manual SGD | Eliminates Adam momentum pathology; matches reference behavior exactly | Medium-Low (may need lr tuning) |

**Combined effect**: Phases 1-3 alone should eliminate the stall after the first hidden unit. The demo should be able to productively install 3-5 hidden units with monotonically decreasing loss, matching the behavior expected from the CasCor algorithm.

---

## Verification Plan

1. **Before any fix**: Add logging to `_train_candidate` to print `(step, abs_corr, grad_norm)` at steps 0, 50, 100, 150, 200 for each candidate. Run the demo and capture the values for hidden units 0, 1, 2. This establishes the baseline and confirms the predicted symptoms.

2. **After each phase**: Re-run the same logging and compare:
   - Does the best correlation for hidden unit 1 increase?
   - Does the gradient norm at step 100 remain above 1e-4?
   - Does the loss curve continue to decrease after each unit addition?

3. **End-to-end**: Run the full demo for 200 epochs and verify that at least 3 hidden units are installed with monotonically decreasing training loss.
