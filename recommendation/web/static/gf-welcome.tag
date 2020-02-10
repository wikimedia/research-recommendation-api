<gf-welcome>
    <div class="container-fluid" if={hasCampaign()}>
        <div class="row">
            <div class="alert alert-primary" role="alert">
                <h4>Welcome to the '{campaign}' campaign!</h4>
                <p if={hasCampaignLink()}>For more information, see
                   here: <a href="{campaignLink}">{campaignLink}</a>
                </p>
            </div>
        </div>
    </div>

    <script>
        var self = this;

        self.hasCampaign = function () {
            return window.translationAppGlobals.campaign !== '';
        }

        self.hasCampaignLink = function () {
            return window.translationAppGlobals.campaignLink !== '';
        }

        self.campaign = window.translationAppGlobals.campaign;
        self.campaignLink = window.translationAppGlobals.campaignLink;
    </script>
</gf-welcome>
