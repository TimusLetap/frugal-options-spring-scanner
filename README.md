# 🚀 Frugal Options Spring Scanner (`<= $0.25` ➔ `$1.00` / `$10.00+`)

**High-Confidence 0DTE & Long Options Spring Scanner** built by unifying and extending [`TimusLetap/Frugal_Trader`](https://github.com/TimusLetap/Frugal_Trader) and [`TimusLetap/options-ticker-universe`](https://github.com/TimusLetap/options-ticker-universe).

Scans option chains across **0DTE (Intraday)**, **Swing (7–60 DTE)**, and **LEAPS / Long-Dated (60–730 DTE)** horizons for **statistically undervalued contracts costing `$0.25` or less (`<= $25` per contract)** on stocks in confirmed **Volatility Coils ("Spring Setups")** with asymmetric convexity to expand to **`$1.00` (4x–20x)** or **`$10.00+` (40x–100x+)** in value.

---

## ✨ Key Capabilities

1. **Strict `<= $0.25` Frugal Pricing Mandate**
   - Every candidate option contract is strictly capped at `$0.25` (`$25` max risk per contract) with tight bid-ask spread filters (`<= $0.03` on sub-`$0.10` quotes, `<= $0.05` on `$0.11–$0.25` quotes).
2. **4-Layer Volatility Spring Detection Engine (`scoring.py`)**
   - **Layer 1 (Volatility Coil & TTM Squeeze):** Bollinger Band Width (`BBW`) percentile (`<= 25th–30th %ile`), **TTM Keltner Channel Squeeze** (Bollinger Bands inside `1.5x ATR` Keltner Channels), and **Historical Volatility Rank (`HVR`)** from `Frugal_Trader`.
   - **Layer 2 (EMA Ribbon Trend & Slope):** EMA 8 / 20 / 50 / 100 alignment and directional slope.
   - **Layer 3 (Relative Strength & Volume Ignition):** Multi-horizon momentum and volume surge ratio.
   - **Layer 4 (RSI Coiled Launchpad):** 14-day RSI poised in the breakout launchpad zone.
3. **Option Undervaluation Engine (`evaluate_option_undervaluation`)**
   - Identifies options where **Implied Volatility is cheaper than Realized Historical Volatility (`IV / HV < 1.0`)**, low 52-week `IV_Rank`, and high **Black-Scholes Fair Value Edge** & `Gamma / Ask` convexity per dollar spent.
4. **Asymmetric Payoff & Convexity Modeler (`$0.25` ➔ `$1.00` ➔ `$10.00+`)**
   - Calculates exact underlying spot prices and ATR multiples required to hit **`$1.00` (`Spot_For_1_00`, `ATR_Move_To_1_00`)** and **`$10.00+` (`Spot_For_10_00`, `ATR_Move_To_10_00`)**.
   - Models non-linear Black-Scholes repricing (`Proj_Value_2ATR`, `Proj_Value_3ATR`, `Proj_Value_5ATR`) under a volatility coil breakout where spot moves `2x–5x` horizon-scaled ATR and IV expands to 85th-percentile realized volatility.
5. **Dual-Horizon Scanners + GEX Radar**
   - **0DTE Intraday Spring Scanner (`zero_dte_scanner.py`):** Holiday-aware NYSE calendar engine (`calendar_utils.py`), macro catalyst & earnings flags, dealer Gamma Exposure (`GEX`), and Unusual Options Activity (`UOA`).
   - **Long & LEAPS Spring Scanner (`leaps_scanner.py`):** Multi-week Swing and Long-Dated coiled spring scanner with multi-session persistence tracking (`ConvictionTracker`).
   - **Volatility Coil & Gamma Squeeze Radar (`scanner.py`):** Multiplicative GEX wall magnet and acceleration tracker.
6. **Interactive Web Dashboard (`src/`)**
   - React 19 + TypeScript + Vite **Options Spring Intelligence Terminal** featuring live filtering for `$10.00+ Super-Springs`, `TTM Keltner Squeezes`, `GEX Profile Charts`, and an interactive **`$0.25 -> $1.00 -> $10.00+` Black-Scholes Spring Payoff Simulator**.

---

## 🛠️ Quick Start

### 1. Python Scanner CLI (`uv`)

```bash
# Install dependencies
uv sync

# Run full pipeline (Volatility Coils & GEX + 0DTE Springs <= $0.25 + Long/LEAPS Springs <= $0.25)
uv run python scanner.py --scan all --max-premium 0.25 --force-0dte

# Run only 0DTE Spring Scanner (<= $0.25)
uv run python scanner.py --scan 0dte --max-premium 0.25 --force-0dte

# Run only Long / Swing / LEAPS Spring Scanner (<= $0.25)
uv run python leaps_scanner.py --max-premium 0.25

# Run unit & quantitative test suite
uv run pytest -v
```

### 2. Web Intelligence Dashboard (`npm` / `vite`)

```bash
npm install
npm run dev
```

---

## 📂 Repository Structure

```text
frugal-options-spring-scanner/
├── .github/workflows/
│   ├── ci_tests.yml                  # Automated pytest suite on push/PR
│   └── spring_scanner_schedule.yml   # Scheduled 0DTE & Long Spring scans + Discord alerts
├── config/
│   └── trading_rules.yaml            # $0.25 max premium, $1.00/$10.00+ targets, risk & regime rules
├── core/
│   ├── contract_selector.py          # Delta, spread, and <= $0.25 frugal contract selector
│   ├── conviction_tracker.py         # Multi-day signal persistence tracker (from Frugal_Trader)
│   ├── execution_engine.py           # Bracket order & OCO execution engine
│   ├── paper_trader.py               # Alpaca paper trading integration
│   ├── regime_filter.py              # Eastern Time prime window & midday blackout guardrails
│   └── risk_manager.py               # T+1 settled cash & anti-averaging-down guardrails
├── data/
│   ├── history/                      # Running 0DTE & Long Spring trade logs
│   └── reports/                      # Generated CSV intelligence reports
├── src/                              # React + TypeScript + Chart.js Intelligence Terminal
│   ├── components/
│   │   ├── GexChart.tsx              # Dealer Gamma Exposure strike profile visualizer
│   │   └── SpringPayoffCalculator.tsx# Interactive $0.25 -> $1.00 -> $10.00+ BS simulator
│   ├── App.tsx
│   ├── index.css
│   ├── main.tsx
│   └── types.ts
├── tests/                            # Comprehensive pytest suite (17 unit & quant tests)
├── calendar_utils.py                 # NYSE holiday shifting, macro/earnings catalysts, market regime
├── discord_notifier.py               # Rich Discord webhook embeds with $1.00/$10.00+ targets
├── leaps_scanner.py                  # Long & Swing Spring Scanner (<= $0.25)
├── market_data.py                    # Rate-limited YFinanceProvider, Finviz/13F/NASDAQ scanners
├── scanner.py                        # Unified CLI pipeline orchestrator
├── scoring.py                        # Black-Scholes, Spring Coil Engine, Undervaluation & Payoff Modeler
├── trade_logger.py                   # Running trade log, $1/$10 outcome tracker, paper validation guard
└── zero_dte_scanner.py               # 0DTE Intraday Spring Scanner (<= $0.25)
```
