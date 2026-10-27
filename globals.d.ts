// Chart.js est chargé via CDN dans index.html (global `Chart`).
declare class Chart {
  constructor(ctx: CanvasRenderingContext2D | null, config: unknown);
  destroy(): void;
}
