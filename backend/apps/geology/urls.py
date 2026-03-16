from django.urls import path
from . import views

urlpatterns = [
    # 模型接口
    path('models', views.ModelListView.as_view(), name='model-list'),
    path('models/<str:model_id>', views.ModelDetailView.as_view(), name='model-detail'),
    path('models/<str:model_id>/resource', views.ModelResourceView.as_view(), name='model-resource'),

    # 钻孔接口
    # NOTE: 'boreholes/search' MUST be registered before 'boreholes/<str:borehole_id>'
    # so that "search" is not captured as a borehole id.
    path('boreholes', views.BoreholeListView.as_view(), name='borehole-list'),
    path('boreholes/search', views.BoreholeSearchView.as_view(), name='borehole-search'),
    path('boreholes/<str:borehole_id>', views.BoreholeDetailView.as_view(), name='borehole-detail'),

    # 工作面接口
    path('workingfaces', views.WorkingFaceListView.as_view(), name='workingface-list'),
    path('workingfaces/<str:wf_id>', views.WorkingFaceDetailView.as_view(), name='workingface-detail'),

    # 统计分析接口
    path('analysis/thickness-distribution', views.AnalysisThicknessView.as_view()),
    path('analysis/borehole-depth-distribution', views.AnalysisDepthView.as_view()),
    path('analysis/workingface-status', views.AnalysisWorkingFaceStatusView.as_view()),
    path('analysis/borehole-count', views.AnalysisBoreholeCountView.as_view()),
    path('analysis/layer-frequency', views.AnalysisLayerFrequencyView.as_view()),

    # Dashboard 聚合
    path('dashboard/summary', views.DashboardSummaryView.as_view()),
]
