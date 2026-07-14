/** Investor-kind badge (friends & family / angel / institutional). */
export default function KindBadge({ kind }: { kind: string }) {
  return <span className="badge">{kind === "friend_family" ? "F&F" : kind}</span>;
}
