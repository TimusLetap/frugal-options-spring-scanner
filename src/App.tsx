import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
import {
  Zap,
  TrendingUp,
  Activity,
  Search,
  Calculator,
  Flame,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Filter
} from 'lucide-react';
import {
  GammaOpportunity,
  LongSpringOpportunity,
  ZeroDteSpringOpportunity,
  ActiveTab
} from './types';
import { SpringPayoffCalculator } from './components/SpringPayoffCalculator';
import { GexChart } from './components/GexChart';

const INITIAL_LONG_SPRINGS: LongSpringOpportunity[] = [
  {
    Ticker: 'NVDA',
    Spot: 142.50,
    Type: 'CALL',
    Horizon: 'Long Swing (45-179d)',
    Strike: 175.0,
    Expiration: '2027-01-15',
    DTE: 65,
    Bid: 0.21,
    Ask: 0.23,
    Mid: 0.22,
    Spread: 0.02,
    Volume: 4820,
    Open_Interest: 19450,
    IV: 34.2,
    Realized_HV: 46.8,
    IV_HV_Ratio: 0.73,
    IV_Rank: 0.18,
    BS_Fair_Value: 0.41,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 89.4,
    Delta_Est: 0.09,
    Contract: 'NVDA270115C00175000',
    Breakeven: 175.23,
    Breakeven_Move_Pct: 23.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 11.4,
    HVR_Pct: 16.2,
    Layers_Confirmed: 4,
    Spring_Score: 93.5,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon (Slope +0.64) + Mom 5d +3.8% / Vol 1.4x + RSI Launchpad (56.2)',
    Spot_For_1_00: 176.0,
    Spot_For_10_00: 185.0,
    ATR_Move_To_1_00: 7.4,
    ATR_Move_To_10_00: 9.4,
    Proj_Value_2ATR: 1.45,
    Proj_Value_3ATR: 4.85,
    Proj_Value_5ATR: 16.40,
    Max_Projected_Value: 16.40,
    Potential_Multiple: 71.3,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 91.2,
    Persistence_Count: 3,
  },
  {
    Ticker: 'TSLA',
    Spot: 328.40,
    Type: 'CALL',
    Horizon: 'Swing Spring (7-44d)',
    Strike: 390.0,
    Expiration: '2026-12-18',
    DTE: 37,
    Bid: 0.22,
    Ask: 0.25,
    Mid: 0.24,
    Spread: 0.03,
    Volume: 6310,
    Open_Interest: 24100,
    IV: 48.5,
    Realized_HV: 62.1,
    IV_HV_Ratio: 0.78,
    IV_Rank: 0.22,
    BS_Fair_Value: 0.44,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 86.8,
    Delta_Est: 0.08,
    Contract: 'TSLA261218C00390000',
    Breakeven: 390.25,
    Breakeven_Move_Pct: 18.8,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 14.2,
    HVR_Pct: 19.5,
    Layers_Confirmed: 4,
    Spring_Score: 91.0,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon (Slope +1.12) + Mom 5d +4.2% / Vol 1.6x + RSI Launchpad (58.4)',
    Spot_For_1_00: 391.0,
    Spot_For_10_00: 400.0,
    ATR_Move_To_1_00: 5.1,
    ATR_Move_To_10_00: 5.8,
    Proj_Value_2ATR: 1.80,
    Proj_Value_3ATR: 6.20,
    Proj_Value_5ATR: 22.50,
    Max_Projected_Value: 22.50,
    Potential_Multiple: 90.0,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 89.6,
    Persistence_Count: 2,
  },
  {
    Ticker: 'COIN',
    Spot: 264.10,
    Type: 'CALL',
    Horizon: 'Long Swing (45-179d)',
    Strike: 330.0,
    Expiration: '2027-01-15',
    DTE: 65,
    Bid: 0.18,
    Ask: 0.21,
    Mid: 0.20,
    Spread: 0.03,
    Volume: 2190,
    Open_Interest: 9840,
    IV: 58.0,
    Realized_HV: 74.5,
    IV_HV_Ratio: 0.78,
    IV_Rank: 0.21,
    BS_Fair_Value: 0.39,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 85.2,
    Delta_Est: 0.07,
    Contract: 'COIN270115C00330000',
    Breakeven: 330.21,
    Breakeven_Move_Pct: 25.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: false,
    BBW_Percentile: 18.0,
    HVR_Pct: 22.4,
    Layers_Confirmed: 3,
    Spring_Score: 84.5,
    Spring_Thesis: 'Volatility Coil (BBW 18%ile, HVR 22%) + Bullish EMA Ribbon + RSI Launchpad (54.1)',
    Spot_For_1_00: 331.0,
    Spot_For_10_00: 340.0,
    ATR_Move_To_1_00: 5.9,
    ATR_Move_To_10_00: 6.7,
    Proj_Value_2ATR: 1.35,
    Proj_Value_3ATR: 5.10,
    Proj_Value_5ATR: 18.90,
    Max_Projected_Value: 18.90,
    Potential_Multiple: 90.0,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 86.4,
    Persistence_Count: 2,
  },
  {
    Ticker: 'PLTR',
    Spot: 58.20,
    Type: 'CALL',
    Horizon: 'LEAPS (180d+)',
    Strike: 75.0,
    Expiration: '2027-06-18',
    DTE: 219,
    Bid: 0.17,
    Ask: 0.20,
    Mid: 0.19,
    Spread: 0.03,
    Volume: 3420,
    Open_Interest: 15800,
    IV: 42.1,
    Realized_HV: 51.0,
    IV_HV_Ratio: 0.83,
    IV_Rank: 0.24,
    BS_Fair_Value: 0.33,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 84.1,
    Delta_Est: 0.11,
    Contract: 'PLTR270618C00075000',
    Breakeven: 75.20,
    Breakeven_Move_Pct: 29.2,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 12.8,
    HVR_Pct: 18.0,
    Layers_Confirmed: 4,
    Spring_Score: 90.2,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon + Mom 5d +2.9% + RSI Launchpad (55.0)',
    Spot_For_1_00: 76.0,
    Spot_For_10_00: 85.0,
    ATR_Move_To_1_00: 7.9,
    ATR_Move_To_10_00: 11.9,
    Proj_Value_2ATR: 1.15,
    Proj_Value_3ATR: 3.40,
    Proj_Value_5ATR: 10.85,
    Max_Projected_Value: 10.85,
    Potential_Multiple: 54.3,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 85.1,
    Persistence_Count: 4,
  },
  {
    Ticker: 'AMD',
    Spot: 148.90,
    Type: 'CALL',
    Horizon: 'Swing Spring (7-44d)',
    Strike: 170.0,
    Expiration: '2026-12-18',
    DTE: 37,
    Bid: 0.14,
    Ask: 0.16,
    Mid: 0.15,
    Spread: 0.02,
    Volume: 2890,
    Open_Interest: 11200,
    IV: 36.4,
    Realized_HV: 44.2,
    IV_HV_Ratio: 0.82,
    IV_Rank: 0.19,
    BS_Fair_Value: 0.28,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 83.7,
    Delta_Est: 0.08,
    Contract: 'AMD261218C00170000',
    Breakeven: 170.16,
    Breakeven_Move_Pct: 14.3,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 9.5,
    HVR_Pct: 14.8,
    Layers_Confirmed: 3,
    Spring_Score: 87.0,
    Spring_Thesis: 'TTM Keltner Squeeze + Volatility Coil (BBW 10%ile) + RSI Launchpad (49.2)',
    Spot_For_1_00: 171.0,
    Spot_For_10_00: 180.0,
    ATR_Move_To_1_00: 5.2,
    ATR_Move_To_10_00: 7.3,
    Proj_Value_2ATR: 1.10,
    Proj_Value_3ATR: 3.65,
    Proj_Value_5ATR: 12.20,
    Max_Projected_Value: 12.20,
    Potential_Multiple: 76.3,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 84.3,
    Persistence_Count: 2,
  },
];

