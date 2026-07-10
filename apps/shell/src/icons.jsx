/* icons.jsx — minimal line-icon set (ported verbatim from the Claude Design handoff). */
const P = {
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  check: <><path d="m5 12.5 4.2 4.2L19 7" /></>,
  chevR: <><path d="m9 6 6 6-6 6" /></>,
  chevD: <><path d="m6 9 6 6 6-6" /></>,
  dots: <><circle cx="5" cy="12" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="19" cy="12" r="1.4" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  moon: <><path d="M20 14.5A8 8 0 1 1 9.5 4a6.3 6.3 0 0 0 10.5 10.5Z" /></>,
  panel: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M14 4v16" /></>,
  expand: <><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3" /></>,
  minimize: <><path d="M9 3v3a2 2 0 0 1-2 2H4M21 9h-3a2 2 0 0 1-2-2V4M4 15h3a2 2 0 0 1 2 2v3M16 20v-3a2 2 0 0 1 2-2h3" /></>,
  close: <><path d="M6 6l12 12M18 6 6 18" /></>,
  send: <><path d="M7 11l5-5 5 5M12 6v13" /></>,
  spark: <><path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z" /></>,
  attach: <><path d="M9 8v8a3 3 0 0 0 6 0V7a4 4 0 0 0-8 0v9" /></>,
  filter: <><path d="M3 5h18M6 12h12M10 19h4" /></>,
  flag: <><path d="M5 21V4M5 4h11l-2 4 2 4H5" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></>,
  bolt: <><path d="M13 2 4 13h6l-1 9 9-11h-6z" /></>,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h8" /></>,
  refresh: <><path d="M3 12a9 9 0 0 1 15-6.7L21 8M21 4v4h-4M21 12a9 9 0 0 1-15 6.7L3 16M3 20v-4h4" /></>,
  note: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M8 13h8M8 17h5" /></>,
  book: <><path d="M5 4a2 2 0 0 1 2-2h12v18H7a2 2 0 0 0-2 2z" /><path d="M5 18h14" /></>,
  key: <><circle cx="8" cy="14" r="4" /><path d="M11 11 21 1M18 4l2 2M15 7l2 2" /></>,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>,
  play: <><path d="M7 5l12 7-12 7z" /></>,
  pause: <><path d="M8 5v14M16 5v14" /></>,
  link: <><path d="M9 15l6-6M10 6l1-1a4 4 0 0 1 6 6l-1 1M14 18l-1 1a4 4 0 0 1-6-6l1-1" /></>,
  upload: <><path d="M12 16V4M7 9l5-5 5 5M5 20h14" /></>,
  lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  star: <><path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6.1L12 17l-5.4 2.8 1.2-6.1-4.5-4.2 6.1-.7z" /></>,
  shield: <><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" /></>,
  grid: <><rect x="4" y="4" width="7" height="7" rx="1" /><rect x="13" y="4" width="7" height="7" rx="1" /><rect x="4" y="13" width="7" height="7" rx="1" /><rect x="13" y="13" width="7" height="7" rx="1" /></>,
  scale: <><path d="M12 3v18M5 7h14M5 7l-3 7h6zM19 7l-3 7h6zM7 21h10" /></>,
  wand: <><path d="m5 19 11-11M14 4l1.5 1.5M19 9l1.5 1.5M18 4l.5-1.5M21 7l1.5-.5" /><path d="m4 14 1 1" /></>,
  gauge: <><path d="M5 18a8 8 0 1 1 14 0" /><path d="M12 14l4-4" /></>,
  arrowR: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  diff: <><path d="M12 3v18M3 7l4-4 4 4M21 17l-4 4-4-4" /></>,
  pencil: <><path d="M17 3l4 4L8 20l-5 1 1-5z" /><path d="M15 5l4 4" /></>,
};

export function Icon({ name, size = 16, sw = 1.7, style, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
      aria-hidden="true"
    >
      {P[name]}
    </svg>
  );
}
