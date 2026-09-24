/** Data table styled with Supermemory aesthetic. */
export default function DataTable({ columns, rows, onRowClick, emptyMessage = 'No data' }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="bg-white/90 rounded-xl border border-dashed border-slate-200 p-8 text-center text-slate-400 font-mono text-xs">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="bg-white/95 rounded-xl border border-slate-200/80 overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/70">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-[11px] font-mono font-medium text-slate-500 uppercase tracking-wider"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, i) => (
              <tr
                key={row.id || i}
                className={`transition-colors duration-100 ${
                  onRowClick
                    ? 'hover:bg-gradient-to-r hover:from-slate-50/80 hover:to-emerald-50/20 cursor-pointer'
                    : 'hover:bg-slate-50/50'
                }`}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3 text-slate-700 text-sm">
                    {col.render ? col.render(row[col.key], row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
