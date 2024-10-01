from typing import Any
from datetime import datetime, timezone
from django.db.models.base import Model as Model
from django.db.models.query import QuerySet
from django.forms.models import BaseModelForm
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.generic import TemplateView, RedirectView, FormView, DetailView, UpdateView, DeleteView, CreateView
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin,PermissionRequiredMixin
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.shortcuts import render,get_object_or_404
from django_filters.views import FilterView
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from background_task.models import Task as BackgroundTask

from .database import TASK_TYPES, CSV_SEPARATOR
from .forms import UserCreationForm, ConnectionForm, UserPermissionForm, TaskCreateForm
from .models import User, Connection, Setting, Company, Task, TaskHistory, TaskArgument
from .filters import ConnectionFilter, TaskFilter, CompanyFilter
from .tasks import task_runner

class FavicoView(RedirectView):
    url = "/static/images/favicon.ico"

class IndexView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["USER_COUNT"] = User.objects.count()
        context["COMPANY_COUNT"] = Company.objects.count()
        context["TASK_COUNT"] = TaskHistory.objects.count()
        return context

class DocumentationView(TemplateView):
    template_name = 'documentation.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["TASK_TYPES"] = TASK_TYPES
        return context

class SignupView(UserPassesTestMixin,FormView):
    template_name = "user/signup.html"
    form_class = UserCreationForm

    def form_valid(self, form):
        if Setting.load().user_registration:
            user = form.save()
            LogEntry.objects.log_action(
                user_id=user.pk,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.pk,
                object_repr=user.__str__(),
                action_flag=1,
                change_message='[{"added": {}}]'
            )
            login(self.request, user)
            return super().form_valid(form)
        form.add_error(None, "User onboarding is disabled. Please contact site administrator.")
        return self.form_invalid(form)
    
    def test_func(self):
        return not self.request.user.is_authenticated
    
    def get_success_url(self) -> str:
        return self.request.GET.get("next", "/connections")
    
class LoginView(UserPassesTestMixin,FormView):
    template_name = "user/login.html"
    form_class = AuthenticationForm

    def form_valid(self, form):
        user = authenticate(self.request, email=form.cleaned_data["username"], password=form.cleaned_data["password"])
        if user is not None:
            login(self.request, user)
            return super().form_valid(form)
        return self.form_invalid(form)
        
    def test_func(self):
        return not self.request.user.is_authenticated
    
    def get_success_url(self) -> str:
        return self.request.GET.get("next", "/connections")

class LogoutView(LoginRequiredMixin,RedirectView):
    url = '/'

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)

class ProfileView(LoginRequiredMixin,FormView):
    template_name = "user/profile.html"
    form_class = PasswordChangeForm
    success_url = "/profile"
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        update_session_auth_hash(self.request, form.user)
        return render(self.request, self.template_name, self.get_context_data(form=form, success=True))

class ProfileEditView(LoginRequiredMixin,UpdateView):
    template_name = "user/profile_edit.html"
    model = User
    fields = ["name",]
    success_url = "/profile"

    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        changed_fields = ",".join([ '"'+field+'"' for field in form.changed_data ])
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=2,
            change_message='[{"changed": {"fields": [ '+changed_fields+' ]}}]',
        )
        return super().form_valid(form)

class ProfileDeleteView(LoginRequiredMixin,DeleteView):
    template_name = "user/profile_delete.html"
    model = User
    success_url = "/logout"

    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=3,
            change_message='[{"deleted": {"name": "User", "object": "'+self.object.__str__()+'"}}]'
        )
        self.object.is_active = False
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

class ConnectionListView(LoginRequiredMixin,PermissionRequiredMixin ,FilterView):
    permission_required = "app.view_connection"
    template_name = "connections/list.html"
    filterset_class = ConnectionFilter
    model = Connection
    paginate_by = 6
    paginate_orphans = 0
    page_kwarg = "page"

    def get_queryset(self):
        return Connection.objects.filter(created_by__company=self.request.user.company).order_by("-created_at")
    
class ConnectionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "app.add_connection"
    template_name = "connections/create.html"
    model = Connection
    fields = ["name",]
    success_url = "/connections"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=1,
            change_message='[{"added": {}}]'
        )
        return response
    
    def get_form_class(self) -> type[BaseModelForm]:
        return ConnectionForm.CONNECTION_FORMS.get(self.request.GET.get("type", "snowflakeconnection"), ConnectionForm.CONNECTION_FORMS["snowflakeconnection"])
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["connection"] = self.model
        context["type"] = self.request.GET.get("type", "snowflakeconnection")
        return context
    
