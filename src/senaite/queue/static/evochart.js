jQuery(function($){
  $(document).ready(function(){
    var data = JSON.parse($("#queue_data").html());
    if (data.length < 2) {
      return;
    }

    $(".chart-container").fadeIn("slow");

    var margin = {top: 20, right: 170, bottom: 20, left: 40},
        width = $('#chart').innerWidth() - margin.left - margin.right,
        height = 200 - margin.top - margin.bottom;

    var format_date = d3.time.format("%Y%m%d%H%M%S")
    var parse_date = format_date.parse;

    var color = d3.scale.category10();


    data.forEach(function(d) {
        d.date = parse_date(d.datetime);
    });

    function get_data_values(data, name) {
      return data.map(function(d) {
        return {date: d.date, num: +d[name]};
      });
    }

    // Extract the keys for series
    var keys = d3.set(["failed", "queued"])
    color.domain(keys.values());

    var series = color.domain().map(function(name) {
        return {
          name: name,
          values: get_data_values(data, name),
        };
    });

    var x_min = d3.min(data, function(d){ return d.date; });
    var x_max = d3.max(data, function(d){ return d.date; });
    var y_min = d3.min(series, function(c) {
      return d3.min(c.values, function(v) {
        return (typeof v === 'undefined') ? 1 : v.num;
      });
    });
    var y_max = d3.max(series, function(c) {
      return d3.max(c.values, function(v) {
        return (typeof v === 'undefined') ? 0 : v.num;
      });
    });

    var x = d3.time.scale()
        .range([0, width]);

    var y = d3.scale.linear()
        .range([height,0]);

    var xAxis = d3.svg.axis()
        .scale(x)
        .orient("bottom")
        .tickSize(0);

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient("left")
        .tickSize(5)
        .tickFormat(d3.format("~s"))
        .ticks(5);

    var line = d3.svg.line()
        .interpolate("linear")
        .x(function(d) { return x(d.date); })
        .y(function(d) { return y(d.num); });

    $('#chart').append('<svg></svg>');
    var svg = d3.select("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    x.domain(d3.extent(data, function(d) { return d.date; }));
    y.domain([y_min, y_max]);

    // Y-axis
    svg.append("g")
        .attr("class", "y axis")
        .attr("fill", "#3f3f3f")
        .style("font-size", "11px")
        .call(yAxis)

    // X-axis
    svg.append("g")
      .attr("class", "x axis")
      .attr("fill", "#3f3f3f")
      .attr("transform", "translate(0," + height + ")")
      .style("font-size", "11px")
      .call(xAxis)
        .append("text")
          .attr("fill", "#3f3f3f")
          .attr("x", width)
          .attr("dy", "-0.71em")
          .style("text-anchor", "end")
          .text("Time");

    // Y-axis gridlines
    svg.append("g")
        .attr("class", "grid")
        .call(yAxis
            .tickSize(-width)
            .tickFormat("")
        )

    // Y-axis legend
    var y_legend = "Count";
    svg.append("text")
        .attr("fill", "#3f3f3f")
        .attr("transform", "rotate(-90)")
        .attr("y", 6)
        .attr("dy", ".71em")
        .attr("text-anchor", "end")
        .style("font-size", "11px")
        .text(y_legend);

    var serie = svg.selectAll(".serie")
      .data(series)
    .enter().append("g")
      .attr("class", "serie");

    // Line path
    serie.append("path")
      .attr("class", "line")
      .attr("fill", "none")
      .attr("stroke-width", function(d) {
        return "1.5px";
      })
      .attr("d", function(d) {
        return line(d.values);
      })
      .style("stroke", function(d) {
        return color(d.name);
      })
      .on("mouseout", function() {
        d3.select(this)
          .attr("stroke-width", function(d) {
            return "1.5px";
          });
      })
      .on("mouseover",  function() {
        d3.select(this)
          .attr("stroke-width", "4px");
      });

    serie.append("text")
      .datum(function(d) {
        // Get the last non empty value for this serie
        var last_val = 0;
        for (var i = d.values.length - 1; i >= 0; i--) {
          var val = d.values[i];
          if (!Number.isNaN(val.num)) {
            last_val = val;
            break;
          }
        }
        return {name: d.name, value: last_val};
      })
      .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + y(d.value.num) + ")"; })
      .attr("x", 10)
      .style("font-size", "11px")
      .style("fill", function(d) {
        if (d.name == "TOTAL") {
          return "#666";
        }
        return color(d.name);})
      .attr("dy", ".35em")
      .text(function(d) { return d.name; });

    series.forEach(function(d) {
        vals = d.values;
        col = color(d.name);
        vals.forEach(function(v) {
            svg.append("circle")
              .attr("r", 2)
              .style("stroke", col)
              .style("stroke-width", 12)
              .style("stroke-opacity", .0)
              .style("fill", col)
              .attr("cx", x(v.date))
              .attr("cy", y(v.num))
              .on("mouseout", function() {
                  last = this.parentNode.children.length;
                  d3.select(this)
                      .attr("r", 3)
                      .style("stroke-opacity", .0);
                  d3.select(this.parentNode.children[last-1])
                      .remove();
              })
              .on("mouseover",  function() {
                  d3.select(this).transition()
                      .duration(150)
                      .attr("r", 5)
                      .style("stroke-opacity", .3);

                  d3.select(this.parentNode)
                      .append("text")
                          .transition()
                          .duration(150)
                          .attr("fill", "#333")
                          .style("font-size", "11px")
                          .attr("x", x(v.date) + 6)
                          .attr("y", y(v.num) - 9)
                          .text(d3.time.format("%e %b")(v.date) +": " +v.num)
              })

        });
    });
  });
});
