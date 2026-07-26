import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

/** Plot component bound to the lightweight dist-min bundle (imported once here). */
export const Plot = createPlotlyComponent(Plotly);
export { Plotly };
