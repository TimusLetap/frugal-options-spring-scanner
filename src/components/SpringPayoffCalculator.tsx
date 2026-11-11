import React, { useState, useEffect } from 'react';
import { Calculator, TrendingUp, ShieldCheck, Zap, Rocket } from 'lucide-react';
import { LongSpringOpportunity } from '../types';

interface SpringPayoffCalculatorProps {
  selectedOption?: LongSpringOpportunity | null;
}

// Cumulative normal distribution approximation for Black-Scholes in browser
function normCdf(x: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const prob =
    d *
    t *
    (0.3193815 +
      t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - prob : prob;
}

function bsPrice(
  spot: number,
  strike: number,
  timeYears: number,
  r: number,
  iv: number,
  optionType: 'CALL' | 'PUT'
): number {
  const intrinsic =
    optionType === 'CALL'
      ? Math.max(0, spot - strike)
      : Math.max(0, strike - spot);
  if (spot <= 0 || strike <= 0 || timeYears <= 0 || iv <= 0) return intrinsic;
  const sqrtT = Math.sqrt(timeYears);
  const d1 =
    (Math.log(spot / strike) + (r + 0.5 * iv * iv) * timeYears) / (iv * sqrtT);
  const d2 = d1 - iv * sqrtT;
  if (optionType === 'CALL') {
    const val = spot * normCdf(d1) - strike * Math.exp(-r * timeYears) * normCdf(d2);
    return Math.max(intrinsic, val);
  } else {
    const val = strike * Math.exp(-r * timeYears) * normCdf(-d2) - spot * normCdf(-d1);
    return Math.max(intrinsic, val);
  }
}

export const SpringPayoffCalculator: React.FC<SpringPayoffCalculatorProps> = ({ selectedOption }) => {
  const [ticker, setTicker] = useState<string>(selectedOption?.Ticker || 'NVDA');
  const [optionType, setOptionType] = useState<'CALL' | 'PUT'>(selectedOption?.Type || 'CALL');
  const [spotPrice, setSpotPrice] = useState<number>(selectedOption?.Spot || 142.50);
  const [strikePrice, setStrikePrice] = useState<number>(selectedOption?.Strike || 160.00);
  const [entryAsk, setEntryAsk] = useState<number>(selectedOption?.Ask || 0.20);
  const [dteDays, setDteDays] = useState<number>(selectedOption?.DTE || 35);
  const [atrDaily, setAtrDaily] = useState<number>(4.80);
  const [currentIvPct, setCurrentIvPct] = useState<number>(selectedOption?.IV || 34.0);
  const [springIvPct, setSpringIvPct] = useState<number>((selectedOption?.Realized_HV || 48.0) * 1.15);
  const [contracts, setContracts] = useState<number>(4);

  useEffect(() => {
    if (selectedOption) {
      setTicker(selectedOption.Ticker);
      setOptionType(selectedOption.Type);
      setSpotPrice(selectedOption.Spot);
      setStrikePrice(selectedOption.Strike);
      setEntryAsk(Math.min(0.25, selectedOption.Ask));
      setDteDays(selectedOption.DTE);
      setCurrentIvPct(selectedOption.IV || 35.0);
      setSpringIvPct(Math.max((selectedOption.Realized_HV || 45.0) * 1.1, (selectedOption.IV || 35.0) * 1.25));
      const estAtr = Math.max(1.0, Math.abs(selectedOption.Spot_For_1_00 - selectedOption.Spot) / Math.max(0.5, selectedOption.ATR_Move_To_1_00 || 2.5));
      setAtrDaily(parseFloat(estAtr.toFixed(2)));
    }
  }, [selectedOption]);

  const safeAsk = Math.max(0.01, Math.min(0.25, entryAsk));
  const totalOutlay = safeAsk * 100 * contracts;

  // Targets for $1.00 and $10.00 intrinsic value
  const spotFor1_00 = optionType === 'CALL' ? strikePrice + 1.0 : Math.max(0.01, strikePrice - 1.0);
  const spotFor10_00 = optionType === 'CALL' ? strikePrice + 10.0 : Math.max(0.01, strikePrice - 10.0);

  const distTo1_00 = Math.abs(spotFor1_00 - spotPrice);
  const distTo10_00 = Math.abs(spotFor10_00 - spotPrice);
  const atrTo1_00 = distTo1_00 / Math.max(0.05, atrDaily);
  const atrTo10_00 = distTo10_00 / Math.max(0.05, atrDaily);

  // Horizon ATR scaling
  const horizonDays = dteDays > 1 ? Math.min(60, dteDays) : 1;
  const horizonAtr = atrDaily * Math.sqrt(horizonDays);
  const remYears = dteDays > 1 ? (Math.max(1, dteDays * 0.65) / 365.0) : (1 / (365 * 3));
  const springIv = Math.max(0.15, springIvPct / 100.0);

  const scenarios = [1, 2, 3, 4, 5].map(mult => {
    const targetSpot =
      optionType === 'CALL'
        ? spotPrice + mult * horizonAtr
        : Math.max(0.01, spotPrice - mult * horizonAtr);
    const val = bsPrice(targetSpot, strikePrice, remYears, 0.045, springIv * (1 + mult * 0.03), optionType);
    const multiple = val / safeAsk;
    const netProfit = (val - safeAsk) * 100 * contracts;
    return {
      mult,
      targetSpot,
      val,
      multiple,
      netProfit,
    };
  });

  const profitAt1_00 = (1.0 - safeAsk) * 100 * contracts;
  const profitAt10_00 = (10.0 - safeAsk) * 100 * contracts;

  return (
    <div className="glass-panel" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '8px', background: 'rgba(0, 242, 254, 0.1)', borderRadius: '8px', color: 'var(--cyan-primary)' }}>
            <Calculator size={22} />
          </div>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
              Asymmetric Spring Payoff Simulator ($0.25 ➔ $1.00 ➔ $10.00+)
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Model volatility coil release + Black-Scholes vanna/gamma repricing across 1x–5x ATR breakout moves
            </p>
          </div>
        </div>
        <span className="ticker-pill">
          Active Model: {ticker} ${strikePrice} {optionType} (@ ${safeAsk.toFixed(2)})
        </span>
      </div>

      <div className="calculator-grid">
        {/* Left column: Parameters */}
        <div>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--cyan-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={16} /> Contract & Volatility Coil Parameters (Strict &le; $0.25 Cap)
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div className="form-group">
              <label className="form-label">Ticker Symbol</label>
              <input type="text" className="form-input" value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())} />
            </div>
            <div className="form-group">
              <label className="form-label">Option Type</label>
              <select className="form-select" value={optionType} onChange={e => setOptionType(e.target.value as 'CALL' | 'PUT')}>
                <option value="CALL">CALL (Bullish Spring)</option>
                <option value="PUT">PUT (Bearish Breakdown)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Contracts Qty</label>
              <input type="number" min="1" max="100" className="form-input" value={contracts} onChange={e => setContracts(parseInt(e.target.value) || 1)} />
            </div>
          </div>

          <div style={{ padding: '12px', background: 'rgba(0, 242, 254, 0.06)', borderRadius: '8px', border: '1px solid rgba(0, 242, 254, 0.2)', marginBottom: '14px' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--cyan-primary)', marginBottom: '8px' }}>
              Frugal Option Contract (&le; $0.25 Entry Mandate)
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Underlying Spot ($)</label>
                <input type="number" step="0.5" className="form-input" value={spotPrice} onChange={e => setSpotPrice(parseFloat(e.target.value) || 0)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Option Strike ($)</label>
                <input type="number" step="0.5" className="form-input" value={strikePrice} onChange={e => setStrikePrice(parseFloat(e.target.value) || 0)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Entry Ask (&le; $0.25)</label>
                <input type="number" step="0.01" min="0.01" max="0.25" className="form-input" value={entryAsk} onChange={e => setEntryAsk(Math.min(0.25, parseFloat(e.target.value) || 0.05))} />
              </div>
            </div>
          </div>

          <div style={{ padding: '12px', background: 'rgba(139, 92, 246, 0.06)', borderRadius: '8px', border: '1px solid rgba(139, 92, 246, 0.2)' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--violet-primary)', marginBottom: '8px' }}>
              Spring Volatility Expansion Profile
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '10px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">DTE (Days)</label>
                <input type="number" min="0" className="form-input" value={dteDays} onChange={e => setDteDays(parseInt(e.target.value) || 0)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Daily ATR ($)</label>
                <input type="number" step="0.25" className="form-input" value={atrDaily} onChange={e => setAtrDaily(parseFloat(e.target.value) || 1)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Entry IV (%)</label>
                <input type="number" step="1" className="form-input" value={currentIvPct} onChange={e => setCurrentIvPct(parseFloat(e.target.value) || 25)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Breakout IV (%)</label>
                <input type="number" step="1" className="form-input" value={springIvPct} onChange={e => setSpringIvPct(parseFloat(e.target.value) || 45)} />
              </div>
            </div>
          </div>
        </div>

        {/* Right column: Asymmetric Payoff Outputs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--emerald-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Rocket size={16} /> Asymmetric Convexity Milestones ($1.00 &amp; $10.00+ Targets)
          </h3>

          <div className="result-box">
            <div className="result-row">
              <span style={{ color: 'var(--text-muted)' }}>Total Capital At Risk ({contracts} contracts @ ${safeAsk.toFixed(2)}):</span>
              <span className="val" style={{ color: 'var(--cyan-primary)', fontSize: '16px' }}>
                ${totalOutlay.toFixed(2)} (Max Loss Capped)
              </span>
            </div>

            <div className="result-row" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '8px' }}>
              <span style={{ color: 'var(--emerald-primary)', fontWeight: 600 }}>
                🎯 $1.00 Contract Target ({(1.0 / safeAsk).toFixed(1)}x Return):
              </span>
              <span className="val" style={{ color: 'var(--emerald-primary)' }}>
                Spot @ ${spotFor1_00.toFixed(2)} ({atrTo1_00.toFixed(1)}x Daily ATR) ➔ +${profitAt1_00.toFixed(0)} Profit
              </span>
            </div>

            <div className="result-row">
              <span style={{ color: 'var(--violet-primary)', fontWeight: 600 }}>
                🚀 $10.00+ Super-Spring Target ({(10.0 / safeAsk).toFixed(0)}x Return):
              </span>
              <span className="val" style={{ color: 'var(--violet-primary)' }}>
                Spot @ ${spotFor10_00.toFixed(2)} ({atrTo10_00.toFixed(1)}x Daily ATR) ➔ +${profitAt10_00.toFixed(0)} Profit
              </span>
            </div>
          </div>

          <div className="result-box">
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
              Black-Scholes Spring Repricing Matrix (Horizon-Scaled ATR + IV Expansion to {springIvPct.toFixed(0)}%)
            </div>
            {scenarios.map(s => (
              <div key={s.mult} className="result-row" style={{ padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ color: 'var(--text-main)' }}>
                  <strong>{s.mult}x Horizon ATR Move</strong> (Spot ➔ ${s.targetSpot.toFixed(2)}):
                </span>
                <span
                  className="val"
                  style={{
                    color:
                      s.val >= 10.0
                        ? 'var(--violet-primary)'
                        : s.val >= 1.0
                        ? 'var(--emerald-primary)'
                        : 'var(--cyan-primary)',
                  }}
                >
                  ${s.val.toFixed(2)} / contract ({s.multiple.toFixed(1)}x | +${s.netProfit.toFixed(0)})
                </span>
              </div>
            ))}
          </div>

          <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.06)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
            <ShieldCheck size={18} style={{ color: 'var(--emerald-primary)', flexShrink: 0 }} />
            <span>
              <strong>Why Coiled Springs Reprice Explosively:</strong> When Bollinger Band Width (BBW) &amp; Historical Volatility Rank (HVR) compress into the bottom quartile, OTM options trade for pennies (&le; $0.25). A directional breakout simultaneously expands Delta (Gamma) and Implied Volatility (Vega/Vanna), creating non-linear 4x ($1.00) to 40x+ ($10.00+) payoffs.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
