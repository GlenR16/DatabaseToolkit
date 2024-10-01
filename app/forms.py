from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import Permission

from .models import User,Company,SnowflakeConnection,Task, Connection, RedshiftConnection

class UserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email','name')

    def save(self, *args, **kwargs):
        user = super().save(commit=False)
        if Company.objects.filter(domain_name=user.email.split("@")[1]).exists():
            user.company = Company.objects.get(domain_name=user.email.split("@")[1])
        user.save()
        return user

class UserPermissionForm(forms.ModelForm):
    user_permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.filter(content_type__app_label="app").exclude(content_type__model="setting").exclude(content_type__model="company").exclude(content_type__model="user"), required=False)
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ['user_permissions','is_active']

class SnowflakeConnectionForm(forms.ModelForm):
    class Meta:
        model = SnowflakeConnection
        fields = ['name','account', 'username','password','warehouse','database','schema']

class RedshiftConnectionForm(forms.ModelForm):
    class Meta:
        model = RedshiftConnection
        fields = ['name','host','port', 'username','password','database']

class ConnectionForm:
    CONNECTION_FORMS = {
        "snowflakeconnection": SnowflakeConnectionForm,
        "redshiftconnection": RedshiftConnectionForm,
    }

class TaskCreateForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['name','type','recurrence_interval', 'run_at','connections',]
        widgets = {
            'run_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields['connections'].queryset = Connection.objects.filter(created_by__company=user.company)
