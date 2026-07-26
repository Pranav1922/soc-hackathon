/**
 * Fixed, GPU-light animated backdrop: a slowly drifting aurora gradient, two soft
 * floating glow blobs, a masked grid, and a subtle drifting particle field.
 * Pure CSS (see index.css) — no JS loop, honours prefers-reduced-motion.
 */
export default function Background() {
  return (
    <div className="aegis-bg" aria-hidden="true">
      <div className="aegis-bg__aurora" />
      <div className="aegis-bg__blob aegis-bg__blob--1" />
      <div className="aegis-bg__blob aegis-bg__blob--2" />
      <div className="aegis-bg__grid" />
      <div className="aegis-bg__dots" />
    </div>
  );
}
