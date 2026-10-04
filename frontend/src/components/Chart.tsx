import { useId, useState, type KeyboardEvent } from "react";
import { format } from "../lib/format";

export interface ChartPoint {
  date: string;
  value: number | null;
}
export interface ChartSeries {
  name: string;
  points: ChartPoint[];
  color?: string;
}
interface ChartProps {
  title: string;
  note: string;
  series: ChartSeries[];
  formatValue?: (value: number | null) => string;
  bounds?: [number, number];
  bars?: boolean;
}

const WIDTH = 640;
const HEIGHT = 240;
const PADDING = { left: 66, right: 18, top: 20, bottom: 36 };
const colors = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

export function Sparkline({ points }: { points: ChartPoint[] }) {
  const values = points.filter(
    (point): point is ChartPoint & { value: number } => point.value != null,
  );
  if (!values.length)
    return <div className="sparkline-empty">No score history available</div>;
  const min = Math.min(...values.map((point) => point.value));
  const max = Math.max(...values.map((point) => point.value));
  const coordinates = values
    .map(
      (point, index) =>
        (values.length === 1 ? 160 : (index / (values.length - 1)) * 320) +
        "," +
        (72 - ((point.value - min) / (max - min || 1)) * 60),
    )
    .join(" ");
  return (
    <svg
      className="sparkline"
      viewBox="0 0 320 84"
      role="img"
      aria-label="Leading stock daily score history"
    >
      <polyline
        points={coordinates}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
      />
    </svg>
  );
}

