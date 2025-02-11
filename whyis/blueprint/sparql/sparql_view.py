import requests
from flask import request, redirect, url_for, current_app, Response

from whyis.blueprint.sparql import sparql_blueprint
from whyis.decorator import conditional_login_required


@sparql_blueprint.route('/sparql', methods=['GET', 'POST'])
@conditional_login_required
def sparql_view():
    has_query = False
    for arg in list(request.args.keys()):
        if arg.lower() == "update":
            return "Update not allowed.", 403
        if arg.lower() == 'query':
            has_query = True
    if request.method == 'GET' and not has_query:
        return redirect(url_for('.sparql_form'))
    #print self.db.store.query_endpoint
    if request.method == 'GET':
        headers = {}
        headers.update(request.headers)
        if 'Content-Length' in headers:
            del headers['Content-Length']
        req = requests.get(current_app.db.store.query_endpoint,
                           headers = headers, params=request.args)
    elif request.method == 'POST':
        if 'application/sparql-update' in request.headers['content-type']:
            return "Update not allowed.", 403
        #print(request.get_data())
        req = requests.post(current_app.db.store.query_endpoint, data=request.get_data(),
                            headers = request.headers, params=request.args)
    #print self.db.store.query_endpoint
    #print req.status_code
    response = Response(req.content, content_type = req.headers['content-type'])
    #response.headers[con(req.headers)
    return response, req.status_code
