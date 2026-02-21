"use client";

import * as d3 from "d3";
import { useEffect, useRef } from "react";

export type BarDatum = { label: string; value: number };

export default function BarChart({
  data,
  height = 220,
}: {
  data: BarDatum[];
  height?: number;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // reset before redraw

    const width = 520;
    const margin = { top: 10, right: 10, bottom: 40, left: 40 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3
      .scaleBand<string>()
      .domain(data.map((d) => d.label))
      .range([0, innerW])
      .padding(0.2);

    const y = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d: BarDatum) => d.value) ?? 1])
      .nice()
      .range([innerH, 0]);

    g.append("g").call(d3.axisLeft(y).ticks(4));
    g.append("g")
      .attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .style("text-anchor", "end")
      .attr("dx", "-0.6em")
      .attr("dy", "0.15em")
      .attr("transform", "rotate(-35)");

    g.selectAll("rect")
      .data(data)
      .enter()
      .append("rect")
      .attr("x", (d: BarDatum) => x(d.label) ?? 0)
      .attr("y", (d: BarDatum) => y(d.value))
      .attr("width", x.bandwidth())
      .attr("height", (d: BarDatum) => innerH - y(d.value))
      .attr("fill", "teal");
  }, [data, height]);

  return <svg ref={svgRef} />;
}