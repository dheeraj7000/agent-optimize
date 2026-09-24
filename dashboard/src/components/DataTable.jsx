export default function DataTable({ columns, rows, onRowClick, emptyMessage = 'No data' }) {
  if (!rows || rows.length === 0) {
    return <div className="table-empty"><span className="table-empty-mark">—</span>
      <strong>Nothing to show yet</strong><p>{emptyMessage}</p></div>
  }

  return <div className="table-frame"><div className="table-scroll">
    <table className="data-table">
      <thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr
        key={row.id || row.trace_id || row.recommendation_id || index}
        className={onRowClick ? 'data-row-clickable' : ''}
        onClick={() => onRowClick?.(row)}>
        {columns.map((column) => <td key={column.key}>
          {column.render ? column.render(row[column.key], row) : row[column.key]}
        </td>)}
      </tr>)}</tbody>
    </table>
  </div></div>
}
