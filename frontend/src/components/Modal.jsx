/**
 * Modal — generic centered overlay dialog used by Help / Tips / Read Me.
 */
import React from 'react';

export default function Modal({ title, onClose, children, mobile = false }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 5000,
        background: 'rgba(5,10,18,0.72)',
        display: 'flex', alignItems: mobile ? 'flex-end' : 'center', justifyContent: 'center',
        padding: mobile ? 0 : 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#101f33',
          border: '1px solid #1e3a5c',
          borderRadius: mobile ? '16px 16px 0 0' : 12,
          width: mobile ? '100%' : 440,
          maxWidth: '100%',
          maxHeight: mobile ? '85vh' : '80vh',
          display: 'flex', flexDirection: 'column',
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', borderBottom: '1px solid #1e3a5c', flexShrink: 0,
        }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 22, cursor: 'pointer', lineHeight: 1, padding: '0 4px' }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: '14px 16px', overflowY: 'auto', flex: 1, fontSize: 13, lineHeight: 1.55 }}>
          {children}
        </div>
      </div>
    </div>
  );
}
