<gf-campaign-info>
    <div class="container-fluid" if={!hasDismissedWikiGapFinderCampaignInfo()}>
        <div class="row">
            <div class="alert alert-dismissible fade in m-b-0" role="alert">
                <button type="button" class="close" data-dismiss="alert" title="Dismiss" onclick={setDismissedWikiGapFinderCampaignInfo}>
                    <span>&times;</span>
                </button>

                <p> There are four times as many articles about men as there are
                    about women. The figures vary regionally, but no matter how you look
                    at it, the picture is clear: the information about women is less
                    extensive than that about men. Regardless of which language version
                    of Wikipedia you read. We want to change this. WikiGap is an
                    initiative that encourages people around the world to add more
                    content to Wikipedia about women figures, experts and role models in
                    various fields. Read more about WikiGap here: <a
                                                                      href="https://meta.wikimedia.org/wiki/WikiGap">https://meta.wikimedia.org/wiki/WikiGap</a>
                </p>

                <p> The WikiGapFinder helps you discover articles about
                    women that exist in one language but are missing in
                    another. Start by selecting a source language and a
                    target language. WikiGapFinder will find trending
                    articles about women in the source that are missing
                    in the target. If you are interested in writing
                    about women in a particular field, name the field or
                    a woman in that field in the search bar. Click on a
                    card to take a closer look at a missing article to
                    see if you would like to create it from scratch or
                    translate it. </p>
            </div>
        </div>
    </div>

    <script>
    var self = this;

    self.hasDismissedWikiGapFinderCampaignInfo = function () {
        return getCookie('dismissedWikiGapFinderCampaignInfo') == '1';
    };

    self.setDismissedWikiGapFinderCampaignInfo = function () {
        document.cookie = 'dismissedWikiGapFinderCampaignInfo=1';
    };
    </script>
</gf-campaign-info>
