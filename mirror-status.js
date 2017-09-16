$(function() {
  $.tablesorter.addParser({
    id: 'hostname',
    is: function (s) {
      return false;
    },
    format: function (s, table, cell) {
      var $cell = $(cell);
      var t = $cell.attr('data-text') || s;
      var list_t = t.split('.');
      list_t.reverse();
      return list_t.join('.');
    },
    type: 'text'
  });

  // call the tablesorter plugin
  $("#results").tablesorter({
    widgets: [
      "filter",
      "sort2Hash",
      "zebra",
    ],
    widgetOptions: {
      filter_useParsedData: false,
    },
  });
});
