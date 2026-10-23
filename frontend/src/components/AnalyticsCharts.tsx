type BarDatum = {
  label: string
  value: number
}

export function BarChart({ title, data, emptyLabel = 'No sales data yet.' }: {
  title: string
  data: BarDatum[]
  emptyLabel?: string
}) {
  const max = Math.max(1, ...data.map((item) => item.value))
  return (
    <section className="panel chart-panel">
      <h2>{title}</h2>
      {!data.length ? <p className="muted">{emptyLabel}</p> : (
        <div className="bar-chart">
          {data.map((item) => (
            <div className="bar-row" key={item.label} title={`${item.label}: ${item.value}`}>
              <span className="bar-label">{item.label}</span>
              <div className="bar-track"><span className="bar-fill" style={{ width: `${Math.max(2, item.value / max * 100)}%` }} /></div>
              <strong className="bar-value">{item.value}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function LineChart({ title, data }: {
  title: string
  data: { date: string; orders: number }[]
}) {
  const width = 700
  const height = 230
  const padding = { top: 18, right: 16, bottom: 42, left: 30 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const maxValue = Math.max(1, ...data.map((item) => item.orders))
  const points = data.map((item, index) => {
    const x = padding.left + (data.length <= 1 ? plotWidth / 2 : index * plotWidth / (data.length - 1))
    const y = padding.top + plotHeight - item.orders / maxValue * plotHeight
    return `${x},${y}`
  }).join(' ')

  return (
    <section className="panel chart-panel line-chart-panel">
      <h2>{title}</h2>
      {!data.length ? <p className="muted">No order activity yet.</p> : (
        <svg className="line-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title} for the last ${data.length} days`}>
          {[0, 0.5, 1].map((fraction) => {
            const y = padding.top + fraction * plotHeight
            return <line key={fraction} x1={padding.left} x2={width - padding.right} y1={y} y2={y} className="chart-gridline" />
          })}
          <polyline points={points} className="chart-line" />
          {data.map((item, index) => {
            const x = padding.left + (data.length <= 1 ? plotWidth / 2 : index * plotWidth / (data.length - 1))
            const y = padding.top + plotHeight - item.orders / maxValue * plotHeight
            return (
              <g key={item.date}>
                <circle cx={x} cy={y} r="3.5" className="chart-point">
                  <title>{item.date}: {item.orders} orders</title>
                </circle>
                {(index % 2 === 0 || index === data.length - 1) && (
                  <text x={x} y={height - 14} textAnchor="middle" className="chart-date">
                    {new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      )}
    </section>
  )
}
