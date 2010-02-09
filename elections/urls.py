from django.conf.urls.defaults import *
from models import *
from django.forms import ModelForm

class VoteForm(ModelForm):
    class Meta:
        model = Vote
        fields = ('candidate', 'preference')

urlpatterns = patterns('',
    (r'^$', 'django.views.generic.list_detail.object_list', {
        'queryset':Election.objects.all(),
    }),
    #(r'^details/(?P<object_id>[^/]+)/$', 'django.views.generic.list_detail.object_detail', {
        #'queryset':Election.objects.all(),
    #}),
    (r'^details/(?P<object_id>[^/]+)/$', 'elections.views.details'),
)
