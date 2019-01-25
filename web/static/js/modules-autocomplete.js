$(function () {
    var datalist = $('#modules-autocomplete').flexdatalist({
        searchIn: 'name',
        searchDelay: 0,
        focusFirstResult: true,
        multiple: true,
        visibleProperties: ['name', 'description'],
        minLength: 0
    })[0];

    // Make sure current value is validated when focus is lost
    var alias = $('.flexdatalist-alias');
    alias.on('focusout', function (event) {
        // Add a small delay to make sure click event was processed
        setTimeout(function () {
            datalist.fvalue.extract(alias[0].value);
        }, 100);
    });
});
