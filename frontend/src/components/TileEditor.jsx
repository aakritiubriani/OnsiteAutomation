import { useState } from 'react';
import TileBox from './TileBox.jsx';

// ── Option sets ──────────────────────────────────────────────────────────────
const FEEDS      = ['Men', 'Women', 'Kids', 'Outlet', 'Premium', 'Sports', 'Beauty'];
const SURFACES   = ['Cart', 'PDP Banner', 'Wishlist', 'Page Path', 'Category Page'];
const COUNTRIES  = ['UAE', 'KSA', 'GCC'];
const PLATFORMS  = ['App', 'Desktop'];
const PRIORITIES = ['P1', 'P2', 'P3'];

// ── Pills ────────────────────────────────────────────────────────────────────
function Pills({ options, selected, onChange, single = false }) {
  function toggle(opt) {
    if (single) { onChange(selected.includes(opt) ? [] : [opt]); return; }
    onChange(selected.includes(opt) ? selected.filter((x) => x !== opt) : [...selected, opt]);
  }
  return (
    <div className="pills">
      {options.map((opt) => (
        <button key={opt} type="button"
          className={`pill ${selected.includes(opt) ? 'on' : ''}`}
          onClick={() => toggle(opt)}>
          {opt}
        </button>
      ))}
    </div>
  );
}

// ── Collapsible section ──────────────────────────────────────────────────────
function Section({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="meta-section">
      <button type="button" className="meta-section-header" onClick={() => setOpen((v) => !v)}>
        <span className="section-heading">{title}</span>
        <span className="section-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="meta-section-body">{children}</div>}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div className="meta-field">
      <label>{label}</label>
      {children}
    </div>
  );
}

// ── Default meta ─────────────────────────────────────────────────────────────
function initMeta(row) {
  const m = row.wireframe_meta || {};
  return {
    feeds:           m.feeds           || [],
    surfaces:        m.surfaces        || m.placements || [],
    countries:       m.countries       || [],
    live_start:      m.live_start      || '',
    live_end:        m.live_end        || '',
    asset_position:  m.asset_position  || '',
    platforms:       m.platforms       || [],
    app_version_min: m.app_version_min || '',
    ab_test:         m.ab_test         || false,
    ab_variant:      m.ab_variant      || '',
    priority:        m.priority        || [],
    notes:           m.notes           || '',
  };
}

