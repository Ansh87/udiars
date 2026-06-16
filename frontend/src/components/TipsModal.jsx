/**
 * TipsModal — general guidance for what to do when each hazard occurs.
 */
import React from 'react';
import Modal from './Modal';
import { TIPS } from '../constants/appData';

export default function TipsModal({ onClose, mobile = false }) {
  return (
    <Modal title="🧭 Emergency Tips" onClose={onClose} mobile={mobile}>
      {TIPS.map(t => (
        <div key={t.key} style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>{t.icon} {t.title}</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: '#cbd5e1' }}>
            {t.items.map((item, i) => <li key={i} style={{ marginBottom: 4 }}>{item}</li>)}
          </ul>
          <a href={t.link} target="_blank" rel="noreferrer" style={{ color: '#60a5fa', fontSize: 12 }}>
            More guidance at ready.gov →
          </a>
        </div>
      ))}
    </Modal>
  );
}
