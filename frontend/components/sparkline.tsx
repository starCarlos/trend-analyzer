type SparklinePoint = {
  bucket_start: string;
  value: number;
};

type SparklineProps = {
  points: SparklinePoint[];
};

function buildPath(points: SparklinePoint[], width: number, height: number) {
  if (!points.length) {
    return { line: "", area: "" };
  }

  const values = points.map((point) => point.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  const coordinates = points.map((point, index) => {
    const x = (index / Math.max(points.length - 1, 1)) * width;
    const y = height - ((point.value - min) / range) * height;
    return [x, y] as const;
  });

  const line = coordinates.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
  const area = `${line} L ${width} ${height} L 0 ${height} Z`;
  return { line, area };
}

export function Sparkline({ points }: SparklineProps) {
  const { line, area } = buildPath(points, 320, 92);

  if (!line) {
    return <div className="empty-state">No points yet. Run a search to let backfill populate this source.</div>;
  }

  return (
    <svg className="sparkline" viewBox="0 0 320 92" preserveAspectRatio="none" role="img" aria-label="Trend sparkline">
      <path className="sparkline-area" d={area} />
      <path className="sparkline-path" d={line} />
    </svg>
  );
}
