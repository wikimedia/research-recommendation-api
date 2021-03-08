var logUIRequest = function (
    sourceLanguage,
    targetLanguage,
    seed,
    origin,
    searchAlgorithm,
    userId,
    campaign,
    campaignCondition
) {
    var schema = 'TranslationRecommendationUIRequests';
    var revision = 15484897;
    var event = {
        'timestamp': Math.floor(new Date().getTime() / 1000),
        'userAgent': navigator.userAgent,
        'sourceLanguage': sourceLanguage,
        'targetLanguage': targetLanguage,
        'origin': origin,
        'userToken': getUserToken(),
        'requestToken': getNewRequestToken()
    };
    if ( seed !== undefined ) {
        event['seed'] = seed;
    }
    if ( searchAlgorithm !== undefined ) {
        event['searchAlgorithm'] = searchAlgorithm;
    }
    if ( userId !== undefined ) {
        event['userId'] = userId;
    }
    if ( campaign !== undefined ) {
        event['campaign'] = campaign;
    }
    if ( campaignCondition !== undefined ) {
        event['campaignCondition'] = campaignCondition;
    }
    logEvent(schema, revision, event);
};

var logAction = function (
    pageTitle,
    action,
    targetTitle
) {
    var schema = 'TranslationRecommendationUserAction';
    var revision = 15858947;
    var event = {
        'requestToken': getExistingRequestToken(),
        'pageTitle': pageTitle,
        'action': action
    };
    if ( targetTitle !== undefined ) {
        event['targetTitle'] = targetTitle;
    }
    logEvent(schema, revision, event);
};

var getUserToken = function () {
    var token = getCookie('userToken');
    if (!token) {
        token = generateToken();
        writeCookie('userToken', token);
    }
    return token;
};

var getNewRequestToken = function () {
    var token = generateToken();
    writeCookie('requestToken', token);
    return token;
};

var getExistingRequestToken = function () {
    return getCookie('requestToken');
};

var generateToken = function () {
    // http://stackoverflow.com/questions/105034/create-guid-uuid-in-javascript?lq=1
    var d = new Date().getTime();
    if (window.performance && typeof window.performance.now === "function"){
        d += performance.now(); //use high-precision timer if available
    }
    var uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = (d + Math.random()*16)%16 | 0;
        d = Math.floor(d/16);
        return (c=='x' ? r : (r&0x3|0x8)).toString(16);
    });
    return uuid;
};

var logEvent = function(schema, revision, event) {
    var eventData = {
        schema: schema,
        $schema: `/analytics/legacy/${schema.toLowerCase()}/1.0.0`,
        revision: revision,
        event: event,
        webHost: location.hostname,
        client_dt: new Date().toISOString(),
        meta: {
            stream: 'eventlogging_'+ schema,
            domain: location.hostname
        }
    };

    try {
        navigator.sendBeacon(
            'https://intake-analytics.wikimedia.org/v1/events?hasty=true',
            JSON.stringify(eventData)
        );
    } catch (error) {
        console.log(error);
    }
};
