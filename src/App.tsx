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
    Spot: 188.70,
    Type: 'CALL',
    Horizon: 'Swing Spring (7-44d)',
    Strike: 215.0,
    Expiration: '2026-12-18',
    DTE: 37,
    Bid: 0.19,
    Ask: 0.21,
    Mid: 0.20,
    Spread: 0.02,
    Volume: 6420,
    Open_Interest: 24850,
    IV: 38.0,
    Realized_HV: 51.4,
    IV_HV_Ratio: 0.74,
    IV_Rank: 0.18,
    BS_Fair_Value: 0.36,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 91.4,
    Delta_Est: 0.11,
    Contract: 'NVDA261218C00215000',
    Breakeven: 215.21,
    Breakeven_Move_Pct: 14.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 11.4,
    HVR_Pct: 16.2,
    Layers_Confirmed: 4,
    Spring_Score: 94.8,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon (Slope +0.74) + Mom 5d +3.8% / Vol 1.5x + $200 GEX Magnet',
    Spot_For_1_00: 216.0,
    Spot_For_10_00: 225.0,
    ATR_Move_To_1_00: 4.8,
    ATR_Move_To_10_00: 6.4,
    Proj_Value_2ATR: 1.65,
    Proj_Value_3ATR: 4.95,
    Proj_Value_5ATR: 15.80,
    Max_Projected_Value: 15.80,
    Potential_Multiple: 75.2,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 92.8,
    Persistence_Count: 3,
  },
  {
    Ticker: 'TSLA',
    Spot: 385.20,
    Type: 'CALL',
    Horizon: 'Swing Spring (7-44d)',
    Strike: 445.0,
    Expiration: '2026-12-18',
    DTE: 37,
    Bid: 0.22,
    Ask: 0.24,
    Mid: 0.23,
    Spread: 0.02,
    Volume: 7190,
    Open_Interest: 28400,
    IV: 49.5,
    Realized_HV: 63.8,
    IV_HV_Ratio: 0.78,
    IV_Rank: 0.21,
    BS_Fair_Value: 0.42,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 88.6,
    Delta_Est: 0.10,
    Contract: 'TSLA261218C00445000',
    Breakeven: 445.24,
    Breakeven_Move_Pct: 15.6,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 9.8,
    HVR_Pct: 17.5,
    Layers_Confirmed: 4,
    Spring_Score: 93.6,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon (Slope +1.18) + Negative Dealer Gamma Above $395',
    Spot_For_1_00: 446.0,
    Spot_For_10_00: 455.0,
    ATR_Move_To_1_00: 4.6,
    ATR_Move_To_10_00: 5.3,
    Proj_Value_2ATR: 2.10,
    Proj_Value_3ATR: 6.20,
    Proj_Value_5ATR: 21.40,
    Max_Projected_Value: 21.40,
    Potential_Multiple: 89.2,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 91.1,
    Persistence_Count: 3,
  },
  {
    Ticker: 'AMD',
    Spot: 491.59,
    Type: 'CALL',
    Horizon: 'Swing Spring (7-44d)',
    Strike: 545.0,
    Expiration: '2026-12-18',
    DTE: 37,
    Bid: 0.20,
    Ask: 0.22,
    Mid: 0.21,
    Spread: 0.02,
    Volume: 4850,
    Open_Interest: 16900,
    IV: 41.2,
    Realized_HV: 52.8,
    IV_HV_Ratio: 0.78,
    IV_Rank: 0.19,
    BS_Fair_Value: 0.35,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 87.2,
    Delta_Est: 0.11,
    Contract: 'AMD261218C00545000',
    Breakeven: 545.22,
    Breakeven_Move_Pct: 10.9,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 10.5,
    HVR_Pct: 15.4,
    Layers_Confirmed: 4,
    Spring_Score: 92.4,
    Spring_Thesis: 'TTM Keltner Squeeze + AI Semi Relative Strength + $520 GEX Call Wall Magnet',
    Spot_For_1_00: 546.0,
    Spot_For_10_00: 555.0,
    ATR_Move_To_1_00: 4.1,
    ATR_Move_To_10_00: 4.8,
    Proj_Value_2ATR: 1.90,
    Proj_Value_3ATR: 5.40,
    Proj_Value_5ATR: 16.80,
    Max_Projected_Value: 16.80,
    Potential_Multiple: 76.4,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 89.8,
    Persistence_Count: 2,
  },
  {
    Ticker: 'PLTR',
    Spot: 170.43,
    Type: 'CALL',
    Horizon: 'Long Swing (45-179d)',
    Strike: 200.0,
    Expiration: '2027-01-15',
    DTE: 65,
    Bid: 0.17,
    Ask: 0.19,
    Mid: 0.18,
    Spread: 0.02,
    Volume: 5120,
    Open_Interest: 19400,
    IV: 44.0,
    Realized_HV: 54.5,
    IV_HV_Ratio: 0.81,
    IV_Rank: 0.22,
    BS_Fair_Value: 0.31,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 85.9,
    Delta_Est: 0.12,
    Contract: 'PLTR270115C00200000',
    Breakeven: 200.19,
    Breakeven_Move_Pct: 17.5,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 12.8,
    HVR_Pct: 18.0,
    Layers_Confirmed: 4,
    Spring_Score: 91.2,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon + High Call OI Magnet @ $190',
    Spot_For_1_00: 201.0,
    Spot_For_10_00: 210.0,
    ATR_Move_To_1_00: 5.2,
    ATR_Move_To_10_00: 6.7,
    Proj_Value_2ATR: 1.55,
    Proj_Value_3ATR: 4.10,
    Proj_Value_5ATR: 12.40,
    Max_Projected_Value: 12.40,
    Potential_Multiple: 65.3,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 88.4,
    Persistence_Count: 4,
  },
  {
    Ticker: 'COIN',
    Spot: 136.50,
    Type: 'CALL',
    Horizon: 'Long Swing (45-179d)',
    Strike: 165.0,
    Expiration: '2027-01-15',
    DTE: 65,
    Bid: 0.18,
    Ask: 0.20,
    Mid: 0.19,
    Spread: 0.02,
    Volume: 3190,
    Open_Interest: 12840,
    IV: 58.0,
    Realized_HV: 74.5,
    IV_HV_Ratio: 0.78,
    IV_Rank: 0.21,
    BS_Fair_Value: 0.34,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 86.4,
    Delta_Est: 0.11,
    Contract: 'COIN270115C00165000',
    Breakeven: 165.20,
    Breakeven_Move_Pct: 21.0,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 14.9,
    HVR_Pct: 20.4,
    Layers_Confirmed: 4,
    Spring_Score: 89.8,
    Spring_Thesis: 'TTM Keltner Squeeze + Negative GEX Air Pocket Above $142 + RSI Launchpad (54.8)',
    Spot_For_1_00: 166.0,
    Spot_For_10_00: 175.0,
    ATR_Move_To_1_00: 5.1,
    ATR_Move_To_10_00: 6.6,
    Proj_Value_2ATR: 1.75,
    Proj_Value_3ATR: 4.60,
    Proj_Value_5ATR: 13.90,
    Max_Projected_Value: 13.90,
    Potential_Multiple: 69.5,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 87.9,
    Persistence_Count: 2,
  },
  {
    Ticker: 'MSTR',
    Spot: 121.24,
    Type: 'CALL',
    Horizon: 'Long Swing (45-179d)',
    Strike: 150.0,
    Expiration: '2027-01-15',
    DTE: 65,
    Bid: 0.20,
    Ask: 0.23,
    Mid: 0.22,
    Spread: 0.03,
    Volume: 4410,
    Open_Interest: 18200,
    IV: 72.0,
    Realized_HV: 91.0,
    IV_HV_Ratio: 0.79,
    IV_Rank: 0.23,
    BS_Fair_Value: 0.38,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 86.1,
    Delta_Est: 0.11,
    Contract: 'MSTR270115C00150000',
    Breakeven: 150.23,
    Breakeven_Move_Pct: 23.9,
    Is_In_Coil: true,
    Is_TTM_Squeeze: false,
    BBW_Percentile: 19.5,
    HVR_Pct: 23.0,
    Layers_Confirmed: 3,
    Spring_Score: 88.9,
    Spring_Thesis: 'High-Beta Volatility Coil + 65% Fair-Value Discount + $140 GEX Magnet',
    Spot_For_1_00: 151.0,
    Spot_For_10_00: 160.0,
    ATR_Move_To_1_00: 4.9,
    ATR_Move_To_10_00: 6.4,
    Proj_Value_2ATR: 2.20,
    Proj_Value_3ATR: 5.80,
    Proj_Value_5ATR: 17.50,
    Max_Projected_Value: 17.50,
    Potential_Multiple: 76.1,
    Can_Reach_1_00: true,
    Can_Reach_10_00: true,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Opportunity_Score: 87.2,
    Persistence_Count: 2,
  },
];

