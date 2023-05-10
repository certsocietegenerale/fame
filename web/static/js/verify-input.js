
$("form[id='submit']").on("submit", function(event) {
  if($('.nav-pills a[href="#url"]').attr('aria-expanded') == "true") {
    let parser = document.createElement('a');

    parser.href = $("input[name='url']").val();
    if ($("input[name='url']").val().indexOf('://') == -1) {
      parser.href = 'http://' + $("input[name='url']").val(); // force the URL to be considered as absolute
    }

    if((parser.protocol != "https:" && parser.protocol != "http:") || parser.hostname.indexOf('.') == -1) {
      msg = "This does not look like a valid URL. Are you sure you want to analyze it?\nYou can force the analysis by clicking on \"OK\"."
      if (!confirm(msg)) {
        event.preventDefault();
      }
    } else {
      event.preventDefault();
      $.ajax({
        url: "/analyses/is_safe_url",
        method: 'POST',
        context: $(this),
        data: { url: $("input[name='url']").val()},
      }).done(function (data) {
          msg = "This URL seems to point to an internal or fully trusted domain. Are you sure you want to analyze it?\nYou can force the analysis by clicking on \"OK\"."
          if(!data.is_safe || confirm(msg)) {
            this.off('submit');
            this.submit();
          }
      });
    }
  } else if ($('.nav-pills a[href="#hash"]').attr('aria-expanded') == "true") {
    let hash = $("input[name='hash']").val();
    if (!/^[a-fA-F0-9]{32}$/.test(hash) // MD5
     && !/^[a-fA-F0-9]{40}$/.test(hash) // SHA1
     && !/^[a-fA-F0-9]{56}$/.test(hash) // SHA224
     && !/^[a-fA-F0-9]{64}$/.test(hash) // SHA256
     && !/^[a-fA-F0-9]{96}$/.test(hash) // SHA384
     && !/^[a-fA-F0-9]{128}$/.test(hash)) { // SHA512
      msg = "This does not look like a valid hash format. Are you sure you want to analyze it?\nYou can force the analysis by clicking on \"OK\"."
      if (!confirm(msg)) {
        event.preventDefault();
      }
     }
  }
});
