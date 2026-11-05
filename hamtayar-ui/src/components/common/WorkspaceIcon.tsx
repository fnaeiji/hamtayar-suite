const paths: Record<string, string> = {
  search: 'M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15 M16 16l5 5',
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  code: 'm8 7-5 5 5 5 m8-10 5 5-5 5 m-3-13-2 20',
  documents: 'M12 16V3 m-5 5 5-5 5 5 M4 15v6h16v-6',
  qa: 'M21 11a8 8 0 0 1-8 8H8l-5 3V11a9 9 0 0 1 18 0Z M8 10h8 M8 14h5',
};
export function WorkspaceIcon({ kind }: { kind: string }) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[kind] ?? paths.overview} />
    </svg>
  );
}