const INITIAL_0DTE_SPRINGS: ZeroDteSpringOpportunity[] = [
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'SPY',
    Option_Type: 'CALL',
    Contract_Symbol: 'SPY261111C00765000',
    Strike: 765.0,
    Spot_Price: 760.42,
    Bid: 0.16,
    Ask: 0.18,
    Spread: 0.02,
    Entry_Ask: 0.18,
    Delta: 0.16,
    Volume: 24820,
    Open_Interest: 14240,
    Vol_OI_Ratio: 1.74,
    IV_Pct: 13.8,
    Realized_HV_Pct: 16.9,
    IV_HV_Ratio: 0.82,
    IV_Rank: 0.18,
    BS_Fair_Value: 0.27,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 88.2,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 12.4,
    Layers_Confirmed: 4,
    Spring_Score: 93.1,
    Spring_Thesis: 'TTM Keltner Squeeze + Bullish EMA Ribbon + Gamma Wall @ $765',
    Dist_ATR_Units: 0.82,
    Spot_For_1_00: 766.0,
    Spot_For_10_00: 775.0,
    ATR_Move_To_1_00: 1.02,
    ATR_Move_To_10_00: 2.68,
    Proj_Value_3ATR: 5.60,
    Proj_Value_5ATR: 14.20,
    Max_Projected_Value: 14.20,
    Potential_Multiple: 78.9,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 18450000,
    Catalyst_Flag: 'Intraday Coiled Spring',
    Opportunity_Score: 91.8,
    Max_Loss_Held_To_Zero: 18.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'QQQ',
    Option_Type: 'CALL',
    Contract_Symbol: 'QQQ261111C00700000',
    Strike: 700.0,
    Spot_Price: 694.51,
    Bid: 0.17,
    Ask: 0.19,
    Spread: 0.02,
    Entry_Ask: 0.19,
    Delta: 0.15,
    Volume: 19400,
    Open_Interest: 10850,
    Vol_OI_Ratio: 1.79,
    IV_Pct: 16.8,
    Realized_HV_Pct: 21.2,
    IV_HV_Ratio: 0.79,
    IV_Rank: 0.19,
    BS_Fair_Value: 0.29,
    Valuation_Label: 'DEEP VALUE (IV < Realized HV)',
    Undervaluation_Score: 87.4,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 13.8,
    Layers_Confirmed: 4,
    Spring_Score: 92.0,
    Spring_Thesis: 'TTM Keltner Squeeze + AI Tech Relative Strength + GEX Magnet @ $700',
    Dist_ATR_Units: 0.79,
    Spot_For_1_00: 701.0,
    Spot_For_10_00: 710.0,
    ATR_Move_To_1_00: 0.94,
    ATR_Move_To_10_00: 2.25,
    Proj_Value_3ATR: 6.10,
    Proj_Value_5ATR: 15.80,
    Max_Projected_Value: 15.80,
    Potential_Multiple: 83.2,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 15900000,
    Catalyst_Flag: 'Intraday Coiled Spring',
    Opportunity_Score: 90.5,
    Max_Loss_Held_To_Zero: 19.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
  {
    Expiration_Date: '2026-11-11',
    DTE: 0,
    Ticker: 'SPY',
    Option_Type: 'PUT',
    Contract_Symbol: 'SPY261111P00755000',
    Strike: 755.0,
    Spot_Price: 760.42,
    Bid: 0.13,
    Ask: 0.15,
    Spread: 0.02,
    Entry_Ask: 0.15,
    Delta: 0.14,
    Volume: 14900,
    Open_Interest: 7400,
    Vol_OI_Ratio: 2.01,
    IV_Pct: 14.5,
    Realized_HV_Pct: 16.9,
    IV_HV_Ratio: 0.86,
    IV_Rank: 0.22,
    BS_Fair_Value: 0.22,
    Valuation_Label: 'UNDERVALUED COIL',
    Undervaluation_Score: 83.4,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 12.4,
    Layers_Confirmed: 3,
    Spring_Score: 85.4,
    Spring_Thesis: 'TTM Keltner Squeeze Breakdown Hedge + Put Gamma Air Pocket below $758',
    Dist_ATR_Units: 0.98,
    Spot_For_1_00: 754.0,
    Spot_For_10_00: 745.0,
    ATR_Move_To_1_00: 1.18,
    ATR_Move_To_10_00: 2.84,
    Proj_Value_3ATR: 4.85,
    Proj_Value_5ATR: 12.80,
    Max_Projected_Value: 12.80,
    Potential_Multiple: 85.3,
    Payoff_Tier: '🚀 $10.00+ Super-Spring Potential (40x+)',
    Gamma_Exposure_Dollars: 11400000,
    Catalyst_Flag: 'Zero-Gamma Hedge',
    Opportunity_Score: 85.9,
    Max_Loss_Held_To_Zero: 15.0,
    Averaging_Down_Violation_Flag: 'CLEAN: 1st entry of day',
  },
];