export function Chart({
  title,
  note,
  series,
  formatValue = format.compact,
  bounds,
  bars = false,
}: ChartProps) {
  const descriptionId = useId();
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const dates = [
    ...new Set(
      series.flatMap((line) => line.points.map((point) => point.date)),
    ),
  ].sort();
  const values = series.flatMap((line) =>
    line.points.flatMap((point) => (point.value == null ? [] : [point.value])),
  );
  if (!dates.length || !values.length)
    return (
      <section className="card chart-card">
        <h3>{title}</h3>
        <p className="chart-note">{note}</p>
        <p className="chart-unavailable">
          No observations available for this chart.
        </p>
      </section>
    );
  const low = bounds?.[0] ?? Math.min(...values, ...(bars ? [0] : []));
  const high = bounds?.[1] ?? Math.max(...values, ...(bars ? [0] : []));
  const span = high - low || 1;
  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const x = (index: number) =>
    PADDING.left +
    (dates.length === 1
      ? plotWidth / 2
      : (index / (dates.length - 1)) * plotWidth);
  const y = (value: number) =>
    PADDING.top + ((high - value) / span) * plotHeight;
  const activeIndex =
    selectedIndex == null ? null : Math.min(selectedIndex, dates.length - 1);
  const activeDate = activeIndex == null ? null : dates[activeIndex];
  const pointMaps = series.map(
    (line) => new Map(line.points.map((point) => [point.date, point.value])),
  );
  const inspectKeyboard = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = activeIndex ?? dates.length - 1;
    setSelectedIndex(
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? dates.length - 1
          : Math.max(
              0,
              Math.min(
                dates.length - 1,
                current + (event.key === "ArrowRight" ? 1 : -1),
              ),
            ),
    );
  };
  return (
    <section className="card chart-card">
      <h3>{title}</h3>
      <p className="chart-note" id={descriptionId}>
        {note} Use arrow keys to inspect values.
      </p>
      <div className="chart">
        <svg
          viewBox={"0 0 " + WIDTH + " " + HEIGHT}
          role="img"
          tabIndex={0}
          aria-label={title}
          aria-describedby={descriptionId}
          onKeyDown={inspectKeyboard}
          onFocus={() => setSelectedIndex(dates.length - 1)}
          onMouseLeave={() => setSelectedIndex(null)}
          onMouseMove={(event) => {
            const rectangle = event.currentTarget.getBoundingClientRect();
            if (!rectangle.width) return;
            const position =
              ((event.clientX - rectangle.left) / rectangle.width) * WIDTH;
            setSelectedIndex(
              Math.max(
                0,
                Math.min(
                  dates.length - 1,
                  Math.round(
                    ((position - PADDING.left) / plotWidth) *
                      (dates.length - 1),
                  ),
                ),
              ),
            );
          }}
        >
          {[0, 1, 2, 3, 4].map((tick) => {
            const value = low + (span * tick) / 4;
            return (
              <g key={tick}>
                <line
                  x1={PADDING.left}
                  x2={WIDTH - PADDING.right}
                  y1={y(value)}
                  y2={y(value)}
                  stroke="var(--grid)"
                />
                <text
                  x={PADDING.left - 8}
                  y={y(value) + 4}
                  textAnchor="end"
                  fill="var(--text-3)"
                  fontSize="10"
                >
                  {formatValue(value)}
                </text>
              </g>
            );
          })}
          {series.map((line, lineIndex) => {
            const color = line.color || colors[lineIndex % colors.length];
            if (bars)
              return (
                <g key={line.name}>
                  {line.points.map((point) =>
                    point.value == null ? null : (
                      <rect
                        key={point.date}
                        x={
                          x(dates.indexOf(point.date)) -
                          Math.max(2, (plotWidth / dates.length) * 0.65) / 2
                        }
                        y={Math.min(y(point.value), y(0))}
                        width={Math.max(2, (plotWidth / dates.length) * 0.65)}
                        height={Math.max(1, Math.abs(y(point.value) - y(0)))}
                        fill={point.value < 0 ? "var(--neg)" : color}
                        opacity={0.8}
                      />
                    ),
                  )}
                </g>
              );
            // A missing observation breaks the line instead of implying a value.
            let continuing = false;
            const path = dates
              .map((date, index) => {
                const value = pointMaps[lineIndex].get(date);
                if (value == null) {
                  continuing = false;
                  return "";
                }
                const command = continuing ? "L" : "M";
                continuing = true;
                return command + x(index) + " " + y(value);
              })
              .join(" ");
            return (
              <g key={line.name}>
                <path d={path} fill="none" stroke={color} strokeWidth="2" />
                {dates.length === 1 && line.points[0]?.value != null && (
                  <circle
                    cx={x(0)}
                    cy={y(line.points[0].value)}
                    r="3"
                    fill={color}
                  />
                )}
              </g>
            );
          })}
          <text
            x={PADDING.left}
            y={HEIGHT - 8}
            fill="var(--text-3)"
            fontSize="10"
          >
            {format.date(dates[0])}
          </text>
          <text
            x={WIDTH - PADDING.right}
            y={HEIGHT - 8}
            textAnchor="end"
            fill="var(--text-3)"
            fontSize="10"
          >
            {format.date(dates[dates.length - 1])}
          </text>
          {activeIndex != null && (
            <line
              x1={x(activeIndex)}
              x2={x(activeIndex)}
              y1={PADDING.top}
              y2={HEIGHT - PADDING.bottom}
              stroke="var(--text-3)"
              strokeDasharray="3 3"
            />
          )}
        </svg>
      </div>
      {activeDate && (
        <p className="chart-inspection" role="status">
          {format.date(activeDate)}
          {series.map((line, index) => (
            <span key={line.name}>
              {" "}
              · {line.name}:{" "}
              {formatValue(pointMaps[index].get(activeDate) ?? null)}
            </span>
          ))}
        </p>
      )}
      <div className="legend">
        {series.map((line, index) => (
          <span className="key" key={line.name}>
            <i
              className="sw"
              style={{
                background: line.color || colors[index % colors.length],
              }}
            />
            {line.name}
          </span>
        ))}
      </div>
      <details className="more">
        <summary>View observations</summary>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                {series.map((line) => (
                  <th key={line.name}>{line.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dates.map((date) => (
                <tr key={date}>
                  <td>{date}</td>
                  {pointMaps.map((points, index) => (
                    <td className="num" key={index}>
                      {formatValue(points.get(date) ?? null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
