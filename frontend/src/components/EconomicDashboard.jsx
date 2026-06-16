/**
 * EconomicDashboard — Tier 3 economic impact panel with recharts.
 */
import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';

const COLORS = ['#22c55e', '#eab308', '#f97316', '#ef4444', '#7c3aed'];
const DAMAGE_COLORS = { None: '#22c55e', Slight: '#eab308', Moderate: '#f97316', Extensive: '#ef4444', Complete: '#7c3aed' };

const fmt = (n) => n?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00';

export default function EconomicDashboard({ economic }) {
  if (!economic) {
    return (
      <div className="card" style={{ textAlign: 'center', color: '#64748b', padding: 20 }}>
        Economic data loading…
      </div>
    );
  }

  const { summary, bridge_damage = [], highway_closures = [] } = economic;

  // Bar chart data — top 8 closure costs
  const closureChartData = [...highway_closures]
    .sort((a, b) => b.estimated_loss_m - a.estimated_loss_m)
    .slice(0, 8)
    .map(r => ({
      name: r.highway || r.segment_id,
      loss: r.estimated_loss_m,
      days: r.est_closure_days,
    }));

  // Pie chart — bridge damage distribution
  const dmgCounts = bridge_damage.reduce((acc, b) => {
    acc[b.damage_label] = (acc[b.damage_label] || 0) + 1;
    return acc;
  }, {});
  const pieData = Object.entries(dmgCounts).map(([name, value]) => ({ name, value }));

  return (
    <div style={{ fontSize: 12 }}>
      {/* Summary metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
        {[
          { label: 'Total Economic Loss', value: `$${fmt(summary?.grand_total_loss_m)}M`, color: '#ef4444' },
          { label: 'Segments at Risk',    value: summary?.segments_at_risk ?? 0,           color: '#f97316' },
          { label: 'Bridges Affected',    value: summary?.total_bridges_affected ?? 0,      color: '#eab308' },
          { label: 'Critical Segments',   value: summary?.critical_segments ?? 0,           color: '#7c3aed' },
        ].map(m => (
          <div key={m.label} className="card" style={{ padding: '10px 12px', marginBottom: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.value}</div>
            <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* Highway closure bar chart */}
      {closureChartData.length > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <div className="card-title">Top Highway Closure Losses ($M)</div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={closureChartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e3353', border: '1px solid #2d4a6e', fontSize: 11 }}
                formatter={(v) => [`$${fmt(v)}M`, 'Est. Loss']}
              />
              <Bar dataKey="loss" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bridge damage pie */}
      {pieData.length > 0 && (
        <div className="card" style={{ marginBottom: 10 }}>
          <div className="card-title">Bridge Damage Distribution</div>
          <ResponsiveContainer width="100%" height={130}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={50} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={DAMAGE_COLORS[entry.name] || '#64748b'} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#1e3353', border: '1px solid #2d4a6e', fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bridge damage table */}
      {bridge_damage.filter(b => b.damage_label !== 'None').length > 0 && (
        <div className="card">
          <div className="card-title">Affected Bridges</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ color: '#64748b', borderBottom: '1px solid #2d4a6e' }}>
                  <th style={{ textAlign: 'left', padding: '4px 6px' }}>Bridge</th>
                  <th style={{ textAlign: 'center', padding: '4px 6px' }}>PGA (g)</th>
                  <th style={{ textAlign: 'center', padding: '4px 6px' }}>Damage</th>
                  <th style={{ textAlign: 'right', padding: '4px 6px' }}>Loss ($M)</th>
                </tr>
              </thead>
              <tbody>
                {bridge_damage
                  .filter(b => b.damage_label !== 'None')
                  .sort((a, b) => b.estimated_loss_m - a.estimated_loss_m)
                  .map(b => (
                    <tr key={b.bridge_id} style={{ borderBottom: '1px solid #1e3353' }}>
                      <td style={{ padding: '4px 6px' }}>{b.bridge_name}</td>
                      <td style={{ textAlign: 'center', padding: '4px 6px', color: '#94a3b8' }}>{b.pga_g}</td>
                      <td style={{ textAlign: 'center', padding: '4px 6px' }}>
                        <span className={`badge badge-${
                          { Slight: 'yellow', Moderate: 'orange', Extensive: 'red', Complete: 'purple' }[b.damage_label] || 'green'
                        }`}>{b.damage_label}</span>
                      </td>
                      <td style={{ textAlign: 'right', padding: '4px 6px', color: '#ef4444' }}>
                        ${fmt(b.estimated_loss_m)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
