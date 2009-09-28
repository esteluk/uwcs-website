from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save,post_delete
from django.db.models import Q
from datetime import timedelta,datetime

from compsoc.settings import DATE_FORMAT_STRING,SAME_SECOND_FORMAT
from compsoc.search import register
from compsoc.events import write_file_callback
from compsoc.shortcuts import flatten

TARGETS = (
    ('ACA', 'Academic'),
    ('GAM', 'Gaming'),
    ('SCL', 'Social'),
    ('SCT', 'Society'),
)

class EventType(models.Model):
    name = models.CharField(max_length=20)
    info = models.TextField()
    target = models.CharField(max_length=3, choices=TARGETS)

    def __unicode__(self):
        return self.name

class Location(models.Model):
    name = models.CharField(max_length=60)
    description = models.TextField()
    image_url = models.CharField(max_length=255, default="/static/img/no_location.png")
    map_loc = models.CharField(max_length=30, blank=True)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return "/events/location/%i/" % self.id

class Event(models.Model):
    type = models.ForeignKey(EventType)
    location = models.ForeignKey(Location)
    shortDescription = models.CharField(max_length=255)
    longDescription = models.TextField()
    start = models.DateTimeField(default=datetime.now)
    finish = models.DateTimeField(default=lambda:datetime.now() + timedelta(hours=1))
    displayFrom = models.DateTimeField(default=datetime.now)
    cancelled = models.BooleanField()

    def days(self):
        days = []
        i = self.start.date()
        end = self.finish.date()
        day = timedelta(days=1)
        while i <= end:
            days.append(i)
            i += day
        return days

    def time_string(self):
        s,f = self.start,self.finish
        if s.date() == f.date():
            return s.strftime(DATE_FORMAT_STRING)+" - "+f.strftime(SAME_SECOND_FORMAT)
        else:
            return s.strftime(DATE_FORMAT_STRING)+" - "+f.strftime(DATE_FORMAT_STRING)

    def __unicode__(self):
        return self.type.name + " @ " + self.time_string()

    def is_displayed(self):
        return datetime.now() > self.displayFrom
    
    def is_in_future(self):
        return datetime.now() < self.start

    def is_now_or_later(self):
        return datetime.now() < self.finish

    def is_in_past(self):
        return datetime.now() > self.start

    def is_running(self):
        return self.start < datetime.now() and datetime.now() < self.finish

    def has_signups(self):
        try:
            self.eventsignup
            return True
        except EventSignup.DoesNotExist:
            return False
    
    def signup_total(self):
        try:
            return self.eventsignup.signupsLimit
        except EventSignup.DoesNotExist:
            return 0

    def signup_count(self):
        try:
            return self.signup_set.count()
        except EventSignup.DoesNotExist:
            return 0

    def get_absolute_url(self):
        return "/events/details/%i/" % self.id

    def get_type_name(self):
        return self.type.name

    def last_change_time(self):
        from django.contrib.admin.models import LogEntry,ContentType
        try:
            cct = ContentType.objects.get(name='event')
            return LogEntry.objects.filter(object_id=self.pk,content_type=cct).latest('action_time').action_time.strftime(DATE_FORMAT_STRING)
        except:
            return 0

class SteamEvent(Event):
    steam_id = models.CharField(max_length=50)

def future_events(n=5):
    '''
    Generates a list of event types t and events e s.t. e is the
    next event for t.  Restricted to the next n events
    '''
    types = EventType.objects.all()
    future = []
    for type in types:
        try:
            event = type.event_set.filter(finish__gte=datetime.now()).exclude(displayFrom__gte=datetime.now()).order_by('start')[0]
        except IndexError:
            pass
        else:
            future.append((type,event))
    return sorted(future,key=lambda (t,e): e.start)[:n]

register(Event,['shortDescription','longDescription','get_type_name'],order='-start',filter=lambda: Q(displayFrom__lte=datetime.now(), cancelled=False))

post_save.connect(write_file_callback, sender=Event)
post_delete.connect(write_file_callback, sender=Event)

