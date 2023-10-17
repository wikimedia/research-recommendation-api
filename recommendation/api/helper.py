import flask
import flask_restplus as restplus


def build_api(name, import_name, url_prefix=None):
    blueprint = flask.Blueprint(name, import_name, url_prefix=url_prefix)
    api = restplus.Api(blueprint, validate=True)

    class Spec(restplus.Resource):
        def get(self):
            return flask.jsonify(api.__schema__)

    @blueprint.after_request
    def after_request(response):
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add(
            "Access-Control-Allow-Headers", "Content-Type,Authorization"
        )
        response.headers.add("Access-Control-Allow-Methods", "GET")
        return response

    api.add_resource(Spec, "/spec")
    return api


def build_namespace(api, name, description):
    return api.namespace(name, description=description)
