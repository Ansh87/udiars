import React from 'react';
import { STATE_CONFIG, REGION_ORDER } from '../constants/appData';

export default function StateSelector({ value, onChange, compact = false }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      title="Select state — map will zoom to bring it into frame"
      style={{
        background: '#1a2942',
        border: '1px solid #2d4a6e',
        borderRadius: 5,
        color: '#e2e8f0',
        padding: compact ? '4px 6px' : '5px 8px',
        fontSize: compact ? 11 : 12,
        cursor: 'pointer',
        outline: 'none',
      }}
    >
      {REGION_ORDER.map(id => (
        <option key={id} value={id}>{STATE_CONFIG[id].name}</option>
      ))}
    </select>
  );
}
