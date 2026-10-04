const ICON_PATHS: Record<string, string[]> = {
  grid: ["M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z"],
  activity: ["M3 12h4l3-8 4 16 3-8h4"],
  layers: ["m12 3 9 5-9 5-9-5 9-5z", "m3 12 9 5 9-5", "m3 16 9 5 9-5"],
  star: [
    "m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.4-5.7-3-5.7 3 1.1-6.4-4.6-4.5 6.4-.9z",
  ],
  brief: ["M7 3h10v3H7z", "M7 5H4v16h16V5h-3", "M8 11h8 M8 15h8"],
  book: [
    "M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1z",
    "M12 5v15",
  ],
  search: ["M20 20l-5-5", "M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0"],
  arrow: ["M4 12h15 m-5-5 5 5-5 5"],
  down: ["M12 4v14 m-5-5 5 5 5-5", "M4 21h16"],
  trend: ["m3 17 6-6 4 4 8-10", "M15 5h6v6"],
  shield: ["m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z", "m8 12 3 3 5-6"],
  globe: [
    "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    "M3 12h18 M12 3c-5 6-5 12 0 18 5-6 5-12 0-18",
  ],
};

export function Icon({ name }: { name: string }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {(ICON_PATHS[name] || ICON_PATHS.activity).map((d, index) => (
        <path key={index} d={d} />
      ))}
    </svg>
  );
}
