<gf-preview>
    <div id="previewModal" class="modal fade" role="dialog" tabindex="-1">
        <div class="modal-dialog modal-lg" role="document">
            <div class="modal-content">
                <div class="modal-header">
                    <div class="gf-modal-header-container">
                        <span class="gf-modal-title">{title}</span>
                        <a role="button" class="gf-icon gf-icon-new-window gf-clickable"
                           target="_blank" rel="noopener" href={articleLink} title="{$.i18n('modal-new-window')}">
                        </a>
                        <span class="gf-icon gf-icon-close gf-clickable"
                              data-dismiss="modal" title="{$.i18n('modal-close')}"></span>
                    </div>
                </div>
                <div class="modal-body">
                    <div class="embed-responsive embed-responsive-4by3">
                        <iframe id="previewDiv"></iframe>
                    </div>
                </div>
                <div class="modal-footer">
                    <div class="gf-modal-footer-container">
                        <div class="gf-modal-footer-left dropup">
                            <span class="{gf-icon: true, gf-icon-previous: true, gf-clickable: true, gf-clickable-disabled: showIndex === 0}"
                                  title="{$.i18n('modal-previous')}"
                                  onclick={left}></span>
                            <span class="gf-icon gf-icon-flag gf-clickable dropdown-toggle" data-toggle="dropdown"
                                  title="{$.i18n('article-flag')}"></span>
                            <div class="dropdown-menu dropdown-menu-left">
                                <button type="button" class="dropdown-item" onclick={addToPersonalBlacklist}>
                                    {$.i18n('article-flag-not-interesting')}
                                </button>
                                <button type="button" class="dropdown-item" onclick={addToGlobalBlacklist}>
                                    {$.i18n('article-flag-not-notable', opts.to)}
                                </button>
                            </div>
                            <span class="{gf-icon: true, gf-icon-next: true, gf-clickable: true, gf-clickable-disabled: showIndex > (articles.length - 2)}"
                                  title="{$.i18n('modal-next')}"
                                  onclick={right}></span>
                        </div>
                        <div class="gf-modal-footer-right">
                            <button class="btn btn-secondary" data-dismiss="modal"
                                    onclick={showCreate}>{$.i18n('modal-create-from-scratch')}</button>
                            <a role="button" class="btn btn-primary m-l-1" target="_blank" rel="noopener"
                               onclick={logCXAction} href={translateLink}>{$.i18n('modal-translate')}</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <gf-create></gf-create>

    <script>
        var self = this;

        self.articles = opts.articles || [];
        self.title = opts.title || '';
        self.to = opts.to;
        self.from = opts.from;
        self.translateRoot = '//' + opts.from + '.wikipedia.org/wiki/Special:ContentTranslation?' +
            'from=' + encodeURIComponent(opts.from) +
            '&to=' + encodeURIComponent(opts.to) +
            '&campaign=' + encodeURIComponent(translationAppGlobals.campaign);
        self.articleRoot = '//' + opts.from + '.wikipedia.org/wiki/';
        self.isSrcDocSupported = document.createElement('iframe').srcdoc !== undefined;

        self.index = -1;
        for (var i=0; i<self.articles.length; i++) {
            if (self.articles[i].title === self.title) {
                self.showIndex = i;
                break;
            }
        }

        var previewRoot = 'https://' + opts.from + '.wikipedia.org/w/api.php?action=parse&format=json&origin=*&disableeditsection=1&prop=text|headhtml&page=';

        self.show = function () {
            var showing = self.articles[self.showIndex];
            self.title = showing.title;
            self.translateLink = self.translateRoot + '&page=' + showing.linkTitle;
            self.articleLink = self.articleRoot + showing.linkTitle;
            self.previewUrl = previewRoot + showing.linkTitle;

            self.showPreview('Loading...');

            $.get(self.previewUrl).done(function (data) {
                if (!data.hasOwnProperty('parse')
                    || !data['parse'].hasOwnProperty('text')
                    || !data['parse']['text'].hasOwnProperty('*')
                    || !data['parse'].hasOwnProperty('headhtml')
                    || !data['parse']['headhtml'].hasOwnProperty('*')
                    || !data['parse'].hasOwnProperty('title')){
                    self.showPreview($.i18n('modal-preview-fail'));
                    return;
                }
                var baseUrl = 'https://' + opts.from + '.wikipedia.org/wiki/' + encodeURIComponent(data['parse']['title']);
                var parser = new DOMParser();
                var html = parser.parseFromString(data['parse']['headhtml']['*'], 'text/html');
                html.getElementsByTagName('head')[0].insertAdjacentHTML('afterbegin', '<base href="' + baseUrl + '">');
                html.getElementsByTagName('head')[0].insertAdjacentHTML('beforeend', '<style type="text/css">body {background-color: unset;}</style>');
                html.getElementsByTagName('body')[0].insertAdjacentHTML('afterbegin', data['parse']['text']['*']);
                var wrap = document.createElement('div');
                wrap.appendChild(html.documentElement);
                self.showPreview(wrap.innerHTML);
            }).fail(function (data) {
                self.showPreview($.i18n('modal-preview-fail'));
            });
        };

        self.setPreviewContent = function (data) {
            var iframe = $('#previewDiv')[0];
            $(iframe).attr("srcdoc", data);
            if (!self.isSrcDocSupported) {
                // This is needed to get the iframe content to load in IE, since srcdoc isn't supported yet
                // Found at github.com/jugglinmike/srcdoc-polyfill
                var jsUrl = "javascript: window.frameElement.getAttribute('srcdoc');";
                $(iframe).attr("src", jsUrl);
                iframe.contentWindow.location = jsUrl;
            }
        };

        self.showPreview = function (data) {
            $('#previewModal').on('shown.bs.modal', function (e) {
                // Necessary for Firefox, which has problems reloading the iframe
                self.setPreviewContent(data);
            });

            self.setPreviewContent(data);
            $('#previewModal').modal('show');

            self.update();
        };

        addToPersonalBlacklist () {
            opts.remove(self.articles[self.showIndex], true);
            $('#previewModal').modal('hide');
        }

        addToGlobalBlacklist () {
            opts.remove(self.articles[self.showIndex], false);
            $('#previewModal').modal('hide');
        }

        left () {
            if (self.showIndex > 0) {
                self.showIndex --;
                self.show();
            }
        }

        right () {
            if (self.showIndex < self.articles.length - 1) {
                self.showIndex ++;
                self.show();
            }
        }

        self.logCXAction = function() {
            logAction(self.title, 'create_using_content_translation');
            return true;
        };

        showCreate (e) {
            riot.mount('gf-create', {
                title: self.title,
                to: self.to,
                from: self.from,
                remove: self.remove
            });

            $('#createModal').modal('show');
        }

        $('#previewModal').on('hide.bs.modal', function (e) {
            self.setPreviewContent('');
        });

        self.on('mount', function () {
            if (isFinite(self.showIndex)) {
                self.show();
            }
        });
    </script>

</gf-preview>
