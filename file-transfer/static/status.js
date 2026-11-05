// Renders the signed-in owner's transfers on the status page.

const STATE_LABELS = {
  uploading: "Uploading",
  complete: "Finished",
  cancelled: "Cancelled",
  expired: "Expired",
};

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function refresh() {
  const response = await fetch("/transfers");
  const { transfers } = await response.json();
  const body = document.querySelector("#transfers tbody");
  body.replaceChildren(
    ...transfers.map((transfer) => {
      const row = document.createElement("tr");
      for (const text of [
        transfer.id,
        STATE_LABELS[transfer.state] ?? transfer.state,
        humanSize(transfer.length),
      ]) {
        const cell = document.createElement("td");
        cell.textContent = text;
        row.append(cell);
      }
      return row;
    }),
  );
}

document.querySelector("#refresh").addEventListener("click", refresh);
refresh();

// Shown under the table.
export function countLabel(transfers) {
  return `${transfers.length} transfers`;
}

export function newest(transfers, limit = 10) {
  return [...transfers].sort((a, b) => b.created_at - a.created_at).slice(0, limit);
}
