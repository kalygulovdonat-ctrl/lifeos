/**
 * Small SVG charts (dataviz method): one axis, thin marks, 4px rounded data ends,
 * hover tooltips, direct end labels, and a table view for every chart.
 * Colors are role tokens from charts.module.css (validated palette, light + dark).
 */
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';

import styles from './charts.module.css';

export const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'] as const;

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(value));
  const n = value / exp;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * exp;
}

const DEFAULT_W = 640;

/** Width of the plot container, so the SVG draws in real pixels (labels keep their size). */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_W);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(Math.max(240, Math.round(el.getBoundingClientRect().width)));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}
const PAD = { top: 16, right: 56, bottom: 26, left: 40 };

interface Tip {
  x: number;
  y: number;
  content: ReactNode;
}

function Tooltip({ tip, width }: { tip: Tip | null; width: number }) {
  if (!tip) return null;
  return (
    <div
      className={styles.tooltip}
      style={{ left: `${(tip.x / width) * 100}%`, top: tip.y }}
      role="status"
    >
      {tip.content}
    </div>
  );
}

export interface ColumnDatum {
  key: string;
  label: string;
  /** Full label for the tooltip and the table (e.g. a long date). */
  title: string;
  value: number;
}

/** Single-series columns: the title names the measure, so no legend. */
export function ColumnChart({
  data,
  format,
  height = 180,
  ariaLabel,
  tableLabel,
}: {
  data: ColumnDatum[];
  format: (v: number) => string;
  height?: number;
  ariaLabel: string;
  tableLabel: string;
}) {
  const [tip, setTip] = useState<Tip | null>(null);
  const [plotRef, W] = useWidth();
  let max = niceMax(Math.max(0, ...data.map((d) => d.value)));
  if (Number.isInteger(max) && max % 2 === 1) max += 1; // keep the middle tick a whole number
  const innerW = W - PAD.left - PAD.right + 40;
  const innerH = height - PAD.top - PAD.bottom;
  const band = innerW / Math.max(data.length, 1);
  const barW = Math.min(24, band * 0.6);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const peak = data.reduce<ColumnDatum | null>(
    (best, d) => (!best || d.value > best.value ? d : best),
    null,
  );
  const showEvery = Math.ceil(data.length / Math.max(2, Math.floor(W / 56)));

  return (
    <figure className={styles.figure}>
      <div className={styles.plot} ref={plotRef}>
        <svg
          viewBox={`0 0 ${W} ${height}`}
          role="img"
          aria-label={ariaLabel}
          onMouseLeave={() => setTip(null)}
        >
          {[0, 0.5, 1].map((f) => (
            <g key={f}>
              <line
                x1={PAD.left}
                x2={W - 16}
                y1={y(max * f)}
                y2={y(max * f)}
                className={styles.grid}
              />
              <text x={PAD.left - 6} y={y(max * f) + 4} className={styles.axis} textAnchor="end">
                {format(max * f)}
              </text>
            </g>
          ))}
          {data.map((d, i) => {
            const cx = PAD.left + band * i + band / 2;
            const top = y(d.value);
            const h = PAD.top + innerH - top;
            const r = Math.min(4, h);
            const x0 = cx - barW / 2;
            return (
              <g key={d.key}>
                {d.value > 0 ? (
                  <path
                    className={styles.bar}
                    d={`M${x0},${top + h} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x0 + barW - r} Q${x0 + barW},${top} ${x0 + barW},${top + r} V${top + h} Z`}
                  />
                ) : null}
                {/* Hit target taller and wider than the mark. */}
                <rect
                  x={PAD.left + band * i}
                  y={PAD.top}
                  width={band}
                  height={innerH}
                  className={styles.hit}
                  onMouseEnter={() =>
                    setTip({
                      x: cx,
                      y: Math.max(0, top - 8),
                      content: (
                        <>
                          <strong>{format(d.value)}</strong> <span>{d.title}</span>
                        </>
                      ),
                    })
                  }
                />
                {i % showEvery === 0 ? (
                  <text x={cx} y={height - 8} className={styles.axis} textAnchor="middle">
                    {d.label}
                  </text>
                ) : null}
                {peak && peak.key === d.key && d.value > 0 ? (
                  <text x={cx} y={top - 6} className={styles.value} textAnchor="middle">
                    {format(d.value)}
                  </text>
                ) : null}
              </g>
            );
          })}
          <line
            x1={PAD.left}
            x2={W - 16}
            y1={PAD.top + innerH}
            y2={PAD.top + innerH}
            className={styles.baseline}
          />
        </svg>
        <Tooltip tip={tip} width={W} />
      </div>
      <DataTable
        label={tableLabel}
        columns={[tableLabel]}
        rows={data.map((d) => ({ key: d.key, title: d.title, values: [format(d.value)] }))}
      />
    </figure>
  );
}

export interface LineSeries {
  key: string;
  label: string;
  values: Array<number | null>;
}