const INITIAL_0DTE_SPRINGS: ZeroDteSpringOpportunity[] = [
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'SPY',
    Option_Type: 'CALL',
    Contract_Symbol: 'SPY261111C00602000',
    Strike: 602.0,
    Spot_Price: 598.20,
    Bid: 0.17,
    Ask: 0.19,
    Spread: 0.02,
    Entry_Ask: 0.19,
    Delta: 0.16,
    Volume: 18420,
    Open_Interest: 9240,
    Vol_OI_Ratio: 1.99,
    IV_Pct: 13.8,
    Realized_HV_Pct: 16.9,
    IV_HV_Ratio: 0.82,
    IV_Rank: 0.18,
    BS_Fair_Value: 0.27,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 86.2,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 14.0,
    Layers_Confirmed: 4,
    Spring_Score: 91.5,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon + Gamma Wall @ $603',
    Dist_ATR_Units: 0.85,
    Spot_For_1_00: 603.0,
    Spot_For_10_00: 612.0,
    ATR_Move_To_1_00: 1.08,
    ATR_Move_To_10_00: 3.10,
    Proj_Value_3ATR: 5.60,
    Proj_Value_5ATR: 14.20,
    Max_Projected_Value: 14.20,
    Potential_Multiple: 74.7,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 14250000,
    Catalyst_Flag: 'Pre-CPI Coiled Spring',
    Opportunity_Score: 90.4,
    Max_Loss_Held_To_Zero: 19.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'QQQ',
    Option_Type: 'CALL',
    Contract_Symbol: 'QQQ261111C00518000',
    Strike: 518.0,
    Spot_Price: 513.40,
    Bid: 0.19,
    Ask: 0.21,
    Spread: 0.02,
    Entry_Ask: 0.21,
    Delta: 0.15,
    Volume: 14200,
    Open_Interest: 6850,
    Vol_OI_Ratio: 2.07,
    IV_Pct: 17.5,
    Realized_HV_Pct: 21.8,
    IV_HV_Ratio: 0.80,
    IV_Rank: 0.20,
    BS_Fair_Value: 0.31,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 85.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 15.2,
    Layers_Confirmed: 4,
    Spring_Score: 89.4,
    Spring_Thesis: 'TTM Keltner Squeeze + Tech Relative Strength + GEX Magnet @ $520',
    Dist_ATR_Units: 0.78,
    Spot_For_1_00: 519.0,
    Spot_For_10_00: 528.0,
    ATR_Move_To_1_00: 0.95,
    ATR_Move_To_10_00: 2.48,
    Proj_Value_3ATR: 6.10,
    Proj_Value_5ATR: 15.80,
    Max_Projected_Value: 15.80,
    Potential_Multiple: 75.2,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 11800000,
    Catalyst_Flag: 'Pre-CPI Coiled Spring',
    Opportunity_Score: 88.9,
    Max_Loss_Held_To_Zero: 21.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'SPY',
    Option_Type: 'PUT',
    Contract_Symbol: 'SPY261111P00593000',
    Strike: 593.0,
    Spot_Price: 598.20,
    Bid: 0.14,
    Ask: 0.16,
    Spread: 0.02,
    Entry_Ask: 0.16,
    Delta: 0.13,
    Volume: 11900,
    Open_Interest: 5400,
    Vol_OI_Ratio: 2.20,
    IV_Pct: 14.9,
    Realized_HV_Pct: 16.9,
    IV_HV_Ratio: 0.88,
    IV_Rank: 0.24,
    BS_Fair_Value: 0.22,
    Valuation_Label: 'UNDERVALUED COIL',
    Undervaluation_Score: 81.4,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 14.0,
    Layers_Confirmed: 3,
    Spring_Score: 82.0,
    Spring_Thesis: 'TTM Keltner Squeeze Breakdown Hedge + Put Gamma Air Pocket below $594',
    Dist_ATR_Units: 1.16,
    Spot_For_1_00: 592.0,
    Spot_For_10_00: 583.0,
    ATR_Move_To_1_00: 1.38,
    ATR_Move_To_10_00: 3.38,
    Proj_Value_3ATR: 4.90,
    Proj_Value_5ATR: 12.80,
    Max_Projected_Value: 12.80,
    Potential_Multiple: 80.0,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 9400000,
    Catalyst_Flag: 'Pre-CPI Coiled Spring',
    Opportunity_Score: 84.7,
    Max_Loss_Held_To_Zero: 16.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
];

