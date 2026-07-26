// The dist-min build and the factory subpath ship no types; declare them so we
// can build the Plot component from the lightweight bundle with full typing.
declare module "plotly.js-dist-min" {
  const Plotly: typeof import("plotly.js");
  export default Plotly;
}

declare module "react-plotly.js/factory" {
  import type { ComponentType } from "react";
  import type { PlotParams } from "react-plotly.js";
  export default function createPlotlyComponent(plotly: unknown): ComponentType<PlotParams>;
}
