/** Shimmering placeholder blocks shown while data loads — friendlier than a
 * bare "Loading…". `lines` stacks that many bars; `height`/`width` size one. */
export default function Skeleton({
  lines = 1,
  height = 14,
  width = "100%",
}: {
  lines?: number;
  height?: number;
  width?: string | number;
}) {
  return (
    <>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{
            height,
            width: i === lines - 1 && lines > 1 ? "60%" : width,
            marginBottom: lines > 1 ? 8 : 0,
          }}
        />
      ))}
    </>
  );
}

/** A card-shaped skeleton for whole-panel loading states. */
export function SkeletonCard() {
  return (
    <div className="card">
      <Skeleton lines={4} height={16} />
    </div>
  );
}
