// Chart.js est chargé via CDN dans index.html (global `Chart`).
declare class Chart {
  constructor(item: HTMLCanvasElement | CanvasRenderingContext2D | null, config: unknown);
  destroy(): void;
}