// ── Tile entry normaliser ─────────────────────────────────────────────────────
function normaliseTile(t) {
  if (typeof t === 'string') return { tile_id: t, copy_en: '', copy_en_refined: '', copy_ar: '', cta_text: '', deeplink: '', asset_dimensions: '' };
  return { cta_text: '', deeplink: '', asset_dimensions: '', ...t };
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function TileEditor({ row, tileCatalog, onSave, onOkay }) {
  const [tiles, setTiles] = useState(() => (row.wireframe_tiles || []).map(normaliseTile));
  const [picked, setPicked] = useState([]);
  const [meta, setMeta] = useState(() => initMeta(row));
  const set = (k, v) => setMeta((m) => ({ ...m, [k]: v }));

  function tileMeta(tileId) {
    return tileCatalog.find((t) => t.id === tileId) || { label: tileId, width: 4, height: 1 };
  }

  function addPicked() {
    if (!picked.length) return;
    setTiles((prev) => [...prev, ...picked.map((tid) => normaliseTile(tid))]);
    setPicked([]);
  }

  function removeTile(idx)  { setTiles((prev) => prev.filter((_, i) => i !== idx)); }
  function moveTile(idx, dir) {
    setTiles((prev) => {
      const j = idx + dir;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev]; [next[idx], next[j]] = [next[j], next[idx]]; return next;
    });
  }
  function updateTileField(idx, key, value) {
    setTiles((prev) => { const n = [...prev]; n[idx] = { ...n[idx], [key]: value }; return n; });
  }
  function setRefined(idx, refinedEn, ar) {
    setTiles((prev) => { const n = [...prev]; n[idx] = { ...n[idx], copy_en_refined: refinedEn, copy_ar: ar }; return n; });
  }

  function summary() {
    if (!tiles.length) return 'TBD';
    return tiles.map((t, i) => `${i + 1}. ${tileMeta(t.tile_id).label}`).join('  ');
  }

  return (
    <div className="tile-editor">

      {/* Campaign header */}
      <div className="editor-header">
        <div>
          <div className="editor-title">{row.campaign_name || '(untitled)'}</div>
          <div className="editor-meta">
            {[row.tier, row.geography, row.start_date, row.category_focus].filter(Boolean).join('  ·  ')}
          </div>
        </div>
      </div>

      {/* ── Placement ── */}
      <Section title="Placement">
        <Field label="Feed">
          <Pills options={FEEDS} selected={meta.feeds} onChange={(v) => set('feeds', v)} />
        </Field>
        <Field label="Page / Surface">
          <Pills options={SURFACES} selected={meta.surfaces} onChange={(v) => set('surfaces', v)} />
        </Field>
        <Field label="Country">
          <Pills options={COUNTRIES} selected={meta.countries} onChange={(v) => set('countries', v)} />
        </Field>
        <div className="meta-row-3">
          <Field label="Go-live start">
            <input type="datetime-local" value={meta.live_start} onChange={(e) => set('live_start', e.target.value)} />
          </Field>
          <Field label="Go-live end">
            <input type="datetime-local" value={meta.live_end} onChange={(e) => set('live_end', e.target.value)} />
          </Field>
          <Field label="Asset position">
            <input type="text" placeholder="e.g. Position 1, Above fold"
              value={meta.asset_position} onChange={(e) => set('asset_position', e.target.value)} />
          </Field>
        </div>
      </Section>

      {/* ── Technical ── */}
      <Section title="Technical">
        <Field label="Platform">
          <Pills options={PLATFORMS} selected={meta.platforms} onChange={(v) => set('platforms', v)} />
        </Field>
        <div className="meta-row-2">
          <Field label="Min app version">
            <input type="text" placeholder="e.g. 4.2.0"
              value={meta.app_version_min} onChange={(e) => set('app_version_min', e.target.value)} />
          </Field>
          <Field label="A/B test">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <label className="toggle-switch">
                <input type="checkbox" checked={meta.ab_test} onChange={(e) => set('ab_test', e.target.checked)} />
                <span className="toggle-track" />
              </label>
              {meta.ab_test && (
                <input type="text" placeholder="Variant name, e.g. Hero-v2"
                  value={meta.ab_variant} onChange={(e) => set('ab_variant', e.target.value)} style={{ flex: 1 }} />
              )}
            </div>
          </Field>
        </div>
      </Section>

      {/* ── Modules ── */}
      <div className="section-heading modules-heading">Modules</div>
      <div className="picker-row">
        <select multiple value={picked}
          onChange={(e) => setPicked(Array.from(e.target.selectedOptions).map((o) => o.value))}>
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

      <div className="preview-label">Preview — click inside each module to add copy &amp; creative details</div>
      <div className="preview-box">
        {tiles.length === 0 && <div className="muted center">Add tiles to see a preview.</div>}
        {tiles.map((t, i) => {
          const m = tileMeta(t.tile_id);
          return (
            <TileBox key={i} entry={t} label={m.label} width={m.width}
              onChangeCopy={(v) => updateTileField(i, 'copy_en', v)}
              onRefined={(en, ar) => setRefined(i, en, ar)}
              onChangeField={(k, v) => updateTileField(i, k, v)} />
          );
        })}
      </div>

      {/* ── Operational — always at the bottom ── */}
      <div className="operational-footer">
        <div className="op-row">
          <div className="meta-field">
            <label>Priority</label>
            <Pills options={PRIORITIES} selected={meta.priority} onChange={(v) => set('priority', v)} single />
          </div>
        </div>
        <div className="meta-field" style={{ marginTop: 10 }}>
          <label>Notes / brief</label>
          <textarea rows={3} placeholder="Any extra context for the design or dev team…"
            value={meta.notes} onChange={(e) => set('notes', e.target.value)} />
        </div>
      </div>

      <div className="action-row">
        <button type="button" onClick={() => onSave(tiles, summary(), meta)}>Save Draft</button>
        <button type="button" className="primary"
          onClick={() => {
            if (!tiles.length) { alert('Add at least one tile before okaying'); return; }
            onOkay(tiles, summary(), meta);
          }}>
          ✓ Okay &amp; Attach to Campaign Sheet
        </button>
      </div>
    </div>
  );
}
