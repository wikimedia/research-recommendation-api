import collections

import flask
import flask_restplus
from flask_restplus import fields

from recommendation.api import helper
from recommendation.web import gapfinder

api = helper.build_api('api', __name__)

TypeSpec = collections.namedtuple('Type', ['name', 'spec_path'])

type_model = api.model(TypeSpec.__name__, TypeSpec(
    name=fields.String(description='Name of the subpart'),
    spec_path=fields.String(description='Path to spec')
)._asdict())


@api.route('/types')
class Type(flask_restplus.Resource):

    @api.marshal_with(type_model, as_list=True)
    @api.doc(description='This returns the available subparts and the paths to their specs')
    def get(self):
        types = []
        for blue in flask.current_app.iter_blueprints():
            if type(blue) is flask.Blueprint and blue not in (api.blueprint, gapfinder.gapfinder):
                types.append(TypeSpec(
                    name=blue.name,
                    spec_path=flask.url_for(blue.name + '.spec')
                )._asdict())
        return types
