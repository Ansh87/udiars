/**
 * HelpModal — emergency hotlines / assistance contacts.
 * Phone numbers are tel: links so mobile users can tap-to-dial.
 */
import React from 'react';
import Modal from './Modal';
import { HOTLINES } from '../constants/appData';

export default function HelpModal({ onClose, mobile = false }) {
  return (
    <Modal title="📞 Help — Emergency Hotlines" onClose={onClose} mobile={mobile}>
      <div style={{ color: '#94a3b8', marginBottom: 12 }}>
        Tap a number to call. In a life-threatening emergency, always call 911 first.
      </div>
      {HOTLINES.map(h => (
        <a
          key={h.number + h.name}
          href={`tel:${h.number.replace(/[^0-9+]/g, '')}`}
          style={{
            display: 'flex', flexDirection: 'column', gap: 2,
            padding: '10px 12px', marginBottom: 8,
            background: '#1a2942', border: '1px solid #2d4a6e', borderRadius: 8,
            textDecoration: 'none', color: 'inherit',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600 }}>{h.name}</span>
            <span style={{ color: '#60a5fa', fontWeight: 700 }}>{h.number} ☎</span>
          </div>
          <div style={{ color: '#64748b', fontSize: 11 }}>{h.note}</div>
        </a>
      ))}
    </Modal>
  );
}
