$(function() {
  // call the tablesorter plugin
  $("#results").tablesorter({
    widgets : [ "zebra", "filter" ],
    widgetOptions: {
      filter_useParsedData: false,
    },
  });
});
