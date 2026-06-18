function statusBadge(row) {
  const tileCount = (row.wireframe_tiles || []).length;
  const isAdhoc = row.source_type === 'adhoc';
  if (row.wireframe_status === 'okayed') {
    return <span className="badge badge-okayed">✓ OKAYED</span>;
  }
  if (tileCount) {
    return <span className="badge badge-draft">DRAFT</span>;
  }
  if (isAdhoc) {
    return <span className="badge badge-adhoc">AD HOC</span>;
  }
  return <span className="badge-empty">not started</span>;
}

export default function CampaignList({ rows, selectedId, onSelect }) {
  if (!rows.length) {
    return (
      <div className="empty-state">
        <p>No campaigns yet. Click Generate or use "+ Add" to create one manually.</p>
      </div>
    );
  }
  return (
    <div className="campaign-list">
      {rows.map((r) => (
        <div
          key={r.id}
          className={`campaign-row ${r.id === selectedId ? 'active' : ''}`}
          onClick={() => onSelect(r.id)}
        >
          <div className="campaign-name">{r.campaign_name || '(untitled)'}</div>
          <div className="campaign-meta">{r.start_date} · {r.tier || '-'}</div>
          <div className="campaign-badge">{statusBadge(r)}</div>
        </div>
      ))}
    </div>
  );
}