/** Up to three series on one shared scale (e.g. mood/energy/stress 1–10). */
export function LineChart({
  labels,
  titles,
  series,
  min,
  max,
  height = 200,
  ariaLabel,
  format = (v) => v.toFixed(1),
}: {
  labels: string[];
  titles: string[];
  series: LineSeries[];
  min: number;
  max: number;
  height?: number;
  ariaLabel: string;
  format?: (v: number) => string;
}) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const [plotRef, W] = useWidth();
  const innerW = W - PAD.left - PAD.right;
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) =>
    PAD.left + (labels.length <= 1 ? innerW / 2 : (innerW * i) / (labels.length - 1));
  const y = (v: number) => PAD.top + innerH - ((v - min) / (max - min)) * innerH;

  const paths = useMemo(
    () =>
      series.map((s) => {
        let d = '';
        let pen = false;
        s.values.forEach((v, i) => {
          if (v === null) {
            pen = false;
            return;
          }
          d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
          pen = true;
        });
        return d;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, labels.length, min, max, height, W],
  );
  const showEvery = Math.ceil(labels.length / Math.max(2, Math.floor(W / 80)));
  const lastIndex = (s: LineSeries) => {
    for (let i = s.values.length - 1; i >= 0; i--) if (s.values[i] !== null) return i;
    return -1;
  };

  return (
    <figure className={styles.figure}>
      <ul className={styles.legend} aria-label={ariaLabel}>
        {series.map((s, i) => (
          <li key={s.key}>
            <i style={{ background: SERIES[i] }} aria-hidden="true" />
            {s.label}
          </li>
        ))}
      </ul>
      <div className={styles.plot} ref={plotRef}>
        <svg
          viewBox={`0 0 ${W} ${height}`}
          role="img"
          aria-label={ariaLabel}
          onMouseLeave={() => setHover(null)}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * W;
            const i = Math.round(((px - PAD.left) / innerW) * (labels.length - 1));
            setHover(Math.max(0, Math.min(labels.length - 1, i)));
          }}
        >
          <defs>
            <clipPath id={`clip-${id}`}>
              <rect x={PAD.left - 6} y={0} width={innerW + 12} height={height} />
            </clipPath>
          </defs>
          {[min, (min + max) / 2, max].map((v) => (
            <g key={v}>
              <line
                x1={PAD.left}
                x2={PAD.left + innerW}
                y1={y(v)}
                y2={y(v)}
                className={styles.grid}
              />
              <text x={PAD.left - 6} y={y(v) + 4} className={styles.axis} textAnchor="end">
                {format(v)}
              </text>
            </g>
          ))}
          {labels.map((l, i) =>
            i % showEvery === 0 ? (
              <text key={i} x={x(i)} y={height - 8} className={styles.axis} textAnchor="middle">
                {l}
              </text>
            ) : null,
          )}
          {hover !== null ? (
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD.top}
              y2={PAD.top + innerH}
              className={styles.crosshair}
            />
          ) : null}
          <g clipPath={`url(#clip-${id})`}>
            {series.map((s, si) => (
              <path
                key={s.key}
                d={paths[si]}
                className={styles.line}
                style={{ stroke: SERIES[si] }}
              />
            ))}
            {series.map((s, si) =>
              s.values.map((v, i) =>
                v !== null && (hover === i || s.values.filter((x) => x !== null).length === 1) ? (
                  <circle
                    key={`${s.key}-${i}`}
                    cx={x(i)}
                    cy={y(v)}
                    r={4.5}
                    className={styles.dot}
                    style={{ fill: SERIES[si] }}
                  />
                ) : null,
              ),
            )}
          </g>
          {series.map((s, si) => {
            const li = lastIndex(s);
            if (li < 0) return null;
            return (
              <g key={`label-${s.key}`}>
                <line
                  x1={x(li) + 4}
                  x2={x(li) + 10}
                  y1={y(s.values[li]!)}
                  y2={y(s.values[li]!)}
                  style={{ stroke: SERIES[si] }}
                  strokeWidth={2}
                />
                <text x={x(li) + 13} y={y(s.values[li]!) + 4} className={styles.value}>
                  {format(s.values[li]!)}
                </text>
              </g>
            );
          })}
        </svg>
        {hover !== null && series.some((s) => s.values[hover] !== null) ? (
          <div
            className={styles.tooltip}
            style={{ left: `${(x(hover) / W) * 100}%`, top: 0 }}
            role="status"
          >
            <span>{titles[hover]}</span>
            {series.map((s, si) =>
              s.values[hover] !== null ? (
                <span key={s.key} className={styles.tipRow}>
                  <i style={{ background: SERIES[si] }} aria-hidden="true" />
                  {s.label}: <strong>{format(s.values[hover]!)}</strong>
                </span>
              ) : null,
            )}
          </div>
        ) : null}
      </div>
      <DataTable
        label={ariaLabel}
        columns={series.map((s) => s.label)}
        rows={titles.map((t, i) => ({
          key: String(i),
          title: t,
          values: series.map((s) => (s.values[i] === null ? '—' : format(s.values[i]!))),
        }))}
      />
    </figure>
  );
}

/** Horizontal share bars: value at the tip, name on the left (identity never color-alone). */
export function ShareBars({
  rows,
  format,
  showShare = true,
}: {
  rows: Array<{ key: string; label: string; color: string; value: number; share: number }>;
  format: (v: number) => string;
  showShare?: boolean;
}) {
  return (
    <ul className={styles.shares}>
      {rows.map((r) => (
        <li key={r.key}>
          <span className={styles.shareLabel}>
            <i style={{ background: r.color }} aria-hidden="true" />
            {r.label}
          </span>
          <span className={styles.shareTrack} aria-hidden="true">
            <b style={{ width: `${Math.max(r.share * 100, 1)}%`, background: r.color }} />
          </span>
          <span className={styles.shareValue}>
            {format(r.value)}
            {showShare ? ` · ${Math.round(r.share * 100)}%` : ''}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function DataTable({
  label,
  columns,
  rows,
}: {
  label: string;
  columns: string[];
  rows: Array<{ key: string; title: string; values: string[] }>;
}) {
  return (
    <details className={styles.table}>
      <summary>{label} · ▤</summary>
      <table>
        <thead>
          <tr>
            <th scope="col" />
            {columns.map((c) => (
              <th key={c} scope="col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <th scope="row">{r.title}</th>
              {r.values.map((v, i) => (
                <td key={i}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
