"use client";

import * as d3 from "d3";
import { useEffect, useRef } from "react";

const data = [25, 40, 60, 80, 20, 90, 50];

export default function BarChart() {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // reset before redraw

    svg
      .selectAll("rect")
      .data(data)
      .enter()
      .append("rect")
      .attr("x", (_, i) => i * 40)
      .attr("y", (d) => 200 - d)
      .attr("width", 30)
      .attr("height", (d) => d)
      .attr("fill", "teal");
  }, []);

  return <svg ref={svgRef} width={400} height={200}></svg>;
}