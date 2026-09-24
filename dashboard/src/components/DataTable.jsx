export default function DataTable({ columns, rows, onRowClick, emptyMessage = 'No data' }) {
  if (!rows || rows.length === 0) {
    return <div className="table-empty"><span className="table-empty-mark">—</span>
      <strong>Nothing to show yet</strong><p>{emptyMessage}</p></div>
  }
  return (
    <div className="table-frame"><div className="table-scroll"><table className="data-table">
      <thead><tr>{columns.map((col) => <th key={col.key}>{col.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={row.id || row.trace_id || row.recommendation_id || i}
        className={onRowClick ? 'data-row-clickable' : ''} onClick={() => onRowClick?.(row)}>
        {columns.map((col) => <td key={col.key}>{col.render ? col.render(row[col.key], row) : row[col.key]}</td>)}
      </tr>)}</tbody>
    </table></div></div>
  )
}
