from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from apps.common.response import success, error
from .services import model_service, borehole_excel_service, workingface_service, analysis_service


@method_decorator(csrf_exempt, name='dispatch')
class ModelListView(View):
    def get(self, request):
        model_type = request.GET.get('type')
        keyword = request.GET.get('keyword')
        data = model_service.get_model_list(model_type=model_type, keyword=keyword)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class ModelDetailView(View):
    def get(self, request, model_id):
        data = model_service.get_model_detail(model_id)
        if not data:
            return error(f"Model {model_id} not found", code=404, status=404)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class ModelResourceView(View):
    def get(self, request, model_id):
        data = model_service.get_model_resource(model_id)
        if not data:
            return error(f"Model {model_id} not found", code=404, status=404)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class BoreholeListView(View):
    def get(self, request):
        keyword = request.GET.get('keyword')
        min_depth = request.GET.get('min_depth')
        max_depth = request.GET.get('max_depth')
        data = borehole_excel_service.get_borehole_list(
            keyword=keyword, min_depth=min_depth, max_depth=max_depth
        )
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class BoreholeDetailView(View):
    def get(self, request, borehole_id):
        data = borehole_excel_service.get_borehole_detail(borehole_id)
        if not data:
            return error(f"Borehole {borehole_id} not found", code=404, status=404)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class BoreholeSearchView(View):
    def get(self, request):
        keyword = request.GET.get('keyword', '')
        data = borehole_excel_service.search_boreholes(keyword)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class WorkingFaceListView(View):
    def get(self, request):
        keyword = request.GET.get('keyword')
        status = request.GET.get('status')
        data = workingface_service.get_workingface_list(keyword=keyword, status=status)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class WorkingFaceDetailView(View):
    def get(self, request, wf_id):
        data = workingface_service.get_workingface_detail(wf_id)
        if not data:
            return error(f"WorkingFace {wf_id} not found", code=404, status=404)
        return success(data)


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisThicknessView(View):
    def get(self, request):
        return success(analysis_service.get_thickness_distribution())


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisDepthView(View):
    def get(self, request):
        return success(analysis_service.get_borehole_depth_distribution())


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisWorkingFaceStatusView(View):
    def get(self, request):
        return success(analysis_service.get_workingface_status())


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisBoreholeCountView(View):
    def get(self, request):
        return success(analysis_service.get_borehole_count())


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisLayerFrequencyView(View):
    def get(self, request):
        return success(analysis_service.get_layer_frequency_stats())


@method_decorator(csrf_exempt, name='dispatch')
class AnalysisBoreholeXYRawView(View):
    def get(self, request):
        return success(analysis_service.get_borehole_xy_positions_raw())


@method_decorator(csrf_exempt, name='dispatch')
class DashboardSummaryView(View):
    def get(self, request):
        return success(analysis_service.get_dashboard_summary())
