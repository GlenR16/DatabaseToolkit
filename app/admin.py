from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.admin.models import LogEntry
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from .models import User, SnowflakeConnection, Company, Setting, Task,TaskArgument, TaskHistory, Connection, RedshiftConnection

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "domain_name", "manager","created_at")
    search_fields = ("name__startswith",)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "company", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff","is_active","is_superuser","company")
    search_fields = ("email__startswith",)
    readonly_fields = ("password",)

@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "type", "created_at")
    list_filter = ("created_by__company",)
    search_fields = ("name__startswith",)

@admin.register(SnowflakeConnection)
class SnowflakeConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "type", "created_at")
    list_filter = ("created_by__company",)
    search_fields = ("name__startswith",)

@admin.register(RedshiftConnection)
class RedshiftConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "type", "created_at")
    list_filter = ("created_by__company",)
    search_fields = ("name__startswith",)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    list_filter = ("created_by__company",)
    search_fields = ("name__startswith",)

@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ("task", "status", "started_at")
    list_filter = ("status","task")
    search_fields = ("task__name__startswith",)

@admin.register(TaskArgument)
class TaskArgumentAdmin(admin.ModelAdmin):
    list_display = ("task", "name", "value")
    search_fields = ("task__name__startswith",)

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "content_type", "codename")
    list_filter = ("content_type",)
    search_fields = ("name__startswith",)
    
@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("user_registration","created_at", "updated_at")

@admin.register(ContentType)
class ContentType(admin.ModelAdmin):
    list_display = ("app_label", "app_labeled_name")
    search_fields = ("app_label__startswith",)

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("object_repr", "action_time", "user", "content_type", "action_flag")
    list_filter = ("action_time","action_flag")
    search_fields = ("user__email__startswith",)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    def email(self,obj):
        return get_object_or_404(User,id=obj.get_decoded().get("_auth_user_id","")).email
    email.short_description = "User Email"
    list_display = ("session_key","email")
    search_fields = ("session_key__startswith",)
    readonly_fields = ("session_key","session_data","expire_date")
