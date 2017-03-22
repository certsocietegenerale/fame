$(function () {
    var resultsTemplate = Handlebars.compile($('#modules-results').html());
    var emptyTemplate = Handlebars.compile($('#modules-empty').html());

    function customTokenizer(datum) {
      var nameTokens = Bloodhound.tokenizers.whitespace(datum.name);
      var descriptionTokens = Bloodhound.tokenizers.whitespace(datum.description);

      return nameTokens.concat(descriptionTokens);
    }

    var input = $('#typeahead-modules');

    var modules = new Bloodhound({
      datumTokenizer: customTokenizer,
      queryTokenizer: Bloodhound.tokenizers.whitespace,
      prefetch: {
        url: input.data('url'),
        cache: false,
        transform: function(response) {
          return response.modules;
        }
      }
    });

    modules.initialize(true);

    input.typeahead({
      hint: true,
      highlight: true,
      minLength: 1
    },
    {
      displayKey: 'name',
      templates: {
        suggestion: resultsTemplate,
        empty: emptyTemplate
      },
      source: modules
    });
});