const INITIAL_GAMMA_COILS: GammaOpportunity[] = [
  {
    Ticker: 'NVDA',
    Opportunity_Score: 88.4,
    Spring_Score: 93.5,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 11.4,
    HVR_Pct: 16.2,
    Layers_Confirmed: 4,
    Tier: '🔥 High Conviction Spring',
    Trend: '^^',
    Spot_Price: 142.50,
    ATR_14: 4.52,
    Expiration: '2026-11-13',
    Days_to_Expiration: 2,
    Put_Call_OI_Ratio: 0.52,
    Gamma_Wall_Strike: 150.0,
    Gamma_Dollars_at_Wall: 28400000,
    'Gamma_Concentration_%': 38.4,
    'Gamma_Fuel_vs_ADV_%': 22.1,
    'Distance_to_Wall_%': 5.3,
    '5_Day_Performance_%': 3.8,
    Days_to_Cover: 1.8,
    'Short_Pct_Float_%': 1.4,
    Has_Short_Data: true,
    Acceleration: 0.72,
    Recommended_Strike: 155.0,
    Recommended_Premium: 0.21,
    Breakeven_Price: 155.21,
    Thesis: '[TTM Keltner Squeeze + Bullish EMA Ribbon] NVDA needs a 5.3% move to reach the $150.00 Gamma Wall ($28.4M per 1% move).',
  },
  {
    Ticker: 'TSLA',
    Opportunity_Score: 86.1,
    Spring_Score: 91.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 14.2,
    HVR_Pct: 19.5,
    Layers_Confirmed: 4,
    Tier: '🔥 High Conviction Spring',
    Trend: '^^',
    Spot_Price: 328.40,
    ATR_14: 12.30,
    Expiration: '2026-11-13',
    Days_to_Expiration: 2,
    Put_Call_OI_Ratio: 0.58,
    Gamma_Wall_Strike: 350.0,
    Gamma_Dollars_at_Wall: 34100000,
    'Gamma_Concentration_%': 41.2,
    'Gamma_Fuel_vs_ADV_%': 24.8,
    'Distance_to_Wall_%': 6.6,
    '5_Day_Performance_%': 4.2,
    Days_to_Cover: 2.4,
    'Short_Pct_Float_%': 3.1,
    Has_Short_Data: true,
    Acceleration: 0.68,
    Recommended_Strike: 365.0,
    Recommended_Premium: 0.24,
    Breakeven_Price: 365.24,
    Thesis: '[TTM Keltner Squeeze + Momentum Surge] TSLA needs a 6.6% move to reach the $350.00 Gamma Wall ($34.1M per 1% move).',
  },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('long_springs');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [only10DollarTarget, setOnly10DollarTarget] = useState<boolean>(false);
  const [onlyTtmSqueeze, setOnlyTtmSqueeze] = useState<boolean>(false);

  const [longSpringData, setLongSpringData] = useState<LongSpringOpportunity[]>(INITIAL_LONG_SPRINGS);
  const [zeroDteData, setZeroDteData] = useState<ZeroDteSpringOpportunity[]>(INITIAL_0DTE_SPRINGS);
  const [gammaData, setGammaData] = useState<GammaOpportunity[]>(INITIAL_GAMMA_COILS);

  const [selectedGamma, setSelectedGamma] = useState<GammaOpportunity | null>(INITIAL_GAMMA_COILS[0]);
  const [selectedOptionForSim, setSelectedOptionForSim] = useState<LongSpringOpportunity | null>(INITIAL_LONG_SPRINGS[0]);

  const loadAllReports = async () => {
    try {
      const longRes = await fetch('/data/reports/long_spring_opportunities.csv');
      if (longRes.ok) {
        const text = await longRes.text();
        const parsed = Papa.parse<LongSpringOpportunity>(text, { header: true, dynamicTyping: true });
        const valid = parsed.data.filter(r => r.Ticker && r.Ask <= 0.25);
        if (valid.length > 0) setLongSpringData(valid);
      }

      const zeroRes = await fetch('/data/reports/0dte_spring_opportunities.csv');
      if (zeroRes.ok) {
        const text = await zeroRes.text();
        const parsed = Papa.parse<ZeroDteSpringOpportunity>(text, { header: true, dynamicTyping: true });
        const valid = parsed.data.filter(r => r.Ticker && r.Ask <= 0.25);
        if (valid.length > 0) setZeroDteData(valid);
      }

      const gammaRes = await fetch('/data/reports/gamma_squeeze_potential.csv');
      if (gammaRes.ok) {
        const text = await gammaRes.text();
        const parsed = Papa.parse<GammaOpportunity>(text, { header: true, dynamicTyping: true });
        const valid = parsed.data.filter(r => r.Ticker);
        if (valid.length > 0) {
          setGammaData(valid);
          setSelectedGamma(valid[0]);
        }
      }
    } catch {
      // Uses initial quantitative datasets when running standalone
    }
  };

  useEffect(() => {
    loadAllReports();
  }, []);

  const filteredLongSprings = longSpringData.filter(d => {
    const matchesSearch = !searchQuery || d.Ticker?.toLowerCase().includes(searchQuery.toLowerCase());
    const matches10 = !only10DollarTarget || d.Can_Reach_10_00 || d.Proj_Value_5ATR >= 10.0;
    const matchesSqueeze = !onlyTtmSqueeze || d.Is_TTM_Squeeze || d.Is_In_Coil;
    return matchesSearch && matches10 && matchesSqueeze && d.Ask <= 0.25;
  });

  const filtered0Dte = zeroDteData.filter(d => {
    const matchesSearch = !searchQuery || d.Ticker?.toLowerCase().includes(searchQuery.toLowerCase());
    const matches10 = !only10DollarTarget || d.Proj_Value_5ATR >= 10.0;
    return matchesSearch && matches10 && d.Ask <= 0.25;
  });

  const filteredGamma = gammaData.filter(d =>
    !searchQuery || d.Ticker?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const superSpringCount =
    longSpringData.filter(d => d.Proj_Value_5ATR >= 10.0).length +
    zeroDteData.filter(d => d.Proj_Value_5ATR >= 10.0).length;

  const maxMultiple = Math.max(
    ...longSpringData.map(d => d.Potential_Multiple || 0),
    ...zeroDteData.map(d => d.Potential_Multiple || 0),
    40
  );

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="glass-panel top-header">
        <div className="logo-group">
          <div className="logo-badge">FRUGAL SPRING</div>
          <div>
            <h1 className="brand-title">Options Spring Intelligence Terminal (&le; $0.25 ➔ $1.00 / $10.00+)</h1>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
              Multi-Layer Volatility Coils (BBW + Keltner Squeeze + HVR) • Undervalued IV &lt; HV • 0DTE &amp; Long Asymmetric Convexity
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="badge-live">
            <span className="pulsing-dot"></span>
            STRICT &le; $0.25 FRUGAL MANDATE ACTIVE
          </div>

          <button className="btn-action" onClick={loadAllReports}>
            <RefreshCw size={14} /> Refresh Scan Data
          </button>
        </div>
      </header>

      {/* KPI Overview Grid */}
      <div className="stats-grid">
        <div className="glass-panel stat-card">
          <span className="stat-label">Strict Max Entry Cost</span>
          <span className="stat-value" style={{ color: 'var(--emerald-primary)' }}>&le; $0.25</span>
          <span className="stat-sub"><ShieldCheck size={14} /> Max $25 risk per contract</span>
        </div>

        <div className="glass-panel stat-card">
          <span className="stat-label">🎯 $1.00+ Base Spring Setups</span>
          <span className="stat-value">{longSpringData.length + zeroDteData.length} Contracts</span>
          <span className="stat-sub"><Zap size={14} /> 4x–20x Repricing on 2x–3x ATR Move</span>
        </div>

        <div className="glass-panel stat-card">
          <span className="stat-label">🚀 $10.00+ Super-Spring Setups</span>
          <span className="stat-value" style={{ color: 'var(--violet-primary)' }}>{superSpringCount} Contracts</span>
          <span className="stat-sub" style={{ color: 'var(--cyan-primary)' }}>
            <Rocket size={14} /> 40x–90x+ Convexity on Coiled Breakouts
          </span>
        </div>

        <div className="glass-panel stat-card">
          <span className="stat-label">Peak Modeled Multiple</span>
          <span className="stat-value" style={{ color: 'var(--cyan-primary)' }}>{maxMultiple.toFixed(1)}x</span>
          <span className="stat-sub"><TrendingUp size={14} /> Undervalued IV &lt; Realized HV</span>
        </div>
      </div>

      {/* Navigation Tab Bar */}
      <div className="nav-tab-bar">
        <button
          className={`tab-btn ${activeTab === 'long_springs' ? 'active' : ''}`}
          onClick={() => setActiveTab('long_springs')}
        >
          <Rocket size={16} /> 🚀 Long &amp; Swing Spring Setups &le; $0.25 ({filteredLongSprings.length})
        </button>

        <button
          className={`tab-btn ${activeTab === '0dte_springs' ? 'active' : ''}`}
          onClick={() => setActiveTab('0dte_springs')}
        >
          <Flame size={16} /> 🔥 0DTE Intraday Spring Setups &le; $0.25 ({filtered0Dte.length})
        </button>

        <button
          className={`tab-btn ${activeTab === 'gamma_coils' ? 'active' : ''}`}
          onClick={() => setActiveTab('gamma_coils')}
        >
          <Activity size={16} /> 🌀 Volatility Coils &amp; GEX Magnet Radar ({filteredGamma.length})
        </button>

        <button
          className={`tab-btn ${activeTab === 'calculator' ? 'active' : ''}`}
          onClick={() => setActiveTab('calculator')}
        >
          <Calculator size={16} /> 🧮 $0.25 ➔ $1.00 ➔ $10.00+ Payoff Simulator
        </button>
      </div>

      {/* Filter & Search Bar */}
      {activeTab !== 'calculator' && (
        <div className="glass-panel controls-bar">
          <div className="search-input-wrapper">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Filter by ticker (e.g., NVDA, TSLA, SPY, QQQ, PLTR)..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button
              className={`btn-action ${only10DollarTarget ? 'btn-primary' : ''}`}
              onClick={() => setOnly10DollarTarget(!only10DollarTarget)}
            >
              <Rocket size={14} /> 🚀 $10.00+ Super-Springs Only (40x+)
            </button>
            <button
              className={`btn-action ${onlyTtmSqueeze ? 'btn-primary' : ''}`}
              onClick={() => setOnlyTtmSqueeze(!onlyTtmSqueeze)}
            >
              <Filter size={14} /> 🌀 Coiled / TTM Squeeze Only
            </button>
          </div>
        </div>
      )}

      {/* TAB 1: LONG & SWING SPRING SETUPS (<= $0.25) */}
      {activeTab === 'long_springs' && (
        <div className="glass-panel table-container">
          <table className="quant-table">
            <thead>
              <tr>
                <th>Ticker &amp; Horizon</th>
                <th>Contract &amp; Exp</th>
                <th>Entry Ask (&le;$0.25)</th>
                <th>Undervaluation (IV vs HV)</th>
                <th>Spring Coil Thesis</th>
                <th>🎯 $1.00 Target (4x+)</th>
                <th>🚀 $10.00 Target (40x+)</th>
                <th>3x / 5x ATR Value</th>
                <th>Confidence</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredLongSprings.map((row, idx) => (
                <tr key={`${row.Ticker}-${row.Strike}-${idx}`}>
                  <td>
                    <span className="ticker-pill">{row.Ticker}</span>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Spot: ${row.Spot?.toFixed(2)} • {row.Horizon || `${row.DTE}d`}
                    </div>
                  </td>
                  <td>
                    <strong style={{ color: row.Type === 'CALL' ? 'var(--emerald-primary)' : 'var(--rose-primary)' }}>
                      ${row.Strike} {row.Type}
                    </strong>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      Exp: {row.Expiration} ({row.DTE} DTE)
                    </div>
                  </td>
                  <td>
                    <span style={{ color: 'var(--cyan-primary)', fontWeight: 700, fontSize: '15px' }}>
                      ${row.Ask?.toFixed(2)}
                    </span>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      Fair BS: ${row.BS_Fair_Value?.toFixed(2) || row.Mid?.toFixed(2)}
                    </div>
                  </td>
                  <td>
                    <span className="tier-badge tier-strong">{row.Valuation_Label || 'UNDERVALUED'}</span>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      IV: {row.IV}% vs HV: {row.Realized_HV || 45}% ({row.IV_HV_Ratio || 0.8}x)
                    </div>
                  </td>
                  <td style={{ maxWidth: '280px', fontFamily: 'var(--font-sans)', fontSize: '12px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--amber-primary)', marginBottom: '2px' }}>
                      {row.Is_TTM_Squeeze ? '🔥 TTM Keltner Squeeze' : '🌀 Volatility Coil'} ({row.Layers_Confirmed || 3}/4 Layers)
                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                      BBW {row.BBW_Percentile}%ile • HVR {row.HVR_Pct}%
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--emerald-primary)', fontWeight: 700 }}>
                      Spot @ ${row.Spot_For_1_00?.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {row.ATR_Move_To_1_00}x Daily ATR
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--violet-primary)', fontWeight: 700 }}>
                      Spot @ ${row.Spot_For_10_00?.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {row.ATR_Move_To_10_00}x Daily ATR
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--emerald-primary)', fontWeight: 700 }}>
                      3xATR: ${row.Proj_Value_3ATR?.toFixed(2)}
                    </div>
                    <div style={{ color: 'var(--violet-primary)', fontWeight: 700 }}>
                      5xATR: ${row.Proj_Value_5ATR?.toFixed(2)} ({row.Potential_Multiple}x)
                    </div>
                  </td>
                  <td>
                    <span className="tier-badge tier-high" style={{ fontSize: '13px' }}>
                      {row.Opportunity_Score?.toFixed(1)}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn-action"
                      onClick={() => {
                        setSelectedOptionForSim(row);
                        setActiveTab('calculator');
                      }}
                    >
                      <Calculator size={13} /> Simulate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 2: 0DTE INTRADAY SPRING SETUPS (<= $0.25) */}
      {activeTab === '0dte_springs' && (
        <div className="glass-panel table-container">
          <table className="quant-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>0DTE Contract</th>
                <th>Entry Ask (&le;$0.25)</th>
                <th>IV vs HV &amp; Fair Value</th>
                <th>Spring &amp; Catalyst</th>
                <th>🎯 $1.00 Target (4x+)</th>
                <th>🚀 $10.00 Target (40x+)</th>
                <th>3x / 5x ATR Repricing</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {filtered0Dte.map((row, idx) => (
                <tr key={`${row.Contract_Symbol}-${idx}`}>
                  <td>
                    <span className="ticker-pill">{row.Ticker}</span>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Spot: ${row.Spot_Price?.toFixed(2)}
                    </div>
                  </td>
                  <td>
                    <strong style={{ color: row.Option_Type === 'CALL' ? 'var(--emerald-primary)' : 'var(--rose-primary)' }}>
                      ${row.Strike} {row.Option_Type}
                    </strong>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      Exp: {row.Expiration_Date} • Dist: {row.Dist_ATR_Units}x ATR
                    </div>
                  </td>
                  <td>
                    <span style={{ color: 'var(--cyan-primary)', fontWeight: 700, fontSize: '15px' }}>
                      ${row.Ask?.toFixed(2)}
                    </span>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      Max Loss: ${row.Max_Loss_Held_To_Zero?.toFixed(0)}
                    </div>
                  </td>
                  <td>
                    <span className="tier-badge tier-strong">{row.Valuation_Label || 'UNDERVALUED'}</span>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Fair BS: ${row.BS_Fair_Value?.toFixed(2)} • Vol/OI: {row.Vol_OI_Ratio}x
                    </div>
                  </td>
                  <td style={{ fontFamily: 'var(--font-sans)', fontSize: '12px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--amber-primary)' }}>
                      {row.Spring_Thesis}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--cyan-primary)' }}>
                      Catalyst: {row.Catalyst_Flag}
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--emerald-primary)', fontWeight: 700 }}>
                      Spot @ ${row.Spot_For_1_00?.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {row.ATR_Move_To_1_00}x ATR
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--violet-primary)', fontWeight: 700 }}>
                      Spot @ ${row.Spot_For_10_00?.toFixed(2)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      {row.ATR_Move_To_10_00}x ATR
                    </div>
                  </td>
                  <td>
                    <div style={{ color: 'var(--emerald-primary)', fontWeight: 700 }}>
                      3xATR: ${row.Proj_Value_3ATR?.toFixed(2)}
                    </div>
                    <div style={{ color: 'var(--violet-primary)', fontWeight: 700 }}>
                      5xATR: ${row.Proj_Value_5ATR?.toFixed(2)} ({row.Potential_Multiple}x)
                    </div>
                  </td>
                  <td>
                    <span className="tier-badge tier-high" style={{ fontSize: '13px' }}>
                      {row.Opportunity_Score?.toFixed(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 3: VOLATILITY COILS & GAMMA SQUEEZE RADAR */}
      {activeTab === 'gamma_coils' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {selectedGamma && (
            <GexChart
              ticker={selectedGamma.Ticker}
              spotPrice={selectedGamma.Spot_Price}
              wallStrike={selectedGamma.Gamma_Wall_Strike}
            />
          )}

          <div className="glass-panel table-container">
            <table className="quant-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Composite Score</th>
                  <th>Spring Coil Profile</th>
                  <th>Spot ➔ Gamma Wall</th>
                  <th>Wall GEX ($M)</th>
                  <th>Best &le;$0.25 Strike</th>
                  <th>Thesis</th>
                </tr>
              </thead>
              <tbody>
                {filteredGamma.map((row, idx) => (
                  <tr
                    key={`${row.Ticker}-${idx}`}
                    onClick={() => setSelectedGamma(row)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <span className="ticker-pill">{row.Ticker}</span>
                    </td>
                    <td>
                      <span className="tier-badge tier-high">{row.Opportunity_Score}</span>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {row.Tier}
                      </div>
                    </td>
                    <td>
                      <span className="tier-badge tier-strong">
                        {row.Is_TTM_Squeeze ? '🔥 TTM Squeeze' : '🌀 Coiled'} ({row.Layers_Confirmed || 3}/4)
                      </span>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        BBW: {row.BBW_Percentile}%ile • HVR: {row.HVR_Pct}%
                      </div>
                    </td>
                    <td>
                      <strong>${row.Spot_Price?.toFixed(2)}</strong> ➔{' '}
                      <span style={{ color: 'var(--cyan-primary)' }}>${row.Gamma_Wall_Strike?.toFixed(2)}</span>
                      <div style={{ fontSize: '11px', color: 'var(--emerald-primary)' }}>
                        +{row['Distance_to_Wall_%']}% to Wall
                      </div>
                    </td>
                    <td>
                      ${((row.Gamma_Dollars_at_Wall || 0) / 1e6).toFixed(2)}M
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                        {row['Gamma_Concentration_%']}% of chain
                      </div>
                    </td>
                    <td>
                      <span style={{ color: 'var(--emerald-primary)', fontWeight: 700 }}>
                        ${row.Recommended_Strike}C @ ${row.Recommended_Premium?.toFixed(2)}
                      </span>
                    </td>
                    <td style={{ maxWidth: '340px', fontFamily: 'var(--font-sans)', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {row.Thesis}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: ASYMMETRIC SPRING PAYOFF SIMULATOR */}
      {activeTab === 'calculator' && (
        <SpringPayoffCalculator selectedOption={selectedOptionForSim} />
      )}
    </div>
  );
};
