import { useState } from 'react';
import TileBox from './TileBox.jsx';

export default function TileEditor({ row, tileCatalog, onSave, onOkay }) {
  const [tiles, setTiles] = useState(() =>
    (row.wireframe_tiles || []).map((t) =>
      typeof t === 'string'
        ? { tile_id: t, copy_en: '', copy_en_refined: '', copy_ar: '' }
        : { ...t }
    )
  );
  const [picked, setPicked] = useState([]);

  function tileMeta(tileId) {
    return tileCatalog.find((t) => t.id === tileId) || { label: tileId, width: 4, height: 1 };
  }

  function addPicked() {
    if (!picked.length) return;
    setTiles((prev) => [
      ...prev,
      ...picked.map((tid) => ({ tile_id: tid, copy_en: '', copy_en_refined: '', copy_ar: '' })),
    ]);
    setPicked([]);
  }

  function removeTile(idx) {
    setTiles((prev) => prev.filter((_, i) => i !== idx));
  }
  function moveTile(idx, dir) {
    setTiles((prev) => {
      const j = idx + dir;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  }
  function updateCopy(idx, value) {
    setTiles((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], copy_en: value };
      return next;
    });
  }
  function setRefined(idx, refinedEn, ar) {
    setTiles((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], copy_en_refined: refinedEn, copy_ar: ar };
      return next;
    });
  }

  function summary() {
    if (!tiles.length) return 'TBD';
    return tiles.map((t, i) => `${i + 1}. ${tileMeta(t.tile_id).label}`).join('  ');
  }

  return (
    <div className="tile-editor">
      <div className="editor-header">
        <div>
          <div className="editor-title">{row.campaign_name || '(untitled)'}</div>
          <div className="editor-meta">
            {[row.tier, row.geography, row.start_date, row.category_focus].filter(Boolean).join('  ·  ')}
          </div>
        </div>
      </div>

      <div className="picker-row">
        <select
          multiple
          value={picked}
          onChange={(e) => setPicked(Array.from(e.target.selectedOptions).map((o) => o.value))}
        >
          {tileCatalog.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
        <button type="button" onClick={addPicked}>+ Add selected tile(s)</button>
      </div>
      <div className="hint">Ctrl/Cmd-click (or Shift-click) to select multiple modules at once.</div>

      <div className="reorder-list">
        {tiles.length === 0 && <div className="muted">No tiles added yet.</div>}
        {tiles.map((t, i) => (
          <div key={i} className="reorder-row">
            <span className="idx">{i + 1}.</span>
            <span className="label">{tileMeta(t.tile_id).label}</span>
            <button type="button" disabled={i === 0} onClick={() => moveTile(i, -1)}>↑</button>
            <button type="button" disabled={i === tiles.length - 1} onClick={() => moveTile(i, 1)}>↓</button>
            <button type="button" onClick={() => removeTile(i)}>✕</button>
          </div>
        ))}
      </div>

      <div className="preview-label">Preview (proportional mockup, not final design)</div>
      <div className="preview-box">
        {tiles.length === 0 && <div className="muted center">Add tiles to see a preview.</div>}
        {tiles.map((t, i) => {
          const meta = tileMeta(t.tile_id);
          return (
            <TileBox
              key={i}
              entry={t}
              label={meta.label}
              width={meta.width}
              onChangeCopy={(v) => updateCopy(i, v)}
              onRefined={(refinedEn, ar) => setRefined(i, refinedEn, ar)}
            />
          );
        })}
      </div>

      <div className="action-row">
        <button type="button" onClick={() => onSave(tiles, summary())}>Save Draft</button>
        <button
          type="button"
          className="primary"
          onClick={() => {
            if (!tiles.length) { alert('Add at least one tile before okaying'); return; }
            onOkay(tiles, summary());
          }}
        >
          ✓ Okay &amp; Attach to Campaign Sheet
        </button>
      </div>
    </div>
  );
}