class ConnectionDetailView(LoginRequiredMixin, PermissionRequiredMixin,DetailView):
    permission_required = "app.view_connection"
    template_name = "connections/view.html"
    model = Connection

    def get_queryset(self):
        return Connection.objects.filter(created_by__company=self.request.user.company)
    
    def get_object(self, queryset=None):
        return super().get_object(queryset).child_model_instance()
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["logs"] = LogEntry.objects.filter(object_id=self.object.pk, content_type_id=ContentType.objects.get_for_model(self.object).id).order_by("-action_time")
        return context
    
class ConnectionEditView(LoginRequiredMixin, PermissionRequiredMixin,UpdateView):
    template_name = "connections/update.html"
    permission_required = "app.change_connection"
    model = Connection
    success_url = "/connections"

    def get_queryset(self):
        return Connection.objects.filter(created_by__company=self.request.user.company,created_by=self.request.user)
    
    def get_object(self, queryset=None):
        return super().get_object(queryset).child_model_instance()
    
    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.object.pk}"
    
    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        changed_fields = ",".join([ '"'+field+'"' for field in form.changed_data ])
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=2,
            change_message='[{"changed": {"fields": [ '+changed_fields+' ]}}]',
        )
        return super().form_valid(form)

    def get_form_class(self) -> BaseModelForm:
        return ConnectionForm.CONNECTION_FORMS.get(self.object.type_class(), ConnectionForm.CONNECTION_FORMS["snowflakeconnection"])
    
class ConnectionDeleteView(LoginRequiredMixin, PermissionRequiredMixin,DeleteView):
    template_name = "connections/delete.html"
    permission_required = "app.delete_connection"
    model = Connection
    success_url = "/connections"

    def form_valid(self, form):
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=3,
            change_message='[{"deleted": {"name": "Connection", "object": "'+self.object.__str__()+'"}}]'
        )
        return super().form_valid(form)

    def get_queryset(self):
        return Connection.objects.filter(created_by__company=self.request.user.company,created_by=self.request.user)
    
class CompanyListView(LoginRequiredMixin, FilterView):
    template_name = "companies/list.html"
    model = Company
    filterset_class = CompanyFilter
    paginate_by = 6
    paginate_orphans = 0
    page_kwarg = "page"

    def get_queryset(self):
        return self.request.user.companies_managed.all().order_by("-created_at")
    
class CompanyDetailView(LoginRequiredMixin,DetailView):
    template_name = "companies/view.html"
    model = Company

    def get_queryset(self):
        return self.request.user.companies_managed.all()
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["logs"] = LogEntry.objects.filter(user__company=self.object).order_by("-action_time")
        return context
    
class CompanyUserPermissionEditView(LoginRequiredMixin,UpdateView):
    template_name = "companies/user_permission_edit.html"
    form_class = UserPermissionForm
    success_url = "/companies"

    def get_queryset(self):
        return get_object_or_404(self.request.user.companies_managed.all(), pk=self.kwargs["pk"]).users.all()
    
    def get_object(self, queryset=None):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["user_id"])
    
    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.kwargs['pk']}"
    
class TaskListView(LoginRequiredMixin,PermissionRequiredMixin,FilterView):
    template_name = "tasks/list.html"
    permission_required = "app.view_task"
    model = Task
    filterset_class = TaskFilter
    paginate_by = 6
    paginate_orphans = 0
    page_kwarg = "page"

    def get_queryset(self) -> QuerySet[Any]:
        return Task.objects.filter(created_by__company=self.request.user.company).order_by("-created_at")
    
class TaskDetailView(LoginRequiredMixin,PermissionRequiredMixin,DetailView):
    template_name = "tasks/view.html"
    permission_required = "app.view_task"
    model = Task

    def get_queryset(self) -> QuerySet[Any]:
        return Task.objects.filter(created_by__company=self.request.user.company)
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["logs"] = LogEntry.objects.filter(object_id=self.object.pk, content_type_id=ContentType.objects.get_for_model(self.object).id).order_by("-action_time")
        return context
    
class TaskCreateView(LoginRequiredMixin,PermissionRequiredMixin,CreateView):
    template_name = "tasks/create.html"
    permission_required = "app.add_task"
    form_class = TaskCreateForm
    success_url = "/tasks"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        schedule = form.instance.run_at - datetime.now(timezone.utc)
        task_runner(form.instance.pk, "AUTO", schedule=schedule , repeat=form.instance.recurrence_interval, repeat_until=None,verbose_name=form.instance.pk, creator=self.request.user)
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=1,
            change_message='[{"added": {}}]'
        )
        return response
    
    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["TASK_TYPES"] = TASK_TYPES
        return context

