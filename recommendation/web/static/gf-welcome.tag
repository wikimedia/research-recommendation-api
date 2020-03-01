<gf-welcome>
    <div class="container-fluid" if={hasCampaign()}>
        <div class="row">
            <div class="col-sm-12">
                 <br/>
                 <h4>Welcome to the '{campaign}' campaign!</h4>
            </div>
        </div>
    </div>

    <script>
        var self = this;

        self.hasCampaign = function () {
            return window.translationAppGlobals.campaign !== '';
        }

        self.campaign = window.translationAppGlobals.campaign;
    </script>
</gf-welcome>
