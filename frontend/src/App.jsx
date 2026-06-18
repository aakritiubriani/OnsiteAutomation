import { useEffect, useState } from 'react';
import CampaignList from './components/CampaignList.jsx';
import TileEditor from './components/TileEditor.jsx';
import AddCampaignForm from './components/AddCampaignForm.jsx';
import { generateCampaigns, loadTileCatalog, exportWireframeXlsx } from './api.js';
import './App.css';

const MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

export default function App() {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [rows, setRows] = useState([]);
  const [tileCatalog, setTileCatalog] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    loadTileCatalog().then(setTileCatalog).catch((e) => setError(e.message));
  }, []);

  async function handleGenerate() {
    setLoading(true);
    setError('');
    try {
      const data = await generateCampaigns(month, year);
      const generated = [...(data.campaigns || []), ...(data.global_events || [])]
        .filter((r) => r.status !== 'rejected');
      // Keep any existing adhoc campaigns when re-generating
      setRows((prev) => {
        const adhoc = prev.filter((r) => r.source_type === 'adhoc');
        return [...generated, ...adhoc];
      });
      setSelectedId(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function addAdhocCampaign(campaign) {
    setRows((prev) => [...prev, campaign]);
    setSelectedId(campaign.id);
    setShowAddForm(false);
  }

  function updateRow(id, patch) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function handleSave(tiles, summaryText, meta) {
    updateRow(selectedId, { wireframe_tiles: tiles, wireframes: summaryText, wireframe_meta: meta, wireframe_status: 'draft' });
  }
  function handleOkay(tiles, summaryText, meta) {
    updateRow(selectedId, { wireframe_tiles: tiles, wireframes: summaryText, wireframe_meta: meta, wireframe_status: 'okayed' });
  }

  async function handleExport() {
    const okayed = rows.filter((r) => r.wireframe_status === 'okayed');
    if (!okayed.length) {
      alert('No wireframes have been okayed yet — build and okay at least one first.');
      return;
    }
    try {
      const blob = await exportWireframeXlsx(okayed, month, year);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `wireframe_${month}_${year}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Export failed: ' + e.message);
    }
  }

  const selectedRow = rows.find((r) => r.id === selectedId);

  return (
    <div className="wf-app">
      <header className="wf-header">
        <h1>Wireframe Generator</h1>
        <div className="month-controls">
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTH_NAMES.slice(1).map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={{ width: 80 }}
          />
          <button type="button" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Generating…' : 'Generate'}
          </button>
          <button type="button" onClick={handleExport}>Export okayed wireframes</button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="wf-body">
        <aside className="wf-sidebar">
          <div className="sidebar-title">
            Campaigns this month
            <button
              type="button"
              className="add-campaign-btn"
              onClick={() => setShowAddForm((v) => !v)}
              title="Add an ad hoc campaign"
            >
              {showAddForm ? '✕' : '+ Add'}
            </button>
          </div>

          {showAddForm && (
            <AddCampaignForm
              onAdd={addAdhocCampaign}
              onCancel={() => setShowAddForm(false)}
            />
          )}

          <CampaignList rows={rows} selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
        <main className="wf-main">
          {selectedRow ? (
            <TileEditor
              key={selectedRow.id}
              row={selectedRow}
              tileCatalog={tileCatalog}
              onSave={handleSave}
              onOkay={handleOkay}
            />
          ) : (
            <div className="empty-state">
              {rows.length
                ? 'Select a campaign on the left to build its wireframe.'
                : 'Pick a month/year and click Generate — or click "+ Add" to create a campaign manually.'}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