class TaskEditView(LoginRequiredMixin,PermissionRequiredMixin,UpdateView):
    template_name = "tasks/update.html"
    permission_required = "app.change_task"
    model = Task
    fields = ["name", "type","connections"]
    success_url = "/tasks"

    def get_queryset(self):
        return Task.objects.filter(created_by__company=self.request.user.company,created_by=self.request.user)
    
    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.object.pk}"
    
    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        changed_fields = ",".join([ '"'+field+'"' for field in form.changed_data ])
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=2,
            change_message='[{"changed": {"fields": [ '+changed_fields+' ]}}]',
        )
        return super().form_valid(form)
    
class TaskDeleteView(LoginRequiredMixin,PermissionRequiredMixin,DeleteView):
    template_name = "tasks/delete.html"
    permission_required = "app.delete_task"
    model = Task
    success_url = "/tasks"

    def get_queryset(self):
        return Task.objects.filter(created_by__company=self.request.user.company,created_by=self.request.user)
    
    def form_valid(self, form):
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=3,
            change_message='[{"deleted": {"name": "Task", "object": "'+self.object.__str__()+'"}}]'
        )
        BackgroundTask.objects.filter(verbose_name=self.object.pk).delete()
        return super().form_valid(form)
    
class ArgumentCreateView(LoginRequiredMixin,PermissionRequiredMixin,CreateView):
    template_name = "arguments/create.html"
    permission_required = "app.add_taskargument"
    model = TaskArgument
    fields = ["name","value"]
    success_url = "/tasks"

    def form_valid(self, form):
        form.instance.task = get_object_or_404(Task, pk=self.kwargs["pk"])
        response = super().form_valid(form)
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=1,
            change_message='[{"added": {}}]'
        )
        return response
    
    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.kwargs['pk']}"
    
class ArgumentEditValue(LoginRequiredMixin,PermissionRequiredMixin,UpdateView):
    template_name = "arguments/update.html"
    permission_required = "app.change_taskargument"
    model = TaskArgument
    fields = ["name","value"]
    success_url = "/tasks"

    def get_queryset(self):
        return TaskArgument.objects.filter(task__created_by__company=self.request.user.company)
    
    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.object.task.pk}"
    
    def get_object(self, queryset: QuerySet[Any] = None) -> Model:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["arg_id"])
    
    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        changed_fields = ",".join([ '"'+field+'"' for field in form.changed_data ])
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=2,
            change_message='[{"changed": {"fields": [ '+changed_fields+' ]}}]',
        )
        return super().form_valid(form)

class ArgumentDeleteView(LoginRequiredMixin,PermissionRequiredMixin,DeleteView):
    template_name = "arguments/delete.html"
    permission_required = "app.delete_taskargument"
    model = TaskArgument
    success_url = "/tasks"

    def get_queryset(self):
        return TaskArgument.objects.filter(task__created_by__company=self.request.user.company)
    
    def get_object(self, queryset: QuerySet[Any] = None) -> Model:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["arg_id"])

    def form_valid(self, form):
        LogEntry.objects.log_action(
            user_id=self.request.user.pk,
            content_type_id=ContentType.objects.get_for_model(self.object).pk,
            object_id=self.object.pk,
            object_repr=self.object.__str__(),
            action_flag=3,
            change_message='[{"deleted": {"name": "Task Argument", "object": "'+self.object.__str__()+'"}}]'
        )
        return super().form_valid(form)
    
    def get_success_url(self) -> str:
        return super().get_success_url() + f"/{self.object.task.pk}"

class HistoryDetailView(LoginRequiredMixin,PermissionRequiredMixin,DetailView):
    template_name = "history/view.html"
    permission_required = "app.view_taskhistory"
    model = TaskHistory

    def get_queryset(self):
        return TaskHistory.objects.filter(task__created_by__company=self.request.user.company)
    
    def get_object(self, queryset: QuerySet[Any] | None = ...) -> Model:
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["history_id"])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["CSV_SEPARATOR"] = CSV_SEPARATOR
        context["logs"] = LogEntry.objects.filter(object_id=self.object.pk, content_type_id=ContentType.objects.get_for_model(self.object).id).order_by("-action_time")
        return context
    
class HistoryCreateView(LoginRequiredMixin,PermissionRequiredMixin,RedirectView):
    permission_required = "app.add_taskhistory"
    url = "/tasks"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        task = get_object_or_404(Task, pk=self.kwargs["pk"], created_by__company=self.request.user.company)
        task_runner(task.pk, "MANUAL", schedule=0, repeat=0, repeat_until=None,verbose_name=task.pk, creator=self.request.user)
        return super().get(request, *args, **kwargs)
    
    def get_redirect_url(self, *args: Any, **kwargs: Any) -> str | None:
        return super().get_redirect_url(*args, **kwargs) + f"/{self.kwargs['pk']}?ran=true"
    