$(function () {
  $('.tags-remove-link').click(function (e) {
    e.preventDefault();

    form = $(this).parent().find('form').first();
    group = form.find('input').val();
    if (confirm("Do you really want to remove access to this file from group '" + group + "' ?")) {
      form.submit();
    }
  });

  $('#add-sharing-group').click(function (e) {
    e.preventDefault();

    form = $('#add-sharing-group-form');
    group = prompt("Share with group");
    if (group) {
      form.find('input').val(group);
      form.submit();
    }
  });

  $('#change-file-type').click(function (e) {
    e.preventDefault();

    form = $('#change-file-type-form');
    type = prompt("New type");
    if (type) {
      form.find('input').val(type);
      form.submit();
    }
  });
});
