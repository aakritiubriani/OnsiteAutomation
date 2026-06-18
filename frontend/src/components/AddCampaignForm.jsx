import { useState } from 'react';

const EMPTY = {
  campaign_name: '',
  tier: 'Tier 2',
  geography: 'KSA + UAE',
  start_date: '',
  end_date: '',
  category_focus: '',
};

export default function AddCampaignForm({ onAdd, onCancel }) {
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState('');

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.campaign_name.trim()) { setErr('Campaign name is required.'); return; }
    onAdd({
      id: `adhoc_${Date.now()}`,
      campaign_name: form.campaign_name.trim(),
      tier: form.tier,
      geography: form.geography,
      start_date: form.start_date || 'TBD',
      end_date: form.end_date || 'TBD',
      category_focus: form.category_focus,
      source_type: 'adhoc',
      wireframe_tiles: [],
      wireframe_status: undefined,
    });
  }

  return (
    <form className="add-campaign-form" onSubmit={handleSubmit}>
      <div className="acf-title">New Campaign</div>

      <label>Campaign name *</label>
      <input
        autoFocus
        type="text"
        placeholder="e.g. Flash Sale — Denim"
        value={form.campaign_name}
        onChange={(e) => set('campaign_name', e.target.value)}
      />

      <label>Tier</label>
      <select value={form.tier} onChange={(e) => set('tier', e.target.value)}>
        <option>Tier 1</option>
        <option>Tier 2</option>
        <option>Tier 3</option>
      </select>

      <label>Geography</label>
      <select value={form.geography} onChange={(e) => set('geography', e.target.value)}>
        <option>KSA + UAE</option>
        <option>KSA</option>
        <option>UAE</option>
        <option>KSA + UAE + Kuwait</option>
        <option>All GCC</option>
      </select>

      <label>Start date</label>
      <input type="date" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} />

      <label>End date</label>
      <input type="date" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} />

      <label>Category focus</label>
      <input
        type="text"
        placeholder="e.g. Women's Dresses, Footwear"
        value={form.category_focus}
        onChange={(e) => set('category_focus', e.target.value)}
      />

      {err && <div className="acf-error">{err}</div>}

      <div className="acf-actions">
        <button type="submit" className="primary">Add Campaign</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
