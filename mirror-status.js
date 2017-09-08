$(function() {
  // call the tablesorter plugin
  $("#results").tablesorter({
    textSorter: {
      0: function(a, b, direction, column, table){
        var list_a = a.split('.'); list_a.reverse(); a = list_a.join('.');
        var list_b = b.split('.'); list_b.reverse(); b = list_b.join('.');
        return ((a < b) ? -1 : ((a > b) ? 1 : 0));
      },
    },
    widgets : [ "zebra", "filter" ],
    widgetOptions: {
      filter_useParsedData: false,
    },
  });
});
