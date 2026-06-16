import { useState } from 'react';
import { refineCopy } from '../api.js';

export default function TileBox({ entry, label, width, onChangeCopy, onRefined }) {
  const [refining, setRefining] = useState(false);
  const widthPct = Math.round((width / 4) * 100);

  async function handleRefine() {
    const text = (entry.copy_en || '').trim();
    if (!text) return;
    setRefining(true);
    try {
      const data = await refineCopy(text);
      onRefined(data.refined_en, data.arabic);
    } catch (e) {
      alert('Refine failed: ' + e.message);
    } finally {
      setRefining(false);
    }
  }

  return (
    <div className="tile-box" style={{ width: `${widthPct}%` }}>
      <div className="tile-box-label">{label}</div>
      <div className="tile-box-row">
        <input
          type="text"
          placeholder="Type ad copy for this tile…"
          value={entry.copy_en || ''}
          onChange={(e) => onChangeCopy(e.target.value)}
        />
        <button type="button" disabled={refining} onClick={handleRefine}>
          {refining ? 'Refining…' : 'Refine & Translate'}
        </button>
      </div>
      {(entry.copy_en_refined || entry.copy_ar) && (
        <div className="tile-box-refined">
          <div><strong>Refined (EN):</strong> {entry.copy_en_refined}</div>
          <div dir="rtl"><strong>عربي:</strong> {entry.copy_ar}</div>
        </div>
      )}
    </div>
  );
}
