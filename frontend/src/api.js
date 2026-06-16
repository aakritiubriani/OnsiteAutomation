async function asJson(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.error) throw new Error(data.error || res.statusText);
  return data;
}

export async function generateCampaigns(month, year) {
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ month, year }),
  });
  return asJson(res);
}

export async function loadTileCatalog() {
  const res = await fetch('/api/wireframe-tiles');
  const data = await asJson(res);
  return data.tiles || [];
}

export async function refineCopy(text) {
  const res = await fetch('/api/refine-copy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  return asJson(res);
}

export async function exportWireframeXlsx(rows, month, year) {
  const res = await fetch('/api/export-wireframe', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, month, year }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || res.statusText);
  }
  return res.blob();
}