const INITIAL_GAMMA_COILS: GammaOpportunity[] = [
  {
    Ticker: 'NVDA',
    Opportunity_Score: 91.2,
    Spring_Score: 94.8,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 11.4,
    HVR_Pct: 16.2,
    Layers_Confirmed: 4,
    Tier: '🔥 High Conviction Spring',
    Trend: '^^',
    Spot_Price: 188.70,
    ATR_14: 5.65,
    Expiration: '2026-11-13',
    Days_to_Expiration: 2,
    Put_Call_OI_Ratio: 0.52,
    Gamma_Wall_Strike: 200.0,
    Gamma_Dollars_at_Wall: 34800000,
    'Gamma_Concentration_%': 41.4,
    'Gamma_Fuel_vs_ADV_%': 24.1,
    'Distance_to_Wall_%': 6.0,
    '5_Day_Performance_%': 3.8,
    Days_to_Cover: 1.8,
    'Short_Pct_Float_%': 1.4,
    Has_Short_Data: true,
    Acceleration: 0.76,
    Recommended_Strike: 205.0,
    Recommended_Premium: 0.21,
    Breakeven_Price: 205.21,
    Thesis: '[TTM Keltner Squeeze + Bullish EMA Ribbon] NVDA ($188.70) needs a 6.0% move to reach the $200.00 Gamma Wall ($34.8M per 1% move).',
  },
  {
    Ticker: 'TSLA',
    Opportunity_Score: 89.4,
    Spring_Score: 93.6,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 9.8,
    HVR_Pct: 17.5,
    Layers_Confirmed: 4,
    Tier: '🔥 High Conviction Spring',
    Trend: '^^',
    Spot_Price: 385.20,
    ATR_14: 13.80,
    Expiration: '2026-11-13',
    Days_to_Expiration: 2,
    Put_Call_OI_Ratio: 0.58,
    Gamma_Wall_Strike: 410.0,
    Gamma_Dollars_at_Wall: 39100000,
    'Gamma_Concentration_%': 43.2,
    'Gamma_Fuel_vs_ADV_%': 26.8,
    'Distance_to_Wall_%': 6.4,
    '5_Day_Performance_%': 4.2,
    Days_to_Cover: 2.4,
    'Short_Pct_Float_%': 3.1,
    Has_Short_Data: true,
    Acceleration: 0.72,
    Recommended_Strike: 420.0,
    Recommended_Premium: 0.24,
    Breakeven_Price: 420.24,
    Thesis: '[TTM Keltner Squeeze + Momentum Surge] TSLA ($385.20) needs a 6.4% move to reach the $410.00 Gamma Wall ($39.1M per 1% move).',
  },
  {
    Ticker: 'AMD',
    Opportunity_Score: 88.7,
    Spring_Score: 92.4,
    Is_In_Coil: true,
    Is_TTM_Squeeze: true,
    BBW_Percentile: 10.5,
    HVR_Pct: 15.4,
    Layers_Confirmed: 4,
    Tier: '🔥 High Conviction Spring',
    Trend: '^^',
    Spot_Price: 491.59,
    ATR_14: 14.90,
    Expiration: '2026-11-13',
    Days_to_Expiration: 2,
    Put_Call_OI_Ratio: 0.61,
    Gamma_Wall_Strike: 520.0,
    Gamma_Dollars_at_Wall: 31200000,
    'Gamma_Concentration_%': 39.8,
    'Gamma_Fuel_vs_ADV_%': 23.4,
    'Distance_to_Wall_%': 5.8,
    '5_Day_Performance_%': 4.9,
    Days_to_Cover: 1.9,
    'Short_Pct_Float_%': 2.1,
    Has_Short_Data: true,
    Acceleration: 0.74,
    Recommended_Strike: 530.0,
    Recommended_Premium: 0.22,
    Breakeven_Price: 530.22,
    Thesis: '[TTM Keltner Squeeze + AI Semi Breakout] AMD ($491.59) needs a 5.8% move to reach the $520.00 Gamma Wall ($31.2M per 1% move).',
  },
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('long_springs');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [only10DollarTarget, setOnly10DollarTarget] = useState<boolean>(false);
  const [onlyTtmSqueeze, setOnlyTtmSqueeze] = useState<boolean>(false);

  const [tickerScanInput, setTickerScanInput] = useState<string>('NVDA, TSLA, PLTR, AMD');
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [onlyQualified, setOnlyQualified] = useState<boolean>(true);
  const [scanSummary, setScanSummary] = useState<{
    message: string;
    qualifiedTickers: string[];
    unqualifiedTickers: string[];
    scannedAt: string;
    isError?: boolean;
  } | null>(null);

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

  const runDynamicScan = async (opts: { tickers?: string; preset?: string; label: string }) => {
    if (isScanning) return;
    setIsScanning(true);
    setScanSummary({
      message: `Scanning live options chains & volatility coils (${opts.label})...`,
      qualifiedTickers: [],
      unqualifiedTickers: [],
      scannedAt: '',
    });

    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tickers: opts.tickers || '',
          preset: opts.preset || '',
          max_premium: 0.25,
          only_qualified: onlyQualified,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        throw new Error(data.error || 'Dynamic scan failed');
      }

      setLongSpringData(data.long_springs || []);
      setZeroDteData(data.zero_dte_springs || []);
      setGammaData(data.gamma_coils || []);
      if (data.gamma_coils && data.gamma_coils.length > 0) {
        setSelectedGamma(data.gamma_coils[0]);
      }
      if (data.long_springs && data.long_springs.length > 0) {
        setSelectedOptionForSim(data.long_springs[0]);
      }

      setScanSummary({
        message: `Scanned ${data.counts.scanned} ticker(s) ➔ ${data.counts.qualified_tickers} qualified (${data.counts.long_springs} Long, ${data.counts.zero_dte_springs} 0DTE, ${data.counts.gamma_coils} Coils)`,
        qualifiedTickers: data.qualified_tickers || [],
        unqualifiedTickers: data.unqualified_tickers || [],
        scannedAt: data.scanned_at || '',
      });
    } catch (err) {
      setScanSummary({
        message: `Scan error: ${err instanceof Error ? err.message : 'Unable to reach scanner API'}`,
        qualifiedTickers: [],
        unqualifiedTickers: [],
        scannedAt: '',
        isError: true,
      });
    } finally {
      setIsScanning(false);
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

          <button className="btn-action" onClick={loadAllReports} disabled={isScanning}>
            <RefreshCw size={14} className={isScanning ? 'animate-spin' : ''} /> Reload Saved CSV
          </button>
        </div>
      </header>

      {/* Dynamic Live Ticker Scanner Control Bar */}
      <section className="glass-panel" style={{ padding: '16px 20px', marginBottom: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1 1 340px' }}>
            <div className="search-input-wrapper" style={{ flex: 1 }}>
              <Search size={16} className="search-icon" />
              <input
                type="text"
                className="search-input"
                placeholder="Enter ticker(s) to scan live (e.g., NVDA, TSLA, PLTR, ARM)..."
                value={tickerScanInput}
                onChange={e => setTickerScanInput(e.target.value.toUpperCase())}
                onKeyDown={e => {
                  if (e.key === 'Enter' && tickerScanInput.trim()) {
                    runDynamicScan({ tickers: tickerScanInput, label: tickerScanInput });
                  }
                }}
              />
            </div>
            <button
              className="btn-action btn-primary"
              disabled={isScanning || !tickerScanInput.trim()}
              onClick={() => runDynamicScan({ tickers: tickerScanInput, label: tickerScanInput })}
            >
              <Zap size={14} /> {isScanning ? 'Scanning...' : 'Scan Ticker(s)'}
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              className="btn-action"
              disabled={isScanning}
              onClick={() => runDynamicScan({ preset: 'indices', label: 'Indices (SPY, QQQ, IWM)' })}
            >
              <Flame size={14} /> Scan Indices (SPY/QQQ/IWM)
            </button>
            <button
              className="btn-action"
              disabled={isScanning}
              onClick={() => runDynamicScan({ preset: 'ai_semis', label: 'AI & Semis' })}
            >
              <TrendingUp size={14} /> Scan AI &amp; Semis
            </button>
            <button
              className="btn-action"
              disabled={isScanning}
              onClick={() => runDynamicScan({ preset: 'high_beta', label: 'High-Beta & Crypto' })}
            >
              <Rocket size={14} /> Scan High-Beta
            </button>
            <button
              className="btn-action"
              disabled={isScanning}
              onClick={() => runDynamicScan({ preset: 'universe', label: 'Full Universe (50 Tickers)' })}
            >
              <Activity size={14} /> Scan Full Universe
            </button>
            <button
              className={`btn-action ${onlyQualified ? 'btn-primary' : ''}`}
              onClick={() => setOnlyQualified(!onlyQualified)}
              title="Only include tickers that pass <= $0.25 ask, $1.00+ payoff, and coil/undervaluation qualification"
            >
              <ShieldCheck size={14} /> {onlyQualified ? 'Qualified Only: ON' : 'Qualified Only: OFF'}
            </button>
          </div>
        </div>

        {scanSummary && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
              padding: '8px 12px',
              borderRadius: '8px',
              fontSize: '12px',
              background: scanSummary.isError ? 'rgba(244, 63, 94, 0.12)' : 'rgba(16, 185, 129, 0.08)',
              border: `1px solid ${scanSummary.isError ? 'rgba(244, 63, 94, 0.35)' : 'rgba(16, 185, 129, 0.25)'}`,
              color: scanSummary.isError ? '#fda4af' : 'var(--text-main)',
            }}
          >
            <div>
              <strong>{scanSummary.message}</strong>
              {scanSummary.qualifiedTickers.length > 0 && (
                <span style={{ marginLeft: '10px', color: 'var(--emerald-primary)' }}>
                  Qualified: {scanSummary.qualifiedTickers.join(', ')}
                </span>
              )}
              {scanSummary.unqualifiedTickers.length > 0 && (
                <span style={{ marginLeft: '10px', color: 'var(--text-dim)' }}>
                  Filtered out (unqualified): {scanSummary.unqualifiedTickers.join(', ')}
                </span>
              )}
            </div>
            {scanSummary.scannedAt && (
              <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                Last Live Scan: {scanSummary.scannedAt}
              </span>
            )}
          </div>
        )}
      </section>

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
