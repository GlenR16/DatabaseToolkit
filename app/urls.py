from django.urls import path

from .views import IndexView, DocumentationView, FavicoView
from .views import LoginView, SignupView, LogoutView
from .views import ProfileView, ProfileEditView, ProfileDeleteView
from .views import ConnectionListView, ConnectionCreateView, ConnectionDetailView, ConnectionDeleteView, ConnectionEditView
from .views import CompanyListView, CompanyDetailView, CompanyUserPermissionEditView
from .views import TaskListView, TaskDetailView, TaskCreateView, TaskDeleteView, TaskEditView
from .views import ArgumentCreateView, ArgumentEditValue, ArgumentDeleteView
from .views import HistoryDetailView, HistoryCreateView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('documentation', DocumentationView.as_view(), name='documentation'),
    path('favicon.ico', FavicoView.as_view(), name='favicon'),
    # Authentication Views
    path('login', LoginView.as_view(), name='login'),
    path('signup', SignupView.as_view(), name='signup'),
    path('logout', LogoutView.as_view(), name='logout'),
    # User Profile Views
    path('profile', ProfileView.as_view(), name='profile'),
    path('profile/edit', ProfileEditView.as_view(), name='profile_edit'),
    path('profile/delete', ProfileDeleteView.as_view(), name='profile_delete'),
    # Connection Views
    path('connections', ConnectionListView.as_view(), name='connections'),
    path('connections/create', ConnectionCreateView.as_view(), name='connection_create'),
    path('connections/<int:pk>', ConnectionDetailView.as_view(), name='connection_detail'),
    path('connections/<int:pk>/edit', ConnectionEditView.as_view(), name='connection_edit'),
    path('connections/<int:pk>/delete', ConnectionDeleteView.as_view(), name='connection_delete'),
    # Company Views
    path('companies', CompanyListView.as_view(), name='companies'),
    path('companies/<int:pk>', CompanyDetailView.as_view(), name='company_detail'),
    path('companies/<int:pk>/edit/<int:user_id>', CompanyUserPermissionEditView.as_view(), name='company_user_permission_edit'),
    # Task Views
    path('tasks',TaskListView.as_view(),name='tasks'),
    path('tasks/create',TaskCreateView.as_view(),name='task_create'),
    path('tasks/<int:pk>',TaskDetailView.as_view(),name='task_detail'),
    path('tasks/<int:pk>/delete',TaskDeleteView.as_view(),name='task_delete'),
    path('tasks/<int:pk>/edit',TaskEditView.as_view(),name='task_edit'),
    # Argument Views
    path('tasks/<int:pk>/arguments/create',ArgumentCreateView.as_view(),name='argument_create'),
    path('tasks/<int:pk>/arguments/<int:arg_id>/edit',ArgumentEditValue.as_view(),name='argument_edit'),
    path('tasks/<int:pk>/arguments/<int:arg_id>/delete',ArgumentDeleteView.as_view(),name='argument_delete'),
    # History Views
    path('tasks/<int:pk>/history/<int:history_id>',HistoryDetailView.as_view(),name='history_detail'),
    path('tasks/<int:pk>/run',HistoryCreateView.as_view(),name='history_create'),

]