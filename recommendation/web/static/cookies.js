var getCookie = function (name) {
    // adapted from
    // https://developer.mozilla.org/en-US/docs/Web/API/Document/cookie/Simple_document.cookie_framework
    return document.cookie.replace(new RegExp("(?:(?:^|.*;)\\s*" + name + "\\s*\\=\\s*([^;]*).*$)|^.*$"), "$1") || null;
};

var writeCookie = function (key, value) {
    document.cookie = key + '=' + value;
};
