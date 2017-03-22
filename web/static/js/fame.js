var should_refresh = true;
var old_should_refresh = true;

function enable_checkboxes() {
  $('[data-toggle="checkbox"]').each(function () {
    if($(this).data('toggle') == 'switch') return;

    var $checkbox = $(this);
    $checkbox.checkbox();
  });
}

function auto_update(url, time, selector) {
  setTimeout(function () {
    if (should_refresh) {
      $.get(url).success(function (html) {
        if (should_refresh) {
          html = $(html);
          $(selector).each(function (i) {
            id = $(this).attr('id');
            $(this).html(html.find('#' + id).html());
          });
        } else {
          auto_update(url, time, selector);
        }
      });
    } else {
      auto_update(url, time, selector);
    }
  }, time);
}

function add_options_to_select(select) {
  return function(data) {
    for (var i = 0; i < data.modules.length; i++) {
      var module = data.modules[i];
      select.append('<option value="' + module + '">' + module + '</option>');
    }
  };
}

function add_options() {
  $('select[data-addoptions]').each(function (index) {
    select = $(this);
    url = select.data('addoptions');
    $.getJSON(url).success(add_options_to_select(select));
  });
}

function enable_toggle_links() {
  $('#main-content').on('click', 'a.toggle', function (e) {
    parent = $(this).closest('.toggle-block');
    parent.find('.toggle').toggle();

    e.preventDefault();
  });
}

function enable_delete_links() {
  $('#main-content').on('click', 'a.timeline-delete', function (e) {
    parent = $(this).closest('.timeline-entry');
    url = $(this).attr('href');
    $.ajax({
      url: url,
      method: 'DELETE'
    }).success(function (data) {
      parent.remove();
    });

    e.preventDefault();
  });
}

function enable_confirm_dialogs() {
  $('[data-confirm]').submit(function (event) {
    var confirm_message = $(this).data('confirm');
    if (!confirm(confirm_message)) {
      event.preventDefault();
    }
  });
}

function disable_autorefresh() {
  old_should_refresh = should_refresh;

  if (should_refresh) {
    $('#auto-refresh').checkbox('uncheck');
  }
}

function enable_autorefresh() {
  if (old_should_refresh) {
    $('#auto-refresh').checkbox('check');
  }
}

//
// Code related to IOC submission
//

function enable_ioc_submission() {
  $('#main-content').on('click', '.ioc-submission-link', function (e) {
    e.preventDefault();

    var url = $(this).attr('href');

    $('#ioc-submission input[type=hidden]').val(url);

    $('#ioc-display').hide();
    $('#ioc-submission').show();
    disable_autorefresh();
  });

  $('#main-content').on('click', '#ioc-submission-cancel', function (e) {
    $('#ioc-submission').hide();
    $('#ioc-display').show();
    enable_autorefresh();

    e.preventDefault();
  });

  $('#main-content').on('submit', '#ioc-submission', function(e) {
    // Display spinner
    $('#ioc-submission .feedback').toggleClass('hidden');

    var iocs = [];
    var url = $('#ioc-submission input[type=hidden]').val();
    var tags = $('#ioc-submission-tags').val();
    var module = url.split('/');
    module = module[module.length -1 ];

    $('.submission-single-ioc').each(function (index) {
      var line = $(this);
      if (line.find('input[type=checkbox]').is(':checked')) {
        var ioc = {
          value: line.find('.submission-ioc-value').text(),
          sources: line.find('.submission-ioc-sources').text(),
          tags: line.find('input[name=tags]').val() + ',' + tags
        };
        iocs.push(ioc);
      }
    });

    function callback(data) {
      $('#ioc-submission').hide();
      $('#ioc-sendto-' + module).toggleClass('hidden');
      $('#ioc-submission .feedback').toggleClass('hidden');
      $('#ioc-sent-' + module).toggleClass('hidden');
      $('#ioc-display').show();
      enable_autorefresh();
    }

    function errorCallback(data) {
      $('#ioc-submission').hide();
      $('#ioc-submission .feedback').toggleClass('hidden');
      $('#ioc-display').show();
      enable_autorefresh();

      $.notify({
            message: "Could not send to " + module
         }, {
             type: "danger",
             offset: {
                 y: 50,
                 x: 30
             }
         });
    }

    $.ajax({
      type: 'POST',
      url: url,
      data: JSON.stringify(iocs),
      success: callback,
      error: errorCallback,
      contentType: 'application/json',
    });

    e.preventDefault();
  });
}

//
// Code related to Antivirus submission
//

function enable_av_submission() {
  $('#main-content').on('click', '.av-submission-link', function (e) {
    e.preventDefault();

    var url = $(this).attr('href');
    var module = $(this).data('module');

    $('#av-sendto-' + module + ' i').removeClass('fa-send');
    $('#av-sendto-' + module + ' i').addClass('fa-spinner spinner');

    function callback(data) {
      if (data == 'ok') {
        $('#av-sendto-' + module).addClass('hidden');
        $('#av-sent-' + module).removeClass('hidden');
      }
      else {
        $('#av-sendto-' + module + ' i').removeClass('fa-spinner spinner');
        $('#av-sendto-' + module + ' i').addClass('fa-send');

        $.notify({
              message: data
           }, {
               type: "danger",
               offset: {
                   y: 50,
                   x: 30
               }
           });
      }
    }

    function errorCallback(data) {
      $('#av-sendto-' + module + ' i').removeClass('fa-spinner spinner');
      $('#av-sendto-' + module + ' i').addClass('text-danger fa-exclamation-triangle');

      $.notify({
            message: "Could not send to " + module
         }, {
             type: "danger",
             offset: {
                 y: 50,
                 x: 30
             }
         });
    }

    $.ajax({
      type: 'POST',
      url: url,
      success: callback,
      error: errorCallback,
      contentType: 'application/json',
    });
  });
}


function enable_autorefresh_switch() {
  $('.content').on('change', '#auto-refresh', function (e) {
    should_refresh = !should_refresh;
  });
}

$(function () {
  $('#file-field').fileinput({
    browseClass: "btn btn-info btn-fill",
    showUpload: false,
    showPreview: false,
    showRemove: false,
  });

  $('#private_repository').change(function (e) {
    $('#private_repository_warning').toggleClass('collapse');
  });

  add_options();
  enable_toggle_links();
  enable_delete_links();
  enable_ioc_submission();
  enable_av_submission();
  enable_confirm_dialogs();
  enable_autorefresh_switch();
});
