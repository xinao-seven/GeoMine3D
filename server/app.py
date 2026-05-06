from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from config import DATA_DIR, STATIC_DIR, DEBUG, SECRET_KEY
from services import borehole_excel_service, model_service, workingface_service, analysis_service


def success(data=None, message="success"):
    return jsonify({"code": 0, "message": message, "data": data})


def error(message="error", code=1, status=200):
    return jsonify({"code": code, "message": message, "data": None}), status


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    CORS(app)

    # -----------------------------------------------------------------------
    # Static & data file serving
    # -----------------------------------------------------------------------
    @app.route('/static/<path:path>')
    def serve_static(path):
        return send_from_directory(STATIC_DIR, path)

    @app.route('/data/<path:path>')
    def serve_data(path):
        return send_from_directory(DATA_DIR, path)

    # -----------------------------------------------------------------------
    # Model routes
    # -----------------------------------------------------------------------
    @app.route('/api/models')
    def model_list():
        model_type = request.args.get('type')
        keyword = request.args.get('keyword')
        return success(model_service.get_model_list(model_type=model_type, keyword=keyword))

    @app.route('/api/models/<model_id>')
    def model_detail(model_id):
        data = model_service.get_model_detail(model_id)
        if not data:
            return error(f"Model {model_id} not found", 404, 404)
        return success(data)

    @app.route('/api/models/<model_id>/resource')
    def model_resource(model_id):
        data = model_service.get_model_resource(model_id)
        if not data:
            return error(f"Model {model_id} not found", 404, 404)
        return success(data)

    # -----------------------------------------------------------------------
    # Borehole routes
    # -----------------------------------------------------------------------
    @app.route('/api/boreholes/search')
    def borehole_search():
        keyword = request.args.get('keyword', '')
        return success(borehole_excel_service.search_boreholes(keyword))

    @app.route('/api/boreholes')
    def borehole_list():
        keyword = request.args.get('keyword')
        min_depth = request.args.get('min_depth')
        max_depth = request.args.get('max_depth')
        return success(borehole_excel_service.get_borehole_list(
            keyword=keyword, min_depth=min_depth, max_depth=max_depth
        ))

    @app.route('/api/boreholes/<borehole_id>')
    def borehole_detail(borehole_id):
        data = borehole_excel_service.get_borehole_detail(borehole_id)
        if not data:
            return error(f"Borehole {borehole_id} not found", 404, 404)
        return success(data)

    # -----------------------------------------------------------------------
    # Working face routes
    # -----------------------------------------------------------------------
    @app.route('/api/workingfaces')
    def workingface_list():
        keyword = request.args.get('keyword')
        status = request.args.get('status')
        return success(workingface_service.get_workingface_list(keyword=keyword, status=status))

    @app.route('/api/workingfaces/<wf_id>')
    def workingface_detail(wf_id):
        data = workingface_service.get_workingface_detail(wf_id)
        if not data:
            return error(f"WorkingFace {wf_id} not found", 404, 404)
        return success(data)

    # -----------------------------------------------------------------------
    # Analysis routes
    # -----------------------------------------------------------------------
    @app.route('/api/analysis/thickness-distribution')
    def analysis_thickness():
        return success(analysis_service.get_thickness_distribution())

    @app.route('/api/analysis/borehole-depth-distribution')
    def analysis_depth():
        return success(analysis_service.get_borehole_depth_distribution())

    @app.route('/api/analysis/workingface-status')
    def analysis_workingface_status():
        return success(analysis_service.get_workingface_status())

    @app.route('/api/analysis/borehole-count')
    def analysis_borehole_count():
        return success(analysis_service.get_borehole_count())

    @app.route('/api/analysis/layer-frequency')
    def analysis_layer_frequency():
        return success(analysis_service.get_layer_frequency_stats())

    @app.route('/api/analysis/borehole-xy-raw')
    def analysis_borehole_xy_raw():
        return success(analysis_service.get_borehole_xy_positions_raw())

    # -----------------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------------
    @app.route('/api/dashboard/summary')
    def dashboard_summary():
        return success(analysis_service.get_dashboard_summary())

    # -----------------------------------------------------------------------
    # Error handlers
    # -----------------------------------------------------------------------
    @app.errorhandler(404)
    def handle_404(e):
        return error("Not Found", 404, 404)

    @app.errorhandler(500)
    def handle_500(e):
        return error("Internal Server Error", 500, 500)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=DEBUG)
