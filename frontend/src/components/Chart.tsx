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
  const barSlotWidth = plotWidth / Math.max(dates.length, 1);
  const barWidth = Math.min(36, Math.max(3, barSlotWidth * 0.68));
  const x = (index: number) =>
    PADDING.left +
    (dates.length === 1
      ? plotWidth / 2
      : (index / (dates.length - 1)) * plotWidth);
  const barX = (index: number) =>
    PADDING.left +
    index * barSlotWidth +
    (barSlotWidth - barWidth) / 2;
  const activeX = (index: number) =>
    bars ? barX(index) + barWidth / 2 : x(index);
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
            const relativePosition = Math.max(
              0,
              Math.min(plotWidth, position - PADDING.left),
            );
            setSelectedIndex(
              Math.max(
                0,
                Math.min(
                  dates.length - 1,
                  bars
                    ? Math.floor(
                        (relativePosition / plotWidth) * dates.length,
                      )
                    : Math.round(
                        (relativePosition / plotWidth) *
                          (dates.length - 1),
                      ),
                ),
              ),
            );
          }}
        >
          <rect
            x={PADDING.left}
            y={PADDING.top}
            width={plotWidth}
            height={plotHeight}
            rx="4"
            fill="var(--chart-plot)"
          />
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
          {bars && low < 0 && high > 0 && (
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={y(0)}
              y2={y(0)}
              stroke="var(--text-3)"
              strokeWidth="1.25"
            />
          )}
          {series.map((line, lineIndex) => {
            const color = line.color || colors[lineIndex % colors.length];
            if (bars)
              return (
                <g key={line.name}>
                  {line.points.map((point) => {
                    if (point.value == null) return null;
                    const pointIndex = dates.indexOf(point.date);
                    const isActive = activeIndex === pointIndex;
                    return (
                      <rect
                        key={point.date}
                        className="chart-bar"
                        x={barX(pointIndex)}
                        y={Math.min(y(point.value), y(0))}
                        width={barWidth}
                        height={Math.max(1, Math.abs(y(point.value) - y(0)))}
                        fill={point.value < 0 ? "var(--neg)" : color}
                        opacity={
                          activeIndex == null || isActive ? 0.82 : 0.42
                        }
                        stroke={isActive ? "var(--text)" : undefined}
                        strokeWidth={isActive ? 1.25 : undefined}
                        rx="2"
                      />
                    );
                  })}
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
                {dates.map((date, index) => {
                  const value = pointMaps[lineIndex].get(date);
                  if (
                    value == null ||
                    (dates.length > 1 && activeIndex !== index)
                  )
                    return null;
                  return (
                    <circle
                      key={date}
                      cx={x(index)}
                      cy={y(value)}
                      r="4"
                      fill={color}
                      stroke="var(--panel)"
                      strokeWidth="2"
                    />
                  );
                })}
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
              x1={activeX(activeIndex)}
              x2={activeX(activeIndex)}
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
          <strong>{format.date(activeDate)}</strong>
          {series.map((line, index) => (
            <span key={line.name}>
              <i
                className="inspection-dot"
                style={{
                  background: line.color || colors[index % colors.length],
                }}
              />
              {line.name}:{" "}
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
          <table className="data-table observation-table">
            <thead>
              <tr>
                <th scope="col">Date</th>
                {series.map((line) => (
                  <th className="num" scope="col" key={line.name}>
                    {line.name}
                  </th>
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
