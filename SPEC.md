# Specification: Frugal Options Spring Scanner Architecture & Guardrails

## 1. Executive Summary & Objective
Synthesize the **Frugal_Trader** multi-layer volatility compression discovery engine and the **options-ticker-universe** quantitative GEX / 0DTE / LEAPS framework into a unified, non-discretionary **0DTE & Long Options Spring Scanner**.

The system discovers **statistically undervalued option contracts costing `$0.25` or less (`<= $25` per contract)** on liquid underlyings in high-confidence **Volatility Coils ("Spring Setups")** with asymmetric convexity to reach **`$1.00` (4x–20x)** or **`$10.00+` (40x–100x+)** upon breakout.

---

## 2. Core Quantitative Mandates

### A. Strict Frugal Pricing Mandate (`<= $0.25`)
- **Maximum Entry Price:** Every surfaced 0DTE, Swing, or LEAPS contract MUST have an entry ask price `0.01 <= Ask <= 0.25` (`$1` to `$25` maximum risk per contract).
- **Tight Spread Enforcement:**
  - Quotes `<= $0.10`: Max bid-ask spread `<= $0.03`.
  - Quotes `$0.11 - $0.25`: Max bid-ask spread `<= $0.05` (0DTE) or `<= $0.08` (Long/LEAPS).

### B. 4-Layer Volatility Spring Detection (`evaluate_spring_setup`)
1. **Layer 1 — Volatility Compression & TTM Keltner Squeeze (`is_in_coil`):**
   - Bollinger Band Width (`BBW`) in the bottom `<= 25th–30th percentile` of its trailing 252-day range, OR
   - **TTM Keltner Channel Squeeze** (20-period Bollinger Bands inside 20-period `1.5x ATR` Keltner Channels), OR
   - **Historical Volatility Rank (`HVR`)** `<= 30%`.
2. **Layer 2 — EMA Ribbon Trend & Slope (`is_trending`):**
   - Directional alignment across EMA 8, EMA 20, EMA 50, and EMA 100 with positive/negative 5-day slope confirmation.
3. **Layer 3 — Relative Strength & Volume Ignition (`has_relative_strength`):**
   - 5-day / 20-day / 6-month momentum outperformance and volume surge vs. 20-day average volume.
4. **Layer 4 — RSI Coiled Launchpad (`has_launchpad_rsi`):**
   - 14-day RSI coiled in the `42 - 68` bullish launchpad (or `32 - 58` bearish breakdown zone).

### C. Option Undervaluation Engine (`evaluate_option_undervaluation`)
- **IV vs. Realized HV Discount (`IV_HV_Ratio`):** Compares option Implied Volatility (`IV`) to trailing 20-day and 60-day Realized Historical Volatility (`HV`). Contracts with `IV / HV < 1.0` are priced cheaper than actual underlying movement.
- **Black-Scholes Theoretical Edge (`BS_Fair_Value` & `BS_Breakout_Vol_Value`):** Prices the contract using realized volatility and 85th-percentile coil-release volatility (`HV_85`).
- **Convexity per Dollar:** Rewards high `Gamma / Ask` and `Vega / Ask`.

### D. Asymmetric Payoff Modeling (`$0.25 -> $1.00 -> $10.00+`)
- **`$1.00` Base Spring Target (`4x+` at `$0.25`):** Computes exact underlying price (`Spot_For_1_00 = Strike ± $1.00`), required `%` move, and `ATR_Move_To_1_00`.
- **`$10.00+` Super-Spring Target (`40x+` at `$0.25`):** Computes exact underlying price (`Spot_For_10_00 = Strike ± $10.00`), required `%` move, and `ATR_Move_To_10_00`.
- **Dynamic Spring Repricing (`Proj_Value_2ATR`, `Proj_Value_3ATR`, `Proj_Value_5ATR`):** Uses Black-Scholes repricing with horizon-scaled ATR moves (`k * ATR * sqrt(horizon)`) and IV expansion to 85th-percentile HV.

---

## 3. Hard Execution Guardrails
1. **Cash Account Rule (T+1 Settlement):** Max allocation `15%` of settled cash (`RiskManager`).
2. **Absolute Anti-Averaging Guardrail:** Blocks any incoming `BUY` order on an underlying with an existing active position (`PermissionError`) or same-day trade log entry.
3. **Regime Time Windows (ET):**
   - `09:45 - 11:15`: Prime Momentum Entry Window.
   - `11:30 - 13:15`: Midday Chop Blackout (new entries blocked).
   - `13:15`: Terminal 0DTE Cutoff.
4. **Paper-Trading Validation Guard:** Requires 8–12 distinct logged cycles before unlocking live capital sizing recommendations.
