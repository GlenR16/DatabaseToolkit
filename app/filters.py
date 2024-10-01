import django_filters

from .models import Connection, Task, Company

class ConnectionFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains',label='Name')
    # filter on type which is a function in Connection model with choices
    type = django_filters.ChoiceFilter(choices=Connection.CONNECTION_TYPES,label='Type',method='filter_type')

    def filter_type(self, queryset, name, value):
        output_ids = [ x.id for x in queryset if x.type_class() == value ]
        return queryset.filter(id__in=output_ids)

    class Meta:
        model = Connection
        fields = ['name', 'type', 'created_by']

class TaskFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains',label='Name')

    class Meta:
        model = Task
        fields = ['name','type' ,'created_by']

class CompanyFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains',label='Name')

    class Meta:
        model = Company
        fields = ['name' ,]