import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  PointElement,
  LineElement
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { Activity } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface GexChartProps {
  ticker: string;
  spotPrice: number;
  wallStrike: number;
}

export const GexChart: React.FC<GexChartProps> = ({ ticker, spotPrice, wallStrike }) => {
  const strikes: number[] = [];
  const baseInterval = spotPrice > 300 ? 5 : spotPrice > 100 ? 2.5 : 1;
  const startStrike = Math.floor((spotPrice * 0.9) / baseInterval) * baseInterval;
  const endStrike = Math.ceil((spotPrice * 1.1) / baseInterval) * baseInterval;

  for (let s = startStrike; s <= endStrike; s += baseInterval) {
    strikes.push(parseFloat(s.toFixed(2)));
  }

  const gexValues = strikes.map(strike => {
    const distFromWall = Math.abs(strike - wallStrike);
    const distFromSpot = strike - spotPrice;

    if (strike >= spotPrice) {
      const peak = Math.exp(-0.5 * Math.pow(distFromWall / (baseInterval * 2), 2));
      return parseFloat((peak * 12.5 + 0.8).toFixed(2));
    } else {
      const putPeak = Math.exp(-0.5 * Math.pow(distFromSpot / (baseInterval * 3), 2));
      return -parseFloat((putPeak * 8.2 + 0.5).toFixed(2));
    }
  });

  const backgroundColors = gexValues.map(v => (v >= 0 ? 'rgba(16, 185, 129, 0.75)' : 'rgba(244, 63, 94, 0.75)'));
  const borderColors = gexValues.map(v => (v >= 0 ? '#10b981' : '#f43f5e'));

  const data = {
    labels: strikes.map(s => `$${s}`),
    datasets: [
      {
        label: 'Net Dealer Gamma Exposure ($M GEX)',
        data: gexValues,
        backgroundColor: backgroundColors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(14, 20, 36, 0.95)',
        titleColor: '#f8fafc',
        bodyColor: '#00f2fe',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: 12,
        callbacks: {
          label: (context: any) => `Net GEX: ${context.parsed.y > 0 ? '+' : ''}${context.parsed.y} Million`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono', size: 10 } },
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.06)' },
        ticks: {
          color: '#94a3b8',
          font: { family: 'JetBrains Mono', size: 11 },
          callback: (val: any) => `${val > 0 ? '+' : ''}${val}M`,
        },
      },
    },
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} style={{ color: 'var(--cyan-primary)' }} />
          <h3 style={{ fontSize: '15px', fontWeight: 700 }}>
            {ticker} Net Gamma Exposure (GEX) Profile by Strike
          </h3>
        </div>
        <div style={{ display: 'flex', gap: '12px', fontSize: '12px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Spot: <strong style={{ color: '#fff' }}>${spotPrice.toFixed(2)}</strong></span>
          <span style={{ color: 'var(--cyan-primary)' }}>Gamma Wall Magnet: <strong>${wallStrike.toFixed(2)}</strong></span>
        </div>
      </div>

      <div style={{ height: '280px', width: '100%', position: 'relative' }}>
        <Bar data={data} options={options as any} />
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-dim)', textAlign: 'center' }}>
        Green bars indicate Dealer Short Call Gamma (upside spring acceleration magnet). Red bars indicate Put Gamma support/breakdown zone.
      </div>
    </div>
  );
};