class SeatingRoom(models.Model):
    '''Information a room that people are sat in'''
    room = models.ForeignKey(Location)
    name = models.CharField(max_length=50)
    max_cols = models.IntegerField()
    max_rows = models.IntegerField()

    def __unicode__(self):
        return "%s @ %s" % (self.name,self.room.__unicode__())

# Signup Options seperated from Event to normalise and avoid nullable.
class EventSignup(models.Model):
    event = models.OneToOneField(Event)
    signupsLimit = models.IntegerField()
    open = models.DateTimeField()
    close = models.DateTimeField()
    fresher_open = models.DateTimeField()
    guest_open = models.DateTimeField()
    seating = models.ForeignKey(SeatingRoom,blank=True,null=True)
    
    def has_seating_plan(self):
        try:
            self.seating
            return True
        except SeatingRoom.DoesNotExist:
            return False

    def __unicode__(self):
        return self.event.__unicode__()

post_save.connect(write_file_callback, sender=EventSignup)
post_delete.connect(write_file_callback, sender=EventSignup)

class Signup(models.Model):
    event = models.ForeignKey(Event)
    time = models.DateTimeField()
    user = models.ForeignKey(User)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["time"]
        unique_together = ("event", "user")

    def __unicode__(self):
        return self.user.username

    def time_form(self):
        return self.time.strftime(DATE_FORMAT_STRING)

post_save.connect(write_file_callback, sender=Signup)
post_delete.connect(write_file_callback, sender=Signup)

class RevisionManager(models.Manager):
    def for_event(self,e):
        return self.filter(event=e).order_by('-number')

class SeatingRevision(models.Model):
    '''Information about a single seating plan revision'''
    event = models.ForeignKey(Event)
    creator = models.ForeignKey(User)
    number = models.IntegerField()
    comment = models.CharField(max_length=30)

    objects = RevisionManager()

    def __unicode__(self):
        return "%i, %s" % (self.number, self.comment)

    def prev(self):
        return SeatingRevision.objects.get(event=self.event,number=self.number-1)

    def users(self):
        return val_users(self.seating_set)

    def added(self):
        '''
        People who were added to the seating plan in the current
        revision.
        Returns an iterable of Seating Objects
        '''
        try:
            return self.seating_set.exclude(user__in=self.prev().users())
        except SeatingRevision.DoesNotExist:
            return self.seating_set.all()

    def removed(self):
        try:
            return self.prev().seating_set.exclude(user__in=self.users())
        except SeatingRevision.DoesNotExist:
            return self.seating_set.none()

    def moved(self):
        try:
            current = self.seating_set.filter(user__in=self.prev().users()).order_by('user')
            previous = self.prev().seating_set.filter(user__in=self.users()).order_by('user')
            return filter(lambda (curr,prev): curr.col != prev.col or curr.row != prev.row,zip(current,previous))
        except SeatingRevision.DoesNotExist:
            return self.seating_set.none()

    def get_absolute_url(self):
        return "/events/seating/%s/%s" % (self.event.id, self.number)

def val_users(query):
    return flatten(query.values_list('user'))

class SeatingManager(models.Manager):
    def for_event(self,e):
        return self.filter(revision__event=e)

    def maximums(self,e):
        return reduce(lambda (col,row),o: (max(col,o.col),max(row,o.row)),self.for_event(e),(0,0))

class Seating(models.Model):
    '''Information about a seat at a revision'''
    user = models.ForeignKey(User)
    revision = models.ForeignKey(SeatingRevision)
    col = models.IntegerField()
    row = models.IntegerField()

    objects = SeatingManager()

    def __unicode__(self):
        return "%s @ %i,%i" % (self.user.member.name(),self.col,self.row)

class SteamEventFeed(models.Model):
    group_name = models.CharField(max_length=30)
    event_type = models.ForeignKey(EventType)
    location = models.ForeignKey(Location)

    def __unicode__(self):
        return self.group_name
